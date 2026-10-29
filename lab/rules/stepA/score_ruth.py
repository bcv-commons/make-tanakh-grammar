#!/usr/bin/env python3
"""Step A, small: the Kuni Ruth drafts of 2026-10-14 (export/kvg/kvg_BSB/_eval/ruth-test/) scored against the human Kuni Ruth
on the rules engine's component measures, through lexeme-aligner's alignment of the human text (their early NT-bridge delivery,
scratch/incoming/kvg-ntbridge-2026-10-27/). The drafts have no alignment of their own, so every measure starts from the human
side: a Hebrew content word, its human Kuni word(s), and whether the draft's verse has them.

  form         the draft verse has the human word exactly (as tokenized by compact-alignments; tone marks kept): all the
               link's content words; "any": one of them (independent of how many words an alignment puts in a link)
  word choice  the draft verse has a word with the same stem (the store's segmenter, morphs.load; tone marks off)
  order tau    Kendall tau of the matched words' draft positions against the Hebrew order; beside it the human text's tau on
               the same words
  function words P / R   per verse, bag of words, against the human verse; a function word = one of lexeme-aligner's Kuni
               stop words (bcv-commons/target-stopwords)
  chrF         summary only, summed over verses like the engine's (the October reports' 60-64 were chrF over whole chapters)

Every link, and the links the same in 5 of 5 of the aligner's runs (stability_kvg_wbt.tsv). By the Hebrew word's class.
    ~/sil-study/.venv/bin/python lab/rules/stepA/score_ruth.py [--out FILE]    (Kuni text never leaves this box; output is local)"""
import collections, csv, itertools, json, os, sqlite3, sys, unicodedata
R = os.environ["MAKE_TANAKH_WORK"]
sys.path.insert(0, os.path.join(R, "scripts"))
import full_align as F  # noqa: E402

DEL = os.path.join(R, "scratch/incoming/kvg-ntbridge-2026-10-27/kvg-delivery")
LAYER = os.path.join(DEL, "compact/k/kvg/kvg_wbt")
# another layer of the same text (2026-10-28: lexeme-aligner's full-alignments-llm v1.1, Jev by clause with our modules, whole
# words or morphed): STEPA_LAYER=<dir>. Its "steady" links are those the v1.1 whole-word and morphed layers make alike (no
# stability file there), in place of the early delivery's 5-of-5 links
V11 = os.path.join(R, "scratch/incoming/full-alignments-llm-v1.1")
LAYER = os.environ.get("STEPA_LAYER") or LAYER
LABEL = os.path.basename(LAYER.rstrip("/")) if os.environ.get("STEPA_LAYER") else "NT-bridge (early, 2026-10-27)"
# another book (2026-10-28: the Jonah held-out test): STEPA_BOOK=JON, STEPA_DRAFT=<dir with jon001.txt ...>
BOOK = os.environ.get("STEPA_BOOK", "RUT")
NCH = {"RUT": 4, "JON": 4}[BOOK]
HUMAN = os.path.join(R, "import/non-free/kvg/KVG-KuNT/text", BOOK.lower() + "%03d.txt")
DRAFT = os.path.join(os.environ.get("STEPA_DRAFT") or os.path.join(R, "export/kvg/kvg_BSB/_eval/ruth-test"), BOOK.lower() + "%03d.txt")
# the team's later decisions that the older human text predates (export/kvg/kvg_BSB/wiki/team-input.md): the human word is
# read as the decided one. Yawe -> Evezøza: "Evezøza everywhere" (the yahweh question, answers of 2026-10-26)
TEAM = {"yawe": "evezøza"}
BOOKS = {"RUT": "RUT_e9d22404", "JON": "JON_8829f4c6"}
STOPWORDS_REV = "976ccfdff0d16de6e37cd7c4c5cbe1b0d5f43b9a"


