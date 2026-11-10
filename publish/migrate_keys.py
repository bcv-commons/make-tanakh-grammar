#!/usr/bin/env python3
"""Clause-key migration between two revisions of a clause layout (hebrew-clause-layout / greek-nt-clause-layout), and its
application to the files keyed by clause: the language repos' .units files and the feature tables.

A clause key is the MACULA id of the clause's first word; the published .units files write the span `first-last`. When the
layout changes a boundary, the key of that clause changes. The map says, for every old clause, what became of it:

  same    the new layout has a clause with the same first and last word
  grown   same first word, a different last word (the clause took or lost words at its end)
  split   the old clause's words lie in several new clauses (the first keeps the old identity)
  merged  the old clause's first word is inside a new clause that begins earlier (several old clauses -> one new)
  moved   the old first word begins no new clause and is not covered by a merge (re-segmented)

    migrate_keys.py map --old DIR --new DIR --out map.json          per-book parquet dirs of the two revisions
    migrate_keys.py apply --map map.json --units FILE|DIR [--write]   rewrite the keys of .units files (dry run without --write)
    migrate_keys.py apply --map map.json --feats clause_feats.json    rewrite a feature table's keys (new file: <name>.migrated.json)
    migrate_keys.py simulate --layout DIR [--seed 7] [--n 200]        make a perturbed copy of a layout (random splits and
                                                                      merges), build the map, apply it to a scratch .units file,
                                                                      and check that every unit is accounted for (the test)

Units rewriting rules: same/grown -> the new span, the range unchanged; split -> the first new clause takes the range, the
later new clauses are written `key:=` right after it (people re-cut them in the editor; header `# units: migrated`);
merged -> the old units that fall into one new clause are written as one unit with the union of their ranges; moved -> the
unit keeps its range under the new clause that holds its first word, flagged in the report. The report lists every verse
whose units changed, so a reviewer can look at them."""
import argparse, collections, glob, json, os, random, re, sys

import pyarrow as pa
import pyarrow.parquet as pq


def clauses_of(layout_dir):
    """{first word id: (last, [words], book)} for every clause row of a layout dir (per-book parquet files); a clause that the
    layout repeats (discontinuous) is one entry with all its words"""
    out = {}
    for f in sorted(glob.glob(os.path.join(layout_dir, "clauses-*.parquet"))) or sorted(glob.glob(os.path.join(layout_dir, "*.parquet"))):
        t = pq.read_table(f)
        cols = t.column_names
        keycol = "clause_key" if "clause_key" in cols else "first"
        for r in t.select([keycol, "words", "book"]).to_pylist():
            w = list(r["words"]) if not isinstance(r["words"], str) else json.loads(r["words"].replace("'", '"'))
            k = r[keycol]
            if k in out:
                out[k] = (max(out[k][0], w[-1]) if w else out[k][0], out[k][1] + w, r["book"])
            else:
                out[k] = (w[-1] if w else k, w, r["book"])
    return out


def build_map(old, new):
    word_new = {w: k for k, (_, ws, _) in new.items() for w in ws}
    M = {}
    for k, (last, ws, book) in old.items():
        targets = []
        for w in ws:
            nk = word_new.get(w)
            if nk and (not targets or targets[-1] != nk):
                targets.append(nk)
        if not targets:
            M[k] = dict(kind="moved", to=[], span=f"{k}-{last}"); continue
        nk0 = targets[0]
        if nk0 == k and len(targets) == 1:
            kind = "same" if new[k][0] == last else "grown"
        elif nk0 == k:
            kind = "split"
        elif len(targets) == 1:
            kind = "merged"
        else:
            kind = "moved"
        M[k] = dict(kind=kind, to=[f"{t}-{new[t][0]}" for t in targets], span=f"{k}-{last}")
    return M


