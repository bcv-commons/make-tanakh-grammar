# The rules-engine lab: learning to build a Bible rules engine, language by language (design, 2026-10-26)

**The pivot (user, 2026-10-26).** Crawl before running. Drafting with an LLM, ICL or NLLB, the growing pool and the databases
built for them are parked; none of them is measured as a drafter now. The lab builds **rules engines**: deterministic programs
that generate a translation from the analysed original, TBTA's target half, with MACULA's analysis instead of an authored record.
What is measured is **our skill at analysing an existing translation and building an engine for it**: how good an engine we
can build for each language, and whether the skill improves from one language to the next.

English is the pilot, not a throw-away: the English engine is meant to be published in the end (academic interest is likely),
and every part of it is built to be reused for the next language. Public since 2026-10-29 (user): code, method and reports; protected texts and anything built from them stay local (RELATIONS.md, section 6).

**State (2026-10-26, end of day 1):** E0-E2, E1b and two linguist rounds done on rung 1, rung 1b running on the same
engine; results, findings and next steps in `scratch/rules/REPORT-2026-10-26.md`.
**State (2026-10-26, round 3):** agent-free round and rung 1c (KJV) done; `scratch/rules/REPORT-round3-2026-10-26.md`, engine `scratch/rules/eng_v3/`.

## 1. The ladder of languages

Each rung has a source (an analysed original), a reference translation (the "team text" the engine learns from and is measured
against) and a word alignment between them. Without an alignment the component measures (§4) cannot be computed, so a rung
without one starts by building it.

