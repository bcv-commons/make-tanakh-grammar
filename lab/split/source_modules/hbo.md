# Source module: Biblical Hebrew (the Old Testament)

Written by an LLM (Claude, Anthropic) in a bsb-add-books session, 2026-10-26, from the grammar of Biblical Hebrew as MACULA Hebrew
(the WLC; CC BY 4.0) annotates it: each word is divided into morphemes (prefixes, stem, suffixes), and each morpheme is a source
unit of its own. Not measured: conventions for linking, to be checked against a language's target module. The same text holds for
every target; what a target has or lacks is in its target module. Aramaic passages: see `arc.md`.

**The unit is the clause** (or 2–3 clauses of one sentence), from bcv-commons' clause layouts (`CLAUSES.md` in the
language-analysis dataset). "In the clause" means the request's clauses; the verse is not a unit.

**Rule form** as in `grc.md`: the Hebrew unit, then how it is linked when the target has the matching category and when it does
not; "none" means no rendering of its own.

## Prefixes and suffixes (each its own source unit)

- `hbo.01` **וְ / וַ** "and": at the start of a clause it joins it to the one before. Link to the target's "and" or clause connective;
  often none (a new sentence). The וַ of the narrative past (wayyiqtol) is part of the verb form's meaning: the target's
  narrative tense marker goes to the verb, the וַ itself is "and" or none.
- `hbo.02` **The prepositions בְּ לְ כְּ מִן** (prefixed or separate): link to the target's preposition, postposition or case marker. לְ
  before an infinitive marks purpose or content ("to …"); לְ marking the indirect object goes to the target's "to" or dative
  marker, else with the verb.
- `hbo.03` **The article הַ**: as the Greek article (`grc.08`): to the target's article (word, prefix, suffix), else none. Inside a
  preposition (בַּ, לַ, כַּ) the article has no letters of its own; it goes with the preposition's unit or none.
- `hbo.04` **Suffix pronouns**: on a noun, the possessor (בֵּיתוֹ "his house"): to the target possessive. On a verb, the object
  (שְׁלָחַנִי "he sent me"): to the target object pronoun or object marker. On a preposition, its object (לוֹ "to him", אִתּוֹ
  "with him"): to the target pronoun (or the pronoun part of a target word).
- `hbo.05` **אֵת** (object marker): no rendering of its own in most targets (none); with a suffix (אֹתוֹ "him") it is the object pronoun:
  `hbo.04`. אֵת "with" (a preposition, the same letters) is `hbo.02`.
- `hbo.06` **The interrogative הֲ**: to the target's question word or particle, else none (the question is in the intonation).

## The verb

- `hbo.07` **The subject is in the verb form** (person, number, gender): a target subject marker goes with the verb, unless the clause has
  a separate subject pronoun (אֲנִי, אַתָּה, הוּא, …): then to that pronoun.
- `hbo.08` **Stem (binyan) and conjugation** carry voice, causation and aspect: target causative, passive, reflexive markers and tense
  or aspect markers go with the verb.
- `hbo.09` **The infinitive absolute with a finite verb** (מוֹת תָּמוּת "you shall surely die"): the target's emphasis ("surely") goes to
  the infinitive absolute; the verb to the finite verb.
- `hbo.10` **וַיְהִי / וְהָיָה** "and it came to pass": often none; a target time phrase ("when …", "after …") goes to the clause it
   introduces.
- `hbo.11` **Verbless clauses** (יְהוָה אֱלֹהֵינוּ "the LORD is our God"): a target copula ("is") has no Hebrew word: none on the
   source side (it is a target word linked to nothing, or with the predicate where the target's conventions say so).

## The noun phrase

- `hbo.12` **Construct chains** (בֵּית הַמֶּלֶךְ "the house of the king"): the construct noun has no article; the target's "of" or
   genitive marker goes with the construct noun (or with the noun after it where the target marks the possessor); the article
   on the last noun makes the whole chain definite: the target's article on the first noun goes to that הַ.
- `hbo.13` **כֹּל** "all, every" is a noun in construct: to the target's "all / every".
- `hbo.14` **Adjectives** follow the noun and agree; a target agreement marker goes with the adjective.

## Particles

- `hbo.15` **אֲשֶׁר, שֶׁ** "who, which, that": to the target's relative marker (word, affix), else none or with the verb of the
   relative clause.
- `hbo.16` **כִּי** "for, because, that, when, indeed": to the target's connective; content clauses "that": to the target's "that".
- `hbo.17` **לֹא, אַל, אֵין, בִּלְתִּי**: to the target's negative (particle, affix, negative verb). אֵין is also "there is not".
- `hbo.18` **הִנֵּה** "look": to the target's attention word; often none.
- `hbo.19` **יֵשׁ** "there is": to the target's existential word or verb.

## Names

- `hbo.20` **יהוה** (read Adonai, "the LORD") and **אֱלֹהִים** (God; also "gods"): to the target's name or title for God.
- `hbo.21` **Names** match by spelling and position; a target name with an added marker is still the name.
