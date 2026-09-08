# PCjr Design / Test Workflow (v10)

## Activation

Use for test/validate/verify/debug/regress of generated PCjr Cartridge
BASIC or 8088 assembly, or any machine-code experiment needing a
verification path.

- Repo is source of truth; BDS library is a runtime cache. Git wins on
  drift.
- `jr` is the single byte-pipeline tool (replaces `debug_asm`/`pjasm`).
  Inline inputs preferred; file inputs only for persistence.

## First-Move Gate (hard)

No code, files, or experiments until the user names the scope AND the
latest session handoff has been read. First response is a scope
confirmation plus retrieval plan. Ask before generating.

## Loop Order (always)

1. Spec first — contract before code.
2. Retrieve before emit (grep_repo / search_ref / bios_grep).
3. Generate in stages: bridge stub -> self-location -> result stores ->
   one `IN` from target port -> polling loop -> full capture.
4. Gate each stage; do not advance on failure.
5. Regress first when transport is suspect: IRPING2, then anchor.
6. Record the result; every run emits a result block.
7. Recover cold on hang; never assume Ctrl+Alt+Del recovers.

## Retrieval Gate (mandatory)

Before emitting any port, mode, segment, or vector value: locate the
manual section, query the MCP tools or user paste, then label
`manual-verified` / `empirical` / `unverified` / `conflict`. Never pass
an unverified value without `; VERIFY:`. The assistant has no local
shell; never claim it ran the util locally.

MCP: server `pcjr-tools`, endpoint `http://localhost:8765/mcp`.

Tool surface:

- `search_ref` — prose manual (Appendix A excluded; pages.jsonl joined
  as `meta`). Modes: `query` (ranked prose, front-matter skipped),
  `grep` (line-attributed hits: page_id + line + context), `peek` (raw
  page by 1-based index), `stats`.
- `bios_grep` — flat BIOS listing `refs/ibm_pcjr-bios.lst`. Modes:
  `grep` (line hits), `peek` (1-based line), `stats`.
- `grep_repo` — repo. Modes: `facts`, `all`, `files`, `ls`, `read`,
  `facts_headings`, `stats`, `roots`.
- `jr` — byte pipeline. Needs `command`.

Traps:

- `verbose: false` drops the request — omit the field or pass true.
- `peek` is 1-based in `search_ref` and `bios_grep`; `start=0` errors.
- `search_ref.peek` is STRIP-FILE ORDER, not physical page order:
  peek(1)=B-47. Locate with `query`/`grep`; peek only a known page.
- The prose spells ports as BARE hex (`A0`, `41`, `62`), never `A0h`.
  Grep bare digits. (`A0h` = 0 hits; `A0` ~ 70.)
- Hex tokens are OCR-normalized by default; `raw=true` opts out.
- Appendix A is NOT in `search_ref`; it is the BIOS listing served by
  `bios_grep`. First ~25 lines of the .lst are an ASCII header block;
  labels start past line 25.
- `pages.jsonl` is never a search index; it arrives as `meta` on page
  results only.
- All greps cap and report truthfully: `truncated` + `total_hits`/
  `total`. A capped result is never a true no-match.
- Required: `search_ref`, `grep_repo`, `bios_grep` need `mode`; `jr`
  needs `command`.

Fallback when MCP is down — ask the user to run and paste:

```

git grep -n -i -E -C2 "<terms>" -- facts.md sessions docs
grep -n -i -E "<term>" refs/pcjr_technical_reference.txt
grep -n -i -E "<term>" refs/ibm_pcjr-bios.lst

```

OCR is noisy: `I`/`1`, `O`/`0`, column drift. A single match is
evidence, not a clean fact. On conflict, record both sources and mark
`conflict`.

## jr byte pipeline

`jr build` (UASM) -> `jr dis` (NDISASM review) -> `jr lint` (named
invariants). Never hand-roll any byte or displacement.

- UASM requires a segment wrapper; skeleton in `docs/jr_tool_spec.md`
  section 3.3.
- `jr build` defaults to `stage=6`; pass `stage=1` explicitly for early
  stubs or the selfloc rule (min_stage 2) rejects them.
- `jr build` success returns a float16-safe loader: auto-sized
  `DIM A(...)` and `256!` multipliers.

## Emission Gate (mandatory)

No DATA block leaves a response unless produced by `jr build` at the
target stage and reviewed via `jr dis`. UASM owns instruction encoding;
`jr lint` owns invariants; NDISASM owns review. The gate proves
construction — it does not prove hardware safety.

## Test Contract (mandatory)

Every generated routine ships a contract block:

```

{
"id": "probe_id",
"source": "FILE.BAS",
"expected": { "return": "RETURNED OK", "...": "..." },
"regression": "IRPING2",
"recovery": "cold_power_cycle"
}

```

Fields generalize per routine; do not copy IRPING2's expectations into
a timer, video, or sound routine.

