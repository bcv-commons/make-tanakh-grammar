# hbo: source rules for an aligner

Short form of `module.md` (same ids; the whole rule is there). Written by an LLM (Claude), not measured. Each Hebrew prefix and
suffix (MACULA's morphemes) is a source unit of its own. A target module's line overrides a rule here. "None" = no rendering of
its own.

**The unit is the clause** (or 2–3 clauses of one sentence), from bcv-commons' clause layouts (`CLAUSES.md` in the
language-analysis dataset). "In the clause" means the request's clauses; the verse is not a unit.

## Prefixes and suffixes
- `hbo.01` וְ / וַ → the target's "and" or connective; often none. The narrative past's tense marker → the verb, not the וַ.
- `hbo.02` בְּ לְ כְּ מִן → the target preposition, postposition or case marker. לְ + infinitive → "to"; לְ of the indirect object → "to" / dative, else the verb.
- `hbo.03` Article הַ → the target's article (word, prefix, suffix), else none. Inside בַּ / לַ / כַּ: with the preposition, or none.
- `hbo.04` Suffix pronoun: on a noun → the target possessive; on a verb → the object pronoun or marker; on a preposition → the pronoun.
- `hbo.05` אֵת (object marker): none; with a suffix (אֹתוֹ) → the object pronoun (`hbo.04`). אֵת "with" is `hbo.02`.
- `hbo.06` הֲ → the target's question word or particle, else none.

## Verb
- `hbo.07` The subject is in the verb form: target subject marker → the verb; → a separate pronoun (אֲנִי, הוּא) only if the clause has one.
- `hbo.08` Target causative, passive, reflexive, tense and aspect markers → the verb.
- `hbo.09` Infinitive absolute + finite verb: the target's "surely" → the infinitive absolute, the verb → the finite verb.
- `hbo.10` וַיְהִי / וְהָיָה: often none; a target "when / after" → the clause it introduces.
- `hbo.11` Verbless clause: a target copula has no Hebrew word (linked to nothing, unless the target module says otherwise).

## Noun phrase
- `hbo.12` Construct chain: the target's "of" or genitive marker → the construct noun (or the next noun where the target marks the possessor); the article on the last noun makes the chain definite.
- `hbo.13` כֹּל → "all / every".
- `hbo.14` Agreement marker on an adjective → that adjective.

## Particles
- `hbo.15` אֲשֶׁר, שֶׁ → the target's relative marker, else none or the relative clause's verb.
- `hbo.16` כִּי → the target connective; "that" for content clauses.
- `hbo.17` לֹא, אַל, אֵין, בִּלְתִּי → the target negative; אֵין is also "there is not".
- `hbo.18` הִנֵּה → the target's attention word; often none.
- `hbo.19` יֵשׁ → the target's existential word or verb.

## Names
- `hbo.20` יהוה, אֱלֹהִים → the target's name or title for God.
- `hbo.21` Names: match by spelling and position; an added marker is still the name.
