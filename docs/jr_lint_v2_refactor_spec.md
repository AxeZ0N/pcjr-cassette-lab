# jr lint v2 — refactor spec + implementation instructions

Status: normative for the implementing session. Single source of truth.
No code, config, deletion, or fact supersede happens in the authoring
session; everything below is executed next session in the phase order
given.

---

## 1. Scope

Refactor `jr` lint from a per-rule `min_stage` gate over three
rulesets into: one v2 config with `rules` / `groups` / `shapes`,
selection resolved as pure data, and opcode-aware checkers backed by a
single `ndisasm` decode per lint run.

Backward-compat contract: the default invocation `jr build x.asm`
changes its accept/block decision on **correct** code in zero cases.
The only default decision changes are on genuinely red code (see §5),
and both are consequences of approved A.

---

## 2. Config: single `jr_rules.json` v2

One file replaces `jr_rules.json`, `jr_rules_handler.json`,
`jr_rules_iret.json`. The two handler/iret files are deleted.

```json
{
  "version": 2,
  "rules": [
    { "id": "...", "kind": "...", "...": "..." }
  ],
  "groups": { "nmi": ["nmi-mask", "nmi-restore"] },
  "shapes": {
    "bridge":  { "rules": ["..."], "stage_presets": { "0": [], "1": ["..."], "...": ["..."], "6": ["..."] } },
    "handler": { "rules": ["..."] },
    "iret":    { "rules": ["..."] }
  }
}
```

Hard rules:

- `rules` is a list of self-contained objects; `id` appears once.
- Load-time validation: duplicate ids → error; any id referenced by a
shape, stage preset, or group must resolve → error naming the id.
- Load builds a `{id: rule}` index once; evaluation order is the list
order.
- No per-rule `min_stage` field exists.
- `groups` exist only as CLI sugar. Shapes and presets list concrete
rule ids, never group names. A group name in a shape/preset reference
is a load error that lists its members.
- Loader: `load_config()` returns the whole validated object. Remove
the old `.get("rules", [])` that silently discarded half the file,
and remove the str-path branch of the old `load_rules`.

---

## 3. Resolution pipeline

Three steps, no more.

```
shape -> rule list (bridge: stage_preset expansion)
      -> only/skip filter
      -> evaluate in list order
```

One pure function:

```
resolve_rules(config, shape, stage, only, skip) -> ordered rule list
```

- `shape` defaults to `bridge`.
- `stage` is valid only for `bridge`; for `handler`/`iret` it errors.
- `stage=0` resolves to the empty list.
- `only` restricts; `skip` removes; group tokens expand; both compose.
- Rule order is JSON list order; no separate ordering step.

`check_rule` loses its `stage` and `strict` parameters. `strict` was
dead weight (passed, never read). Severity escalation lives in `lint`.

---

## 4. Checker registry

Replace the 135-line `if/elif` chain with a dict:

```
CHECKERS = {"prefix", "suffix", "opcode-count", "opcode-absent",
            "before", "selfloc", "budget"}
```

Each checker is a small function taking
`(rule, data, decoded, ceiling, R)`.

### Decoded stream

`lint` runs `ndisasm -b 16` **exactly once**. `decoded` is the
per-instruction `(mnemonic, operands)` list handed to every opcode
checker as a first-class input, same status as `data`. `build` already
computes disasm for its return dict; that same text feeds lint, so the
common path adds no extra subprocess.

Consequence: split `decode()` (structured pairs) from `dis()` (raw
human text), and in `build` reorder disasm **before** lint so the one
subprocess serves both.

No homegrown instruction decoder. ndisasm is the existing spec §9
dependency. Hand-rolled decoding is the CH0CAL `38 D8` failure class.

### Checker semantics

| kind | input | logic |
|---|---|---|
| `prefix` | bytes | positional, unchanged |
| `suffix` | bytes | positional, unchanged |
| `opcode-count` | decoded | mnemonic + optional operand substring; op `eq`/`le`/`ge` |
| `opcode-absent` | decoded | mnemonic + optional operand substring must not appear |
| `before` | bytes | **unchanged**, keeps absence-inactive quirk (B) |
| `selfloc` | bytes | marker-derived (already correct in `jr.py`) |
| `budget` | bytes | length vs ceiling |

