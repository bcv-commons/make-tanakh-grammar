#!/usr/bin/env python3
"""The verbatim gate: a draft made with a team's text among its inputs must not reproduce the team's own verse.

The rule (the user's, 2026-11-04): a draft is verbatim only where it reproduces the team's text OF THE SAME VERSE; phrases
shared with other verses are the language's own usage and never flagged. Per clause of a draft, against the team's text of
the clause's own verse(s):
  - the longest run of consecutive identical words,
  - the share of the clause's words inside runs of >= 5 words,
  - flagged when the longest run >= X (10), or, in a clause of more than X words, the share >= 0.8.
Words are compared exactly: lower-cased, NFC, split at spaces and hyphens, punctuation stripped; tone and length marks kept.

Most drafted chapters have no team text (that is why they are drafted) and pass untouched; the gate matters where a team
has a chapter already. The bundle (publish/bundle.py) applies it to every clause of every draft."""
import collections, json, re, sqlite3, unicodedata


def norm(text):
    out = []
    for w in re.split(r"[\s\-‐‑]+", unicodedata.normalize("NFC", (text or "").lower())):
        w = "".join(c for c in w if c.isalnum() or unicodedata.combining(c) or c in "'’ʼ").strip("'’ʼ")
        if w:
            out.append(w)
    return out


def team_verses(corpus, refs):
    """ref (as the source numbers it) -> the team's verse text, for exactly the given verses, wherever they lie: a check of
    what is about to be published, not a measure (nothing is tuned on it)"""
    out = {}
    if corpus is None:
        return out
    z = sqlite3.connect(corpus["_db"]); heb = "heb" if "heb" in [r[1] for r in z.execute("pragma table_info(verse)")] else "ref"
    for ref, words, wi in z.execute(f"select coalesce({heb}, ref), words, wordidx from verse"):
        if ref not in refs or not wi:
            continue
        ws = collections.defaultdict(str)
        for p, i in zip(json.loads(words), json.loads(wi)):
            ws[i] += p
        out[ref] = " ".join(ws[i] for i in sorted(ws))
    return out


def longest(a, b):
    """the longest common run of consecutive words, and every (end position in a, run length) met on the way"""
    best, runs = 0, []; prev = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                cur[j] = prev[j - 1] + 1; best = max(best, cur[j]); runs.append((i, cur[j]))
        prev = cur
    return best, runs


def covered(a, runs, m):
    """the share of a's words inside runs of >= m words"""
    cov = set()
    for i, k in runs:
        if k >= m:
            cov.update(range(i - k, i))
    return len(cov) / len(a) if a else 0.0


class Gate:
    def __init__(self, team, flag_run=10, share=0.8, min_run=5):
        self.team, self.x, self.share, self.m = team, flag_run, share, min_run

    def check(self, text, refs):
        """None, or the figures of a flagged clause"""
        d = norm(text); g = norm(" ".join(self.team.get(r, "") for r in refs))
        if not d or not g:
            return None
        L, runs = longest(d, g); sh = covered(d, runs, self.m)
        if L >= self.x or (len(d) > self.x and sh >= self.share):
            return {"longest run": L, "share": round(sh, 3), "words": len(d)}
        return None
