# Bridging the rules engine and the LLM / ICL / NLLB drafters: pilots and a plan (2026-10-29)

Public report; figures and method only. Examples from the texts are in the private appendix (`private/rules/bridge/NOTES.md`
on the box). Everything here was run on the lab's Danish workbench: Hebrew -> Danish, with Den Frie Bibel (DFB, CC0) as
the human reference, our own LLM drafts as a second corpus, and the rules engine eng_v10 (`lab/rules/eng_v10/`).

## 1. The question

The engine (rung 4, Danish) draws its words, forms, function words and order from aligned text and nothing else; it is
deterministic, inspectable and cheap, and it scores chrF ~38 on held-out verses. An LLM drafting the same verses scores far
higher. The question of this report is not which is better but **what the engine can do for the LLM, ICL and NLLB drafters
and what they can do for it**: six hypotheses (section 3), each tested as a pilot on the same verses with the same scorer,
plus a track that makes the engine itself as good as the data allows.

## 2. Setup

**Corpora** (all built by `lab/bridge/build_corpus.py` from align-text layers; never in git):

- `dfb_base.db`: DFB Tanakh, 11,138 verses aligned to the Hebrew by lexeme-aligner's align-text, base layer (no `--jev`: content
  links only, no function-word channel). Split: **test** = RUT, JON, JDG 6-8, EXO 3-4, NUM 13-14 (364 verses); **dev** =
  JDG 13-14, EXO 14, NUM 22 (116 verses); train = the rest (10,658). None of the test or dev books are in our own Danish
  drafts, so no system has seen them in any form.
- `dan_ot.db`: our Danish drafts (5,922 training verses, 17 books), the rung-4 corpus.
- `dfb_base+dan.db`: both (16,580 training verses; `merge_corpus.py`).
- A `--jev` layer of the whole DFB Tanakh (function words, cleaner links) was run at the end of the session; see section 6.