No offset reconciliation: mnemonic checkers are counts/absence; byte
checkers are positional. Neither needs the other. `8C CB` → `mov bx,cs`
clears the `retf-count` false positive; a `CF` immediate inside
`mov ax,0xcf00` clears the `iret-has-iret` false positive.

---

## 5. Shape rule sets

### bridge (stage 6 = full)

| id | kind | severity |
|---|---|---|
| entry | prefix `0E1F5506` | error |
| retf-count | opcode-count `retf` == 1 | error |
| epilogue | suffix `075DCB` | error |
| no-int21h | opcode-absent `int` + `21` | error |
| no-iret | opcode-absent `iret` | **error** (was warn) |
| no-speaker | opcode-absent `out` + `61` | **error** (was warn) |
| selfloc | selfloc | error |
| budget | budget | error |
| latch-read | before (byte) | warn |
| nmi-mask | before (byte) | warn |
| nmi-restore | suffix (byte) | warn |

Stage presets (explicit full lists, not incremental):

- 0: `[]`
- 1: entry, retf-count, epilogue, no-int21h, no-iret, no-speaker
- 2: + selfloc
- 3: + budget
- 4: + latch-read
- 5: + nmi-mask, nmi-restore
- 6: stage-5 list (strict **not** implied)

### handler (3-byte entry, no ES)

| id | kind | severity |
|---|---|---|
| handler-entry | prefix `0E1F55` | error |
| retf-count | opcode-count `retf` == 1 | error |
| handler-epilogue | suffix `5D5350CB` | error |
| no-int21h | opcode-absent | error |
| no-iret | opcode-absent `iret` | **error** (was warn) |
| no-speaker | opcode-absent | **error** (was warn) |
| selfloc | selfloc | error |
| budget | budget | error |

### iret (3-byte entry, no ES)

| id | kind | severity |
|---|---|---|
| iret-entry | prefix `0E1F55` | error |
| iret-retf-count | opcode-count `retf` == 0 | error |
| iret-has-iret | opcode-count `iret` == 1 | error |
| iret-epilogue | suffix `5DCF` | error |
| no-int21h | opcode-absent | error |
| no-speaker | opcode-absent | **error** (was warn) |
| selfloc | selfloc | error |
| budget | budget | error |

---

## 6. Severity and strict

- `strict` is optional, orthogonal, never implied. Not by stage 6, not
by any shape. Stage-6 + `strict=False` reports warnings and passes
exactly as today.
- Default: warnings reported, errors block; `strict` escalates warns to
errors only when passed.
- Deliberate default change under A: `no-iret` and `no-speaker` move
warn → error in all shapes. Green code is unaffected; red code now
fails. Flag this in facts at close.

---

## 7. CLI

```
jr build SRC.asm   [--shape bridge|handler|iret] [--stage 0-6]
                   [--only ids] [--skip ids] [--strict]
                   [--result R] [--ceiling N] [--uasm path] [--keep]

jr lint FILE.bin   [same selection flags]
```


- `--rules` removed from both subcommands. CLI argparse rejects it
with rc=2 (`unrecognized arguments`) before the engine's friendly
`use --shape handler|iret` message can fire; FastMCP drops the unknown
key silently. Recorded as spec drift; the friendly message is MCP-only.
- `--stage` bridge-only; `--stage` with `handler`/`iret` errors.
- `--only`/`--skip` take comma-separated ids and group names.
- Always print the active selection:
`shape=bridge stage=6 rules=entry,retf-count,...` or `SKIPPED: nmi-restore`.

---

## 8. MCP surface

- Add params `shape`, `only`, `skip`.
- Retire `rules`.
- `only`/`skip` are JSON string arrays.
- User-applied server change; server restart required.

---

## 9. Emission

- `build --stage=0`: compile-only, no rules run, status `pass`, no
warnings. Fixes the current `warnings = "LINTING SKIPPED"` →
`status="warn"` bug.
- `--only`/`--skip`: emission normal, no gate, no banner beyond the
always-printed selection line.
- Selfloc invariant: if `selfloc` active and `--result` absent → error.

