# Characterization

Bench results for the curve tracer, organized around the tests in
`curve_tracer_blueprint.md` §7. The first section tracks where each §7 test
stands; the second is a dated bench log.

A number goes into the test matrix only when it comes from the intended parts:
OPA2197, 0.1% gain resistors, BD139. Sessions on substitute parts are logged
below but do not count toward §7.

## Test matrix (blueprint §7)

| Test | Method | Target | Status |
|---|---|---|---|
| Voltage accuracy | Compare ADC2 reading vs. 5.5-digit DMM across range | <0.5% error | Not started |
| Current accuracy | Sweep into 0.1% precision resistors of known value | <1% error, all 3 ranges | Not started |
| Noise floor | 1000 samples at fixed bias, compute σ | Report per range | Not started |
| CMRR | Common-mode step, measure output shift; repeat with 1% resistors | ~74 dB (0.1%) vs ~54 dB (1%) | Not started |
| Settling time | Step drain DAC, scope the buffer output | Sets minimum `settle_us` | Not started |
| Linearity | Sweep across a precision resistor, fit residuals | Report INL | Not started |
| Self-heating | DC vs. pulsed sweep, same device | Visible droop difference | Not started |
| Known-device check | 2N7000, 2N3904, 1N4148 vs. datasheet curves | Qualitative match | Not started |

---

## Breadboard build stages

The bench log refers to these stages. They split blueprint **Phase 1** (sweep
source on breadboard, current limit working) into steps small enough to debug
one at a time:

1. Rails, star ground, decoupling
2. Op-amp inserted and powered, no circuit
3. Gain network only, feedback from op-amp output
4. Add BD139 and `R_B`, feedback moves to emitter
5. Scope for VHF oscillation before proceeding
6. Add `R_sense`, feedback moves past it
7. Add 1N4148 B-E clamp and Q2 current limiter
8. Add `R_iso`, DUT socket, load test and short test

The feedback tap moves deliberately: op-amp output (stage 3), then emitter
(stage 4), then past `R_sense` (stage 6). Three positions, moved twice, so
each addition inside the loop is tested on its own. `R_iso` at stage 8 does
not move it — feedback stays on the emitter side of `R_iso` (§3.1).

---

## Bench log

### 2026-09-18 — Stage 3: gain network only, no pass transistor

**This is a substitute-parts shakedown, not a characterization run.** The
op-amp and both gain resistors are stand-ins, so nothing here counts toward
the test matrix. It exercises the wiring and the measurement method, nothing
more.

**Setup**

- Sargent-Welch lab trainer: breadboard plus built-in supplies. Yellow
  adjustable supply at 15.0 V; single-supply operation, no negative rail.
- Op-amp: **LM324** (quad, DIP-14) substituted for the OPA2197. The OPA2197 is
  SOIC-only and needs an adapter board that wasn't on hand. A TL074 was tried
  first and rejected: its input common-mode range excludes ground, which
  single-supply operation requires.
- Gain resistors: 5% lab parts, measured out of circuit at
  **R_f = 19.34 kΩ** and **R_G = 9.74 kΩ**, standing in for the
  **23.2 kΩ / 10 kΩ** 0.1% pair (gain **3.32**) in §3.1.
  *This reference was 23.3 kΩ / gain 3.33 until Sep 22, 2026.* 23.3 kΩ is not
  an E96 value and was never orderable; 23.2 kΩ is the stocked neighbour.
  The six `sim/*.asc` files still carry `23.3k` and have **not** been re-run:
  the difference is 0.4% in `R_f` and 0.3% in `R_f + R_g` (33.2 kΩ vs the
  33.3 kΩ the sims used), which is below the precision of every result quoted
  from them, so re-running buys nothing. Recorded here so the discrepancy is
  not re-derived later and mistaken for an error.
- Input from the trainer's 10 kΩ pot.
- DMM probe tips are too large for the breadboard holes and read 0 on contact
  with the board surface. Measure at component legs or via a wire stub.

**Measured** (V_in at pin 3, V_out at pin 1)

| V_in | V_out | V_out / V_in | |
|---|---|---|---|
| 0.28 V | 0.84 V | 3.000 | |
| 2.51 V | 7.59 V | 3.024 | |
| 4.28 V | 12.95 V | 3.026 | **Discarded** — see below |

**Analysis**

- Predicted gain from the measured resistors: 1 + 19.34 / 9.74 = **2.986**.
- **4.28 V point discarded.** It drives the output to 12.95 V, 2.05 V below the
  15 V rail. The LM324's output stage cannot reach the positive rail; its
  output-high level is typically about 2 V below V+, and the guaranteed figure
  is lower still. So this point sits at the ceiling, where gain compresses.
  Its ratio (3.026) matches the 2.51 V point, so the data show no visible
  compression. The discard is precautionary, not evidence of clipping.
- **Gain discrepancy, unresolved.** The two remaining points give 3.000 and
  3.024. With two-decimal readings the 0.28 V point is only good to about ±2%,
  so it cannot tell 2.986 from 3.02. The 2.51 V point is good to about ±0.3%,
  and it reads **1.3% above prediction** — more than meter resolution accounts
  for.
- **Probable cause, not confirmed:** the ground return was a single alligator
  clip squeezing two jumper pins, a marginal joint carrying the whole ground
  return. Contact resistance there offsets the circuit's ground reference from
  the supply's.
  - Caveat on that explanation: a circuit ground *raised* by contact
    resistance lowers V_out relative to the supply ground, so it would read
    the gain low, not high. With the meter referenced to circuit ground it
    cancels entirely. It may not explain the sign of this error.
  - Meter error is the other candidate. A scale error on the ohms range
    largely cancels in R_f / R_G if both are read on the same range, so the
    re-measurement in next-session item 3 separates meter error from a wiring
    fault.

**Status at end of session:** the circuit stopped working after the ground
wiring was redone. Suspect a jumper in the wrong hole group. Unresolved.

**Next session**

1. Re-establish a dedicated GND jack → cream row ground wire, one wire per
   connection, no shared alligator clips.
2. Verify 0.000 V between the GND jack and the ground rail before measuring.
3. Retake the three gain points with V_in under 3.3 V so the output stays clear
   of the LM324 ceiling. Expect ~2.986. In the same session, re-measure R_f and
   R_G out of circuit on the same meter and the same range. A systematic
   ohms-range error partly cancels in the ratio R_f / R_G, so if the
   re-measured ratio still predicts ~2.986 and the gain still reads ~3.02, a
   meter scale error is ruled out and the discrepancy points to the wiring.
4. Resolve the op-amp package question: SOIC-to-DIP adapter, or stay on the
   LM324 through stage 8 and swap before Phase 7.
5. Locate a TO-220 NPN (BD139, TIP31C, or similar) for stage 4.
