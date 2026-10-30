# The Hebrew–Greek bridge in use: engine, checker, retrieval, LLM, Kuni (2026-10-30)

Follow-up to `REPORT-bridge-2026-10-29.md` (sections 8 and 9 set the agenda). Everything here is a pilot measured on the
Danish workbench and, for Kuni, on the team's Ruth and Jonah; nothing was drafted for production. Figures only; no protected
text is quoted (DFB and the Kuni text stay on the box; MACULA, GLAUx and the clause layouts are credited in section 1).

Held-out discipline: dev = JDG 13–14, EXO 14, NUM 22 (116 verses) for every tuning decision; test = RUT, JON, JDG 6–8, EXO 3–4,
NUM 13–14 (364 verses) once per final configuration; the reserved set 1KI 17–19, 2SA 11–12, JER 36–38 was not read. Unless a
table says otherwise, Danish figures are `lab/bridge/score.py` on the DFB Jev-layer reference with the derived function-word
list, as in the first report. Paired bootstraps over verses, 1,000 resamples, 95% intervals.

## 1. The bridge, once, for every language

Three layers, each built from open data and reusable for any target language (`lab/bridge/`):

| layer | from | what it gives | script |
|---|---|---|---|
| lexeme bridge | MACULA Hebrew (CC BY 4.0) Greek-Strong's column; GLAUx LXX (CC BY-SA 4.0) verse co-occurrence; Jev for the rest | Hebrew Strong's ↔ Greek Strong's with a tier and a weight; Tanakh 0.896 / NT 0.836 of content tokens covered | `strong_bridge.py`, `bridge_jev.py` |
| grammar bridge | the lexeme-bridged verb pairs in the 20,620 verses the LXX shares with the Hebrew | Hebrew conjugation × stem → the Greek tense/voice/mood it is rendered by (67,165 pairs) | `grammar_bridge.py` |
| clause index | bcv-commons' Hebrew and Greek NT clause layouts (one `kind`/`rule` vocabulary for both testaments) | 89,940 Tanakh and 29,682 NT clauses with verb lexemes and forms, content lexemes, shape; a retriever: for a Hebrew clause, NT clauses with a bridged verb, the same shape, an expected tense, shared content | `clause_index.py` |

The grammar bridge reads as expected (wayyiqtol qal → aorist active indicative 0.67; yiqtol → future; imperative → aorist
imperative 0.52), which is also the check that the lexeme bridge pairs the right verbs. On the 364 test verses the retriever finds
a bridged candidate for 92% of the 1,764 clauses, the best candidate has the identical shape for 18% and a strong verb, near
shape and expected tense for 35%. Retrieval weights (0.4 verb, 0.25 shape, 0.2 tense, 0.15 lexical) are untuned.

A bcv-query request (publish all lexeme-bridge pairs with their tier) is drafted locally and waits for the user.

## 2. The bridged engine: Greek NT alignment as Tanakh lexicon

DFB's New Testament was aligned to the Greek by lexeme-aligner's align-text with the Jev layer (user's go; $5.38 of a $10 cap;
the DFB NT is partial, 6,020 verses with text). From it a Greek → Danish engine corpus (`build_nt_corpus.py`), and from the
bridges a *bridged* rendering table for Hebrew lemmas: Hebrew lemma → Strong's → Greek lexemes (tier-weighted) → the NT corpus's
renderings of those lexemes, verb forms filtered by the grammar bridge's expected Greek tense/mood, nouns by number
(`bridge_engine.py`). Three engines on the same verses:

- **ot**: E5 on the Tanakh alignment (the known engine);
- **ot+nt**: E5, and where the Tanakh alignment has never seen the lemma, the bridged rendering;
- **nt**: no Tanakh alignment at all: Hebrew order, every content word by the bridge, prefixes dropped.

Lexical choice alone (`bridge_lexicon_eval.py`: content tokens of the test verses with a reference rendering; "covered" = the
table has an answer; accuracy = the top rendering's stem is the reference's):

| table | Danish coverage | acc@1 (covered) | acc@1 (all) | Kuni coverage | acc@1 (covered) | acc@1 (all) |
|---|---|---|---|---|---|---|
| ot (own alignment) | 0.960 | 0.550 | 0.528 | 0.711 | 0.343 | 0.244 |
| nt (bridged only) | 0.890 | 0.399 | 0.356 | 0.891 | 0.141 | 0.126 |
| ot, else nt | 0.974 | 0.557 | 0.542 | 0.899 | 0.312 | 0.280 |

