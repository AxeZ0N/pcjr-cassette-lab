# PyCJr — Test Log (regression/probe run history) (v5)

Repo-resident run history. Not BDS-imported. Rules (stage gates,
emission gate, debug anchor rule) live in
`bds/10_skills/pcjr_test_workflow.md`; values and single-fact anchors
live in `facts.md`; this file records run entries and baselines.

## Run entry template

```

date: YYYY-MM-DD
id: <probe id>
source: <FILE.BAS / artifact>
contract: <expected fields>
observed: <actual fields>
keyboard_after: <intact | broken | not applicable>
regression: <IRPING | last known-good>

```

## Known-good baselines (recorded data, not rules)

### IRPING (golden regression artifact)

- Frozen 61-byte raw IR edge sampler; DATA lives in the platform skill
  Rule 5, not here.
- Expected pass: `rising>0`, `falling>0`, `status=0` or `64`.
- Role: run first when transport behavior is suspect.

### SHAPE3 Stage 3

- Recorded: `status=1`, `edges=2`, `init=0`.
- Role: early-stage known-good.

### STAGE5 clean

- Recorded: `status=1`, `edges=40`, `init=0`, keyboard intact.
- Recorded `max_delta=3456` at edge 20 (session reading; see note).
- Note: edge count varies 38-40 across clean runs. Root cause resolved:
  arming window swallowed frame 1's leading start burst
  (`facts.md` `open_3840`).

### CH0CAL

- Recorded pass: `st=1`, `ed=38`, `in=0`, `it=61440`, keyboard intact.
- gap1: `3428` @ 1500us, `23704` @ 10000us, `47636` @ 20000us.
- gap2: `1126` counts (~472 us) = stretched envelope H, not silence, not
  a bit cell. See `facts.md` `gap2_1126`.
- Derivation and defects: `docs/ch0_calibration.md`.

### ENVSHAPE

- Recorded clean: `st=1`, `ed=38`, `in=0`, `it=61440`, `nh19 nl18`,
  keyboard intact. Added to workflow anchor list.

## Superseded readings (do not reuse)

- STAGE5 earlier readings `edges=38` / `max_delta=2592` are superseded by
  the STAGE5 clean baseline above.
- `max_delta=3528` appears in some notes; the recorded anchor value is
  `3456`. Flag any file still carrying 3528 for reconciliation
  (`bin/migrate_repo.py` scans for this).

## 2026-08-22 baseline

```

date: 2026-08-22
id: repo_baseline
source: tooling_build_repo_refactor
contract: living-repo layout + grep_repo + jr-commit.sh
observed: facts.md seeded; anchors migrated; docs slimmed
keyboard_after: not applicable
regression: not applicable

```

### BUSY100CAL (aborted)

- S0 pass: Out of DATA traps, ERR 4. 1/0 no trap.
- S1 pass: CH0 lo=12 hi=205, INP/OUT confirmed.
- S2 pass: A0 mask/unmask, keyboard intact.
- S3/S4 data rejected: n=0 reps 50776/49808/53624; n=5 -> 64 (wrap
  fold); n=10 -> 20256 (wrap fold); wrap-flag run still multi-wrap
  ambiguous. Aborted, tool unfit. See facts.md busy100cal_aborted.

### ENVSHAPE delay sweep

- ed=38 flat 0.2..1.0s. >1s ed=18 (truncation). 40 retired.
  open_3840 refuted; merge hypothesis open.
