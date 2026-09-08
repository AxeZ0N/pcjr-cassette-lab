#!/usr/bin/env python3
"""Read-only repo search for the PyCJr living repo (v2 rebuild).

Scope is named by mode, not by operation:

    facts           fact-layer grep: facts.md + sessions/ + docs/
    all             whole-repo grep (text files only)
    files           substring discovery of root-relative paths
    ls              directory listing
    read            exact file read with optional start_line/end_line
    facts_headings  heading index of facts.md (line, date, name, status)
    stats           fact-layer file/line counts
    roots           which fact-layer roots exist

Safety invariants, re-derived from the archived v1 walker (never a
resurrection; fresh code, same guarantees):

    text suffixes only, hidden path components refused, symlink escapes
    refused, absolute/`..` refused, broken symlinks skipped.

All grep modes carry total_hits/returned/truncated. Truncation is never
silent: a capped search is distinguishable from a true no-match.
"""

import os
import re
from pathlib import Path

FACT_ROOT_NAMES = ["facts.md", "sessions", "docs"]
TEXT_SUFFIXES = {
    ".md", ".txt", ".csv",
    ".py", ".sh", ".bat",
    ".bas", ".asm",
    ".json", ".toml", ".yaml", ".yml", ".xml", ".ini", ".cfg",
}

HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")

def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent

def fact_roots() -> list:
    r = repo_root()
    return [r / name for name in FACT_ROOT_NAMES if (r / name).exists()]

def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False

def _iter_text_files_under(top: Path):
    """Yield resolved text files under top.

    Prunes hidden dirs, skips hidden files, skips non-text suffixes,
    refuses symlink escapes (dirs and files) and broken symlinks.
    """
    top = top.resolve()
    for dirpath, dirnames, filenames in os.walk(top, topdown=True, followlinks=False):
        dirnames[:] = sorted(
            d for d in dirnames
            if not d.startswith(".")
            and not (Path(dirpath) / d).is_symlink()
        )
        for fn in sorted(filenames):
            if fn.startswith("."):
                continue
            p = Path(dirpath) / fn
            if p.suffix.lower() not in TEXT_SUFFIXES:
                continue
            try:
                rp = p.resolve()
            except OSError:
                continue
            if not _is_within(rp, top):
                continue  # symlink escape
            yield rp

def iter_text_files(paths):
    for p in paths:
        if p.is_file():
            if p.suffix.lower() in TEXT_SUFFIXES and not p.name.startswith("."):
                yield p.resolve()
        elif p.is_dir():
            yield from _iter_text_files_under(p)

def _as_int(v, default):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default

def _compile(query, literal):
    pat = re.escape(query) if literal else query
    try:
        return re.compile(pat, re.IGNORECASE), None
    except re.error as exc:
        return None, f"Bad regex: {exc}"

def format_records(records):
    if not records:
        return "No matches."
    out = []
    for r in records:
        loc = r.get("path", r.get("page_id", "?"))
        for k, ln in enumerate(r["before"], start=r["line"] - len(r["before"])):
            out.append(f"{loc}:{k}:  {ln}")
        out.append(f"{loc}:{r['line']}:> {r['text']}")
        for k, ln in enumerate(r["after"], start=r["line"] + 1):
            out.append(f"{loc}:{k}:  {ln}")
        out.append("---")
    return "\n".join(out)

def _match_records(query, context, literal, paths, max_matches):
    rx, err = _compile(query, literal)
    if err:
        return None, err
    if max_matches < 1:
        max_matches = 1
    records = []
    total_hits = 0
    for f in iter_text_files(paths):
        try:
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            if rx.search(line):
                total_hits += 1
                if len(records) < max_matches:
                    lo = max(0, i - 1 - context)
                    hi = min(len(lines), i + context)
                    records.append({
                        "path": str(f.relative_to(repo_root())),
                        "line": i,
                        "text": line,
                        "before": lines[lo:i - 1],
                        "after": lines[i:hi],
                    })
    return {
        "matches": records,
        "total_hits": total_hits,
        "returned": len(records),
        "truncated": len(records) < total_hits,
    }, None

def _grep_all(query, context, literal, max_matches):
    rx, err = _compile(query, literal)
    if err:
        return {"error": err}
    if max_matches < 1:
        max_matches = 1
    records = []
    total_hits = 0
    files_searched = 0
    for f in _iter_text_files_under(repo_root()):
        files_searched += 1
        try:
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            if rx.search(line):
                total_hits += 1
                if len(records) < max_matches:
                    lo = max(0, i - 1 - context)
                    hi = min(len(lines), i + context)
                    records.append({
                        "path": str(f.relative_to(repo_root())),
                        "line": i,
                        "text": line,
                        "before": lines[lo:i - 1],
                        "after": lines[i:hi],
                    })
    return {
        "matches": records,
        "total_hits": total_hits,
        "returned": len(records),
        "truncated": len(records) < total_hits,
        "files_searched": files_searched,
    }

def _guard_path(path, require_dir=False):
    """Validate a root-relative path; returns (resolved, None) or (None, err)."""
    if not isinstance(path, str) or not path.strip():
        return None, "ERROR: 'path' is required"
    p = Path(path)
    if p.is_absolute():
        return None, f"ERROR: absolute path refused: {path!r}"
    if ".." in p.parts:
        return None, f"ERROR: path traversal refused: {path!r}"
    if any(part.startswith(".") for part in p.parts):
        return None, f"ERROR: hidden path component refused: {path!r}"
    root = repo_root().resolve()
    try:
        candidate = (root / p).resolve(strict=False)
    except OSError as exc:
        return None, f"ERROR: cannot resolve {path!r}: {exc}"
    if not _is_within(candidate, root):
        return None, f"ERROR: path resolves outside repo root (symlink?): {path!r}"
    if require_dir:
        if not candidate.is_dir():
            return None, f"ERROR: not a directory under repo root: {path!r}"
    else:
        if not candidate.is_file():
            return None, f"ERROR: not a file under repo root: {path!r}"
        if candidate.suffix.lower() not in TEXT_SUFFIXES:
            return None, (
                f"ERROR: unsupported suffix {candidate.suffix!r}; "
                f"allowed: {sorted(TEXT_SUFFIXES)}"
            )
    return candidate, None

