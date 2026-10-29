#!/usr/bin/env python3
"""Candidates for the scorers' team map (score_ruth.team_map): the team's decisions (method team-decision) on words, names and
formulas, beside the store's other entries for the same thing whose form differs (the same id family, or an id the team
entry's note names), and how often that older form occurs in the human Kuni text. A candidate counts only once the team
entry names it ("replaces": [form, ...], set in the work repo's store) or score_ruth.CONFIRMED does: a decision for new
drafts does not by itself say the older text is wrong.

    . ./env.sh; /usr/bin/python3 lab/rules/stepA/team_candidates.py [BOOK ...]     (default RUT JON; output is local: Kuni
    forms, never in git)"""
import collections, glob, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import score_ruth as SR  # noqa: E402
F, R = SR.F, SR.R
KINDS = {"term", "name", "formula"}


def human(book):
    """the human text's tokens, lowercased, per book (the published edition: import/non-free/kvg/KVG-KuNT/text)"""
    toks = []
    for p in sorted(glob.glob(os.path.join(os.path.dirname(SR.HUMAN), book.lower() + "[0-9][0-9][0-9].txt"))):
        toks += [t.lower() for _, v in F.draft_texts(p) for t in F.tokenize(v)]
    return toks


def count(toks, form):
    ft = [t.lower() for t in F.tokenize(form)]
    if not ft or "<" in form:
        return 0
    n = len(ft)
    return sum(toks[i:i + n] == ft for i in range(len(toks) - n + 1))


def main(books):
    es = {}
    for f in ("observations.json", "decisions.json"):
        for e in json.load(open(os.path.join(SR.STORE, f), encoding="utf-8")).get("entries", []):
            es[e["id"]] = e
    texts = {b: human(b) for b in books}
    _, applied = SR.team_map()
    for e in es.values():
        if e.get("method") != "team-decision" or e.get("status") == "superseded" or e.get("kind") not in KINDS:
            continue
        base = e["id"].rsplit(".team", 1)[0]
        named = set(re.findall(r"\b(?:term|name|formula):[\w.:-]+", e.get("note") or ""))
        rel = [k for k in es if k != e["id"] and es[k].get("method") != "team-decision"
               and (k == base or k.startswith(base + ".") or k in named or k.rsplit(".gloss", 1)[0] in named)]
        old = collections.OrderedDict()
        for k in rel:
            v = es[k].get("value") or ""
            if v and v.lower() != (e.get("value") or "").lower():
                old.setdefault(v, []).append(k)
        state = "applied" if e["id"] in applied else "named" if e.get("replaces") else "open"
        print(f"{e['id']} [{state}] = {e.get('value')!r}" + (f"  replaces {e['replaces']}" if e.get("replaces") else ""))
        for v, ks in old.items():
            n = {b: count(t, v) for b, t in texts.items()}
            print(f"    {v!r}  ({', '.join(ks)})  in the human text: " + ", ".join(f"{b} {c}" for b, c in n.items()))
        if not old:
            print("    (no other form in the store)")


if __name__ == "__main__":
    main(sys.argv[1:] or ["RUT", "JON"])
