# How the three repos relate

## 1. The three repos

| repo | role | history | visibility |
|---|---|---|---|
| **bcv-commons/make-tanakh** | the stable toolkit (template): scripts, formats, docs, skills | its own | public |
| **make-tanakh-work** (larsgson/make-tanakh-work, until 2026-10-29 bsb-add-books-work) | data: projects, drafts, language stores, alignments, the site; a classical template copy | shared with make-tanakh | public |
| **bcv-commons/make-tanakh-grammar** (this repo) | the rules-engine lab, grammar analysis and its publishing; where tools start | its own | public repo; push only what is screened (section 6) |

Dependencies run one way: this repo uses make-tanakh's code and formats and reads the work repo's data; make-tanakh
never imports this repo; the work repo uses this repo's results only as published, pinned datasets.

## 2. This repo's role

In: the engine and its measurements, the analysis we publish, experimental tools. Out: drafts, stores, project data
(work repo); stable tools (template); any Bible text or anything built from one (corpora are rebuilt locally).

## 3. What it takes from the others

- **Code from make-tanakh** (`full_align`, `langtools`, `vrs`, `morphs`, `lang`, ...). For now it is imported from the
  work repo's `scripts/` (`env.sh` sets `PYTHONPATH`): until the work repo's tools equal the template's again (the
  reconciliation, step 3 of the split), only that copy has what the projects' data need. Afterwards: make-tanakh as a
  submodule at a tag, once the toolkit takes its data root from a setting (it now derives it from its own path).
- **Data from the work repo, by path** (`MAKE_TANAKH_WORK`): `orig/heb.sqlite`, `orig/grc.sqlite`, the projects'
  `.align` files and stores, `reference/`, `import/` (non-free editions only as local inputs, never copied here).
- **Datasets from bcv-commons**, as pinned in the work repo (hebrew-clause-layout, speaker layer, greek-nt-clause-layout,
  compact-alignments, lexeme-aligner's layers).

## 4. What it gives the others

- **bcv-commons/language-analysis** (Hugging Face): stores, conventions modules, segmenter bundles per language and
  version (`lab/split/publish_analysis.py`); lexeme-aligner pins its versions. Pushes need the user's go.
- **Tools for the template**, when proven (section 5).
- Later, the engine's results as a dataset the drafting tools may pin as data.

## 5. How a change travels

A tool starts here; when it is measured and general it goes to make-tanakh as one delivery (patches, a VERIFY file);
the template implements it its own way; the work repo merges `template/main`; this repo drops its copy and records the
move in [PROMOTIONS.md](PROMOTIONS.md). A data change (a store entry, an alignment) is made in the work repo. The user
commits and pushes in every repo.

## 6. Licences and what never moves

Code MIT, docs CC0 here and in make-tanakh; the work repo's drafts CC0. Never in this repo: Bible texts (BSB, Vamvas, KJV
corpora are rebuilt; HEBM95 © Bible Society in Israel and the Kuni text (NC-ND) stay on the box), BHSA data (CC BY-NC),
TBTA data. Reports quote within `docs/licensing.md`'s limits (short, credited).

## 7. Version records

- Each result names the engine version (`eng_v10`) and the work repo's commit (its toolkit and data); after the
  reconciliation, the make-tanakh tag.
- The datasets this repo publishes carry their version in their manifest.
- A contract test (to come) reads one chapter of each format the lab uses and fails when a toolkit update changes one.
