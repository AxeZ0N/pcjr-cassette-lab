# `jr` — PCjr bridge byte pipeline specification

**Version:** 2.0 (lint v2 config + opcode-aware checkers)
**Status:** normative — matches the shipped `refs/jr-tools/jr.py` and
`refs/jr-tools/jr_rules.json` v2, with the inline-first MCP surface
(asm_text / bin_hex / bas_text) added 2026-08-28.
**Audience:** implementer with no prior PyCJr context.

This document is sufficient to implement the `jr` tool, its default
shape configuration, the loader template, and the self-verification
fixtures. When prose and a normative block disagree, the normative block
wins:

- Section 4, the v2 `jr_rules.json` config
- Section 5, the loader template
- Section 9, the fixtures

---

## 0. Conventions and reading guide

Writing rules for this spec:

1. Every lint rule cites a hardware fact: a `facts.md` heading, a session
   file, or a manual entry. No rule exists without evidence.
2. No byte pattern appears without its mnemonic equivalent. The reader
   must be able to translate bytes to instructions by eye.
3. Every failure message prints **expected vs found**. A bare "missing"
   message on correct-but-non-canonical code erodes trust.
4. No static check claims to prove hardware safety. The hardware stage
   gate is the only proof.

Terminology:

- **`R`** — result region offset from the code base.
- **ceiling** — maximum allowed code length in bytes.
- **stage** — development stage 0..6; `stage=0` is legal (compile-only).
- **shape** — one of `bridge`, `handler`, `iret`; selects a rule list.
- **preset** — a named, explicit rule-id list for one bridge stage.
- **`jr`** — the single CLI described in Section 3.
- **DATA block** — Cartridge BASIC `DATA &H..,&H..` lines terminated by
  a `-1` sentinel, the canonical pasteable machine-code carrier.

## 1. Thesis and history

`jr` is a byte pipeline for IBM PCjr bridge code. It assembles, lints a
set of *named* hardware invariants, emits pasteable Cartridge BASIC DATA,
and verifies the typed listing against the assembled image.

It is **not** a proof system. It is a checklist of the failures this
project has already paid for.

Four failures define the rule set:

1. **S1 v2 (2026-08-25).** A routine passed the old emission gate and
   rebooted the PCjr into BIOS on the first NMI. Static checks do not
   prove hardware safety; they only warn about named hazards.
2. **The +128 trap (2026-08-25).** `lea bp,[bp+128]` instead of `+121`
   shifts every result store seven bytes high. The selfloc displacement
   is arithmetic nobody should do by hand.
3. **CH0CAL `38 D8` gap (2026-08-25).** A `cmp ax,bx` emitted ungated
   because the old decoder didn't cover it. An opcode whitelist is a
   proxy for hazards not yet named.
4. **ST2B ripple (2026-08-27).** Single-poll edge detection latched AGC
   ripple dips, producing trimodal spans. The defect was in the
   algorithm, not the bytes. `jr`'s job there is to rule out the byte
   layer so the human attacks the real variable.

Division of labor:

| Concern | Owner |
|---|---|
| Branch range, undefined/duplicate labels, malformed operands | UASM |
| Named PCjr invariants (entry, selfloc, retf, counter latch, NMI, budget) | `jr lint` |
| Retyped-listing drift, anchor migration | `jr verify`, `jr golden` |
| Algorithm/timing bugs, final safety proof | hardware stage gate |

## 2. Scope and boundaries

`jr` does:

- Assemble `.asm` to `.bin` via UASM `-bin`.
- Lint `.bin` against an opcode-aware rule table, selected by `--shape`
  and gated by `--stage` (bridge only).
- Emit Cartridge BASIC DATA and a generated loader, producing a complete
  `.bas` ready to paste.
- Verify a typed `.bas` against the assembled `.bin`.
- Extract a golden `.bin` from an existing anchor `.bas`.

`jr` does **not**:

- Prove hardware safety.
- Implement a homegrown instruction decoder. `jr` runs `ndisasm -b 16`
  exactly once per lint run; opcode checkers consume that decoded stream
  as a first-class input. Hand-rolled decoding is the CH0CAL `38 D8`
  failure class.
- Replace a general-purpose assembler. UASM assembles; `jr` does not own
  encoding.
- Catch algorithm/timing bugs. Those are the hardware gate's job.

## 3. Architecture

One CLI, `jr`, with subcommands:

