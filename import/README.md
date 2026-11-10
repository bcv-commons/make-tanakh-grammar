# import/: existing editions, filed by licence

Every text this repository learns from is an *edition*: one existing translation (a whole Bible, a New Testament, or
single books) in one folder, `import/<licence>/<language>/<edition>/`. The layout is make-tanakh's
(`import/README.md` there), so an edition folder can be copied between the two repositories.

    import/
      _template/edition.yaml          start a new edition from this
      CC0  CC-BY  CC-BY-SA            open editions
      CC-NC  CC-ND  non-free          editions that may not be published
        <iso>/                        one folder per language, by its ISO 639-3 code
          <edition>/
            edition.yaml              what the edition is, where it came from, its licence and credit line
            README.md                 optional: how the text was received or built
            text/                     the text (never in git)
            source/                   optional: the files as received, e.g. Paratext SFM (never in git)

## The licence folders

| folder | for | what follows here |
|---|---|---|
| `CC0` | public domain and CC0 editions | nothing required; credited as a courtesy |
| `CC-BY` | CC BY | its credit line wherever it is quoted |
| `CC-BY-SA` | CC BY-SA | its credit line; what holds its text is share-alike |
| `CC-NC` | CC licences with NC and without ND | the text and what holds it stay on this box |
| `CC-ND` | any CC licence with ND (an NC-ND edition goes here: ND wins) | the text and what holds it stay on this box |
| `non-free` | everything else: all rights reserved, unclear, permission for private use only | the text and what holds it stay on this box |

- **When in doubt, `non-free`.** An edition moves to an open folder only with its licence checked and recorded in
  `edition.yaml` (`source`, `licence`, and for CC BY and CC BY-SA `attribution`).
- **No text is in git, in any folder.** This repository is public and holds no Bible text (stricter than make-tanakh,
  which keeps hand-copied open texts). Tracked are only `edition.yaml`, a `README.md` and our own build scripts
  (`*.py`); `.gitignore` leaves every subfolder of an edition out. Keep the tracked files free of the text itself, of
  word forms of a protected text, and of private details: the pre-commit screen reads them.
- **The folder states the licence; it does not decide what may be sent where.** Whether a text may be shown to the
  drafting model or sent to Jev is the user's decision per language, in the rights table of the language's
  configuration (`shared/rights.py`). The drafts are CC0 and published unless the configuration holds them back
  (`"publishing": {"hold": ...}`, `publish/push.py`).
- **Edition ids are unique** across the folders.

## Which editions belong here

- **The target language's** text: the team's translation the drafts are modelled on.
- **A related language's** text and **the regional language's** text, when the preparation of a target language uses
  them. Each is an edition of its own language, under that language's code. Which language serves which target, and
  in what role, is recorded with the target (its identity record), not in the edition.

A dialect without an ISO 639-3 code of its own gets an interim folder name; the precise language tag goes into
`edition.yaml` (`language:`).

## Bringing an edition in

1. Copy `_template/` to `import/<licence>/<iso>/<edition-id>/` and fill in `edition.yaml`.
2. Put the text in `text/`, in one of the forms the first stage reads (`onboard/align.py`): make-tanakh's chapter
   files (`<book>NNN.txt`), or anything lexeme-aligner reads (USFM, USJ, a vref corpus, one verse per line). Files as
   received (Paratext SFM, a zip) go in `source/`, with a line in `README.md` on how `text/` was made from them.
3. Name it in the language's configuration as the text's `path`: a path that starts with `$IMPORT` (this folder;
   `MAKE_TANAKH_IMPORT`, default `./import`), then the licence folder, the language and the edition, then `text`.

Nothing here fetches a text yet. An edition that exists in make-tanakh's work copy is copied over with its folder; a
text from a Bible source is fetched there (`scripts/fetch_edition.py`) or with lexeme-aligner.

## The editions on this box

| edition | folder | language | licence | text |
|---|---|---|---|---|
| `zin_wbt` | `CC-BY-SA`, `zin` | Zinza (Bantu, Tanzania), New Testament | CC BY-SA 4.0 | fetched in make-tanakh from helloAO; pinned by `fetch.lock.json` |
| `KVG-KuNT` | `non-free`, `kvg` | Kuni (Kuni-Boazi, Papua New Guinea), New Testament, Genesis 1-30, Ruth, Jonah | CC BY-NC-ND 4.0 as published; the newer working copy for private use only | the team's Paratext files in `source/`, chapter files in `text/` |
