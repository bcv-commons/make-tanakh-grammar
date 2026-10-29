# Rules round 2 (en_bsb_r2): notes

Base: E6 trained on `nogospels`, with round 1's two engine changes (func_only renderings; `first` / `next_class` in the
context lexicon and in the rule format). Evidence from the test script's 1,500-verse train sample (s, Random(7)) and a
second disjoint 1,500-verse train sample (o, Random(11), my own queries; both training verses only). Dev = Mark 3, 9, 12.
Test chapters never read or queried. 19 rules kept (4 from round 1, 15 new); 7 test runs.

## The main finding

The engine change absorbed nearly everything round 1 asked for. Round 1's εἰμί / δεῖ / ἔχω / θέλημα / adverbial καί /
ἐάν rules no longer fire (the engine now writes is/are/am/was/must/will itself), and the four targets round 1 named for
`first` / `next_class` are already learned by the context lexicon:

- καί opening the verse: the engine writes "" (gold s: "" 54 / and 42 / then 32 of 164); no alternative wins.
- ὅτι opening the verse: the engine writes "for" (10/19, 13/23), already right.
- article + participle: the engine writes "who" before a verb; the gold splits "" / who / the one who / those who and
  no split by case, number or `first` beats it, except the verse-opening nominative ("he who", kept, small).
- οὐ before a non-verb: the engine writes "not" before prep/adj/noun/det and "" before verbs, already the majority.

So the gains left at this level are lexical and of two kinds: (1) English forms the engine generates wrongly (ἀνήρ
singular "men", ἄνθρωπος plural "man"/"mans", γυνή plural "womans", αἰών "forevers"); (2) a few fixed constructions
(μετὰ ταῦτα, διὰ τί, ὀνόματι, ἀπόστολος in letter openings, anarthrous κύριος). The rest needs new information
(capabilities below).

## Kept rules (train s: fires, right before → after; dev the same; from `rules.py test`)

| id | what | train | dev |
|---|---|---|---|
| theos-gen (r1) | θεός N-GSM, pre "" → pre "of" | 152, 32→85 | 8, 0→7 |
| oun (r1) | οὖν outside questions → "therefore" | 52, 5→17 | 0 |
| legon (r1) | λέγων V-PAP-NSM, pre "" → "" | 18, 1→8 | 3, 0→1 |
| hos-like (r1) | ὡς with subject → "like" | 22, 8→11 | 0 |
| kyrios-anarthrous | κύριος without article, dat/nom, pre "" → pre "the" | 29, 7→20 | 5, 1→3 |
| aner-sg | ἀνήρ N-NSM/ASM/GSM → head "man" | 27, 0→11 | 0 |
| aner-dat | ἀνήρ N-DSM → "husband" | 5, 0→3 | 0 |
| anthropos-pl | ἄνθρωπος plural → head "men" | 47, 3→16 | 3, 0→0 (form right) |
| gune-pl | γυνή plural → head "women" | 9, 0→5 | 0 |
| aion-gpm | αἰών N-GPM → "ever" | 10, 0→6 | 0 |
| onoma-named | ὄνομα N-DSN, first=clause → "named" | 8, 0→7 | 0 |
| be-1s-nosubj | εἰμί V-PAI-1S, no subject, no question → "i am" | 6, 0→4 | 0 |
| be-2-nosubj | εἰμί V-PAI-2P/2S, same → "you are" | 12, 0→8 | 3, 0→2 |
| apostolos-nsm | ἀπόστολος N-NSM → pre "an" | 7, 0→6 | 0 |
| art-nom-verse-ptc | det nom sg, first=verse, next_class=verb → "he who" | 4, 0→2 | 0 |
| kai-verse-pron | καί, first=verse, next_class=pron → "and" | 23, 6→12 | 1, 0→0 |
| meta-verse-pron | μετά, first=verse, next_class=pron → "after" | 5, 1→4 | 0 |
| hos-verb | ὡς, next_class=verb, no subject → "" | 9, 1→3 | 0 |
| dia-q-pron | διά in a question, next_class=pron → "why" | 6, 0→3 | 1, 0→0 |