(Kuni: Tanakh table from Genesis 1–30 as aligned locally, test Ruth + Jonah; section 5.) The bridged table alone chooses the right
Danish stem for 40% of the words it covers (14% for Kuni, whose NT alignment is by word parts and whose Genesis alignment is a
base layer); as a back-off it adds coverage without losing accuracy.

The bridge only fires where the Tanakh alignment has never seen the lemma (a looser back-off, bridging lemmas seen once, was worse
on dev: 31.24 vs 31.45 at 5% data). The condition that matters is therefore how much Tanakh alignment a language has, so the engine
was run on fixed random subsets of the training verses (seed 7), dev to decide, test once per size:

| Tanakh alignment used | verses | ot chrF | ot+nt chrF | Δ chrF [95%] | ot word choice | ot+nt | Δ word choice [95%] | bridged tokens |
|---|---|---|---|---|---|---|---|---|
| 5% | 829 | 32.12 | 34.12 | **+2.00** [1.71, 2.31] | 0.488 | 0.528 | +0.040 [0.033, 0.046] | 287 |
| 10% | 1,658 | 33.50 | 34.95 | **+1.46** [1.20, 1.73] | 0.515 | 0.546 | +0.031 [0.025, 0.037] | 194 |
| 100% | 16,580 | 38.43 | 39.00 | **+0.56** [0.41, 0.74] | 0.608 | 0.621 | +0.013 [0.010, 0.016] | 53 |
| nt only (dev) | 0 | — | 19.21 | | — | 0.306 | | 1,294 |

Test = 364 verses, paired bootstraps over verses. Form, function words and order are unchanged by construction (the bridge
supplies words, not rules). The gain is where the method is meant to be used: a language with little Tanakh alignment and a
complete NT. The NT-only engine (no Tanakh alignment, Hebrew order, no prefixes) is a floor, not a tool.

Reserved final set (1 Kings 17–19, 2 Samuel 11–12, Jeremiah 36–38, 181 verses held out of training; read once, after everything
above, full Tanakh data): ot 44.51 → ot+nt 44.54 chrF (+0.035 [0.01, 0.07]), word choice unchanged, 5 bridged tokens. On narrative
chapters of a fully aligned Tanakh there is nothing left for the bridge to add; the test-set gain came from Ruth, Jonah and Numbers
vocabulary that the training verses never showed. The two readings agree: the bridge is a low-data tool.

## 3. The confidence-aware checker

The checker (`checker.py`) is the engine's rendering table with a confidence rule: a Hebrew lemma seen n ≥ N times whose top
rendering holds a share ≥ T is *expected*; a draft that lacks every expected stem is flagged. Precision strict = the reference
has the expected word; loose = the draft's rendering differs from the reference's. Operating point chosen on dev: N = 5, T = 0.8.

| drafts (dev, 116 verses) | flags | precision strict | precision loose | recall of real misses |
|---|---|---|---|---|
| NLLB (fine-tuned on DFB) | 52 | 0.42 | 0.81 | 0.68 |
| LLM alone | 50 | 0.17 | 0.23 | 0.37 |

On NLLB drafts four flags in five mark a real deviation; on LLM drafts the flags are mostly paraphrase. Two uses were measured:

- **Reranking NLLB n-best by flags** (dev; 8 beams, 8 nucleus samples, merged 15.4 candidates per verse): null to harmful,
  beam −0.13 [−0.42, 0.05], merged −0.40 [−0.83, 0.02] chrF. Not taken to test. The checker sees words, not the sentence;
  the candidate with the fewest flags is not the best one.
- **The LLM repairing flagged clauses** (test, the flags per clause under the draft, "correct only where a CHECK line is
  right in context"): section 5. Null, as the precision predicts.

The checker's place is review (showing a translator the words a draft departs from), and Kuni (section 6), where the drafts
are far from the aligned text and half the flags are real.

## 4. NLLB with a retrieved hint

The retrieval-augmented form of the first report's H4: the fine-tuning source line carries, after a separator, the Danish verse
of the most similar clause the index finds (`build_nllb_retrieval.py`), from the translation's own NT (memory = NT: the hint
needs no Tanakh alignment at all) or from the NT and the Tanakh training verses (memory = Tanakh+NT; never the verse itself, never dev or
test). Same recipe as the plain model (NLLB-200 600M, consonantal Hebrew, 1,000 steps), test once:

