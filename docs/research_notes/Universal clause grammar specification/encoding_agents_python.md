# Encoding grammatical and interlinear information for LLM agents and Python scripts

Research notes, 2026-10-22. Scope: how a per-clause grammar specification (source clause frame, target
profile, realization rules with counts/provenance, difference log) and interlinear material should be encoded so
that it is cheap in tokens and understood by Claude-class agents, easy for Python to read/write/learn from, and
compatible with linguistic data standards. Facts older than 2025 are dated. "Measured here" means a local
tiktoken run on 2026-10-22; the script is `encoding_token_measure.py` beside this file.

## KQ1. What do MTOB / LingoLLM / Aycock (and 2024–2026 follow-ups) say about grammar prose vs examples vs glosses, about context length, and about agentic settings?

### Takeaway
Across every controlled study found, parallel examples (retrieved, relevant ones) carry nearly all of the
translation gain; grammar prose adds little or nothing for translation but does help linguistic sub-tasks
(glossing, grammaticality); glosses help translation when they are accurate and lose when they are noisy;
dictionaries alone are weak and in two 2026 RAG studies actively hurt glossing. Prompt length does not predict
quality (test-type coverage does), and retrieved/focused context beats whole-book context at a fraction of the
tokens, which is the case for an agent that searches rather than reads everything.

### Cited Findings