def layer(book, d=None):
    d = d or LAYER
    main = json.load(open(os.path.join(d, BOOKS[book] + ".json")))
    meta = json.load(open(os.path.join(d, BOOKS[book] + ".meta.json")))
    refs = list(F.index(book, "lexemes"))
    assert len(refs) == len(main), (book, len(refs), len(main))
    return refs, main, meta.get("fn") or [None] * len(refs)


def texts(path, nch):
    out = {}
    for c in range(1, nch + 1):
        for v, t in F.draft_texts(path % c):
            out[f"{c}:{v}"] = t
    return out


def steady(book):
    """{(ref, srcOrd): (None, 5)} for the links counted as steady: the early delivery's 5-of-5 links, or for a v1.1 layer the
    links its whole-word and morphed layers make alike"""
    if not os.environ.get("STEPA_LAYER"):
        return {(r["verse"], int(r["srcOrd"])): (r["key"], int(r["runs_agreeing_of_5"]))
                for r in csv.DictReader(open(os.path.join(DEL, "stability_kvg_wbt.tsv")), delimiter="\t")}
    refs, a, _ = layer(book, os.path.join(V11, "kvg_wbt+llm+jev-v4"))
    _, b, _ = layer(book, os.path.join(V11, "kvg-m_wbt+llm+jev-v4"))
    out = {}
    for ref, x, y in zip(refs, a, b):
        px, py = F.parse(x), F.parse(y)
        for o, pos in px.items():
            if o in py and sorted(py[o]) == sorted(pos):
                out[(ref, o)] = (None, 5)
    if os.environ.get("STEPA_STEADY") == "all3":          # and the early delivery's link the same (in any of its runs' result)
        refs, c, _ = layer(book, os.path.join(DEL, "compact/k/kvg/kvg_wbt"))
        early = {(ref, o): sorted(pos) for ref, x in zip(refs, c) for o, pos in F.parse(x).items()}
        out = {k: v for k, v in out.items() if early.get(k) == sorted(F.parse(dict(zip(refs, a))[k[0]])[k[1]])}
    return out


def kendall(xs, ys):
    c = d = 0
    for i, j in itertools.combinations(range(len(xs)), 2):
        s = (xs[i] - xs[j]) * (ys[i] - ys[j])
        c += s > 0
        d += s < 0
    return (c - d) / (c + d) if c + d else None


def func_words():
    """lexeme-aligner's published Kuni function words (bcv-commons/target-stopwords kvg.txt, pinned): their compact layer has
    no function-word channel to learn them from"""
    from huggingface_hub import hf_hub_download
    p = hf_hub_download("bcv-commons/target-stopwords", "kvg.txt", repo_type="dataset", revision=STOPWORDS_REV)
    return {w.lower() for w in F.tokenize(open(p, encoding="utf-8").read())}