| model | memory | hinted test lines | word choice | fn R | order τ | chrF | Δ vs plain [95%] |
|---|---|---|---|---|---|---|---|
| plain (first report) | — | — | 0.635 | 0.64 | 0.619 | 49.70 | |
| + NT hint | NT | 480 of 480 | 0.639 | 0.641 | 0.612 | 49.57 | −0.12 [−0.66, 0.42]; word choice +0.007 [−0.002, 0.017] |
| + Tanakh+NT hint | Tanakh+NT | 459 Tanakh, 21 NT | 0.627 | 0.635 | 0.609 | 48.77 | **−0.93** [−1.51, −0.37] |

The Tanakh+NT-hinted model (retrained at half batch after an out-of-memory stop; otherwise the plain recipe) is worse than the plain
model on chrF, −0.93 with an interval that excludes zero; word choice −0.005 [−0.014, 0.004] and order +0.009 [−0.009,
0.027] are null, so the loss is in forms and function words. A retrieved clause as a second input to a 600M model
is noise to it: the NT hint was null, the Tanakh+NT hint harmful. Retrieval has no place in the NLLB fine-tune at this data size;
it belongs to the LLM (next section), which can read the hint as evidence rather than as more source text.

## 5. The LLM with evidence rationed per clause

The first report's LLM arms gave the model the engine's output by the chapter (draft, glosses, examples, lexicon) and found
nothing. Here every verse is shown clause by clause (the Hebrew clause layout) and each arm adds ONE kind of evidence under the
clause it belongs to, never a dump (`llm_arms2.py`; the same Claude agent, one chapter per prompt, 364 test verses per run):

- **alone**: the verse and its clauses;
- **conf**: under a clause, the checker's confident renderings only (section 3's rule; 681 lines over the test set);
- **ret**: under a clause, the most similar NT clause through the bridges (section 1; score ≥ 0.6; 879 lines): the Greek and
  the Danish verse of this very translation it stands in;
- **repair**: an earlier draft and the checker's flags per clause, "correct only where a CHECK line is right in context"
  (101 lines).

| arm | runs | word choice | form | fn P | fn R | order τ | chrF per run | mean |
|---|---|---|---|---|---|---|---|---|
| alone | 5 | 0.789 | 0.704 | 0.770 | 0.725 | 0.660 | 62.64 62.02 62.59 63.29 62.61 | 62.63 |
| conf | 3 | 0.788 | 0.700 | 0.772 | 0.727 | 0.663 | 62.92 63.03 62.54 | 62.83 |
| ret | 5 | 0.793 | 0.708 | 0.775 | 0.741 | 0.670 | 63.73 63.57 63.99 63.09 63.46 | 63.57 |
| repair | 2 | 0.779 | 0.696 | 0.772 | 0.729 | 0.658 | 62.14 62.15 | 62.15 |

Paired bootstraps against alone (run k with run k, verses resampled, pooled over runs):

| arm (runs paired) | Δ chrF [95%] | Δ word choice | Δ form | Δ fn recall | Δ order τ |
|---|---|---|---|---|---|
| ret (5) | **+0.93** [+0.53, +1.32] | +0.004 [−0.000, +0.009] | +0.005 [−0.001, +0.010] | **+0.016** [+0.011, +0.021] | **+0.010** [+0.004, +0.018] |
| conf (3) | +0.41 [+0.07, +0.76] | +0.001 [−0.004, +0.005] | −0.001 [−0.006, +0.005] | +0.004 [−0.000, +0.009] | +0.008 [−0.001, +0.018] |
| repair (2) | −0.18 [−0.68, +0.35] | −0.008 [−0.016, −0.001] | −0.003 [−0.012, +0.004] | +0.006 [−0.000, +0.013] | −0.003 [−0.016, +0.013] |

The retrieved NT clause is the first evidence from the engine's side that moves the LLM at all, and it moves the components the
engine never could: function-word recall and order, i.e. the construction, not the word. The confident gloss is null (the LLM
already chooses those words), and repair is null (section 3). Each run is one agent pass; the arms are not tuned.

## 6. Kuni: the NT side by the morphed alignment

The user's direction: the Kuni Tanakh by the NT bridge, from the published morphed alignment. Data (nothing sent out; the Kuni text
stays on the box):

- **NT side:** lexeme-aligner's published layer `kvg-m_wbt+llm+jev-v4` (bcv-commons/full-alignments-llm; 27 NT books, aligned by
  word parts with the pinned Kuni segmenter, Jev layer) and the local by-parts split file. Two engine corpora
  (`build_kvg_nt.py`): the target unit as the written word, or as the part (prefix, stem, tone, suffix). 7,933 verses, 110,981
  linked source words; held out: Mark and James (test), Philemon, 2–3 John, Jude, Titus (dev).
