#!/usr/bin/env python3
"""Rights before data moves: what may be done with a team's text, said once in the language's configuration and asked by
every step that sends it somewhere.

    "rights": {"licence": "CC BY-NC-ND 4.0",
               "llm": true,                 # the text may be shown to the drafting model (prompts hold the team's wording)
               "jev": true,                 # the text may be sent to TypeSafe's Jev (the paid alignment pass)
               "aligner_service": false,    # the text may be sent to lexeme-aligner's maintainers (else: aligned locally only)
               "publish": false,            # drafts made with the team's text among their inputs may be published
               "note": "who said so, and when"}

A missing table or a missing row means no. Publishing has further gates of its own (publish/push.py): what is published is
the drafts, never the team's text."""
import sys

WHERE = {"llm": "the drafting model", "jev": "Jev (TypeSafe)", "aligner_service": "lexeme-aligner's service",
         "publish": "the language's public text repository (the drafts, never the team's text)"}


def allowed(cfg, to):
    return (cfg.get("rights") or {}).get(to) is True


def check(cfg, to):
    """stop unless the language's rights table allows sending its text to `to`"""
    if not allowed(cfg, to):
        sys.exit(f"{cfg['iso']}: the rights table of the language's configuration does not allow this: {WHERE[to]} "
                 f"(\"rights\": {{\"{to}\": true}}, with a note on who said so)")
