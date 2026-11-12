#!/usr/bin/env python3
"""The derived files of a bundle (internal-docs/review-feedback-data-plan-2026-11-10.md, sections 3.3, 3.5, 3.10; agreed with
the review project 2026-11-10: derived files carry no `# text` hash, a stale row is a notice, we rebuild them per revision).

  <BOOK>_<CCC>.parts            every token's pieces, for the main draft and each alternative:
                                    # parts: make-tanakh-parts/1; splitter <file>@<sha256 12> ...; unicode <version>
                                    c:v<TAB><verse hash><TAB>0=<piece>|<piece><TAB>1=<piece> ...
                                a piece is `<text>:<slot>[:<morph id>]`, a tone piece `:tone[:<label>]@<pos>:<mark>;...`
                                (pos counted in letters from the word's end, as bcv-split); slot = whole | stem | p<n> |
                                s<n> | i<n> (prefix, suffix, infix and their position) | tone. The pieces of a token rebuild
                                the word as written; the standard tokeniser gives the token from it. Verse hash: the first
                                8 hex of sha256("c:v<TAB>text"). The split is the language's splitter on the drafts, taken
                                from the bundle's alignment run (publish/align.py, step split).
  .tanakh/runs/<BOOK>_<CCC>.json   per kind of draft: the run that made it (label, model, prompts' sha256, code commit,
                                the register's revision and sha256 at draft time, built), so an edit is tied to the draft it corrected; "main" names the main draft's kind (always
                                "main"; the other kinds are the alternatives)
  .tanakh/clause-features.json  a pointer, not values (the user, 2026-11-10: the columns are CC BY-SA, the repository CC0): the
                                published dataset bcv-commons/clause-columns at its pinned revision, keyed by the clause keys
                                of .units, and the columns that "clauses like this" and the rules' `when` use
  .tanakh/glosses.json          FORMAT.md section 8 (make-tanakh-glosses/1): per Hebrew lexeme the forms of the main drafts'
                                .align links (content and function words), lower case, commonest first, at most 8

    . ./env.sh; python3 publish/derived.py --lang kvg --bundle private/publish/kvg/bundle-jos   (bundle.py calls it)"""
import argparse, collections, glob, hashlib, json, os, re, sys, unicodedata as ud

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import paths, pins  # noqa: E402
from publish import align as AL, chapter_format as CF  # noqa: E402
FA = CF.FA

PARTS_FORMAT = "make-tanakh-parts/1"
CLAUSE_COLUMNS = {"repo": "bcv-commons/clause-columns", "type": "dataset", "revision": "8a132e44224c83cdaa92fadd93cf440c58552354",
                  "file": "data/hebrew.parquet", "sha256": "9dcee6765f5ea947fe8d1e0e5be2a9a75b00cf4e82e537d672e06c845826c7bc",
                  "layout": "bcv-commons/hebrew-clause-layout@514a88320ab6556e0f7fd2e686c9637fcf39bd62", "licence": "CC BY-SA 4.0"}
SIMILAR = ("force", "neg", "voice", "person", "number", "line", "speech", "conj", "kind")   # what the rule engine's `when` reads
GLOSS_TOP = 8


def verse_hash(ch, v, text):
    return hashlib.sha256(f"{ch}:{v}\t{text}".encode("utf-8")).hexdigest()[:8]


def slot_of(r):
    s = r["slot"]
    if s in ("prefix", "suffix", "infix"):
        return s[0] + (str(r["position"]) if r.get("position") is not None else "")
    return s


def piece(r):
    if r["slot"] == "tone":
        return ":tone" + (f":{r['label']}" if r.get("label") else "") + "@" + ";".join(r.get("tone") or [])
    return f"{r['text'] or ''}:{slot_of(r)}" + (f":{r['chain_id']}" if r.get("chain_id") else "")


def parse_piece(p):
    """a piece -> {text, slot, morph, tone}"""
    body, at, marks = p.partition("@") if p.startswith(":tone") else (p, "", "")
    text, _, rest = body.partition(":"); slot, _, morph = rest.partition(":")
    return {"text": text, "slot": slot, "morph": morph or None, "tone": [m for m in marks.split(";") if m] if at else []}


def put_tone(text, marks):
    """bcv-split's rebuild rule (lexeme-aligner split_format.put_tone): marks by letter cluster counted from the end"""
    cl = []
    for c in ud.normalize("NFD", text):
        (cl[-1].append(c) if ud.combining(c) and cl else cl.append([c]))
    letters = [k for k, x in enumerate(cl) if ud.category(x[0]).startswith("L")]
    for m in marks:
        pos, _, mark = m.partition(":"); n = int(pos)
        if not mark or n < 1 or n > len(letters):
            raise ValueError(f"tone mark {m!r}: no letter {pos} from the end")
        cl[letters[-n]].append(ud.normalize("NFD", mark))
    return ud.normalize("NFC", "".join("".join(x) for x in cl))


