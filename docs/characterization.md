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

The bench log refers to these stages, which split the sweep source into steps
small enough to debug one at a time.

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

### What Phase 1 covered (dropped Oct 8, 2026)

**Phase 1 was dropped on Oct 8, 2026** (blueprint §9), as an accepted risk:

- no ≥ 8 MHz DIP-8 part on hand;
- no working bench;
- the narrowed gate tested only the bare loop on a substitute part.

Stages 1–6 below are not run before the order. The oscillation test is at
H4, on the board, with `hardware/CONTINGENCY.md` as the response. The stages
stay documented as the Oct 26 fallback path, which needs a working bench.
The rest of this section is the record of the gate as it stood.

**Scope changed Oct 5, 2026 — the project now targets an assembled PCB**
(blueprint §14). Blueprint **Phase 1 is now stages 1–6 only**: a stability
GO/NO-GO on the composite amplifier, due **Oct 12**, gate is *no oscillation
with real parasitics*, with `C_f` fitted and swept. **Stages 7–8 are no
longer breadboarded** — the clamp, the limiter, `R_iso`, and the load and
short tests move to PCB bring-up (phase H4). They stay documented here
because they are the **fallback path**: if the Oct 26 checkpoint abandons the
PCB, Phase 1 reverts to all eight stages (§9).

**Part for Phase 1: the fastest DIP-8 op-amp in the lab, ≥8 MHz GBW.** Not the
OPA2197 — the SOIC-8 adapters are off the critical path now that the fab
assembles the board (§14.3) — and **not the LM324**, whose 1.3 MHz GBW puts
crossover ~8× below the 2–3 MHz stray input pole this gate exists to find. At
≥8 MHz the substitute's crossover is ≥2.4 MHz, inside the same band as the
OPA2197's ~3.0 MHz, which is the only property the gate depends on.

**Log the supply topology with the result.** A fast DIP-8 part likely needs a
**dual supply**, because its input common-mode range probably excludes ground
(the property that ruled out the TL074, §8), whereas the design runs on +15 V
single. The stability answer still transfers; **no DC figure does** — offset,
swing near ground and low-end linearity all belong to the substitute's rails,
not the design's. Record which part, what GBW, and what rails.

The test-matrix rule at the top of this file stands: a number counts toward §7
only when it comes from the intended parts. **A Phase 1 GO is a go/no-go, not
a §7 entry.**

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
   *Superseded — see the 2026-09-22 blueprint revision: the part is a
   **BD139-16 in SOT-32 / TO-126**, and TO-220 heatsinks and hardware do not
   fit it. TIP31C is no longer in the BOM.*

---

### 2026-09-24 — Stage 4 attempted: no data, bench supply fault

**No data. Nothing here counts toward the test matrix, and nothing here says
anything about the circuit.** Stage 4 (add BD139 and `R_B`, feedback moves to
emitter) was wired but **never successfully powered**.

**What happened**

- Lab trainer **unit 12**. All three supplies — yellow adjustable, +5 V and
  −15 V — read **~1.2 V in magnitude** instead of their set or nominal values.
- The supplies were measured **with the board disconnected**, so the collapse
  was present with no load from the circuit at all.
- **Fuse intact.**
- Hardware fault reported for the unit.

**What this does and does not tell us**

- **The circuit is not implicated, and this session cannot be used as evidence
  against it either way.** The rails were already collapsed with the board
  disconnected. Stage 4's wiring remains **unvalidated — not known-good, and
  not known-bad.** It has never had power applied.
- *Inference, not established:* three rails failing together points to a
  **common upstream element** — shared transformer secondary, rectifier, or
  regulator feed — rather than three independent failures. The **−15 V rail is
  the strongest evidence for this**, because the stage 3 setup is
  single-supply and never connected to it, so nothing in this build could have
  loaded it.
