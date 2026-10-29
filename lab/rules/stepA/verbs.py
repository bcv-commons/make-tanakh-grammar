#!/usr/bin/env python3
"""Step A, small, part 2: where the Kuni Ruth drafts lose on verbs. Per Hebrew verb whose human Kuni rendering the draft's
verse doesn't have exactly (score_ruth.py's form miss):
  part of the rendering   a rendering of several words (a verb and its auxiliary): the draft has one, not the other
  stem near    no draft word has the human word's stem, but one is close (4+ letters shared at the start, one inside the
               other, or difflib >= 0.75): mostly the same verb with inflection the store doesn't split
  stem other   nothing close: another word chosen, the verb left out, or a wrong link (Kuni's links are unstable); split by
               whether the human stem occurs in the Kuni NT (what the drafters learned from) or not
  tone only    the same parts, written with other tone marks
  affixes      the same stem, other affixes: which ones the draft lacks and which it adds, named by the store's meaning
               (morphs.meaning: value and the Greek feature it marks)
The stem comes from the store's segmenter (morphs.load); the human links from lexeme-aligner's NT-bridge alignment.
    ~/sil-study/.venv/bin/python lab/rules/stepA/verbs.py [--out FILE]   (local output: it quotes Kuni affixes, no text)"""
import collections, difflib, os, re, sqlite3, sys, unicodedata
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import score_ruth as SR  # noqa: E402
F = SR.F


def main(a):
    out = a[a.index("--out") + 1] if "--out" in a else None
    import morphs, grammar
    S = morphs.load("kvg/kvg_BSB")
    AFF = morphs.affix_entries(grammar.load("kvg/kvg_BSB"))
    plain = lambda s: "".join(c for c in unicodedata.normalize("NFD", s.lower()) if not unicodedata.combining(c))

    def parts(w):
        try:
            ms = S.split(w)
        except Exception:  # noqa: BLE001
            return plain(w), ()
        st = plain("".join(m.form for m in ms if m.slot == "stem")) or plain(w)
        return st, tuple(sorted((m.slot, plain(m.form).strip("-"), m.position) for m in ms if m.slot != "stem"))

    def name(aff):
        slot, fm, pos = aff
        e = AFF.get((fm, pos)) or AFF.get((f"{fm}-", pos)) or AFF.get((f"-{fm}", pos)) or AFF.get((f"-{fm}-", pos))
        return f"{slot} {fm}" + (f" = {morphs.meaning(e)}" if e and morphs.meaning(e) else "")

    con = sqlite3.connect(os.path.join(SR.R, "orig/heb.sqlite"))
    cls = dict(con.execute("select key, class from tokens where book = ?", (SR.BOOK,)))
    lem = dict(con.execute("select key, lemma from tokens where book = ?", (SR.BOOK,)))
    stab = {k: v[1] for k, v in SR.steady(SR.BOOK).items()}
    refs, main_, _ = SR.layer(SR.BOOK)
    keys = F.index(SR.BOOK, "keys")
    hum, dra = SR.texts(SR.HUMAN, SR.NCH), SR.texts(SR.DRAFT, SR.NCH)
    FUNC = SR.func_words()

    # the stems of the Kuni NT: all the Kuni the drafters of 2026-10-14 learned from (Ruth, Jonah, Genesis held out)
    import glob
    NTSTEMS = set()
    for f in glob.glob(os.path.join(SR.R, "import/non-free/kvg/KVG-KuNT/text/*.txt")):
        if os.path.basename(f)[:3] in ("rut", "jon", "gen"):
            continue
        for _, t in F.draft_texts(f):
            NTSTEMS.update(parts(w.lower())[0] for w in F.tokenize(t))
    C = collections.defaultdict(collections.Counter)          # subset -> outcome counts
    lack, add = collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
    cases = collections.defaultdict(list)                     # "aux" | "tone" -> the cases, for the detail file
    for ref, m in zip(refs, main_):
        cv = ref.split()[1]
        if cv not in dra:
            continue
        ht = [t.lower() for t in F.tokenize(hum[cv])]
        dt = [t.lower() for t in F.tokenize(dra[cv])]
        dparts = [(w, *parts(w)) for w in dt]
        for o, pos in sorted(F.parse(m).items()):
            ks = keys.get(ref) or []
            if o >= len(ks) or cls.get((ks[o] or "").split("+")[0]) != "verb":
                continue
            hw = [ht[p] for p in pos if p < len(ht)]
            hw = [w for w in hw if w not in FUNC] or hw
            if not hw:
                continue
            subs = ("all", "5of5") if stab.get((ref, o)) == 5 else ("all",)
            if all(w in set(dt) for w in hw):
                out_ = "exact"
            else:
                # a rendering of several words (a verb and its auxiliary): the word whose stem the draft has, if any
                dst = {d[1] for d in dparts}
                miss = [w for w in hw if w not in set(dt)]
                h = next((w for w in miss if parts(w)[0] in dst), miss[0])
                hs, ha = parts(h)
                same = [d for d in dparts if d[1] == hs]
                if not same and any(parts(w)[0] in dst for w in hw):
                    out_ = "part of the rendering"      # one word of several there (the verb or its auxiliary), not the other
                    cases["aux"].append((ref, lem.get((ks[o] or "").split("+")[0]), hw, [w for w in miss if parts(w)[0] not in dst],
                                         stab.get((ref, o)) == 5))
                elif not same:
                    # the same verb with inflection the store doesn't split (a stem with and without an affix, two tone patterns), or
                    # another word: stems sharing 4+ letters at the start, one inside the other, or close by difflib
                    near = any(len(hs) >= 4 and len(d[1]) >= 4 and (os.path.commonprefix([hs, d[1]]).__len__() >= 4
                               or hs in d[1] or d[1] in hs or difflib.SequenceMatcher(None, hs, d[1]).ratio() >= 0.75)
                               for d in dparts)
                    out_ = "stem near" if near else ("stem other, in the NT" if hs in NTSTEMS else "stem other, not in the NT")
                else:
                    d = min(same, key=lambda d: len(set(d[2]) ^ set(ha)))
                    if set(d[2]) == set(ha):
                        out_ = "tone only"
                        cases["tone"].append((ref, lem.get((ks[o] or "").split("+")[0]), h, d[0], stab.get((ref, o)) == 5))
                    else:
                        out_ = "affixes"
                        for s in subs:
                            for x in set(ha) - set(d[2]):
                                lack[s][name(x)] += 1
                            for x in set(d[2]) - set(ha):
                                add[s][name(x)] += 1
            for s in subs:
                C[s][out_] += 1
                C[s]["n"] += 1

    L = ["# Step A (small), part 2: the Kuni Ruth 1-4 drafts' verbs against the human Ruth (links from lexeme-aligner's NT bridge)", ""]
    for s in ("all", "5of5"):
        n = C[s]["n"]
        L.append(f"## links: {s} ({n} Hebrew verbs)")
        for k in ("exact", "tone only", "affixes", "part of the rendering", "stem near", "stem other, in the NT", "stem other, not in the NT"):
            L.append(f"- {k}: {C[s][k]} ({C[s][k] / max(1, n):.1%})")
        L.append("- affixes the draft lacks (human has): " + "; ".join(f"{k} {v}" for k, v in lack[s].most_common(12)))
        L.append("- affixes the draft adds (human hasn't): " + "; ".join(f"{k} {v}" for k, v in add[s].most_common(12)))
        L.append("")
    txt = "\n".join(L)
    print(txt)
    if out:
        open(out, "w", encoding="utf-8").write(txt + "\n")
        open(out.replace(".txt", "_detail.txt"), "w", encoding="utf-8").write(detail(cases, S, plain) + "\n")


