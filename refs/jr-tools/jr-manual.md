# jr — PCjr Bridge Byte Pipeline

`jr` assembles PCjr bridge assembly, checks it against named hardware invariants, and packages it as pasteable Cartridge BASIC DATA statements. It does not prove hardware safety — that remains the hardware stage gate's job.

Specification: [`../../docs/jr_tool_spec.md`](../../docs/jr_tool_spec.md)

---

## Installation

**Requirements**

- Python 3 (standard library only)
- `uasm` on PATH (or `--uasm /path/to/uasm`)
- `ndisasm` on PATH for `jr dis` and the lint decode pass

**Setup**

1. Make the tool executable:
       chmod +x refs/jr
2. Optionally add `refs/` to PATH or create a symlink in `/usr/local/bin`.

**UASM self‑test**

On first `jr build`, a one‑time check confirms that UASM produces unpadded output. The result is cached in `~/.jr_cache`. If UASM is updated, delete the cache to force a retest.

---

## Quick Start

Create a bridge source `demo.asm` using the canonical skeleton:

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
        lea  bp, [bp + 128 - 7]      ; result offset R = 128, entry = 7
        ; ... routine body ...
        in   al, 0A0h              ; clear keyboard latch
        mov  al, 80h
        out  0A0h, al              ; re-enable NMI
        pop  es
        pop  bp
        retf

    code ends
    end start

Build it:

    jr build demo.asm

Output:

    shape=bridge stage=6 rules=entry,retf-count,epilogue,no-int21h,no-iret,no-speaker,selfloc,budget,latch-read,nmi-mask,nmi-restore
    PASS: demo.asm -> demo.bin (21 bytes, R=128) -> demo.bas

Inspect the emitted BASIC:

    jr data demo.bin

Verify a typed listing against the binary:

    jr verify demo.bas demo.bin

Output:

    verify: demo.bas matches demo.bin (21 bytes)

---

## Subcommand Reference

### `jr build SRC.asm [options]`

Assemble, lint, emit `SRC.data` and generate `SRC.bas`.

| Option       | Description                                      |
|--------------|--------------------------------------------------|
| `--shape S`  | Rule shape: `bridge` (default), `handler`, `iret` |
| `--stage N`  | Bridge development stage (0–6, default 6). Bridge-only. |
| `--only ids` | Restrict to comma-separated rule ids / group names |
| `--skip ids` | Remove comma-separated rule ids / group names |
| `--result R` | Explicit result offset (default: 128 if ≤128 bytes, else 180) |
| `--ceiling C`| Maximum allowed code length (default 180)        |
| `--strict`   | Escalate warnings to errors                      |
| `--uasm P`   | Path to UASM executable                          |
| `--keep`     | Keep intermediate files on failure               |

Exit codes: `0` success, `1` usage, `2` UASM failure, `4` lint failure, `5` loader/emission failure.

`--rules` is retired. The CLI argparse rejects `--rules` with rc=2 before
the engine's friendly `use --shape handler|iret` message can fire.

### `jr lint FILE.bin [options]`

Lint only. Same selection options as `build` (except `--uasm`). Requires
`--result` if the `selfloc` rule is active. `--stage` is bridge-only;
`handler`/`iret` shapes reject `--stage`.

`--stage 0` is legal: compile-only, no rules run, status `pass`.

Exit codes: `0` no errors (and no warnings under `--strict`), `4` otherwise.

### `jr verify NAME.bas NAME.bin`

Parse BASIC DATA and byte‑compare to binary.

Exit codes: `0` match, `6` mismatch, `7` parse error.

### `jr golden NAME.bas [--out FILE.bin]`

Extract bytes from a typed listing into a binary file. Default output `NAME.golden.bin`.

Exit codes: `0` success, `7` parse error.

### `jr dis FILE.bin`

Run `ndisasm -b 16 FILE.bin` for human inspection.

### `jr data FILE.bin`

Print DATA lines (uppercase hex, `&H` prefix) ending with `DATA -1`.

### `jr parse NAME.bas [--out FILE.bin]`

Extract DATA bytes from BASIC. Tolerates optional line numbers, `&H`/`&h`, comma/whitespace variation, multiple `DATA` per line (via `:`), trailing comments.

Exit codes: `0` success, `7` parse error.

---

## Shape Rule Table

### bridge (stage 6 = full)