- *Inference:* an intact fuse argues against gross sustained overcurrent
  downstream of it, which is consistent with a fault ahead of the fuse or in a
  regulator stage rather than a short pulled by anything plugged in.
- A common rail sitting near 1.2 V on all three outputs looks like the rails
  being held at some common low value rather than merely unregulated, but
  diagnosing the trainer is not this project's problem — it is the lab's.

**Status at end of session:** blocked on bench hardware. Stage 4 wired,
unpowered, untested. The stage 3 items above were **not** closed by this
session — the gain discrepancy and the ground-wiring fault both remain open.

**Next session**

1. **Use a different trainer**, or confirm unit 12 has been repaired. Either
   way, verify all three rails at the jacks *before* wiring or connecting
   anything.
2. Treat the stage 4 wiring as unverified: re-check it against §3.1 before
   applying power, including that the feedback tap has actually moved to the
   emitter.
3. Confirm the pass transistor on hand is the **BD139-16 (TO-126)** and that
   its tab — **the collector, at +15 V** — is not touching anything grounded.
4. Carry forward all five open items from 2026-09-18; none were addressed.

---

### 2026-11-02/03 — Board 2: first power-up and Block 1 (`hardware/MVP_CARD.md`)

**Intended parts, on the PCB.** This is the first session on the real board,
but none of the §7 tests above was run, so the matrix does not move. Block 1
is a stability check, not a §7 entry. Everything in *Setup* and *Results* is
measured unless marked. Everything under *Off-bench* is labelled analysis or
simulation, and names the sim.

**Setup (2026-11-02, prep)**

- Board 2, C1 empty. Card step 1's shunt check, 1a–1c, passed (male jumper
  pins pushed into the Arduino socket holes). Nucleo seated; RNG1 on J3 and J4.
- **L1** = 100 nF ceramic, measured **95.2 nF** (BK 2704A, capacitance range;
  dielectric unknown) ‖ 200 Ω 1 W metal film, measured **202 Ω** (2 kΩ
  range). Legs twisted together, no solder.
- **J6 as assembled:** its wire openings face into the board, toward
  D3/TP19. Electrically fine. Middle terminal = D (beeps to TP19); G = the
  end by the ▲ mark; S = the other end.
- **Kelvin:** J5 HI → D, LO → S, confirmed by a positive `vds_meas`.
- Port `/dev/cu.usbmodem1103`. Supply KORAD KD3005P, **14.95 V** at the
  leads (DMM), limit 0.100 A.

**Setup (2026-11-03, Block 1).** Scope TDS3034C: Recall Factory Setup, then
the card's settings (AC, BW limit 20 MHz, 10×, probe on TP3 = Q1 emitter).
Probe compensation self-test good: flat-topped ~5 V square at 10×.

**Results**