## 2026-08-22 · ENVSHAPE26 · result
{
  "id": "ENVSHAPE26",
  "source": "ENVSHAPE26.BAS",
  "expected": { "return": "returned ok", "st": 1, "ed": 38, "in0": 0, "it": 61440, "nH": 19, "nL": 18, "mH": 572, "xh": "1124..1126", "mL": 745, "xl": "3500..3502", "keyboard_after": "intact" },
  "observed":  { "return": "returned ok", "st": 1, "ed": 38, "in0": 0, "it": 61440, "nH": 19, "nL": 18, "mH": 572, "xh": 1124, "mL": 745, "xl": 3502, "keyboard_after": "intact (presumed)" },
  "verdict": "PASS",
  "recovery": "cold_power_cycle"
}
## 2026-08-22 · ENVSHAPE26 · result
{
  "id": "ENVSHAPE26",
  "source": "ENVSHAPE26.BAS",
  "expected": { "return": "returned ok", "st": 1, "ed": 38, "in0": 0, "it": 61440, "nH": 19, "nL": 18, "mH": 572, "xh": "1124..1126", "mL": 745, "xl": "3500..3502", "keyboard_after": "intact" },
  "observed":  { "return": "returned ok", "st": 1, "ed": 38, "in0": 0, "it": 61440, "nH": 19, "nL": 18, "mH": 572, "xh": 1124, "mL": 745, "xl": 3502, "keyboard_after": "intact (presumed)" },
  "verdict": "PASS",
  "recovery": "cold_power_cycle"
}
## 2026-08-24 · AGCPROBE · result
{
  "id": "AGCPROBE",
  "source": "AGCPROBE.BAS + pycjr harness",
  "stimulus": "custom probe waves: burst-pair (W,S,W,S) and 8-burst train",
  "clock": "CH0 2.38636 MHz empirical",
  "keyboard_after": "intact (all runs)",
  "runs": [
    {"label":"G1_iso","spec":"62,5000,62,5000","ed":4,"H":[550,548],"L":[11566]},
    {"label":"G2_w25","spec":"25,5000,25,5000","ed":4,"H":[550,550],"L":[11420]},
    {"label":"G2_w40","spec":"40,5000,40,5000","ed":4,"H":[550,550],"L":[11420]},
    {"label":"G2_w62","spec":"62,5000,62,5000","ed":4,"H":[550,550],"L":[11564]},
    {"label":"G2_w125","spec":"125,5000,125,5000","ed":4,"H":[550,550],"L":[11636]},
    {"label":"G2_w250","spec":"250,5000,250,5000","ed":4,"H":[1126,1052],"L":[11422]},
    {"label":"G2_w500","spec":"500,5000,500,5000","ed":4,"H":[1702,1702],"L":[11420]},
    {"label":"G3_s1500","spec":"62,1500,62,1500","ed":4,"H":[550,548],"L":[3142]},
    {"label":"G3_s440","spec":"62,440,62,440","ed":4,"H":[550,550],"L":[620]},
    {"label":"G3_s220","spec":"62,220,62,220","ed":4,"H":[550,478],"L":[188]},
    {"label":"G3_s157","spec":"62,157,62,157","ed":2,"H":[],"L":[]},
    {"label":"G3_s80","spec":"62,80,62,80","ed":2,"H":[],"L":[]},
    {"label":"G3_s40","spec":"62,40,62,40","ed":2,"H":[],"L":[]},
    {"label":"G4_train","spec":"8x(62,440)","ed":16,"H":[550,550,548,550,550,548,550,550],"L":[620,694,694,620,694,622,620]}
  ],
  "notes": [
    "Battery-2 transcription header 'ed=5' was a slip; every line in that block carries 3 deltas = ed 4. Analyzed as ed=4.",
    "Pre-suite sanity run '2000,62,375' gave st=1 ed=2 it=61440, no H/L dump; single burst correctly blocked by the ed>=3 gate.",
    "Manual h-press (pre-suite): st=1 ed=34 in=0 it=61440, h decoded, H contains single 1450 ct (607 us) merge candidate; the first 55 ct value was a transcription error, corrected away.",
    "ed>=3 dump gate discarded merged-high width on S=157/80/40; next probe needs ed>=2 dump."
  ]
}
# 2026-08-24 · threshold pinning battery 1 (merge+recovery)

{
  "id": "threshold_battery_1",
  "source": "threshold_battery.txt",
  "regression": "CH0CAL",
  "recovery": "cold_power_cycle",
  "contract": {
    "stimulus": "W=62us two-burst, lead=0, trailing=5000us",
    "sweep": "merge S=180/190/200/210, recovery S=260/300/340/380"
  },
  "results": [
    {"S":180,"ed":4,"H":"550 406","L":188},
    {"S":190,"ed":4,"H":"550 478","L":188},
    {"S":200,"ed":4,"H":"550 478","L":188},
    {"S":210,"ed":4,"H":"550 478","L":188},
    {"S":260,"ed":4,"H":"550 550","L":188},
    {"S":300,"ed":4,"H":"550 548","L":334},
    {"S":340,"ed":4,"H":"550 550","L":476},
    {"S":380,"ed":4,"H":"550 500","L":476}
  ],
  "notes": "S=380 H2=500 transient; did not reproduce in battery 3."
}

# 2026-08-24 · threshold pinning battery 2 (knee pinning)

{
  "id": "threshold_battery_2",
  "source": "threshold_battery_2.txt",
  "regression": "CH0CAL",
  "recovery": "cold_power_cycle",
  "contract": {
    "stimulus": "W=62us two-burst, lead=0, trailing=5000us",
    "sweep": "fuse S=160/165/170/175, recovery S=230/240/250, repeats 300/340/380"
  },
  "results": [
    {"S":160,"ed":2,"note":"fused"},
    {"S":165,"ed":2,"note":"fused"},
    {"S":170,"ed":2,"note":"fused"},
    {"S":175,"ed":4,"H":"550 406","L":188},
    {"S":230,"ed":4,"H":"550 478","L":188},
    {"S":240,"ed":4,"H":"550 550","L":188},
    {"S":250,"ed":4,"H":"550 550","L":188},
    {"S":300,"ed":4,"H":"550 548","L":334},
    {"S":340,"ed":4,"H":"550 550","L":476},
    {"S":380,"ed":4,"H":"550 550","L":476}
  ],
  "notes": "S=380 L=476 repeats battery 1 S=340; S=380 H2 anomaly retired."
}

# 2026-08-24 · anomaly knock-out battery 3

{
  "id": "threshold_battery_3",
  "source": "threshold_battery_3.txt",
  "regression": "CH0CAL",
  "recovery": "cold_power_cycle",
  "contract": {
    "stimulus": "batch1 W=250/S=5000 x4, batch2 W=62 S=310/320/330/335"
  },
  "results": [
    {"S":5000,"W":250,"H1":1054,"H2":1054,"L":11492},
    {"S":5000,"W":250,"H1":1126,"H2":1124,"L":11422},
    {"S":5000,"W":250,"H1":1126,"H2":1054,"L":11420},
    {"S":5000,"W":250,"H1":1126,"H2":1126,"L":11380},
    {"S":310,"W":62,"H":"550 548","L":334},
    {"S":320,"W":62,"H":"550 550","L":404},
    {"S":330,"W":62,"H":"550 548","L":406},
    {"S":335,"W":62,"H":"550 550","L":404}
  ],
  "notes": "W250 asymmetry intermittent (1/4); L staircase jumps 310->320 (334->404)."
}
## 2026-08-24 · ch0cal_deterministic_hpress · result

