#!/usr/bin/env python3
"""PCjr Technical Reference manual store (v1 rebuild).

Single source of page attribution: tech_ref_sanitize.segment_pages over
refs/pcjr_technical_reference.txt. Appendix A pages are excluded here
(the BIOS listing lives in refs/ibm_pcjr-bios.lst, served by pcjr_bios).

pages.jsonl is loaded once and joined on page_id for axes/regions
metadata only. It is never a search index.

peek indexes are STRIP-FILE ORDER, not manual physical order:
peek(1) is B-47, not the manual front. Use query/grep to locate
content; use peek only for raw access to a known page.

Modes (via ManualStore):
    query  ranked prose search, front matter skipped, page-level matches
    grep   exhaustive line-attributed hits across all pages
    peek   raw page body by 1-based page index
    stats  page counts plus jsonl coverage
"""

import json
import re
from pathlib import Path

import tech_ref_sanitize as SAN

from pcjr_hex import compile_pattern

TOC_LINE_RE = re.compile(r"(?:\.\s*){3,}\s*\d{1,3}\s*-\s*\d{1,3}\s*$")

def is_front_matter(body):
    """True if the page looks like TOC/front matter, not body text.

    Re-derived from the archived RefStore: marker words, else a page
    with >= 3 TOC lines making >= 30% of non-empty lines.
    """
    upper = body.upper()
    markers = ("TAB INDEX", "CONTENTS", "TABLE OF CONTENTS")
    if any(m in upper for m in markers):
        return True
    non_empty = [ln for ln in body.splitlines() if ln.strip()]
    if not non_empty:
        return False
    toc_lines = sum(1 for ln in non_empty if TOC_LINE_RE.search(ln))
    return toc_lines >= 3 and (toc_lines / len(non_empty)) >= 0.3

def _format_hits(records):
    if not records:
        return "No matches."
    out = []
    for r in records:
        loc = r["page_id"]
        for k, ln in enumerate(r["before"], start=r["line"] - len(r["before"])):
            out.append(f"{loc}:{k}:  {ln}")
        out.append(f"{loc}:{r['line']}:> {r['text']}")
        for k, ln in enumerate(r["after"], start=r["line"] + 1):
            out.append(f"{loc}:{k}:  {ln}")
        out.append("---")
    return "\n".join(out)

class ManualStore:
    """Read-only store of the digitized reference strip, Appendix A excluded."""

    def __init__(self, strip_path, pages_jsonl_path=None):
        self.strip_path = Path(strip_path)
        raw = self.strip_path.read_text(encoding="utf-8", errors="replace")
        pages, _recovered = SAN.segment_pages(raw)
        self.pages = []
        for page, title, body in pages:
            if not body.strip():
                continue
            if SAN.is_appendix_a(page):
                continue
            self.pages.append({
                "idx": len(self.pages) + 1,
                "page_id": page,
                "title": title,
                "body": body,
            })
        if not self.pages:
            raise ValueError("no pages parsed; check strip format")
        self._jsonl = {}
        if pages_jsonl_path:
            self._load_jsonl(Path(pages_jsonl_path))

    def _load_jsonl(self, path):
        if not path.exists():
            return
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            pid = obj.get("page_id")
            if pid:
                self._jsonl[pid] = obj

    def _meta(self, page_id):
        """Return axes/regions metadata for a page, or None if absent."""
        obj = self._jsonl.get(page_id)
        if not obj:
            return None
        return {
            "num_lines": obj.get("num_lines"),
            "toc_frac": obj.get("toc_frac"),
            "listing_frac": obj.get("listing_frac"),
            "figureish": obj.get("figureish"),
            "regions": obj.get("regions"),
        }

    def query(self, term, context=3, max_pages=1, raw=False):
        """Ranked prose search. Front matter is skipped. Page-level matches."""
        rx, err = compile_pattern(term, raw)
        if err:
            return {"error": err}
        if max_pages < 1:
            return {"error": "max_pages must be >= 1"}
        out = []
        shown = 0
        total_matched = 0
        for pg in self.pages:
            if is_front_matter(pg["body"]):
                continue
            lines = pg["body"].splitlines()
            hits = [i for i, ln in enumerate(lines) if rx.search(ln)]
            if not hits:
                continue
            total_matched += 1
            if shown >= max_pages:
                continue
            shown += 1
            rec = {
                "page_id": pg["page_id"],
                "title": pg["title"],
                "num_lines": len(lines),
            }
            if context <= 0:
                rec["text"] = pg["body"].rstrip("\n")
            else:
                keep = set()
                for h in hits:
                    for j in range(
                        max(0, h - context), min(len(lines), h + context + 1)
                    ):
                        keep.add(j)
                rec["text"] = "\n".join(
                    f"{j + 1}\t{lines[j].rstrip()}" for j in sorted(keep)
                )
            meta = self._meta(pg["page_id"])
            if meta:
                rec["meta"] = meta
            out.append(rec)
        return {
            "matches": out,
            "total_pages_matched": total_matched,
            "returned": shown,
            "truncated": shown < total_matched,
        }

    def grep(self, term, context=3, max_matches=50, raw=False):
        """Exhaustive line-attributed hits. Front matter is included."""
        rx, err = compile_pattern(term, raw)
        if err:
            return {"error": err}
        if max_matches < 1:
            max_matches = 1
        records = []
        total_hits = 0
        seen_pages = []
        for pg in self.pages:
            lines = pg["body"].splitlines()
            for i, ln in enumerate(lines, 1):
                if rx.search(ln):
                    total_hits += 1
                    if pg["page_id"] not in seen_pages:
                        seen_pages.append(pg["page_id"])
                    if len(records) < max_matches:
                        lo = max(0, i - 1 - context)
                        hi = min(len(lines), i + context)
                        records.append({
                            "page_id": pg["page_id"],
                            "line": i,
                            "text": ln,
                            "before": lines[lo:i - 1],
                            "after": lines[i:hi],
                        })
        pages = {}
        for pid in seen_pages:
            m = self._meta(pid)
            if m:
                pages[pid] = m
        return {
            "matches": records,
            "pages": pages,
            "total_hits": total_hits,
            "returned": len(records),
            "truncated": len(records) < total_hits,
            "text": _format_hits(records),
        }

    def peek(self, start, end=None):
        """Raw page body by 1-based page index."""
        if start < 1:
            return {"error": "start must be >= 1"}
        end = end or start
        if end < start:
            return {"error": "end must be >= start"}
        entries = []
        for n in range(start, end + 1):
            if n < 1 or n > len(self.pages):
                entries.append({"idx": n, "error": "NOT FOUND"})
                continue
            pg = self.pages[n - 1]
            rec = {
                "idx": n,
                "page_id": pg["page_id"],
                "title": pg["title"],
                "text": pg["body"].rstrip("\n"),
            }
            meta = self._meta(pg["page_id"])
            if meta:
                rec["meta"] = meta
            entries.append(rec)
        return {
            "entries": entries,
            "total_pages": len(self.pages),
            "requested_start": start,
            "requested_end": end,
        }

    def stats(self, verbose=False):
        front = sum(1 for pg in self.pages if is_front_matter(pg["body"]))
        covered = sum(1 for pg in self.pages if pg["page_id"] in self._jsonl)
        out = {
            "total_pages": len(self.pages),
            "front_matter": front,
            "content_pages": len(self.pages) - front,
            "jsonl_covered": covered,
        }
        if verbose:
            out["pages"] = [
                {"idx": pg["idx"], "page_id": pg["page_id"], "title": pg["title"]}
                for pg in self.pages
            ]
        return out