| ID           | Kind            | Severity | Checks |
|--------------|-----------------|----------|--------|
| `entry`      | prefix `0E1F5506` | error  | `push cs / pop ds / push bp / push es` |
| `retf-count` | opcode-count    | error  | Exactly one `retf` |
| `epilogue`   | suffix `075DCB` | error  | `pop es / pop bp / retf` |
| `no-int21h`  | opcode-absent   | error  | No `int` with operand `21` |
| `no-iret`    | opcode-absent   | error  | No `iret` |
| `no-speaker` | opcode-absent   | error  | No `out` with operand `61` |
| `selfloc`    | selfloc         | error  | `lea bp,[bp+disp]` displacement equals `R - 7` |
| `budget`     | budget          | error  | Code size ≤ ceiling (default 180) |
| `latch-read` | before (byte)   | warn   | Timer reads (40/41/42) preceded by latch idiom |
| `nmi-mask`   | before (byte)   | warn   | `in al,62h` preceded by NMI mask |
| `nmi-restore`| suffix (byte)   | warn   | If A0h/62h touched, restore NMI before `pop es / pop bp / retf` |

Stage presets: `0` none, `1` entry/retf-count/epilogue/no-int21h/no-iret/no-speaker, `2` + selfloc, `3` + budget, `4` + latch-read, `5` + nmi-mask/nmi-restore, `6` stage-5 list (strict not implied).

### handler (3-byte entry, no ES)

| ID           | Kind            | Severity |
|--------------|-----------------|----------|
| `handler-entry` | prefix `0E1F55` | error |
| `retf-count`    | opcode-count `retf` == 1 | error |
| `handler-epilogue` | suffix `5D5350CB` | error |
| `no-int21h`  | opcode-absent | error |
| `no-iret`    | opcode-absent `iret` | error |
| `no-speaker` | opcode-absent | error |
| `selfloc`    | selfloc | error |
| `budget`     | budget | error |

### iret (3-byte entry, no ES)

| ID           | Kind            | Severity |
|--------------|-----------------|----------|
| `iret-entry` | prefix `0E1F55` | error |
| `iret-retf-count` | opcode-count `retf` == 0 | error |
| `iret-has-iret`   | opcode-count `iret` == 1 | error |
| `iret-epilogue`   | suffix `5DCF` | error |
| `no-int21h`  | opcode-absent | error |
| `no-speaker` | opcode-absent | error |
| `selfloc`    | selfloc | error |
| `budget`     | budget | error |

**Canonical idiom:** Use `mov al,imm` (not `xor al,al`, `sub al,al`, or `and al,0`). The linter flags non‑canonical zeroing.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0    | Success |
| 1    | Usage error |
| 2    | UASM assemble failure, or argparse rejection of unknown args |
| 4    | Lint failure (error rule or `--strict` warning) |
| 5    | Build emission/loader failure (`R < code_len`, file I/O) |
| 6    | Verify/golden byte mismatch |
| 7    | Parse error |

---

## FAQ

**Why does my code pass lint but still fail on hardware?**  
Static checks only warn about named hazards. Algorithm and timing bugs are not detectable by byte analysis — always test on hardware.

**Can I use `xor al,al` instead of `mov al,0`?**  
No. The canonical idiom policy requires `mov al,imm` for uniformity and machine‑checkability.

**What does `opcode-absent iret` mean now that it's an error?**  
An actual `iret` instruction was decoded. In bridge/handler shapes that is a hard failure; in the `iret` shape `iret == 1` is required and `retf == 0` is enforced instead.

**What is the correct selfloc displacement?**  
For a Contract-A bridge, `R - 7`. The `get_ip` label is at offset 7, not 6. `lea bp,[bp+121]` targets `R=128`.

**How do I raise the budget ceiling?**  
Use `--ceiling N` (default 180). But if code exceeds 180 bytes, reconsider algorithm or split routine.

**What are stages?**  
Bridge-only development stages gate rules by maturity. `stage=0` is compile-only; `stage=6` is the full set. `handler`/`iret` shapes do not take a stage.

**How do I select a subset of rules?**  
Use `--only ids` and `--skip ids` with comma-separated rule ids or group names (e.g. `--only nmi,entry`).

**What happened to `--rules`?**  
Retired. The CLI argparse rejects it (rc=2). The engine-level retirement message is MCP-only.

**What happens if `jr build` fails?**  
No new `.data` or `.bas` are written. Pre‑existing outputs are left untouched. Use `--keep` to retain intermediate files for debugging.