def rebuild(pieces):
    ps = [parse_piece(p) for p in pieces]
    text = "".join(p["text"] for p in ps if p["slot"] != "tone"); marks = [m for p in ps if p["slot"] == "tone" for m in p["tone"]]
    return put_tone(text, marks) if marks else ud.normalize("NFC", text)


def splitter_pin(lang):
    """the splitter's files with their sha256 (12 hex), from the language's segmenter bundle"""
    b = paths.resolve(lang, paths.config(lang)["segmenter"])
    return " ".join(f"{f}@{hashlib.sha256(open(os.path.join(b, f), 'rb').read()).hexdigest()[:12]}"
                    for f in ("morphs.py", "bcv_segment.py", "seg_facts.json") if os.path.exists(os.path.join(b, f)))


def split_rows(work, book, ch):
    """{verse: {token i: [rows by part]}} of one chapter from an alignment run's split file"""
    import pyarrow.parquet as pq, pyarrow.compute as pc
    t = pq.read_table(os.path.join(work, "split", "words.parquet"))
    t = t.filter(pc.and_(pc.equal(t["book"], book), pc.equal(t["chapter"], ch)))
    out = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in sorted(t.to_pylist(), key=lambda r: (r["verse"], r["i"], r["part"])):
        out[r["verse"]][r["i"]].append(r)
    return out


def write_parts(lang, bundle):
    """.parts beside every chapter of every kind -> {kind: [tokens, verses written, verses whose tokens differ]}"""
    cfg = paths.config(lang); code = cfg.get("code", cfg["iso"]); res = {}
    head = f"# parts: {PARTS_FORMAT}; splitter {splitter_pin(lang)}; unicode {ud.unidata_version}"
    for kind, drafts in sorted(AL.kinds(bundle).items()):
        work = paths.private("publish", code, "align", os.path.basename(os.path.normpath(bundle)), kind); st = [0, 0, 0]
        for (b, c), p in sorted(drafts.items()):
            verses = CF.read_md(p)[4]; S = split_rows(work, b, c); lines = [head]
            for v in sorted(verses, key=int):
                toks = FA.tokenize(verses[v]); rows = S.get(int(v), {})
                if sorted(rows) != list(range(len(toks))):          # the split counted the verse otherwise: no row rather than a wrong one
                    st[2] += 1; continue
                lines.append("\t".join([f"{c}:{v}", verse_hash(c, v, verses[v])] + [f"{i}=" + "|".join(piece(r) for r in rows[i]) for i in range(len(toks))]))
                st[0] += len(toks); st[1] += 1
            open(p[:-3] + ".parts", "w", encoding="utf-8").write("\n".join(lines) + "\n")
        res[kind] = st
    return res


def check_parts(stem):
    """(problems, notices) of a chapter's .parts against its .md: a stale row is a notice, a row that does not rebuild its tokens
    is a problem"""
    if not os.path.exists(stem + ".parts"):
        return [], []
    verses = CF.read_md(stem + ".md")[4]; ch = int(stem[-3:]); problems, notices = [], []
    for n, l in enumerate(open(stem + ".parts", encoding="utf-8"), 1):
        if l.startswith("#"):
            if n == 1 and not l.startswith(f"# parts: {PARTS_FORMAT}"):
                problems.append("parts: the header names no known format")
            continue
        f = l.rstrip("\n").split("\t"); m = re.fullmatch(r"(\d+):(\d+)", f[0])
        if not m or int(m.group(2)) not in verses:
            problems.append(f"parts line {n}: unknown verse {f[0]}"); continue
        v = int(m.group(2)); text = verses[v]
        if f[1] != verse_hash(ch, v, text):
            notices.append(f"parts {f[0]}: stale (the verse changed)"); continue
        toks = FA.tokenize(text)
        if len(f) - 2 != len(toks):
            problems.append(f"parts {f[0]}: {len(f) - 2} tokens, the verse has {len(toks)}"); continue
        for i, cell in enumerate(f[2:]):
            k, _, body = cell.partition("=")
            try:
                ok = k == str(i) and FA.tokenize(rebuild(body.split("|"))) == [toks[i]]
            except ValueError:
                ok = False
            if not ok:
                problems.append(f"parts {f[0]} token {i}: the pieces do not rebuild the token"); break
    return problems, notices


