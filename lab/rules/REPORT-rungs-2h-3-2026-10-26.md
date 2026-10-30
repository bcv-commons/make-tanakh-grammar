# Rules-engine lab: the first non-English targets (rungs 2h, 3), the article, Hebrew E6, 2026-10-26

Follows `REPORT-round3-2026-10-26.md`. No LLM, no agent. The test chapters were not read. Measures on held-out B (1,500
training verses out of the pool) unless noted; dev in the run files.

## 1. Two new target languages, same engine

| corpus | data | builder | DB |
|---|---|---|---|
| Greek NT → Hebrew (Salkinson–Ginsburg 1885/86, PD) | bcv-commons/alignments-by-id v1.1 `n1904/h/heb/heb_scg` (CC0, Nestle 1904 ids); parts from bcv-commons/hebrew-nt-analysis v0.1 (CC BY 4.0) | `hebnt/build.py` | `data/hebnt.db`: 7,899 verses, 175,599 parts, 117,527 links |
| Hebrew → Modern Greek (Vamvas 1850, PD) | full-alignments-llm `ell_GreVamvas+llm+jev-v4` (CC0, local copy) on our Vamvas text | `vamvas/build_ot.py` | `data/vamvas_ot.db`: 22,716 verses, 290,080 Hebrew words linked |

The target unit for Hebrew is the **part** (prefix ו ב ל ה, stem, suffix pronoun), unpointed, so Hebrew's function morphemes are
the engine's function words. **Function words are derived, not listed:** Hebrew: part strings that are mostly prep / cj / art
/ pron / om / rel / ptcl in the analysis (101 strings); Greek: words linked mostly to Hebrew function morphemes only (478
words; it catches και, εν, ο/η/το, να, αυτού, and some noise such as έχω forms and ordinals). The engine reads them through a new
switch, `FUNC_FILE`. Nothing else was changed for the two languages.

| B | E1 lexicon | E2 + order | E5 cells | E6 split | E7 memory |
|---|---|---|---|---|---|
| NT → Hebrew (nogospels), chrF | 28.4 | 28.8 | **29.3** | 28.0 | 28.8 |
| order τ | 0.798 | 0.872 | | | |
| Tanakh → Modern Greek, chrF | 45.6 | 45.6 | **46.8** | 40.6 | 45.9 |
| order τ | 0.934 | 0.935 | | | |
| for comparison: NT → BSB / KJV E5 | | | 38.3 / 43.5 | | |
| Tanakh → BSB / KJV E5 | | | 41.0 / 50.0 | | |

(Hebrew chrF is over the parts as separate tokens, so it is not comparable in absolute terms with the others.)

What it shows:

1. **E1, E2, E5 carry over unchanged.** The order rules learn Hebrew order from the Greek (τ 0.80 → 0.87 on B), as they learned
   English; Modern Greek follows the Hebrew order closely already (τ 0.93 before any rule, as the KJV). The cells (E5) add
   +0.5 to +1.2 over E2 on both, as on English.
