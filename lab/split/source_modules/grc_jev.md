# grc: source rules for an aligner

Short form of `module.md` (same ids; the whole rule is there). Written by an LLM (Claude), not measured. A target module's
line overrides a rule here. "None" = no rendering of its own; don't link it to a neighbour to fill a gap.

**The unit is the clause** (or 2–3 clauses of one sentence), from bcv-commons' clause layouts (`CLAUSES.md` in the
language-analysis dataset). "In the clause" means the request's clauses; the verse is not a unit.

## Verb
- `grc.01` Finite verb: the subject is in its ending. Target subject marker → the verb; → a separate subject pronoun (ἐγώ, σύ, αὐτός, οὗτος) only if the clause has one.
- `grc.02` Target tense, aspect, mood, voice markers → the verb, never another word.
- `grc.03` Compound verb (ἐκ-βάλλω) is one word: a target verb + particle renders the whole verb.
- `grc.04` Article + participle (ὁ πιστεύων) = relative: target relative/subject marker → the article, verb → the participle. Circumstantial participle: a finite verb, a conjunction + verb, or none.
- `grc.05` τοῦ / εἰς τό / ἐν τῷ / μετὰ τό + infinitive: target purpose or time marker → the article or preposition, verb → the infinitive.
- `grc.06` εἰμί + participle: target auxiliary → εἰμί, verb → the participle.
- `grc.07` Target quote marker → ὅτι or λέγων; none if the target has none.

## Noun phrase
- `grc.08` Article ὁ: → the target's article (word, prefix, suffix); else none. Not to a preposition or possessive the target adds; not to a demonstrative unless the target module says it renders the article.
- `grc.09` Case: target case marker or "of / to" → the noun, or the Greek preposition governing it.
- `grc.10` μου, σου, αὐτοῦ, ἡμῶν, ὑμῶν, αὐτῶν → the target possessive on the possessed noun.
- `grc.11` Agreement marker on an adjective or numeral → that adjective, not the noun.

## Particles
- `grc.12` καί → "and" / "also"; often none at a narrative sentence start.
- `grc.13` δέ, μέν, γάρ, οὖν, τε, ἄρα → the target connective; often none.
- `grc.14` οὐ, μή, οὐδέ, οὐκέτι … → the target negative (particle, affix, auxiliary). οὐδείς → the target's "no one".
- `grc.15` ἵνα, ὅπως → the target's "so that / that", else the verb.
- `grc.16` ἰδού, ἴδε → the target's attention word; often none.
- `grc.17` ἄν: none in most targets; with the verb where the target marks the conditional on it.

## Names
- `grc.18` Names: match by spelling and position; an added class marker or case ending is still the name.
- `grc.19` κύριος (the LORD, Jesus), θεός: the target's word for God, with or without its own article (`grc.08`).