**Scorer** (`lab/bridge/score.py`): the Step A scorer generalised. The reference's alignment says what each Hebrew word is
rendered as; a draft is scored on word choice (content words, by stem), form (exact), function words (bag P/R against a
function-word list), order (Kendall tau of the Hebrew words' first occurrences), and chrF as a summary. It scores any text,
so the engine, the LLM and NLLB are on one scale. Paired bootstraps over verses (1,000 or 300 resamples) for differences.
The engine's own measure (`E.measure`) agrees on the components and is lower on chrF (it scores its own tokens): 32.7 vs 37.7
on the same dev verses.

**Engine on unseen verses** (`lab/bridge/engine_render.py`): the engine built on one corpus renders the Hebrew of another;
its per-word renderings are kept (`*.glosses.json`) for the prompt arms and the checker.

**LLM**: Claude (Fable 5.1) as a subagent that may read only the prompt file and must write a JSON of verses; one run per
arm unless stated; chapter-sized prompts (`lab/bridge/llm_arms.py`). Caveat: DFB is a public text; the LLM may have seen it.
Per-verse chrF of the LLM alone against DFB: no verse above 90, 7 of 116 above 80, 25 below 50; so no verbatim recall, but a
general familiarity with Danish Bible wording cannot be excluded.

## 3. Hypotheses and pilots

| | hypothesis | pilot |
|---|---|---|
| H1 | engine draft first, LLM post-edits | arm `postedit`: the engine's verse as DRAFT, "keep what is right" |
| H2 | engine as the tool that resolves words and forms, LLM writes the sentence | arm `glosses`: per Hebrew word the engine's rendering |
| H3 | engine as a checker of LLM/NLLB drafts | `check_draft.py`: flags where the draft lacks the engine's word; precision against the reference |
| H4 | engine output as extra NLLB training data | NLLB-200-600M fine-tuned Hebrew->Danish with and without engine renderings of unaligned verses |
| H5 | retrieved examples (ICL) with and without the engine | arms `icl` (8 training verses per verse by lemma overlap), `icl_gl`, and `lexicon` / `icl_lex` (the aligned lexicon instead of the engine's choice) |
| H6 | learn from where the LLM beats the engine | by-class breakdown of the gap; the engine on more aligned data |

## 4. Results on dev (116 verses; the test set is read once, section 5)

### 4.1 The engine and the LLM on one scale

| system (dev, 116 verses) | word choice | form | fn P | fn R | order tau | chrF |
|---|---|---|---|---|---|---|
| engine E5, trained on DFB base layer (10,658 v.) | 0.635 | 0.521 | 0.436 | 0.016 | 0.752 | 29.75 |
| engine E5, trained on our drafts (5,922 v.) | 0.624 | 0.517 | 0.633 | 0.355 | 0.720 | 37.67 |
| engine E5, trained on both (16,580 v.) | 0.670 | 0.556 | 0.672 | 0.297 | 0.743 | **38.05** |
| LLM alone, run 1 / run 2 | 0.820 / 0.820 | 0.778 / 0.772 | 0.817 / 0.816 | 0.747 / 0.745 | 0.750 / 0.750 | 66.68 / 67.24 |

Stages E2/E6/E7 are within 0.7 chrF of E5 on every corpus. The DFB base layer has no function-word channel, so the engine
built on it alone learns almost no function words (fn R 0.02); our drafts' alignment supplies them, and the two corpora
together give the best engine. LLM minus engine: +29.0 chrF [26.9, 31.2]. By class the gap is in verbs (choice 0.55 vs
0.78) and adjectives (0.39 vs 0.80), least in nouns (0.77 vs 0.85); where the engine's verb choice is right its form is
right 89% of the time, so the engine's shortfall is lexical choice, not morphology.

### 4.2 Prompt arms (H1, H2, H5): what the aligned data does for the LLM

| arm | what the LLM gets besides the Hebrew | chrF run 1 / run 2 | paired difference to LLM alone (run 1) |
|---|---|---|---|
| postedit (H1) | the engine's draft, to correct | 66.42 | −0.26 [−1.49, 0.86] |
| glosses (H2) | the engine's rendering of each Hebrew word | 66.88 | +0.20 [−0.69, 1.12] |
| icl (H5) | 8 training verses per verse by lemma overlap | 68.77 / 67.15 | +2.04 [0.67, 3.08]; run 2: +0.40 [−1.43, 1.91] |
| icl_gl | examples + the engine's glosses | 68.93 | vs icl: +0.21 [−0.86, 1.39] |
| lexicon | the aligned corpus's top-3 renderings per lemma, with counts | 68.22 / 65.11 | +1.59 [0.37, 2.65]; pooled over both runs: −0.29 [−1.06, 0.44] |
| icl_lex | examples + lexicon (prompts ~80 KB per chapter) | 66.09 | vs icl: **−2.65 [−4.20, −1.19]** |

Read with the run variance: two runs of the same prompt differ by 0.5 chrF (alone), 1.6 (icl) and 3.1 (lexicon). On 116
verses with two runs, **no evidence from the aligned data is shown to move the LLM's draft**: not the engine's draft, not its
per-word renderings, not retrieved examples, not the lexicon. The one firm effect is negative: both kinds of evidence at
once overload the prompt (−2.65, and the agent needed twice the tokens). Function-word recall is the only component that
moves with examples (+0.02 [0.008, 0.036] in run 1). Ten LLM runs were spent; a real test needs ≥5 runs per arm on the
364-verse test set (section 8).

### 4.3 The engine as a checker (H3)

`check_draft.py` flags each Hebrew content word whose engine rendering (by stem) is absent from the LLM's draft, and asks
the reference who was right. Engine trained on both corpora vs the LLM alone: 1,327 words with a rendering, 450 flags
(34%); the reference sides with the engine in **12%** of the flags (precision strict); the draft really lacks the
reference's word in 29%; recall of the draft's real misses 0.59. Precision is flat over the lemma's training frequency
(0.07–0.15 from <5 to ≥500) and over the engine's rule type (contextual 0.14, factored 0.11). The engine's disagreements
with the LLM are mostly its own synonym and form variance; as a word-level checker of an LLM draft it is not usable as
it stands. A checker would need the engine's confidence per word (agreement among the corpus's renderings), not its
single choice.

**On NLLB's drafts the same checker works** (same dev verses, engine on the jev corpus + drafts): 498 flags, precision
strict **0.32**, loose 0.53, recall of the draft's real misses 0.69 (the LLM: 0.12 / 0.27 / 0.60). The engine knows the
words a fine-tuned NLLB gets wrong, because both learn from the same aligned text and the engine's lexicon is the more
literal of the two; it does not know the words an LLM gets wrong, because those are beyond the corpus. So the checker's
use is drafter-dependent: on NLLB (and on any drafter near the engine's level) a flag is right one time in three before
any confidence filter.

### 4.4 The engine track on dev (H6)

Option sweep (ENDINGS, CHOICE_CTX, MID_KEYS, PRE_LEX, FORM_ROLE, HEB_SFX, GOV_KEY, NOWORD, LEX_ART, ART, POST_CELL each
off or changed): chrF 38.05–38.06 for all; the switches tuned on the Greek rung are inert on Hebrew→Danish at E5. The
learning curve is not: 2,072 / 4,145 / 8,290 / 16,580 training verses → 34.70 / 36.00 / 37.00 / 38.05 chrF (word choice
0.602 → 0.670), about +1 chrF per doubling and not flattening. **The engine's lever is aligned data**, which is where the
other drafters come in (section 8).

## 5. Test set

Each configuration was run on the test set once, after its dev work was over. Reference alignment for every figure here:
the `--jev` layer of DFB (`dfb_jev.db`, section 6); function-word list `dan_func.txt`.

| system (test, 364 verses) | word choice | form | fn P | fn R | order tau | chrF |
|---|---|---|---|---|---|---|
| engine E5, our drafts (5,922 v.) | 0.572 | 0.430 | 0.585 | 0.338 | 0.694 | 36.30 |
| engine E5, DFB base layer + drafts (16,580 v.) | 0.586 | 0.447 | 0.607 | 0.268 | 0.738 | 35.21 |
| engine E5, DFB jev layer (10,658 v.) | 0.590 | 0.450 | 0.599 | 0.477 | 0.599 | 38.08 |
| engine E5, DFB jev layer + drafts (16,580 v.) | 0.603 | 0.466 | 0.600 | 0.403 | 0.675 | **38.07** |
| NLLB-600M fine-tuned on DFB (10,475 pairs, 1,000 steps) | 0.632 | 0.536 | 0.646 | 0.642 | 0.600 | 49.70 |
| NLLB-600M fine-tuned on DFB + 10,474 engine renderings, 1:1 (H4) | 0.590 | 0.473 | 0.620 | 0.392 | 0.706 | 40.37 |
| the H4 model + 300 DFB-only steps (synthetic first, real last) | 0.635 | 0.536 | 0.654 | 0.649 | 0.603 | 49.60 |
| the DFB model + 300 DFB-only steps (control for the extra steps) | 0.641 | 0.543 | 0.649 | 0.646 | 0.608 | 49.91 |
| LLM alone (Claude), one run | 0.779 | 0.697 | 0.770 | 0.726 | 0.661 | 62.14 |

Paired differences on the test set: jev layer + drafts minus drafts alone: chrF +1.75 [1.24, 2.31], word choice +0.031
[0.019, 0.042], form +0.036 [0.026, 0.045], function words R +0.065 [0.055, 0.075]; minus base layer + drafts: chrF +2.86
[2.43, 3.26]. LLM minus engine (drafts): +25.9 [24.5, 27.1]. NLLB minus engine (jev + drafts): chrF +11.6 [10.6, 12.7],
but word choice only +0.029 [0.013, 0.046], form +0.07, function words R +0.24 [0.22, 0.26], and **order −0.075 [−0.10,
−0.05]**: the fine-tuned NLLB beats the engine on fluency (function words, endings), barely on which words, and the engine
orders the Hebrew words better. LLM minus NLLB: +12.5 [11.1, 14.0]. NLLB by class: nouns 0.64, verbs 0.61, adjectives
0.64 choice (the engine 0.63 / 0.48 / 0.47: NLLB's gain over the engine is the verbs). On Ruth + Jonah alone (133 verses) every system is lower (LLM
59.1, engine 31.9–33.7): DFB's wording there is further from the Hebrew word order. By class on test, LLM vs engine
(drafts): nouns 0.81 vs 0.63 choice, verbs 0.70 vs 0.48, adjectives 0.76 vs 0.47.

H4 method: `build_nllb_data.py --extra` adds the E5 engine's renderings (built on the DFB base layer + drafts) of the 10,474
Tanakh verses DFB lacks or the test and dev books exclude, as plain pairs beside the real ones, no tag; same test and validation
verses, same 1,000 steps (3 epochs over the mix, so 1.5 passes over the real pairs instead of 3). The two 300-step
continuations start from the saved models with `run_nllb.sh MODEL=...` on the real pairs only, same batch and a fresh
schedule, so they differ only in what came before. Scores: `score_nllb.py` on the same reference as every other row.

## 6. The engine track: as good as the data allows

The user asked for the engine to be made as "smart" as the data allows. Three things were tried; only one worked, and it
is the one the learning curve predicted.

1. **Options**: inert (section 4.4). The engine's switches were tuned on Greek→English and do not move Hebrew→Danish.
2. **Stages**: E2, E5, E6, E7 within 0.7 chrF of each other on every corpus; E5 stays the stage to use. On the jev corpus + drafts (dev): E2 39.55, E5 40.95, E6 40.07, E7 40.56.
3. **Data**: the whole DFB Tanakh (28 books, 11,138 verses) was aligned by lexeme-aligner's `align-text` twice: the base layer
   (content links only, Jev not used) and the `--jev` layer (function-word channel, cleaner links; 29,592 Jev requests,
   estimated $17.68). A corpus built from the jev layer has 126,289 links against the base layer's 98,994, and 173 Danish
   function words fall out of the alignment itself (words linked only through the function channel) with no knowledge of
   Danish in the code. The engine on it: dev 29.75 → 40.97 chrF (base → jev, DFB alone); with our drafts added 38.05 →
   40.95; on test 35.21 → 38.07. The gain is in function words (recall 0.02 → 0.49 on DFB alone) and in word choice (+0.011
   [0.001, 0.02] on dev, +0.031 on test over the drafts' corpus).

So the engine's ceiling moved by about three chrF points in one evening, entirely by better alignment of the same text, and
the learning curve (+1 chrF per doubling of aligned verses, not flattening at 16.6k) says more aligned text would move it
further. What the engine cannot get from more of the same data is the verbs and adjectives (section 4.1): their choice
depends on context the alignment does not carry. That is the bridge to the LLM (section 8).

Side findings for the engine: with the jev layer, DFB alone gives higher function-word recall (0.48 vs 0.40) but worse
order (tau 0.60 vs 0.68) than DFB + drafts; the drafts' alignment (our own aligner on our own drafts) carries more usable
order evidence. The derived function-word list, used as the scorer's list, shifts every figure (word choice 0.73, chrF
40.44 on dev) and is not comparable with the lab's list; the lab's list is kept for scoring, the derived list is a
by-product worth checking by a Danish reader.

## 7. What the literature says (read this session)

- **LLM-RBMT** (Owens Valley Paiute, AmericasNLP 2024, arXiv 2405.08997): the LLM never touches the low-resource text. It
  splits the English input into the simple SV/SVO sentences a rule-based sentence builder accepts, and turns the builder's
  structured output back into English; the rule system owns lexicon, morphology and sentence structure. Evaluated by
  embedding similarity, no parallel data. The division of labour (LLM for the source side and fluency, rules for the
  target language) is the opposite of our H1/H2 and is what makes sense when the LLM does not know the target language.
- **TULUN** (arXiv 2505.18683): NMT draft + LLM post-edit guided by glossaries and translation memories; +2.8 chrF over
  NLLB-54B on FLORES (six low-resource languages), +17-22 chrF++ on Tetun/Bislama domain tasks. No ablation of draft vs
  glossary vs examples in the abstract.
- **Dhao** (arXiv 2601.09982): fine-tuned NMT draft + LLM with retrieved examples recovers Tanakh chrF++ 27.1 -> 35.2 (NT-trained);
  the gain is attributed to the number of retrieved examples, not the retrieval method; the LLM "repairs severe failures".
- **Grammar-book synthetic data** (arXiv 2607.22376): LLM-extracted rules, examples and lexicons from grammar books generate
  synthetic parallel data for fine-tuning; beats seed-data baselines in 59-75% of 96 configurations, best +3 to +9 chrF++;
  gains are inconsistent and best-case.
- **Apertium synthetic data for NLLB** (WMT24, Moksha/Erzya), **DuTerm** (flexible terminology beats strict), **MTOB and its
  critique** (gains come from parallel examples, not grammar prose), **chrF++ caveats** (arXiv 2602.17425): as in the
  session's digest; they all point the same way: what transfers to an LLM is resolved, example-shaped evidence (parallel
  sentences, dictionary entries), not the system's own draft or its rules in prose.

## 8. Conclusions and plan

### What the pilots say

1. **The engine's output does nothing for the LLM** (H1, H2): neither its verse draft nor its per-word renderings move an
   LLM that is already 25–30 chrF above it. This agrees with the literature (MTOB critique, Aycock: gains come from
   parallel examples, not from a weaker system's analysis) and with the lab's earlier hint experiments (all null).
2. **Evidence from the aligned data, given raw, is not shown to help either** (H5): retrieved examples and the aligned
   lexicon each came out +1.5–2 chrF in one run and null in the next; pooled, null. The run variance of an LLM given
   evidence (1.6–3.1 chrF between identical runs) is larger than the effects being looked for, so nothing under ~3 chrF
   can be seen with fewer than five runs on 116 verses. Too much evidence is firmly harmful (−2.65).
3. **The engine as a word-level checker depends on the drafter** (H3): 12% precision on the LLM's drafts (its disagreements
   there are its own variance), **32% on NLLB's** (53% loose, recall 0.69) with no confidence filter at all. A checker
   needs the corpus's agreement per Hebrew word (how many renderings, how concentrated), which the engine has in its
   tables but does not expose; that is a one-day change and the next thing to try, first on NLLB, then on the LLM.
4. **Engine renderings as NLLB training data do not transfer** (H4). Mixed 1:1 with the real pairs for the same 1,000 steps,
   they cost 9.3 chrF [8.1, 10.5]: the model learned the engine's style (20 instead of 26 tokens a verse, function words 38%
   instead of 47%; function-word recall −0.25, word choice −0.04, form −0.06) and took over the one thing the engine does
   better, order (tau +0.11 [0.08, 0.13]). Three hundred further steps on the real pairs alone wash the style out: 49.60
   against a control given the same 300 steps, 49.91 (−0.30 [−1.21, 0.44]; word choice −0.006, order −0.006, both null; the control's own gain over its
   parent is +0.21 [−0.31, 0.79]). So the synthetic phase is dilution without transfer: nothing
   of the engine's order survives the real data, and nothing is lost either. Synthetic text that carries our drafts' word
   choices (the engine was built from them) is also not a clean source for a model meant to be measured against DFB.
   Untried: tagging the synthetic side so the model can keep the two styles apart, and a 1:4 mix; neither is cheap to
   measure to within 1 chrF with one run each, and the figures above leave little room for a gain.