def main(a):
    out = a[a.index("--out") + 1] if "--out" in a else None
    import morphs
    S = morphs.load("kvg/kvg_BSB")

    def stem(w):
        try:
            ms = S.split(w)
        except Exception:  # noqa: BLE001
            return w
        st = "".join(m.form for m in ms if m.slot == "stem")    # the plain stem: tone marks are measured by form
        return "".join(c for c in unicodedata.normalize("NFD", (st or w).lower()) if not unicodedata.combining(c))

    con = sqlite3.connect(os.path.join(R, "orig/heb.sqlite"))
    cls = dict(con.execute("select key, class from tokens where book = ?", (BOOK,)))
    stab = steady(BOOK)
    refs, main_, fns = layer(BOOK)
    keys = F.index(BOOK, "keys")
    hum, dra = texts(HUMAN, NCH), texts(DRAFT, NCH)
    FUNC = func_words()

    M = collections.defaultdict(collections.Counter)    # (subset, class) -> counts
    taus = collections.defaultdict(list)
    fe_tp = fe_n = fr_n = 0
    for ref, m in zip(refs, main_):
        cv = ref.split()[1]
        if cv not in dra:
            continue
        ht = [TEAM.get(t.lower(), t.lower()) for t in F.tokenize(hum[cv])]
        dt = [t.lower() for t in F.tokenize(dra[cv])]
        dset, dstem = set(dt), {stem(w) for w in dt}
        first = {}
        for i, w in enumerate(dt):
            first.setdefault(w, i)
        xs = collections.defaultdict(list)
        for o, pos in sorted(F.parse(m).items()):
            hw = [ht[p] for p in pos if p < len(ht)]
            hw_c = [w for w in hw if w not in FUNC] or hw
            if not hw_c:
                continue
            key = (keys.get(ref) or [None] * (o + 1))[o] if o < len(keys.get(ref, [])) else None
            k0 = (key or "").split("+")[0]
            c = cls.get(k0, "?")
            n5 = stab.get((ref, o), (None, 0))[1]
            got_form = all(w in dset for w in hw_c)
            got_any = any(w in dset for w in hw_c)
            got_stem = any(stem(w) in dstem for w in hw_c)
            for sub in ("all", "5of5") if n5 == 5 else ("all",):
                for cc in (c, "*"):
                    M[(sub, cc)]["n"] += 1
                    M[(sub, cc)]["form"] += got_form
                    M[(sub, cc)]["any"] += got_any
                    M[(sub, cc)]["choice"] += got_stem
                if got_form:
                    xs[sub].append((first[hw_c[0]], o, ht.index(hw_c[0])))
        for sub, trip in xs.items():
            if len(trip) >= 3:
                kd = kendall([t[0] for t in trip], [t[1] for t in trip])
                kh = kendall([t[2] for t in trip], [t[1] for t in trip])
                if kd is not None and kh is not None:
                    taus[sub].append((kd, kh))
        fe = collections.Counter(w for w in dt if w in FUNC)
        fr = collections.Counter(w for w in ht if w in FUNC)
        fe_tp += sum((fe & fr).values()); fe_n += sum(fe.values()); fr_n += sum(fr.values())

    import sacrebleu
    vs = [cv for cv in (r.split()[1] for r in refs) if cv in dra]
    chrf = sacrebleu.corpus_chrf([" ".join(F.tokenize(dra[v])) for v in vs], [[" ".join(F.tokenize(hum[v])) for v in vs]]).score
    lines = [f"# Step A (small): Kuni {BOOK} drafts ({os.path.relpath(os.path.dirname(DRAFT), R)}) vs the human text, through lexeme-aligner's alignment: {LABEL}",
             "(links: 5of5 = steady: the early delivery's 5-of-5 links, or for v1.1 the links its whole and morphed layers share"
             + (", and the early delivery too" if os.environ.get("STEPA_STEADY") == "all3" else "") + ")",
             f"verses {len(vs)}; function words: {len(FUNC)} types; chrF (summary, over verses as in the engine) {chrf:.1f}",
             f"function words P {fe_tp / max(1, fe_n):.3f}  R {fe_tp / max(1, fr_n):.3f}", ""]
    for sub in ("all", "5of5"):
        t = taus[sub]
        lines.append(f"## links: {sub}")
        lines.append(f"order tau (verses with >= 3 matched words: {len(t)}): draft {sum(x for x, _ in t) / max(1, len(t)):.3f}"
                     f"  human on the same words {sum(y for _, y in t) / max(1, len(t)):.3f}")
        lines.append("| Hebrew class | links | word choice (stem) | form (exact) | form (any word of the link) |")
        lines.append("|---|---|---|---|---|")
        for (s, c), v in sorted(M.items(), key=lambda kv: (kv[0][1] != "*", -kv[1]["n"])):
            if s == sub and v["n"] >= 10:
                lines.append(f"| {c} | {v['n']} | {v['choice'] / v['n']:.3f} | {v['form'] / v['n']:.3f} | {v['any'] / v['n']:.3f} |")
        lines.append("")
    txt = "\n".join(lines)
    print(txt)
    if out:
        open(out, "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main(sys.argv[1:])