def _read_file(path, start_line=None, end_line=None):
    target, err = _guard_path(path)
    if err:
        return {"error": err}
    try:
        all_lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return {"error": f"cannot read {path!r}: {exc}"}
    total = len(all_lines)

    s = max(1, _as_int(start_line, 1))
    e = min(total, _as_int(end_line, total))
    if s > e:
        return {
            "error": f"start_line ({s}) exceeds end_line ({e}); "
                     "use 1-based line numbers with start_line <= end_line"
        }
    shown = all_lines[s - 1:e]
    return {
        "path": str(target.relative_to(repo_root())),
        "start_line": s,
        "end_line": e,
        "lines": len(shown),
        "truncated": e < total,
        "total_lines": total,
        "text": "\n".join(f"{i}\t{line}" for i, line in enumerate(shown, s)),
    }

def _files(query, max_matches):
    if max_matches < 1:
        max_matches = 1
    q = query.strip().lower()
    root = repo_root().resolve()
    total = 0
    matches = []
    for f in _iter_text_files_under(root):
        rel = str(f.relative_to(root))
        if q in rel.lower():
            total += 1
            if len(matches) < max_matches:
                matches.append(rel)
    return {
        "paths": matches,
        "total": total,
        "returned": len(matches),
        "truncated": len(matches) < total,
    }

def _ls(path, max_matches):
    if max_matches < 1:
        max_matches = 1
    root = repo_root().resolve()
    if not path or path in (".", ""):
        target = root
    else:
        t, err = _guard_path(path, require_dir=True)
        if err:
            return {"error": err}
        target = t
    try:
        names = sorted(os.listdir(target))
    except OSError as exc:
        return {"error": str(exc)}
    entries = []
    total = 0
    for name in names:
        if name.startswith("."):
            continue
        p = target / name
        if p.is_symlink():
            continue
        total += 1
        if len(entries) < max_matches:
            entries.append({
                "name": name,
                "type": "dir" if p.is_dir() else "file",
                "path": str(p.relative_to(root)),
            })
    return {
        "path": str(target.relative_to(root)),
        "entries": entries,
        "total": total,
        "returned": len(entries),
        "truncated": len(entries) < total,
    }

def _facts_headings():
    f = repo_root() / "facts.md"
    if not f.exists():
        return {"error": "facts.md not found"}
    headings = []
    for i, line in enumerate(
        f.read_text(encoding="utf-8", errors="replace").splitlines(), 1
    ):
        m = HEADING_RE.match(line)
        if not m:
            continue
        heading = m.group(1).strip()
        parts = [p.strip() for p in heading.split("\u00b7")]
        rec = {"line": i, "heading": heading}
        if len(parts) >= 1:
            rec["date"] = parts[0]
        if len(parts) >= 2:
            rec["name"] = parts[1]
        if len(parts) >= 3:
            rec["status"] = parts[2]          # was parts[-1] — wrong for 4+ fields
            if len(parts) > 3:
                rec["extra"] = parts[3:]      # provenance, preserved not discarded
        headings.append(rec)
    return {"headings": headings, "count": len(headings)}

def _stats():
    paths = fact_roots()
    n_files = 0
    n_lines = 0
    per_root = {}
    for p in paths:
        files = list(iter_text_files([p]))
        per_root[p.name] = {"files": len(files)}
        for f in files:
            n_files += 1
            try:
                n_lines += sum(1 for _ in f.open(encoding="utf-8", errors="replace"))
            except OSError:
                pass
    return {
        "roots": [p.name for p in paths],
        "files": n_files,
        "lines": n_lines,
        "detail": per_root,
    }

def dispatch(
    mode,
    query=None,
    context=2,
    literal=False,
    path=None,
    start_line=None,
    end_line=None,
    max_matches=50,
):
    """MCP-facing dispatcher for tool `grep_repo`."""
    ctx = _as_int(context, 2)
    mm = _as_int(max_matches, 50)

    if mode == "facts":
        if not query:
            return {"error": "facts requires 'query'"}
        res, err = _match_records(query, ctx, bool(literal), fact_roots(), mm)
        if err:
            return {"error": err}
        res["text"] = format_records(res["matches"])
        return res
    if mode == "all":
        if not query:
            return {"error": "all requires 'query'"}
        res = _grep_all(query, ctx, bool(literal), mm)
        if "error" in res:
            return res
        res["text"] = format_records(res.get("matches", []))
        return res
    if mode == "files":
        if not query:
            return {"error": "files requires 'query' substring"}
        return _files(query, mm)
    if mode == "ls":
        return _ls(path, mm)
    if mode == "read":
        if not path:
            return {"error": "read requires 'path'"}
        return _read_file(path, start_line, end_line)
    if mode == "facts_headings":
        return _facts_headings()
    if mode == "stats":
        return _stats()
    if mode == "roots":
        return {
            "roots": [str(p.relative_to(repo_root())) for p in fact_roots()],
            "existing": [p.exists() for p in fact_roots()],
        }
    return {
        "error": (
            f"unknown mode {mode!r}; use "
            "facts|all|files|ls|read|facts_headings|stats|roots"
        )
    }