5. **The engine's lever is alignment quality and quantity** (H6, section 6): +3 chrF from the jev layer of the same text,
   +1 per doubling of verses. Its remaining gap to the LLM is lexical choice in verbs and adjectives, i.e. context.

### The plan that follows

The bridge is not "engine output into the LLM's prompt" and not "LLM output into the engine's lexicon as is". It is the
**aligned data in the middle**, with each system doing what it is good at:

- **Alignment is the shared asset.** Every drafter is measured against it (this report's scorer), the engine is built from
  it, and the LLM's drafts become useful to the engine only once they are aligned (our own drafts, aligned, gave the
  engine its function words and order; DFB aligned with Jev gave it +3). So the pipeline step that pays is: draft (LLM
  or NLLB) → align (lexeme-aligner, Jev where the text is free) → corpus → engine and checker. The engine's learning
  curve says each aligned chapter still counts.
- **The engine as the measuring instrument, not the writer.** Its tables give per-word and per-construction expectations
  with counts; the scorer built from them is already the only way we compare drafters on one scale. The next build is
  the confidence-aware checker (point 3): flag a draft only where the corpus is near-unanimous and the draft differs, and
  measure its precision on dev as here. That is the engine's role in review (Step A) rather than in drafting.
- **The LLM as the drafter, with evidence rationed per clause.** The one firm negative (overload) and the lab's standing
  clause-by-clause rule point the same way: at most one kind of evidence per clause, chosen by the engine's confidence
  (a rendering the corpus agrees on is worth giving; a split one is not), never whole-chapter dumps. Test with ≥5 runs
  per arm on the 364-verse test set; expect effects of 1–2 chrF at most and plan the measurement for that.
