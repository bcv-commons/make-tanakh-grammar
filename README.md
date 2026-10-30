# make-tanakh-grammar

The grammar side of the make-tanakh family: a rules engine that learns, language by language, how the Hebrew and Greek
source grammar is rendered in a target language, measured component by component; the language analysis we publish
(bcv-commons/language-analysis on Hugging Face); and the place where new tools start before they go to the template.

It is a cousin of [make-tanakh](https://github.com/bcv-commons/make-tanakh) (this repo: bcv-commons/make-tanakh-grammar), not a copy of it: its own history and
releases. How the three repos relate: [RELATIONS.md](RELATIONS.md).

    . ./env.sh                        # MAKE_TANAKH_WORK = a make-tanakh work copy with sources and projects,
                                      # MAKE_TANAKH_PRIVATE = where corpora and run outputs go (default ./private),
                                      # BCV_COMMONS = the bcv-commons checkouts (bcv-query, lexeme-aligner)
    cd lab/rules && python3 danish/run.py      # e.g. rung 4 (needs its corpus first: danish/build_ot.py)

| folder | what |
|---|---|
| `lab/rules/` | the engine (`eng_v10` current; `eng_v0`-`eng_v9`, `engine` earlier versions), rungs (`r3`, `danish`, `kjv`, `hebm95`, ...), Step A (`stepA`), reports and `RUN.md` (the log) |
| `lab/rules/data/` | corpus builders, and the function-word lists derived from free alignments; the corpora are built into `$MAKE_TANAKH_PRIVATE/rules/data/` |
| `tools/` | `screen.py`, the pre-commit screening (below) |
| `lab/split/` | the language analysis: conventions modules, segmenter bundle, split files, `publish_analysis.py` (the HF dataset) |
| `lab/contract/` | the contract test: one chapter of each format the lab reads from the work repo, as schemas, counts and hashes; `check.py` fails when a toolkit update changes a format |
| `lab/heldout/` | held-out test setup (edition copy, store scrub) for Step A |
| `docs/` | the lab plan, research notes, the split inventory; `learning-to-speak.md`, how the tools fit around an LLM drafter (start here) |

## What you can reproduce

The lab needs the Python standard library, sacrebleu for chrF, and a work copy of make-tanakh with its sources
(`orig/grc.sqlite`, `orig/heb.sqlite`, built by the toolkit) as `MAKE_TANAKH_WORK`. Each rung builds its corpus first; the
builders write to `$MAKE_TANAKH_PRIVATE/rules/data/`, the runs write their outputs below `$MAKE_TANAKH_PRIVATE/rules/`.

| rung | source -> target | corpus builder | inputs |
|---|---|---|---|
| 1, 1b | Greek, Hebrew -> English (BSB) | `data/build.py`, `data/build_ot.py`; `data/build_la.py` on lexeme-aligner's BSB layer | the BSB's own alignment tables in the work copy's sources (public domain; MACULA CC BY 4.0) |
| 1c | Greek, Hebrew -> English (KJV) | `kjv/build_nt.py`, `kjv/build_ot.py` (download the text) | KJV (public domain outside the UK), lexeme-aligner's layers |
| 2h | Greek NT -> Hebrew (Salkinson-Ginsburg) | `hebnt/build.py` | bcv-commons/alignments-by-id (CC0), the text public domain |
| 3 | Hebrew -> Greek (Vamvas) | `vamvas/build_ot.py` | bcv-commons/full-alignments-llm, Vamvas layer (CC0) |
| 4 | Hebrew -> Danish (our drafts) | `danish/build_ot.py` | the work repo's Danish drafts and their `.align` (CC0) |

Paths are relative to `lab/rules/`. Reports name the engine version (`eng_v10`) and the work repo's commit.

**Only on the maintainers' machine** (the texts are not free; their code is here, their data and results are not):
rung 2 (Greek NT -> Modern Hebrew, HEBM95, © Bible Society in Israel) and Step A on Kuni (`lab/rules/stepA/`; the Kuni
text is CC BY-NC-ND, our drafts' words stay with it). Their reports keep figures and method only. TBTA and BHSA data
are consulted, never stored here.

## What is committed, and the screening

`.gitignore` is an allowlist: code (`*.py`, `*.sh`), docs and reports (`*.md`), the licences and a few derived lists are
admitted; anything else stays local until it is admitted on purpose. `private/` (`MAKE_TANAKH_PRIVATE`) is never
tracked. Before each commit `tools/screen.py` (the hook in `.githooks/`; enable it once per clone with
`git config core.hooksPath .githooks`) refuses a file that holds a corpus or binary, Hebrew-script text beyond a few
words that is not the WLC, Kuni word forms, TBTA or BHSA data. `python3 tools/screen.py --all` screens the whole tree.
Without the protected texts on your machine the Kuni and TBTA checks are skipped (you have nothing of them to leak),
and the Hebrew check is strict.

Licences: code MIT (`LICENSE`), docs CC0 (`LICENSE-docs`). No Bible text is committed here.
