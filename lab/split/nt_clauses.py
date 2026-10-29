#!/usr/bin/env python3
"""The Greek NT clause by clause, for an aligner that works clause by clause (user 2026-10-27: never verse by verse).

    /usr/bin/python3 lab/split/nt_clauses.py <OUT DIR> [--max 30] [--min 3]

From orig/grc.sqlite: MACULA Greek's syntax trees (Clear Bible, CC BY 4.0) on the Berean Greek Bible's token keys (the keys
lexeme-aligner's NT layers use). Writes per book `clauses/<BOOK>.jsonl`, one row per clause:

  clause      the MACULA node id of the clause (unique in the book)
  parent      the nearest clause above it (null for a sentence's top clause); sentence: the top clause of its tree
  depth       clauses above it; rule, clausetype: MACULA's (P-VC-S, Conj3CL, ...; clausetype where MACULA gives one)
  ref         the verse of its first word ("MRK 1:4"; a clause may run across verses: see first_ref / last_ref)
  words       the BGB token keys whose nearest clause this is, in text order (its own words, not its sub-clauses')
  n_words, n_subtree   its own words; with all its sub-clauses
  group       the request unit proposed for an aligner: the clause itself, with its sub-clauses of fewer than --min words
              (an article or a one-word participle on its own) inside it; a unit of fewer than 2 * --min words joins the next
              unit of its sentence (at most 3 clauses that stand on their own, at most --max words). So a unit is one clause,
              or 2-3 clauses of one sentence when one alone is too short to be linked on its own.

and `groups/<BOOK>.jsonl`, one row per group: group, sentence, clauses, words (in text order), n_words, first_ref, last_ref."""
import collections, json, os, sqlite3, sys
R = os.environ["MAKE_TANAKH_WORK"]


def main():
    out = sys.argv[1]
    a = sys.argv[2:]
    MAX = int(a[a.index("--max") + 1]) if "--max" in a else 30
    MIN = int(a[a.index("--min") + 1]) if "--min" in a else 3
    g = sqlite3.connect(os.path.join(R, "orig", "grc.sqlite"))
    commit = dict(g.execute("select name, value from meta")).get("macula_greek")
    nodes = {r[0]: r for r in g.execute("select id, book, ch, v, parent, class, rule, clausetype from nodes")}
    words = collections.defaultdict(list)
    ref_of = {}
    order = {}
    for i, (key, book, ch, v, cl) in enumerate(g.execute("select key, book, ch, v, clause from tokens order by key")):
        order[key] = i; ref_of[key] = f"{book} {ch}:{v}"
        if cl:
            words[cl].append(key)
    def up(n):   # the nearest clause above node n
        p = nodes[n][4]
        while p and nodes[p][5] != "cl":
            p = nodes[p][4]
        return p
    clauses = {n for n in words} | {n for n, r in nodes.items() if r[5] == "cl"}
    par = {c: up(c) if c in nodes else None for c in clauses}
    kids = collections.defaultdict(list)
    for c, p in par.items():
        if p:
            kids[p].append(c)
    sub = {}
    def size(c):
        if c not in sub:
            sub[c] = len(words[c]) + sum(size(k) for k in kids[c])
        return sub[c]
    group = {}
    def assign(c, gid=None):
        if gid is not None:
            group[c] = gid
            for k in kids[c]:
                assign(k, gid)
            return
        group[c] = c
        for k in kids[c]:
            assign(k, c if size(k) < MIN else None)
    tops = [c for c in clauses if not par[c]]
    for t in tops:
        assign(t)
    top = {}
    def sent(c):
        if c not in top:
            top[c] = c if not par[c] else sent(par[c])
        return top[c]
    by_book = collections.defaultdict(list)
    for c in clauses:
        if not words[c] and not kids[c]:
            continue
        ws = sorted(words[c], key=order.get)
        allw = ws or [w for k in kids[c] for w in words[k]]
        first = min(allw, key=order.get) if allw else None
        d, p = 0, par[c]
        while p:
            d += 1; p = par[p]
        r = nodes.get(c)
        by_book[c.split(".")[0]].append({
            "clause": c, "parent": par[c], "sentence": sent(c), "depth": d, "rule": r[6] if r else None,
            "clausetype": r[7] if r else None, "ref": ref_of.get(first), "first_ref": ref_of.get(ws[0]) if ws else None,
            "last_ref": ref_of.get(ws[-1]) if ws else None, "words": ws, "n_words": len(ws), "n_subtree": size(c),
            "group": group[c], "_o": order.get(first, 0)})
    os.makedirs(os.path.join(out, "clauses"), exist_ok=True); os.makedirs(os.path.join(out, "groups"), exist_ok=True)
    tot = collections.Counter()
    for book, rows in by_book.items():
        rows.sort(key=lambda x: x["_o"])
        gr = collections.OrderedDict()
        for x in rows:
            G = gr.setdefault(x["group"], {"group": x["group"], "sentence": x["sentence"], "clauses": [], "words": []})
            G["clauses"].append(x["clause"]); G["words"] += x["words"]
        # a short group (< 2 * --min words: "ἐγένετο Ἰωάνης") joins the next group of the same sentence when both fit in --max
        gl = list(gr.values()); merged = []
        for G in gl:
            P = merged[-1] if merged else None
            if P and P["sentence"] == G["sentence"] and (len(P["words"]) < 2 * MIN or len(G["words"]) < 2 * MIN) \
                    and len(P["words"]) + len(G["words"]) <= MAX and P.get("_n", 1) < 3:
                P["clauses"] += G["clauses"]; P["words"] += G["words"]; P.setdefault("_ids", [P["group"]]).append(G["group"])
                P["_n"] = P.get("_n", 1) + 1
            else:
                merged.append(G)
        ren = {}
        for G in merged:
            for i in G.pop("_ids", []):
                ren[i] = G["group"]
        for x in rows:
            x["group"] = ren.get(x["group"], x["group"])
        for G in merged:
            G.pop("_n", None)
        gr = collections.OrderedDict((G["group"], G) for G in merged)
        with open(os.path.join(out, "clauses", f"{book}.jsonl"), "w", encoding="utf-8") as f:
            for x in rows:
                x.pop("_o"); f.write(json.dumps(x, ensure_ascii=False) + "\n")
        with open(os.path.join(out, "groups", f"{book}.jsonl"), "w", encoding="utf-8") as f:
            for G in gr.values():
                G["words"].sort(key=order.get)
                G.update(n_words=len(G["words"]), first_ref=ref_of.get(G["words"][0]) if G["words"] else None,
                         last_ref=ref_of.get(G["words"][-1]) if G["words"] else None)
                f.write(json.dumps(G, ensure_ascii=False) + "\n")
                tot["groups"] += 1; tot["group_words"] += G["n_words"]; tot["max"] = max(tot["max"], G["n_words"])
        tot["clauses"] += len(rows); tot["words"] += sum(x["n_words"] for x in rows)
    json.dump({"source": "orig/grc.sqlite", "macula_greek": commit, "max": MAX, "min": MIN, **tot},
              open(os.path.join(out, "BUILD.json"), "w"), indent=1)
    print(dict(tot), "mean words per group", round(tot["group_words"] / tot["groups"], 1))


if __name__ == "__main__":
    main()
