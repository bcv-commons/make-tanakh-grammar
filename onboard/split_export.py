#!/usr/bin/env python3
"""A team's text as a split file (bcv-split/0.1): every word of every verse with the parts the language's segmenter gives it.

Run by onboard/align.py with the aligner's own Python, from the aligner's checkout (it uses the aligner's tokeniser and text
fingerprints, so that the split file and the alignment layers name the same tokens):

    <aligner>/.venv/bin/python -I onboard/split_export.py BUNDLE OUT EDITION USJ_DIR SOURCE_NOTE LICENCE_NOTE

BUNDLE is a segmenter bundle of the language-analysis dataset (seg_facts.json, morphs.py, bcv_segment.py). Rules:
- a word's parts are the segmenter's, in its order and numbering (part = list index); their texts are cut out of the written
  word, so case and spelling stay as written; a word the segmenter does not divide, or whose parts do not rebuild it, is one
  row with slot `whole`;
- a grammatical tone the segmenter takes off is a `tone` part without text ("<position>:<mark>", position counted in letter
  clusters from the word's end);
- a hyphen word is split joined, each piece numbered from 0; an affix written with a hyphen is a token of its own
  (`written: hyphen`, `host` = the offset of its host token).
The file holds the text's words: it goes where the text may go."""
import hashlib, json, re, sys, unicodedata
from collections import Counter
from datetime import date
from pathlib import Path

BUNDLE, OUT, TAG, USJ, SOURCE, LICENCE = sys.argv[1], Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4]), sys.argv[5], sys.argv[6]
sys.path[:0] = ["pipeline", "pipeline/vendor/bibles", BUNDLE]
import bcv_segment, bcv_written  # noqa: E402
import pyarrow as pa, pyarrow.parquet as pq  # noqa: E402
from lexeme_aligner import usj_source  # noqa: E402
from lexeme_aligner.text_fingerprint import usj_verses, book_file_hash  # noqa: E402

seg = bcv_segment.load(BUNDLE)
nfc = lambda s: unicodedata.normalize("NFC", s)


def clusters(s):
    """NFD base-letter clusters: [start, end] of each letter plus the combining marks after it"""
    out = []
    for k, c in enumerate(s):
        if unicodedata.combining(c) and out:
            out[-1][1] = k + 1
        else:
            out.append([k, k + 1])
    return out


def parts_of(word):
    """[(slot, text, form, position, chain_id, tone)] in the segmenter's order, or None (keep the word whole)"""
    ms = seg.S.split(word, tones=True)
    if len(ms) < 2:
        return None
    d = unicodedata.normalize("NFD", nfc(word)); cl = clusters(d); drop, tone_of = set(), {}
    for k, m in enumerate(ms):
        if m.slot != "tone":
            continue
        entries = []
        for item in m.text.split():
            pos, _, code = item.partition(":")
            mark = "".join(chr(int(h, 16)) for h in re.findall(r"U\+([0-9A-Fa-f]{4,6})", code)) or code; pos = int(pos)
            if not 0 <= pos < len(cl):
                return None
            a, b = cl[pos]; at = d.find(mark, a, b)
            if at < 0:
                return None
            drop.update(range(at, at + len(mark))); entries.append(f"{len(cl) - pos}:{mark}")
        tone_of[k] = entries
    base = nfc("".join(c for k, c in enumerate(d) if k not in drop))
    if "".join(nfc(m.text) for m in ms if m.slot != "tone") != base.lower():
        return None
    res, at = [], 0
    for k, m in enumerate(ms):                          # slice the written word: the segmenter lowercases
        if m.slot == "tone":
            res.append(("tone", "", m.form, None, seg.ids.get((m.form, m.position)), tone_of[k])); continue
        t = nfc(m.text)
        res.append((m.slot, base[at:at + len(t)], m.form, m.position, seg.ids.get((m.form, m.position)) if m.slot != "stem" else None, None))
        at += len(t)
    if "".join(r[1] for r in res) != base or not all(r[1] for r in res if r[0] != "tone"):
        return None
    return res


def hyphen_groups(text, n):
    """runs of token numbers joined by a single '-' with nothing else between them"""
    sp = usj_source._token_spans(text)
    assert len(sp) == n
    groups, cur = [], [0] if n else []
    for k in range(1, n):
        if text[sp[k - 1][1]:sp[k][0]] == "-":
            cur.append(k)
        else:
            groups.append(cur); cur = [k]
    if cur:
        groups.append(cur)
    return [g for g in groups if len(g) > 1]