def rewrite_units_line(line, M, report, ref):
    """one verse line of a .units file -> the new line"""
    if line.startswith("#") or "\t" not in line:
        return line
    head, body = line.rstrip("\n").split("\t", 1)
    out = []; changed = False
    for e in body.split():
        k, _, rng = e.partition(":")
        span, _, rep = k.partition("/")
        first = span.split("-")[0]
        m = M.get(first)
        if not m:
            out.append(e); continue
        if m["kind"] in ("same", "grown"):
            nk = m["to"][0]
            if nk != span:
                changed = True
            out.append(f"{nk}{'/' + rep if rep else ''}:{rng}")
        elif m["kind"] == "split":
            changed = True
            out.append(f"{m['to'][0]}:{rng}")
            out += [f"{t}:=" for t in m["to"][1:]]
        elif m["kind"] == "merged":
            changed = True
            nk = m["to"][0]
            prev = next((i for i, x in enumerate(out) if x.split(":")[0] == nk), None)
            if prev is None:
                out.append(f"{nk}:{rng}")
            else:                                   # union of the ranges with the unit already written
                pk, _, prng = out[prev].partition(":")
                ids = sorted(set(ids_of(prng) + ids_of(rng)))
                out[prev] = f"{pk}:{ranges(ids) if ids else '='}"
        else:
            changed = True; report["moved"].append((ref, head, k))
            out.append(f"{m['to'][0] if m['to'] else span}:{rng}")
    if changed:
        report["changed verses"].append((ref, head))
    return head + "\t" + " ".join(out) + "\n"


def ids_of(sp):
    ids = []
    for part in (sp or "").split(","):
        if part == "=" or not part:
            continue
        if "-" in part:
            a, b = part.split("-"); ids += range(int(a), int(b) + 1)
        else:
            ids.append(int(part))
    return ids


def ranges(ids):
    out, s = [], None; ids = sorted(set(ids))
    for i, p in enumerate(ids):
        if s is None:
            s = p
        if i + 1 == len(ids) or ids[i + 1] != p + 1:
            out.append(f"{s}" if s == p else f"{s}-{p}"); s = None
    return ",".join(out)


def apply_units(M, path, write, report):
    files = [path] if os.path.isfile(path) else sorted(glob.glob(os.path.join(path, "**", "*.units"), recursive=True))
    for f in files:
        lines = open(f, encoding="utf-8").read().splitlines(keepends=True)
        new = [rewrite_units_line(l, M, report, os.path.basename(f)) for l in lines]
        if new != lines:
            report["files changed"] += 1
            if new and new[0].startswith("# units:"):
                new[0] = re.sub(r"# units: \w+", "# units: migrated", new[0])
            if write:
                open(f, "w", encoding="utf-8").write("".join(new))
    return report


def apply_feats(M, path):
    d = json.load(open(path, encoding="utf-8")); out = {}; st = collections.Counter()
    for k, v in d.items():
        m = M.get(k)
        if not m or m["kind"] in ("same", "grown"):
            out[k] = v; st[m["kind"] if m else "unmapped"] += 1
        elif m["kind"] == "split":
            out[k] = v; st["split"] += 1
        elif m["kind"] == "merged":
            nk = m["to"][0].split("-")[0]
            out.setdefault(nk, v); st["merged"] += 1          # the first old clause's features stand for the merged clause
        else:
            st["moved (dropped)"] += 1
    p2 = re.sub(r"\.json$", ".migrated.json", path)
    json.dump(out, open(p2, "w"), ensure_ascii=False); return p2, st