## Disproof Contract (mandatory)

Every hypothesis-driven experiment states its falsification logic in
the contract before running. "Disprove" and "fail to disprove" are
defined terms, not vibes.

```

{
"id": "...",
"hypothesis": "H — the claim under test",
"falsifier": "F — the exact observable that would disprove H",
"clean_run": "S — success criterion independent of H's outcome",
"verdict": "disproved | failed_to_disprove | no_result"
}

```

Rules:

1. **Disproved** — F was observed on a clean run. Record as an
   empirical fact. Supersede every fact or assumption that depended
   on H. The claim is dead.

2. **Failed to disprove** — F was NOT observed on a clean run. H
   survives this one test and nothing more. It is NOT proven, NOT
   manual-verified, NOT promoted to empirical fact. Record as
   "survived one disproof attempt." Do not advance a stage on
   failed-to-disprove alone.

3. **No result** — the run was not clean (hang, wrong loaded-N count,
   contamination, swallowed arming keystroke). Neither verdict
   applies. Fix the run and re-run; the disproof question stays open.

4. Clean is judged by the contract's `clean_run` field only — never by
   whether the observed outcome was the one the author wanted.

Non-normative examples:

- BITSAMP CH1-verbatim: H = "the CH0 clock conversion was a confound."
  F = "CH1-verbatim still decodes h -> bit=1." F observed -> H
  DISPROVED.
- 2026-08-28 scope "close on failed disproof": H = "CH1 wait overshoot
  is explained by the shorter loop." F = "overshoot disappears when
  loop cost is measured directly." F not observed -> failed to
  disprove; the overshoot anomaly remains open.

## Stage Gate (mandatory)

`jr build stage=N` activates every rule whose `min_stage <= N`. `.` =
error (blocks build); `!` = warn (blocks only under `strict=true`).

| Stage | New risk | Lint rules active | Hardware pass condition |
|---|---|---|---|
| 0 | None (compile-only) | (none) | N/A |
| 1 | Bridge stub | entry, retf-count, epilogue, no-int21h, no-iret, no-speaker | Returns RETURNED OK |
| 2 | Self-location | + selfloc | Writes known byte at O+R |
| 3 | Result stores | + budget (ceiling 180) | BASIC reads expected values |
| 4 | IN from target port | + latch-read | Status changes as documented |
| 5 | Polling loop | + nmi-mask, nmi-restore | Edges observed on stimulus |
| 6 | Full capture | stage-5 list (strict not implied) | All contract fields match |

Note: `strict` is orthogonal and never implied — not by stage 6, not by
any shape. Stage-6 + `strict=False` reports warnings and passes exactly
as before.

If a stage fails, the defect is in the bytes added in that stage. Fix
only that stage, then re-run.

## Anti-Patterns (never)

- Emitting code without a contract block.
- Advancing a stage without passing the previous gate.
- Burying an unverified port/segment/vector without `; VERIFY:`.
- Skipping IRPING2 when transport behavior looks wrong.
- Assuming any recovery other than cold power-cycle.
- Telling the assistant to run local tools/scripts itself — it has no
  shell.
- Trusting a manual value without search_ref/bios_grep output or
  pasted output.
- Treating a noisy OCR match as a clean manual fact.
- Silently overwriting an empirical fact with a single garbled query.
- Treating `search_ref.peek` indexes as physical page order; they are
  strip-file order.
- Grepping the prose for `A0h`-suffixed ports; the manual spells them
  bare (`A0`).
- Grepping Appendix A through `search_ref`; the BIOS listing lives in
  `bios_grep`.
- Reading a capped grep as a true no-match; check `truncated` and
  `total_hits`.
- Unbounded arm on 62h bit 6: KBDNMI de-serializes after the first
  edge when NMI is active. Mask NMI (`OUT A0h,00h`), finite loop,
  restore 80h before RETF.
- Swallowing the arming keystroke: add a delay or wait-for-edge.
- `jr build` at stage 6 on a stage-1 stub without `stage=1`.
- Calling a failed-to-disprove result "verified", "confirmed", or
  "empirical". It is none of those.

## Debug Anchor Rule

Before debugging a failing capture, re-run the last known-good probe
with identical stimulus. Anchor passes -> transport sane, defect in
changed code. Anchor fails -> run IRPING2 first. Change one variable per
iteration. Anchor identities -> `facts.md` heading `anchor_identities`.
Recorded readings live in session handoff / facts / test_log, never
here.

## Anchor Ground Truth and Retype Path

- Ground truth lives in `docs/anchors/<PROG>.BAS` and
  `docs/anchors/<PROG>.ASM`. Retype from those files — never from
  session back-issues.
- A program earns its anchor files in the same session it first passes
  hardware. Never defer anchor file creation.
- DATA blocks must byte-match the ASM via `jr build`; hand-rolled bytes
  are a process violation.