- **Tanakh side:** the team's Genesis 1–30, Ruth and Jonah aligned locally by align-text, base layer only (no Jev on the team's text).
  Genesis = training (775 verses), Ruth + Jonah = the Kuni Tanakh test (133 verses, never built from).

Greek → Kuni engine (E5, one run per corpus) on the held-out NT books: words corpus word choice 0.476, form 0.316, chrF 31.75;
parts corpus word choice 0.506, form 0.311 (its chrF, 30.39, is on part strings and not comparable). Parts help word choice
(+0.03), as the morphed layer's design intends.

Hebrew → Kuni, the bridged engine (section 2's three modes, Tanakh = Genesis base layer, NT = the words corpus; stems by the Kuni
segmenter; test Ruth + Jonah):

| engine | coverage | word choice | form | chrF | Δ vs ot [95%] |
|---|---|---|---|---|---|
| ot (Genesis only) | 0.554 | 0.256 | 0.202 | 14.24 | |
| ot+nt (bridge where Genesis never saw the lemma) | 0.935 | 0.315 | 0.246 | 20.66 | chrF **+6.43** [5.78, 7.08]; word choice +0.059 [0.046, 0.075] |
| nt only | 1.000 | 0.182 | 0.107 | 15.98 | chrF +1.75 [0.78, 2.76]; word choice −0.073 [−0.102, −0.042] |

This is the Danish low-data row at a lower data size, with the same shape: the bridge fills what the small Tanakh alignment lacks
(coverage 0.55 → 0.94) and the NT-only engine is a floor. Function words are zero throughout: the base layer has no
function-word channel, and the Tanakh side was aligned whole-word, in isolation from the NT and without Jev, which the user
corrected the same afternoon (next).

**The whole-scope run (the user's direction).** The team's whole text, 30 books, aligned as one set with the newer align-text:
the NT first, then the Tanakh with lexeme-aligner's own NT bridge; once by words and once by PARTS (the pinned Kuni segmenter's
split, the chain on the parts view, folded back to words), with Jev on Genesis, Ruth and Jonah by parts ($2.25). Ruth is the
check, since the published morphed layer covers the identical Ruth text: content links of our runs against it (precision /
recall) are 0.505 / 0.462 for the Tanakh-only base run, 0.524 / 0.473 with the NT bridge, 0.532 / 0.466 by parts, 0.490 / 0.490 by
parts with Jev; function links appear only with the Jev layer (0.27 / 0.28). Two Jev-by-parts layers of the same recipe on the
same Ruth text, one with the team's NT and one with eBible's, agree on half of the content links; and the base chain run twice
with nothing changed agrees with itself on two thirds (0.67 / 0.65), the two runs scoring 0.524 / 0.473 and 0.564 / 0.495 against
the published layer. The chain's own variance is as large as the NT bridge's measured effect, so a pooled prior has to be
measured against it with several paired runs.

The Jev-aligned Tanakh corpora (Genesis train, Ruth + Jonah test with the Jev links as reference; 11,998 linked source words
against 8,552 from the base layer, 64 derived function words) change the Kuni table:

| engine (Jev Tanakh corpora) | coverage | word choice | form | fn R | chrF | Δ vs ot [95%] |
|---|---|---|---|---|---|---|
| words: ot | 0.802 | 0.319 | 0.145 | 0.316 | 19.22 | |
| words: ot+nt | 0.937 | 0.374 | 0.179 | 0.323 | 22.62 | chrF **+3.40** [2.79, 4.00]; word choice +0.055 [0.042, 0.069] |
| words: nt only | 1.000 | 0.228 | 0.095 | 0.012 | 15.98 | chrF −3.25 [−4.38, −2.05] |
| parts: ot | 0.802 | 0.339 | 0.157 | 0.263 | 17.51 | |
| parts: ot+nt | 0.937 | 0.393 | 0.193 | 0.273 | 21.01 | chrF **+3.50** [2.90, 4.13]; word choice +0.054 [0.041, 0.068] |

(The references differ from the table above, so the rows are not comparable across tables; within this table everything is
paired.) The Tanakh side alone now covers 80% of the test lemmas and has function words; the bridge still adds 3.4–3.5 chrF and
+0.055 word choice, and the NT-only engine falls below the Tanakh engine, as it should once the Tanakh alignment is sound. Parts give
+0.02 word choice over words on both sides, the morphed layer's purpose.