contract: {"id":"ch0cal_deterministic_hpress","source":"CH0CAL/AGCPROBE",
  "expected":{"st":1,"ed":"38 (anchor)","functional":"h"},
  "regression":"IRPING","recovery":"cold_power_cycle"}

result: st=1, ed=36 (2/2 deterministic), functional h decodes, kb intact.
H: 550 548 550 550 548 1126 550 548 550 550 548 550 548 550 406 1124 550
L: 334 478 1052 478 550 908 550 478 3572 334 478 1052 478 478 188 982 406
Merges: H6=1126, H17=1124 (both 157us 0→1 gaps). Stable across 2/2.

verdict: FAIL vs anchor ed=38; FUNCTIONAL PASS. Classified receiver
analog drift (closed warm room). Code/Pi/wiring exonerated. One transient
38 after percussive, not reproducible. z2 functional sweep deferred to
next session.
## 2026-08-25 · DENSETRAIN · result

contract: {"id":"DENSETRAIN","source":"densetrain_battery.txt",
  "expected":{"return":"RETURNED OK","ed":"24 clean, fewer iff fusing",
  "H":"flat ~230us, no >10% sag","L_min":"deliverable"},
  "regression":"AGCPROBE.BAS (AGC1) + CH0CAL ASM",
  "recovery":"cold_power_cycle"}

result: st=1, kb intact. Sweep S=260..160us, 12-burst trains.
- S=260: H 550 flat (one 620ct outlier), L 190/262 bimodal.
- S=240: H 550/476 mixed, L 190 uniform; clean 24/24.
- S=230: one fusion (H 1378ct merged), L 190; 22/24.
- S=220: clean edges, H oscillates 476/478 and 406/404; L 190.
- S<=200: collapse, multiple fusions.

verdict: dense separation floor ~230-240us (stochastic onset 230,
clean 240). H dense minimum 406ct (~170us). 250us cell refuted.
## 2026-08-25 · RECOVERY4 · result

{
  "id": "RECOVERY4",
  "source": "recovery4_battery.txt",
  "regression": "AGCPROBE.BAS (AGC1) + CH0CAL ASM",
  "recovery": "cold_power_cycle",
  "results": [
    {"label":"CTRL_180","ed":12,"fusions":6,"note":"reproduces dense collapse"},
    {"label":"R4_180","ed":22,"fusions":1,"note":"fusion post-reset block 3"},
    {"label":"R4_200","ed":24,"fusions":0,"note":"S=200 rescued by reset"},
    {"label":"R4_220","ed":24,"fusions":0,"note":"L7=133 below 79us floor"}
  ],
  "verdict": "PASS mechanistically; retired economically (k≈3 vs k>22 break-even)"
}
## 2026-08-25 · irping_basload_pass · result

contract: {"id":"IRPING_BASLOAD","source":"BASLOAD.BAS + IRPING DATA",
"expected":{"return":"RETURNED OK","transport":"sane (char echo)"},
"regression":"self","recovery":"cold_power_cycle"}
result: `loaded 61 bytes`; Pi key echoed on screen; keyboard intact
after. Transport sane. Rising/falling not transcribed this run; the
IRPING block read through BASLOAD's S1 offsets printed flag=0
saved=6:6 status=0 — a diagnostic misread, not a transport failure.

## 2026-08-25 · ch0cal_envshape_pass · result

contract: {"id":"CH0CAL_ENVSHAPE","source":"ENVSHAPE.BAS (CH0CAL ASM)",
"expected":{"return":"RETURNED OK","functional":"h decodes","keyboard_after":"intact"},
"regression":"IRPING -> CH0CAL","recovery":"cold_power_cycle"}
result: passed; functional 'h' decode, keyboard intact. ed reading
environmental per facts.md ch0cal_ed_reading_conflict; not
contractual.

## 2026-08-25 · s1_v1_div0 · result

contract: {"id":"S1_NMI_INTERCEPT","source":"BASLOAD.BAS + S1 v1 (110B)",
"expected":{"return":"RETURNED OK","flag":1,"status":0,"keyboard_after":"intact"},
"regression":"IRPING -> CH0CAL","recovery":"cold_power_cycle"}
result: FAIL. `loaded 110 bytes`, ~3s, `Division by zero in (blank)`,
keyboard dead. Root cause: bp clobber (no push/pop bp).

## 2026-08-25 · s1_v2_reboot · result

contract: {"id":"S1_NMI_INTERCEPT_V2","source":"BASLOAD.BAS + S1 v2 (114B)",
"expected":{"return":"RETURNED OK","flag":1,"status":0,"keyboard_after":"intact"},
"regression":"IRPING -> CH0CAL","recovery":"cold_power_cycle"}
result: FAIL. `loaded 114 bytes`; Pi 'h' during window -> PCjr reboot
into BIOS. No result map read. Defect not localized; stage gate
triggered.## 2026-08-25 · s1_ladder_stage1_bridge · result
contract: {id s1_ladder_stage1_bridge, expected return RETURNED OK,
keyboard intact, regression none}
result: PASS. loaded 9 bytes, returned ok, keyboard alive.

## 2026-08-25 · s1_ladder_stage2_selfloc · result
contract: {id s1_ladder_stage2_selfloc, expected flag 0x5A, return OK}
result: PASS. flag=0x5A (90 dec), keyboard alive.

