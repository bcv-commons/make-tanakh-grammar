#!/usr/bin/env python3
"""A project's style-corpus edition as a split file (lexeme-aligner's `bcv-split/0.1`, docs/split-format.md there): every
token (bcv tokenizer v2) with the parts the project's morph store gives it (scripts/morphs.py, the Segmenter).

Local tool (2026-10-26; template patches paused): meant to become `morphs.py export-split` at the next template update.

    ~/sil-study/.venv/bin/python lab/split/export_split.py <project> <edition id> [--out DIR]
      -> DIR/_split.json, DIR/words.parquet (default lab/split/out/<edition>/)

Rules:
- Tokens and `i`: the vendored tokenizer v2 (lexeme-aligner's pinned copy of bibles verse-text 1.0.0); a token's written
  form is the same run of letters and marks in the NFC verse text, marks kept.
- Parts: Segmenter.split of the written word. It returns lowercase parts with the grammatical tone taken off; the parts'
  texts are cut back out of the written word (case and spelling as written), the tone as a `tone` part ("pos:mark", pos =
  letter clusters from the word's end, the validator's counting).
- A hyphen word ("Yesu-gé"): tokenizer v2 makes each piece a token. When the store splits the whole word into one part per
  piece, each piece is one row (`written: hyphen`, `host` = the stem piece's offset); otherwise each piece is a `whole` row.
- Basis per part: an affix the store has decided -> team; observed or open with try's counts passing (morphs.is_confirmed)
  -> derived; any other affix -> labelled. Stems take the basis of their word's weakest affix; an undivided token is
  `whole`, basis derived.
- A word whose parts do not rebuild it exactly is written `whole` and counted ("fallback: no exact rebuild")."""
import argparse, collections, datetime, hashlib, importlib.util, json, os, re, sys, unicodedata as ud
HERE = os.path.dirname(os.path.abspath(__file__)); R = os.environ["MAKE_TANAKH_WORK"]
sys.path.insert(0, os.path.join(R, "scripts"))
import langtools as LT, morphs as M, grammar  # noqa: E402

VENDOR = os.path.join(os.environ["BCV_COMMONS"], "lexeme-aligner/pipeline/vendor/bibles/bcv_tokenize.py")
HYPHENS = "-‐‑"
RANK = {"team": 0, "derived": 1, "external": 2, "model": 3, "labelled": 4}


def tokenizer():
    spec = importlib.util.spec_from_file_location("bcv_tokenize", VENDOR)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def runs(text):
    """[(start, end)] of the letter + mark runs of an NFC text (the tokenizer's words, before marks are stripped)"""
    out, a = [], None
    for k, ch in enumerate(text):
        if ud.category(ch)[0] in ("L", "M"):
            a = k if a is None else a
        elif a is not None:
            out.append((a, k)); a = None
    if a is not None:
        out.append((a, len(text)))
    return out


def vclusters(s):
    """the validator's clusters (a character + the combining marks after it), NFD"""
    out = []
    for ch in ud.normalize("NFD", s):
        if ud.combining(ch) and out:
            out[-1] += ch
        else:
            out.append(ch)
    return out