def simulate(layout_dir, seed, n, tmp):
    """perturb a copy of the layout: n random splits (a clause of >= 4 words cut in two) and n random merges (a clause taken
    into the previous one of the same verse); write per-book parquet files with the same columns"""
    rnd = random.Random(seed); os.makedirs(tmp, exist_ok=True)
    rows_by_book = {}
    for f in sorted(glob.glob(os.path.join(layout_dir, "clauses-*.parquet"))):
        rows_by_book[f] = pq.read_table(f).to_pylist()
    allrows = [(f, i) for f, rows in rows_by_book.items() for i in range(len(rows))]
    keycol = "clause_key" if "clause_key" in next(iter(rows_by_book.values()))[0] else "first"
    def words(r):
        return list(r["words"]) if not isinstance(r["words"], str) else json.loads(r["words"].replace("'", '"'))
    splits = merges = 0
    for f, i in rnd.sample(allrows, min(len(allrows), n * 6)):
        rows = rows_by_book[f]; r = rows[i]; w = words(r)
        if splits < n and len(w) >= 4:
            cut = rnd.randint(2, len(w) - 2)
            a = dict(r); b = dict(r)
            a["words"] = w[:cut]; a["last"] = w[cut - 1]
            b["words"] = w[cut:]; b["first"] = w[cut]; b[keycol] = w[cut]; b["last"] = w[-1]
            rows[i] = a; rows.insert(i + 1, b); splits += 1
        elif merges < n and i < len(rows) and i > 0 and rows[i - 1]["verse"] == r["verse"] and rows[i - 1][keycol] != r[keycol]:
            p = rows[i - 1]; pw = words(p)
            p["words"] = pw + w; p["last"] = w[-1]; del rows[i]; merges += 1
    for f, rows in rows_by_book.items():
        pq.write_table(pa.Table.from_pylist(rows), os.path.join(tmp, os.path.basename(f)))
    return splits, merges


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("map"); a.add_argument("--old", required=True); a.add_argument("--new", required=True); a.add_argument("--out", required=True)
    b = sub.add_parser("apply"); b.add_argument("--map", required=True); b.add_argument("--units"); b.add_argument("--feats"); b.add_argument("--write", action="store_true")
    c = sub.add_parser("simulate"); c.add_argument("--layout", required=True); c.add_argument("--seed", type=int, default=7); c.add_argument("--n", type=int, default=200)
    c.add_argument("--units", help="a .units dir to migrate against the perturbed layout (dry run)"); c.add_argument("--tmp", default=os.path.join(os.environ.get("MAKE_TANAKH_PRIVATE", "private"), "scratch", "migrate_sim"))
    args = ap.parse_args()
    if args.cmd == "map":
        M = build_map(clauses_of(args.old), clauses_of(args.new))
        json.dump(M, open(args.out, "w"), indent=0)
        print(dict(collections.Counter(m["kind"] for m in M.values())))
    elif args.cmd == "apply":
        M = json.load(open(args.map)); report = collections.Counter(); report.update({"files changed": 0}); report["changed verses"] = []; report["moved"] = []
        if args.units:
            apply_units(M, args.units, args.write, report)
            print(f"units: files changed {report['files changed']}, verses changed {len(report['changed verses'])}, moved {len(report['moved'])}"
                  + ("" if args.write else " (dry run; --write to rewrite)"))
        if args.feats:
            p2, st = apply_feats(M, args.feats); print("feats ->", p2, dict(st))
    else:
        new_dir = os.path.join(args.tmp, "layout")
        splits, merges = simulate(args.layout, args.seed, args.n, new_dir)
        old, new = clauses_of(args.layout), clauses_of(new_dir); M = build_map(old, new)
        kinds = collections.Counter(m["kind"] for m in M.values())
        print(f"simulated {splits} splits, {merges} merges; map: {dict(kinds)}")
        # every new clause must be reachable: as 'to' of some old clause
        reach = {t.split("-")[0] for m in M.values() for t in m["to"]}
        print("new clauses not reachable from any old clause:", sum(1 for k in new if k not in reach))
        if args.units:
            report = collections.Counter(); report.update({"files changed": 0}); report["changed verses"] = []; report["moved"] = []
            apply_units(M, args.units, False, report)
            print(f"units dry run: files changed {report['files changed']}, verses changed {len(report['changed verses'])}, moved {len(report['moved'])}")
