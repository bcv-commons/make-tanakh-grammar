# Rules-engine lab: run log
- 2026-10-26T06:06Z Day 1 (user away, "keep going"): E0 (alignment from the BSB tables; lexeme-aligner layer differs in 9.0%, note 12 sent by the user), E1, E1b, E2-E7, swap tests, linguist rounds r1 (140k tokens) and r2 (164k), rung 1b (Hebrew) adapter, one test evaluation (results/final_test.json). Report: REPORT-2026-10-26.md.
- 2026-10-26 (later) Detector calibration and agent-free rounds (auto/, auto/CALIBRATION.md); BSB NLLB instrument training (nllb/queue.sh, ~7 h per model).
- 2026-10-26 ~09:00 Round 3, agent-free (r3/): participant ids as fields (engine/parts.py from scripts/participants.py --mentions, all NT books, build/participants/);
  D3 with them (results/auto/v2p*.md); `gov` (governed by a preposition / in a noun phrase); fields switchable by CTX_EXTRA (cells.py);
  swap tests for tense, voice, noun number (engine/metamorphic2.py, attested forms only); held-out sample B (HOLD=1: 1,500 training
  verses, seed 8, out of the pool) beside dev; Hebrew pronoun suffix in the cell (HEB_SFX=1, heb_run.py); E8 = memory only where it
  agrees with E6 (final_eval stages e8pre / e8lex). Copies before the round: engine/*.r3.py. Test chapters not read.
- 2026-10-26 ~10:30 Round 3 done: eng_v3 frozen (MID_KEYS, pron.gov, HEB_SFX, LEX_ART, noun.after_cstr on by default); rung 1c
  (KJV NT + Tanakh from lexeme-aligner, kjv/, data/kjv_{nt,ot}.db). Report: REPORT-round3-2026-10-26.md.
- 2026-10-26 ~11:30 lexeme-aligner's note (BSB layer fixes B1-B6, KJV C): fixed layer checked against our rebuild
  (e0/layercheck.py -> results/e0_layercheck.json: NT 99.44%, Tanakh 98.51% per word); KJV NT pinned to alignments-by-id v1.1;
  reply drafted, not sent: scratch/outbox/to-lexeme-aligner-13.md. Their new clear-split layer not yet tried.
- 2026-10-26 rungs 2h (Greek->Hebrew Salkinson) and 3 (Hebrew->Vamvas), article det.poss, Hebrew E6 CHOICE_CTX/PRE_LEX: REPORT-rungs-2h-3-2026-10-26.md
- 2026-10-26 eng_v4 frozen (NT B E6 38.34, Tanakh B E6 39.39); ENDINGS=learn: Vamvas E6 +1.2, BSB -0.2/-0.5, not kept; report section 4
2026-10-26 NLLB CPU tests T1-T3 done: nllb/cpu_tests.md
- 2026-10-28 night: rung 4 (Hebrew -> Danish, our drafts' .align, danish/): eng_v10 = eng_v9 + NOWORD + ENDINGS=auto (bootstraps: all targets >= 0); REFL tried, off. REPORT-rung4-danish-2026-10-28.md
- 2026-10-29 lexeme-aligner v0.1.0 as a submodule (vendor/lexeme-aligner, aa60a9c; env.sh LEXEME_ALIGNER, ALIGNER_DATA). First
  test: align-text (no --jev) on the BSB, RUT JON MRK PHM (lab/align/export_bsb.py; 27 s), scored against the BSB tables
  (lab/align/gold_bsb.py; MRK test chapters left out). Content words only (v0.1.0 has no function-word channel; 3,701 gold
  function words not scored): 5,321 words, links P 0.853 R 0.529; a right word 0.849, exact 0.466, unlinked 0.034. Most
  misses are partial: the tables give the whole word with its prefixes, article, auxiliary or ending ("in the land", "I will
  send"), align-text the core ("land", "send"): Tanakh 51% partial, 25% exact, 17% wrong; NT 30% partial, 54% exact, 10% wrong.
  English is favoured (the spine's English glosses feed the gloss step). Outputs: private/align/bsb4/.
- 2026-10-29 align-text --jev (TypeSafe Jev, capped $1 per run; estimates $0.71 BSB, $0.85 DFB) on the same four books.
  BSB against the tables (gold_bsb.py now reads either layer): the jev layer has a function-word channel; all 9,022 words:
  links P 0.922 R 0.762; content P 0.913 R 0.728 (base 0.852 / 0.530), exact 0.605 (0.465); function words P 0.940 R 0.833.
  Wrong links (disjoint from the tables) NT 10.0% -> 2.0%, Tanakh 17.3% -> 4.4%. Den Frie Bibel (CC0, no gold;
  lab/align/export_edition.py, compare_layers.py, test chapters left out): content linked 0.971 base / 0.954 jev, Danish words
  covered 0.386 -> 0.817; base and jev agree on 62.8% of content words, jev adds words to 24.3%, disjoint 5.5% (BSB: 57.4%,
  23.6%, 6.3%), so DFB behaves like the BSB. eflomal varies run to run (BSB base P 0.853 / 0.851). DFB PHM 23 is read into 22
  (the source writes "v23:"). Outputs: private/align/{bsb4,dfb4}/.
- 2026-10-29 evening/night: the bridge pilots (engine <-> LLM / ICL / NLLB), Danish workbench: REPORT-bridge-2026-10-29.md.
  Tools (lab/bridge/): build_corpus.py (engine corpus from an align-text layer; function words derived from the fn channel),
  merge_corpus.py, score.py (the Step A scorer for any text: word choice / form / function words / order / chrF, paired
  bootstraps), engine_render.py (an engine built on one corpus renders another's Hebrew; per-word glosses kept), llm_arms.py
  (prompt arms alone / postedit / glosses / icl / icl_gl / lexicon / icl_lex, and their scoring), check_draft.py (H3 checker
  precision), build_nllb_data.py + run_nllb.sh + score_nllb.py (Hebrew -> Danish NLLB-600M). Whole DFB Tanakh aligned by align-text,
  base and --jev (29,592 requests, est. $17.68): private/align/dfb_ot/; corpora private/rules/data/dfb_{base,jev}.db (+dan merges);
  test = RUT JON JDG 6-8 EXO 3-4 NUM 13-14 (364 v.), dev = JDG 13-14 EXO 14 NUM 22 (116 v.), none in our drafts.
  Dev: engine E5 38.05 (base+drafts) -> 40.95 (jev+drafts); LLM alone 66.7 / 67.2; engine draft, glosses, examples, lexicon in
  the prompt: all null over two runs (run variance 0.5-3.1 chrF); examples + lexicon together -2.65 [-4.2, -1.2]. Checker from
  the engine's glosses: precision 0.12. Options inert; learning curve +1 chrF per doubling. Test (once): engine jev+drafts 38.07
  (drafts alone 36.30, +1.75 [1.24, 2.31]); LLM alone 62.14; NLLB-600M fine-tuned on DFB (1,000 steps) 49.70 (vs engine +11.6, order tau
  -0.075); NLLB on DFB + engine renderings 1:1 (H4) 40.37, after 300 real-only steps 49.60 vs control 49.91 (dilution, no transfer). Consonantal Hebrew for NLLB (zero-shot
  30.95 vs 29.34 pointed, 3x fewer tokens). Twelve LLM runs. Outputs: private/rules/bridge/ (NOTES.md = the private appendix).
- 2026-10-30 morning: the Hebrew <-> Greek lexeme bridge, both ways, for every target language (report section 9):
  lab/bridge/strong_bridge.py (tiers macula / lxx / jev) + bridge_jev.py (Jev chooses among proposed candidates). Coverage by
  content token Tanakh 0.896, NT 0.836; the rest is names, Septuagint-only vocabulary, NT-only concepts. Output
  private/rules/bridge/strong_bridge.{tsv,json}; MACULA WLC TSV kept at private/rules/data/orig/. bcv-query read only; its
  lxx_bridge.tsv update is a request to send after the user's look.
- 2026-10-30 day (user's "go" on the bridge plan; report lab/rules/REPORT-bridge2-2026-10-30.md, appendix private/rules/bridge/NOTES.md):
  grammar bridge (lab/bridge/grammar_bridge.py: Hebrew conjugation x stem -> Greek tense/voice/mood from 67,165 LXX verb pairs) and
  clause index over bcv-commons' two clause layouts (clause_index.py: 89,940 Tanakh / 29,682 NT clauses; retrieval by bridged verb,
  shape, expected tense, content; 92% of test clauses get a candidate). DFB NT aligned by align-text with Jev ($5.38 of $10; DFB NT
  partial, 6,020 verses). Bridged Hebrew -> Danish engine (bridge_engine.py: bridged rendering where the Tanakh alignment never saw the
  lemma): test +2.00 [1.71, 2.31] chrF at 5% of the Tanakh alignment, +1.46 at 10%, +0.56 [0.41, 0.74] at 100%; reserved final set
  (1KI 17-19, 2SA 11-12, JER 36-38, read once) +0.035. Kuni: NT corpora from the published kvg-m_wbt+llm+jev-v4 layer + local
  split file (build_kvg_nt.py; Greek -> Kuni E5 on MRK+JAS chrF 31.75 words / wc 0.506 parts); team's GEN 1-30 + RUT + JON aligned
  locally (base layer); bridged engine on RUT+JON: 14.24 -> 20.66 chrF (+6.43 [5.78, 7.08]), coverage 0.55 -> 0.94. Checker:
  reranking NLLB n-best by flags null/harmful on dev; LLM repair of flagged clauses null (-0.01). NLLB + NT-retrieved hint 49.57
  vs 49.70 (null); Tanakh+NT hint: see report. LLM with evidence per clause (llm_arms2.py, 15 runs): alone 62.63 (5 runs), confident
  gloss 62.83 (3), retrieved NT clause 63.57 (5), repair 62.15 (2); bootstraps in the report. Nothing outward; intern-docs/ (git-ignored)
  holds the bcv-query request. New: lab/bridge/{grammar_bridge,clause_index,checker,nllb_nbest,build_nllb_retrieval,build_nt_corpus,
  build_kvg_nt,bridge_engine,bridge_lexicon_eval,llm_arms2,llm_boot}.py.
- 2026-10-30 afternoon (user: Jev on the team's Genesis/Ruth/Jonah; whole-scope direction; tests for a lexeme-aligner request): the
  team's whole Kuni text (30 books, export_kvg_text.py) aligned with the sibling checkout's align-text, words (its NT bridge on) and by
  PARTS (split file from the pinned segmenter d8fdb53e via export_kvg_split.py, parts view, align-text --usj on the view; Jev on
  GEN RUT JON by parts, $2.25). Ruth links vs the published Jev-by-parts layer (link_agree.py): Tanakh-only base 0.505/0.462, words+NT
  bridge 0.524/0.473, parts base 0.532/0.466, parts+Jev 0.490/0.490 content (two Jev layers of the same recipe agree on half the
  content links). Their lxx_greek prior pack = our macula tier (coverage 0.858 vs our 0.896, whole Tanakh); prior quality on Ruth
  (prior_quality.py): theirs hit@1 0.137 cov 0.854, our bridge x the same eflomal renderings 0.170 / 0.892. Kuni Tanakh corpora from
  the Jev layer (kvg_ot_jev{,_parts}.db, fold_view_layer.py): bridged engine words 19.22 -> 22.62 (+3.40 [2.79, 4.00]), parts 17.51
  -> 21.01 (+3.50 [2.90, 4.13]); nt-only below ot now that the Tanakh side has function words. Request draft (not sent):
  intern-docs/lexeme-aligner-whole-scope-request.md. New: lab/bridge/{export_kvg_text,export_kvg_split,fold_view_layer,link_agree,prior_quality}.py.
- 2026-10-30 evening (user: raise the agent cap, Kuni first, then Danish; explore #2-#4 meanwhile): Kuni LLM arms with the project's
  chapter materials, alone vs + one retrieved NT clause per clause (llm_arms2.py --lang --context --chapters; 70 verses, 5 paired runs
  each): +4.15 chrF [3.31, 5.02], word choice +0.046, form +0.044, fn R +0.107, order null. Danish: dev-tuned weights (tune_retrieval.py)
  -0.64 [-1.17, -0.14] against the default arm; two clauses per clause -0.29 [-0.83, 0.23] against one. NLLB with the Tanakh+NT hint -0.93
  [-1.51, -0.37]. Agreement of two base alignment runs as confidence: agreed links precision 0.706, one-run links 0.232; drafts aligned
  twice with Jev (draft_review.py --layer2): firm flags 0.68, one-run 0.62, either 0.59. Kuni learning curve: the bridged engine flat at
  ~22.5 from 5% of Genesis (+7.4 there, +3.4 at 100%). Zinza prepared (prepare_zin.sh: words and parts base runs on the latest
  segmenter, corpora; Greek -> Zinza wc 0.43 words / 0.49 parts; Jev by parts estimated $10.53, not sent). bcv-query took the
  lexeme tiers and the grammar bridge (strong_bridge.py --tiers, spine merges derived; grammar_bridge.py --bridge --tiers --out, .tsv).
  Analysis dataset pushed by the user (fe645bf6, format 3); format 4 built for lexeme-aligner's cache (conventions.py), not pushed.
  Agent runs this round: 30 (Kuni 10, Danish 20). Jev $0.40.
- 2026-10-30 night (user: test weighted variants of the bridge table locally, after lexeme-aligner found our whole table null as
  NT-bridge priors in their chain): prior_variants.py on Kuni RUT + JON (1,301 Hebrew content tokens, two eflomal runs), top-1 hit of
  the prior against the reference word. Their lxx_greek with their recipe 0.148 / 0.138; the same Greek list weighted by the LXX share
  and summed 0.217 / 0.215 (same coverage 0.845); plus GLAUx pairs for Greek content words outside the NT's 50 most frequent 0.234 /
  0.232; count cuts lower; the jev tier adds nothing; top-5 flat. The gain is in the weighting: their build_priors counts every Greek
  equivalent in full. Proxy only (Jev references); a note proposing the weighting waits for the user (not sent).
  docs/learning-to-speak.md: the picture for new users (exposure for the drafter, grammar for the tools around it).
- 2026-10-30 night: lexeme-aligner's chain test of our weighted priors (4 gold languages, 3 paired runs): link F1 level or slightly
  below lxx_greek (-0.013 to +0.004); they keep lxx_greek, our variants stay settings. Bridge-prior line closed. Zinza Jev layer by
  parts published (full-alignments-llm v1.2, zin-m_wbt+llm+jev-v4; words edition with a parts channel, fingerprints = our words run):
  corpora data/zin_nt_jev_{words,parts}.db (build_kvg_nt.py --prefix zin_nt_jev --split-dir private/align/zin_all/split), 115,069
  links against the base run's 60,908, function words now derived. Greek -> Zinza E5, test MRK JAS 781 v.: words 25.97 -> 37.90,
  +11.93 [11.47, 12.40]; parts 23.00 -> 35.30, +12.30 [11.85, 12.80] (paired bootstrap over verses). Learning curve on the Jev
  corpora (2% to 100% of NT chapters): words chrF 23.5 / 26.5 / 30.2 / 34.2 / 36.4 / 37.9, no plateau; parts +0.07 to +0.09 word
  choice at every size; function-word recall flat near 0.35 from a quarter of the NT. Not comparable with SIL's Kuni Ruth figures
  (another language, an in-NT test, chrF2 on tokens). Wording: "Tanakh" for the books, "Hebrew" for the source language, in all
  reports and docs (user's house rule); code names unchanged.