def write_runs(bundle, labels, manifests, register_now):
    """.tanakh/runs/<BOOK>_<CCC>.json per chapter. Each kind's `register` is what its build recorded at draft time (the
    revision and the entries' sha256); a build from before the record (2026-11-12) gets the revision at bundle time,
    marked `register at bundle`. `drafted` is make-tanakh's lifecycle stamp ({revision, when}) of the main draft"""
    out = collections.defaultdict(dict)
    for kind, drafts in AL.kinds(bundle).items():
        man = manifests.get(kind) or {}; b = (man.get("builds") or [{}])[-1]; s = (man.get("sends") or [{}])[-1]
        reg = b.get("register") if isinstance(b.get("register"), dict) else None
        for (bk, c) in drafts:
            out[(bk, c)][kind] = {k: v for k, v in {
                "run": f"{labels.get(kind, kind)}@{(b.get('when') or '')[:10]}", "label": labels.get(kind, kind),
                "model": s.get("model") or b.get("model"), "prompts sha256": b.get("prompts sha256"), "code": b.get("code"),
                "register": reg and reg.get("revision"), "register sha256": reg and reg.get("sha256"),
                "register at bundle": None if reg else register_now, "built": b.get("when"), "kind of draft": b.get("kind") or kind}.items() if v}
    d = os.path.join(bundle, ".tanakh", "runs"); os.makedirs(d, exist_ok=True)
    for (bk, c), kinds in sorted(out.items()):
        m = kinds.get("main") or {}
        drafted = {"revision": m.get("register") or m.get("register at bundle"), "when": m.get("built")} if m else None
        json.dump({"book": bk, "chapter": c, "main": "main", **({"drafted": drafted} if drafted else {}), "drafts": kinds},
                  open(os.path.join(d, f"{bk}_{c:03d}.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    return len(out)


def write_glosses(lang, bundle, repo_commit=None):
    """.tanakh/glosses.json from the main drafts' .align links (FORMAT.md section 8)"""
    forms = collections.defaultdict(collections.Counter); chapters = 0
    for (b, c), p in sorted(AL.kinds(bundle).get("main", {}).items()):
        verses = CF.read_md(p)[4]; _, rows = FA.read_chapter(p[:-3] + ".align"); chapters += 1
        lx, fn = FA.index(b, "lexemes"), FA.index(b, "fn")
        for v, (mn, fnl, _) in rows.items():
            toks = FA.tokenize(verses.get(int(v), "")); ref = f"{b} {c}:{v}"
            for field, idx in ((mn, lx.get(ref, [])), (fnl, fn.get(ref, []))):
                for o, pos in FA.parse(field).items():
                    if 0 <= o < len(idx) and pos and all(q < len(toks) for q in pos):
                        forms["hbo:" + idx[o]][" ".join(toks[q] for q in sorted(pos)).lower()] += 1
    cfg = paths.config(lang)
    g = {"format": "make-tanakh-glosses/1", "language": cfg.get("code", cfg["iso"]),
         "source": {"repo": "bcv-commons/make-tanakh-grammar", "commit": repo_commit or (pins.git_commit(paths.ROOT) or {}).get("commit"),
                    "editions": ["drafts"], "chapters": chapters},
         "licence": "CC0-1.0 (counts from our drafts); lexemes: MACULA Hebrew (WLC) via lexeme-spine-macula, CC BY 4.0",
         "lexemes": {k: [[f, n] for f, n in c.most_common(GLOSS_TOP)] for k, c in sorted(forms.items())}}
    os.makedirs(os.path.join(bundle, ".tanakh"), exist_ok=True)
    json.dump(g, open(os.path.join(bundle, ".tanakh", "glosses.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    return len(g["lexemes"])


def write_clause_features(bundle):
    """.tanakh/clause-features.json: where the Hebrew clauses' features are, never the values"""
    os.makedirs(os.path.join(bundle, ".tanakh"), exist_ok=True)
    json.dump({"format": "make-tanakh-clause-features/1", **CLAUSE_COLUMNS, "key": "clause_key",
               "join": "a .units key is <clause_key>-<the clause's last word>[/n]: the part before '-' is the clause_key of the row; /n marks "
                       "the clause's n-th piece in the verse (a clause interrupted by another clause has two pieces, one key)",
               "similar": list(SIMILAR), "note": "values are not copied into this CC0 repository; read them from the dataset"},
              open(os.path.join(bundle, ".tanakh", "clause-features.json"), "w", encoding="utf-8"), indent=1)


def register_revision(lang):
    from shared import register
    return register.version(paths.config(lang).get("_register")).get("revision")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", required=True); ap.add_argument("--bundle", required=True)
    ap.add_argument("--labels", default="", help="kind=label,... of the runs (main=dev-1109); default: the kind's name")
    a = ap.parse_args()
    from drafting import draft
    labels = dict(x.split("=") for x in a.labels.split(",") if x)
    print(json.dumps({"parts [tokens, verses, verses skipped]": write_parts(a.lang, a.bundle), "glosses (lexemes)": write_glosses(a.lang, a.bundle)})); write_clause_features(a.bundle)
    mans = {}
    for kind, drafts in AL.kinds(a.bundle).items():
        bk = sorted(drafts)[0][0]
        mans[kind] = draft.load_manifest(argparse.Namespace(lang=a.lang, book=bk, label=labels.get(kind, kind)))
    print("runs:", write_runs(a.bundle, labels, mans, register_revision(a.lang)))


if __name__ == "__main__":
    main()
