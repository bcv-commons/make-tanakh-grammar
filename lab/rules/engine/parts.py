#!/usr/bin/env python3
"""Participant fields per Greek token, from scripts/participants.py (build/participants/<code>.mentions.tsv, built with
`python3 scripts/participants.py <CODE> 1-<last> --mentions` for every NT book). A verb's mention is its implicit subject
(MACULA subjref); other mentions are nouns, names, pronouns. Fields, computed in book order across verses:

  p_subj   verbs: "same" (the subject of the previous verb mention), "new", "group" (several participants), None (no subject id)
  p_ref    non-verbs with an id: "verse" (mentioned earlier in this verse), "prev" (in the previous verse), "far", "first"
  p_psubj  non-verbs with an id: the participant is the previous verb's subject (True / False)
  p_rival  any mention: another single person is mentioned in this or the previous verse (True / False)"""
import collections, csv, glob, os

ROOT = os.environ["MAKE_TANAKH_WORK"]
PDIR = os.path.join(ROOT, "build/participants")
FIELDS = ("p_subj", "p_ref", "p_psubj", "p_rival")
_cache = None


def load(C):
    """key -> fields for every token of the corpus C (tokens without an id get None values)"""
    global _cache
    if _cache is not None:
        return _cache
    pid, kind = {}, {}
    for f in glob.glob(os.path.join(PDIR, "*.participants.tsv")):
        for r in csv.DictReader(open(f, encoding="utf-8"), delimiter="\t"):
            kind[r["pid"]] = r["kind"]
    for f in glob.glob(os.path.join(PDIR, "*.mentions.tsv")):
        for r in csv.DictReader(open(f, encoding="utf-8"), delimiter="\t"):
            pid[r["key"]] = r["pid"]
    toks = sorted((t for ts in C.tok.values() for t in ts), key=lambda t: t["key"])
    out = {}
    last_subj = None; seen = {}          # pid -> (book, ch, v) of its latest mention
    recent = collections.deque()         # (verse, pid) of person mentions in this and the previous verse
    prev_book = None
    for t in toks:
        vs = (t["book"], t["ch"], t["v"])
        if t["book"] != prev_book:
            last_subj, seen, prev_book = None, {}, t["book"]; recent.clear()
        while recent and not (recent[0][0] == vs or (recent[0][0][:2] == vs[:2] and recent[0][0][2] == vs[2] - 1)):
            recent.popleft()
        p = pid.get(t["key"])
        f = dict.fromkeys(FIELDS)
        if p:
            single = "+" not in p
            others = {q for _, q in recent if q != p}
            f["p_rival"] = bool(others)
            if t["class"] == "verb":
                f["p_subj"] = "group" if not single else "same" if p == last_subj else "new"
                last_subj = p
            else:
                s = seen.get(p)
                f["p_ref"] = "first" if not s else "verse" if s == vs else "prev" if s[:2] == vs[:2] and s[2] == vs[2] - 1 else "far"
                f["p_psubj"] = p == last_subj
            if single and kind.get(p) == "PERSON":
                recent.append((vs, p))
            for q in p.split("+"):
                seen[q] = vs
            seen[p] = vs
        out[t["key"]] = f
    _cache = out
    return out
