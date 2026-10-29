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