| Card step | Result | Card pass band | |
|---|---|---|---|
| 6, supply current | 3 mA, CV. Rails not checked (Daniel's call) | 3–25 mA, not CC | pass, at the band's lower edge |
| 7, baseline B | 7.19 mV, but possibly unpowered: superseded. **B = 12.0 mV**, read idle and powered after step 8 | < 10 mV | over the band (the card says record and go on) |
| 8, L1 hold, p-p at TP3 | 12–30 mV over t = 20–40 s; **26.8 mV** (8b); **26.0 mV** with the probe ground moved to TP9, lead flat (8c, CONTINGENCY A2) | ≤ B + 5 = 17 mV | **over**. Broadband: no periodic component at 1 µs/div; the counter read noise (235 MHz with the 20 MHz limit on; "no ref crossing" in 8c). Not probe-ground pickup |
| 8, V and I | **5.193 V, 25.74 mA**, steady over 60 s (`mvp_08_hold_L1.csv`) | 4.8–5.5 V, 23–29 mA | pass |
| 9, open load, p-p at TP3 | **Oscillates.** 9: > 205 mV (clipped at 20 mV/div), ~0.787 MHz read while clipped. 9b: > 2.05 V (clipped at 200 mV/div), **1.149 MHz** (~4.3 div/cycle at 200 ns/div, consistent). 9c: ~0.56 V at 1 V/div, not cleanly periodic, trigger Auto | ≤ B + 5 mV | **fail** |
| 9, V and I | 9: 6.006 V, 0.830 mA. 9b: **6.192 V, 2.998 mA**. 9c: 6.007 V, 0.832 mA | 5.7–6.2 V, \|i\| ≤ 0.5 mA | V in band; **I over** in all three |

V and I are 62-row means of each CSV (`host/h4/mvp_*.csv`). The amplitude at
open load changed from run to run, and the run with the largest oscillation
(9b) had the largest DC errors. The session stopped on the card's step 9
fail branch (CONTINGENCY A3). The diode was not run. The A3 sheet in
`hardware/CONTINGENCY.md` has the same rows.

**Block 1 verdict: fail.** No sustained oscillation with a 200 Ω ‖ 100 nF
load; intermittent ~0.8–1.15 MHz oscillation at open load, C1 empty.

**Figures checked against each other (analysis of the measured values)**

- **L1 current.** 5.193 V / 202 Ω = 25.71 mA against 25.74 mA measured:
  **0.13%** apart (the CSV means give 25.738 vs 25.705 mA). The notes said
  "within 0.1%"; 0.13% is still well inside the ohms reading's own
  uncertainty. The host already subtracts the Kelvin divider's 13 µA.
- **No static current offset.** That agreement, with L1 quiet, shows the
  current channel has no offset near 0.8 mA. So the 0.83–3.0 mA read at open
  load comes with the oscillation, not with the channel.
- **Series resistance, FB_SENSE to the socket** (inferred):
  (6.001 − 5.193) V / 25.74 mA = 31.4 Ω. Less R_iso (22 Ω) and the shunt
  (1 Ω), that leaves **~8.4 Ω for the PTC** plus contacts, inside its
  1.6–15 Ω band. It also absorbs any DAC gain error at 6 V, so it is not a
  measurement of the PTC. Sims 12–14 use it.

#### Off-bench analysis, 2026-11-03

Three new sims, all LTspice, documented in `sim/README.md`:

- **Sim 12** (`sim/12_bare_loop_cin.cir`): CONTINGENCY §3's procedure. Sim
  10/11's topology, plus the PTC, the shunt, D3 as a capacitor, the Kelvin
  divider and the scope probe. It uses sims 08–11's generic op-amp macro-model
  (single pole, no input capacitance), with C_in at IN− stepped.
- **Sim 13** (`sim/13_parallel_load.cir`): sim 12's circuit with a resistor
  across D–S, for the diode question below.
- **Sim 14** (`sim/14_bare_loop_opa197.cir`): sim 12 with **TI's OPAx197
  model** in place of the macro-model. TI's model carries the input
  capacitance itself (6.4 pF per input to ground, 1.6 pF across), so no C_in
  is added. Open load only. Sim 14b (`sim/14b_l1_opa197.cir`) is the same
  deck into L1.

D3's capacitance is the one unknown that matters. The datasheets on hand
don't give it. Distributor listings for other makers' SMAJ12A say
0.8–1.3 nF at 0 V, and it falls with reverse bias, so the sims bracket it at
0.5–2.2 nF.

**(a) Predicted C_f from the measured f (CONTINGENCY §3).** *Simulation,
sim 12.* With the macro-model, no C_in up to 15 pF sustains an oscillation.
**20–30 pF does**, at open load only, at 0.67–0.99 MHz and 1.2–4.5 V p-p at
TP3. The bench read 0.79–1.15 MHz and 0.56 to > 2.05 V. §1's relation
gives **C_f = 0.431 × (20–30 pF) = 8.6–12.9 pF**. That is outside §2A's
5–9 pF and sits at the 20 pF edge of §3 step 4's window.

**Do not fit that value.** The measured f is **well below the ~3 MHz
crossover §2B estimated**, and that is the tell:

- A loop oscillates where its total phase reaches −180°. If the stray C_in
  pole (2.5–4.5 MHz at 5–9 pF) were what ran it out of phase, it would
  oscillate near crossover. Sim 12's small-signal ring at 5–9 pF is at
  1.1–2.6 MHz, depending on D3.
- Running out of phase at ~1 MHz means a lag much lower in frequency than
  the C_in pole. Sim 12 shows where it comes from: at open load there is a
  ring near **0.8 MHz even with C_in = 0**, well damped (each half-cycle
  ~0.3× the last). That is the load-side mode in (b). C_in, or anything else
  that costs phase, only erodes its damping.
- **The sustained oscillation is large-signal**, so its frequency is not the
  small-signal one. It sits below the small-signal ring because the follower
  cuts off on every down-swing; see (b).
- **The macro-model has no excess phase.** In sim 12, the 20–30 pF also
  stands in for every lag the generic op-amp lacks. *Simulation, sims 14
  and 14b (TI's OPAx197 model, which carries its own 6.4 pF per input and
  1.6 pF across them; no C_in added).* At open load with C1 empty, the
  start-up ring is at **0.91 MHz**, each half-cycle **0.83×** the last, and
  the first peak is 616 mV. That is near-marginal, against sim 12's ~0.3× at
  C_in = 0. So most of sim 12's 20–30 pF is lag the macro-model leaves out,
  not stray capacitance on the board. Under L1 it is quiet: after the
  settling curve is removed, 0.24 mV p-p is left over 10–14 µs. The sim's
  ring still decays where the bench's was sustained, so the vendor model is
  somewhat optimistic.

**What it implies.** The bare loop's weak point is at open load, and it is
load-dependent: CONTINGENCY §4's load test points away from R_B and at the
load side. With the vendor model, C_in is TI's 6.4 + 1.6 pF (IN+ is
driven, so C_DIFF counts to ground) plus the board's share at IN-, under
~1 pF. That is 8–9 pF, and §1 gives **C_f ≈ 3.4–3.9 pF**, the top of §2A's
2.2–3.9 pF. *Simulation, sim 14:* 3.3 pF in C1 cuts the open-load ring
from 0.83× to **0.40×** per half-cycle, and its first peak from 616 to
129 mV. **8.6–12.9 pF would over-compensate**: that is CONTINGENCY's *too
much C_f* failure. C_f damps the load-side mode in (b); it does not remove
it. Sim 14 is one point (6 V, D3 1.2 nF). Sims 14c and 14d add 2.2 and
4.7 pF at 6 V, and 0.1 and 0.3 V with C1 empty and 3.3 pF: damping
improves steadily up to 4.7 pF, and 3.3 pF is quiet at both low levels
(`sim/README.md`).

