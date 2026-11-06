#!/usr/bin/env python3
"""The Hebrew-Greek bridges, read: which Greek lexemes render a Hebrew lexeme in the Septuagint tradition (lexeme bridge), and
which Greek tense and mood a Hebrew conjugation and stem corresponds to (grammar bridge). With them a Hebrew clause can ask the
team's NT for evidence. Files: $MAKE_TANAKH_PRIVATE/source/bridges/{strong_bridge.json, grammar_bridge.json}."""
import collections, json

from shared import paths
from source.tokens import norm_strong

TOP, MIN_SHARE, CELL_MIN = 3, 0.05, 0.2            # as fixed in research before the first run


def lexemes():
    """Hebrew Strong's number -> [(Greek Strong's number, share)], best first, share >= MIN_SHARE (the best over the bridge's tiers)"""
    j = json.load(open(paths.private("source", "bridges", "strong_bridge.json"), encoding="utf-8"))["h2g"]; out = {}
    for h, lst in j.items():
        best = collections.defaultdict(float)
        for g, src, n, p in lst:
            best[str(g)] = max(best[str(g)], p)
        out[norm_strong(h)] = sorted(((g, p) for g, p in best.items() if p >= MIN_SHARE), key=lambda x: -x[1])
    return out


def cells():
    """Hebrew 'conjugation|stem' -> {Greek 'tense|mood'} with share >= CELL_MIN (voice dropped)"""
    j = json.load(open(paths.private("source", "bridges", "grammar_bridge.json"), encoding="utf-8"))["h2g"]; out = {}
    for h, lst in j.items():
        out[h] = {f"{g.split('|')[0]}|{g.split('|')[-1]}" for g, p in lst if p >= CELL_MIN}
    return out
