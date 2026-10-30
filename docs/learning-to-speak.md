# Learning to speak: how the tools fit around an LLM drafter

A picture for new users of the tools that come out of this lab, and the lab results behind it. The figures are from the bridge
reports of 2026-10-29 and 2026-10-30 (`lab/rules/REPORT-bridge-2026-10-29.md`, `lab/rules/REPORT-bridge2-2026-10-30.md`).

## The picture

An LLM drafting a translation is like a child learning to speak. The child learns from hearing the language used, a great deal
of it. A grammar teacher explaining the rules does not make the child speak better.

The picture fits the drafting side well. It fits the rest of the work less well. The grammar teacher does not help the child
speak. The editor checking the child's essay still needs the grammar.

So the tools fall into two groups:

- **Exposure, for the drafter.** Real text of the target language, chosen so that it says something close to what is being
  drafted.
- **Grammar, for the people and tools around the drafter.** Alignment, review, retrieval, measurement and consistency checks.

## What the results say

Everything that tried to teach the LLM in its prompt did nothing. That covers engine drafts, glosses, rule-based examples,
lexicons and checker-guided repair. One combination, examples and lexicon together, even hurt.

The one thing that helped was exposure: the team's own NT clause that says something similar, placed beside each Hebrew
clause. That is a child hearing a sentence used in context, not a teacher explaining a rule. It helps most where the LLM has
heard the language least.

| language | chrF gain from the retrieved NT clause | over |
|---|---|---|
| Kuni | +4.15 [3.31, 5.02] | 5 paired runs, 70 verses |
| Danish | +0.93 [0.53, 1.32] | 5 paired runs, 364 verses |

On Kuni the gain lies in word choice, forms and function words. Word order does not change.

Refining the exposure did not help. Retrieval weights tuned on a dev set were worse than the untuned ones on Danish. Two
retrieved clauses per Hebrew clause were no better than one. One good example per clause is the working setting.

For drafting, then, the picture holds. The LLM has already absorbed grammar from vast exposure. Where it lacks exposure, more
real text helps, and explained grammar does not.

## Where the grammar analysis earns its place

The analysis is not wasted. It works for the people and tools around the drafter, not inside the prompt.

- **Alignment.** The Jev module built from our conventions goes into every Kuni and Zinza alignment request. It lists the
  affixes, the words never divided and the team's decisions. Our segmenter splits words into parts for the parts route, and
  lexeme-aligner built the whole Zinza NT layer that way. Alignment is the shared asset that everything else stands on.
- **Review.** A draft aligned twice flags Hebrew words that the draft left out. The flags are right 62 to 68 percent of the
  time, and twice as often as the engine's own tables. Links that two alignment runs agree on are right three times as often as
  links only one run makes. That is a tool for the team's reviewers, and it rests on the alignment above.
- **Retrieval.** The clause index uses the analysed clause layouts and the grammar bridge to find the NT clause that helped.
- **Measurement.** The rules engine splits a score into word choice, form, function words and order. That is how we know the
  retrieval gain lies in words and forms, and not in order. The engine is the fixed instrument; the LLM is what is measured.
- **Consistency.** The team's decisions on terms and names are stored as rules and checked against drafts.

## The bridge: why Danish shows little gain

The bridge links Hebrew words to the Greek words the Septuagint uses for them. Through it, a team's NT tells the tools how the
team renders a Hebrew word, even where no OT exists yet. It stands in for missing Old Testament data. Danish has a whole aligned
Old Testament, so there is little gap to fill.

| case | gain from the bridge |
|---|---|
| Danish engine, 5% of the OT | +2.0 chrF |
| Danish engine, the whole OT | +0.56 |
| Danish, the reserved final set | +0.035 |
| Kuni engine, 5% of Genesis | +7.4 |
| Kuni engine, all its OT | +3.4 |
| Danish LLM with a retrieved clause | +0.93 |

The full-data Danish case was always the workbench for testing the method, not the target. The target is a language with a full
NT and little or no OT, like Kuni or Zinza. A Danish team starting the OT from nothing would see the low-data gain. With the
bridge, the Kuni engine reaches its full level from about one and a half chapters of Genesis.

lexeme-aligner measured the same bridge in its aligner, for editions with a thin OT. It gave 1.4 to 5.3 points of alignment F1
across English, Spanish, Hindi and Arabic. So the bridge is in use wherever the OT is thin.

## What this means for the tools

The working loop the lab points to:

1. Retrieve, for each Hebrew clause, the team's NT clause that says something similar, through the bridge.
2. The LLM drafts the clause with that example beside it.
3. The draft is aligned twice, and the Hebrew words it left out become firm or soft review flags.
4. The team reviews and decides.
5. Approved text joins the pool, and the next chapter's retrieval and alignment draw on it.

The rules engine stays in reserve. It is the drafter for languages too thin for the LLM, and the yardstick for every change to
the loop.

Two things this lab does not settle:

- **What reviewers do with the flags.** Whether firm and soft flags save the team time can only be learned with a team.
- **Languages the LLM has barely heard.** Kuni gains most from exposure, but it still starts from the LLM's general knowledge.
  For a language with less presence, the engine's place in drafting may grow. Zinza is the next test.
