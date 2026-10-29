# Source module: Biblical Aramaic (Daniel 2:4b–7:28, Ezra 4:8–6:18 and 7:12–26, Jeremiah 10:11, Genesis 31:47)

Written by an LLM (Claude, Anthropic) in a bsb-add-books session, 2026-10-26, from the grammar of Biblical Aramaic as MACULA
Hebrew annotates it (the WLC; CC BY 4.0). Not measured. Rule ids (`arc.NN`) are stable: a rule keeps its id when its text changes. The rules of `hbo.md` (`hbo.NN`) hold where nothing here differs: prefixes (וְ בְּ
לְ כְּ) and suffix pronouns are each a source unit and are linked the same way.

**The unit is the clause** (or 2–3 clauses of one sentence), from bcv-commons' clause layouts (`CLAUSES.md` in the
language-analysis dataset). "In the clause" means the request's clauses; the verse is not a unit.

- `arc.01` **The emphatic state** (the ending ־אָ / ־תָא, מַלְכָּא "the king") is Aramaic's article: if the target has an article (word,
  prefix, suffix), link it to the noun's emphatic ending where MACULA gives it its own unit, else to the noun; if the target has
  no article: none.
- `arc.02` **דִּי** is the relative ("who, which"), the genitive "of" (בַּיְתָא דִּי אֱלָהָא "the house of God"), and "that / because":
  to the target's relative marker, "of", or connective, by its use in the clause.
- `arc.03` **לְ marking a definite object** (as אֵת in Hebrew): no rendering of its own in most targets; to the target's object marker
  where it has one.
- `arc.04` **The participle as a present or continuous verb**, often with הֲוָה "was" (periphrasis): the target's tense or aspect
  marker goes with the participle, the auxiliary to הֲוָה.
- `arc.05` **אִיתַי / לָא אִיתַי** "there is / there is not": to the target's existential word, and its negative.
- `arc.06` **Persian loanwords** (official titles in Dan 3:2–3, Ezra) render as titles: one target term for one Aramaic word where the
  target has one.
