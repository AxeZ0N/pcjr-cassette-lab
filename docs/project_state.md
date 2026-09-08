# PyCJr — Project State (durable record) (v6)

Repo-resident durable record. Not BDS-imported. BDS loads the `bds/`
package; this file backs it.

## Provenance

| Item | URL |
|---|---|
| PCjr BASIC manual | https://archive.org/details/pcjr-basic |
| Tech Ref PDF (secondary) | https://www.minuszerodegrees.net/manuals/IBM/IBM%204860%20(PCjr)%20-%20Technical%20Reference.pdf |

The digital-born `refs/deepseek_reference.txt` (479 entries) supersedes
the PDF for lookups; the PDF is the provenance copy.

## File inventory (pointer)

See `README.md` and `MANIFEST.md`. Do not duplicate the table here.

## Facts and sessions

- Values: `facts.md` (append-only; updates use `supersedes:`).
- Narrative: `sessions/YYYY-MM-DD_scope.md`.
- Run history: `docs/test_log.md`.

## Hardware state (pointer only)

Stable hardware facts live in `facts.md` headings `hardware_map` and
`nmi_chain_detail`. CH0 clock is empirical and owned by
`facts.md#hardware_map`; do not restate values here.

## Research log (pointer)

Phase status, empirical clocks, and closed/open items live in
`facts.md` heading `research_track_state`. Open items are owned by
`bds/30_project/pycjr_project.md`.

## Session hygiene

Each session has one defined scope. Volatile readings — edge counts,
max_delta, gap counts, iteration counts, pass results — live in
`facts.md`, `docs/test_log.md`, and the session handoff, never here or
in the skills. When a session scope is done, recommend a new session.