```

jr build  SRC.asm   [options]   assemble -> lint -> emit .data + loader .bas
jr lint   FILE.bin  [options]   lint only
jr verify NAME.bas NAME.bin     parse .bas, byte-compare to .bin
jr golden NAME.bas [--out F]    parse .bas, write golden .bin
jr dis    FILE.bin              run ndisasm -b 16 (human listing)
jr data   FILE.bin              bytes -> DATA lines + -1 sentinel
jr parse  NAME.bas [--out F]    extract DATA from a typed listing -> .bin

```

### 3.0 Inline surface (2026-08-28, MCP)

The MCP `jr` tool accepts inline string inputs in addition to file paths.
Inline is preferred for development; file inputs only for persistence.

| Param | Replaces | Carries |
|---|---|---|
| `asm_text` | `src` path | full UASM source text |
| `bin_hex` | `binfile` path | raw bytes as uppercase hex, no `0x`/`&H` |
| `bas_text` | `bas` path | full typed BASIC listing |

`build` accepts `asm_text` OR `src`; `lint`/`dis`/`data` accept `bin_hex`
OR `binfile`; `parse` accepts `bas_text` OR `bas`.

### 3.1 Data flow

```

SRC.asm
| uasm -bin -Fl -Fo
v
SRC.bin
| jr lint (shape/stage-gated rules, ndisasm-backed)
v
SRC.data  (DATA lines + -1)
|

- loader template (Section 5) -> SRC.bas

typed SRC.bas
| jr parse
v
extracted.bin -> jr verify / jr golden

```

`build` runs lint **before** emitting `.data`/`.bas`. A failed lint leaves
no new `.data` or `.bas` artifact.

### 3.2 Dependencies

- Python 3, standard library only.
- `uasm` on PATH (or `--uasm /path/to/uasm`).
- `ndisasm` on PATH for `jr dis` and for the lint decode pass.

No capstone. No Makefile. No MCP in the byte path.

### 3.3 UASM invocation and source skeleton

```

uasm -bin -Fl -Fo out.bin src.asm

```

UASM requires a segment wrapper even in `-bin` mode. The canonical bridge
source skeleton (Contract-A, with ES preservation):

```asm
option casemap:none
option segment:use16

code segment
    assume cs:code
    org 0

start:
    push cs
    pop  ds
    push bp
    push es
    call get_ip
get_ip:
    pop  bp
    lea  bp, [bp + N - 7]      ; N = result offset R (N-7 is the disp)
    ; ... routine body ...
    in   al, 0A0h              ; clear keyboard latch
    mov  al, 80h
    out  0A0h, al              ; re-enable NMI
    pop  es
    pop  bp
    retf

code ends
end start
```

`org 0` pins offset 0 to the first byte. The output `.bin` must have no
header and no padding.

Contract-A entry arithmetic: the `get_ip` label lands at offset 7
(`push cs` / `pop ds` / `push bp` / `push es` = 4 bytes, `call get_ip` =
3 bytes). After `pop bp`, BP holds `O + 7`, so the selfloc displacement
must be `R - 7`. The old `R - 6` arithmetic was pre-Contract-A and is
wrong.

The bridge shape requires ES preservation (`push es` after `push bp`,
`pop es` immediately before `pop bp`). Clobbering BP or ES corrupts
Cartridge BASIC on return. See `facts.md` headings `bridge_bp_preserve`
and `es_clobber_bridge_contract`.

### 3.4 One-time UASM padding self-test

On the first `jr build` run of a new installation, `jr` must prove the
UASM dialect produces unpadded output:

1. Assemble a source containing only `retf` (`CB`) with the segment
wrapper above.
2. Assert the output file is exactly one byte (`CB`).

If not, the implementation must report that UASM `-bin` is padding and
stop. This is a one-time check cached under the install's config dir.

## 4. Rules as data

The linter is a small engine over a single v2 config. One config file
replaces the old `jr_rules.json` + `jr_rules_handler.json` +
`jr_rules_iret.json` split. Selection is resolved as pure data.

### 4.1 Config schema

