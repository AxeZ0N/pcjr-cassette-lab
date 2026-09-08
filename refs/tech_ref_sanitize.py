#!/usr/bin/env python3
# PCjr Manual Pipeline (v1)
#
# Single-module pipeline:
#   segment  ->  language-model axes  ->  figure-region segmentation
#
# Commands:
#   train     INPUT -> model.json
#   classify  INPUT MODEL -> raw-chunk axes report
#   run       INPUT [MODEL] [--output out.jsonl] [--keep-appendix-a]
#             [--seg-out out.seg.txt] [--top-mixed N]
#
# 'run' keys every record by MANUAL page id (2-30, A-10, '?'), drops
# Appendix A by default, computes three continuous page axes, finds
# diagram regions per page, and emits one JSON object per line.
#
# Region line indices are 1-based positions among NON-BLANK body lines,
# never raw file lines.

import argparse
import json
import math
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ----------------------------------------------------------------------
# constants
# ----------------------------------------------------------------------

PAGE_TOKEN_RE = re.compile(
    r'(?P<prefix>[A-Za-z0-9]+)\s*-\s*(?P<num>[0-9OIlTt\s]+)'
)
_ROMAN = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x",
          "xi", "xii", "xiii", "xiv", "xv"}
_DIGIT_FIX = {"O": "0", "o": "0", "I": "1", "l": "1", "|": "1",
              "t": "1", "T": "1"}

DIAGRAM_PUNCT = set("+-|/\\.:;=<>[](){}*_^#@~")
REPEAT_RE = re.compile(r'([-+=|_.:*#~<>])\1{2,}')
DOT_RUN_RE = re.compile(r'\.(\s*\.){2,}')
HEX_FIX = {"O": "0", "o": "0", "I": "1", "l": "1", "|": "1",
           "!": "1", "S": "5", "s": "5"}
LISTING_ADDR_RE = re.compile(r'[0-9A-F]{4}')

PROSE_HI = -8.0
PROSE_LO = -9.5

# region parameters
ART_SEED = 0.5
ART_MEAN = 0.4
ART_MIN_LEN = 3
ART_GAP = 2
CAPTION_RE = re.compile(r"^(figure|fig\.|table)\b", re.IGNORECASE)


# ----------------------------------------------------------------------
# segmenter (v5)
# ----------------------------------------------------------------------

def normalize_page_num(raw):
    s = raw.strip()
    s = "".join(_DIGIT_FIX.get(ch, ch) for ch in s)
    s = re.sub(r"\s+", "", s)
    return s


def escape_attr(value):
    return value.replace("&", "&amp;").replace('"', "&quot;")


def parse_footer(line):
    stripped = line.strip()
    if not stripped:
        return None, None
    low = stripped.lower()
    if low in _ROMAN:
        return low, ""
    m = PAGE_TOKEN_RE.search(stripped)
    if not m:
        return None, None
    prefix = m.group("prefix").strip()
    num = normalize_page_num(m.group("num"))
    if not prefix or not num or not num.isdigit():
        return None, None
    page = f"{prefix}-{num}"
    before = stripped[:m.start()].strip()
    after = stripped[m.end():].strip()
    title = " ".join(p for p in (before, after) if p)
    return page, title


def segment_pages(text):
    chunks = text.split("\f")
    pages = []
    recovered = 0
    for chunk in chunks:
        lines = chunk.splitlines()
        end = len(lines)
        while end > 0 and not lines[end - 1].strip():
            end -= 1
        if end == 0:
            pages.append(("?", "", ""))
            continue
        footer_line = lines[end - 1]
        body_lines = lines[:end - 1]
        page, title = parse_footer(footer_line)
        if page is None:
            prev_end = end - 2
            while prev_end >= 0 and not lines[prev_end].strip():
                prev_end -= 1
            if prev_end >= 0:
                p2, t2 = parse_footer(lines[prev_end])
                if p2 is not None:
                    page, title = p2, t2
                    head = footer_line.strip()
                    if head:
                        title = f"{title} {head}".strip() if title else head
                    body_lines = lines[:prev_end]
                    recovered += 1
        if page is None:
            page, title = "?", ""
        start = 0
        while start < len(body_lines) and not body_lines[start].strip():
            start += 1
        body = "\n".join(body_lines[start:]).strip()
        pages.append((page, title, body))
    return pages, recovered