**Lexeme-aligner's bridge and ours.** Its NT→Tanakh prior (credited to this project's idea of 2026-10-27) takes the LXX Greek of a
Hebrew lexeme from its prior pack and the edition's own NT eflomal renderings. The pack is exactly our MACULA tier: coverage of
Hebrew content tokens 0.858 (the whole Tanakh) against our three tiers' 0.896. Prior quality on Ruth's 845 content tokens with a
reference link, top candidate = the reference word: the pack's priors 0.137 (coverage 0.854); our bridge over the same eflomal
renderings 0.170 (0.892); over the published NT Jev layer's renderings 0.150. The wider bridge is worth about three points of
coverage and top-1; the request to lexeme-aligner (drafted locally, not sent) asks for a pooled prior over the whole scope of a
language's approved text rather than one edition's NT, the bridge table with tiers, and human-approved text only in the pool.

The bridged checker on the existing Kuni drafts (Step A's Ruth v11 and the Jonah test, 132 verses; the same rule, n ≥ 5 and
share ≥ 0.8): from the Genesis table 121 confident words, 21 flags, precision strict 0.43 / loose 0.48, recall 0.29; from the
bridged NT table alone 43 / 11 / 0.36 / 0.45 / 0.45; both 159 / 29 / 0.45 / 0.48 / 0.32. Half of the Kuni flags are right, which is
the Danish NLLB-draft figure's order, not the LLM-draft one: the Kuni drafts are far from the aligned text, and the checker finds
real misses there. The bridge adds a third more confident words and the same precision. With the Jev-aligned Genesis as the
table (next paragraph) the checker has more confident words (127) but lower precision (strict 0.20, loose 0.27): renderings
folded from parts are less often one whole word, so the word-level checker reads them badly. The right form on a morphed
language is a parts-level checker, with the draft segmented the same way; not measured yet.

## 7. What this changes in the plan

1. **The bridge is a low-data tool, and that is what it is for.** On a fully aligned Tanakh it adds half a chrF point on the test set
   and nothing on the reserved chapters; at 5–10% of the Tanakh alignment it adds 1.5–2 points, and on Kuni, where the Tanakh side is
   one base-layer Genesis, 6.4 points and a coverage from 0.55 to 0.94. Every new language starts in that condition. The bridged
   engine and checker are therefore the first thing a new language gets, before any Tanakh alignment exists, from its NT alignment
   alone.
2. **The checker is for review and for Kuni, not for reranking or for the LLM.** Its flags are right on NLLB and Kuni drafts and
   wrong on LLM drafts; reranking by flags and LLM repair are both null. It belongs in the team's review page, as the words a
   draft departs from, with the confidence shown.