2. **E6 is English-shaped and loses on both** (Hebrew −1.3, Greek −6.2 against E5). Its form step strips and applies English
   suffixes only (`cells.lemmatize`: -s, -ed, -ing, -ies, -eth), so on Greek it finds no stem and the "lexeme + regular form"
   split collapses; on Hebrew the parts already separate most morphology, so the loss is smaller. **This is the first concrete
   item for the "nothing in the engine knows English" claim:** the suffix inventory must be learned from the target corpus
   (the store's affix machinery, `morphs.py`, does this for the drafting languages).
3. The derived function-word lists are good enough to run with; the Greek list needs a frequency floor or a second test (έχω
   forms are not function words).

## 2. The article (Greek → BSB)

Where the article's rendering is decided (B, E6): the first context step (3,250 of 3,877 articles) is right 54%; the
backoff steps 28-52%. Two corpus facts drive most errors: after ὁ + noun + **genitive personal pronoun** ("ὁ πατήρ μου") the BSB
has no "the" in 80% (5% "the"); before a **proper noun** none in 86%. Elsewhere "the" 44%, none 36%.

| B | E5 chrF | E6 chrF | function words R (E5) |
|---|---|---|---|
| eng_v3 | 38.32 | 37.31 | 0.489 |
| + article keys with possessive / proper head (`MID_KEYS=3`) | 38.47 | 37.46 | 0.493 |
| + the possessive in the article's cell (`det.poss`) | **38.94** | **37.99** | **0.504** |
| + proper head as well (`det.head_type`) | 38.94 | 37.99 | 0.504 |

The possessive is the feature; the proper-noun feature adds nothing once the per-noun keys (round 3) are in. Paired bootstrap on B (MID_KEYS=3 on both sides; the OFF side also lacks `pron.gov`, so this is the two
context fields together): E6 **+0.67 [0.56, 0.77]**, E5 +0.60 [0.50, 0.69]. The variant runs above give the possessive alone:
about +0.5.

## 3. Hebrew E6's gap to E5

Where E5 is right and E6 wrong (B): nouns 601 tokens, verbs 169; every other class is equal. Inside nouns and verbs:
the content word differs (437 nouns, 190 verbs), then "the" (240 dropped / 166 added) and "of" (151 / 95). Causes, from
samples:

- **The choice ignores the word's own prefixes:** בְּיַד is "through", not "in the hand"; לְאִשָּׁה "in marriage"; כַּף in Numbers 7 is
  "dish".
- **No empty choice:** a word the BSB leaves unrendered here (merged into a neighbour) gets a word anyway (140 nouns).
- **The function words are the cell's, shared by all lemmas,** so a lemma's own habit is lost ("the earth", "out of the land").

Two switches, both lexical features of the TBTA kind:

| B, Hebrew E6 | word choice | exact | function words R | chrF |
|---|---|---|---|---|
| eng_v3 | 0.613 | 0.302 | 0.457 | 38.39 |
| + choice by lemma and case / prefixes / suffix, with the empty choice (`CHOICE_CTX`) | 0.618 | 0.305 | 0.460 | 38.61 |
| + the lemma's own function words in its cell when seen ≥ 3 times, 60% one pattern (`PRE_LEX=3`) | 0.619 | 0.322 | 0.475 | **39.39** |
| (PRE_LEX=5 / 10) | | | | 39.24 / 39.07 |
| E5, for comparison | 0.606 | 0.341 | 0.510 | 40.99 |

The gap falls from 2.6 to 1.6. Paired bootstrap on B, both switches ON − OFF: Hebrew E6 **+1.00 [0.85, 1.15]**; on the Greek → BSB
E6 they help too, **+0.37 [0.29, 0.46]**. What is left is mostly the form step (on "form by rule" tokens E6 is right in 215 of
2,865, E5 in 492) and further function words.

## 4. eng_v4 (frozen) and the ending learner

**eng_v4** (`eng_v4/`, defaults in `cells.py`): eng_v3 + `MID_KEYS=3`, `det.poss`, `CHOICE_CTX`, `PRE_LEX=3`. Measures:
`r3/v4_measures.jsonl`; swap tests `r3/v4_features_B.log`.

| B, chrF | E5 | E6 | E7 |
|---|---|---|---|
| NT nogospels v3 → v4 | 38.32 → **38.94** | 37.31 → **38.34** | 37.98 → 38.64 |
| Tanakh v3 → v4 | 40.99 → 40.99 | 38.39 → **39.39** | 40.70 → 40.76 |

E6 still behaves as a rule system: future / aorist / plural swaps leave the rest unchanged in 1.00 / 0.98 / 1.00.

**The ending learner** (working engine, switch `ENDINGS=learn`, `cells.learn_families`): stems and endings from the parallel
data, with no list for any language. The target head words that render one source lemma and share their first letters with
its base form are one family; the family's stem is their shortest common beginning (love / loved / loving → lov + e / ed / ing;
λόγος / λόγου / λόγον → λόγ + ος / ου / ον; βασιλεύς / βασιλέως → βασιλ + εύς / έως). It learns 134 Greek endings (ησεν, ησαν, ους, οις,
έως …). A first attempt from the vocabulary alone (stems seen with several endings) split "walk" into wal + k and was dropped.

| B, E6 chrF | eng_v4 | + ENDINGS=learn | + the noun's role in its form key (`FORM_ROLE`) |
|---|---|---|---|
| Hebrew → Modern Greek | 41.14 | 42.02 | **42.31** |
| Hebrew → BSB | 39.39 | 38.88 | 38.87 |
| Greek → BSB | 38.34 | 38.10 | |
| Modern Greek E5, for comparison | 46.75 | | |