def is_appendix_a(page):
    if page == "?":
        return False
    return page.rsplit("-", 1)[0] == "A"


def render_page(page, title, body):
    return (f'<page number="{escape_attr(page)}" title="{escape_attr(title)}">\n'
            f"{body}\n</page>\n\n")


# ----------------------------------------------------------------------
# language model
# ----------------------------------------------------------------------

@dataclass
class LanguageModel:
    trigram_counts: Dict[str, int] = field(default_factory=dict)
    total_trigrams: int = 0
    vocab_size: int = 0

    @classmethod
    def from_json(cls, path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls(dict(data["trigram_counts"]),
                   int(data["total_trigrams"]), int(data["vocab_size"]))

    def to_json(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "trigram_counts": self.trigram_counts,
                "total_trigrams": self.total_trigrams,
                "vocab_size": self.vocab_size,
            }, f, indent=2)

    def train(self, text):
        counts = Counter()
        for line in text.splitlines():
            s = line.strip()
            if not s:
                continue
            s = "  " + s.lower() + "  "
            for i in range(len(s) - 2):
                counts[s[i:i+3]] += 1
        for tri, c in counts.items():
            self.trigram_counts[tri] = self.trigram_counts.get(tri, 0) + c
        self.total_trigrams = sum(self.trigram_counts.values())
        self.vocab_size = len(self.trigram_counts)

    def score_line(self, line):
        s = line.strip()
        if not s or self.vocab_size == 0:
            return None
        s = "  " + s.lower() + "  "
        n = len(s) - 2
        denom = self.total_trigrams + self.vocab_size
        total = 0.0
        for i in range(n):
            tri = s[i:i+3]
            c = self.trigram_counts.get(tri, 0)
            total += math.log((c + 1) / denom)
        return total / n


def page_stats(chunk):
    lines = [l for l in chunk.splitlines() if l.strip()]
    if not lines:
        return 0.0, 0.0, 0.0, 0
    chars = [ch for l in lines for ch in l if not ch.isspace()]
    if not chars:
        return 0.0, 0.0, 0.0, len(lines)
    a = sum(ch.isalpha() for ch in chars)
    p = sum(ch in DIAGRAM_PUNCT for ch in chars)
    d = sum(ch.isdigit() for ch in chars)
    return a/len(chars), p/len(chars), d/len(chars), len(lines)


def select_seed_pages(text, alpha=0.80, punct=0.15, min_lines=10):
    out = []
    for chunk in text.split("\f"):
        a, p, _, n = page_stats(chunk)
        if n >= min_lines and a >= alpha and p <= punct:
            out.append(chunk)
    return out


# ----------------------------------------------------------------------
# axes
# ----------------------------------------------------------------------

@dataclass
class LineFeat:
    indent: int
    alpha_ratio: float
    digit_ratio: float
    punct_ratio: float
    word_count: int
    single_char_tokens: int
    repeat_runs: bool


def is_toc_entry(line):
    s = line.strip()
    if not s or not DOT_RUN_RE.search(s):
        return False
    m = PAGE_TOKEN_RE.search(s)
    if not m or s[m.end():].strip():
        return False
    return bool(re.search(r'[A-Za-z]{2,}', s[:m.start()]))


def is_listing_line(line):
    s = line.lstrip()
    if not s:
        return False
    tok = s.split()[0]
    if len(tok) < 4:
        return False
    norm = "".join(HEX_FIX.get(c, c) for c in tok[:4].upper())
    return bool(LISTING_ADDR_RE.fullmatch(norm))


def line_features(line):
    s = line.strip()
    if not s:
        return None
    indent = len(line) - len(line.lstrip())
    non_space = [ch for ch in s if not ch.isspace()]
    if not non_space:
        return None
    total = len(non_space)
    a = sum(ch.isalpha() for ch in non_space)
    d = sum(ch.isdigit() for ch in non_space)
    p = sum(ch in DIAGRAM_PUNCT for ch in non_space)
    toks = s.split()
    wc = sum(1 for t in toks if sum(c.isalpha() for c in t) >= 2)
    sct = sum(1 for t in toks if len(t) == 1)
    rr = bool(REPEAT_RE.search(s))
    return LineFeat(indent, a/total, d/total, p/total, wc, sct, rr)


