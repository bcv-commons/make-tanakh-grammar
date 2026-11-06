#!/usr/bin/env python3
"""The clause layouts of the source texts (the aligner's inputs: greek-nt-clause-layout, hebrew-clause-layout): one row per
clause segment with its kind, its rule and its words. A clause interrupted by another one has several rows with one clause id."""
import os

import pyarrow.parquet as pq

from shared import paths


def greek_rows():
    """rows: book, chapter, clause (id), seg, kind, rule, words (token keys)"""
    return pq.read_table(paths.aligner_data("greek-nt-clause-layout", "clauses.parquet"),
                         columns=["book", "chapter", "clause", "seg", "kind", "rule", "words"]).to_pylist()


def hebrew_rows(book):
    """rows: book, chapter, clause_key (id), seg, kind, rule, words (morpheme keys), verse_ref_en (the verse in the English numbering)"""
    p = paths.aligner_data("hebrew-clause-layout", f"clauses-{book}.parquet")
    if not os.path.exists(p):
        raise SystemExit(f"no clause layout for {book}: {p}")
    return pq.read_table(p, columns=["book", "chapter", "clause_key", "seg", "kind", "rule", "words", "verse_ref_en"]).to_pylist()
