# PyCJr — Living-Repo FAQ

Questions you will actually ask while using the new system.

## 1. New session: what do I do?

Paste two things:

```bash
git log --oneline -20
```

and the newest `sessions/*.md` file. BDS auto-loads `bds/` + memory.
Everything else is paste-first.

## 2. Where did a design decision go?

Depends on what it is:

- Single value → `facts.md`
- Rule built from it → skill
- Why / what was rejected → `sessions/<date>_<scope>.md`
- Assumption / open item → project doc
- Run result → `docs/test_log.md`
- Hot pointer → BDS memory (drifts; never the ledger)

## 3. I can't remember a fact. How do I find it?

Server up:

```
<BDS:AUTO:MCP url="pcjr-tools" tool="grep_repo" args='{"mode":"query","query":"carrier_high_us|gap2"}'></BDS:AUTO:MCP>
```

Server down, ask the assistant for the grep and paste the output:

```
git grep -n -i -E -C2 "carrier_high_us|burst_us|gap2" -- facts.md sessions docs
```

## 4. Do I ever edit an old facts.md line?

No. Append a new line with `supersedes:`. Old lines are history.

## 5. facts.md vs docs/ vs sessions/ — quick rule?

- `facts.md` = values (one per line).
- `docs/` = long derivations, provenance, run history (compiled views).
- `sessions/` = narrative: decisions, rationale, loose ends, next step.

## 6. What does the assistant see?

`bds/` (auto) + live MCP tools (`search_ref`, `debug_asm`, `grep_repo`)

- whatever you paste. It does NOT see `facts.md`, `sessions/`, `docs/`,
`refs/`, `mcp/`, `bin/` unless you paste them.

## 7. End of session: what exactly do I do?

The assistant emits a payload zip. Download it and run:

```
bin/jr-ingest.sh payload.zip
```

That appends the facts headings, session notes, and test-log entries,
then commits in one step. Manual alternative:

```
bin/jr-commit.sh "scope: <summary>" facts.md sessions/... docs/...
```

## 8. The two baseline commits touch bds/ and bin/. How?

Use the one-time escape:

```
bin/jr-commit.sh --setup "machinery baseline" bin/... refs/... mcp/...
bin/jr-commit.sh --setup "refactor baseline" facts.md sessions/... bds/... docs/... README.md MANIFEST.md
```

Or plain `git add -A && git commit -m "..."`. Default `jr-commit.sh`
stays narrow on purpose.

## 9. What does grep_repo cover?

`facts.md`, `sessions/`, `docs/` only. Stdlib, no git, fixed roots.
It is read-only by design; it can never mutate the repo.

## 10. Repo and BDS library disagree. Who wins?

Repo. Always. After every `skill_create`, sync the matching repo file.

## 11. How do I record a test run now?

Append an entry to `docs/test_log.md`; put any single reusable value in
`facts.md`; tell the story in the session file.

## 12. What about the old pcjr_* memory keys?

They are not migrated automatically. After approving the new no-prefix
batch, remove the old `pcjr_*` keys manually in the BDS memory UI. The
assistant cannot delete them.

## 13. How do I update a skill?

1. Edit the repo `bds/10_skills/*.md` file (source of truth).
2. Run the matching `skill_create` in BDS.
3. Confirm the library matches the repo.
Test overwrite semantics on the smallest edit first.

## 14. The migration script — safe to run twice?

Yes. Idempotent. Default is dry run:

```
python3 bin/migrate_repo.py
python3 bin/migrate_repo.py --apply
python3 bin/migrate_repo.py --apply --delete-superseded --yes
```

It never touches `refs/deepseek_reference.txt` or `pyproject.toml`.

## 15. Why does the migration script warn about max_delta=3528?

Recorded anchor is `3456`. `3528` is stale. Grep it down and fix before
committing.

## 16. I see a `; VERIFY:` tag in code. What now?

That value is unverified against the Tech Ref. Query `search_ref` before
using it on hardware, or explicitly accept it with a decision note.

## 17. When should I run IRPING?

Anytime transport looks wrong — before debugging new capture code.
Anchor first, then change one variable per iteration.

## 18. The server isn't running. What breaks?

`search_ref`, `debug_asm`, and `grep_repo` all go dark. Fallback:
paste-first `git grep` for the repo; for the manual, run
`python3 refs/pcjr_ref_tool.py refs/deepseek_reference.txt query "<term>" --context 3 --max-pages 1`
and paste the output.

## 19. How do I start a new scope?

When a session scope is done, recommend a new session. Copy the newest
handoff, name it `sessions/YYYY-MM-DD_new_scope.md`, and go.

## 20. Why no pcjr_ prefix on memory keys?

The keyword matcher splits on underscores and every message says "PCjr",
so `pcjr_*` keys fire like `always` and bloat context. Use `carrier_timing`,
`ch0_clock`, etc., and keep `always` keys near-empty.

## 21. What's inside an ingest payload?

`COMMIT.txt` (one-line commit message), `facts.append.md` (facts to
append, deduped by heading), `sessions/<date>_<scope>.md` (the new
session handoff), `docs/test_log.append.md` (only when a hardware run
happened), and optional `docs/anchors/<PROG>.BAS` / `<PROG>.ASM` (new
or restored ground-truth anchors). Repo files are never overwritten;
ingest appends and commits once. Run `bin/jr-ingest.sh payload.zip`.
