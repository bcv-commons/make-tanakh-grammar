# Measuring MT quality into low-resource, morphologically rich languages without a reader (2023-2026)

Scope: metrics that separate grammatical form from lexical choice; protocols for detecting small gains;
LLM-as-judge and back-translation judging when the judge cannot write (or barely reads) the language;
reference-free QE for unseen targets and cheaper proxies. Our setting throughout: Kuni (Papuan) and
Zinza (Bantu) drafts against one human translation, chapter chrF run-to-run sd ~1.0, per-verse sd 3-5,
word alignments to Hebrew/Greek, a verb position-class template per language, a blind LLM judge that
ranked the human text second, and a target of detecting 2-4 chrF or equivalent grammar gains.

Note on a term in the brief: "MorphScore" (Arnett & Bergen, COLING 2025; expanded to 70 languages in
2025) is a *tokenizer* metric (how well subword boundaries align with morpheme boundaries), not an MT
metric; its authors found it does not predict downstream model performance. It is listed under Gaps in
section 1, not as a usable MT measure.

## 1. Metrics that separate grammatical form from lexical choice; what detects inflection/agreement errors that chrF misses, and what is implementable from an alignment plus a morph template

### Takeaway
No metric published 2023-2026 isolates inflection/agreement from lexical choice for an arbitrary
low-resource target without a parser; the evidence base is (a) perturbation benchmarks showing where
chrF is weakest (case, POS-shift/affix, word order, gender: chrF detects 82-87% vs 92-99% for learned
metrics, but learned metrics are unavailable or unreliable for unseen languages), (b) character/byte-level
F-scores as the best reference-based lexical metrics for morphologically rich targets, and (c) rule-based
"violation catalogues" for Bantu concord (NSL-MT) and simplified MQM taxonomies (AfriMTE) that can be
turned into a slot-level checker built on an alignment and a position-class template. Validation of such a
checker against human judgement would have to be done locally; nothing published does it.