def prose_gate(lm):
    if lm is None:
        return 0.0
    if lm <= PROSE_LO:
        return 1.0
    if lm >= PROSE_HI:
        return 0.0
    return (PROSE_HI - lm) / (PROSE_HI - PROSE_LO)


def struct_score(feat, prev_indent):
    sc = 0.0
    if feat.repeat_runs:
        sc += 0.30
    if feat.punct_ratio > 0.35:
        sc += 0.25
    if feat.single_char_tokens >= 3:
        sc += 0.20
    if feat.digit_ratio > 0.30 and feat.alpha_ratio < 0.40:
        sc += 0.15
    if prev_indent is not None and abs(feat.indent - prev_indent) > 6:
        sc += 0.10
    if feat.word_count >= 6 and feat.alpha_ratio > 0.60:
        sc -= 0.40
    if feat.word_count == 0 and feat.punct_ratio > 0.4:
        sc += 0.10
    return sc


def art_score(line, feat, lm, prev_indent):
    if not line.strip() or is_toc_entry(line) or feat is None:
        return 0.0
    return max(0.0, min(1.0, struct_score(feat, prev_indent) * prose_gate(lm)))


def score_page_lines(lines, model):
    scores = []
    art = []
    prev_indent = None
    for line in lines:
        feat = line_features(line)
        lm = model.score_line(line)
        scores.append(lm)
        art.append(art_score(line, feat, lm, prev_indent))
        if feat is not None:
            prev_indent = feat.indent
    return scores, art


def axes_for_body(body, model):
    lines = [l for l in body.splitlines() if l.strip()]
    n = len(lines)
    if n == 0:
        return 0, 0.0, 0.0, 0.0, [], []
    toc = sum(1 for l in lines if is_toc_entry(l))
    listing = sum(1 for l in lines if is_listing_line(l))
    _, art = score_page_lines(lines, model)
    return n, toc/n, listing/n, sum(art)/n, lines, art


# ----------------------------------------------------------------------
# regions
# ----------------------------------------------------------------------

# replace these four constants
LM_REGION_SEED = -9.0
LISTING_SKIP_FRAC = 0.30
REGION_MIN_LOW_FRAC = 0.6
ART_MIN_LEN = 3          # keep
ART_GAP = 2              # keep


def find_regions(lines, lm_scores, listing_frac):
    """Find diagram regions from LM scores alone.

    Seeds are lines whose LM score is <= LM_REGION_SEED. No structural
    multiplier is applied: schematic part numbers and strokes are both
    far below the prose band, and the AND-gate erased them.

    Regions are skipped entirely on pages that are already assembly
    listings; those are caught by listing_frac, not figure regions.
    """
    if listing_frac >= LISTING_SKIP_FRAC:
        return []

    seeds = [
        i for i, s in enumerate(lm_scores)
        if s is not None and s <= LM_REGION_SEED
    ]

    regions = []
    i = 0
    while i < len(seeds):
        start = seeds[i]
        last = start
        j = i + 1
        while j < len(seeds):
            gap = seeds[j] - last - 1
            if gap > ART_GAP:
                break
            last = seeds[j]
            j += 1
        end = last

        # absorb adjacent figure/table captions
        if start > 0 and CAPTION_RE.match(lines[start - 1].strip()):
            start -= 1
        if end + 1 < len(lines) and CAPTION_RE.match(lines[end + 1].strip()):
            end += 1

        length = end - start + 1
        low = sum(
            1 for k in range(start, end + 1)
            if lm_scores[k] is not None and lm_scores[k] <= LM_REGION_SEED
        )
        mean_low = low / length if length else 0.0

        if length >= ART_MIN_LEN and mean_low >= REGION_MIN_LOW_FRAC:
            regions.append({
                "start": start + 1,
                "end": end + 1,
                "len": length,
                "mean": round(mean_low, 3),
                "sample": lines[start].strip()[:60],
            })
        i = j

    return regions


# ----------------------------------------------------------------------
# run command
# ----------------------------------------------------------------------

