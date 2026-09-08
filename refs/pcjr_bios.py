#!/usr/bin/env python3
"""Read-only BIOS listing search over refs/ibm_pcjr-bios.lst.

The BIOS dump is a flat text listing from 0000:0000 to FFFF:FFFF,
separate from the prose manual. It carries no page ids; matches are
line-attributed only.

The first ~25 lines are an ASCII IBM header block (no addresses);
listing labels start past that. grep/peek cover the whole file,
including the header — a query matching header text will hit it.

Modes (via BiosStore):
    grep   line hits with context, OCR hex normalization default on
    peek   raw lines by 1-based line number
    stats  line count of the listing
"""

from pathlib import Path

from pcjr_hex import compile_pattern

def _format_hits(records):
    if not records:
        return "No matches."
    out = []
    for r in records:
        for k, ln in enumerate(r["before"], start=r["line"] - len(r["before"])):
            out.append(f"{k}:  {ln}")
        out.append(f"{r['line']}:> {r['text']}")
        for k, ln in enumerate(r["after"], start=r["line"] + 1):
            out.append(f"{k}:  {ln}")
        out.append("---")
    return "\n".join(out)

def _collapse_ws(s):
    """Collapse runs of whitespace to single spaces, trimming edges.

    The BIOS .lst pads columns with variable runs of spaces (e.g.
    ``PROC    NEAR``). Matching the raw line against a single-spaced
    needle false-negatives. Collapse both sides so ``PROC NEAR`` hits
    ``PROC    NEAR``, while display text keeps original spacing.
    """
    return " ".join((s or "").split())


class BiosStore:
    """Read-only store of the flat BIOS listing."""

    def __init__(self, path):
        self.path = Path(path)
        raw = self.path.read_text(encoding="utf-8", errors="replace")
        self.lines = raw.splitlines()
        if not self.lines:
            raise ValueError(f"empty BIOS listing: {path}")

    def grep(self, term, context=3, max_matches=50, raw=False):
        """Line-attributed grep. raw=true disables hex normalization.

        Query and line whitespace are both collapsed to single spaces
        before matching (tolerant of column padding). Recorded text is
        the ORIGINAL line; only the match test uses the collapsed form.
        """
        rx, err = compile_pattern(_collapse_ws(term), raw)
        if err:
            return {"error": err}
        if max_matches < 1:
            max_matches = 1
        records = []
        total_hits = 0
        for i, ln in enumerate(self.lines, 1):
            if rx.search(_collapse_ws(ln)):
                total_hits += 1
                if len(records) < max_matches:
                    lo = max(0, i - 1 - context)
                    hi = min(len(self.lines), i + context)
                    records.append({
                        "line": i,
                        "text": ln,
                        "before": self.lines[lo:i - 1],
                        "after": self.lines[i:hi],
                    })
        return {
            "matches": records,
            "total_hits": total_hits,
            "returned": len(records),
            "truncated": len(records) < total_hits,
            "text": _format_hits(records),
        }
    def peek(self, start, end=None):
        """Raw lines by 1-based line number."""
        if start < 1:
            return {"error": "start must be >= 1"}
        end = end or start
        if end < start:
            return {"error": "end must be >= start"}
        entries = []
        for n in range(start, end + 1):
            if n < 1 or n > len(self.lines):
                entries.append({"line": n, "error": "NOT FOUND"})
                continue
            entries.append({"line": n, "text": self.lines[n - 1]})
        return {
            "entries": entries,
            "total_lines": len(self.lines),
            "requested_start": start,
            "requested_end": end,
        }

    def stats(self):
        return {"path": str(self.path), "total_lines": len(self.lines)}