**MTOB (Tanzer et al., ICLR 2024; first arXiv Sept 2023)**
- Benchmark: Kalamang (<200 speakers), 573-page grammar ≈ 217,388 tokens as plaintext (GPT-3 tokenizer), 2,531-entry
  word list, 500 parallel sentences (400 train / 100 test); best baseline Claude 2 with wordlist + sentences + 100K-token
  grammar excerpt reached 44.7 chrF kgv→eng and 45.8 eng→kgv vs human 51.6 / 57.0 — [MTOB (ar5iv)](https://ar5iv.labs.arxiv.org/html/2309.16575); [arXiv abs](https://arxiv.org/abs/2309.16575)
- Retrieval design: 2 closest wordlist entries per input word (k_w=2), 2 matching sentences per input word (k_s=2);
  grammar passages as 512-token chunks with 256-token stride, retrieved by longest-common-substring (LCS), which
  "consistently beat" embedding retrieval; parallel sentences were "the most beneficial single context type" — [MTOB (ar5iv)](https://ar5iv.labs.arxiv.org/html/2309.16575)
- Retrieved short grammar excerpts "did not help much", attributed by the authors to retrieval failure rather than
  LLM inability; the ~50K ("Gm") and ~100K ("Gl") unconditional grammar dumps helped only in the long-context setting
  (Claude 2 only) — [MTOB (ar5iv)](https://ar5iv.labs.arxiv.org/html/2309.16575)
- Fine-tuning Llama 2 7B/13B on the grammar text (LoRA, 4 epochs) harmed results — [MTOB (ar5iv)](https://ar5iv.labs.arxiv.org/html/2309.16575)
- Gemini 1.5 Pro (Feb 2024) was reported at 58.3 chrF eng→kgv with the whole book + dictionary + ~400 sentences in
  context, above the 57.0 human baseline; this figure comes from secondary write-ups of the Gemini 1.5 report, not
  verified here in the report itself — [Zvi summary](https://thezvi.substack.com/p/the-one-and-a-half-gemini); [Gemini 1.5 report, arXiv 2403.05530](https://arxiv.org/html/2403.05530v2)

**Aycock, Stap, Wu, Monz, Sima'an, "Can LLMs Really Learn to Translate a Low-Resource Language from One Grammar Book?" (ICLR 2025; arXiv v2 April 2025)**
- Method: the Kalamang book was split by formatting into parallel lines (4,489 lines, 17,858 tokens, <20% of the
  book) and non-parallel explanatory text (2,282 lines, 81,268 tokens) — [arXiv 2409.19151v2](https://arxiv.org/html/2409.19151v2)
- Gemini 1.5 Pro ChrF++ (eng→kgv / kgv→eng, prompt tokens in brackets): 0-shot 11.0/12.7; wordlist 29.1/27.9 (9.0k);
  **5-shot retrieved parallel 38.9/33.4 (0.8k)**; book parallel only 26.6/33.1 (15.6k); parallel + wordlist 34.7/34.7
  (24.6k); parallel with glosses (IGT) 33.7/32.8 (22.7k); **full book 34.4/34.4 (99.6k)**; full book + wordlist
  38.3/39.6 (108.6k); **explanations only 22.6/27.5 (81.3k)**; typology (WALS-style) prompt alone 10.8/13.9 (68.4k);
  parallel + wordlist + 400 training sentences 40.7/46.6 (29.4k) vs full book + training 43.7/46.1 (113.4k) — [arXiv 2409.19151v2](https://arxiv.org/html/2409.19151v2)
- "Test-set type coverage" explains ChrF++ (R² = 0.84 eng→kgv, 0.87 kgv→eng); prompt length does not (p = 0.997 and
  0.78) — [arXiv 2409.19151v2](https://arxiv.org/html/2409.19151v2)
- Fine-tuned NLLB-1.3B on the book's parallel data: 34.2/28.6 vs in-context Gemini 26.6/33.1; with the training set
  38.7/36.9 vs 33.4/38.5; Gemini fine-tuning underperformed both by 6–12 ChrF++ — [arXiv 2409.19151v2](https://arxiv.org/html/2409.19151v2)
- Nepali and Guarani (seen languages): the full book or explanations never beat 0-shot (e.g., Guarani eng→gug
  26.6 0-shot vs 19.3 explanations only) — [arXiv 2409.19151v2](https://arxiv.org/html/2409.19151v2)
- Linguistic tasks are different: gloss prediction (morpheme accuracy) typology + parallel subset 46.1, parallel
  45.4, full book 40.1, explanations 21.0, vs supervised GlossLM-FT 43.8 / SMP-Base 45.2; grammaticality judgement:
  parallel subset beats explanation-only by up to 18%, typology prompt adds up to 3% — [arXiv 2409.19151v2](https://arxiv.org/html/2409.19151v2)
- Conclusion quoted on the abstract page: "almost all improvements stem from the book's parallel examples rather than
  its grammatical explanations"; no evidence long-context LLMs use grammatical explanations effectively for XLR
  translation — [arXiv abs](https://arxiv.org/abs/2409.19151)

**"Back to School: Translation Using Grammar Books" (Reid et al., EMNLP 2024)**
- GPT-4-turbo (128K), 16 languages, books 40K–120K tokens, MTOB-style prompt (2 LCS dictionary entries and 2
  sentences per source word, whole book appended). System averages (chrF++): eng→X baseline 19.2, W 22.7, **W+S 30.3,
  W+S+G 26.7**, NLLB 38.0; X→eng 34.1, 35.9, 35.7, 37.5, NLLB 47.7. W+S won 12/16 eng→X; adding G won 3/16 eng→X and
  6/16 X→eng. Kalamang: eng→kgv W+S 41.9* vs W+S+G 37.3; kgv→eng 27.6 vs 34.8* — [ACL Anthology PDF](https://aclanthology.org/2024.emnlp-main.1127.pdf)
- Regression: dictionary size and grammar length correlate positively with score; number of available sentences
  negatively (the authors suspect pre-training exposure for the seen languages) — [ACL Anthology PDF](https://aclanthology.org/2024.emnlp-main.1127.pdf)

**LingoLLM (Zhang et al., Findings of ACL 2024)**
- Prompt = dictionary entries + grammar book (or a GPT-4 summary if it does not fit) + morphologically analysed,
  word-by-word glossed input + instructions to annotate noun number/case, verb tense/voice/form, subject/object before
  translating. GPT-4 average spBLEU over 10 directions: zero-shot 0.5, few-shot 3.2, **dictionary only 8.2, full
  (with grammar) 10.5**; Mixtral 4.7 → 5.9; Gitksan BLEURT 0.4573 (dict only) → 0.5448 with morphological analysis;
  grammar books "can exceed 50,000 tokens" — [arXiv 2402.18025v2](https://arxiv.org/html/2402.18025v2)

**GrammaMT (Ramos et al., arXiv 2410.18702, Oct 2024)**
- Three strategies: gloss-shot (examples with gloss), chain-gloss (model glosses then translates), model-gloss
  (external GlossLM gloss). N = 21 examples was the ablation optimum. Llama-3-70B on four SIGMORPHON-2023 languages:
  few-shot avg BLEU 3.94; gloss-shot −0.53; chain-gloss +0.31; **model-gloss +12.03**; GPT-4o 4.88 → 18.69 with
  model-gloss; gold glosses +17.46 BLEU over few-shot — [arXiv 2410.18702v2](https://arxiv.org/html/2410.18702v2)
- Removing grammatical labels from glosses lowers performance (gains are not just from English lemmata); on
  Portuguese/Russian a parallel dictionary prompt scored 35.80/22.09 vs gloss-shot 44.37/23.99; weak glosses can hurt — [arXiv 2410.18702v2](https://arxiv.org/html/2410.18702v2)
- Gloss format used in the prompt: `Source: (yeye) alimwona (yeye).` / `Gloss: 3SG -PST –see-FV 3SG` /
  `Translation: "S/he saw him/her."` — [arXiv 2410.18702v2](https://arxiv.org/html/2410.18702v2)

**In-context glossing (Ginn, Hulden, Palmer, Findings of EMNLP 2024)**
- Prompt: system role "expert documentary linguist", `Transcription:` / `Translation:` in, `Glosses:` out; Leipzig
  conventions; translation line later omitted because the model copied words from it; retrieval by chrF was "usually
  the most effective", all targeted strategies beat random; accuracy ≈ logarithmic in the number of shots (R² 0.93–0.998),
  still rising at 100 shots for most languages; Gemini beat the supervised SOTA on Gitksan by 6.5 points but SOTA
  (Girrbach 2023) wins elsewhere — [arXiv 2406.18895v3](https://arxiv.org/html/2406.18895v3)
- A gloss-label list without explanations gave "negligible accuracy changes" but increased adherence to the label
  set; it cost "several hundred tokens per prompt" and was dropped — [arXiv 2406.18895v3](https://arxiv.org/html/2406.18895v3)

**Word-by-word retrieval prompting (Elsner & Liu, SIGMORPHON 2025, arXiv 2502.09778)**
- Per word: up to 3 exact-match sentences, 3 approximate matches (shared ≥4-char substring), reverse-lookup examples,
  the word's most common training gloss and its gloss distribution; GPT-4o returns 3 ranked glosses in JSON. Word-level
  accuracy (baseline / winner / this): git 16.93 / 21.09 / 25.52; lez 49.66 / 78.78 / 76.19; ntu 42.01 / 81.04 / 73.33;
  nyb 5.96 / 85.34 / 78.52; ddo 73.41 / 80.96 / 75.28; usp 57.26 / 73.39 / 65.32. Retrieval + LLM beats retrieval alone
  everywhere; LLM-written syncretism instructions raised Tsez 75.28 → 75.86 (converb confusions −11%) but did not
  help Lezgi; whole study ≈ $300 — [arXiv 2502.09778v1](https://arxiv.org/html/2502.09778v1)

**2026 RAG glossing studies**
- Mapudungun (Almendra et al., AmericasNLP 2026), Gemini 2.5 Pro + RAG; accuracy on text / morphological / tagging
  tiers: baseline 98.26 / 78.62 / 41.08; **corpus 98.96 / 74.92 / 56.41***; grammar 96.18 / 76.88 / 39.46;
  **dictionary 90.62* / 70.95* / 34.91***; all 98.26 / 80.60 / 55.69*; a 589-meaning-unit annotated corpus was
  enough; "dictionary integration causes a significant drop" — [ACL Anthology 2026.americasnlp-6.6](https://aclanthology.org/2026.americasnlp-6.6/)
- Jungar Tuvan (Field Matters 2026, arXiv 2603.00923): BiLSTM-CRF 0.474 → hybrid with LLM post-correction and
  TF-IDF-retrieved examples 0.698 (deepseek-v3.2-exp, n=15); a plain-text `key:value` morpheme dictionary lowered
  accuracy for 3 of 4 LLMs (−0.014 to −0.051 full; −0.041 to −0.104 top-100), gemma-3-27b gained (+0.130); glosses
  formatted as `word1-MORPH1 word2-MORPH2` inside `###` delimiters — [arXiv 2603.00923v1](https://arxiv.org/html/2603.00923v1); [ACL Anthology](https://aclanthology.org/2026.fieldmatters-1.3/)
- Turkish gloss pivot (SIGUL 2026): "Pivoting with glosses remains a better approach than a direct translation for
  languages with limited parallel data"; quality depends on gloss quality, "particularly lexical information" — [ACL Anthology 2026.sigul-1.19](https://aclanthology.org/2026.sigul-1.19/)
- PolyGloss (ACL 2026): GlossLM corpus extended to ~340k examples / 2,077 languages; ByT5 seq2seq models that beat
  open-source LLMs on segmentation, glossing and alignment — [arXiv 2601.10925](https://arxiv.org/abs/2601.10925); corpus figure from [search summary](https://en.papernotes.org/ACL2026/multilingual_mt/massively_multilingual_joint_segmentation_and_glossing/)

**Context length and position (general LLM evidence)**
- Lost in the Middle (Liu et al., 2023): on 20-document QA, performance is highest at the start or end of the
  context and "can degrade by more than 20%" when the answer is in the middle, in the worst case below the closed-book
  setting (GPT-3.5-Turbo closed-book 56.1%, oracle 88.3%) — [arXiv 2307.03172](https://arxiv.org/abs/2307.03172)
- Chroma "Context Rot" (14 July 2025), 18 models incl. GPT-4.1, Claude 4, Gemini 2.5, Qwen3: performance "grows
  increasingly unreliable as input length grows" even on simple tasks; on LongMemEval, focused prompts (~300 tokens)
  beat full prompts (~113k tokens) across all model families, Claude models with the largest gap (abstentions);
  shuffled haystacks beat logically ordered ones across all 18 models — [Chroma report](https://www.trychroma.com/research/context-rot)
- Anthropic engineering (29 Sept 2025): context "must be treated as a finite resource with diminishing marginal
  returns" ("context rot", an "attention budget"); recommends "just in time" context via lightweight identifiers
  (file paths, stored queries) loaded by tools, progressive disclosure, and a hybrid (some data up front, the rest
  on demand, as Claude Code does with CLAUDE.md + grep/glob); "do the simplest thing that works" — [Anthropic: Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- Anthropic prompting docs (current): for 20k+-token inputs put long data at the top, above the query; wrap each
  document in `<document>` with `<document_content>` and `<source>`; ask Claude to quote relevant parts first; wrap
  examples in `<example>` tags; "use structured formats for state data" (e.g., JSON) and unstructured text for
  progress notes — [Claude prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)

### Inferences
- For this toolkit the ordering of value per token is: retrieved parallel examples (verses in parts) ≫ accurate
  glosses on those examples > a compact typological/feature profile ≈ 0 > grammar prose. Aycock's 5-shot retrieved
  parallel condition (0.8k tokens, 38.9 ChrF++) beating the whole 99.6k-token book (34.4) is the single most relevant
  number: the per-clause spec should be a retrieval key into examples, not a replacement for them.
- Glosses are worth their tokens only when accurate (GrammaMT: gold +17 BLEU, model gloss +12, LLM self-gloss ≈ 0).
  The source side here (Hebrew/Greek with MACULA/BHSA morphology) is gold-quality, so source-side glosses in the
  clause frame are the cheap, high-value part; target-side "parts" are the uncertain part and should carry counts.
- Two independent 2026 studies found dictionaries (long key:value lists) hurt LLM glossing; this matches the
  project's own Ruth-3 experience that lexicon noise in packs did not cut work. Lists of candidate forms should be
  short, ranked and filtered by the clause's features, not exhaustive.
- Grammar explanations do help the model gloss and judge grammaticality (Aycock), i.e. the "check" and "why"
  steps, so prose rules belong in the checker/loop prompt and the wiki, not in the drafting pack.
- The agentic answer: all the measured gains come from targeted retrieval (LCS/chrF similarity per word or
  verse), and Anthropic's own guidance is to pre-load a small stable core and fetch the rest on demand; a chapter pack
  should shrink to a per-clause frame + top-k examples, with `concord.py`-style search for the remainder.

### Gaps
- No study found that tests an agent with search tools against a static pack on the same language; the agentic
  evidence is indirect (retrieval ablations + Anthropic/Chroma context findings).
- No SIL / Partnership for Applied Biblical NLP publication on LLM drafting with grammar or IGT was found (only the
  eBible corpus paper, 2023, and the Scripture Forge/silnlp in-context path already in the project's SIL study).
- The Gemini 1.5 Kalamang figure (58.3) was seen only in secondary sources.
- No 2025–26 paper re-running MTOB with newer models or with agentic retrieval was found.

## KQ2. Which notation gives the fewest tokens for a clause frame (~8 slots) and for an interlinear line? Figures and tokenizer caveats.

### Takeaway
Measured here with tiktoken (o200k_base = GPT-4o/GPT-5 family; cl100k_base = GPT-4): a positional one-line frame
costs 18 tokens, TSV 21, CSV 23, a TOON row 24, a Markdown-table row 27, `key=val` 34, Penn brackets 33, YAML 44,
compact JSON 45, TOML 57, pretty JSON 73; over ten clauses the positional line is 19 tokens/clause vs 75 for pretty
JSON. Compact feature codes (`1SG.PST`, `NEG.SBJV`) cost 4 tokens each, exactly the same as the spelled-out phrase, so
abbreviation saves characters, not tokens. Pointed Hebrew is the dominant cost (10.8 tokens/word on o200k, 15.9 on
cl100k) — stripping accents alone cuts it to 3.2. Claude's current tokenizer was not measured; Anthropic states it
yields ~30% more tokens than pre-4.7 models.

### Cited Findings

**Published format comparisons**
- TOON official benchmark (o200k_base tokenizer, gpt-tokenizer): mixed-structure track total TOON 227,830 vs JSON
  formatted 291,711 (−21.9%), JSON compact 198,546 (**TOON +14.7%**), YAML 241,474 (−5.7%), XML 330,206; flat-only
  track CSV 63,997, TOON 67,778 (+5.9% vs CSV), JSON formatted 164,452, JSON compact 104,724, YAML 130,997; retrieval
  accuracy over 209 questions × 4 models: TOON 76.4% (2,759 tokens), JSON compact 73.7% (3,104), YAML 74.5% (3,749),
  JSON 75.0% (4,587), XML 72.1% (5,221); per model claude-haiku-4-5: TOON 59.8%, JSON 57.4%, CSV 50.5% (on 109 q);
  gemini-3-flash: XML 98.1% best; caveats: deeply nested data JSON compact wins (+11% for TOON), CSV 5–10% more
  compact for pure tables — [TOON benchmarks](https://mintlify.wiki/toon-format/toon/advanced/benchmarks)
- Independent re-tests (improvingagents.com, summarised): GPT-4.1-nano on tabular data: TOON 47.5% (9th of 12
  formats), JSON 52.3%, Markdown key-value 60.7% best, tokens TOON 21,518 vs JSON 66,396; GPT-5-nano nested: TOON
  43.1% (last), JSON 50.3%, Markdown 54.3%, YAML 62.1%; the write-up's own numbers are internally inconsistent and
  the tokenizer unnamed; recommendation "let your own results guide you" — [dev.to analysis](https://dev.to/ikaganacar/toon-benchmarks-a-critical-analysis-of-different-results-5h66)
- He et al. 2024, "Does Prompt Formatting Have Any Impact on LLM Performance?" (plain text / Markdown / YAML / JSON,
  GPT-3.5 and GPT-4 checkpoints, Nov 2024): GPT-3.5-turbo-0613 HumanEval plain 40.24, Markdown 54.27, YAML 42.68,
  JSON 59.76; GPT-4-1106 MMLU plain 81.01, Markdown 81.25, YAML 80.76, JSON 73.92; GPT-4-32k HumanEval JSON 21.95 vs
  plain 76.22 (the model reasoned instead of coding); no format is universally best, JSON favoured by GPT-3.5,
  Markdown by GPT-4; transfer of best format across model series IoU often < 0.2 — [arXiv 2411.10541v1](https://arxiv.org/html/2411.10541v1)
- Tam et al. 2024, "Let Me Speak Freely?" (EMNLP Industry 2024): strict format constraints (JSON mode) lower reasoning
  performance, stricter = larger drop; looser instructions or a free-text-then-convert step recover it; classification
  is unaffected or helped — [arXiv 2408.02442](https://arxiv.org/pdf/2408.02442)
- Anthropic: prefills for forcing JSON/YAML are superseded by structured outputs; "Try asking the model to conform to
  your output structure first, as newer models can reliably match complex schemas when told to" — [Claude prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)

**Measured here (tiktoken, 2026-10-22; frame = `id,type,rel,act,pol,tam,subj,obj,disc` with values `GEN24:8b cond prot cmd NEG FUT 2s 3p then`)** — tool: [openai/tiktoken](https://github.com/openai/tiktoken); script `encoding_token_measure.py`
- One frame, tokens o200k / cl100k: JSON pretty 73/72; JSON compact 45/44; YAML 44/44; TOML 57/55; TSV row 21/21;
  CSV row 23/23; Markdown row 27/28 (header + separator 38 once); `key=val` line 34/33; **positional line
  `GEN24:8b cond/prot cmd NEG FUT 2s>3p then` 18/19**; Penn-style brackets 33/35; TOON header 22 + row 24.
- Ten frames: JSON pretty 752; JSON compact 443; YAML list 529; Markdown table 308; `key=val` lines 349; TSV with
  header 234 (14 for the header, 22/row); CSV 256; positional lines 189 (**18.9/clause**). Bytes per token: CSV 1.8,
  TSV 2.0, YAML 2.0, JSON compact 2.7 (its tokens are fatter but there are more of them).
- Interlinear, one 5-word Hebrew clause: Hebrew line 39 (o200k) / 61 (cl100k); Leipzig gloss line 25/26; target
  parts line `ka wele ka+ dza +ne nqo+ ta +q` 15/16; stacked three lines 81/105; inline `word/gloss` pairs 67/90 (the
  saving is only the Hebrew-line overhead; the Hebrew itself dominates); transliteration 38/46 (no cheaper than
  pointed Hebrew on o200k).
- Script cost on real chapters: Genesis 1 pointed + accented Hebrew 369 words = 3,994 tokens o200k (**10.8
  tokens/word**), 5,853 cl100k (15.9/word); consonantal (marks stripped) 1,169 (3.2/word) / 2,343 (6.4/word); John 1
  accented Greek 827 words = 3,467 (4.2/word) / 5,768 (7.0/word); unaccented 2,170 (2.6/word) / 4,198; English BSB
  1.13 tokens/word.
- Code pieces (o200k; cl100k identical unless noted): `ku+` 2 [`ku`,`+`]; `+a` 1; `ku+ lam +a` 5; `~PROH` 3
  [`~`,`PRO`,`H`]; `~H1` 3; **`1SG.PST` 4 [`1`,`SG`,`.P`,`ST`] = `first person singular past` 4**; **`NEG.SBJV` 4 =
  `negative subjunctive` 4**; `3FS` 2; `IPFV` 2 (cl100k 3); `FUT.2s.cond.neg` 8 (dots and case changes each cost a
  token); `V.NEG` 3; `SC3s` 3; `pred=ti-` 4; `src=agent:r2` 5; reference `GEN24:8b` 5, `GEN 24:8b` 6.
- Difference-log line as given (`GEN24:8b V.NEG pred=ti- got=ta- why=SC3s src=agent:r2 feat=FUT.2s.cond.neg`) 36
  tokens; same as TSV 29; as compact JSON 48.
- A real Kuni pack: `_learn/packs/gen001.md` 254 KB = 93,345 tokens o200k / 101,232 cl100k (2.7 bytes/token);
  `gen046.pkg.md` 48 KB = 22,663 / 24,988 (2.1 bytes/token). (The project's "40–150 KB" packs are therefore roughly
  15k–55k tokens on o200k; more on Claude.)
- Tokenizer disparity literature: tiktoken over 200+ languages, non-Latin and morphologically complex languages show
  "often 3-5 times higher" relative tokenization cost than English — [arXiv 2510.12389](https://arxiv.org/abs/2510.12389)

**Claude-specific tokenizer facts**
- Anthropic: "Claude 4.7 and later models and Claude Mythos Preview use a newer tokenizer. The same input text produces
  approximately 30 percent more tokens than on earlier models"; Fable 5.1 / Mythos 5.1 / Fable 5 / Mythos 5 share it;
  the `count_tokens` endpoint is free (5,000–20,000 RPM by tier) and counts under the tokenizer of the `model`
  passed; counts are estimates — [Claude token counting](https://platform.claude.com/docs/en/build-with-claude/token-counting)

### Inferences
- For the agent view, a positional or TSV line per clause with a one-time legend is the cheapest readable form
  (≈18–22 tokens per 8-slot clause); JSON/YAML cost 2.3–4× for the same content and only pay off when the structure is
  irregular. TOON brings nothing over TSV here (same tabular case where CSV already wins) and its accuracy claims are
  contested.
- Do not shorten feature labels below word level expecting token savings: `1SG.PST` and "first person singular
  past" both cost 4 tokens. The right unit is one well-known token per feature (`NEG`, `FUT`, `3FS`, `IPFV`) joined by a
  separator the tokenizer treats as cheap; dots inside codes cost a token each (`FUT.2s.cond.neg` = 8), so a
  space-separated or fixed-column bundle (`FUT 2s cond neg`) is cheaper and no less clear.
- The pack's token budget is dominated by Hebrew script if quoted pointed: 10.8 tokens/word vs 1.1 for English.
  Show the Hebrew once (consonantal or unpointed where the licence/WLC rule allows, else only the lemma/gloss line), and
  refer to words by position ids thereafter; a glossed Leipzig line is 25 tokens for the same clause.
- Measure the final layouts with `count_tokens` against the exact Claude model before fixing a budget; the relative
  ordering between formats should hold, the absolute numbers will be ~30% higher than o200k.

### Gaps
- No Claude-tokenizer measurements (no API key in this environment); the 30% figure is Anthropic's aggregate.
- No published study measures gloss/feature notations specifically; the per-code figures above are local.
- Format-accuracy studies (He et al., TOON) are on GPT/Gemini/Haiku and on retrieval/code tasks, not on
  linguistic frames; whether Claude reads TSV frames as accurately as JSON frames is untested.

## KQ3. Which single-source format (CLDF, CoNLL-U Plus, JSONL…) and which agent rendering?

### Takeaway
The accepted standards split cleanly: CLDF ExampleTable (CSV + JSON metadata, tab-separated word/gloss lists,
pycldf/pyigt) is the interchange standard for IGT examples; CoNLL-U Plus (TSV, `# global.columns`, namespaced
extra columns like `PARSEME:MWE`, `_`/`*` for unknown/empty, `conllu` library with `fields=`) is the token-level
standard that already tolerates project columns; Xigt (XML, 34 stars, 26 open issues, no visible release) and
FLExText (XML, FlexInterlinear.xsd) are import/export targets rather than working formats. One tabular source of
truth (TSV/CSV rows keyed by clause and slot, validated through CoNLL-U-Plus-style column declarations or CLDF
metadata) renders to both pandas/sqlite and a one-line-per-clause agent view with a legend.

### Cited Findings
- CLDF ExampleTable columns (`dc:conformsTo` `…terms.rdf#ExampleTable`): `ID` (required, `[a-zA-Z0-9_\-]+`),
  `Language_ID` (required), `Primary_Text` (required), `Analyzed_Word` (list, **separator `"\t"`**), `Gloss` (list,
  separator `"\t"`), `Translated_Text`, `Meta_Language_ID`, `LGR_Conformance` (`WORD_ALIGNED|MORPHEME_ALIGNED`),
  `Comment` — [ExampleTable-metadata.json](https://raw.githubusercontent.com/cldf/cldf/master/components/examples/ExampleTable-metadata.json)
- Morphemes/clitics inside a word follow the Leipzig Glossing Rules with `-` and `=`, which "must not be used for the
  separator property"; incomplete glossing uses `…` (U+2026); other tables link to examples via `exampleReference` — [CLDF examples README](https://github.com/cldf/cldf/blob/master/components/examples/README.md)
- pyigt: "easy access to Interlinear Glossed Text (IGT) according to the Leipzig Glossing Rules, stored as CLDF
  examples"; an IGT is a list of aligned words, each a list of aligned morphemes; extra ExampleTable columns are kept
  as properties; CLI `igt ls` prints the four-line layout — [pyigt docs](https://pyigt.readthedocs.io/en/stable/igt.html)
- A Bern group used CLDF files to hold a FLEx-exported lexicon and interlinear examples — [Using CLDF and CLLD for language documentation](https://boris.unibe.ch/140429); a 2018 LINGTYP thread discussed Xigt vs CLDF for IGT export — [LINGTYP list](https://listserv.linguistlist.org/pipermail/lingtyp/2018-April/006213.html)
- CoNLL-U Plus: first line `# global.columns = ID FORM LEMMA UPOS XPOS FEATS HEAD DEPREL DEPS MISC`; any non-zero
  number of columns; project columns are uppercase with a colon namespace (`PARSEME:MWE`); `_` = underspecified /
  unknown, `*` recommended for "known but empty"; fields may not contain TAB/CR/LF; `sent_id` required and unique;
  `source_sent_id` for stand-off references; FEATS shown as `Case=Nom|Gender=Fem|Number=Sing`; planned extensions
  include Unimorph-style morphology — [UD CoNLL-U Plus](https://universaldependencies.org/ext-format.html); Grew supports the column declaration but not cross-references — [grew.fr](https://grew.fr/doc/conllup)
- `conllu` 6.0.0 (Oct 2024, no dependencies, Python ≥3.8): `parse(data, fields=[...])` for custom columns,
  `field_parsers` to split `|`-separated values into lists, `metadata_parsers` for comments, `filter(feats__Degree="Pos")`,
  `serialize()` round trip; `parse_incr` for large files — [PyPI conllu](https://pypi.org/project/conllu/)
- Xigt: data model of IGT → tiers → items with `alignment` / `segmentation` / `content` reference attributes and
  alignment expressions such as `a1[1:3]+a2[1:2+0:1]`; XML example splitting "cocinas" into `cocin` + `as` aligned to
  `cook`, `2`, `SG`, `PRS`, `IND`; pip-installable, developed under AGGREGATION, optional Toolbox/ODIN importers; repo
  shows 34 stars, 26 open issues, 1 PR, no visible release in the captured page — [xigt/xigt](https://github.com/xigt/xigt); [PyPI](https://pypi.org/project/xigt/)
- FLExText: PRONOM fmt/1799 points to `FlexInterlinear.xsd` in the FieldWorks repo; root `document` →
  `interlinear-text` → `paragraphs`; the EMELD-derived item types read by interlineaR are `txt`, `cf` (vernacular) and
  `gls`, `msa`, `hn` (analysis) at morpheme level — [PRONOM fmt/1799](https://pronom.nationalarchives.gov.uk/fmt/1799); [interlineaR manual](https://cloud.r-project.org/web/packages/interlineaR/refman/interlineaR.html); EMELD model from Hughes, Bird & Bow 2003 — [ACL U03-1008](https://preview.aclanthology.org/moar-dois/U03-1008.pdf)
- SIGMORPHON 2023 glossing shared-task file format (Toolbox-like): `\t` orthographic line, `\m` morphological
  segmentation (open track only), `\g` gloss line, `\l` translation, e.g. `\m heet-ne 'ii'-P woo-wooyoo …` /
  `\g FUT-that 's.when-pause REDUP-new-SUBJ …`; metrics word-level and morpheme-level glossing accuracy; training
  sizes from ~140k tokens (Arapaho) to 261 tokens (Gitksan); winner Tü-CL +23.99 points (closed) / +17.42 (open) over a
  RoBERTa baseline — [Findings PDF](https://aclanthology.org/2023.sigmorphon-1.20.pdf); data at [github.com/sigmorphon/2023glossingST](https://github.com/sigmorphon/2023glossingST)
- GlossLM (EMNLP 2024): >450k IGT examples, 1.8k languages, labels normalised to a shared set; ByT5-based;
  largest advantage on unsegmented text and small corpora — [arXiv 2403.06399](https://arxiv.org/abs/2403.06399v3); [ACL Anthology](https://aclanthology.org/2024.emnlp-main.683)
- Anthropic recommends JSON "or other structured formats" for state data so that "schema requirements" are explicit,
  and plain text for notes — [Claude prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)

### Inferences
- Single source of truth: keep the clause specification as tabular rows (TSV/CSV per chapter, or one SQLite
  table in `orig/*.sqlite` style), with (a) a CoNLL-U-Plus-style column declaration on line 1 and namespaced project
  columns (`BCV:ROLE`, `BCV:TAM`, `BCV:SPEECH`), `_` for unknown and `*` for "known empty"; (b) CLDF JSON metadata
  describing the same columns, so `pycldf` can validate and the examples can be exported as an ExampleTable
  (`Analyzed_Word`/`Gloss` tab-separated) for reuse by bcv-commons. The two standards are column-compatible; CLDF adds
  the typed metadata, CoNLL-U Plus adds the token/dependency conventions.
- The agent view is a rendering, never edited by hand: one line per clause = `<ref> <frame positional slots>` plus
  a glossed source line and the realised target in parts, preceded by a 20–40-line legend of slot order and codes
  (Ginn 2024 found a label list adds adherence at negligible accuracy cost; keep it short since it costs tokens each
  chapter). Example lines rendered from the same rows are what the research says actually helps.
- JSONL is the right wire format for the append-only difference log (one record per event, trivially appended
  and read by pandas/`json.loads`), while the learned rule table should be CSV/TSV again so it can be diffed in git and
  rendered to the agent as lines.
- Xigt and FLExText are worth an exporter (for linguists' tools and ELAN/FLEx), not a working format: their
  reference attributes and XML overhead are exactly what costs tokens and parsing effort.

### Gaps
- No evidence found of CoNLL-U Plus being used for IGT with gloss columns in practice (the UD page lists Unimorph
  morphology as a planned extension only).
- pycldf's handling of the tab separator in CSV cells was not verified by running it here.
- Xigt's last release date could not be read from the repository page (the badges are present, the release list
  is empty in the fetched text).

## KQ4. How should the difference log be shaped so counts-with-back-off learning and provenance weighting are simple in Python? What precedents exist for learned, transparent rule tables?

### Takeaway
The transparent precedents all reduce to counting events over feature bundles and then choosing the most specific
rule that is reliable: Yarowsky decision lists (sort by log-likelihood ratio, apply the first match, smooth zero
counts, interpolate specific vs general lists), AGGREGATION (count observed orders, map to the nearest canonical
value), and ruLearn (generate rules at several generalisation levels from bilingual phrases, keep the minimum set that
reproduces the data). A long-format event log (one row per clause × slot × observation with the full feature bundle
and a source column) supports all three with `pandas.groupby` over feature-prefix levels, and provenance becomes a
per-row weight.

### Cited Findings
- Yarowsky 1994 (ACL): decision lists computed from the log-likelihood ratio
  `log(Pr(class1|collocation)/Pr(class2|collocation))`; "Sorting by this value will list the strongest and most reliable
  evidence first"; classification uses "the highest line in the list that matches the given context"; zero counts
  are smoothed (e.g., a 2/0 raw ratio re-estimated on held-out data to ≈1.8/0.2); an optional interpolation step
  between global and specific lists, and pruning of redundant lower entries — [ACL P94-1013](https://aclanthology.org/P94-1013/) (PDF read locally)
- AGGREGATION / Bender, Goodman, Crowgey & Xia 2013: English translations are parsed, trees projected onto the
  source line with SBJ/OBJ tags, then "searched for any of ten patterns: SOV, SVO, OSV, OVS, VSO, VOS, SV, VS, OV, VO";
  Lewis & Xia 2008 obtained 99% word-order accuracy over 97 languages "provided the IGT collections had at least 40
  instances per language"; the authors note "testsuite bias" (IGT built to illustrate phenomena is not a natural
  distribution) — [ACL W13-2710](https://aclanthology.org/W13-2710/) (PDF read locally)
- Howell & Bender 2022 (NEJLT): each observed order of verb/subject/object "is counted to compute a three
  dimensional vector … compared to the vector representations for each canonical word order", positing the order with
  the shortest Euclidean distance; determiner order by counting determiners before vs after the noun; the Grammar
  Matrix choices file is the learning target (a "much simpler representation than the grammars derived from them");
  50 features with 136 possible values (e.g., word order 10, case system 9, sentential negation 41); 27 development +
  5 held-out languages; out-performs three baselines in coverage while limiting ambiguity — [NEJLT 2022](https://nejlt.ep.liu.se/article/view/4017); [ACL 2022.nejlt-1.3](https://preview.aclanthology.org/setup/2022.nejlt-1.3) (PDF read locally); Grammar Matrix choices-file framing from [Bender et al. 2014 case study](https://mirror.aclweb.org/acl2014/W14-22/pdf/W14-2206.pdf)
- ruLearn (Sánchez-Cartagena, Pérez-Ortiz, Sánchez-Martínez, PBML 106, 2016): "multiple rules with different
  generalisation levels are generated from bilingual phrases extracted from the parallel corpus and the minimum set of
  rules that correctly reproduces the bilingual phrases is selected. In this way, conflicts between rules are
  effectively solved at a global level"; "a few hundred parallel sentences proved to be sufficient"; rules "can be
  easily modified by human experts and can co-exist with hand-crafted rules"; quality "similar to that obtained by
  using hand-crafted rules" — [PBML PDF](https://www.dlsi.ua.es/~fsanchez/pub/pdf/sanchez-cartagena16b.pdf)
- Sánchez-Martínez & Forcada 2009 (JAIR): alignment templates extracted from sentence-aligned text, "extended with
  restrictions derived from the bilingual dictionary" that govern when they apply; three Apertium pairs; quality
  improved over word-for-word and came close to hand-coded rules — [JAIR 10599](https://jair.org/index.php/jair/article/view/10599)
- AGGREGATION's own working format was Xigt, developed for the project; IGT is enriched by projecting POS and
  dependencies from the English line — [xigt/xigt](https://github.com/xigt/xigt); [ACL W13-2710](https://aclanthology.org/W13-2710/)
- The project's existing conventions (for compatibility): CoNLL-U Plus `_` vs `*` distinction for unknown vs
  empty — [UD CoNLL-U Plus](https://universaldependencies.org/ext-format.html); CLDF `LGR_Conformance` levels for how
  far a gloss is aligned — [ExampleTable-metadata.json](https://raw.githubusercontent.com/cldf/cldf/master/components/examples/ExampleTable-metadata.json)

### Inferences
- Log shape (inference from the precedents, not a sourced recommendation): one JSONL/TSV record per observation
  with fixed atomic columns rather than a packed `feat=FUT.2s.cond.neg` string: `ref, clause_id, slot, pred, got,
  src_kind (agent|human|team|script), src_id, run, ts` plus one column per feature dimension in a fixed order
  (`tam, pers, num, pol, mood, clause_type, rel, speech`). Back-off is then `df.groupby(dims[:k])` for k = n…0, i.e.
  Yarowsky's specific-to-general ordering; a rule row is `(dims prefix, got, count, total, llr)` and the applied rule
  is the first matching row sorted by specificity then |llr|, with counts below a floor (Lewis & Xia's "≥40 instances"
  is the only published threshold found) falling back to the next level.
- Provenance weighting is a column, not a structure: `weight = {team-decision: ∞/binding, human corpus: 1.0,
  agent: w_a, script: w_s}`; weighted counts in groupby give ruLearn-style "human rules coexist with learned rules"
  without special cases, and the store's existing `method: team-decision` binding rule maps directly to it.
- Keep the packed one-line form (`GEN24:8b V.NEG pred=ti- got=ta- why=SC3s …`, 36 tokens) only as the agent-facing
  rendering of the same record; the agent writes it, a script parses it into the long table. The `why=` field should
  be a closed code list (store entry id or rule id) so it can be grouped.
- ruLearn's "minimum rule set that reproduces the data" is the model for publishing the learned table: emit the
  shortest set of (feature-prefix → realisation) rows that reproduces the log at ≥ a chosen precision, so the agent
  view stays short.

### Gaps
- No paper found that reports confidence/provenance fields for learned transfer or glossing rules beyond counts and
  log-likelihood ratios; the weighting scheme above is a design inference.
- Lewis & Xia 2008's 40-instance threshold is for word order; no published per-affix thresholds were found.

## KQ5. Is there evidence that compact codes (1SG.PST, NEG.SBJV) are understood by LLMs as well as spelled-out features?

### Takeaway
No study directly compares abbreviated vs spelled-out feature labels. Indirect evidence: LLMs produce and consume
Leipzig-style codes competently in-context (Ginn 2024; Elsner & Liu 2025; GrammaMT shows the grammatical labels
themselves carry the gain), a label list without explanations raised adherence but not accuracy, and GlossLM/PolyGloss
needed label normalisation because corpora use divergent codes. Tokenization makes the choice free in tokens, so the
decision should rest on consistency (one normalised code set, declared once) rather than on cost.

### Cited Findings
- GrammaMT: "removing them [grammatical labels] from glosses lowers performance, so gains are not just from English
  lemmata" — [arXiv 2410.18702v2](https://arxiv.org/html/2410.18702v2)
- Ginn et al. 2024: a gloss-label list without explanations gave "negligible accuracy changes" but "increased
  adherence to the label set"; abbreviation-vs-explained labels "were not tested" — [arXiv 2406.18895v3](https://arxiv.org/html/2406.18895v3)
- Elsner & Liu 2025 prompt GPT-4o with Leipzig function tags (e.g., `PFV.CVB`, `PST.UNW`) and report word-level
  accuracy well above the SIGMORPHON baseline (e.g., Natügu 42.01 → 73.33) with no separate analysis of the
  abbreviation convention — [arXiv 2502.09778v1](https://arxiv.org/html/2502.09778v1)
- Aycock et al.: Gemini 1.5 Pro predicts Leipzig glosses from in-context parallel examples at 45–46 morpheme
  accuracy, level with supervised systems (40.8–45.2) — [arXiv 2409.19151v2](https://arxiv.org/html/2409.19151v2)
- GlossLM normalised "much of" its 450k-example corpus "to a shared set of labels" because sources differ — [arXiv 2403.06399](https://arxiv.org/abs/2403.06399v3)
- The Leipzig Glossing Rules: category labels are "abbreviated grammatical category labels, printed in upper case
  letters" with a standard list that "authors often modify" — [Leipzig Glossing Rules (MPI EVA)](https://www.eva.mpg.de/lingua/resources/glossing-rules.php)
- Tokens, measured here: `1SG.PST` = 4 tokens = "first person singular past"; `NEG.SBJV` = 4 = "negative
  subjunctive"; `3FS` 2; `IPFV` 2 — [openai/tiktoken](https://github.com/openai/tiktoken) (local run, see KQ2)
- Jungar Tuvan 2026: LLM post-correction with `word-MORPH` glosses reached 0.698 token accuracy from a 0.474 neural
  baseline, with no explanation of the labels in the prompt — [arXiv 2603.00923v1](https://arxiv.org/html/2603.00923v1)

### Inferences
- Standard Leipzig codes are safe for Claude-class models when used consistently; project-specific codes
  (`SC3s`, `~PROH`, `~H1`) are the ones that need a legend, and the legend costs a few hundred tokens once per prompt
  (Ginn's figure). Spelled-out words buy nothing in tokens and cost width in tables, so keep codes but prefer
  single-token standard ones (`NEG`, `FUT`, `3FS`) over compound dotted bundles.
- The project should keep one normalised code inventory in the language store and render it, since the only
  measurable effect of a label list was adherence.

### Gaps
- Direct abbreviation-vs-spelled-out ablations do not exist in the literature found; this could be settled locally
  with a small `judge.py`-style A/B on a few chapters.
- No Claude-specific gloss-reading evaluation was found (the glossing studies use GPT-4o, Gemini, Llama, Cohere,
  DeepSeek, Qwen, Gemma).
