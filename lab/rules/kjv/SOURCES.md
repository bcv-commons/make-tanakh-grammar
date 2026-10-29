# Rung 1c sources (read 2026-10-26)

- KJV text: bible.helloao.org `eng_kjv` (= eBible eng-kjv2006), `complete.json`, public domain outside the UK;
  local copy `data/kjv/dl/eng_kjv_complete.json`. Fingerprints (compact-alignments v1) match every layer file read.
- NT links: bcv-commons/alignments-by-id `tr/e/eng/eng_kjv`, tag v1.1 (commit bb56fae2ad7d865bfc48679e4640747b4b1756f4; its
  KJV files are identical to main 81dfec69 that was read first). CC0. Joined by the Nestle 1904 ids each link carries.
- OT links: bcv-commons/full-alignments-llm `e/eng/eng_kjv+llm+jev-v4`, tag **v1.0** (097268d2), read 2026-10-26; links identical to main 9f7135e4 read first (287,374 words, `data/kjv_ot_main9f7135e4.db` kept); v1.0 adds the checker's "renders nothing" answers as ownerless `+` words: of 598,808 KJV tokens 92.5% linked, 6.8% decided none, 0.7% undecided.
  CC0. Spine: compact-alignments `_index` (keys, fn_keys) via scripts/full_align.py.
- The OT layer is pinned to v1.0 (above). The BSB layer check (`e0/layercheck_v1.py`) reads full-alignments-manual v1.0 (a12264ed).
