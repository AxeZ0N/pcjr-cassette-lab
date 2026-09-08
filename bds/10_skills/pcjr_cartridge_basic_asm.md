# IBM PCjr Cartridge BASIC & 8088 Assembly — Canonical Verified Skill (v8)

## Activation

Use whenever the user requests code or design help for the IBM PCjr
(4860/4861), PCjr Cartridge BASIC, PCjr 8088 assembly, or the PyCJr
IR link.

- Repo is source of truth; BDS library is a runtime cache. Git wins on
  drift.
- Session-fresh readings and every fact body live in `facts.md` and
  `docs/test_log.md`, never here. This skill carries invariants and
  pointers only.

## Target Platform

- CPU: Intel 8088 @ 4.77 MHz, 16-bit real mode
- BASIC: IBM Cartridge BASIC (PCjr-specific), NOT BASICA/GW-BASIC
- OS: optional PC-DOS 2.1. No `INT 21h` unless DOS is confirmed loaded.

## Primary Sources

1. IBM PCjr Technical Reference — via `pcjr-tools` MCP (`search_ref`
   for prose; `bios_grep` for the ROM BIOS listing).
2. IBM PCjr BASIC Reference
3. Ralf Brown's Interrupt List (RBIL)

Label every hardware fact: `manual-verified`, `empirical`,
`unverified`, or `conflict`. Unverified port/segment/vector values must
carry `; VERIFY: value against PCjr Technical Reference`.

Retrieval traps:

- The prose manual spells ports as BARE hex (`A0`, `41`, `62`), never
  `A0h`. Grep bare digits when locating register facts.
- Appendix A (ROM BIOS listing) is NOT in `search_ref`; it is the flat
  file `refs/ibm_pcjr-bios.lst` served by `bios_grep`.
- Full retrieval protocol lives in `pcjr_test_workflow`.

## Manual Locator

| Topic | Manual Location |
|---|---|
| Processor, performance, 8259A interrupt controller | 2-13 to 2-16 |
| 64KB RAM, ROM subsystem | 2-17 to 2-19 |
| I/O channel, system board I/O | 2-21 to 2-29 |
| 8255 bit assignments | 2-30 |
| Cassette interface | 2-39 |
| Video/graphics, palette, lightpen | 2-43 to 2-74 |
| Beeper, sound, SN76496 | 2-85 to 2-89 |
| Infra-Red Link, receiver | 2-97 |
| Cordless keyboard, transmitter | 2-101 to 2-103 |
| Program cartridge and interface | 2-107 to 2-114 |
| Games interface, joystick | 2-119 to 2-122 |
| Serial port RS232 | 2-125 to 2-130 |
| System power supply | 2-135 |
| BIOS usage, vectors, memory map | 5-5 to 5-13 |
| Keyboard encoding and usage | 5-21 to 5-42 |
| BIOS cassette logic | 5-47 to 5-51 |
| ROM BIOS listing | Appendix A |
| Characters, keystrokes, color | Appendix C |

## Rule 1 — Machine-Code Bridge (Hard Rule)

Use exactly this contract. No exceptions:

```basic
DEF SEG          ' code segment
O = VARPTR(A(0)) ' offset
CALL O           ' far call
```

The called machine routine MUST:

- start with `PUSH CS` / `POP DS` / `PUSH BP` / `PUSH ES`
(bytes `0E 1F 55 06`)
- preserve BP: `PUSH BP` at entry (after `POP DS`), `POP BP`
immediately before `RETF`. Clobbering BP corrupts the Cartridge
BASIC interpreter frame and yields `Division by zero in (blank)`
with a dead keyboard — unrecoverable, cold power-cycle only.
(empirical, 2026-08-25, S1 v1)
- preserve ES: `PUSH ES` at entry (immediately after `PUSH BP`),
`POP ES` immediately before `POP BP`. Clobbering ES corrupts BASIC
on return — bytes-corruption signature, keyboard alive but frozen
on string operations. (empirical, 2026-08-31,
es_clobber_bridge_contract)
- end with far `RETF` (opcode `0CBh`); epilogue bytes `07 5D CB`

Never emit `CALL ABSOLUTE` (evaluates to 0 in Cartridge BASIC, calls
offset 0 — hangs). Never emit `USR0` (black-screens).