def detail(cases, S, plain):
    """The cases behind two of the losses: the auxiliary the draft leaves out (is it in the store, the wiki?) and the
    tone-only misses (a grammatical tone pattern of the store, or the word's own marks; would the corpus spelling catch it?)"""
    import glob, json
    prof = os.path.join(SR.R, "export/kvg/kvg_BSB/profile")
    store = " ".join(plain(json.dumps(e, ensure_ascii=False)) for f in ("observations", "decisions")
                     for e in json.load(open(os.path.join(prof, f + ".json"), encoding="utf-8"))["entries"])
    wiki = " ".join(plain(open(f, encoding="utf-8").read()) for f in glob.glob(os.path.join(SR.R, "export/kvg/kvg_BSB/wiki/**/*.md"), recursive=True))
    # the NT (what the October drafters learned from) as the alignment tokenizes it: hyphen words in pieces (gi-ein -> gi, ein)
    written = collections.Counter()
    for f in glob.glob(os.path.join(SR.R, "import/non-free/kvg/KVG-KuNT/text/*.txt")):
        if os.path.basename(f)[:3] not in ("rut", "jon", "gen"):
            for _, t in SR.F.draft_texts(f):
                written.update(w.lower() for w in SR.F.tokenize(t))
    vocab = collections.Counter()
    for w, n in written.items():
        vocab[plain(w)] += n
    word_in = lambda w, t: re.search(r"(?<![\w-])" + re.escape(plain(w)) + r"(?![\w])", t) is not None
    L = ["# Step A part 2, detail: the auxiliaries the drafts leave out, and the tone-only misses", "",
         "## Auxiliaries (part of the rendering): the missing word(s)", "",
         "| missing word | cases | stable | NT tokens | in the store | in the wiki | Hebrew verbs |", "|---|---|---|---|---|---|---|"]
    by = collections.defaultdict(list)
    for ref, lm, hw, miss, st in cases["aux"]:
        for w in miss or ["?"]:
            by[w].append((ref, lm, st))
    for w, xs in sorted(by.items(), key=lambda kv: -len(kv[1])):
        L.append(f"| {w} | {len(xs)} | {sum(x[2] for x in xs)} | {vocab.get(plain(w), 0)} | {'yes' if word_in(w, store) else 'no'} | "
                 f"{'yes' if word_in(w, wiki) else 'no'} | {', '.join(sorted({x[1] or '?' for x in xs}))} |")
    L += ["", "## Tone only: human vs draft", "",
          "| verse | Hebrew | human (NT tokens) | draft (NT tokens) | tone pattern (human / draft) | stable |", "|---|---|---|---|---|---|---|"]
    kinds = collections.Counter()
    for ref, lm, h, d, st in cases["tone"]:
        th = [m.form for m in S.split(h) if m.slot == "tone"]
        td = [m.form for m in S.split(d) if m.slot == "tone"]
        gram = th != td
        seen = written.get(d, 0)
        kinds[("grammatical" if gram else "lexical", "draft form in the NT" if seen else "draft form never in the NT")] += 1
        L.append(f"| {ref} | {lm} | {h} ({written.get(h, 0)}) | {d} ({seen}) | {'+'.join(th) or '-'} / {'+'.join(td) or '-'} | {'yes' if st else ''} |")
    L += ["", "tone-only misses: " + "; ".join(f"{a}, {b}: {n}" for (a, b), n in sorted(kinds.items()))]
    return "\n".join(L)


if __name__ == "__main__":
    main(sys.argv[1:])
