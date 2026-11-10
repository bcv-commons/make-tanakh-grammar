#!/usr/bin/env python3
"""The team's word forms per source lexeme for the drafters, read from the language's lexicon/words.db (onboard/lexicon.py):
the content words' forms in the main prompt (draft.py build --lexicon), shape's whole-word candidates (shape.py build
--lexicon) and the check of a draft (drafting/lexcheck.py).

The counts are made here from the occurrences, without the chapters being drafted and the books a job leaves out, so that a
dev check never sees its own chapters (words.db itself holds every open verse). A Hebrew lexeme gets the team's direct forms
(from its Tanakh text, where the language has one) first, then the forms of its usual Greek equivalents in the team's NT,
through the bridges (source/bridges.py), but only where the team's Tanakh text has fewer than DIRECT_ENOUGH links for it,
and only the bridges with at least half the best bridge's share (the bridge's shares come from several tiers: יהוה has κύριος
0.94 but also λέγω 0.40). Forms are compared in lower case; a form of several
tokens counts as found when all its tokens are."""
import collections, os, re, sqlite3

from shared import paths
from source import bridges

MIN_SHARE, TOP, MIN_N = 0.05, 3, 3          # a form shown: share of its lexeme's links, forms per lexeme; links to be checkable
DIRECT_ENOUGH, BRIDGE_REL = 10, 0.5          # a Hebrew lexeme with this many direct links needs no bridge; bridges kept: >= half the best's share


def strong_of(lexeme_id):
    """`hbo:2050b` -> ('hbo', '2050'): the source tokens' Strong's numbers carry no homonym letter"""
    lang, s = lexeme_id.split(":"); return lang, re.sub(r"\D", "", s)


def tokens_of(form):
    return [w for w in form.replace(" … ", " ").split() if w]


class Lexicon:
    """.ok (the language has a words.db), of(lang, strong), renderings(source, token), expected(source, token), vocab"""
    def __init__(self, cfg, skip=(), leave_out=()):
        p = paths.lang_dir(cfg["iso"], "lexicon", "words.db"); self.ok = os.path.exists(p)
        self.n = collections.defaultdict(collections.Counter)            # (lang, strong) -> Counter(plain form)
        self.written = collections.defaultdict(collections.Counter)      # plain form -> Counter(form as written)
        self.lemma = {}; self.built = None; self.vocab = set()
        if not self.ok:
            return
        skip = {(b, int(c)) for b, c in skip}; leave_out = set(leave_out)
        db = sqlite3.connect(p); self.built = db.execute("select value from meta where name='built'").fetchone()[0]
        forms = dict((i, f) for i, f in db.execute("select id, form from form"))
        for lx, lem in db.execute("select id, lemma from lexeme"):
            self.lemma.setdefault(strong_of(lx), lem)
        for lx, fm, ref in db.execute("select lexeme, form, ref from occ"):
            b, cv = ref.split(); ch = int(cv.split(":")[0])
            if b in leave_out or (b, ch) in skip:
                continue
            f = forms[fm]; pl = f.lower(); self.n[strong_of(lx)][pl] += 1; self.written[pl][f] += 1
            self.vocab.update(tokens_of(pl))
        self.bridge = bridges.lexemes()

    def shown(self, pl):
        return self.written[pl].most_common(1)[0][0] if self.written.get(pl) else pl

    def of(self, lang, strong):
        """([(form as written, share, n)] the TOP commonest with share >= MIN_SHARE, total links) or None"""
        c = self.n.get((lang, strong))
        if not c:
            return None
        tot = sum(c.values())
        return [(self.shown(f), n / tot, n) for f, n in c.most_common(TOP) if n / tot >= MIN_SHARE], tot

    def bridges(self, strong, direct):
        """the Greek equivalents of a Hebrew lexeme worth asking, given its number of direct links: [(Greek number, share)]"""
        bs = self.bridge.get(strong, [])[:bridges.TOP]
        if direct >= DIRECT_ENOUGH or not bs:
            return []
        return [(g, p) for g, p in bs if p >= BRIDGE_REL * bs[0][1]]

    def renderings(self, source, t):
        """a content token's forms: [(label, rows, total, weight)]: its own lexeme first (label None), then for a Hebrew token its
        usual Greek equivalents (label = the Greek lemma, weight = the bridge's share)"""
        out = []
        own = self.of(source, t["strong"])
        if own:
            out.append((None, own[0], own[1], 1.0))
        if source == "hbo":
            for g, share in self.bridges(t["strong"], own[1] if own else 0):
                x = self.of("grc", g)
                if x:
                    out.append((self.lemma.get(("grc", g), g), x[0], x[1], share))
        return out

    def expected(self, source, t):
        """every lower-case form the team uses for a content token's lexeme (and, for a Hebrew token, for its usual Greek
        equivalents), or None when none of these lexemes has MIN_N links. Every form, not the commonest few: on Kuni JHN 1-4 the
        team's own text has one of its top three forms for 72 % of the checkable words, one of all its forms for 93 %"""
        own = sum(self.n.get((source, t["strong"]), {}).values())
        keys = [(source, t["strong"])] + ([("grc", g) for g, _ in self.bridges(t["strong"], own)] if source == "hbo" else [])
        cs = [self.n[k] for k in keys if sum(self.n.get(k, {}).values()) >= MIN_N]
        return {f for c in cs for f in c} or None


def found(form, words):
    """is a lower-case form (one or more tokens) in a set of lower-case words?"""
    return all(w in words for w in tokens_of(form))