- **NLLB as the cheap second drafter** for checking and for languages without an LLM: fine-tuning on the aligned corpus's
  text is the baseline (49.7 chrF after 1,000 steps on 10,475 pairs, 90 minutes on the local GPU, still rising); engine
  renderings as synthetic data are off the list (point 4). What NLLB needs from the engine is the checker (point 3) and,
  cheaper still, reranking: an n-best list rescored by the number of high-confidence flags, which needs no LLM. The data
  side is the same aligned corpus; the model is retrained when the corpus grows.
- **For a language without a Bible-fluent LLM (Kuni)** the LLM-RBMT division is the one to copy: the LLM works on the
  source side (clause splitting, sense choice, explicitation) and the engine's tables on the target side; the Kuni Step A
  scorer already exists, and a Hebrew→Kuni engine needs only the Kuni Genesis text aligned locally (no Jev: the text is
  NC-ND).

### Not done, and why

The Kuni leg (no user decision on Jev/Kuni; the Danish evidence transfers only partly), the LLM's post-edit of NLLB
output (the lab's earlier −2.8 result stands until the checker exists), and anything on the Hebrew side of the LLM
(clause splitting, LLM-RBMT style), which is a different experiment. Twelve LLM runs and ~$18 of Jev were spent.

## 9. Postscript (2026-10-30 morning): the Hebrew ↔ Greek lexeme bridge

The plan's Kuni paragraph rests on a bridge from the NT (aligned to the Greek) to the Tanakh: a Hebrew lexeme reaches its Greek
equivalents, and through them the target renderings the NT alignment already holds. The user's direction: no English pivot,
built once, reusable for every language. `lab/bridge/strong_bridge.py` builds it in three tiers, each marked in the output
so a consumer chooses how far to trust it:

| tier | source | pairs | Tanakh content tokens reached | NT content tokens reached |
|---|---|---|---|---|
| macula | MACULA Hebrew's curated per-occurrence Greek Strong's (CC BY 4.0), all counts kept | 4,643 | 85.8% | 78.5% |
| + lxx | verse co-occurrence of the Hebrew text with the Septuagint (GLAUx, CC BY-SA 4.0), Dice ≥ 0.3, both texts in one verse scheme (TVTMS maps) | 1,879 | 88.5% | 80.5% |
| + jev | `bridge_jev.py`: code proposes candidates (shared gloss words weighted by specificity, weak co-occurrence); Jev chooses one or none; 511 lexemes asked, 213 kept at p ≥ 0.5 | 212 | 89.6% | 83.6% |

What remains unbridged is of three kinds and is left so on purpose: names (5% of Tanakh content tokens; transliteration, not
bridging), Tanakh words whose Septuagint equivalent is not NT vocabulary (cedar, drink offering, ephod: nothing on the NT side
to reach), and NT-only concepts (disciple, apostle, baptize, crucify: Jev answered "none"). Lowering the co-occurrence
threshold adds collocates, not equivalents (cedar → wood, frankincense, scarlet), so it stays at 0.3. The bridge is
language-independent; bcv-query's own `lxx_bridge.tsv` (the macula tier, cut to four Greek lexemes per Hebrew one) is the
published version, and a request to update it follows once the user has looked at the tiers.

Next for the bridge (not done): a grammar bridge beside it (Hebrew conjugation to Greek tense and mood, from the same
Septuagint verse pairs), and a clause index over the NT clause layout (`kind`, `rule` are one vocabulary for both
testaments) so that a Hebrew clause finds NT clauses of the same shape with a bridged verb, whose target renderings exist
before any Tanakh verse is translated. That is the retrieval step of the plan's NLLB arm.