---

## 10. Cleanups

1. Delete dead code `jr.py:457–459` (unreachable, references undefined
`ret`).
2. Delete `refs/jr-tools/jr_rules_handler.json` and
`refs/jr-tools/jr_rules_iret.json`.
3. Remove `load_rules` str-path branch.

---

## 11. Docs

Update:

- `docs/jr_tool_spec.md` — §2 scope (opcode-aware linter, no homegrown
decoder), §4 rules-as-data (v2 schema/shapes/groups, no `min_stage`),
§6 stage gating (presets as data, stage-0 legal, strict orthogonal),
and the Stage Gate table (full preset lists, drop "+ strict=true" on
stage 6).
- `refs/jr-tools/jr-manual.md` — CLI surface (`--rules` gone, new
flags).
- Test-workflow skill: remove "stage 6 + strict=true" from the Stage
Gate table only; user re-imports per `skill_create_semantics`.
- `refs/jr-tools/test_jr.py` — update for new resolution, dispatch, and
stage-0 semantics.

---

## 12. Facts ledger (at implementing-session close)

`facts.append.md` must carry:

- `supersedes: jr_handler_ruleset_added`
- `supersedes: jr_iret_ruleset_added`

…because those facts point at files being deleted. Plus new facts for:
single-config consolidation, shape/only/skip surface, strict
decoupling, and the A-driven severity escalation.

---

## 13. Open verification items

1. **Pin ndisasm exact rendering** for `int 21`, `iret`, `out 61` from
a real `jr dis` run on a known-good anchor. Do not guess. Expected
forms to verify: `int 0x21`, `iret`, `out 0x61,al`.
2. **Read back `jr_rules.json` v2 after paste** — the
`jr_rules_json_truncation` fact is the standing lesson.

---

## 14. Non-goals

No full instruction decoder. No per-shape rule duplication. No
incremental presets. No plugin/class hierarchy. Seven checker kinds,
one registry, one resolution function, one config file.

---

## 15. Implementation plan (ordered, gated)

### Phase 0 — pin the matcher strings (retrieval gate)

Pull a known-good anchor (`IRPING2` preferred, `CH0CAL` fallback), run
`jr dis` via MCP on its bytes, record the exact ndisasm renderings of
`int 21`, `iret`, `out 61`. Do not proceed to Phase 2 until this is
pinned and recorded.

### Phase 1 — mechanical prep (independent patch)

- Stage-0 legality in both `build()` and `lint()`.
- Stage-0 status bug (`LINTING SKIPPED` → `warn`).
- Dead-code deletion.
- Selfloc message text `R − 6` → `R − entry` across the three rulesets
and spec prose.

### Phase 2 — engine revamp

- `load_config()` + validated id index.
- `resolve_rules()` pure function.
- Checker registry; `opcode-count`/`opcode-absent` using pinned
matchers.
- `decode()`/`dis()` split; `build` reorder disasm before lint.
- CLI `--shape`/`--only`/`--skip`; `--rules` retirement.

### Phase 3 — config v2

- Emit single `jr_rules.json` v2 once.
- Read back and verify in full before considering it done.
- Delete the two old ruleset files.

### Phase 4 — docs, skill, tests

- Per §11.

### Phase 5 — MCP schema

- User applies `shape`/`only`/`skip`, retires `rules`, restarts server.

### Phase 6 — regression

- Relint IRPING2 and CH0CAL against v2; confirm pass.
- Do not fold `jr_tool_spec_fixture_stale` closure into this scope
unless separately authorized.

### Phase 7 — close

- Payload: `COMMIT.txt`, `facts.append.md` (the two supersedes plus new
facts), session handoff.
- **No `docs/test_log.append.md`** — documentation/tooling scope, no
hardware run.

---

## 16. Emission discipline

- Surgical patch specs for `jr.py` and docs; never wholesale
re-emission of the 724-line file.
- Full v2 JSON emitted once, gated on the read-back in Phase 3.
- Keep one variable per iteration; do not advance past a failed gate.

