"""Feasibility: the person contrast 2S vs 3S in the present active indicative, as the corpus shows it (NT, BSB alignment).
Per Greek token: the aligned BSB words; the last aligned word that is not a pronoun or auxiliary = the verb word."""
import collections, sqlite3, bsbwords as B
c = sqlite3.connect(B.R + "/orig/grc.sqlite")
PRON = {"i", "you", "he", "she", "it", "we", "they", "him", "her", "them", "me", "us"}
AUX = {"do", "does", "did", "am", "is", "are", "was", "were", "will", "have", "has", "had", "not", "be", "been", "being", "shall", "would"}
rows = c.execute("""select t.book, t.ch, t.v, t.lemma, t.morph, b.positions from tokens t join bsb b on b.key = t.key
                    where t.morph in ('V-PAI-2S', 'V-PAI-3S') and b.positions is not null""").fetchall()
stat = collections.defaultdict(collections.Counter); lemmas = collections.defaultdict(set); ex = collections.defaultdict(list)
for bk, ch, v, lemma, morph, pos in rows:
    try:
        w = [B.verse_words(bk, ch)[v][int(p)] for p in pos.split()]
    except (KeyError, IndexError, FileNotFoundError):
        stat[morph]["unreadable"] += 1; continue
    lw = [x.lower() for x in w]
    verb = next((x for x in reversed(lw) if x not in PRON and x not in AUX), None)
    s = stat[morph]; s["n"] += 1; lemmas[morph].add(lemma)
    if verb is None: s["no verb word"] += 1; continue
    s["pronoun you in span"] += "you" in lw
    s["3rd pronoun in span"] += bool({"he", "she", "it"} & set(lw))
    s["verb ends -s"] += verb.endswith("s") and not verb.endswith("ss")
    s["verb ends -ed / irregular past?"] += verb.endswith("ed")
    s["aux in span"] += bool(AUX & set(lw))
    if len(ex[morph]) < 6: ex[morph].append((f"{bk} {ch}:{v}", lemma, " ".join(w)))
both = lemmas["V-PAI-2S"] & lemmas["V-PAI-3S"]
for m in ("V-PAI-3S", "V-PAI-2S"):
    s = stat[m]; print(m, dict(s)); print("   ", ex[m])
print("lemmas with both persons:", len(both))
