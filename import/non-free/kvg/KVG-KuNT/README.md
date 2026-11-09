# Kuni New Testament, with Genesis 1-30, Ruth and Jonah (kvg)

The texts are not in git (`import/non-free/`); this README and `edition.yaml` are.

- `source/`: the team's Paratext SFM files as received (UTF-8, NFD): 27 books of the New Testament, Genesis 1-30,
  Ruth, Jonah and the glossary.
- `text/`: one file per chapter, built from `source/` in make-tanakh (`build_text.py` of the same edition folder
  there). 298 chapter files, 8,926 verses.
- `glossary.tsv`: the glossary's terms with their English equivalents and the explanation.

The copy here was taken from make-tanakh's work copy on 2026-11-09 and is equal to it file for file.

**What production's corpora were built from** is not `text/` but `private/lang/kvg/inputs/text`: one file per book in
the Hebrew Bible's numbering, made in research. It holds the same verses, with two differences against what the
first stage's text step makes from `text/` (compared 2026-11-09): 124 of 8,926 verses still carry their section
heading inside the verse (the first stage leaves headings out), and Jonah has one verse more (the two numberings
of Jonah 1:17 / 2:1 are mapped differently). The corpora, the alignment layers and the bundles are pinned to that
text, so the language's configuration keeps naming it until the text is rebuilt on purpose.
