# PCjr Payload Generation — Session-Close Record Emitter (v3)

## Activation

Use at the end of a PyCJr session when the user asks to emit the record
payload. Repo is source of truth; re-read the ingest contract from
`facts.md` heading `ingest_payload` and `docs/FAQ.md` §7/§21 before
emitting. Repo wins over this skill on drift.

## Payload contract

Payload = a zip emitted through BDS LONG_WORK with BDS:create_file per
file. Members are two classes: append journals and replacement files.
The user runs `bin/jr-ingest.sh <payload.zip>`; the script validates
members, applies them, and commits in one step.

Append journals:

- `COMMIT.txt` — one-line commit message (required).
- `facts.append.md` — facts to append to `facts.md`.
- `sessions/<date>_<scope>.md` — the new session handoff file.
- `docs/test_log.append.md` — ONLY if a hardware run happened.

Replacement files (full-file, allowlisted — never append):

- `bds/00_system_prompt.md`
- `bds/10_skills/*.md`
- `bds/20_persona/*.md`
- `bds/30_project/*.md`
- `docs/anchors/<PROG>.{BAS,ASM,bin,data}` — only when adding or
  restoring a ground-truth anchor.

`bin/` is not ingestible; script edits are manual.

Append journals are never overwritten. Allowlisted replacement files
are replaced whole. Any zip member outside these classes is a hard
error and nothing is written. `jr-ingest.sh` owns this enforcement;
never hand-unzip a payload.

## facts.append.md rules

- One `##` heading per fact, shape: `## YYYY-MM-DD · fact_name · status`
  where status is one of `manual-verified`, `empirical`, `unverified`,
  `conflict`, `policy`, `decision`, `open item`, `analysis`.
- Body is markdown under the heading. Never edit old facts in the
  payload; supersede with `supersedes: <old_heading>` on its own line.
- Never emit `facts.md` in the payload — only `facts.append.md`.

## sessions file rules

- Filename: `sessions/YYYY-MM-DD_<scope>.md`, unique per session.
- Single defined scope. If a scope is done, recommend a new session.
- Markdown handoff with five sections in this order: Verified this
  session; Open questions; Loose ends; Suggested next scope; Ground
  truth.
- Open items and proposals stay proposals. Never lock a future spec
  into session notes unless the user says "lock it".
- Reference anchors by name; full listing only for a new program.

### Ground truth section rules

- Every hardware-passed program must have `docs/anchors/<PROG>.BAS`
  (BASIC runner, full retypable listing) and
  `docs/anchors/<PROG>.ASM` (machine-code design logic).
- The Ground truth section lists anchor paths only, not listings.
- No anchor path present means the session cannot close.
- DATA blocks in `.BAS` must byte-match the corresponding `.ASM`;
  regenerate via `jr build`, never hand-roll.

## test_log rules

- Emit `docs/test_log.append.md` only when a run produced a result
  block. No run -> omit the file entirely, no empty append.
- Result entries use the test-workflow contract/result format; never
  copy one routine's expectations into another routine's contract.

## COMMIT.txt rules

- Exactly one line. Verb-first summary of the session, low-noise.
- No markdown, no bullets.

## Emission rules

- Wrap all create_file calls in BDS:LONG_WORK; the zip is the
  deliverable.
- After LONG_WORK closes, one short plain sentence naming the files and
  whether test_log was included. Never re-explain every file.
- If the payload was already emitted and got lost, re-emit the SAME
  files; do not reformat into prose.
- Never emit a member outside the append/replacement classes above;
  `jr-ingest.sh` rejects unknown members as a hard error.
- Ask before adding a new member class to the contract.

## Memory batch rules (separate from the payload, same close)

Hard rules:

- Never write silently. Propose the full batch — every key and its
  complete value — and wait for approval. One batch per turn.
- No `pcjr_` key prefix.
- `called` keys hold pointers to `facts.md` or `sessions/`, never fact
  restatements.

Full key-naming, budget, and anti-pattern rules: `facts.md` heading
`memory_batch_spec`.