def group_parts(words):
    """a hyphen word split joined: {piece: [(slot, text, form, position, chain_id, tone)]}, or None when the joined split has
    a tone part, does not rebuild, a part crosses the hyphen, or no piece gets an affix (then each piece is split alone)"""
    joined = "-".join(nfc(w) for w in words); ms = seg.S.split(joined, tones=True)
    if len(ms) < 2 or any(m.slot == "tone" for m in ms) or "".join(nfc(m.text) for m in ms) != joined.lower():
        return None
    bounds, at = [], 0
    for w in words:
        bounds.append((at, at + len(nfc(w)))); at += len(nfc(w)) + 1
    out, at = {k: [] for k in range(len(words))}, 0
    for m in ms:
        a, b = at, at + len(nfc(m.text)); at = b
        a2 = a + 1 if joined[a] == "-" else a; b2 = b - 1 if joined[b - 1] == "-" else b      # a hyphen at the edge belongs to no piece
        hit = [k for k, (x, y) in enumerate(bounds) if x <= a2 and b2 <= y]
        if not hit or b2 <= a2:
            return None
        out[hit[0]].append((m.slot, joined[a2:b2], m.form, m.position, seg.ids.get((m.form, m.position)) if m.slot != "stem" else None, None))
    if any(not v for v in out.values()) or not any(p[0] != "stem" for v in out.values() for p in v):
        return None
    if any("".join(p[1] for p in v) != nfc(words[k]) for k, v in out.items()):
        return None
    return out


rows, stats, books, fps = [], Counter(), [], {}
for f in sorted(USJ.glob("*.json")):
    book = f.stem.split("-", 1)[1]; books.append(book); fps[book] = book_file_hash(f)
    for (ch, vs), text in sorted(usj_verses(f).items()):
        toks, words = usj_source.tokenize(text), bcv_written.tokenize_written(text)
        assert len(toks) == len(words), (book, ch, vs)
        joined = {}
        for g in hyphen_groups(text, len(toks)):
            gp = group_parts([words[k] for k in g])
            if gp is not None:
                stats["hyphen groups"] += 1
                for j, k in enumerate(g):
                    joined[k] = (gp[j], g[j + 1] - k if j + 1 < len(g) else g[j - 1] - k)
        for i, (tok, word) in enumerate(zip(toks, words)):
            base = dict(book=book, chapter=ch, verse=vs, i=i, token=tok, word=nfc(word), written=None, host=None)
            ps, host_off = joined.get(i, (parts_of(word), None)); stats["tokens"] += 1
            if ps is not None and len(ps) == 1 and ps[0][0] in ("prefix", "suffix") and host_off is not None:
                slot, t, form, pos, cid, _ = ps[0]; stats[f"hyphen {slot}"] += 1
                rows.append({**base, "part": 0, "slot": slot, "text": t, "form": form, "position": pos, "chain_id": cid, "tone": None,
                             "label": None, "p_split": None, "written": "hyphen", "host": host_off})
                continue
            if ps is None or len(ps) == 1:
                rows.append({**base, "part": 0, "slot": "whole", "text": nfc(word), "form": None, "position": None, "chain_id": None,
                             "tone": None, "label": None, "p_split": None})
                continue
            stats["divided"] += 1
            for k, (slot, t, form, pos, cid, tone) in enumerate(ps):
                stats[slot] += 1
                rows.append({**base, "part": k, "slot": slot, "text": t, "form": form if slot not in ("stem", "tone") else None,
                             "position": pos if slot not in ("stem", "tone") else None, "chain_id": cid, "tone": tone,
                             "label": form if slot == "tone" else None, "p_split": 1.0 if k == 0 else None})
OUT.mkdir(parents=True, exist_ok=True)
pq.write_table(pa.Table.from_pylist(rows), OUT / "words.parquet")
sha = hashlib.sha256((OUT / "words.parquet").read_bytes()).hexdigest()
head = {"spec": "bcv-split/0.1", "edition": TAG, "tokenizer_version": usj_source.TOKENIZER_VERSION, "source": SOURCE, "basis": "derived",
        "numbering": "seg.S.split(written token, tones=True); part = list index; a hyphen word is split joined, each piece numbered from 0",
        "sha256": sha, "text_licence": LICENCE, "books": books, "text_fp": fps, "text_fp_version": 1, "date": date.today().isoformat()}
(OUT / "_split.json").write_text(json.dumps(head, ensure_ascii=False, indent=1) + "\n")
print(json.dumps({**stats, "rows": len(rows), "sha256": sha[:16]}))