## 2026-08-25 · s1_ladder_stage3_nmi_touch · result
contract: {id s1_ladder_stage3_nmi_touch, expected return OK,
keyboard intact}
result: PASS. mask/clear/restore clean, keyboard alive.
(regression IRPING + CH0CAL both green before run)

## 2026-08-25 · s1_ladder_stage4_read_ivt · result
contract: {id s1_ladder_stage4_read_ivt, expected saved F000:xxxx}
result: PASS. saved=3960:61440 = F000:0F78, keyboard alive.
note: harness first run overflowed (256*peek > 32767 under DEFINT);
fixed with sv!/sg! single precision.

## 2026-08-25 · s1_ladder_stage5_write_ivt · result
contract: {id s1_ladder_stage5_write_ivt, expected return OK,
saved unchanged, keyboard intact}
result: FAIL. screen flag=0 saved=F78:F000 status=0, keyboard DEAD.
false pass caught on human keyboard gate. cold_power_cycle.

## 2026-08-25 · s1_ladder_stage5c_noop_write · result
contract: {id s1_ladder_stage5c_noop_write, expected return OK,
keyboard intact}
result: FAIL. returned ok, saved=F78:F000, keyboard DEAD. no-op write
of saved value proves the IVT write act itself is the trigger, not the
value. Decision: INT 02h vector write is UB on this machine.
## 2026-08-26 · s1v2 · result

{
  "id": "s1v2",
  "source": "S1V2.BAS",
  "result": {
    "return": "returned ok",
    "loaded": 71,
    "flag": "0",
    "rising": "17",
    "falling": "17",
    "keyboard": "intact"
  },
  "pass": true,
  "recovery": "cold_power_cycle"
}

## 2026-08-26 · s2v1 · result

{
  "id": "s2v1",
  "source": "S2V1.BAS",
  "result": {
    "return": "returned ok",
    "loaded": 106,
    "st": "1",
    "edge_count": "22h (34)",
    "snapshot": "0",
    "iter_low_byte": "0",
    "keyboard": "intact"
  },
  "pass": true,
  "recovery": "cold_power_cycle"
}

## 2026-08-26 · b26vec · result

{
  "id": "b26vec",
  "source": "B26VEC.BAS",
  "result": {
    "vectors": 11,
    "match": "11/11",
    "keyboard": "n/a (no machine code)"
  },
  "pass": true,
  "recovery": "cold_power_cycle"
}

## 2026-08-26 · s3v1 · result

{
  "id": "s3v1",
  "source": "S3V1.BAS",
  "result": {
    "return": "returned ok",
    "loaded": 106,
    "st": "1",
    "ed": "36",
    "dump": "transcription corrupted"
  },
  "verdict": "void — transcription only",
  "note": "hardware, ASM, and encoder exonerated; method retired",
  "recovery": "cold_power_cycle"
}
## 2026-08-26 · s4a_v1_timeout · result

contract: {"id":"S4A","source":"S4A.BAS v1 (139B, CH0 variant)",
"expected":{"return":"RETURNED OK","st":"0|3","half":"0|1",
"keyboard_after":"intact"},
"regression":"IRPING -> CH0CAL","recovery":"cold_power_cycle"}
result: PASS (timeout path). No stimulus; st=0, half=0,
t0=58371 t1=45216 (code-tail artifacts, not timestamps). Keyboard
intact. 2/2 identical.

## 2026-08-26 · s4a_v1_h_softlock · result

contract: {"id":"S4A","source":"S4A.BAS v1 (139B, CH0 variant)",
"expected":{"return":"RETURNED OK","st":3,"half":"0|1",
"keyboard_after":"intact"},
"regression":"IRPING -> CH0CAL","recovery":"cold_power_cycle"}
result: FAILED. h press during window caused screen line corruption
and keyboard softlock. Root cause: v1 restored NMI mid-make-frame;
KBDNMI deserialized the frame tail as garbage. Cold power-cycle
recovered.

## 2026-08-26 · s4a_v2_h_pass · result

contract: {"id":"S4A","source":"S4A.BAS v2 (112B, LOOP-timing)",
"expected":{"return":"RETURNED OK","st":3,"half":"0|1",
"keyboard_after":"intact"},
"regression":"IRPING -> CH0CAL","recovery":"cold_power_cycle"}
result: PASS. h press: st=3, half=1 (predicted first data bit of
0x23). Keyboard alive. Run via --run_test.
## 2026-08-26 · s4b1_stage1_pass · result

contract: {"id":"S4B1-stage1","source":"S4B1.BAS stage1 (39B)",
  "expected":{"return":"RETURNED OK","st":"&HAA","bit0":"&HBB",
  "bit1":"&HCC","biphase_ok":"&HDD","keyboard_after":"intact"},
  "regression":"IRPING -> S4A","recovery":"cold_power_cycle"}
result: loaded=39, returned ok, st=&HAA bit0=&HBB bit1=&HCC
  biphase=&HDD, keyboard intact. PASS.

## 2026-08-26 · s4b1_stage2_ch0_live · result

contract: {"id":"S4B1-stage2","source":"S4B1_stage2.BAS (103B)",
  "expected":{"return":"RETURNED OK","st":"2","rise/trail stored",
  "delta_nonzero":"1","keyboard_after":"intact"},
  "regression":"IRPING -> S4A","recovery":"cold_power_cycle"}
result: st=2 rise=0x4DE6 trail=0x4BA4 burst=0x242 (578 counts=242.2us)
  and an earlier run burst=526 counts=220.4us. CH0 latch/read works
  under NMI mask during live frame; keyboard intact. PASS.

