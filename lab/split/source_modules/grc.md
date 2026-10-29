# Source module: Koine Greek (the New Testament)

Written by an LLM (Claude, Anthropic) in a bsb-add-books session, 2026-10-26, from the grammar of Koine Greek as MACULA Greek
(Nestle 1904 / the Berean Greek Bible; CC BY 4.0) annotates it. Not measured: each rule is a convention for linking, to be checked
against a language's target module and, where one exists, a hand-made alignment. The same text holds for every target language;
what a target has or lacks is in its target module.

**The unit is the clause** (or 2–3 clauses of one sentence), from bcv-commons' clause layouts (`CLAUSES.md` in the
language-analysis dataset). "In the clause" means the request's clauses; the verse is not a unit.

**Rule ids** (`grc.NN`) are stable: a rule keeps its id when its text changes, and a new rule gets a new number.

**Rule form.** Each rule names the Greek unit, then how it is linked when the target has the matching category and when it
does not. "None" means the Greek word has no rendering of its own; it is not linked to a neighbour to fill a gap.

## The verb

- `grc.01` **The ending carries the subject.** A finite verb's person and number are in its ending. A target subject marker (a free
  pronoun, a prefix, a verb ending) goes with the Greek verb, unless the clause has a separate subject pronoun (ἐγώ, σύ, ἡμεῖς,
  ὑμεῖς, αὐτός, οὗτος, ἐκεῖνος): then the target's subject word goes to that pronoun.
- `grc.02` **Tense, mood, voice, aspect** are in the verb form. Target tense, aspect, mood and voice markers (auxiliaries, affixes,
  particles) go with the Greek verb, never with another word.
- `grc.03` **Compound verbs** (ἐκ-βάλλω, ἀπο-στέλλω, συν-άγω) are one word: a target verb + particle or verb + preposition renders the
  whole Greek verb, unless the clause repeats the preposition separately.
- `grc.04` **Participles**: an attributive or substantive participle (ὁ πιστεύων "the one who believes") is a relative clause in many
  targets: the target relative marker or subject marker goes with the article + participle (`grc.08`), the verb with the
  participle. A circumstantial participle (ἀποκριθεὶς εἶπεν "answering, he said") is often a finite verb, a conjunction + verb,
  or none (answering … said → said).
- `grc.05` **Infinitives**: τοῦ / εἰς τό + infinitive (purpose), ἐν τῷ + infinitive (while), μετὰ τό + infinitive (after) are clauses:
  the target's purpose or time marker goes to the article (or the preposition), the verb to the infinitive.
- `grc.06` **Periphrasis** (ἦν διδάσκων "was teaching"): the target's continuous form goes with both: auxiliary to εἰμί, verb to the
  participle.
- `grc.07` **λέγων / λέγοντες, ὅτι** introducing speech: the target's quote marker (a word "that", a speech particle, a colon-word) goes
  to ὅτι or λέγων; none when the target has no marker.

## The noun phrase

- `grc.08` **The article ὁ ἡ τό.** If the target has an article (a word, a prefix, a suffix such as a definite ending): link to it.
  If not: none. It is not linked to a preposition or a possessive the target adds, nor to a demonstrative, unless
  the target module says the target's demonstrative renders the article (an anaphoric "that one"; Zinza óogwo). With a participle or a
  prepositional phrase (οἱ ἐν τῷ οἴκῳ "those in the house") it makes a relative or a noun: see `grc.04`.
- `grc.09` **Case** is in the ending. Target case markers (affixes, postpositions, prepositions like "of", "to") go with the noun or
  with the Greek preposition that governs it; the genitive "of" goes with the genitive noun when no Greek word renders it.
- `grc.10` **Enclitic possessives** μου, σου, αὐτοῦ, ἡμῶν, ὑμῶν, αὐτῶν: link to the target possessive (word, affix, ending) on the
   possessed noun.
- `grc.11` **Adjectives and numerals** agree with their noun; a target agreement marker (class prefix, ending) goes with the
   adjective it is on, not with the noun.

## Particles and conjunctions

- `grc.12` **καί** "and", also "also / even" (καὶ αὐτός "he too"); at the start of a narrative sentence it often has no rendering.
- `grc.13` **δέ, μέν, γάρ, οὖν, τε, ἄρα** are discourse particles: link to the target connective that renders them ("but", "for",
   "so", "then"); often none.
- `grc.14` **Negation** οὐ, οὐκ, οὐχ, οὐχί, μή, οὐδέ, μηδέ, οὐκέτι, μηκέτι: to the target's negative (particle, affix, auxiliary,
   negative verb form). With a negative pronoun (οὐδείς "no one") the target's "no one" goes to οὐδείς.
- `grc.15` **ἵνα, ὅπως** + subjunctive: purpose or content; to the target's "so that / that" (word or verb form), else with the verb.
- `grc.16` **ἰδού, ἴδε** "look": to the target's attention word; often none.
- `grc.17` **ἄν** with a verb: no rendering of its own in most targets; with the verb when the target marks the conditional on it.

## Names

- `grc.18` **Hebrew names** are often indeclinable (Ἀβραάμ, Δαυίδ); Greek names inflect (Παῦλος, Παύλου). Match names by spelling and
   position; a target name with an added class marker or case ending is still the name.
- `grc.19` **κύριος** for the LORD (quoting the Old Testament) and for Jesus; **θεός** with or without the article: the target's word for
   God may carry its own article or not, see `grc.08`.