def run_pipeline(raw, model, keep_appendix_a, seg_out, top_mixed):
    pages, recovered = segment_pages(raw)
    kept = []
    for pg in pages:
        if pg[0] == "?" and not pg[2].strip():
            continue
        if not keep_appendix_a and is_appendix_a(pg[0]):
            continue
        kept.append(pg)

    if seg_out:
        text = "".join(render_page(p, t, b) for p, t, b in kept)
        Path(seg_out).write_text(text, encoding="utf-8")
        print(f"Wrote segment: {seg_out}")

    records = []
    for page, title, body in kept:
        n, toc, listing, fig, lines, art = axes_for_body(body, model)
        lm_scores = [model.score_line(l) for l in lines]
        regions = find_regions(lines, lm_scores, listing)
        records.append({
            "page_id": page,
            "title": title,
            "num_lines": n,
            "toc_frac": round(toc, 3),
            "listing_frac": round(listing, 3),
            "figureish": round(fig, 3),
            "regions": regions,
        })

    if top_mixed and top_mixed > 0:
        cands = [r for r in records
                 if 0.02 < r["figureish"] < 0.40
                 and r["toc_frac"] < 0.20
                 and r["listing_frac"] < 0.20]
        cands.sort(key=lambda r: r["figureish"], reverse=True)
        print(f"\nTop mixed-page candidates (eyeball to lock a gate anchor):")
        for r in cands[:top_mixed]:
            print(f"  {r['page_id']:>8}  figureish={r['figureish']:.3f}  "
                  f"lines={r['num_lines']:>3}  title={r['title'][:40]}")

    return records, recovered


def main(argv=None):
    ap = argparse.ArgumentParser(description="PCjr manual pipeline")
    sub = ap.add_subparsers(dest="cmd", required=True)

    tr = sub.add_parser("train")
    tr.add_argument("input")
    tr.add_argument("--output", default="language_model.json")
    tr.add_argument("--seed-alpha", type=float, default=0.80)
    tr.add_argument("--seed-punct", type=float, default=0.15)
    tr.add_argument("--min-lines", type=int, default=10)

    cl = sub.add_parser("classify")
    cl.add_argument("input")
    cl.add_argument("model")
    cl.add_argument("--output", default="-")

    rn = sub.add_parser("run")
    rn.add_argument("input")
    rn.add_argument("model", nargs="?")
    rn.add_argument("--output", default="pages.jsonl")
    rn.add_argument("--keep-appendix-a", action="store_true")
    rn.add_argument("--seg-out")
    rn.add_argument("--top-mixed", type=int, default=0)

    args = ap.parse_args(argv)

    if args.cmd == "train":
        raw = Path(args.input).read_text(encoding="utf-8", errors="replace")
        seeds = select_seed_pages(raw, args.seed_alpha, args.seed_punct,
                                  args.min_lines)
        if not seeds:
            raise SystemExit("No seed pages")
        model = LanguageModel()
        for s in seeds:
            model.train(s)
        model.to_json(args.output)
        print(f"Seed pages: {len(seeds)}  vocab: {model.vocab_size}  "
              f"trigrams: {model.total_trigrams}  -> {args.output}")

    elif args.cmd == "classify":
        raw = Path(args.input).read_text(encoding="utf-8", errors="replace")
        model = LanguageModel.from_json(args.model)
        rows = ["page_id\tnum_lines\ttoc_frac\tlisting_frac\tfigureish"]
        for i, chunk in enumerate(raw.split("\f")):
            n, toc, listing, fig, _, _ = axes_for_body(chunk, model)
            rows.append(f"?{i}\t{n}\t{toc:.3f}\t{listing:.3f}\t{fig:.3f}")
        report = "\n".join(rows) + "\n"
        if args.output == "-":
            sys.stdout.write(report)
        else:
            Path(args.output).write_text(report, encoding="utf-8")
            print(f"Wrote: {args.output}")

    elif args.cmd == "run":
        raw = Path(args.input).read_text(encoding="utf-8", errors="replace")
        if args.model:
            model = LanguageModel.from_json(args.model)
        else:
            seeds = select_seed_pages(raw)
            if not seeds:
                raise SystemExit("No seed pages; train a model first")
            model = LanguageModel()
            for s in seeds:
                model.train(s)
        records, _ = run_pipeline(raw, model, args.keep_appendix_a,
                                  args.seg_out, args.top_mixed)
        with open(args.output, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"Pages emitted: {len(records)} -> {args.output}")


if __name__ == "__main__":
    main()