## 2026-08-26 · s4b1_stage3b_boundary · result

contract: {"id":"S4B1-stage3b","source":"S4B1_stage3b.BAS (180B)",
  "expected":{"return":"RETURNED OK","st":"3","half":"0|1",
  "rise/trail/burst reported","keyboard_after":"intact"},
  "regression":"IRPING -> S4A","recovery":"cold_power_cycle"}
result: st=3 rise=0xC330 trail=0xC0D8 burst=0x258 (600 counts=251.4us)
  half=0, keyboard intact. Fixed 740-anchor samples the bit0 boundary
  and disagrees with S4A's half=1 at the same nominal offset. Negative
  result for fixed grid; edge-sync is the next path. RECORDED.
## 2026-08-27 · dec1_st1_hw_pass · result
{
  "id": "DEC1_ST1",
  "source": "DEC1_ST1.BAS",
  "expected": {
    "return": "RETURNED OK",
    "flag": "2 when both edges seen",
    "span": "880..1100 counts"
  },
  "regression": "IRPING -> S4B1_ST3B",
  "recovery": "cold_power_cycle"
}
result: PASS 2/2. Run 1: flag=2, r0=0xCDD0, r1=0xCA54, span 892 ct
(373.8 us). Run 2: flag=2, r0=0xBB46, r1=0xB7C8, span 894 ct
(374.6 us). Keyboard intact. loaded-106 gate observed.
## 2026-08-27 · dec1_st2a_hw_pass · result
{
  "id": "DEC1_ST2A",
  "source": "DEC1_ST2A.BAS",
  "expected": {"return": "RETURNED OK", "status": "2 when PC0 seen", "pc6": "40"},
  "result": {"return": "RETURNED OK", "status": 2, "pc6": "40", "kb": "intact", "loaded": "57"},
  "verdict": "pass"
}

## 2026-08-27 · dec1_st2b_fail · result
{
  "id": "DEC1_ST2B",
  "source": "DEC1_ST2B.BAS",
  "expected": {"return": "RETURNED OK", "status": "3", "span": "~148 ct (120-180 window)"},
  "result": {"return": "RETURNED OK", "spans": [334, 572, 572, 574, 574, 520, 520, 574], "no_stim": "status=0", "kb": "intact", "loaded": "92"},
  "verdict": "fail",
  "note": "trimodal AGC ripple; single-poll trailing edge insufficient"
}
# 2026-08-28 · bitsamp_ch1_544 · result

contract: {"id":"BITSAMP-CH1-544","source":"BITSAMP.BAS (inline jr build)",
"expected":{"return":"RETURNED OK","st":"3","bit":"0|1","ones":"0..5",
"trail/sample nonzero","keyboard_after":"intact"},
"regression":"IRPING -> CH0CAL","recovery":"cold_power_cycle"}
result: st=3 bit=1 ones=3 rej=1, 3/3, keyboard intact.
trail-sample deltas: 658 / 658 / 660 CH1 ticks (551.8 / 553.5 us at
1.19318 MHz). Deterministic to 1 tick. Ones=3 (not 5): 2 of 5 majority
polls LOW — sample on ragged edge of bit0 HIGH. Failed disproof of
CH0 clock-conversion confound; correct decode, thin margin.
Not anchored.## 2026-08-30 · IRPING2_MIN · result

```json
{
"id": "IRPING2_MIN",
"contract": {
  "source": "BASLOAD.BAS + IRPING2.ASM",
  "expected": { "return": "RETURNED OK", "result_byte": 3 },
  "regression": "self (transport-only); CH0CAL stays functional primary",
  "recovery": "cold_power_cycle"
},
"result": {
  "loaded": 56,
  "return": "RETURNED OK",
  "result_byte": 3,
  "keyboard": "intact",
  "rising": 0,
  "falling": 0,
  "note": "rising/falling are meaningless on this probe; it writes only O+128."
},
"verdict": "pass"
}
```

## 2026-08-30 · framegap_1000 · result
{"id":"FRAMEGAP-1000","source":"FRAMEGAP.BAS inline jr build",
"expected":{"return":"RETURNED OK","st":"3","gap":"~1790","bit":"1","ones":"4..5"},
"result":{"st":3,"bit":0,"ones":1,"gap":[1020,1020,1020,1022,1022,1022],
"delta":[658,658,658,660,660]},
"verdict":"fail","note":"threshold 1000 accepts a mid-frame '10' data pair (~855 us), not the frame gap. Reference edge wrong; bit0 samples LOW half."}

## 2026-08-30 · framegap_1400 · result
{"id":"FRAMEGAP-1400","source":"FRAMEGAP.BAS inline jr build",
"expected":{"return":"RETURNED OK","st":"3","gap":"~1790"},
"result":{"st":2,"bit":0,"ones":0,"gap":[3437,3474],"ripple":null},
"verdict":"fail","note":"correct frame boundary reached (idle+1500us gap), but I6 sync-errors on the start-burst trailing-edge ripple. Byte-identical I6 at this phase rejects the Pi envelope."}

## 2026-08-30 · i6_instrument · result
{"id":"FRAMEGAP-I6INSTR","source":"FRAMEGAP.BAS instrumented",
"expected":{"ripple":"1..4","st":"2"},
"result":{"ripple":[4,3,2,3,2,3,2,2],"st":2},
"verdict":"informational","note":"I6 HIGH count is 2-3 sustained on re-arm builds, 1 narrow on one-shot. Ripple width tracks arm strategy, proving AGC-history-dependent entry state."}