| rung | source → target | reference | alignment | licence | what it adds |
|---|---|---|---|---|---|
| 1 | Greek NT → English | BSB (from the BGB) | the BSB's own table, every word (`orig/grc.sqlite` `bsb`) | PD; MACULA CC BY 4.0 | the pilot: architecture, rule format, measures, the agent loop |
| 1b | Hebrew → English | BSB | `orig/heb.sqlite` `bsb` | PD; MACULA CC BY 4.0 | the second source: does the engine's source layer generalise |
| 1c | Greek NT (TR) → English | KJV (1769, `eng-kjv2006`, Strong's-tagged; added 2026-10-26) | to come: lexeme-aligner, full, TR spine (request `scratch/outbox/to-lexeme-aligner-12.md`); their compact `eng_cpb` has content words only | PD outside the UK | thou / ye, -est / -eth, pronoun cases, inversion in questions: the same transfer rules, a second spellout table |
| 2 | Greek NT → modern Hebrew | HEBM95 (1995 Modern Hebrew, Bible Society in Israel; chosen by the user 2026-10-26) | lexeme-aligner `HEBM95+llm+jev-v4`, the whole NT (27 books, 137,404 rows, function words included; prefixes keep the word whole, the Greek function word points at the word that carries it) | © Bible Society in Israel, not open: local only, like a non-free edition; the user will ask the rights holder | rich morphology: binyanim, prefixed particles, construct state, gender agreement, right to left |
| 3 | Hebrew → Greek | Vamvas (1850, whole Bible) | lexeme-aligner `ell_GreVamvas+llm+jev-v4` (CC0, 39/39 Tanakh books) | CC0 | the reverse direction; cases, articles, participles as target |
| 3b | Hebrew → Koine Greek | the LXX (Swete, PD) | eflomal + Jev alignment to the Hebrew, from lexeme-aligner (the user arranges it, 2026-10-26); CATSS is restricted | to clear | the true Koine case (the LXX is Koine: Jewish translation Greek); only verses where the LXX follows the MT (the LXX quarantine) |
| 4 | Greek / Hebrew → Danish | Den Frie Bibel (CC0); our own Danish Tanakh drafts with `.align` | DFB: none yet (to build); ours: exact | CC0 | transfer: how much of the English engine carries to a close language |
| 5 | → Arabic dialects, … | to find (bcv-commons/bibles catalogue) | to build | to clear | root-and-pattern morphology, diglossia |
| then | → Kuni, the second Bantu language | the team's text | Jev layers | NC-ND, local | the languages the lab is for |

Two cautions, stated now so that the results are not over-read:
- **HEBM95 is not free.** Its text and anything that quotes it stay local (`local_output/` rules); the rules we derive from it are
  our own work, but publishing the Hebrew engine waits for the Bible Society in Israel's consent. Its alignment is Jev's, not a
  gold one: the component measures on rung 2 are against a machine alignment (lexeme-aligner's MRK 1, JHN 3, ROM 8 pilot judged it).
- **Vamvas is not Koine.** It is 19th-century learned Greek: the measurable rehearsal for rung 3b. The LXX is Koine; it is the
  hard case because it often does not follow the MT and its alignment is still to be made (lexeme-aligner, eflomal + Jev).

## 2. The engine

One engine, language-neutral code; everything language-specific lives in data files, each rule with an id, its provenance (the
verses that motivated it, who wrote it: script, agent run, person) and its counts.

1. **Source layer** (shared by all targets): the MACULA trees, `orig/grc.sqlite` / `orig/heb.sqlite` `nodes` (clause, phrase,
   rule, role, head) and `tokens` (lemma, morphology). Read into one tree per verse; nothing language-specific.
2. **Transfer rules** (per target): restructure the source tree into the target's structure, TBTA's nine kinds as the checklist
   (feature adjustment, tense/aspect/mood mapping, relative-clause strategy, genitive relations, role-to-case mapping,
   collocations, structural adjustment such as participle chains to finite clauses, inserted explanations).
3. **Lexicon** (per target): source lemma (+ sense context) → target lemma with its features; learned from the reference's
   alignment, choices between senses by context rules.
4. **Synthesis rules** (per target): order, function words (articles, auxiliaries, prepositions, particles), agreement, inflection
   (a paradigm table per language, then spellout), the morphophonemic and orthographic surface.
5. **Trace:** every output word records the rules and lexicon entries that produced it, so every error points at a rule.

The engine never calls an LLM. Rule files are our own work (CC0 when published); the source analysis keeps MACULA's CC BY credit.

## 3. The skill: the linguist's seat

TBTA learns because a linguist edits its rules after each generated text. Here an agent sits in that seat:

1. the engine generates the training chapters;
2. a script compares them with the reference, per component (§4), and lists the largest classes of differences with their traces;
3. the agent reads one class (source tree, reference, engine output, trace) and proposes a change: a new rule, a narrower or
   wider condition, a lexicon entry, a paradigm cell; with the verses that motivate it;
4. the engine runs with the change on the training chapters (precision of the rule: where it fires, how often it agrees with the
   reference) and on the dev chapters; the change stays if the component improves and breaks fewer than it fixes;
5. everything is logged: the change, the evidence, the before and after, the tokens spent.

The agent writes rules, never target text. One agent at a time, no swarms; the user says go before each round.
The **skill** is the part that improves from language to language: the prompt and checklist the agent works with, the scripts
that find difference classes, the rule kinds the engine supports. What it learns on English is written into that skill, and the
next rung starts from it.

## 4. The measures

On held-out chapters, never seen by the agent or the scripts that propose rules. Same Greek / Hebrew chapters on every rung
where the reference has them, so the languages can be compared on the same source.

**The engine, per component** (all against the reference's alignment):
- **word choice:** per source content word, the engine's target lemma = the reference's;
- **form:** given the right lemma, the inflected form = the reference's;
- **function words:** recall and precision of the reference's unaligned and function words (articles, auxiliaries, particles);
- **order:** rank correlation of the aligned words' positions, engine against reference, per clause;
- **structure:** share of the reference's restructurings (a participle made finite, a clause split or joined) the engine makes;
- **coverage:** share of source tokens and clauses the engine handles without a fallback;
- **rule precision:** per rule, on held-out text: fired, agreed;
- one whole-verse similarity (chrF of the engine's output against the reference) as a summary only.

**The skill, per rung:**
- the curve of the component measures over the agent's rounds;
- rounds and tokens to reach a level (for instance word choice 80%, order 0.8);
- **transfer:** how many rules and rule kinds carry over from the previous rung unchanged, changed, or not at all; how much
  faster the new rung reaches the levels of the previous one.

None of this compares the engine with an LLM or NLLB drafter. That comparison is for a later phase.

## 4a. Word-level contrasts inside the clause (added 2026-10-26, the user's question)

The engine's synthesis rules (agreement, inflection, function words) are found by **contrasts**: the same construction with one
feature changed (3rd person → 2nd, singular → plural, present → aorist, active → passive, positive → negative), and what that
changes in the target words. On English we must find "-s for the 3rd person singular present" from the data as if we did not know
it, because on Kuni we will not know. Four kinds of test, each a script in `scratch/rules/contrast/`:

1. **Natural minimal pairs (discovery, from the reference).** Source tokens with the same lemma and the same tree context (clause
   type, the token's role, the other morphological features) that differ in one feature; their aligned target spans compared:
   a suffix edit, a word added or dropped (a pronoun, an auxiliary), a different word. Output: a contrast table per feature
   (value pair → target change, count, consistency, exceptions, examples). The confounds are recorded, not averaged away: the
   BSB renders many Greek historic presents as past ("He said"), questions take "do", εἰμί is its own paradigm. The table is
   conditioned on the target's own choice where the reference shows it (the aligned span's tense) and on clause context.
2. **What else changes in the clause.** For each pair, the diff of the whole clause's aligned words, not only the token's: an
   inserted subject pronoun, agreement on another word, a moved word. This is where feature copying and pro-drop rules come from.
3. **Metamorphic tests on the engine (no reference needed).** Every held-out clause with the feature swapped in the source tree,
   run through the engine: only the words a rule names may change, and only in the way the contrast table says. Catches rules that
   are too broad and rules that interfere. The suite grows with every accepted rule.
4. **Elicitation (known languages only, a sample).** A perturbed source clause the corpus never shows (a verb attested only in
   the 3rd person, put in the 2nd), the engine's output judged by an oracle: an LLM or a speaker for English, Danish, Hebrew; the
   team for Kuni (the question page; TBTA's grammar-introduction sentences are the same idea). The oracle judges, it never
   drafts. This measures how far the rules generalise beyond the attested cells.

Per language and feature, the **paradigm grid** shows which cells the corpus attests, how often, and how consistently; the
unattested cells are the elicitation list. Contrast tables come after E1 (step E1b) and before the hand rules: E2's rules are
written from the tables, not from what we know of English.

Feasibility (2026-10-26, `scratch/rules/contrast/mine_person.py`, NT, present active indicative): 2,126 3S and 305 2S tokens,
47 lemmas in both. In the aligned BSB words, 2S spans contain "you" in 127 of 199 readable cases, the verb word ends in -s 5
times; 3S: -s in 400 of 1,374, "he/she/it" in 277, a past form for 113 (historic presents), εἰμί and auxiliaries for 752. The
contrast is there and visible; the confounds are as large as the signal, which is why the tables must be conditioned. The
word reader still misreads a few spans (JHN 1:22, 1:26): to fix in E0.

## 5. The first rung, step by step (each for the user's go)

| step | what | cost |
|---|---|---|
| **E0 data check** (started 2026-10-26: the BSB layer differs from the BSB's own tables in 9.0% of NT words, `scratch/rules/e0/swapcheck.py`; the lab rebuilds the alignment from the tables) | the trees and the BSB alignment joined per verse; Mark split into training, dev and held-out chapters (fixed); what share of the BSB words are aligned, which are not (the function words the engine must add) | CPU |
| **E1 baseline by script** | lexicon from the alignment (most frequent BSB word per lemma and morphology), source order, no rules: the floor of every measure | CPU |
| **E1b contrast tables** | §4a kinds 1-2 for person, number, tense, voice, polarity on Mark; the paradigm grid | CPU |
| **E2 first hand rules** | a few rules written from the contrast tables for simple main clauses (subject-verb-object order, articles, "not", tense auxiliaries), measured against E1: shows what plain rules give | CPU |
| **E3 the first agent round** | the loop of §3 on one difference class, one agent, a small token budget | about 0.5M tokens |
| **E4 rounds** | clause type by clause type: main clauses, speech frames, participles, subordinate and relative clauses, then the rest of Mark | per round, for go |

Rung 1b (Hebrew into English) follows once Mark's curve flattens; then rung 2.

## 6. What is parked, and what is kept

The interrupted strand's full state and to-do list: `self-training-lab-2026-10/README.md`.

Parked: the growing-pool restart (`scratch/lab/st/grow/`, `reset_empty.sh` not run), every LLM / ICL / NLLB drafting test, the
TBTA feature test, S8 part 3. Their results stay as they are in `scratch/lab/st/` and `internal-docs/self-training-lab-2026-10/plans/self-training-plan.md`
(that plan is superseded as the lab's direction by this note). Kept for the engine: MACULA, the alignments, the morph codec
(Kuni's spellout, when the Kuni rung comes), the S4 learner's counting (as a script that proposes rule candidates), and TBTA's
rule kinds as the checklist (its data is not used).

Code: `scratch/rules/` (private until the user decides). Log: `scratch/rules/RUN.md`.