```
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

- `rules` is a list of self-contained objects; each `id` appears once.
- Load-time validation: duplicate ids are an error; any id referenced by
a shape, stage preset, or group must resolve or the load errors naming
the missing id.
- Load builds a `{id: rule}` index once; evaluation order is list order.
- No per-rule `min_stage` field exists. Stage gating is expressed as
explicit preset lists, never as incremental sums.
- `groups` exist only as CLI sugar. Shapes and presets list concrete rule
ids, never group names. A group name in a shape/preset reference is a
load error that lists its members.

### 4.2 Checker kinds

| kind ↕▾ | input ↕▾ | logic ↕▾ |
|---|---|---|
| −`prefix` | bytes | positional prefix match, unchanged |
| −`suffix` | bytes | positional suffix match, unchanged |
| −`opcode-count` | decoded | mnemonic + optional operand substring; op `eq`/`le`/`ge` |
| −`opcode-absent` | decoded | mnemonic + optional operand substring must not appear |
| −`before` | bytes | unchanged; keeps the absence-inactive quirk |
| −`selfloc` | bytes | marker-derived displacement equals `R - entry` |
| −`budget` | bytes | code length vs ceiling |
⚙

No offset reconciliation: mnemonic checkers are counts/absence; byte
checkers are positional. Neither needs the other. `8C CB` → `mov bx,cs`
clears the `retf-count` false positive; a `CF` immediate inside
`mov ax,0xcf00` clears the `iret-has-iret` false positive. This is why
the decoded stream from the single `ndisasm` pass is authoritative for
opcode checkers.

### 4.3 Resolution pipeline

Three steps, no more:

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
- `stage=0` resolves to the empty list (compile-only, status `pass`).
- `only` restricts; `skip` removes; group tokens expand; both compose.
- Rule order is JSON list order; no separate ordering step.

### 4.4 Shape rule sets

#### bridge (stage 6 = full)

| id ↕▾ | kind ↕▾ | severity ↕▾ |
|---|---|---|
| −entry | prefix `0E1F5506` | error |
| −retf-count | opcode-count `retf` == 1 | error |
| −epilogue | suffix `075DCB` | error |
| −no-int21h | opcode-absent `int` + `21` | error |
| −no-iret | opcode-absent `iret` | error |
| −no-speaker | opcode-absent `out` + `61` | error |
| −selfloc | selfloc | error |
| −budget | budget | error |
| −latch-read | before (byte) | warn |
| −nmi-mask | before (byte) | warn |
| −nmi-restore | suffix (byte) | warn |
⚙

Stage presets (explicit full lists, not incremental):

- 0: `[]`
- 1: entry, retf-count, epilogue, no-int21h, no-iret, no-speaker
- 2: + selfloc
- 3: + budget
- 4: + latch-read
- 5: + nmi-mask, nmi-restore
- 6: stage-5 list (strict **not** implied)

#### handler (3-byte entry, no ES)

| id ↕▾ | kind ↕▾ | severity ↕▾ |
|---|---|---|
| −handler-entry | prefix `0E1F55` | error |
| −retf-count | opcode-count `retf` == 1 | error |
| −handler-epilogue | suffix `5D5350CB` | error |
| −no-int21h | opcode-absent | error |
| −no-iret | opcode-absent `iret` | error |
| −no-speaker | opcode-absent | error |
| −selfloc | selfloc | error |
| −budget | budget | error |
⚙

#### iret (3-byte entry, no ES)

| id ↕▾ | kind ↕▾ | severity ↕▾ |
|---|---|---|
| −iret-entry | prefix `0E1F55` | error |
| −iret-retf-count | opcode-count `retf` == 0 | error |
| −iret-has-iret | opcode-count `iret` == 1 | error |
| −iret-epilogue | suffix `5DCF` | error |
| −no-int21h | opcode-absent | error |
| −no-speaker | opcode-absent | error |
| −selfloc | selfloc | error |
| −budget | budget | error |
⚙

The authoritative copy is the v2 `jr_rules.json`; this section is the
summary. When they disagree, the JSON wins.

## 5. Loader template

The generated `.bas` uses the float16-safe loader (verified
2026-08-28):

```

10 DEFINT A-Z
20 DIM A(__DIM__)
30 I = 0 : O = 0 : X$ = "" : B = 0 : D = 0
40 ST = 0 : RI = 0 : FA = 0
50 I = 0
60 READ D
70 IF D = -1 THEN 110
80 POKE VARPTR(A(0)) + I, D
90 I = I + 1
100 GOTO 60
110 PRINT "Loaded "; I; " bytes. Press Enter to CALL..."
120 INPUT X$
130 O = VARPTR(A(0))
140 CALL O
150 PRINT "RETURNED OK"
160 ST = PEEK(VARPTR(A(0)) + __RESULT__)
170 RI = PEEK(VARPTR(A(0)) + __RESULT__ + 2) + 256! * PEEK(VARPTR(A(0)) + __RESULT__ + 3)
180 FA = PEEK(VARPTR(A(0)) + __RESULT__ + 4) + 256! * PEEK(VARPTR(A(0)) + __RESULT__ + 5)
190 PRINT "status="; ST; " rising="; RI; " falling="; FA
200 END