## 2026-08-30 · rise_stamp · result
{"id":"FRAMEGAP-RISE","source":"FRAMEGAP.BAS rise-stamped",
"expected":{"bwidth":"~260-350 ticks"},
"result":{"bwidth":[-658,-658],"trail":[51442,10282],"rise":[52100,10940],"delta":null},
"verdict":"fail","note":"bwidth 658 ticks = 551 us = stretched burst + merged silence. Re-arm leaves AGC holding HIGH through the 310 us silence."}

## 2026-08-30 · oneshot · result
{"id":"ONESHOT","source":"ONESHOT.BAS inline jr build",
"expected":{"bwidth":"~260-350 ticks","st":"3"},
"result":{"bwidth":[-552,-552,-552,-552],"ripple":[1,1,2,2],"st":2},
"verdict":"fail","note":"552 ticks = 462 us = one full bit + 22 us. Armed on a data edge, not the start burst. Frame boundary is required for correct phase."}
## 2026-08-30 · ivt_readonly · result

{
"id": "ivt_readonly",
"run": "2026-08-30",
"observed": {"loaded": 36, "return": "RETURNED OK",
  "offset": 3960, "segment": 61440, "decode": "F000:0F78"},
"manual_ref": "bios_grep 04D3 writes NMI_PTR offset 0F78; 000A never written",
"verdict": "read_clean"
}

## 2026-08-30 · ivt_write_quiescent_sameboot · result

{
"id": "ivt_write_quiescent_sameboot",
"run": "2026-08-30",
"observed": {"loaded": 66, "pre": "3960:61440", "wr": "3960:61440",
  "post": "3960:61440", "return": "RETURNED OK", "keyboard_after": "fine"},
"clean_run": true,
"falsifier_observed": false,
"verdict": "failed_to_disprove"
}

## 2026-08-30 · ivt_write_quiescent · result (non-fresh boot)

{
"id": "ivt_write_quiescent",
"run": "2026-08-30",
"observed": {"loaded": 66, "return": "RETURNED OK",
  "keyboard_after": "fine", "readback": "0000:0000"},
"clean_run": false,
"verdict": "no_result"
}
## 2026-08-30 · ivtwr_loop_a · result

{"id":"ivtwr_loop_a","expected":{"return":"RETURNED OK","mismatch":0,"final":"3960:61440","keyboard":"alive"},"observed":{"return":"RETURNED OK","mismatch":0,"final":"3960:61440","keyboard":"alive"},"regression":"CH0CAL","recovery":"cold_power_cycle","loaded_bytes":115}

## 2026-08-30 · ivtwr_loop_b · result

{"id":"ivtwr_loop_b","expected":{"return":"RETURNED OK","mismatch":0,"final":"3960:61440","keyboard":"alive"},"observed":{"return":"RETURNED OK","mismatch":0,"final":"3960:61440","keyboard":"alive"},"regression":"CH0CAL","recovery":"cold_power_cycle","loaded_bytes":115}

## 2026-08-30 · ivtwr_loop_race · disproof verdict

{"id":"ivtwr_loop_race","hypothesis":"H — IVT write harmless quiescent; fatal only under active keyboard NMI","falsifier":"F — Mode B completes with keyboard alive AND mismatch=0","clean_run":"S — Mode A completes first: RETURNED OK, mismatch=0, keyboard alive","verdict":"disproved"}## 2026-08-31 · N1-B0 · no_result

{"id":"N1B0","source":"N1B0.BAS","verdict":"no_result",
 "reason":"18-byte self-loc IRET handler: screen corruption, dead keyboard after CALL. First crash confined to custom-INT-02h dispatch step.",
 "recovery":"cold_power_cycle"}

## 2026-08-31 · N1-B1 · no_result

{"id":"N1B1","source":"N1B1.BAS","verdict":"no_result",
 "reason":"2-byte bare E4 A0 CF handler: screen clean, keyboard dead after run. Reducing handler body did not clear the death — defect upstream of handler body.",
 "recovery":"cold_power_cycle"}

## 2026-08-31 · N1-B2 · no_result

{"id":"N1B2","source":"N1B1.BAS (no-key control)","verdict":"no_result",
 "reason":"identical failure to N1-B1 with no key pressed during delay. Does not isolate wrapper vs dispatch; N1-B3 stock-vector control required.",
 "recovery":"cold_power_cycle"}
</BDS:create_file>
</BDS:LONG_WORK>

Payload emitted: `COMMIT.txt`, `facts.append.md`, `sessions/2026-08-31_nmi_dispatch_ladder.md`, `docs/test_log.append.md`. No anchors — no probe earned a hardware pass this session. No memory batch proposed; say the word if you want one.
## 2026-08-31 · NMIPEEK ES A/B · result

{
"id":"nmipeek_es_ab",
"source":"NMIPEEK.BAS",
"hypothesis":"H — the bytes-corruption crash is caused by ES clobber across the bridge",
"falsifier":"F — ES-preserved NMIPEEK still corrupts (same signature with PUSH/POP ES in place)",
"clean_run":"S — returned ok, m1=42, saved=3960:61440, keyboard alive and echoes",
"observed": {
  "no_es_save": "bytes corruption, keyboard alive but frozen on string ops (every run)",
  "es_preserved": "returned ok, m1=42, saved=3960:61440, keyboard alive (every run)"
},
"verdict":"failed_to_disprove"
}

## 2026-08-31 · NMIPEEK shift/overflow corrections · result

