# PyCJr — CH0 Calibration Record (CH0CAL) (v5)

Durable record of the two-frame IBG cross-calibration that settled the
CH0 input-clock question. Values live in `facts.md`; this file is the
compiled view (method, resolution, defects).

## Verdict

CH0 = 2.38636 MHz (14.31818/6 = CPU/2). Empirical. Retires the
1.19318 MHz inference. The manual is silent; keep the `empirical` label
and never promote to `manual-verified`. See `facts.md` `ch0_clock`.

## Method

Pi-driven two-frame inter-burst gap (IBG) cross-calibration. Three IBG
points; the slope is derived from delta pairs, so it is immune to a
stale single denominator. Latch geometry is trailing-edge vs
leading-edge; measured gap = IBG - burst width (~62 us shortfall).

| IBG (us) | latched counts |
|---|---|
| 1500 | 3428 |
| 10000 | 23704 |
| 20000 | 47636 |

## AGC resolution

The earlier "AGC inflation" anomaly was a wrong-clock artifact. At the
true CH0 clock the STAGE5-clean boundary count matches the emitter's
~1500 us frame gap within edge slack. No AGC anomaly; the 1.19318 MHz
inference was the error.

## Derived constants (pointer)

See `facts.md`: `ch0_clock`, `poll_quant`, `gap2_1126`.

## Known defects / deferred

- CH0CAL line 45 `dl2!=10000` is a stale hardcoded constant. The line-300
  `raw_hz` verdict misreports when the actual IBG differs (20 ms printed
  "4.77 candidate"). The slope method is immune. Fix or mark
  informational-only before reuse.
- BASIC arming flush (line 130, `for fl=1 to 100`) is an uncalibrated
  count loop. The original 3000-iteration version cost >1 s and armed
  after the wave (ed=0). Use an in-ASM deterministic settle on a
  critical path. This flush is the resolved root cause of `open_3840`.
- Timer-2 IR-test wrap (40 kHz counter value; PB0/PB1 gate/data) is
  unverified against manual 2-85..2-89.

## Regression

IRPING first when transport is suspect. CH0CAL pass identity recorded in
`docs/test_log.md`.