The paradigm class (the stem's commonest ending as a key for the regular rule, `ENDCLASS`) changed nothing.

- **Greek gains +1.2, English loses 0.2 to 0.5,** so the learner does not pass the "English loses nothing" test and does not
  go into a frozen version yet. On English the hand list's knowledge that "loved" comes from "love" (e-drop, y → ies) is
  worth more than consistent stems.
- **Greek E6 is still 4.4 behind E5.** The loss is in the noun's form (911 nouns, E5 right and E6 wrong, almost all "form
  seen"): Greek case comes from the syntax, and the Hebrew cell (state, number, prefixes) does not predict it. The clause role
  helps a little (+0.3). E5 gets the case right because it keeps the whole rendering per lemma and context.
- **Short words are not split** (stem ≥ 3 letters: γη, υιός), and accent shifts (άνθρωπος / ανθρώπου) break a family.

## 5. Next

1. **The ending learner, second try:** use the hand list where it is right (as a prior the data can overrule) or let the
   learned split compete with the list per word, so English loses nothing; compare letters without accents inside a family;
   a case key from the source syntax (the governing preposition, the role, the construct chain) for case languages.
2. The Greek function-word list: a second test so that verbs like έχω drop out.
3. eng_v4 is frozen with these (section 4).
4. The NLLB instrument tests when the models finish.

## 6. Later the same day: the corpus from lexeme-aligner's BSB layer, eng_v5, the Greek case keys (eng_v6)

**The corpus** is now built from lexeme-aligner's BSB layer v1.0 (`data/build_la.py` -> `data/nt_la.db`, `ot_la.db`; joined tokens
split by their table rows). eng_v4 measured on it, B: NT E6 38.34 -> 39.11, Tanakh E6 39.39 -> 39.71 (the cleaner alignment alone).

**eng_v5** = eng_v4 + the learned endings (`ENDINGS=hybrid`), on that corpus. English equal to eng_v4 (B E6 NT +0.05, Tanakh +0.14;
dev -0.21 / +0.06); Modern Greek +1.3 (section 4). Swap tests E6: future 1.00, aorist 0.98, plural 1.00.

**The Greek case gap.** A new context key, `GOV_KEY`: the word that governs a noun (a separate preposition by its lemma, the object
marker אֵת, a construct noun, a verb), read in the noun's form key with its role (`FORM_ROLE`). Hebrew -> Vamvas, B, E6:

| | chrF | noun form right |
|---|---|---|
| eng_v5 | 41.83 | 0.306 |
| + FORM_ROLE | 42.45 | 0.314 |
| + GOV_KEY | **42.81** | **0.326** |

Paired bootstrap: GOV_KEY alone +0.36 [0.27, 0.44]; both +0.98 [0.87, 1.09]; on Hebrew -> BSB both -0.02 [-0.04, 0.01] (English
loses nothing). Frozen as **eng_v6** (`eng_v6/`, both on by default). E6 is still 3.9 behind E5 (46.71) on Modern Greek.

## 7. What E6 still lost on Modern Greek, and eng_v7

Where eng_v6 E6 loses to E5 on Hebrew -> Vamvas (B: 1,612 tokens E5 exact, E6 not; 699 the other way), `r3/heb_gap3.py`,
`r3/gap3b_vamvas_v6.txt`. Most are not case endings:
- **the words after a noun** (about 350): Greek has article + noun + possessive («η καρδία σου», «δύναμις αυτού»); E6 gave
  «καρδία» or «αυτού δύναμις». E6 was built on English, where nothing follows the noun: the cell's post words (the cell pattern
  holds pre, ending, post) were folded into the word choice and placed before the noun, or lost;
- movable ν on verbs (about 90: «είπε» / «είπεν»), a spelling choice;
- articles before names («του ιεροβάαλ»), the second word of the future «θέλω + verb», and true word choice.

**POST_CELL** (`engine/gen6.py`): the function words after the word come from its cell (and the lemma's own, as PRE_LEX), as the
words before it do. Paired bootstrap, B, E6:

| | all classes | nouns only (`POST_CELL=noun`) |
|---|---|---|
| Hebrew -> Vamvas | +2.01 [1.85, 2.20] | **+2.11 [1.95, 2.28]** |
| Hebrew -> BSB | -0.03 [-0.09, 0.03] | +0.02 [-0.00, 0.04] |
| Greek NT -> BSB | -0.08 [-0.13, -0.02] | -0.00 [-0.01, 0.00] |

Frozen as **eng_v7** (`eng_v7/`: eng_v6 + `POST_CELL=noun`). Hebrew -> Vamvas, B: E5 46.71, **E6 44.91** (eng_v5 41.83, eng_v6
42.81); the E5-E6 gap 4.9 -> 1.8 in two steps. Left: articles before names, the future's second word, movable ν (worth an
equivalence in the measure rather than a rule: it is free variation).

## 8. Rung 2: Greek NT → Modern Hebrew (HEBM95), and the prefix switches (2026-10-26, evening)

Corpus `r3/data/hebm95_nt.db` (`hebm95/build.py`: lexeme-aligner's HEBM95 layer on our tokenizer, fingerprints checked; 7,903
verses, 118,087 links, 505 function words derived from the alignment). HEBM95 is © Bible Society in Israel: local only.