**(b) Why it is quiet with L1 and oscillates at open load.** *Analysis,
checked against sims 12 and 13.*

- **Q1's bias.** At 6 V, open load, the emitter carries only the feedback
  network and the Kelvin divider: 6 V / 33.2 kΩ + 15 µA ≈ **0.2 mA**. Its
  small-signal output resistance is then r_e ≈ 26 mV / 0.2 mA ≈ **130 Ω**.
  Under L1 it carries 26 mA and r_e ≈ 1 Ω.
- **What it drives at open load.** D3, ~0.5–1.5 nF, behind R_sense, R_iso,
  the PTC and the shunt (~41 Ω in all). The pole is
  1 / (2π · (130 + 41) Ω · 1.2 nF) ≈ **0.78 MHz**, inside the loop's band.
  That is the 0.8 MHz mode in (a). The scope probe adds ~12 pF at TP3, which
  is small next to D3.
- **What it drives under L1.** 100 nF behind ~31 Ω: a pole at ~51 kHz,
  and above ~0.5 MHz the load looks like the 31 Ω resistor. That is the
  regime R_iso was chosen for (sim 03: clean from 100 pF to 100 nF). Q1 at
  26 mA is fast as well.
- **Capacitance, not only bias.** Sim 13's "100 nF alone" case draws no
  more bias than open load and is quiet. A resistive load quiets it too, by
  raising the bias: 1 kΩ at 6 V (6 mA) is quiet. So both matter: a mid-size
  capacitance (D3's ~1 nF) seen through a weakly biased follower is the worst
  case. Sim 12: L1 is quiet at every C_in up to 30 pF and every D3 value.
- **Why it is large-signal, and the DC errors.** Swinging 1.2 nF by 2 V p-p
  at 1.15 MHz takes 1.2 nF · π · 1.15 MHz · 2.05 V ≈ **8.9 mA** peak, ~40×
  Q1's 0.2 mA bias. The follower cuts off on each down-swing, and only the
  B-E clamp, through the op-amp, pulls the node down. In sim 12 the real DC
  at the socket barely moves (−6 to −46 mV) and the real DC current stays
  near zero: a capacitive node cannot carry 3 mA of DC. The bench read
  +5 to +191 mV and +0.83 to +3.0 mA. So **the DC errors are in the
  measurement chains**, the difference amp and the Kelvin buffer feeding
  ADCs that sample a ~1 MHz waveform. That is inference: no sim contains the
  sense chains, and the mechanism is not established.
- **Why intermittent.** In both models the open-load loop sits near its
  margin (sim 14 especially). A small shift moves it across: D3's capacitance
  with bias, the PTC warming, the probe, the start-up transient.

**(c) Is 26 mV p-p broadband under load expected?** *Analysis. No sim
covers it: every sim has its noise sources set to zero.*

- **B is not the loop's noise floor.** At idle both DACs are at 0, the
  follower is off and the loop has no gain. B (12.0 mV) is the scope, the
  probe and pickup at TP3, with the loop open.
- **During a hold the loop passes its input to TP3 at gain 3.32**, up to
  about 1 MHz. That includes DAC noise and the Nucleo's digital activity, and
  the ADCs oversample continuously during a hold. One DAC LSB
  (3.3 V / 4095) is **2.7 mV at TP3**.
- **The excess is ~24 mV p-p** (√(26.8² − 12.0²), adding as noise). That is
  ~9 DAC LSB p-p, or roughly 1.5 LSB rms. That is plausible for an MCU DAC
  with the core running. No DAC noise figure is on hand, so it is a
  plausibility argument, not a prediction.
- **The op-amp can't account for it.** 5.5 nV/√Hz × 3.32 over a 20 MHz
  bandwidth is ~0.1 mV rms, ~0.6 mV p-p.
- **So the size is unsurprising. The card's limit was too tight to separate
  noise from oscillation.** B + 5 mV allows less than 2 DAC LSB at TP3. What
  separates the two is periodicity. Step 8 showed none, it didn't move with
  the probe ground (A2), and sim 12 has L1 quiet at every C_in.

#### Diode demo: a resistor across D–S

A diode sweep starts at open load. A 1N4148 on range 1 is effectively off
below ~0.4 V: 18 µA at 0.4 V and 0.65 µA at 0.25 V, against a 40.3 µA LSB
(analysis, LTspice's standard 1N4148 model, I_S 2.52 nA, n 1.752). The
question is which resistor R_p, clamped in J6 alongside the diode (no
solder), keeps the loop free of sustained oscillation from 0.1 V up.

**Answer: 470 Ω.** *Simulation, sim 13.* It is the largest value quiet in
all 28 cases: 7 levels from 0.1 to 6 V, at C_in 20 and 30 pF (the sim 12
fit and margin), with D3 at 0.5 and 1.2 nF. The next value up, 680 Ω,
oscillates at 0.1 V in the worst corner (97 mV p-p, 0.76 MHz). 1 kΩ
oscillates at 0.1–0.3 V in that corner, and 2.2 kΩ in every corner. 330 Ω
and 200 Ω are also quiet. L1's 202 Ω resistor would do, at 2.3× the
subtraction cost below. R_p dissipates 4.8 mW at 1.5 V. The worst case is
the low end, where the follower's bias is smallest, which is where the diode
sweep spends its first third.

**Limits of the answer.** It rests on sim 12's macro-model fit. Sim 14's
vendor model was too slow to sweep R_p. Sim 13's 20–30 pF corners are the
ones that reproduce the bench's oscillation, so they stand in for a loop as
close to the edge as the real one. Sim 14 says the excess phase is real. The low-level behaviour has not
been seen on the bench. R_p also shares the sweep's 40 mA limit: 3.2 mA at
1.5 V.

**Proposed host option, not implemented: `--r-parallel OHM|auto`.**

- **Where.** On `capture`, it records `cal_r_parallel_ohm` in the header. On
  `extract`, `plot` and `model`, it overrides that value.
- **What.** After the recompute agreement check (which must still compare
  the firmware's own i_meas), the DUT current becomes
  `i_dut = i_meas − vds_meas / R_p`. That uses the Kelvin voltage, exactly as
  `Calibration.current_ma` already subtracts the Kelvin divider's
  `V / rdiv` (`host/ct_host/recompute.py`).
- **`auto`.** This fits 1/R_p from the rows with vds_meas ≤ 0.25 V, where
  the diode draws < 1 µA, and prints R_p with its uncertainty. That needs no
  bench step: the sweep's first 17 points already contain it.

**What it costs at the diode's low-current end** (analysis):

- **The LSB doesn't change**: still 40.3 µA, and R_p uses ~2% of the ADC's
  range at 1.5 V.
- **Noise.** The voltage term adds ~1.3 µA rms per point (0.6 mV / 470 Ω),
  against ~5 µA already (σ of i_meas in `mvp_08`).
- **Systematic error** from R_p's uncertainty. At 0.5% (a DMM reading, or
  `auto`'s ~0.8% fit, which gives 5–8 µA over 0.43–0.6 V), it is **~5 µA,
  about 0.12–0.15 LSB**, at any point. Relative to the diode current:

| Diode current | V (1N4148 model) | R_p = 470 Ω draws | 0.5% of that, as share of the diode current |
|---|---|---|---|
| 40 µA (1 LSB) | 0.436 V | 0.93 mA (23×) | 4.6 µA = **11%** |
| 100 µA | 0.477 V | 1.01 mA (10×) | 5.1 µA = 5% |
| 400 µA | 0.539 V | 1.15 mA | 5.7 µA = 1.4% |
| 1 mA | 0.580 V | 1.24 mA | 6.2 µA = 0.6% |

The usable low end, taken as ≤ 5% error, moves from ~1 LSB (40 µA, 0.44 V)
to ~100 µA (0.48 V). That costs the bottom ~40 mV of the exponential region
that n and I_S are fitted from.

**Next (decisions for Daniel)**

1. Whether to run the diode with 470 Ω across D–S. A bench option: one
   `capture` of R_p alone (0–1.5 V) before the diode. i_meas vs vds_meas
   should be a straight line through zero. A DC error like 9b's would show up
   as a departure, with no scope reading, and the same file calibrates R_p.
2. Whether to implement `--r-parallel`.
3. The C1 route (CONTINGENCY *Off-bench after A3*). It now depends on
   whether TI's model is trusted for the op-amp's excess phase. If it is, C1
   is ~3.3–3.9 pF (3.3 pF damps the open-load ring to 0.40× in sim 14), not
   the 8.6–12.9 pF that sim 12's fit gives. Either value is 0603, so it goes
   on a rev 2 (R2-2) or to someone with fine-pitch experience, not the bench.
