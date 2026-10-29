"""BSB verse words as indexed by orig/grc.sqlite `bsb` positions (0-based, punctuation stripped)."""
import os, re
R = os.environ["MAKE_TANAKH_WORK"]
_cache = {}
def verse_words(code, ch):
    key = (code, ch)
    if key not in _cache:
        txt = open(os.path.join(R, "reference/BSB", f"{code.lower()}{ch:03d}.txt"), encoding="utf-8").read()
        txt = "\n".join(l for l in txt.splitlines() if not l.startswith("=="))
        out = {}
        for m in re.finditer(r"\bv(\d+)\s+(.*?)(?=\bv\d+\s|\Z)", txt, re.S):
            out[int(m[1])] = re.findall(r"[\w’'-]+", m[2])
        _cache[key] = out
    return _cache[key]
