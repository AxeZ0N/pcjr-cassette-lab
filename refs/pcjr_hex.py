#!/usr/bin/env python3
"""Shared OCR hex-normalization helpers for manual and BIOS grep.

The digitized manual is noisy OCR: I/1, O/0, l/1, |/1, S/5, !/1.
For hex-looking tokens (41h, A0h, F0000, 0000:0008) the greps map each
hex digit to a character class of its OCR confusables, so `41h` also
matches `4lh`, `4Ih`, `4|h`. `raw=true` opts out.

HEX_CLASS maps the *canonical* digit to the set of glyphs that OCR
produced as that digit. Only 0/1/5 have confusables that appeared in
the strip; other hex digits (2,3,4,6,7,8,9,A-F) stay literal.
"""

import re

HEX_CLASS = {
    "0": "0Oo",
    "1": "1lI|!",
    "5": "5Ss",
}

_HEX_TOKEN_RE = re.compile(r"^[0-9A-Fa-f]{1,5}(:[0-9A-Fa-f]{1,5})*[hH]?$")

def is_hex_token(q):
    """True if q looks like a hex token: hex digits, optional colons, optional h."""
    s = (q or "").strip()
    if len(s) < 2:
        return False
    return bool(_HEX_TOKEN_RE.fullmatch(s))

def hex_regex(q):
    """Build a regex where each hex confusable digit becomes a character class."""
    out = []
    for ch in q.strip():
        cls = HEX_CLASS.get(ch)
        if cls:
            out.append("[" + cls + "]")
        else:
            out.append(re.escape(ch))
    return "".join(out)

def compile_pattern(term, raw=False):
    """Compile a search term. Returns (regex, None) or (None, error_string).

    If raw is False and term is a hex token, OCR hex normalization is
    applied. Otherwise the term is compiled as a literal Python regex.
    Matching is always case-insensitive.
    """
    q = (term or "").strip()
    if not q:
        return None, "empty pattern"
    try:
        if not raw and is_hex_token(q):
            pat = hex_regex(q)
        else:
            pat = q
        return re.compile(pat, re.IGNORECASE), None
    except re.error as exc:
        return None, f"Bad regex: {exc}"
