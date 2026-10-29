# Rules-engine lab: run log
- 2026-10-26T06:06Z Day 1 (user away, "keep going"): E0 (alignment from the BSB tables; lexeme-aligner layer differs in 9.0%, note 12 sent by the user), E1, E1b, E2-E7, swap tests, linguist rounds r1 (140k tokens) and r2 (164k), rung 1b (Hebrew) adapter, one test evaluation (results/final_test.json). Report: REPORT-2026-10-26.md.
- 2026-10-26 (later) Detector calibration and agent-free rounds (auto/, auto/CALIBRATION.md); BSB NLLB instrument training (nllb/queue.sh, ~7 h per model).
- 2026-10-26 ~09:00 Round 3, agent-free (r3/): participant ids as fields (engine/parts.py from scripts/participants.py --mentions, all NT books, build/participants/);
  D3 with them (results/auto/v2p*.md); `gov` (governed by a preposition / in a noun phrase); fields switchable by CTX_EXTRA (cells.py);
  swap tests for tense, voice, noun number (engine/metamorphic2.py, attested forms only); held-out sample B (HOLD=1: 1,500 training
  verses, seed 8, out of the pool) beside dev; Hebrew pronoun suffix in the cell (HEB_SFX=1, heb_run.py); E8 = memory only where it
  agrees with E6 (final_eval stages e8pre / e8lex). Copies before the round: engine/*.r3.py. Test chapters not read.
- 2026-10-26 ~10:30 Round 3 done: eng_v3 frozen (MID_KEYS, pron.gov, HEB_SFX, LEX_ART, noun.after_cstr on by default); rung 1c
  (KJV NT + OT from lexeme-aligner, kjv/, data/kjv_{nt,ot}.db). Report: REPORT-round3-2026-10-26.md.
- 2026-10-26 ~11:30 lexeme-aligner's note (BSB layer fixes B1-B6, KJV C): fixed layer checked against our rebuild
  (e0/layercheck.py -> results/e0_layercheck.json: NT 99.44%, OT 98.51% per word); KJV NT pinned to alignments-by-id v1.1;
  reply drafted, not sent: scratch/outbox/to-lexeme-aligner-13.md. Their new clear-split layer not yet tried.
- 2026-10-26 rungs 2h (Greek->Hebrew Salkinson) and 3 (Hebrew->Vamvas), article det.poss, Hebrew E6 CHOICE_CTX/PRE_LEX: REPORT-rungs-2h-3-2026-10-26.md
- 2026-10-26 eng_v4 frozen (NT B E6 38.34, OT B E6 39.39); ENDINGS=learn: Vamvas E6 +1.2, BSB -0.2/-0.5, not kept; report section 4
2026-10-26 NLLB CPU tests T1-T3 done: nllb/cpu_tests.md
- 2026-10-28 night: rung 4 (Hebrew -> Danish, our drafts' .align, danish/): eng_v10 = eng_v9 + NOWORD + ENDINGS=auto (bootstraps: all targets >= 0); REFL tried, off. REPORT-rung4-danish-2026-10-28.md
- 2026-10-29 lexeme-aligner v0.1.0 as a submodule (vendor/lexeme-aligner, aa60a9c; env.sh LEXEME_ALIGNER, ALIGNER_DATA). First
  test: align-text (no --jev) on the BSB, RUT JON MRK PHM (lab/align/export_bsb.py; 27 s), scored against the BSB tables
  (lab/align/gold_bsb.py; MRK test chapters left out). Content words only (v0.1.0 has no function-word channel; 3,701 gold
  function words not scored): 5,321 words, links P 0.853 R 0.529; a right word 0.849, exact 0.466, unlinked 0.034. Most
  misses are partial: the tables give the whole word with its prefixes, article, auxiliary or ending ("in the land", "I will
  send"), align-text the core ("land", "send"): OT 51% partial, 25% exact, 17% wrong; NT 30% partial, 54% exact, 10% wrong.
  English is favoured (the spine's English glosses feed the gloss step). Outputs: private/align/bsb4/.
- 2026-10-29 align-text --jev (TypeSafe Jev, capped $1 per run; estimates $0.71 BSB, $0.85 DFB) on the same four books.
  BSB against the tables (gold_bsb.py now reads either layer): the jev layer has a function-word channel; all 9,022 words:
  links P 0.922 R 0.762; content P 0.913 R 0.728 (base 0.852 / 0.530), exact 0.605 (0.465); function words P 0.940 R 0.833.
  Wrong links (disjoint from the tables) NT 10.0% -> 2.0%, OT 17.3% -> 4.4%. Den Frie Bibel (CC0, no gold;
  lab/align/export_edition.py, compare_layers.py, test chapters left out): content linked 0.971 base / 0.954 jev, Danish words
  covered 0.386 -> 0.817; base and jev agree on 62.8% of content words, jev adds words to 24.3%, disjoint 5.5% (BSB: 57.4%,
  23.6%, 6.3%), so DFB behaves like the BSB. eflomal varies run to run (BSB base P 0.853 / 0.851). DFB PHM 23 is read into 22
  (the source writes "v23:"). Outputs: private/align/{bsb4,dfb4}/.
