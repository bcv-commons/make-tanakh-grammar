# Split exporter (local, 2026-10-26)

`export_split.py <project> <edition id> [--out DIR]` writes lexeme-aligner's `bcv-split/0.1` (their docs/split-format.md) from a
project's morph store. To become `morphs.py export-split` at the next template update (template patches paused).

| file | tokens | rows | validator (`python -m lexeme_aligner.split_format check`) |
|---|---|---|---|
| `out/zin_wbt/` (Zinza, CC BY-SA text) | 173,368 | 240,383 | ALL PASS, also with `--usj usj-zin_wbt` |
| `local_output/kvg/split/KVG-KuNT/` (Kuni, our local copy, NC-ND, local only) | 252,378 | 281,947 | ALL PASS without `--usj`; with it 22,871 tokens of 28 verses differ: our Kuni text is the team's newer working copy (and has OT books their kvg_wbt lacks), so it is not their edition |

Zinza: 29,684 tokens divided (17%), no tone parts. Kuni: 22,717 divided, 329 with a grammatical-tone part, 2,880 hyphen
affixes as tokens of their own; 36,754 hyphen pieces stay whole (the project store does not split -te, -gé ...).
Danish, Jamaican: the store has no morph entries; nothing to export.

## The segmenter bundle (`seg_bundle.py <project> <DIR>`)

What we hand over besides the data: the store's facts and a segmenter that runs without the project.
`seg_facts.json` (`bcv-segfacts/0.1`: the morph entries without their evidence refs, never-split words, orthography, attested words
with counts, the words' Greek classes), `morphs.py` (copy of the segmenter's code, MIT), `bcv_segment.py` (reader:
`load(dir).split(word)`). Checked in an isolated Python from another folder: splits every corpus word exactly as the store does
(Zinza 18,979 words, Kuni 16,883: 0 different). Bundles: `bundle/zin_wbt/` (1.1 MB), Kuni local
`local_output/kvg/split/KVG-KuNT-bundle/`. The fact file is derived from the edition: published only with a free text.
A first version that kept a field list missed `productive` (174 Kuni words split differently); it now keeps every field.

All-`whole` files (no morph entries; a test of `i` and `token` only): Jamaican `local_output/jam/split/jambswn-et/` (254,257
tokens) ALL PASS with `--usj usj-jambsw`; Danish `out/den-frie-bibel/` (364,370) passes the rebuild, but neither of their Danish
copies (`dan_det`, `cdfbiv`) is Den Frie Bibel, so `i` can't be checked against theirs.