{
"id":"nmipeek_harness_fixes",
"source":"NMIPEEK.BAS",
"note":"First ES-preserved build had PUSH ES before self-location, shifting pop di from offset 6 to 7 and skewing all stores (saved read 0x7800:0x000F). Corrected to PUSH ES after self-location. Harness sg promoted to sg! because stock segment F000=61440 overflows DEFINT.",
"recovery":"cold_power_cycle"
}
# NMIDISP Probe A — 2026-08-31

## Contract

{
  "id": "nmidisp_a",
  "source": "NMIDISP.BAS",
  "expected": { "installer_return": "RETURNED OK", "dispatch_flag": 1 },
  "regression": "IRPING2",
  "recovery": "cold_power_cycle"
}

## Result

{
  "id": "nmidisp_a",
  "loaded": 72,
  "installer_return": "RETURNED OK",
  "observed": "status=1 rising=0 falling=0 (status field = dispatch flag)",
  "dispatch_flag": 1,
  "keyboard": "dead (expected: KBDNMI replaced, scancodes discarded)",
  "cursor": "blinking (IF restored, INT 08h alive)",
  "regression": "IRPING2 status=3 (pass)",
  "verdict": "clean run — dispatch observed; coexistence survived one disproof attempt"
}

## Control

{
  "id": "nmidisp_a_control",
  "stimulus": "none",
  "loaded": 72,
  "dispatch_flag": 0,
  "regression": "IRPING2 status=3 (pass)",
  "verdict": "clean — no spurious NMI in the window"
}
## 2026-08-31 · probe_b_axclobber_74

{
  "id": "probe_b_axclobber_74",
  "hypothesis": "H — chain via mov ax,imm / push ax / retf coexists",
  "falsifier": "F — BASIC corrupt or keyboard dead after chain",
  "clean_run": "S — loaded 74; RETURNED OK",
  "observed": "loaded 74, RETURNED OK, Syntax error in 160 on first key, KB dead, cursor flashing",
  "verdict": "no_result — flag never printed, IRPING2 unconfirmed; defect: AX clobbered by chain setup, transparent KBDNMI restore passed it to BASIC"
}

## 2026-08-31 · probe_b_allregs_86

{
  "id": "probe_b_allregs_86",
  "hypothesis": "H — all-registers-saved handler chains with SP preserved",
  "falsifier": "F — hard freeze or lost keystroke",
  "clean_run": "S — loaded 86; RETURNED OK",
  "observed": "loaded 86, RETURNED OK, hard freeze on first key, no cursor",
  "verdict": "no_result — 18-byte save frame perturbed stack depth/phase at KBDNMI entry"
}

## 2026-08-31 · probe_b_noop_bisect

{
  "id": "probe_b_noop_bisect",
  "hypothesis": "H — defect lives in handler non-zero work; a pure chain coexists",
  "falsifier": "F — zero-work redirect still hard-freezes or fails to echo",
  "clean_run": "S — loaded 57; RETURNED OK; INPUT prompt displayed",
  "observed": "passed: keyboard alive, keystroke echoed via INPUT",
  "verdict": "failed_to_disprove — F not observed; H survives one disproof attempt. IRPING2 status unconfirmed in report."
}
## 2026-09-04 · IRPING2 regression

{
  "id": "IRPING2",
  "source": "IRPING2.BAS",
  "expected": { "return": "RETURNED OK", "status": "3" },
  "observed": { "return": "RETURNED OK", "status": "3" },
  "verdict": "pass",
  "regression": "none (this is the regression anchor)",
  "recovery": "cold_power_cycle"
}

## 2026-09-04 · BRIDGEA positive control

{
  "id": "BRIDGEA",
  "source": "BRIDGEA.BAS",
  "expected": { "return": "RETURNED OK", "marker": "66" },
  "observed": { "return": "RETURNED OK", "marker": "66" },
  "verdict": "pass",
  "regression": "IRPING2",
  "recovery": "cold_power_cycle"
}
## 2026-09-04 · IRPING2 gate · pass

{ "id": "IRPING2_gate_20260904", "source": "IRPING2.BAS",
  "expected": { "status": "3" },
  "observed": { "status": 3 },
  "verdict": "pass" }

## 2026-09-04 · CH1RATE run 1 · artifact

{ "id": "CH1RATE_DIFF_r1", "source": "CH1RATE.BAS",
  "expected": { "return": "RETURNED OK", "status": 1, "ratio": "quadrant" },
  "observed": { "return": "RETURNED OK", "status": 1,
                "reported_dCH0": 46226, "reported_dCH1": 43428,
                "reported_ratio": 0.93947 },
  "verdict": "no_result — subtraction artifact",
  "note": "True decrements CH0=19310, CH1=22108, R~1.145." }

## 2026-09-04 · CH1RATE run 2 · artifact

{ "id": "CH1RATE_DIFF_r2", "source": "CH1RATE.BAS",
  "observed": { "reported_ratio": 0.9370 },
  "verdict": "no_result — same artifact" }

## 2026-09-04 · LOOPCOUNT N=1 CH0 · pass

{ "id": "LOOPCOUNT_N1_CH0_CTRL", "source": "LOOPCOUNT.BAS",
  "expected": { "status": 1, "dCH0": "small (10-40)" },
  "observed": { "status": 1, "t0": 10714, "t1": 10582, "dCH0": 132 },
  "verdict": "pass" }

## 2026-09-04 · LOOPCOUNT N=1000 CH0 · pass

