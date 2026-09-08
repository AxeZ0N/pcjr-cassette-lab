# PyCJr — Changelog

## v5.1 — 2026-08-22 — Wiring cleanup

- Registered `grep_repo` in `mcp/pcjr_tools_server.py` (three tools now).
- Fixed `bin/start_pcjr_mcp.sh` and `bin/byte_selftest.sh` to point at
  the real driver filenames (`mcp/pcjr_tools_server.py`,
  `refs/pcjr_asm_debug.py`).
- Normalized `bin/grep_selftest.sh` to resolve repo root via SCRIPT_DIR.
- Corrected all manual fallback commands from the removed
  `pcjr_ref_util.py` to `refs/pcjr_ref_tool.py REF ...`.
- Server `PCJR_REF_DIR` default now derives from the server file's
  location instead of a stale absolute path.
- MANIFEST rewritten to v5; README completed.
- `bin/pycjr.py`: fixed `--cc` help text (Fn+B, not Ctrl+C) and the
  chars/sec docstring/actual mismatch.

## v5 — 2026-08-22 — Living-repo refactor + tooling

Two commits:

1. Machinery: `bin/jr-commit.sh`, `bin/migrate_repo.py`,
   `bin/grep_selftest.sh`, `refs/pcjr_repo_grep.py`,
   `mcp/pcjr-tools.md` (adds `grep_repo` read-only repo tool).
2. Refactor: `facts.md` (append-only journal), `sessions/`,
   `bds/*` v5 (skill edits: Rule 8 carrier pair 13/12, ENVSHAPE anchor,
   repo-authoritative posture), `docs/*` slimmed into compiled views,
   README + MANIFEST updated, superseded docs flagged for deletion.

Closed this session:
- `open_3840` (38-vs-40 edge variance) = arming window swallowed frame
  1's leading start burst.
- Rule 8 carrier pair corrected to 13 us high / 12 us low.
- `gap2_1126` reinterpreted as stretched envelope H (~471 us).
- ENVSHAPE promoted to a known anchor.

## v4 — pre-refactor

Frozen hardware map, IR protocol, stage gates, CH0CAL derivation.
Recorded values superseded where noted in `facts.md`.