def cut(word, ms):
    """the parts' texts cut out of the written word: [(Morph, text as written)] and the tone part's marks in the
    validator's counting, or None when the parts do not rebuild the word"""
    plain = [m for m in ms if m.slot != "tone"]
    tone = [m for m in ms if m.slot == "tone"]
    joined = "".join(m.text for m in plain)
    our = M.clusters(joined)                    # the Segmenter's clusters of the joined text (tone positions count these)
    took = collections.defaultdict(list)
    for m in tone:
        for item in m.text.split():
            a, mk = item.split(":")
            took[int(a)].append(M.CH(mk))
    wcl = M.clusters(word)                      # the written word, same clustering
    if len(wcl) != len(our):
        return None
    # remove the tone marks from the written clusters, then compare case-blind with the parts
    bare = []
    for k, c in enumerate(wcl):
        for mk in took.get(k, ()):
            if mk not in c[1:]:
                return None
            c = c[0] + c[1:].replace(mk, "", 1)
        bare.append(c)
    if "".join(bare).lower() != ud.normalize("NFD", joined).lower():
        return None
    out, k = [], 0
    for m in plain:
        n = len(M.clusters(m.text))
        out.append((m, ud.normalize("NFC", "".join(bare[k:k + n])))); k += n
    marks = []
    if took:
        # validator counting: letter clusters from the end of the joined written text
        text = "".join(t for _, t in out)
        vc = vclusters(text)
        letters = [j for j, c in enumerate(vc) if ud.category(c[0]).startswith("L")]
        # offset (in NFD characters) of each of our clusters' base character
        offs, o = [], 0
        for c in bare:
            offs.append(o); o += len(c)
        voffs, o = [], 0
        for c in vc:
            voffs.append(o); o += len(c)
        for a, mks in sorted(took.items()):
            j = voffs.index(offs[a]) if offs[a] in voffs else None
            if j is None or j not in letters:
                return None
            for mk in mks:
                marks.append(f"{len(letters) - letters.index(j)}:{mk}")
    return out, marks, tone