### Cited Findings
- DEMETR (35 perturbations, 10 source languages into English; per-perturbation detection accuracy, %):
  chrF vs BLEU vs COMET vs BLEURT-20 vs BERTScore vs COMET-QE: negation 98.7 / 90.5 / 98.8 / 100 / 99.1 / 85.4;
  gender (pronoun) 85.3 / 75.8 / 93.8 / 95.0 / 93.9 / 89.7; numeric 87.6 / 84.1 / 96.5 / 99.1 / 99.1 / 61.9;
  word-order swap 86.9 / 68.5 / 98.8 / 99.1 / 99.7 / 97.7; case (pronoun) 83.2 / 70.1 / 91.8 / 93.8 / 97.8 / 88.6;
  POS shift (affix change) 82.2 / 72.9 / 98.4 / 98.5 / 98.6 / 97.8; tense 88.6 / 92.3 / 89.4 / 94.2 / 97.1 / 78.0;
  aspect 94.1 / 97.4 / 96.1 / 99.6 / 99.8 / 64.5; function word 89.0 / 78.7 / 92.7 / 94.5 / 96.5 / 82.8.
  DEMETR has no separate agreement/inflection category; gender and number changes are filed under
  Accuracy, case/POS/tense/aspect under Fluency — [DEMETR](https://arxiv.org/abs/2210.13746)
- chrF catches a single changed affix (POS shift) only 82.2% of the time, the lowest of its rows, while
  negation (98.7%) and aspect (94.1%) are near the learned metrics; reference-free COMET-QE is the weakest
  on tense (78.0), aspect (64.5) and numbers (61.9) — [DEMETR](https://arxiv.org/abs/2210.13746)
- AfriMTE/AfriCOMET (NAACL 2024): on 13 African language pairs, segment-level Spearman with human DA:
  BLEU 0.237, chrF++ 0.277, COMET-22 0.328, AfriCOMET-STL 0.406, AfriCOMET-MTL 0.441 (averages); for the
  extreme pairs: eng-luo BLEU 0.182 / chrF++ 0.279 / COMET-22 0.062 / AfriCOMET-MTL 0.359; eng-twi 0.204 /
  0.178 / 0.096 / 0.101; eng-xho 0.090 / 0.161 / 0.071 / 0.146; eng-kik 0.273 / 0.295 / 0.202 / 0.410.
  Human data per pair (dev+devtest adequacy): 240-518 segments (eng-luo 499, eng-twi 516) —
  [AfriMTE and AfriCOMET](https://arxiv.org/abs/2311.09828)
- AfriMTE's simplified MQM, the low-resource adaptation of MQM used for those annotations: adequacy error
  types Addition, Omission, Mistranslation, Untranslated; fluency error types Grammar, Spelling, Typography,
  Unintelligible; annotators mark error spans then give a 0-100 DA with anchors at 0/34/67/100 —
  [AfriMTE and AfriCOMET](https://arxiv.org/abs/2311.09828)
- WMT24 metrics submissions on the AfriMTE challenge set (segment level, whole set, Pearson/Spearman/Kendall):
  MetricX-24 0.519/0.395/0.271; AfriCOMET-1.1 0.512/0.413/0.287; COMET-22 0.367/0.284/0.194; chrF-S
  0.312/0.233/0.158; chrF 0.283/0.219/0.149; xCOMET 0.222/0.212/0.145; BLEU 0.186/0.190/0.128. Weighted
  average across pairs: MetricX-24 0.627/0.483/0.346, chrF 0.359/0.296/0.205. The authors: correlations are
  "mostly below 0.5 for Spearman and Kendall"; English-Luo and English-Twi "show persistently" low values;
  gains come from "language-specific adaptation, cross-lingual transfer learning, and larger language model
  sizes" — [Evaluating WMT 2024 Metrics Shared Task Submissions on AfriMTE](https://aclanthology.org/2024.wmt-1.36/)
- WMT25 (16 pairs, including English→Bhojpuri, Maasai, Egyptian Arabic, Icelandic, Estonian, Serbian):
  at the segment level "reference-based baseline metrics (YiSi-1, chrF, and BERTScore) fill out the top three
  rank clusters, outranking recently strong trained metrics", while LLM auto-raters lead at the system level;
  challenge sets show "poor correlation with human judgments for low-resource languages" —
  [WMT25 Findings, Automated Translation Evaluation Systems](https://aclanthology.org/2025.wmt-1.24/)
- bytF (MT Summit 2025): byte-level n-gram F-scores with character/word back-off (bytF+, bytF++); on
  English→5 Indian languages, Chinese and Japanese they are "comparable ... or significantly better correlated
  than chrF and chrF++ with human judgments at the segment level"; default n-gram orders "often" correlate
  worse, so the orders must be tuned — [bytF](https://aclanthology.org/2025.mtsummit-1.29/)
- IndicMT Eval (MQM-based human scores, Indian languages): chrF++ has the highest correlation among
  overlap metrics, but overlap metrics as a class are worst against MQM — [IndicMT Eval](https://arxiv.org/abs/2212.10180)
- On extremely low-resource Indic varieties (Magahi, Bhojpuri, Chhattisgarhi), BLEU "tends to penalize
  morphologically rich languages" and the authors recommend reporting it only as a complement to chrF++ —
  [Evaluating Extremely Low-Resource MT: chrF++ vs BLEU](https://arxiv.org/abs/2602.17425)
- Older morpheme-level precedent (still the only direct one): Popović's WMT 2011 F-scores on words,
  morphemes and POS tags, correlated with WMT human judgements for en/es/fr/de/cs; the 2014 MTM summary
  reports morpheme- and POS-based F-scores "give even better correlations, especially on the sentence level"
  than word-level F (secondary source, slides) — [MTM 2014 evaluation slides](https://www2.statmt.org/mtm14/uploads/Main/EvaluationQE_MTM2014.pdf)
- tBLEU (2014) aligns reference and hypothesis words before n-gram matching so that inflection errors are
  "tolerated"; designed for morphologically rich targets, pre-neural — [tBLEU](https://mirror.aclweb.org/acl2014/W14-33/pdf/W14-3353.pdf)
- L'AMBRE (2021) scores morphosyntactic well-formedness (agreement) of generated text but needs a
  dependency parser, and parsers "are not well-suited for parsing ungrammatical (or noisy) text" —
  [L'AMBRE](https://arxiv.org/abs/2103.16590)
- NSL-MT (2025 preprint) catalogues Bantu violations generated by rule, without a parser: Swahili noun-class
  agreement (ki-toto m-zuri for m-toto m-zuri, severity 1.0), verb concord (1.0), tense marker (1.0), object
  marker (0.9), possessive concord (0.8); Luganda noun-class concord (1.0), tense-aspect (1.0), locative prefix
  (0.9), agglutination (0.8), tone (0.7). Generators are Python classes using regular expressions for suffix
  replacement, reordering, insertion/deletion, applied only where the pattern matches. The paper does not say
  how agreement targets are identified and gives no checker for model output; MT gains are on ~86 test
  sentences (NLLB-200 en→sw chrF++ 15.97→62.20, en→lg 42.24→49.02) and should be read as a catalogue, not an
  evaluation result — [NSL-MT](https://arxiv.org/abs/2511.09537)
- M-GATE (2026): linguist-crafted grammatical-error-detection items in 30 languages; the best model reaches
  MCC 0.36, models that translate competently "sit near chance on adversarial grammar items" and err toward
  under-flagging ungrammatical text; translation quality correlates r = 0.86 with log Common Crawl share —
  [M-GATE](https://arxiv.org/abs/2608.03803)
- MorphScore is a tokenizer-morpheme alignment metric; in the original study it "was not predictive of model
  performance", and the 70-language version finds morphological alignment "does not explain very much
  variance" in downstream results — [Why do LMs perform worse for morphologically complex languages?](https://arxiv.org/abs/2411.14198);
  [MorphScore, 70 languages](https://arxiv.org/abs/2507.06378)
- WMT24 and WMT25 compute chrF with sacreBLEU `chrF2|nchars.6|space.false` (WMT24) / `nc:6|nw:0` (WMT25),
  i.e. character 6-grams, no word n-grams, no spaces — [WMT24 Metrics findings](https://aclanthology.org/2024.wmt-1.2.pdf);
  [WMT25 findings](https://aclanthology.org/2025.wmt-1.24/)

### Inferences
- For Kuni and Zinza the published learned metrics (COMET-22, xCOMET, MetricX) are not an option as a
  *grammar* signal: on unseen African languages their correlations collapse to chrF's level or below
  (eng-twi: COMET-22 0.096 vs chrF++ 0.178; eng-luo 0.062 vs 0.279), and the one metric family that works
  there (AfriCOMET) needed 240-518 human-rated segments per language plus an African-centric encoder.
- The DEMETR pattern tells where chrF is blind: a single wrong affix or case marker costs chrF little
  (82-83% detection, i.e. roughly one in six affix errors passes), while negation and aspect changes are
  caught. A dedicated affix-slot measure therefore adds information rather than duplicating chrF.
- A parser-free slot checker is buildable from what we have: (1) take each verb in the draft that the
  alignment links to a Hebrew/Greek verb; (2) segment it with the position-class template (prefix slots,
  stem, suffix slots); (3) compare each slot with the same verb in the human reference where the alignment
  links both to the same source word; (4) report per-slot accuracy/F1 (subject marker, TAM marker, object
  marker, noun-class concord) separately from stem match. This is what tBLEU's "align, then match" and
  NSL-MT's regex rules do, with our alignment replacing their heuristics. Validation should copy DEMETR:
  corrupt the human text's slots with the NSL-MT catalogue (wrong class prefix, wrong tense marker, wrong
  concord) and check the measure penalises each corruption more than chrF does.
- The simplified MQM of AfriMTE (4 adequacy + 4 fluency types, spans, 0-100 DA) is the realistic human
  protocol for a team that can give a few hours: it was what produced usable correlations for Luo/Twi-class
  languages, and the "Grammar" fluency category maps onto the slot checker's output.
- Report chrF with the WMT settings (character 6-grams, no word n-grams) so numbers are comparable with the
  thresholds in section 2; bytF is worth a trial only if Kuni/Zinza orthography has sub-character structure
  (it does not; Latin script), so chrF stays.

### Gaps
- No 2023-2026 paper proposes or validates a parser-free morpheme-/affix-level metric for MT into an
  agglutinative or Bantu language; the morpheme F-score evidence is 2011 (European languages) and secondary.
- No published correlation with human judgement for any slot/agreement checker on a Bantu or Papuan language;
  the AfroMT per-noun-class accuracy analysis (2021) is the closest and is pre-2023.
- No tagged-accuracy measure for MT output found in the period; M-GATE's grammar task scores LLMs as error
  detectors on crafted items, not MT output.
- No MQM taxonomy specifically adapted for a Papuan language was found; AfriMTE's is the only low-resource
  adaptation with reported correlations.

## 2. Protocols: paired bootstrap, runs per system, minimum detectable effect, WMT significance standards; per-verse paired test sets

### Takeaway
WMT's standard is a paired permutation/bootstrap test with 1000 resamples at p = 0.05 plus rank clustering,
and recent calibration work puts a "humans would agree" chrF delta at about 1.6 (80% pairwise accuracy) to
3.0 (90%) at system level on ~500+ segments, while a chrF delta of ~0.8-0.9 is where bootstrap significance
becomes likely on WMT-size test sets; for LLM systems the repeated-run evidence is thin (10 samples or
10 judgments is the common choice; temperature 0 is near- but not fully deterministic), and the right
unit for our setting is the verse, paired per verse (Koehn 2004), across several runs.

### Cited Findings
- WMT24 Metrics: metric pairs are compared with the PERM-BOTH permutation test (Deutsch et al. 2021),
  "1000 resampling runs and ... p = 0.05", sampled in blocks of 100 with early stopping when p < 0.02 or
  > 0.50; system-level soft pairwise accuracy p-values use a paired permutation test with 1k resamples;
  ranks are assigned by greedy significance clusters — [WMT24 Metrics findings](https://aclanthology.org/2024.wmt-1.2.pdf)
- WMT24 Table 10 (minimum metric delta for an 80% chance that human MQM scores differ significantly,
  en→de / en→es / ja→zh): BLEU 5.4 / 11 / 1.4; chrF 3.0 / 2.1 / 3.5; spBLEU 4.3 / 9.1 / 4.0; COMET-22
  0.018 / 0.017 / 0.021; CometKiwi 0.024 / 0.027 / 0.050; MetricX-24-Hybrid 0.52 / 0.95 / 0.60; GEMBA-ESA
  4.5 / 1.5 / 4.8. The authors: "Contrary to the shared understanding that 2 BLEU improvement represents
  'significant' ... 5.4 BLEU improvement is required to be confident (80%)" for en→de —
  [WMT24 Metrics findings](https://aclanthology.org/2024.wmt-1.2.pdf)
- WMT24 Table 11 (minimum delta for an 80% chance that the metric difference itself is bootstrap-significant
  at p < 0.05): chrF 0.83 / 0.77 / 0.89; BLEU 0.97 / 0.93 / 0.89; COMET-22 0.0043 / 0.0055 / 0.0046;
  MetricX-24-Hybrid 0.11 / 0.15 / 0.14; GEMBA-ESA 0.82 / 0.85 / 1.4 — [WMT24 Metrics findings](https://aclanthology.org/2024.wmt-1.2.pdf)
- Navigating the Metrics Maze (ToShip23: 6,530 system pairs, 94 languages): metric delta needed for a given
  pairwise accuracy against humans, 70% / 80% / 90% / 95%: chrF 1.00 / 1.63 / 3.05 / -; BLEU 1.39 / 2.34 / - / -;
  COMET-22 0.35 / 0.56 / 0.94 / 1.53; CometKiwi-QE22 0.33 / 0.53 / 0.85 / 1.18; xCOMET-XXL 0.76 / 1.24 / 1.99 /
  2.74; BLEURT-20 0.66 / 1.07 / 1.73 / 2.44; chrF at 50% (coin toss) is 0.14. Delta-accuracy "stays roughly
  constant as testset size changes, while p-values fall as testsets grow"; delta variance "is higher for
  testsets under about 500 segments" — [Navigating the Metrics Maze](https://arxiv.org/abs/2401.06760)
- Segment-level meta-evaluation uses pairwise accuracy with tie calibration (acc*_eq), which credits a metric
  for predicting human ties and fits one tie threshold per metric per test set; system level uses soft pairwise
  accuracy (SPA), which weights each pair by the significance of both the human and the metric difference —
  [Tie calibration](https://arxiv.org/abs/2305.14324); [Soft pairwise accuracy](https://arxiv.org/abs/2409.09598)
- sacreBLEU implements paired bootstrap resampling (`--paired-bs`, default 1000 resamples, reports 95% CI
  and p-value, e.g. "26.6 (26.6 ± 0.6)") and paired approximate randomization (`--paired-ar`, default 10,000
  trials, "claimed to be more accurate ... when it comes to Type-I errors", Riezler & Maxwell 2005); p < 0.05
  is marked; seed 12345 — [sacreBLEU README](https://github.com/mjpost/sacrebleu)
- The per-sentence paired bootstrap is Koehn (2004), "Statistical Significance Tests for Machine Translation
  Evaluation" — [Koehn 2004](https://aclanthology.org/W04-3250/)
- Card et al. 2020 treat MT power analysis as a hard case (corpus-level BLEU, little unseen data) and simulate
  variance; a paper following their advice reports that "datasets with about 2,000 examples, with improvements
  of about 1 BLEU or higher, are statistically powered" — [With Little Power Comes Great Responsibility](https://arxiv.org/abs/2010.06595);
  [kNN-MT (applying Card et al.)](https://arxiv.org/pdf/2010.00710)
- GEMBA-MQM V2 (WMT25): "To reduce stochastic variance, each segment is scored ten times", outliers beyond
  2σ removed, reciprocal-rank weighted average; GPT-4.1-mini; severity weights 25/5/1 (minor punctuation 0.1).
  No single-run vs ten-run correlation is reported — [GEMBA V2](https://aclanthology.org/2025.wmt-1.67/)
- Non-deterministic MT (ACL Findings 2026): 10 candidates per source at temperature 0.5 (robustness at 10,
  20, 50); "the lowest-quality candidate generated by ND-MT consistently determines the overall system ranking
  across different sampling sizes" (the "buckets effect"); min-aggregated rankings were stable (Kendall 1.0 for
  BLEU/chrF++ at 20 and 50 samples); recommendation to report min/max/mean/std over samples and to state the
  temperature; chrF++ "exceeds 100 at higher temperatures" in their setup, which they call unreliable —
  [On Temperature-Constrained Non-Deterministic MT](https://arxiv.org/abs/2601.13729)
- Temperature 0 is not fully deterministic: a 2026 drift study at T = 0.0 and 0.7 (gpt-4o-mini, llama3.1-8b)
  finds residual run-to-run variation, citing frontier models that did not give identical completions across
  ten "deterministic" runs — [Quantifying non-deterministic drift in LLMs](https://arxiv.org/abs/2601.19934)
- M-GATE treats T = 0 as "effectively deterministic for reporting" with per-model CIs of about ±0.03-0.04
  MCC on the grammar task; residual differences concentrate "in items where the model is nearly split" —
  [M-GATE](https://arxiv.org/abs/2608.03803)
- MetricX-24 reports "each experiment with one random seed due to limited resources" —
  [MetricX-24](https://arxiv.org/abs/2410.03983)
- Mambai (retrieval-augmented LLM prompting): 41.9 chrF++ on a test set from the language manual vs 33.1 on
  a set from a native speaker, attributed to overfitting to the prompt material; a reminder that test-set
  provenance moves chrF more than prompt variants do — [Mambai study](https://arxiv.org/abs/2404.04809)
- eBible corpus (NLLB fine-tuning on 1,009 Bible portions, 833 languages): per fold "250 randomly selected
  verses are held out as the test set and 250 as the validation set", five folds; chrF3 medians by family
  52.5 (Afro-Asiatic) to 60.4 (Niger-Congo), Trans-New Guinea 60.1 ± 0.9, with the ± undefined and no CIs or
  significance tests reported; per-verse BLEU distributions are "broad" — [eBible Corpus](https://arxiv.org/abs/2304.09919)
- Dror et al. 2018 is the standard guide to choosing the test (paired, non-parametric for metric scores) —
  [The Hitchhiker's Guide to Testing Statistical Significance in NLP](https://aclanthology.org/P18-1128/)

### Inferences
- Minimum detectable effect, our numbers: with chapter chrF sd ~1.0 across runs, a paired comparison of
  n runs per system has se ≈ 1.0·sqrt(2/n) on the chapter mean, so one run each cannot tell 2 chrF from
  noise (se 1.41), 3 runs gives se 0.82 (a 2-point gain is ~2.4 se), 5 runs se 0.63. The published calibration
  says 1.6-3.0 chrF is where humans would agree at system level, so 2-4 chrF is a real target if (a) it is
  measured over several chapters (≥ ~500 verses, the point below which Kocmi et al. see delta variance rise)
  and (b) each system is run 3-5 times at a fixed temperature.
- Pair by verse, not by chapter: Koehn's bootstrap over verses with the two systems' outputs for the same
  verse is the right test for one human reference; per-verse sd 3-5 is absorbed by pairing. Report the
  bootstrap 95% CI of the mean delta and the fraction of verses where system A wins (a tie-aware win rate,
  in the spirit of acc*_eq), not only the p-value.
- Follow the ND-MT advice for LLM systems: report mean and min over runs; a prompt whose worst run is bad
  will rank badly under min, which is what matters when one draft goes to a team.
- When an LLM judge is part of the protocol, GEMBA V2's 10 judgments with 2σ trimming is the current WMT
  practice; fewer than that leaves run noise comparable to the effect sought.
- Build the held-out set the eBible way (verses sampled across books, 250 per fold) rather than one chapter:
  the Mambai result shows a single-provenance test set can move chrF by 9 points.

### Gaps
- No paper found that states how many independent runs per system are used to compare LLM translation
  *prompts* into a low-resource language, nor one that reports seed-to-seed chrF sd for such systems;
  the closest are ND-MT (10 samples, T 0.5, high-resource pairs) and GEMBA V2 (10 judgments).
- No published power curve for chrF at the sizes we have (20-50 verses per chapter); the 2,000-example /
  1-BLEU figure is for BLEU on high-resource news data.
- No protocol paper found that uses human-translated Bible verses as a paired bootstrap test set for
  drafting systems; the eBible paper's 250-verse folds are the only documented Bible-verse test design and
  it reports no significance testing.

## 3. LLM-as-judge for languages the judge cannot write or barely reads: GEMBA-MQM, reference anchoring, pivot/back-translation judging, biases

### Takeaway
Reference-free LLM judges on an unseen language correlate with humans at about τ 0.2 (Nupe: GEMBA 0.21,
CometKiwi-XXL 0.18) and show a fluency/translationese bias that is strongest in low-resource languages
(bias severity ~0.27 low-resource vs ~0.09 high-resource before mitigation); anchoring the judge to the
human reference by extracting semantic units first lifted τ to 0.71 in the one study that tried it
(106 sentences, five native speakers). There is no validated evidence that judging via back-translation
works, and round-trip scores track forward quality at system level but not at segment level.

### Cited Findings
- GEMBA-MQM's authors state WMT evaluations "primarily focus on high-resource languages", so its behaviour
  on low-resource languages is untested — [GEMBA-MQM](https://arxiv.org/abs/2310.13988)
- Nupe-English (LoResLM 2026; "zero prior representation"): on 106 randomly sampled test sentences rated by
  five native speakers (DA 0-100, adequacy/fluency/cultural naturalness, randomized, blind), Fleiss' κ / Kendall
  τ with humans: CometKiwi-DA-XXL 0.23 / 0.18; GEMBA 0.27 / 0.21; xCOMET (reference) 0.52 / 0.44; Ref-Anchor-MQM
  0.78 / 0.71. The authors attribute the failure to representations "never exposed to the language during
  pre-training", producing "a pronounced fluency bias, rewarding grammatically plausible output even when it
  diverges substantially from the source meaning" — [Anchoring the Judge (Nupe)](https://aclanthology.org/2026.loreslm-1.19/)
- Ref-Anchor-MQM: the judge first extracts Key Semantic Units from the human reference, classifies each in the
  candidate as Preserved (1.0) / Modified (0.5) / Lost (0.0), then assigns MQM errors (Accuracy, Terminology,
  Omission, Addition) with severities weighted 25/5/1, score = 100 − deductions. Worked example: a fluent but
  wrong NLLB output (BLEU 8.1) was flagged as a Major Terminology error while "GEMBA overvalued surface-level
  fluency" — [Anchoring the Judge (Nupe)](https://aclanthology.org/2026.loreslm-1.19/)
- Small open LLMs (≤13B) as reference-free judges on low-resource Indic pairs (WMT23 DA), zero-shot best
  Spearman/Kendall: en-gu 0.249/0.187, en-hi 0.254/0.188, en-mr 0.276/0.222, en-ta 0.363/0.290, en-te
  0.145/0.109; fine-tuned CometKiwi on the same pairs 0.637/0.467, 0.615/0.446, 0.546/0.390, 0.635/0.455,
  0.338/0.235; pairs with English as target score higher for every system (et-en CometKiwi 0.860) —
  [When LLMs Struggle: reference-less QE for low-resource languages](https://arxiv.org/abs/2501.04473)
- WMT24 AfriMTE challenge set, reference-free: GEMBA-ESA Pearson/Spearman/Kendall 0.403/0.330/0.243 vs
  MetricX-24-QE 0.486/0.381/0.262, AfriCOMET-QE-1.1 0.476/0.396/0.275, CometKiwi-XXL 0.215/0.181/0.125,
  xCOMET-QE 0.172/0.153/0.104 — [WMT24 submissions on AfriMTE](https://aclanthology.org/2024.wmt-1.36/)
- WMT24 main task: GEMBA-ESA ranked 2nd overall (0.711) but its rank was "significantly lower under ESA than
  for MQM", on 9 pairs including Czech→Ukrainian and English→Icelandic, "likely" because ESA produces no ties
  "whereas GEMBA_ESA produces them regularly" — [WMT24 Metrics findings](https://aclanthology.org/2024.wmt-1.2.pdf)
- WMT25: LLM auto-raters "top the rankings at the system level" but "still underperform" at the segment
  level; GEMBA-V2 (GPT-4.1-mini, 10 judgments) "places no worse than in the sixth cluster"; for English-Maasai
  the human annotations "frequently" mark the whole segment as an error (hallucinated text); auto-raters failed
  to detect catastrophic wrong-language/script output (Bhojpuri as a language mixture, Serbian in Latin script,
  Egyptian Arabic as MSA) — [WMT25 findings](https://aclanthology.org/2025.wmt-1.24/)
- Translationese bias (ICML 2026): judges (GPT-4o, Gemini-2.5-Flash, open models) prefer back-translated
  machine text over the human reference; items judged in both orders, counted only if consistent. Baseline bias
  severity by tier: Aya high 0.091 / mid 0.111 / low 0.272; Belebele 0.081 / 0.091 / 0.126; XL-Sum 0.071 /
  0.095 / 0.172 (low-resource sets include Amharic, Hausa, Yoruba, Zulu, Burmese, Guarani). Machine win rate
  rises with Cross-Lingual Alignment Discrepancy and falls with sequence surprisal, i.e. judges favour outputs
  "closer to the English latent manifold" (an "English-anchoring bias" hypothesis); the DIBJudge fine-tune cuts
  bias (Belebele S_bias 0.247 → 0.083) — [Mitigating Translationese Bias in Multilingual LLM-as-a-Judge](https://arxiv.org/abs/2603.10351)
- Position bias in LLM judges is systematic, varies by judge and task, is weakly affected by prompt length and
  "strongly affected by the quality gap between candidates" (15 judges, pairwise and list-wise) —
  [Judging the Judges: position bias](https://aclanthology.org/2025.ijcnlp-long.18/); repetition stability and
  position consistency as the measures — [Position bias measures](https://arxiv.org/abs/2406.07791)
- Multilingual judge study (English/Spanish/Basque): with in-domain data, fine-tuned small models reach
  proprietary-model performance; without it, zero-shot larger models are better out of domain; multilingual
  supervision gave +4.2 Pearson for Basque; fine-tuning on out-of-domain data can hurt —
  [Towards Reliable Multilingual LLMs-as-a-Judge](https://arxiv.org/abs/2605.28710)
- A 2026 survey finds judge reliability for low-resource languages "often only validated for a small number of
  languages" and "often overestimated" — [Challenges and Recommendations for LLM-as-a-Judge in Multilingual Settings](https://arxiv.org/abs/2607.02235);
  English-trained judges "do not consistently transfer to typologically distant or low-resource languages" —
  [Cross-Lingual LLM-Judge Transfer](https://arxiv.org/abs/2603.18557)
- Read-vs-write asymmetry: LLMs "perform better with low-resource languages as a source than as a target"
  (six Romansh varieties; Gemini 2.5 Flash scores lower generating a specific variety) —
  [Translation Asymmetry in LLMs (Romansh)](https://arxiv.org/abs/2603.25489); MuG-Eval avoids LLM-as-judge for
  low-resource generation because judge quality "degrades outside a few high-resource languages" —
  [MuG-Eval](https://arxiv.org/abs/2505.14395)
- Translate-then-judge in a classification task: an LLM judge working directly in low-resource languages did
  worse than first machine-translating the text into English — [Translate, then Detect](https://arxiv.org/abs/2509.14493);
  translating benchmarks into 198 languages gave results correlated 0.95 (Spearman) with human-translated
  versions, yet MT "is not yet a fully reliable method" — [WMT25 benchmark-translation paper](https://aclanthology.org/2025.wmt-1.1.pdf)
- Round-trip translation (ACL Findings 2023, FLORES 33 languages incl. Burmese, Hausa, Pashto, Khmer):
  system-level Pearson between RTT and forward scores 0.94-0.96 (chrF 0.96) for mBART50/M2M-100, but RTT
  features alone predict segment DA poorly (en-de Kendall: RTT-chrF 13.6, RTT-BERTScore 25.9, COMET-QE-DA 42.7,
  all ×100); RTT fails when a system copies unknown source words (SMT with copying: τ −0.4 to 0.2) —
  [Rethinking Round-Trip Translation](https://aclanthology.org/2023.findings-acl.22/)

### Inferences
- Our blind judge ranking the human text second is the expected failure, not an anomaly: in an unseen
  language a reference-free judge rewards what looks like fluent, English-aligned text, and the human
  translation is the least translationese candidate. The measured low-resource bias (about one consistent
  judgment in four favouring the machine text on Aya) is of the size that reorders a 3-4 way ranking.
- The one protocol with evidence is reference-anchored: give the judge the human verse, have it list the
  semantic units, then score each draft against the units (Preserved/Modified/Lost) before any fluency
  judgement. This uses the judge's reading, which the Romansh asymmetry suggests is the stronger side, and
  does not ask it to write. It is a reference-based measure, so it can only be run on verses the team has
  translated, i.e. the held-out set of section 2.
- Mechanics to carry over regardless of judge: both presentation orders, count only consistent verdicts,
  10 judgments with trimming, and a separate "is this the right language/script, is anything copied from the
  source" check, since even WMT25's strongest auto-raters missed wrong-language output.
- Back-translation judging: treat as unvalidated. Round-trip scores are informative only at system level and
  only when the drafting system cannot copy source words, which an LLM drafter can; and if the judge compares
  back-translations it reintroduces the translationese preference through the back-translator.

### Gaps
- No study found of an LLM that reads a language at a middling level (chrF ~50 into English) acting as a
  ranking judge; the Nupe result is for a language with zero exposure, and no paper stratifies judge accuracy
  by the judge's own translation ability into or out of the language.
- No validated back-translation-based judging protocol for MT into an unseen language; RTT evidence is
  pre-LLM-judge and system-level.
- Ref-Anchor-MQM is one study, 106 sentences, one language; its κ 0.78 is also the annotators' own agreement
  figure, so the judge's independent reliability is not separately established; the judge LLM used in the
  anchored protocol is not clearly reported in the parts of the paper I could read.
- The per-judge translationese bias for GPT-4o vs Gemini-2.5-Flash is in figures I could not read.

## 4. Reference-free QE for very-low-resource targets: CometKiwi-XL/XXL, MetricX-24, xCOMET on unseen languages; cheaper proxies

### Takeaway
Every current QE model is unreliable on a language its encoder did not see: CometKiwi's model card says so,
AfriMTE measures it (CometKiwi Spearman 0.026 Twi, 0.161 Luo, −0.030 Xhosa; CometKiwi-XXL 0.18 average on
the WMT24 challenge set), and WMT25's reference-free Maasai track is dominated by whole-segment hallucination
errors. The cheap proxies with evidence are negation/number checks (where chrF itself is strong), round-trip
consistency at system level, and wrong-language / copied-source detection; alignment-coverage proxies have
no published validation.

### Cited Findings
- CometKiwi (WMT22) model card: "results for language pairs with uncovered languages are unreliable"; the
  model was trained to handle unseen languages via multilingual pretraining and few-shot fine-tuning —
  [wmt22-cometkiwi-da model card](https://huggingface.co/Unbabel/wmt22-cometkiwi-da); the XL/XXL versions
  again target unseen test pairs — [Scaling up CometKiwi](https://arxiv.org/abs/2309.11925)
- AfriMTE reference-free Spearman, CometKiwi vs AfriCOMET-QE-STL vs -MTL: eng-twi 0.026 / 0.061 / 0.060;
  eng-luo 0.161 / 0.217 / 0.174; eng-xho −0.030 / 0.085 / 0.130; eng-kik 0.247 / 0.415 / 0.317; eng-hau 0.245 /
  0.482 / 0.586; eng-ibo 0.188 / 0.631 / 0.574; eng-swh 0.756 / 0.587 / 0.718; averages 0.274 / 0.357 / 0.389
  (Pearson 0.306 / 0.502 / 0.499) — [AfriMTE and AfriCOMET](https://arxiv.org/abs/2311.09828)
- WMT24 challenge set, QE: MetricX-24-QE Spearman 0.381, AfriCOMET-QE-1.1 0.396, MetricX-24-Hybrid-QE 0.359,
  GEMBA-ESA 0.330, CometKiwi-XXL 0.181, xCOMET-QE 0.153 — [WMT24 submissions on AfriMTE](https://aclanthology.org/2024.wmt-1.36/)
- MetricX-24: mT5-XXL (13B), hybrid training on source+hyp, hyp+ref and source+hyp+ref; DA data from WMT
  2015-2022 (~50 pairs), MQM from only en-de, en-ru, en-zh, zh-en; synthetic examples for empty output,
  gibberish, "fluent but unrelated", undertranslation (20-80% of words dropped), missing punctuation,
  reference-matching; evaluated only on WMT23 MQM/DA, no unseen-language evaluation; one random seed —
  [MetricX-24](https://arxiv.org/abs/2410.03983)
- xCOMET-XL's language list is inherited from XLM-R XL (100 languages; neither Kuni nor Zinza is in XLM-R) —
  [XCOMET-XL model card](https://huggingface.co/Unbabel/XCOMET-XL)
- Zero-shot transfer can work when the pretraining encoder saw the language: MetricX-24 and xCOMET scored
  strongly on Esperanto, which is in XLM-R and is Romance-derived; the authors attribute it to the pretrained
  encoders — [Open MT for Esperanto](https://arxiv.org/abs/2603.29345)
- Low-resource and non-English-centric pairs "get skewed CometKiwi scores" in a 2025 multilingual LLM-MT
  report — [NiuTrans.LMT](https://arxiv.org/abs/2511.07003); CometKiwi-XL's per-language means are displaced
  against quality on an Indic QE benchmark, so pooled correlations fall — [IndicQE-APE](https://arxiv.org/abs/2608.16344)
- WMT24++ (55 languages): "absolute metric values are not comparable across languages, some MT systems may
  be favored if they only support languages for which the metric scores are high" — [WMT24++](https://arxiv.org/abs/2502.12404)
- WMT25 ran English→Maasai reference-free (references not available in time); low-resource error spans are
  "frequently" the whole segment (hallucination), and auto-raters "are unable to detect the catastrophic
  translations" that output the wrong language or script — [WMT25 findings](https://aclanthology.org/2025.wmt-1.24/)
- Negation as a proxy: chrF detects a negation flip 98.7% of the time vs COMET-QE 85.4% (DEMETR);
  the 2020 negation study found automatic metrics "bad estimators" when negation is present, with chrF++
  and METEOR better than BLEU but no winner across directions — [DEMETR](https://arxiv.org/abs/2210.13746);
  [It's not a Non-Issue](https://aclanthology.org/2020.findings-emnlp.345/); COMET's explanations "struggle to
  identify localized errors (negation errors, named entity errors and discrepancies in numbers)" —
  [The Inside Story](https://arxiv.org/abs/2305.11806)
- Round-trip consistency: system-level RTT-vs-forward Pearson 0.94-0.96 across 33 FLORES languages; adding
  RTT features to COMET-QE-DA improved segment-level DA prediction only slightly (en-de Kendall 42.7 → 44.2);
  fails under source-word copying — [Rethinking Round-Trip Translation](https://aclanthology.org/2023.findings-acl.22/)
- Sources of nondeterminism and "fluent but unrelated" output are exactly the synthetic categories MetricX-24
  had to add, and WMT25's challenge sets still show "susceptibility to fluent but semantically irrelevant
  content" — [MetricX-24](https://arxiv.org/abs/2410.03983); [WMT25 findings](https://aclanthology.org/2025.wmt-1.24/)

### Inferences
- For Kuni and Zinza, CometKiwi/xCOMET/MetricX scores would be noise with a language-specific offset
  (the IndicQE "displaced means" effect), so they cannot rank drafts within a language and must not be used to
  compare across the two languages. The AfriMTE route (AfriCOMET) needed hundreds of human-rated segments per
  language and a regional encoder; not available for Papuan languages.
- The proxies that survive scrutiny are the ones our loop already has or can add cheaply: (1) negation and
  number checks against the source (chrF-class detection, which COMET-QE lacks); (2) round-trip into English,
  used only to rank systems over a whole book and only with a check that no source words were copied;
  (3) language/script identity and untranslated-word detection, which WMT25 shows even strong auto-raters
  skip; (4) the affix-slot checker of section 1 as the grammar proxy.
- Alignment-based coverage (share of source lemmas with a linked target word, from our Hebrew/Greek
  alignments) is the natural undertranslation detector, which is what MetricX-24 had to synthesise training
  data for; it has no published validation and would need a DEMETR-style perturbation test locally.

### Gaps
- No paper measures CometKiwi-XL/XXL or xCOMET on a language absent from XLM-R; the measured collapses
  (Twi, Luo, Xhosa) are for languages XLM-R saw little of, so our case is at least as bad but unquantified.
- No published validation of alignment-coverage or lexicon-coverage proxies as QE for an unseen language.
- No SIL/ETEN evaluation of LLM drafts against human-rated quality was found; the ETEN "Evaluating Bible
  Translation" article could not be retrieved (404), and SIL guidance only lists expected error types (names,
  numbers, kinship terms, participant roles, pronouns) — [ETEN digest](https://etenlab.substack.com/p/bible-translation-innovation-digest)