{ "id": "LOOPCOUNT_N1000_CH0", "source": "LOOPCOUNT.BAS",
  "expected": { "status": 1, "dCH0": "132 + 999*(18-75)" },
  "observed": { "status": 1, "t0": 28786, "t1": 10006, "dCH0": 18780 },
  "verdict": "pass — 18.67 ticks/iter, 74.7 cycles at 1.19318 MHz" }
## 2026-09-04 · CH1LOOP_rate · failed_to_disprove

{
"id": "CH1LOOP_rate",
"hypothesis": "H — CH1 decrements at 1.1925 MHz with A0h D5=0 (manual 2-35:21-25).",
"falsifier": "F — Δ outside 18.0..19.4 CH1 ticks/LOOP",
"clean_run": "status=1, RETURNED OK, loaded 69, both builds",
"verdict": "failed_to_disprove"
}

N=1:   t0=47480  t1=47348  dCH1=132
N=1000: t0=3908   t1=50664  dCH1=18780
Δ = (18780 − 132) / 999 = 18.67 CH1 ticks/LOOP## 2026-09-06 · irping2_regression

{"id":"irping2","observed":"status=3","clean_run":true,"verdict":"pass"}

## 2026-09-06 · drainless_run_a_60cps

{"id":"drainless_ab","run":"A","rate":"60 cps","observed":{"pre":"h=36 t=36","post":"h=36 t=34","fill_entries":15,"echo":"15 h"},"clean_run":true,"verdict":"failed_to_disprove"}

## 2026-09-06 · drainless_run_b_86cps

{"id":"drainless_ab","run":"B","rate":"86 cps","observed":{"pre":"h=60 t=60","post":"h=60 t=58","fill_entries":15,"echo":"15 h"},"clean_run":true,"verdict":"failed_to_disprove"}

## 2026-09-06 · skiplen_250_clean

{"id":"skiprepr","runs":2,"nominal":250,"len":250,"clean_run":true,"verdict":"falsifier not observed below cap"}

## 2026-09-06 · input_cap_300

{"id":"skiplen","runs":[{"rate":"86 cps","nominal":300,"len":254,"enter":"dropped"},{"rate":"60 cps","nominal":300,"len":254,"enter":"dropped"}],"clean_run":false,"verdict":"cap confirmed rate-independent"}
## 2026-09
## 2026-09-06 · tokdensity60

{"id":"tokdensity60","rate":"60 cps","payload":"S,C 40x27","sparse":"clean","dense":"clean","clean_run":true,"verdict":"disproved"}

## 2026-09-06 · tokdensity86

{"id":"tokdensity86","rate":"86 cps","payload":"S,C 40x27","sparse":"clean","dense":"clean","clean_run":true,"verdict":"disproved"}
## 202
## 2026-09-07 · linewatch86 · result

{
"id": "linewatch86",
"source": "LINEWATCH.BAS (self-check) + pycjr --stdin --cps 86",
"expected": { "count": "31", "mismatch": 0, "last": "ZZ", "ring": "empty" },
"observed": { "count": 31, "mismatch": 0, "last": "ZZ", "head": 60, "tail": 60 },
"clean_run": true,
"verdict": "failed_to_disprove — no loss at true 86",
"regression": "IRPING2 (not re-run this session)",
"recovery": "cold_power_cycle"
}

## 2026-09-07 · uniform40_86 · result

{
"id": "uniform40_86",
"source": "ten-line 40-char uniform payload + pycjr --stdin --cps 86",
"expected": { "lengths": "all 40" },
"observed": { "lengths": "all 40", "stop": "Break in 50" },
"clean_run": true,
"verdict": "failed_to_disprove — no loss at true 86",
"note": "rate not independently re-stated this run; same session setting as linewatch86",
"recovery": "cold_power_cycle"
}
## latchgate_seed_probe

{
"id": "latchgate_seed_probe",
"source": "LATCHGATE.BAS",
"runs": [
  {"loaded": 41, "ch1": 18018},
  {"loaded": 41, "ch1": 15866},
  {"loaded": 41, "ch1": 17306}
],
"keyboard": "alive after each",
"regression": "subsumed by clean 41-byte IR paste + responsive keyboard",
"recovery": "cold_power_cycle",
"verdict": "clean pass — masked CH1 latch/read live-safe"
}

## seednop_disproof

{
"id": "seednop_disproof",
"source": "SEEDNOP.BAS",
"runs": [
  {"variant": "A", "nops": 0, "loaded": 68, "overshoot": 88},
  {"variant": "B", "nops": 2, "loaded": 70, "overshoot": 98},
  {"variant": "C", "nops": 8, "loaded": 76, "overshoot": 130}
],
"each_variant_runs": 4,
"hypothesis": "H — missing settle NOPs at the I5 seed cause the overshoot",
"falsifier": "F — overshoot unchanged (±2 ticks) across 0/2/8 NOP variants",
"verdict": "failed_to_disprove — F not observed on clean runs"
}
## 2026-09-07 · paste_wrap_86_postreboot · failed_to_disprove

```
{
"id": "paste_wrap_86_postreboot",
"hypothesis": "H — bridge-entry contamination persists until reset",
"falsifier": "F — corruption observed in a clean post-reboot paste at 86 cps",
"clean_run": "full multi-line paste, LIST continuous, keyboard responsive",
"verdict": "failed_to_disprove"
}
```

Observed: post-reboot multi-line paste at true 86 cps, no corruption,
keyboard alive. F not observed on a clean run. H survives this test and
nothing more. The 40-char wrap seen on an earlier payload was a display
artifact, not the corruption signature under test.