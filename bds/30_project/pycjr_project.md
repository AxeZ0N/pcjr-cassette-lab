# PyCJr Project (v6)

Targets the IBM PCjr 4860/4861 and the Pi-side IR sender (pigpio,
GPIO18, 40 kHz carrier). No DOS by default; machine code runs through
the Cartridge BASIC bridge.

## Always-on

- Skills are authoritative: `pcjr_cartridge_basic_asm` (v8),
  `pcjr_test_workflow` (v10), `pcjr_payload_generation`. If absent from
  context, re-request them. Rules live in skills, never restated here.
- Repo = source of truth; BDS library = runtime cache. Git wins on
  drift. Read path: `grep_repo` MCP or user-pasted `git grep`.

## Assumptions

- All PCjr keyboard input arrives via the IR module. Pi passthrough:
  press or held key both emit make/break; held repeats frames. No
  physical keyboard; same input channel.
- Default: no DOS. BIOS interrupts only unless DOS is confirmed.

## Repo layout (v6 living repo)

```

PyCJr/
bds/                      # BDS import package
00_system_prompt.md
10_skills/*.md
20_persona/*.md
30_project/*.md
facts.md                  # append-only fact journal
sessions/                 # append-only narrative per scope
docs/                     # compiled views / archive, regenerable
mcp/  refs/  bin/  pyproject.toml

```

## Facts & session loop

`facts.md` is append-only, one fact per heading, updates via
`supersedes:`. Session files carry decisions, rationale, and
next-session pointer. Full record-payload contract lives in
`pcjr_payload_generation`; user ingests and commits. New session:
`git log --oneline -5` + latest session handoff.

## Hardware state (pointer)

Stable hardware facts live in `facts.md` headings `hardware_map`,
`ir_protocol_frozen`, `nmi_chain_detail`, `research_track_state`. Do
not restate values here; query them. CH0 clock is empirical and owned
by those headings.

## Open items (this file is the owner)

1. Timer-2 IR-test wrap verification (manual 2-85..2-89).
2. IR-test edge probe (mask NMI, A0h 40h, finite poll PC6).
3. RAM demodulator chaining unrecognized frames to the stock path.

## Volatile measurements

Per-session readings — edge counts, max_delta, gap counts, iteration
counts, pass results — belong in the session handoff, `facts.md`, and
`docs/test_log.md`, not in this file or the skills. Update the handoff
as experiments progress.
