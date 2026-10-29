# Repo split: inventory (2026-10-29, read-only; nothing moved yet)

Three repos, three roles (agreed with the user 2026-10-29):

| repo | role | history | visibility |
|---|---|---|---|
| **bcv-commons/make-tanakh** | the stable toolkit (template) | its own | public |
| **make-tanakh-work** (now larsgson/bsb-add-books-work) | data only: projects, drafts, stores, alignments; a classical template copy | shared with the template | public |
| **make-tanakh-grammar** (new) | the cousin: rules-engine lab, grammar analysis, its publishing; the incubator where tools start | fresh | public (user 2026-10-29), screened: protected data stays local |

Dependencies run one way: grammar → make-tanakh (code, pinned submodule at a tag) and → the work repo's data (by path,
`MAKE_TANAKH_WORK`); make-tanakh never imports grammar; the work repo consumes grammar's results only as published,
pinned datasets (as with bcv-query's layout). A tool proven in grammar is promoted to the template in a delivery; grammar
then drops its copy.

## 1. Tracked tools that differ from the template

Measured against the merge base 0ba848a (the template is at 5121713). **Ours** = changed here since then, the files to
deliver; **theirs** = changed in the template since then, which come in with the merge (several on both sides: conflicts
to resolve at the merge).

### 1a. Ours → template (general, in use by the work repo's data or the site)

| change | files | why the template needs it |
|---|---|---|
| NT word alignment + the site's Greek clause view (greek-nt-clause-layout v0.5) | `scripts/align.py` (grc_scaffold), `bridge_align.py`, `full_align.py`, `clause_lines.py`, `build_site.py`, `build_grc_gntl.py` (new), `setup.py` (gntl step), `docs/website.md`, `CLAUDE.md` (command line) | the work repo's 27 Bern German NT `.align` files and the site's NT view depend on it |
| speaker layer v0.11 → v0.14 | `setup.py`, `src.py`, `participants.py`, `package.py`, `tests/test_package_pids.py`, `docs/sources.md` | `orig/heb.sqlite` is built on v0.14; the packages show it |
| alternations (forms differing in marks, their rules, review in the loop) | `alternations.py` (new), `tests/test_alternations.py` (new), `chapter_check.py`, `language_profile.py`, `lang.py` (raw_tokens), `docs/language-store.md`, `setup.py` (`--only gntl`), `docs/sources.md` | the Kuni store holds 98 `alt:` entries: the work repo's store fails validation without it |
| store format: hyphen prefix chains, word `parts`, affix `variants`, tone positions | `morphs.py`, `language_profile.py`, `docs/language-store.md`, `.claude/skills/audit-store/SKILL.md` | the Kuni and Zinza stores use these fields |
| `--src-chars` (reverse models) | `scripts/nllb/train.py` | small, general |
| clause-overlay proposal examples | `docs/proposals/clause-overlay/examples/` (4 new files) | belongs with the proposal already in the template's docs |
| rename strings (User-Agents, layer id `+auto+make-tanakh`, site name) | `donor.py`, `fetch_edition.py`, `fetch_heb_macula.py`, `export_usfm.py`, `macula_to_tf.py`, `lang.py`, `vrs.py`, `src.py`, `setup.py`, `full_align.py`, `bridge_align.py`, `build_site.py` | already the template's step 2: identical after the merge, nothing to deliver |

### 1b. Ours → grammar (experimental)

None of the tracked tools. Everything experimental already lives in `scratch/` (section 2).

### 1c. Dropped

None.

### 1d. Theirs (come in with the merge)

`grammar.py` (a Grambank answer's basis derived; rule and basis named), `tests/test_grammar_basis.py` (removed there),
`onboard.py`, `fetch_edition.py` (script per edition from the bibles catalogue), `docs/configuration.md`,
`docs/onboarding.md`, the rename (README, LICENSE, CLAUDE.md title). **Both sides:** `CLAUDE.md`, `build_site.py`,
`donor.py`, `export_usfm.py`, `fetch_edition.py`, `full_align.py`, `language_profile.py`, `macula_to_tf.py`,
`docs/language-store.md`.

## 2. The ignored folders: what goes where

**Grammar** = moves to make-tanakh-grammar (code, docs, small results; data rebuilt there, never committed).
**Work** = stays in the work repo's ignored `scratch/` (project runs, exchange records). **Archive** = parked strands: a
tar on the box, the code optionally under grammar's `archive/`. **Local only** = never into any repo.

| folder | size | where | note |
|---|---|---|---|
| `scratch/rules/` engine, rungs, Step A, reports, `RUN.md` | 283M (code and docs 1.8M) | **grammar** | eng_v10 current; eng_v0-v9 as tags or `archive/`; `data/*.db` and `dumps/` rebuilt, not committed |
| `scratch/rules/data/` corpora | most of the 283M | **local only** (rebuilt by `build*.py`) | hold BSB, KJV, Vamvas text and **HEBM95 (© Bible Society in Israel)** |
| `scratch/rules/hebm95/`, `r3/gap*hebm95*` | | **local only** | contain HEBM95 text |
| `scratch/rules/stepA/` | | **grammar**, screened | the scorers yes; result files quote Kuni words (NC-ND): the quotation rule decides, else local |
| `scratch/split/` conventions, publish_analysis, export_split, seg_bundle, source_modules | 5.7M (code 216K) | **grammar** | the language-analysis publishing; `out/`, `bundle/` are built (Zinza CC BY-SA, DFB CC0): rebuilt, not committed |
| `scratch/hf/language-analysis` | 25M | **grammar**, ignored there | the dataset's staging checkout |
| `scratch/kvg/spot/setup_*.py`, `scratch/eval/heldout_scrub.py` | | **grammar** (Step A test setup) | `heldout_scrub.py` is also on the template list (the unsent eval-2026-10-23 bundle) |
| `scratch/clause_spec/`, `scratch/morph/`, `scratch/zin/` (seeding, classes) | 367M, 503M, 92M | **archive**, code to grammar `archive/` | paused strands (layer A/A′/B/C, morph models, Zinza seeding) |
| `scratch/lab/` (self-training lab, NLLB queues) | 1.6G | **archive** | parked by the pivot; models stay in `~/models/nllb-finetuned/` (never deleted) |
| `scratch/kvg/` other (team page, store backups, jev, morph rebuild) | 230M | **work** | Kuni project work |
| `scratch/dan_run/`, `bern_run/`, `outbox/`, `incoming/`, `bibles-package/`, `pilot-clauses/`, `merge-backup-*`, `backup-*` | | **work** | runs and exchange records |
| `scratch/bhsa/`, `bcv-query-tools/`, `tf/` | 131M | **local only** | BHSA (CC BY-NC, never sent) |
| `scratch/tbta/` | 2.1M | **local only** | TBTA treated as non-free |
| `scratch/sil-src/`, `sil-study/` | 241M, 18M | **local only** / archive | SIL's code and our study of it |
| `internal-docs/rules-engine-lab.md`, `grammar-seeding-plan.md`, `research_notes/` (clause-level spec research), `self-training-lab-2026-10/` | | **grammar** (the last as `archive/`) | |
| `internal-docs/` rest (handover, letters, netlify plan, clause-packages plan, onboarding-by-kind, SIL study, Scripture Forge feedback, divergence list) | | **work** | `divergence-from-template.md` is replaced by grammar's promotion log after the merge |
| `local_output/` | 1G | **work**, local only | non-free derived work (Kuni, Zinza, Bern German) |

## 3. What grammar's code needs from make-tanakh

Imports found in the lab code: `full_align` (18), `langtools` (22), `vrs` (14), `morphs` (8), `lang` (5), `ot_routes`,
`model_text`, `judge`; data paths `orig/heb.sqlite`, `orig/grc.sqlite`, the projects' `.align` files and stores. So:
`vendor/make-tanakh` (submodule, pinned tag) on the path for the code; `MAKE_TANAKH_WORK` for `orig/` and `export/`.
A contract test reads one chapter of each format (`.align`, store, `orig/*.sqlite` schema) and fails when a pinned
update changes one. Each result line records the make-tanakh commit and the engine version.

## 4. The relationship documents (one in each repo, same structure)

The user's ask (2026-10-29): each repo describes how the three relate. One shared outline, each copy written from its
own side, cross-linked:

1. **The three repos** — the table above, the same in all three.
2. **This repo's role** — what belongs here and what doesn't.
3. **What it takes from the others** — and how it is pinned (template merge, submodule tag, dataset version, path).
4. **What it gives the others** — and in what form (template tags, `.align`/stores as data, HF datasets).
5. **How a change travels** — the promotion path (grammar → template delivery → work merge); who decides (the user commits).
6. **Licences and what never moves** — non-free texts local, BHSA never, quotation limits; per repo.
7. **Version records** — where the pins are written (template merge commit; `vendor/make-tanakh`; `MANIFEST` of
   datasets) and the contract test.

| repo | document | also |
|---|---|---|
| make-tanakh | `docs/related-repos.md` | linked from README; says how a work copy and a grammar cousin use it (tags, formats it promises to keep: `docs/language-store.md`, `docs/clause-sidecar.md`, the `.align` format) |
| make-tanakh-work | `RELATIONS.md` (or `docs/related-repos.md`, the template's, plus a short local section) | `CLAUDE.md`'s "tools come from the template" rule |
| make-tanakh-grammar | `RELATIONS.md` + `PROMOTIONS.md` (the promotion log) | `CLAUDE.md` with its binding rules; `vendor/make-tanakh` pin |

## 5. Order of work (each step for the user's go)

1. Create make-tanakh-grammar (private), move section 2's "grammar" items, write its `RELATIONS.md`, `CLAUDE.md`, the
   submodule and the contract test; check the engine reproduces eng_v10's figures from there.
2. The template delivery: section 1a, plus `docs/related-repos.md` for the template.
3. Merge template/main into the work repo; `git diff template/main -- scripts docs .claude` empty; its `RELATIONS.md`.
4. Rename the work repo and the folder (copy the Claude memory folder to the new path's name).