The second sample agrees for every rule (the `evidence` field in the jsonl gives both samples' gold distributions).
Function-word counts ("pre right") go up or stay for every rule on train and dev. The small ones (aner-dat,
art-nom-verse-ptc, hos-verb, dia-q-pron, meta-verse-pron) break at most one right rendering each.

## Removed and dropped

Removed from round 1 (the engine change made them redundant):
- be-3s, be-3s-he, be-3p, be-3p-they, be-2, be-2-you, be-1p-we, be-1s, be-1s-i, be-impf-3s, kai-adv, dei, ean,
  thelema: 0 fires on train and dev (the engine's pre is now "is"/"am"/... or it renders the token itself).
- be-inf (33 fires, 10→10), echo-3s (8, 5→5), echo-pl (40, 15→15): fire but no gain; the engine already writes the same.
  With only the 4 kept round-1 rules dev chrF is 35.92, the same as with all 21.

Dropped this round:
- ginomai-aor3s (γίνομαι V-2ADI-3S, pre "" → ""): train s 1→5, o 1→13, but dev 1→0 and chrF 35.98 → 35.89. Same as round 1.
- art-nsf-clause (ὁ T-NSF, first=clause, next=noun → ""): o +9 but s only 20→22 of 38 fires; not clearly better.
- Not written (no group beats the engine on both samples): ἵνα next=verb ("to" 12 vs "so that" 10 in s, 10 vs 13 in o);
  aorist 3sg without subject by `first`/`next_class` (he vs "" splits both ways); αὐτός accusative by next class;
  nominative article before an adjective (s +9, o +1); noun without article → "a" (never the majority in any cell).

## Final dev measures (without → with the file)

```
word choice (content, stem): 0.5819 -> 0.5842
form (content, exact): 0.4926 -> 0.4948
rendering exact (all tokens): 0.4249 -> 0.4304
function words P: 0.5861 -> 0.587
function words R: 0.4805 -> 0.4882
order tau (mean per verse): 0.8727 -> 0.8732
chrF (summary): 35.82 -> 35.98
```

(Round 1's file on this engine: 35.82 → 35.92, rendering exact 0.4286, word choice 0.5819.)

## Missing capabilities (ranked by the dev differences they would address, results/diffs_dev.md)

1. **Subject continuity for verbs** (≈120 dev pre differences in the verb classes: "– → he", "he → –", "– → they were").
   Train shows no split by `first` or `next_class` either; the field needed is whether the subject is the one of the
   previous clause (participant ids).
2. **Pronoun referents** (≈110 in the pron classes: him → –, him → Jesus, his → –, who → whoever). Needs the referent
   and whether it was just named.
3. **Conjunction choice beyond position** (157 in conj: verse-opening καί "" / and / then; ἵνα "so that → to" 9;
   ὅτι "that → –" 12). καί needs the next verb's tense/mood or discourse break; ἵνα and ὅτι need the governing verb's
   lexical class (ask/command, say/know).
4. **Preposition object case and governing verb** (≈83 in prep: to → –, from → with, – → into). `next_class` did not
   help; μετά + accusative → "after" is only reachable through μετὰ ταῦτα.
5. **Definiteness of the article's head** (≈75 in det: the → –, – → the): whether the head is a proper name or a predicate.
6. **English morphology of irregular forms**: in 1,500 train verses ≈57 engine words are malformed (forevers 21,
   womans 20, mans 15, writtened 5, submited 4, tolded 3, forgivened 3, takened, shakened, seeked) plus "i written"
   (perfect without "have"). Four rules patch the nouns lemma by lemma; the verb forms need an irregular-form table in
   the generator.
7. **A previous-token field** (`prev_lemma` / `prev_class`): διὰ τί leaves τί as "what" after the dia-q-pron rule
   ("why what"); μετὰ ταῦτα and αὐτόν after a participle need it too. Small counts, but cheap.

## Next

Implement 6 (irregular English forms in the generator; would retire aner-sg, anthropos-pl, gune-pl, aion-gpm) and 7
(prev-token field), then the participant-based fields (1, 2), which address the largest share of the dev differences.
The context-only rule space over the current fields looks exhausted: the miner over lemma/class × first × next_class ×
subj/neg/q/art × pre finds nothing further that wins on both train samples.
