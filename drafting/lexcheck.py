#!/usr/bin/env python3
"""The word check of a draft, without a model: per verse, which source content words have none of the team's usual forms in
the draft, and which draft words the team's text never uses. For the reviewer a list per verse; for the language a second
figure beside the dev check's chrF3.

  checkable   a source content word whose lexeme (or, for a Hebrew word, one of its usual Greek equivalents) has at least 3
              links in the team's text outside the chapters drafted and the books the run left out (drafting/lexicon.py)
  found       a checkable word with one of its expected forms in the draft's verse (all tokens of a form of several);
              toneless: the same with the marks dropped (the configuration's "keep_marks" kept)
  unknown     a draft word that occurs nowhere in the team's text outside the chapters drafted and the books left out

The answer check (beside every run, when the language has a register with decided team terms or names): per source word
whose lexeme a decided term names (its `source`: H<n>, a Greek lemma), whether one of the decided forms (preferred, admitted)
is in the verse ("found"), and every deprecated or denied form that is ("conflicts", which a draft must not have and the
team's own text should not: a conflict there is a question for the team).

With --team the same figures for the team's own text of the verses: the ceiling a draft can reach. The team's text of a closed
or held-out chapter is never read. Per run: runs/<lang>/draft/<book>/<label>/lexcheck.json (word forms: private).

    . ./env.sh; python3 drafting/lexcheck.py --lang kvg --book JHN --labels dev dev-1109 [--team]"""
import argparse, collections, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import paths  # noqa: E402
from source import tokens  # noqa: E402
from drafting import devcheck, draft, lexicon, prompt  # noqa: E402


def words_of(text, f):
    return {f(w) for w in (devcheck.norm_word(x) for x in text.replace("-", " ").split()) if w}


def source_words(source, refs):
    """ref -> the verse's content tokens [(number in the verse, token)]"""
    T = tokens.greek() if source == "grc" else tokens.hebrew(sorted({r.split()[0] for r in refs}))
    out = collections.defaultdict(list)
    for k in sorted(T):
        t = T[k]
        if t["ref"] in refs and t["cls"] in prompt.CONTENT and t["strong"]:
            out[t["ref"]].append(t)
    return out


def check_texts(texts, source, L, f, team_vocab):
    """texts {group key: (refs, text)} -> (figures, per group {missed, unknown})"""
    refs = {r for rs, _ in texts.values() for r in rs}; S = source_words(source, refs)
    st = collections.Counter(); per = {}
    for key, (rs, text) in texts.items():
        ws = words_of(text, f); miss = []
        for r in rs:
            for t in S.get(r, []):
                exp = L.expected(source, t)
                if not exp:
                    continue
                st["checkable"] += 1
                if any(lexicon.found(f(x), ws) for x in exp):
                    st["found"] += 1
                else:
                    miss.append([r, t["text"], t["lemma"], sorted(exp)[:6]])
        unk = sorted(w for w in ws if w not in team_vocab)
        st["draft words"] += len(ws); st["unknown"] += len(unk); st["verses"] += 1; st["verses with a miss"] += bool(miss)
        per[key] = {"missed": miss, "unknown": unk}
    fig = {"verses": st["verses"], "content words checkable": st["checkable"],
           "found": round(st["found"] / max(1, st["checkable"]), 3), "verses with a miss": st["verses with a miss"],
           "unknown words": round(st["unknown"] / max(1, st["draft words"]), 3)}
    return fig, per


def answer_check(texts, source, reg, f):
    """texts {group key: (refs, text)} -> {checked, found, conflicts [[ref, form, entry id]]} against the register's decided terms"""
    from shared import register as RG
    by = RG.by_lexeme(reg); bad = {}
    for e in RG.binding(reg):
        if e["kind"] in ("term", "name"):
            for x in RG.forms(e, "deprecated") + list(e.get("denials") or []):
                bad.setdefault(f(x.lower()), e["id"])
    refs = {r for rs, _ in texts.values() for r in rs}; S = source_words(source, refs); n = hit = 0; conf = []
    for key, (rs, text) in texts.items():
        ws = words_of(text, f)
        for r in rs:
            for t in S.get(r, []):
                es = [e for e in by.get(("grc", t["lemma"]) if source == "grc" else ("hbo", t["strong"]), []) if RG.applies(e, source, t)]
                if es:
                    n += 1; hit += any(lexicon.found(f(x.lower()), ws) for e in es for x in RG.forms(e, "preferred", "admitted"))
        conf += [[rs[0], x, eid] for x, eid in bad.items() if lexicon.found(x, ws)]
    return {"checked": n, "found": round(hit / n, 3) if n else None, "conflicts": conf}


def run_scope(a, label):
    """(chapters drafted, books left out) of a run, from its builds"""
    a.label = label; m = draft.load_manifest(a); chs = set(); leave = set()
    for b in m["builds"]:
        chs |= set(b.get("chapters", ())); leave |= set((b.get("evidence") or {}).get("left out", ()) or b.get("leave out", ()))
    return chs, leave


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", required=True); ap.add_argument("--book", required=True); ap.add_argument("--labels", nargs="+", required=True)
    ap.add_argument("--team", action="store_true", help="the same figures for the team's text of the verses")
    a = ap.parse_args(); a.book = a.book.upper(); cfg = paths.config(a.lang); source = draft.source_of(a.book)
    V = devcheck.team_text(cfg, source); keep = tuple(cfg.get("keep_marks", ())); res = {"language": a.lang, "book": a.book, "runs": {}}
    for label in a.labels:
        chs, leave = run_scope(a, label); skip = {(a.book, c) for c in chs}
        L = lexicon.Lexicon(cfg, skip, leave)
        if not L.ok:
            sys.exit(f"{a.lang}: no lexicon/words.db (onboard/lexicon.py words)")
        own = lambda r: r.split()[0] in leave or (r.split()[0], int(r.split()[1].split(":")[0])) in skip
        vocab = {w for r, ws in V.items() if not own(r) for w in words_of(" ".join(ws), lambda x: x)}
        vocab_bare = {devcheck.detone(w, keep) for w in vocab}
        a.label = label; texts = {r: (x["refs"], x["text"]) for r, x in draft.answers(a).items()}
        out = {"scope": {"chapters": sorted(chs), "left out": sorted(leave), "words.db built": L.built}}
        out["draft"], per = check_texts(texts, source, L, lambda x: x, vocab)
        out["draft, toneless"], _ = check_texts(texts, source, L, lambda x: devcheck.detone(x, keep), vocab_bare)
        reg = None
        if cfg.get("_register") and os.path.exists(os.path.join(cfg["_register"], "VERSION.json")):
            from shared import register as RG
            reg = RG.load(cfg["_register"])
            if not RG.by_lexeme(reg) and not RG.deprecated(reg):
                reg = None
        if reg:
            out["answers"] = answer_check(texts, source, reg, lambda x: x)
        if a.team:
            gold = {k: (rs, " ".join(" ".join(V[r]) for r in rs)) for k, (rs, _) in texts.items() if all(r in V for r in rs)}
            out["team"], _ = check_texts(gold, source, L, lambda x: x, vocab)
            if reg:
                out["team answers"] = answer_check(gold, source, reg, lambda x: x)
        json.dump({**out, "verses": per}, open(os.path.join(draft.job_dir(a), "lexcheck.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        res["runs"][label] = out
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