## Rule 2 — Variable Ordering (Hard Rule)

- Pre-declare every scalar before `O = VARPTR(A(0))`.
- Creating any variable after `VARPTR` moves the array and invalidates `O`.
- `DEFINT` literals must not exceed 32767; use `DEFDBL` for values that
may overflow. 16-bit reads need the `!` suffix and `256!` multiplier.

## Rule 3 — Sentinel Loader (Mandatory Pattern)

Never use a manual byte-count loader; a wrong count omits the final
`RETF` and hangs. Always terminate `DATA` with `-1`.

Gate every run on the printed `loaded N bytes` count — it discriminates
DATA blocks. Full loader listing: `docs/anchors/BASLOAD.BAS`.

## Rule 4 — Position-Independent Result Storage (Mandatory)

Never store machine-code results at a hardcoded DS offset. Locate the
entry point at runtime:

```
    call get_ip              ; E8 00 00
get_ip:
    pop  bp                  ; 5D  BP = entry offset + 6
    lea  bp, [bp + 128 - 6]  ; 8D AE 7A 00  BP = entry offset + 128
```

Results go at `O+128`, matching `PEEK(VARPTR(A(0))+128)` in BASIC.

## Rule 5 — IRPING2 Regression

IRPING2 is the frozen 56-byte both-edge transport sampler for port `62h`
bit 6; pass = status=3. Re-run it first whenever transport is suspect.
IRPING2 passes -> transport sane, defect in new code. Anchors:
`docs/anchors/IRPING2.BAS` / `IRPING2.ASM`; `jr build` regenerates bytes.

## Rule 6 — Hardware Map

Full register table (8255 A/B/C, 8253 CH0/1/2, A0h bits, 8253 latch
commands) -> `facts.md` heading `hardware_map`.

Hard hazard inline: never latch/read `41h` (CH1) with keyboard NMI
active — kills the keyboard. Safe path: `OUT 43h,00h` (latch CH0) ->
`IN 40h`; never bare `IN` on any counter port.

## Rule 7 — NMI Rules

- Keyboard NMI vectors via INT `02h` at `0000:0008` -> KBDNMI.
- Latch = 8255 PC0. Fires NMI only if A0h D7 = 1.
- Clear = dummy `IN AL,0A0h`; restore = `OUT 0A0h,80h`.
- INT 02h IVT write act (byte-exact write/readback of the saved vector)
is safe on a fresh boot -> `facts.md` heading `int02_write_act_safe`.
- Full manual dispatch chain (entries 32/34/35/92/93/94/233/338) ->
`facts.md` heading `nmi_chain_detail`.

## Rule 8 — IR Protocol

All frozen protocol facts (carrier, emitter timings, frame spec,
emulator invariants) -> `facts.md` heading `ir_protocol_frozen`.

Emitter invariants in brief: always make+break, no typematic, no
lock-state tracking, atomic Shift, one key per wave.

## Rule 9 — Failure Mode Prohibitions

Never emit:

- `CALL ABSOLUTE` or `USR0`
- CGA planar/bitplane code (PCjr 16-color video is packed-pixel,
2 pixels/byte)
- `OUT 61h` speaker toggles (sound is TI SN76496)
- `INT 21h` unless DOS is confirmed loaded
- IBM PC ROM addresses (`F6000`, etc.); PCjr regions are `F0000`
(Cassette BASIC), `E8000` (cartridge selects), `FFFFF` (BIOS)
- Count-based machine-code loaders
- Hardcoded DS offsets for results
- Variables created after `VARPTR(A(0))`
- Any path that returns without re-enabling the keyboard:
dummy `IN AL,0A0h` (clear latch), then `OUT 0A0h,80h` (restore NMI)
- Custom INT 02h handler dispatch — untested, not pre-authorized

## Research Track

Phases, empirical clocks, and open items -> `facts.md` heading
`research_track_state`.

## Anchors

Ground truth lives in `docs/anchors/`, never here. Retype from those
files, never from session back-issues. DATA blocks in `.BAS` must
byte-match the corresponding `.ASM`; regenerate via `jr build`
(UASM emits `.data`/`.bas`), never hand-roll.

