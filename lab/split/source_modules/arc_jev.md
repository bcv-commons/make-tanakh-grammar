# arc: source rules for an aligner

Short form of `module.md` (same ids; the whole rule is there). Written by an LLM (Claude), not measured. The `hbo` rules hold
where nothing here differs. A target module's line overrides a rule here.

**The unit is the clause** (or 2–3 clauses of one sentence), from bcv-commons' clause layouts (`CLAUSES.md` in the
language-analysis dataset). "In the clause" means the request's clauses; the verse is not a unit.

- `arc.01` Emphatic state (־אָ, מַלְכָּא "the king") is the article: the target's article → the emphatic ending (or the noun); else none.
- `arc.02` דִּי → the target's relative marker, "of", or connective, by its use in the clause.
- `arc.03` לְ marking a definite object: none, or the target's object marker.
- `arc.04` Participle as present or continuous: tense/aspect marker → the participle; auxiliary → הֲוָה.
- `arc.05` אִיתַי / לָא אִיתַי → the target's existential word, and its negative.
- `arc.06` Persian official titles: one target term per Aramaic word.