3. **The retrieved NT clause is the first engine-side evidence that moves the LLM**, and it moves the construction (function words,
   order), not the word. It is cheap (no Tanakh data, one clause per clause, the translation's own NT) and it is the one arm worth
   repeating with tuned retrieval weights, a second clause per clause, and on Kuni with the team's NT.
4. **NLLB does not use a hint it was not trained to need.** The NT-retrieved hint is null; the Tanakh+NT hint (section 4) decides
   whether retrieval has any place in NLLB fine-tuning at this scale; if not, NLLB stays the drafter it already is (49.7) and the
   engine's side speaks to it only through the checker.
5. **Kuni, next:** the whole-scope alignment of the team's text by parts with Jev is now the Tanakh side (section 6); what follows is
   a parts-level checker on drafts (the draft segmented by the same segmenter), the bridged engine and checker on the team's
   review page, retrieval into the LLM with the team's NT, and, as the user set out, Jev on a draft after eflomal to align it
   for review (never to learn from it). The parts corpus is the one to build word choice from.
6. **Whole scope, for lexeme-aligner:** alignment is best from the widest pool of approved text of the language, across the
   bridge; lexeme-aligner's chain already bridges the Tanakh through one edition's NT, and a pooled prior over all approved text
   (with the tiered bridge table) is the request drafted locally. Machine drafts never enter the pool. The two-Jev-layers
   agreement of 49% on Ruth says any such change must be measured with paired runs against the chain's own variance.
7. **Housekeeping:** the reserved final set has now been read for the engine; a new one is chosen before the next final table.
   Retrieval weights, the (strong, stem)-keyed lexeme bridge, the bcv-query request and the lexeme-aligner request wait for the
   user.

## 8. Second round (2026-10-30 evening): retrieval on Kuni, confidence from agreement, low data, Zinza

**Retrieval into the LLM on Kuni.** The arm that worked on Danish, rebuilt for Kuni: the drafter gets the project's own chapter
materials (Step A's clause packs and the verse pack's decisions, grammar, parts and names), with and without one retrieved NT
clause per clause from the team's NT through the bridge. Jonah 1–4 and Ruth 1, 70 verses, five paired runs each, scored against the
Jev-by-parts links of the team's text.

| Kuni, 5 paired runs | chrF | word choice | form | fn R | order |
|---|---|---|---|---|---|
| alone (mean) | 36.5 | 0.575 | 0.333 | 0.465 | 0.474 |
| + retrieved NT clause (mean) | 40.6 | 0.620 | 0.377 | 0.572 | 0.490 |
| difference [95%] | **+4.15** [3.31, 5.02] | +0.046 [0.028, 0.065] | +0.044 [0.025, 0.064] | +0.107 [0.065, 0.149] | +0.017 [−0.039, 0.080] |

Four times the Danish gain, and on every component but order. Where the drafter knows the language least, a clause of the team's
own NT that does the same thing is the strongest evidence it gets. This is the rule-based side's way into the LLM that works:
aligned text of the language, chosen by the bridge, not the engine's renderings.

**Danish: tuning and a second clause.** Neither refinement helps on Danish. Two retrieved clauses per clause against one: chrF −0.29 [−0.83, +0.23], word choice −0.013 [−0.021, −0.005]; against alone +0.64 [−0.00, +1.28]. Weights tuned on dev against the untuned ones: −0.64 [−1.17, −0.14] (against alone +0.29 [−0.34, +0.88]). The dev proxy (shared wording between the retrieved verse and the reference) does not predict test, and a second clause dilutes the first. The untuned single clause, +0.93, stays the arm.

**Confidence from the chain's own variance.** The same base alignment run twice on the same text agrees with itself on two thirds
of Ruth's content links. The agreed links match the published layer at precision 0.71 (639 links), those made by one run only at
0.23 (664): a confidence channel at no cost but CPU. On review, aligning a draft twice with Jev and flagging a source word only when
both runs leave it unlinked raises flag precision from 0.62 to 0.68, recall 0.15 to 0.12: firm and soft flags. Aligning a draft at
all (precision 0.62) beats the engine's tables as a checker (0.28) by far; the parts-level checker beats the word-level one (loose
precision 0.38 against 0.31).

**The low-data curve on Kuni.** The bridged engine trained on part of the Jev-aligned Genesis, tested on Ruth and Jonah:

| Genesis data | engine | + NT bridge | gain [95%] |
|---|---|---|---|
| 5% (~1.5 chapters) | 15.1 | 22.5 | +7.4 [6.6, 8.2] |
| 10% | 16.0 | 22.2 | +6.3 [5.5, 7.0] |
| 25% | 17.7 | 22.3 | +4.6 [3.9, 5.3] |
| 50% | 18.7 | 22.7 | +4.0 [3.3, 4.7] |
| 100% (30 chapters) | 19.2 | 22.6 | +3.4 [2.8, 4.0] |

With the bridge the engine is flat from a chapter and a half to thirty: the team's NT carries over what Genesis would teach.

**Zinza prepared as the true low-data case.** The free Zinza NT aligned by words and by parts with the published segmenter
(language-analysis zin, the latest version); Greek → Zinza engine corpora built (Mark and James held out). On the base layers the
engine reaches word choice 0.43 by words and 0.49 by parts with coverage under half: the base alignment links 61,000 source
words, Kuni's Jev layer 111,000. The Jev layer by parts is the step that makes Zinza usable (about $10.50 high side); it is asked of
lexeme-aligner, after the analysis dataset is republished in format 3.

**NLLB closed.** Section 4: the Tanakh+NT hint costs 0.93 chrF. Retrieval belongs to the LLM.

## Sources and licences

MACULA Hebrew (Clear Bible, CC BY 4.0); GLAUx LXX (CC BY-SA 4.0); bcv-commons' lexeme spine and clause layouts; lexeme-aligner
v0.1.0 (align-text, the published Kuni layer `kvg-m_wbt+llm+jev-v4`); Den Frie Bibel (text and licence from the user); the Kuni
text (CC BY-NC-ND, never leaves the box); the Zinza NT (Wycliffe Bible Translators, CC BY-SA 4.0); NLLB-200 distilled 600M (CC BY-NC 4.0). Jev by TypeSafe.
