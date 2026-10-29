# Grammar seeding: a donor language's grammar as the store's starting point (plan, 2026-10-22; scope cut 2026-10-22)

Private planning note (the box). Meant for the template's setup wizard eventually; the first evidence comes from a Zinza
pilot the template session runs on request (`scratch/outbox/to-template-zinza-grammar-seed.md`, the shortened version).
Kuni is left out: no related language the model knows.

## The idea

NLLB starts a new language from a related one (`zin_Latn` begins as a copy of Luganda's `lug_Latn` vector; fine-tuning moves
it away). The grammar starts the same way: what the model already knows about the donor goes into the store as
**hypotheses**, marked `seed` and non-binding. The setup only plants them. The normal work afterwards (memory agent, drafting
agents, our scripts) confirms, corrects or refutes them, chapter by chapter.

| | NLLB | grammar |
|---|---|---|
| seed | the donor's label vector, copied | the donor's grammar from the model's memory, as `seed` store entries |
| refinement | fine-tuning on the verses | agents meeting the category in a chapter; `morphs.py try` and rates on the corpus |
| result | the vector drifts from the donor | `observed` (Zinza form, figures) / `contradicted` (kept) / still `seed` |
| fading | the donor matters less each step | a seed leaves the packs once observed entries cover its category |

## The setup step (about ten minutes of agent time)

- **The donor decision** in `project.yaml`: `donor: {known: lug, structure: [haya, nyambo, kerewe], nllb_init: lug_Latn,
  why}`. `known` = the closest relative the model knows well (the probe may decide); `structure` = closest by Glottolog. One
  decision serves NLLB and the grammar.
- **One seed agent, from memory only**, blind to any Zinza analysis, no corpus pass, no NLLB: writes the donor's grammar as
  store entries: the verb template as a `template:` block (slot order) plus one morph entry per slot filler; noun classes
  with augment and the locatives 16/17/18; concords; negation, copula, relatives, the quotative, *na*, word order, tone.
- **Per entry**: `status: seed`, `method: donor:lug`, `donor_form`, `donor_note`, a plain-words `test` (which source feature,
  which position to look at), a Grambank id where one fits. The value stays the donor's form until something observes the
  Zinza one. Three optional fields; everything else is the store as it is, so the tools read it unchanged.
- **Seeds are harmless from the first minute**: the validator accepts the status, the check never enforces a seed, the pack
  prints one only where its category occurs ("unconfirmed, from Luganda; check"), `check_project` counts the untested ones.

## What is deferred, and picks up by itself

- The Zinza reading of each seed: done by whichever agent meets the category first; the pack points it there.
- Corpus confirmation (`morphs.py try`, rates): our scripts, whenever we like.
- The wiki page: generated once entries are observed.
- No donor (Kuni): seed from area/family typology (Grambank/WALS), weaker, same lifecycle.

## Risks and safeguards

- **Donor bias**: a seed is confirmed by a test or by corpus evidence, never by an agent's reading alone. Seen in Zinza:
  `omu+` stored as class 1/3 only; the locative *omu* "in" (class 18, a word of its own, 4,495×) went unseen. Safeguard: a
  whole word identical to a seeded prefix is flagged for a second reading.
- **False friends**: donor forms are examples; Zinza forms enter only through observation.
- **Forgotten seeds**: the untested count in `check_project` keeps them visible.

## Evaluation (the Zinza pilot)

Compare on the same spot corpus (Philippians held out): **U** = our unseeded run (`local_output/zin/spot_A`: 50 morphs,
negation 26% → 56%, the *omu* locative missed); **S** = the seeded store after a memory agent; the Mac's blind test (37
morphs). Measures: seeds observed / contradicted / untested; confirmed morphs and their odds; negation, person, tense rates;
parts-split coverage; categories one run found and the other missed (locatives, applicative, connective, augment, copula);
cost. Then our tools on S: zin-m rebuild, the morph pack and its check on the human Philippians, the alignment by parts.

## Next after the pilot

If S beats U: the wizard step, the seed prompt and the status go into the template (the user decides when), and the donor
block drives NLLB's init too. Separately: Luganda vs Swahili as NLLB start (one 5-hour run).

## Clause frames and the self-learning loop (discussed 2026-10-22; implementation on hold, the user's decision)

*In short: predict a grammatical frame per source clause, let the agent draft in parts, read the frame back, log the differences, re-learn the rules.*

### Unit: the clause, not the verse

Concord, negation scope, order, tense/mood by clause type and the quotative are clause properties; the verse is only a
reference label.

### Unkeyed frames

Each source clause (MACULA: type, roles, verb features, negation) gets a frame in the *target's* slots, with
target grammatical values and source lexemes only as placeholders (no stem chosen, so no ready answer):

```
PHP 1:3a  main, statement
  V   { SC:1s=n-   TAM:PRS=ni-   STEM:<εὐχαριστέω>   FV:-a }
  O   { <θεός> cl9?   POSS:1s=-anje }
  LOC { aha  <μνεία>  POSS:2p }
```

Slot tables learned by script from the corpus aligned by parts (bridges + confirmed morphs):

- TAM, NEG,
- SC (person, or the subject noun's class), OC,
- EXT (applicative for a dative/ὑπέρ), FV,
- prepositions/locatives, connective, order,
- and noun class per source lemma.

Measured slot by slot on held-out human chapters (Zinza: Philippians) before any agent.

### The loop

```
source clause → frame predicted (script) → agent drafts the clause in parts tagged with source token numbers
 → realized frame read off the draft (script; the step-7 check) → per-slot differences logged (script; the agent adds only a
 reason code) → slot tables re-learned with the new conditions (script) → better frame for the next clause
```

Log line (append-only, codes only):

`GEN24:8b  V.NEG  pred=ti-  got=ta-  why=SC3s  src=agent:r2  feat=FUT.2s.cond.neg`

Learner: counts with back-off and a decision list per slot (transparent; each rule traceable to its log lines); recurring
rules become store `claim`s with the log lines as evidence.

### Safeguards against learning its own mistakes

- Evidence weighted by source (team > human corpus > confirmed agent decision > agent decision).
- No promotion on agent evidence alone (needs corpus odds, team confirmation, or recurrence across independent agents
  without check objections).
- After each learning round the held-out human chapters are re-scored slot by slot, and a round that lowers accuracy is
  rolled back (the learning curve).

### Hebrew for a language without an OT (Zinza)

- Start from the NT tables carried over through the shared feature set and the LXX bridge.
- Hebrew-only constructions (wayyiqtol chains, infinitive absolute, oaths, hinneh) are learned from agent decisions
  and team review only, so the safeguards matter most there.
- Kuni, with human OT chapters, is the test bed for the loop.

### Order when resumed

1. frame generator + slot tables (Zinza)
2. → realized-frame reader and difference log (tested on the human Philippians as if it were a draft)
3. → learner with weights, promotion and rollback
4. → Kuni with Hebrew.

No LLM needed until drafting is green-lit.

### Next decision (open)

A universal formal specification from the source grammar (Hebrew, Greek) to any target language, per clause: see the
section below once decided.