```

`__DIM__` is sized to cover the code length plus the result region;
`__RESULT__` is the result offset (default 128). The `256!` multiplier is
mandatory — Cartridge BASIC's `DEFINT` overflows above 32767.

## 6. Stage gating

`jr build --stage N` activates the bridge shape's `stage_presets[N]`
list. Rules with `severity: "warn"` block only under `--strict`. Stage
gating is bridge-only; `--stage` with `handler`/`iret` is a usage error.

- `stage=0` is legal: no rules run, status `pass`, no warnings. It is
compile-only.
- `build` defaults to `stage=6` when no `stage` is given (empirical,
2026-08-28) — pass `stage=1` explicitly for a bare bridge stub.
- `strict` is optional, orthogonal, and never implied — not by stage 6,
not by any shape. Stage-6 + `strict=False` reports warnings and passes
exactly as today.

Stage Gate table:

| Stage ↕▾ | New risk ↕▾ | Lint rules active ↕▾ | Hardware pass condition ↕▾ |
|---|---|---|---|
| −0 | None (compile-only) | (none) | N/A |
| −1 | Bridge stub | entry, retf-count, epilogue, no-int21h, no-iret, no-speaker | Returns RETURNED OK |
| −2 | Self-location | + selfloc | Writes known byte at O+R |
| −3 | Result stores | + budget | BASIC reads expected values |
| −4 | IN from target port | + latch-read | Status changes as documented |
| −5 | Polling loop | + nmi-mask, nmi-restore | Edges observed on stimulus |
| −6 | Full capture | stage-5 list (strict not implied) | All contract fields match |
⚙

## 7. CLI selection surface

```

jr build SRC.asm   [--shape bridge|handler|iret] [--stage 0-6]
                   [--only ids] [--skip ids] [--strict]
                   [--result R] [--ceiling N] [--uasm path] [--keep]

jr lint FILE.bin   [same selection flags]

```

- `--shape` defaults to `bridge`.
- `--stage` is bridge-only; `--stage` with `handler`/`iret` errors.
- `--only`/`--skip` take comma-separated rule ids and group names.
- `--rules` is removed from both subcommands. The CLI argparse rejects it
with rc=2; the engine-level friendly `use --shape handler|iret` message
is unreachable on the CLI path (MCP only). Recorded as spec drift.
- Every run prints the active selection:
`shape=bridge stage=6 rules=entry,retf-count,...` or `SKIPPED: nmi-restore`.

## 8. Exit codes

- `0` success
- `1` usage error
- `2` UASM assemble failure, or argparse rejection of unknown args
- `4` lint failure (invariant violated, or warning under `--strict`)
- `5` build emission/loader failure (`R < code_len`, file I/O)
- `6` verify/golden byte mismatch
- `7` parse error

## 9. Fixtures

Fixtures are the known-good anchor bytes. The normative fixture set is:

- IRPING stage-5 DATA — golden regression artifact.
- S4B1_ST2 — known-good stage-6 capture binary.

Each fixture must assemble, lint, and re-derive its DATA byte-exact.
When a fixture disagrees with this spec, the fixture's `.bin` is the
authority; this spec must be corrected to match.

The self-verification suite in `test_jr.py` uses synthetic Contract-A
fixtures; those are test artifacts, not hardware anchors. Anchor
regeneration for IRPING2/CH0CAL (pre-Contract-A) is a separate scope.

## 10. Security / process invariants

- No writes through the MCP server; `jr` file-output commands run under
the user's own invocation (CLI) or write only into the repo working
tree the user owns.
- The tool never invokes a network, never imports capstone, never shells
beyond `uasm` and `ndisasm`.

## 11. Migration note

`jr` supersedes `debug_asm` (`refs/pcjr_asm_debug.py`) and `pjasm`
(`refs/pcjrasm.py`) as the MCP byte-pipeline surface. `facts.md`
`jr_mcp_pipeline` records the transition. The lint v2 refactor replaces
the per-rule `min_stage` gate over three rulesets with one v2 config;
`facts.md` records `jr_handler_ruleset_added` and
`jr_iret_ruleset_added` as superseded.

Historical references elsewhere are append-only records, not current API.