chrF on set B, eng_v7: E1 32.38, E2 32.74, E5 **34.06**, E6 32.99, E7 33.47; τ 0.81 → 0.87; word choice 0.32.
E5 right / E6 wrong 832 tokens, the reverse 416; the biggest kinds: verbs, other word 258; nouns, other word 252; nouns, same
word with another prefix 234. E6 learns endings only; Hebrew writes its function words as prefixes.

Two switches, both language-neutral (no list of prefixes):
- `PREFIXES=n` (cells.learn_families): a family member is prefix (≤ n letters) + the shared stem + ending; the form is written
  `pre>+ending`. On HEBM95 it finds ו ה ב ל מ, the verb prefixes י נ ת, and וה וב by itself.
- `PRE_FN=1` (cells.add_pre_fn, gen6.rolekey): the form key of nouns and verbs adds the function words directly before the
  token (καί, ἐν, ὁ), the same for training and rendering.

E6, paired bootstrap, ON − OFF:

| | HEBM95 | BSB-NT | BSB-Tanakh | Vamvas |
|---|---|---|---|---|
| PREFIXES=3 | +0.16 [0.01, 0.31] | | | |
| PRE_FN | +0.08 [0.01, 0.16] | | | |
| both | **+0.24 [0.09, 0.38]** | −0.04 [−0.09, 0.01] | −0.07 [−0.10, −0.04] | −0.27 [−0.36, −0.17] |

Gate (`PREFIXES=auto`, `PRE_FN=auto`): learn with prefixes, keep them only when at least 0.3 of the family words carry one
(HEBM95 0.60; BSB-NT English 0.05). Bootstrap with the gate: HEBM95 E6 **+0.24 [0.09, 0.38]** (gate on), Vamvas **0.00 [0.00, 0.00]**
(gate off). Frozen as **eng_v8** (`eng_v8/`: eng_v7 + PREFIXES=auto, PRE_FN=auto).

Before the gate: not a default. They are switches for a prefixing target, set per language (eng_v7 unchanged). The gain is a quarter of
the E5–E6 gap: most nouns are "form seen" (1,859 of 2,336 in B's first 600 verses), and the memory of a seen form is what
decides. Next for rung 2: the verb gap (other word 258), which is word choice, not form.

Modern Greek: the derived auxiliaries and articles as function words cost E6 (aux only −0.80 [−0.99, −0.62], articles only
−0.38 [−0.58, −0.20]); that route is dropped. The 1.8-point E5–E6 gap stays open.

**eng_v8 on HEBM95, set B** (`r3/v8_hebm95_B.jsonl`): chrF E1 32.38, E2 32.74, E5 34.06, **E6 33.23** (v7 32.99), E7 33.53; form
exact E5 0.302, E6 0.286. Gap tokens (`r3/nt_gap8_hebm95.txt`): E5 right / E6 wrong 832 → 674, the reverse 416 → 490 (net 416 →
184). What remains: nouns other word 213, verbs other word 204, nouns other prefix 173. Its cases are mixed: a remembered form
of another word (alignment noise: ᾄδω → a form of "pursuers"), a rule form that is a real but wrong word, word choice. Rung 2 is
closed here; E5 stays the best stage on HEBM95 (as on Vamvas).

## 9. The Modern Greek gap: the article (2026-10-27) -> eng_v9

Of the tokens E5 rendered right and E6 wrong on Vamvas set B (1,386; 844 the other way), about 660 were the article:
missing in E6 (411 nouns: «του ιεροβάαλ» -> «ιεροβάαλ»), another form not agreeing with the noun (189: «της πόλιν»), extra (78).
Cause: E6 chose the noun's form by its case but took the words before it from elsewhere, and `LEX_ART` (the lexicon's
"takes the article") looked for English "the", so it did nothing on any other target.

`ART=learn` (`engine/gen6.py`): the target's articles learned from the alignment, two routes (the words linked to the source
article; the word before nouns with the `art` feature against nouns without), both requiring the word to stand before >= 50
different nouns and to be a noun's whole rendering in <= 5% of its uses. Then a noun's article is learned and chosen with its
form, as a pair (stem, key, words before) -> (article, head).

Learned: Vamvas αι η ο οι τα τας την της το τον του τους των; BSB-NT the; BSB-Tanakh the that this other; HEBM95 את של.

| E6, ART=learn on - off (paired bootstrap, set B) | chrF |
|---|---|
| Vamvas Tanakh | **+1.43** [1.28, 1.59] |
| BSB Tanakh | +0.41 [0.32, 0.52] |
| BSB NT | +0.14 [0.10, 0.19] |
| HEBM95 NT | +0.02 [0.01, 0.04] |

Frozen as `eng_v9` (eng_v8 + `ART=learn`). The E5-E6 gap on Modern Greek (1.8) is mostly closed; what is left: the noun's
other ending (same stem) and the movable nu, smaller groups.
