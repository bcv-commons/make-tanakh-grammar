# Engine-gap detectors and agent-free rounds, calibrated against linguist rounds 1-2 (2026-10-26)

Code `auto/auto.py`, driver `auto/run_all.sh`; per version `results/auto/v{0,1,2}.md/.json`, rule tests `results/auto/ruletests.txt`.
Engines frozen as `eng_v0` (before round 1), `eng_v1` (after round 1's engine change: function-word-only renderings, `first`,
`next_class`), `eng_v2` (after round 2's: corpus-checked forms, `prev_class`, `prev_lemma`). Samples A (the agents' 1,500
training verses) and B (1,500 other training verses); dev for the rule tests; the test chapters are not read. No LLM.

## Did the detectors find what the agents found?

| agents' finding | detector | v0 | v1 | v2 | verdict |
|---|---|---|---|---|---|
| r1: lemmas rendered with function words only (εἰμί, δεῖ, ἔχω, θέλημα) | D1 "verb/noun: function words only" | **7 lemmas, 263 tokens on A (top flag)** | 1 lemma, 15 | 1, 15 | found; disappears after the fix |
| r2: invented forms ("writtened", "womans") | D4 words the training BSB lacks | 8.1 per 1000 | 7.9 | **0.4** | found; the fix confirmed |
| r1: opening position (καί), next word's class | D3 tree fields, conj / prep / det | conj +74 B tokens (node.rule, pos.verse), prep +47 (next.gcase, next.class), det +122 (nhead.lemma) | conj +36, prep +2, det +72 | conj +7, prep +2, det +20 | found; shrink as the fields are added |
| r2: article's noun definite / proper | D3 det | nhead.lemma | nhead.lemma | next.type, nhead.type (+20) | found, small |
| r1/r2: preposition's object case | D3 prep | next.gcase (+47) | gone | gone | found on v0, then covered by next_class |
| r1/r2 top item: subject continuity (~120 dev differences) | D3 verb (pcverb.*, pcl.same_pn, pcl.subj) | +13 | +6 | +2 | **missed** |
| r1/r2 second item: pronoun referents (~110) | D3 pron | +82 (node.rule, nhead) | +34 | +2 | **missed** (what it finds is not the referent) |

New, not named by the agents: D1 on v2 flags "other: function words only" over 13 lemmas, 225 tokens: pronouns and articles
after a preposition (σύ genitive after a preposition → "you", αὐτός → "him", ὁ after a preposition with pre "of the" → "the").
The preposition and its object both supply the English function word: a placement gap between them, an engine question.

## Agent-free rule rounds against the agents' rounds (dev, same test script)

| engine | file | rules | rendering exact | function words R | chrF |
|---|---|---|---|---|---|
| v0 | auto | 27 | 0.4003 → 0.4135 | 0.475 → 0.493 | 35.58 → 35.59 |
| v0 | agent r1 | 21 | 0.4003 → 0.4144 | 0.475 → 0.497 | 35.58 → 35.96 |
| v1 | auto | 30 | 0.4249 → 0.4336 | 0.481 → 0.492 | 35.82 → 36.12 |
| v2 | auto | 30 | 0.4249 → 0.4418 | 0.481 → 0.487 | 35.80 → 35.83 |
| v2 | agent r2 | 19 | 0.4249 → 0.4304 | 0.481 → 0.488 | 35.80 → 35.95 |

The search matches or beats the agents on token-level measures (v2: exact +0.017 against +0.006); chrF moves are within the
dev noise of 127 verses (±0.2) and point both ways. On rules in this format, the agents added little that a search does not find.

## What this means for an agent-free setup

1. **Rules: a script will do.** The search in the agents' format reaches what the agents reached.
2. **Gaps the engine's design cannot express at all** (a shape no rule can make: D1) **and invented forms (D4) are detected
   reliably** and their fixes confirmed.
3. **Gaps one tree hop away are detected** (opening position, neighbour class, head noun, object case: D3), and they shrink as
   fields are added: the detector also says when a gap is closed.
4. **The blind spot is discourse:** subject continuity and pronoun referents, the agents' two top items, are not visible to
   single tree fields, even from the previous clause. Without a linguist they would go unseen. They need participant ids
   (who is who across clauses) as a source layer first; then the same D3 test can measure them. That is the next build step,
   and the detector's miss is the argument for it.
