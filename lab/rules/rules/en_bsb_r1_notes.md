# Rules round 1 (en_bsb_r1): notes

Base: E6 trained on `nogospels`. Evidence from the test script's 1,500-verse train sample (s), a second disjoint
1,500-verse train sample (o, my own query with Random(11)) and dev (Mark 3, 9, 12). Test chapters never touched.
5 test rounds; 21 rules kept.

## The main finding

Most expressible gains share one cause: lemmas whose BSB rendering is made only of words in `E.FUNC`
(is/are/am/was, to be, has/have, must, will). The engine's core must be a content word, so it picks a wrong one
(εἰμί → "comes"/"stay"/"to remain", ἔχω → "holds", δεῖ → "ought", θέλημα → something else). Rules patch these
lemma by lemma; the right fix is in the engine (allow a FUNC-only core when the lemma's BSB renderings are FUNC-only).
General conditions (class + morphology + subj/neg/q/art + engine pre) gave nothing: the miner over those keys found
no group where another output beat the engine's on both train samples. E6's cells already use that information.

## Kept rules (train: fires, right before → after; dev the same)

| id | what | train | dev |
|---|---|---|---|
| be-3s | εἰμί V-PAI-3S, pre "" → "is" | 113, 0→75 | 24, 0→9 |
| be-3s-he | V-PAI-3S, pre "he" → "he is" | 29, 0→7 | 4, 0→2 |
| be-3p | V-PAI-3P → "are" | 23, 0→13 | 1, 0→0 |
| be-3p-they | V-PAI-3P, pre "they" → "they are" | 13, 0→4 | 1, 0→0 |
| be-2 | V-PAI-2P/2S/1P → "are" | 19, 0→15 | 1, 0→1 |
| be-2-you | 2P/2S, pre "you" → "you are" | 10, 0→6 | 2, 0→1 |
| be-1p-we | 1P, pre "we" → "we are" | 5, 0→2 | 0 |
| be-1s | 1S → "am" | 11, 0→9 | 0 |
| be-1s-i | 1S, pre "i" → "i am" | 5, 0→3 | 0 |
| be-impf-3s | V-IAI-3S → "was" | 20, 0→10 | 1, 0→1 |
| be-inf | V-PAN → "to be" | 33, 1→10 | 3, 0→2 |
| kai-adv | adverbial καί (class adv), engine "and" → "" | 169, 17→83 | 4, 1→3 |
| theos-gen | θεός N-GSM, pre "" → pre "of" | 152, 32→85 | 8, 0→7 |
| dei | δεῖ V-PAI-3S → "must" | 20, 0→14 | 1, 0→1 |
| oun | οὖν outside questions, no subject → "therefore" | 52, 5→17 | 0 |
| ean | ἐάν as particle (ὃς ἐάν), engine "if" → "" | 7, 0→7 | 2, 0→2 |
| echo-3s | ἔχω V-PAI-3S, head → "has" | 8, 0→6 | 4, 0→1 |
| echo-pl | ἔχω other present persons, head → "have" | 40, 1→18 | 0 |
| thelema | θέλημα → "will" | 12, 0→9 | 1, 0→1 |
| legon | λέγω V-PAP-NSM (quotative λέγων), pre "" → "" | 18, 1→8 (pre 11→11) | 3, 0→1 |
| hos-like | ὡς with subject, no neg/question → "like" | 22, 2→11 | 0 |

The evidence fields in the jsonl give the gold distributions per rule.

## Tried and dropped

- be-impf-3p (εἰμί V-IAI-3P → "were"): train 4→4, pre 4→4, dev pre 2→0. The gold splits between were / they were / there were.
- be-fut (εἰμί future, pre "will" → "will be"): train 0→2 but pre right 4→2 (the pre counts disagree); dev +1. Dropped by the rule.
- dunamai (δύναμαι without negation, head "can"): train 2→5 but dev 1→0 and word choice 0.5899→0.5876 (the clause's neg flag
  misses some negations, and "cannot" is a content word while "can" is FUNC).
- Not written, because the miner showed no gain on both samples: subject pronoun "he" on aorist 3sg without subject
  (s +13, o −6), article nominative → "who" (s +5, o +12, 111 fires: too broad), γίνομαι → "" (s +8, o +23, dev −1).

## Final dev measures (without → with the file)

```
word choice (content, stem): 0.5899 -> 0.5899
form (content, exact): 0.4983 -> 0.4983
rendering exact (all tokens): 0.4003 -> 0.4144
function words P: 0.5659 -> 0.5703
function words R: 0.475 -> 0.4965
order tau (mean per verse): 0.8799 -> 0.8811
chrF (summary): 35.58 -> 35.96
```

## Missing capabilities (ranked by the dev differences they would address)

1. **Pronoun referents / participant tracking** (≈70 dev pre differences, αὐτός classes): the BSB writes "Jesus",
   "the boy" or nothing where the engine writes him/his. Needs the referent (who) of the pronoun and whether it was just named.
2. **Subject continuity for verbs** (≈67: aorist/imperfect/present 3rd person "– → he", "he → –", "they → –"): whether the
   subject is the same as in the previous clause. On train, "" vs "he" is ~55/45, so no rule over the current fields works.
3. **Verse- or clause-initial position** (≈60 of the 171 καί differences; also ὅτι): verse-initial καί is "" 102 / "and" 100
   / "then" 42 in train (s), and in dev "" 34 / "then" 13 / "and" 10; verse-initial ὅτι is "for" 11/21 and 13/24, engine 0.
4. **The preposition's object case and governing verb** (≈90 dev prep differences): εἰς after motion verbs → "into", μετά
   + accusative → "after", ἐκ in ἐξ ὅλης → "with". The prep token has no case and no context.
5. **Neighbour / head word class** (article before a participle: nominative article engine "the", gold "who" 18 / "" 17
   / "the one who" 7 of 80, engine right 7; οὐ before a non-verb: "not" 35 of 52 (s), engine ""): a condition on the next
   token's class or the phrase head's class.
6. **Main-verb lexical class for ἵνα** (dev "so that → to" 9): ἵνα after verbs of asking/commanding → "to".
7. **A FUNC-only core in the engine** (the main finding above): would replace most of the 21 rules with one learned behaviour.

## Next

Implement 7 (engine, then retire the εἰμί/ἔχω/δεῖ/θέλημα rules and measure again), then add two context fields to the
format: `first` (token opens the verse / clause) and `next_class` (class of the following token, or of the head of the
article's phrase). Those two alone cover καί, ὅτι, the article + participle and οὐ + non-verb, with train evidence above.
Prepositions need the object's case (`obj_case`) from the MACULA tree; pronoun and subject classes need participant ids.