def basis_of(m, ents):
    e = ents.get((m.form, m.position))
    if not e:
        return "labelled", None
    if e.get("status") == "decided":
        return "team", e.get("id")
    return ("derived" if M.is_confirmed(e) else "labelled"), e.get("id")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project"); ap.add_argument("edition"); ap.add_argument("--out")
    ap.add_argument("--licence", help="the text's licence (default: the edition.yaml of the style corpus)")
    a = ap.parse_args()
    out = a.out or os.path.join(os.environ["MAKE_TANAKH_PRIVATE"], "split", "out", a.edition)
    os.makedirs(out, exist_ok=True)
    T = tokenizer()
    P = LT.Project(a.project); G = grammar.load(a.project); S = M.load(a.project, P, G)
    if S is None:   # no morph entries: every token one `whole` row (still a test of `i` and `token`)
        print(f"{a.project}: the store has no morph entries: every token whole", file=sys.stderr)
    ents = M.affix_entries(G) if S is not None else {}
    st = collections.Counter(); rows = []; books = set(); btext = collections.defaultdict(dict)
    for ref, code, (ch, v), _, text in P.corpus():
        book = ref.split()[0]; books.add(book); btext[book][(ch, v)] = text
        text = ud.normalize("NFC", text)
        rs = runs(text)
        words = [text[x:y] for x, y in rs]
        toks = T.tokenize(text)
        if [T.strip_marks(w) for w in words] != toks:
            st["verses skipped: runs differ from the tokenizer (unspaced script?)"] += 1; continue
        # hyphen groups: runs joined by a single hyphen with no space
        groups, g = [], [0]
        for k in range(1, len(rs)):
            if rs[k][0] - rs[k - 1][1] == 1 and text[rs[k - 1][1]] in HYPHENS:
                g.append(k)
            else:
                groups.append(g); g = [k]
        groups.append(g)
        for g in groups:
            st["tokens"] += len(g)
            if len(g) == 1:
                i = g[0]; w = words[i]
                ms = S.split(w) if S is not None else []
                res = cut(w, ms) if len(ms) > 1 else None
                if len(ms) > 1 and res is None:
                    st["fallback: no exact rebuild"] += 1
                if res is None:
                    rows.append(dict(book=book, chapter=ch, verse=v, i=i, token=toks[i], word=w, part=0, slot="whole", text=w, basis="derived"))
                    continue
                parts, marks, tone = res
                bs = [basis_of(m, ents) for m, _ in parts if m.slot != "stem"] + [basis_of(m, ents) for m in tone]
                weakest = max((b for b, _ in bs), key=RANK.get) if bs else "derived"
                p = 0
                for m, t in parts:
                    b, cid = basis_of(m, ents) if m.slot != "stem" else (weakest, None)
                    rows.append(dict(book=book, chapter=ch, verse=v, i=i, token=toks[i], word=w, part=p, slot=m.slot, position=m.position or None,
                                     text=t, form=m.form if m.slot != "stem" else None, chain_id=cid, basis=b)); p += 1
                if marks:
                    b, cid = basis_of(tone[0], ents)
                    rows.append(dict(book=book, chapter=ch, verse=v, i=i, token=toks[i], word=w, part=p, slot="tone", text="", tone=marks,
                                     label=tone[0].form, form=tone[0].form, chain_id=cid, basis=b))
                st["tokens divided"] += 1
                continue
            # a hyphen word
            hw = "-".join(words[i] for i in g)
            ms = [m for m in S.split(hw) if m.slot != "tone"] if S is not None else []
            texts = [m.text.strip("".join(HYPHENS)) for m in ms]
            if ms and len(ms) == len(g) and len(S.split(hw)) == len(ms) and all(t.lower() == words[i].lower() for t, i in zip(texts, g)) \
                    and sum(m.slot == "stem" for m in ms) == 1:
                si = g[[m.slot for m in ms].index("stem")]
                for m, i in zip(ms, g):
                    if m.slot == "stem":
                        rows.append(dict(book=book, chapter=ch, verse=v, i=i, token=toks[i], word=words[i], part=0, slot="whole", text=words[i], basis="derived"))
                    else:
                        b, cid = basis_of(m, ents)
                        rows.append(dict(book=book, chapter=ch, verse=v, i=i, token=toks[i], word=words[i], part=0, slot=m.slot, position=m.position or None,
                                         text=words[i], form=m.form, chain_id=cid, written="hyphen", host=si - i, basis=b))
                st["hyphen words as affix tokens"] += 1
            else:
                for i in g:
                    rows.append(dict(book=book, chapter=ch, verse=v, i=i, token=toks[i], word=words[i], part=0, slot="whole", text=words[i], basis="derived"))
                st["hyphen words left whole"] += 1
    import pyarrow as pa, pyarrow.parquet as pq
    # `p` (the producer's confidence in the part): 1.0 where the team decided the affix; left empty elsewhere, as the store has
    # no calibrated per-part confidence yet (the aligner's feedback per affix is meant to give one)
    for r in rows:
        r["p"] = 1.0 if r.get("basis") == "team" else None
    cols = ["book", "chapter", "verse", "i", "token", "word", "part", "slot", "position", "text", "tone", "label", "form", "chain_id",
            "written", "host", "basis", "p"]
    tab = pa.table({c: [r.get(c) for r in rows] for c in cols})
    fp = os.path.join(out, "words.parquet"); pq.write_table(tab, fp)
    lic = a.licence
    if not lic:
        import yaml
        for e in P.editions:
            y = os.path.join(R, e["dir"], "edition.yaml")
            if os.path.exists(y):
                lic = " ".join(str((yaml.safe_load(open(y, encoding="utf-8")) or {}).get("licence") or "").split()) or None
                break
    head = {"spec": "bcv-split/0.1", "edition": a.edition, "tokenizer_version": T.TOKENIZER_VERSION,
            "source": f"bsb-add-books store, {a.project}, {datetime.date.today()}", "basis": "derived",
            "sha256": hashlib.sha256(open(fp, "rb").read()).hexdigest(), "text_licence": lic or "unknown",
            "books": sorted(books), "date": str(datetime.date.today()), "stats": dict(st),
            # each book's text fingerprint (v1, the 8-hex hash in compact-alignments' file names), from the text the file was
            # made on: a reader without the edition's USJ can tell whether it is the same text
            "text_fp": {b: T.file_hash(T.fingerprints(btext[b])[0]) for b in sorted(books)}, "text_fp_version": 1}
    json.dump(head, open(os.path.join(out, "_split.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(out, dict(st), "rows", len(rows), "licence", lic)


if __name__ == "__main__":
    main()
