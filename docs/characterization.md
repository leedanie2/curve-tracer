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
| Voltage accuracy | Compare ADC2 reading vs. 5.5-digit DMM across range | <0.5% error | **Partial, 2026-11-08**: 3 points, 1.7–5.2 V, against a 3½-digit DMM. Agrees within 7 mV; the DMM's own ±0.8% sets the limit, so <0.5% is not yet shown |
| Current accuracy | Sweep into 0.1% precision resistors of known value | <1% error, all 3 ranges | **Partial, 2026-11-08**: range 1 only, 8.5–26 mA into L1 (5% part, DMM ±3%). −0.17 to −0.22 mA against V_DMM / R_DMM, inside the DMM's band; current zero −0.087 mA from the R_p calibration |
| Noise floor | 1000 samples at fixed bias, compute σ | Report per range | Not started |
| CMRR | Common-mode step, measure output shift; repeat with 1% resistors | ~74 dB (0.1%) vs ~54 dB (1%) | Not started |
| Settling time | Step drain DAC, scope the buffer output | Sets minimum `settle_us` | Not started |
| Linearity | Sweep across a precision resistor, fit residuals | Report INL | Not started |
| Self-heating | DC vs. pulsed sweep, same device | Visible droop difference | Not started |
| Known-device check | 2N7000, 2N3904, 1N4148 vs. datasheet curves | Qualitative match | **Partial, 2026-11-08**: 1N4148 within 8–24 mV of two published models; 2N7000 V_GS(th) 2.15 V against the datasheet's 0.8/2.1/3.0 V. No 2N3904 (no BJT mode) |

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
- ~~**No static current offset.** That agreement, with L1 quiet, shows the
  current channel has no offset near 0.8 mA. So the 0.83–3.0 mA read at open
  load comes with the oscillation, not with the channel.~~ **Corrected
  2026-11-13:** 9 and 9c's 0.830 and 0.832 mA are the current channel's
  floor with nothing drawing current, 0.198 + 0.104 · V mA, which reads
  0.824 mA at 6 V with the loop quiet (session 3, (b)). They were not
  oscillation error. Only 9b's 2.998 mA, the largest oscillation, read above
  it, by 2.17 mA. A 0.13% agreement at 25.7 mA couldn't have shown a
  0.1 mA-scale offset anyway: L1's ±3% DMM reading is far coarser.
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
  *Corrected 2026-11-08: the loop is not off at idle.* The buffered sweep
  DAC does not reach 0 V: at code 0 the node sits at **0.18 V** (DMM at
  J6 with L1, idle; the sweep's first row reads 0.177 V). So at idle Q1
  carries ~0.9 mA into L1 and the loop has its full gain. B was taken with
  L1 in J6, so it is the loop's noise at that floor, not the scope's alone.
  The bullets below still hold for the *excess* over B. Session 2 showed
  the consequence: 470 Ω across D–S oscillated at idle.
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

*Superseded on the bench, 2026-11-08: 470 Ω oscillated at idle (781 kHz,
> 205 mV p-p). L1 (200 Ω ‖ 100 nF) was quiet and is the R_p from then on.
See [the session 2 entry](#2026-11-08--board-2-session-2-r_p-accuracy-diode-mosfet-hardwaremvp_cardmd-d)
for why, and for what sim 13 got wrong. The paragraph below is the record
of the prediction as made.*

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
*Implemented 2026-11-03 (`host/`, `--r-parallel OHM|auto|CSV`). Since
2026-11-08 a fitted R_p also subtracts the fit's offset, the instrument's
current zero; see session 2.*

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

---

### 2026-11-08 — Board 2, session 2: R_p, accuracy, diode, MOSFET (`hardware/MVP_CARD.md` §D)

**Intended parts, on the PCB, C1 still empty.** Everything under *Setup*
and *Results* is measured unless marked. Analysis and simulation are
labelled where they appear. V and I figures are the CSV means (22 rows per
20 s hold); the terminal lines read at the bench agree with them to within
one row's noise.

**Setup**

- **R_p** 470 Ω from the drawers, DMM **469 Ω**. **L1** rebuilt with the
  same part values (200 Ω 1 W ‖ 100 nF ceramic): DMM **200 Ω**, capacitor
  not remeasured. BK 2704A; "200 Ω" can only be the 2 kΩ range (the 200 Ω
  range over-ranges at 199.9), so ±(1% + 4 dgt) = **±6 Ω** on the 2704C's
  published spec. The 2704A's own sheet was not found; the 2704C's
  figures stand in for it throughout.
- Scope TDS3034C, Recall Factory Setup, AC, 20 MHz BW, 20 mV/div,
  1 µs/div, 10×. Probe on TP3, ground on TP9.
- Power-up 3 mA, CV. Port `/dev/cu.usbmodem1103`. MCU die 32.2–32.6 °C
  over the session (CSV headers); ambient not recorded.

**Results**

| Step | Result | Card pass band | |
|---|---|---|---|
| 13, 470 Ω in J6, **idle** (no command) | **Oscillates: 781.1 kHz, > 205 mV p-p** (clipped) | no periodic wave | **fail**; 13a/13b not run |
| 13c, L1, idle | 22.4 mV p-p, noise only | — | — |
| 13c, L1, hold 0.1 V | 0.1890 V, 0.8517 mA; 20.0 mV p-p, noise | no periodic wave | pass. Card expected 0.087 V: the DAC floor holds the node at 0.19 V |
| 13c, L1, hold 0.3 V | 0.2648 V, 1.2280 mA; 20.4 mV p-p, noise | no periodic wave | pass (card: 0.260 V, 1.29 mA) |
| 13d, DAC floor | 0.18–0.19 V at the device; DMM at J6 at idle 0.18 V | ≤ 0.20 V | pass |
| 14, L1 calibration (`mvp_14_rp.csv`) | R = **201.31 ± 0.056 Ω**, offset **−0.0874 ± 0.0010 mA**, max residual 0.0156 mA, R² 0.999993; 100 points over 0.1766–1.300 V. Scope quiet | R ±3% of R_DMM; \|offset\| ≤ 0.10 mA; residual ≤ 0.05 mA | pass (+0.66% from 200 Ω) |
| 15a–c | skipped: R_p is L1 | | |
| 15d–f | table below | 2% + 10 mV; 3% + 0.10 mA | pass, all three |
| 15g, TP8 (+3V3) to TP27 (GNDPWR) | 3.30 V | 3.20–3.40 V | pass. The card says TP9 (GND); the two grounds join at the star tie NT2, mV apart |
| 17, 1N4148 ‖ L1 (`mvp_17_diode_rp.csv`) | 100 valid rows, `end: ok`. Scope quiet, one brief bump mid-sweep. R_p auto 200.25 Ω (−0.52%) | ok/ilimit; n 1.0–2.5 | pass |
| 18, 2N7000 ‖ L1 (`mvp_18_mosfet_rp.csv`) | 545 rows (544 valid, 1 flagged), `end: ilimit`. Scope: "a bunch of waves" during the sweep. R_p auto 201.01 Ω (−0.15%) | ≥ 3 curves above zero | pass: 9 curves above 0.2 mA |
| 18c, hold V_GS 2.4 V, V_DS 1.5 V (`mvp_18c_hold_2n7000.csv`) | 1.1314 V, 11.839 mA total; 28.0 mV p-p, counter locked at **748.5 kHz**, faint slow ripple in the noise | — | see (f) |

The 18 header lists 16 gate steps, 1.5–3.0 V. **14 ran**: the sweep hit
40 mA total at V_GS = 2.80 V (row 544, 40.70 mA, flagged) and stopped, so
2.9 and 3.0 V were never applied.

#### (a) Why 470 Ω oscillates and L1 does not

**Is it the 100 nF? Yes.** L1 also biases Q1 harder than 470 Ω does, but
that is the smaller effect.

*Measured.* With nothing running, the loop holds the node at the DAC floor
(0.18–0.19 V), where L1 carries 0.85–0.88 mA. 470 Ω would carry ~0.4 mA
there (analysis; its own idle reading wasn't logged). 470 Ω oscillated at
781 kHz; L1 was quiet at idle, 0.1 V and 0.3 V, and at
2–6 V (15d–f, and Block 1).

*Analysis* (the load as the loop sees it from FB_SENSE, C1 empty). Q1's
emitter resistance r_e = 26 mV / I, plus R_sense, drives R_iso + PTC +
shunt (31.4 Ω) into the node, where R_p sits beside D3 (~1.2 nF near zero
bias). That gives the loop one extra pole and zero:

| Load | Q1 bias | r_e | Pole | Zero | Phase lag, at most |
|---|---|---|---|---|---|
| 470 Ω | 0.42 mA | 62 Ω | 1.56 MHz | 4.5 MHz | 29° near 2.7 MHz |
| 200 Ω alone | 0.90 mA | 29 Ω | 2.55 MHz | 4.9 MHz | 18° near 3.5 MHz |
| 470 Ω ‖ 100 nF | 0.42 mA | 62 Ω | 18.5 kHz | 53 kHz | 29° near 32 kHz |
| L1, 200 Ω ‖ 100 nF | 0.90 mA | 29 Ω | 30 kHz | 58 kHz | 18° near 42 kHz |

- **Without the 100 nF**, the lag lands at 1.5–5 MHz, around the loop's
  crossover (~1–3 MHz), on top of the op-amp's own excess phase. That is the
  load-side mode the 2026-11-03 entry found at open load, with R_p's current
  lowering r_e somewhat.
- **With the 100 nF**, the same-sized lag moves two decades down, to
  20–60 kHz, where the loop has phase to spare. By crossover the load looks
  like 31 Ω plus a capacitor of ~2 Ω: resistive, R_iso's design regime
  (sim 03).
- **Bias** changes the size of the lag (29° → 18° from 0.42 to 0.90 mA), not
  where it lands.

*Simulation, sim 15* (`sim/15_floor_rp_opa197.cir`, TI's OPAx197 model,
C1 empty, held at the floor, D3 1.2 nF). The four loads above:

| Load | Start-up ring | Half-cycle ratio | Residual p-p, 8–12 µs |
|---|---|---|---|
| 470 Ω | 1.69 MHz | 0.66 | 0.77 mV |
| 470 Ω ‖ 100 nF | none | — | 0.01 mV |
| 200 Ω alone | 2.13 MHz | 0.57 | 0.01 mV |
| L1 | none | — | 0.01 mV |

Both loads with 100 nF show no ring at all, at either bias. Both without
it ring, and L1's bias only takes the ratio from 0.66 to 0.57. So the
model agrees with the analysis on the mechanism. **It is optimistic in
absolute terms**, as in sims 14 and 14d: its 470 Ω ring decays where the
bench's was sustained, and at 1.7 MHz rather than the bench's 781 kHz (a
large-signal oscillation runs below the small-signal ring; 2026-11-03 (a)).
So read sim 15 for the ordering, not for margins. One consequence, not
tested: **a plain 200 Ω**, L1 without its capacitor, rings in the same
model only a little less than 470 Ω, so it would likely oscillate on the
bench too.

**What sim 13 got wrong.** Sim 13 used the generic macro-model with 20–30 pF
of C_in, fitted so that the open-load loop oscillated as the bench did. That
fit stood in for excess phase the macro-model lacks (sim 14). It reproduced
one operating point. It did not carry over to a resistive R_p at the floor,
so its 470/330/200 Ω rows were optimistic. Its 100 nF-alone row is the
one the bench and sim 15 support. **Corrected conclusion: with C1 empty,
it is ≥ 100 nF across D–S that keeps the loop quiet at low levels. A
resistor alone (470 Ω, and by sim 15 probably 200 Ω) does not.** The
diode-demo paragraph of the 2026-11-02/03 entry and `sim/README.md`
sim 13 carry the correction.

#### (b) The instrument's current zero, and a host change

*Measured.* With R_p's current removed, a device that is off should read
zero. It reads about **−0.09 mA** in every capture of the session:

| Where | Fitted offset |
|---|---|
| Step 14, L1 alone, 0.18–1.30 V | −0.0874 ± 0.0010 mA |
| Step 17, the diode capture's own rows below 0.25 V (diode off) | −0.099 ± 0.008 mA |
| Step 18, each off gate step (1.5–1.8 V), 0.18–2.6 V | −0.077 to −0.098 mA |

That is ~2 current LSB, consistent with ~90 µV of offset referred to the
1 Ω shunt (buffers and difference amp), or a few ADC counts. Until this
session the host subtracted `V / R_p` only and left the zero in, by
design (`host/ct_host/parallel.py`). Here that matters: the diode fit's
floor is 0.2 mA, so the zero is 43% of the smallest current fitted.

*Analysis.* Subtracting the whole calibration line, `V / R_p + offset`,
gives the device current whether the zero is a current offset or a voltage
offset: an off device reads zero either way. **Since 2026-11-08 the host
does that** for a calibration or `auto` R_p (Daniel's decision, this
session). The offset is recorded in the capture header as
`host_r_parallel_offset_ma`; `mvp_17` and `mvp_18` were re-annotated with
`ct_host annotate --force` (header lines only; rows untouched).

#### (c) Accuracy against the DMM (15d–f)

| Hold | vds_meas | V_DMM | ΔV | DMM ±(0.8% + 1 dgt) | i_meas | V_DMM / 200 Ω | ΔI |
|---|---|---|---|---|---|---|---|
| 15d, 2 V | 1.7337 V | 1.74 V | −6.3 mV | ±24 mV | 8.5261 mA | 8.700 mA | −0.174 mA (−2.0%) |
| 15e, 4 V | 3.4631 V | 3.47 V | −6.9 mV | ±38 mV | 17.1485 mA | 17.350 mA | −0.202 mA (−1.2%) |
| 15f, 6 V | 5.1930 V | 5.20 V | −7.0 mV | ±52 mV | 25.7786 mA | 26.000 mA | −0.221 mA (−0.85%) |

*Analysis.*

- **Voltage.** A line through the three points gives gain **−0.02%** and
  offset **−6 mV**. The DMM's ±0.8% and its 10 mV digit are far larger, so
  the result is: voltage agrees with the DMM to within the DMM. That
  bounds the voltage error at about ±0.8% ± 10 mV. It does not reach
  blueprint §7's <0.5%, which needs the 5½-digit meter §7 names.
- **Current.** Against V_DMM / R_DMM: gain **−0.28%**, offset
  **−0.15 mA**. The reference is the weak part. R_DMM is ±3% (2 kΩ range)
  and V_DMM ±0.8%, so the current gain is known only to about **±3%**, and
  all three errors sit inside that. Each DMM digit in V is 0.05 mA in the
  reference, so the intercept is ±0.05 mA. It agrees with the instrument's
  self-referenced zero from step 14 (−0.087 ± 0.001 mA) to about one
  DMM count.
- **Linearity, self-referenced.** Step 14's line (0.9–6.4 mA) extrapolated
  to these holds predicts the current within +0.001, +0.033 and +0.070 mA
  (+0.27% at 26 mA). L1 dissipates 134 mW at 15f and warms, so this does
  not separate ADC non-linearity from L1's tempco.
- **Reference (15g).** 3.30 V on the 20 V range, ±36 mV: the ADC reference
  is 3.300 V to ±1.1%. Nothing in the rows asks for a rescale.

#### (d) The diode: model card, overlay, and published models

*Measured (extraction), zero subtracted.* `h4/mvp_17_diode.lib`:

| | Zero left in (as first extracted) | **Zero subtracted (adopted)** |
|---|---|---|
| n | 1.6513 ± 0.0085 | **1.7885 ± 0.0031** |
| I_S | 0.826 ± 0.061 nA | **2.680 ± 0.062 nA** |
| R_s | 1.479 ± 0.040 Ω | **1.135 ± 0.016 Ω** |
| Points (≥ 0.2 mA) | 58, 0.547–0.755 V | 60, 0.525–0.755 V |
| Fit residual, rms | 0.80 mV | 0.33 mV |

The fit's own uncertainties shrink 2.7× and its residual 2.4× with the
zero out. That is what a real offset looks like. The 40 rows below 0.2 mA
are dropped as unresolved on range 1.

**Systematic from the zero** (added 2026-11-08, Daniel's decision; `extract`
and `model --zero-bracket -0.087 -0.099`, in the card's header). The zero
itself is known only to the spread of its estimates in (b): −0.087 mA from
the calibration, −0.099 mA from the diode's own off rows. Refitted at each
end:

| Zero | n | I_S | R_s | Fit residual, relative | Points |
|---|---|---|---|---|---|
| −0.087 mA | 1.7877 | 2.663 nA | 1.1374 Ω | 1 | 60 |
| −0.099 mA | 1.8309 | 3.691 nA | 1.0058 Ω | 2.1× | 61 |
| **Spread** | **0.043** | **1.03 nA (39%)** | **0.13 Ω** | | |

The spread is 14× n's statistical error and 17× I_S's, so it is the
uncertainty to quote. It barely moves the curve: V at 0.2, 1, 10 and 20 mA
changes by 2.9, 1.2, 0.1 and 0.4 mV. So the comparison with published
models below stands. The −0.087 mA end fits 2.1× tighter, which weakly
favours it; the headline keeps the calibration's −0.0874 mA.

*Simulated (ngspice-47), the card run back over the measured range*
(`h4/mvp_17_diode_sim.csv`, figure `media/overlay_diode_1n4148.png`):
residual **0.51 mV rms** over the 60 fitted points, **−0.38 mV mean**. The
mean is ngspice's default 27 °C against the fit's 300 K (26.85 °C):
n · ΔV_T · ln(I / I_S) predicts −0.39 mV. Without it the scatter is
0.34 mV, the fit's own.

**Against published 1N4148 models** (analysis; V at fixed current from
`n·V_T·ln(I/I_S) + I·R_s`, V_T at 300 K):

| Model | n | I_S | R_s | V at 0.2 mA | 1 mA | 10 mA | 20 mA |
|---|---|---|---|---|---|---|---|
| **This 1N4148, measured** | 1.789 | 2.68 nA | 1.14 Ω | 519.0 mV | 594.3 | 711.0 | 754.4 |
| LTspice `standard.dio` (`1N4148`, mfg=OnSemi) | 1.752 | 2.52 nA | 0.568 Ω | 511.1 | 584.4 | 693.8 | 730.9 |
| Nexperia `1N4148.txt` | 1.906 | 4.352 nA | 0.6458 Ω | 529.1 | 608.9 | 728.1 | 768.7 |

Sources: LTspice's `lib/cmp/standard.dio`, read from the installed library:
`.model 1N4148 D(Is=2.52n Rs=.568 N=1.752 Cjo=4p M=.4 tt=20n ...)`.
Nexperia's model, `https://assets.nexperia.com/documents/spice-model/1N4148.txt`;
its server refuses scripted downloads, so the three values are as indexed by
a web search on 2026-11-08 and not read first-hand. **Check them against the
file before relying on that row.**

- **The measured curve lies between the two models**: 8–24 mV above
  LTspice's and 10–14 mV below Nexperia's. n is 2% above LTspice's and 6%
  below Nexperia's; I_S is within 6% of LTspice's. n and I_S trade off
  against each other, so V at fixed current is the fairer comparison.
- **What limits it.** One diode of unknown maker, from the drawers. Its
  temperature was not measured, and a silicon junction moves about
  −2 mV/°C, so 5–10 °C is the size of the disagreement with either model.
- **R_s is 2× the models'.** Here R_s is fitted where I·R_s is at most
  23 mV (20 mA), so it also absorbs curvature in the exponential
  (high-level injection) and the leads and J6 clamp between the Kelvin
  point and the junction. The published values are fitted to higher
  currents. Read 1.14 Ω as this fixture's R_s up to 20 mA, not the die's.

#### (e) The 2N7000: extraction, and why there is no `.model` card

*Measured, zero subtracted.* Plot: `media/family_2n7000.png` (the bench's
own render is `h4/mvp_18_mosfet_rp.png`). Curves are smooth: on every gate
step the saturation region fits a quadratic to 3.5–5.7 µA rms, the same as
the off steps, where only L1 conducts.

| Quantity | Value | How |
|---|---|---|
| **V_GS(th)**, I_D = 1 mA, V_DS = V_GS | **2.147 V** | Model-free: log-interpolated between 2.100 V (0.656 mA) and 2.199 V (1.584 mA). The datasheet's definition. onsemi 2N7000/D (onsemi.com/download/data-sheet/pdf/2n7000-d.pdf), same conditions: 0.8 / 2.1 / 3.0 V min/typ/max |
| g_m at V_DS = 1.5 V | 2.8 mS at 0.24 mA; 13.6 mS at 1.5 mA; 39.9 mS at 6.4 mA; 82.7 mS at 18.4 mA | Central difference between gate steps |
| g_m / I_D | 11.8 /V at 0.24 mA, falling to 4.5 /V at 18.4 mA | The same |
| λ, apparent | 0.027–0.029 /V on the 2.4–2.7 V steps (R² ≥ 0.991); 0.04–0.09 /V on the 2.0–2.2 V steps (R² 0.89–0.97) | Per-step line in saturation |
| R_DS(on) at V_GS = 2.80 V | 7.7 ± 0.2 Ω | Not the datasheet's condition (10 V); for reference only |

**The Level-1 fit is not sound over this range**, so no card is written.
The square law needs √I_D linear in V_GS. Here its slope climbs from 0.11
to 0.31 √A/V between 2.0 and 2.7 V, and g_m / I_D falls steadily instead
of following 2 / V_ov. The part is in moderate inversion over almost the
whole range that range 1 can resolve. So the fitted V_th and KP depend on
the window:

| Window | V_th | KP·W/L | R² (√I_D vs V_GS) |
|---|---|---|---|
| Default (slice at 0.527 V, the 2.80 V curve's end) | 2.006 V | 0.101 A/V² | 0.975 |
| Saturation, slice 1.5 V, 2.1–2.7 V | 2.033 V | 0.108 A/V² | 0.984 |
| Top three steps only, 2.5–2.7 V (11–28 mA) | 2.150 V | 0.175 A/V² | 0.9994, one degree of freedom |

V_th moves 0.14 V and KP 1.7× with the window. Any one of them would
misfit the rest of the family by tens of percent. A card that fits needs
either currents well above threshold (V_GS ≥ 3 V, beyond range 1's 50 mA
at these V_DS), or a model with a moderate-inversion region (EKV, or
Level 3 with its subthreshold terms), which `ct_host model` doesn't fit.

**Caveats on the figures above.**

- **V_GS is commanded, not measured.** The gate channel's read-back (H4
  P1b) was skipped. V_GS(th) carries the gate DAC's gain error, which is
  not measured (reference ±1.1% from 15g, gain resistors 0.1%).
- **λ is apparent.** DC sweeps heat the die (up to ~50 mW on the 2.7 V
  step), and the sign of the 2N7000's current tempco at these V_GS is not
  measured here. The output slope mixes channel-length modulation with
  self-heating. The larger λ at low currents is also where the fits are
  poorest.
- **The hold and the sweep differ by 0.6%.** At V_GS 2.4 V and
  V_DS 1.131 V the sweep read 11.909 mA total, the 20 s hold 11.839 mA.
  Not explained; a thermal difference is the obvious candidate.

#### (f) The 748 kHz component during the MOSFET runs

Daniel's read: near-marginal ringing, not oscillation; ADC averaging makes
it negligible on DC readings.

- **Negligible on DC readings: supported by the data** (measured). The 18c
  hold's I has σ = 6.4 µA, against 3.4–4.5 µA on the L1 holds at similar
  currents. So the component adds at most ~5 µA rms per row (0.12 LSB).
  Every gate step of the sweep is as smooth as an L1-only curve, and the
  off steps reproduce the step 14 calibration to −0.15% in R and 0.01 mA
  in zero.
- **Why it stays off the DC** (analysis). The excess over the 20 mV
  noise is about √(28² − 20²) ≈ 20 mV p-p at TP3. Between TP3 and the DUT
  sit ~41 Ω (R_sense, R_iso, PTC, shunt), and at 748 kHz L1's 100 nF is
  2.1 Ω. So the DUT node moves ~1 mV p-p, and ~0.45 mA p-p flows in the
  shunt. That is 9 mV p-p at the difference amp's output, slewing at
  ~0.02 V/µs against its 20 V/µs. The chain stays linear, and a linear
  chain averages a periodic signal to zero rather than rectifying it. That
  is the opposite of Block 1's open-load case, where the node itself swung
  volts. So the mechanism is linearity, and the 64× averaging only trims
  the random part.
- **"Not oscillation" is not established.** A counter that locks at
  748.5 kHz through a 20 s DC hold, with nothing exciting the loop, sees a
  persistent component. That is either a small sustained oscillation or a
  lightly damped mode driven continuously by noise. The Pk-Pk and
  Frequency readings can't separate them. *Near-marginal* fits both;
  *ringing* implies a decay that wasn't seen. A few single-shot
  acquisitions would separate them (constant envelope: sustained; random
  envelope: noise-driven), or the scope's FFT linewidth. That is a bench
  step, so it is left open.
- **Where it comes from: open.** 748 kHz is in the same family as 781 kHz
  (470 Ω, idle) and 0.79 MHz (open load, 11-03). But L1's 100 nF should
  push the sweep loop's load-side mode far below crossover (see (a)), and
  L1 alone was quiet at every level. The new element is the MOSFET and its
  gate path (1 kΩ from the gate buffer into C_iss, with C_gd from the
  drain). It may be a different loop.
- **Caveat for the extraction.** The family was captured while this
  component was present for at least part of the sweep. The data show no
  sign of it at the 5 µA level, and the MOSFET figures above carry that
  caveat.

#### What this changes elsewhere

- Sim 13's conclusion (470 Ω quiet) is refuted on the bench; `sim/README.md`
  sim 13 carries the correction.
- The "loop is off at idle" premise is wrong: corrected in (c) of the
  2026-11-02/03 entry, in `hardware/CONTINGENCY.md` §2B, and on the card's
  step 7.
- The MVP card's R_p is L1 from now on. Its fallback is L1 rebuilt, or
  any resistor with ~100 nF across it (analysis and sim 15); the 330 Ω
  fallback is removed (Daniel, 2026-11-08).
- Blueprint §11 records sim 13 and TI's model, with Phase 0's BD139, as one
  pattern: the model that said stable.

**Still open after this session**

1. The 748 kHz component: sustained or noise-driven, and which loop.
2. Voltage and current accuracy to §7's targets need a better reference
   (5½-digit DMM, 0.1% resistors). This session bounds them at the DMM's
   ±0.8% (V) and ±3% (I).
3. The gate DAC: V_GS is commanded, not measured.
4. A MOSFET model card: needs higher V_GS or a moderate-inversion model.
5. The diode's temperature; the Nexperia figures to be read first-hand.

---

### 2026-11-09 — Off-bench: session 3 planned; sim 16 (100 nF alone)

Session 3 is `hardware/MVP_CARD.md` section E (≤ 30 min, by 2026-11-15):
a breadboard fixture, the stabiliser checked on it at idle and
0.2 / 1 / 6 V, holds into 0.1% resistors, and the 1N4148 again.

**Could the stabiliser be 100 nF with no resistor?** *Simulation, sims 16
and 16b* (`sim/README.md`). TI's model, C1 empty. 100 nF alone across D–S
doesn't ring anywhere simulated: at the floor (where Q1 carries ~6 µA)
through a 15 mV step up and back down, and at 1 V and 6 V from start-up.
That holds both at J6 and on the fixture, 5 cm away behind ~100 nH; the
fixture adds only an overshoot during the 0 → 6 V charge. Open load at the
floor, the reference, rings at 155–290 kHz under the same steps. So by
sim 15's analysis and sim 16, the capacitor is the stabiliser and the
resistor is not needed. The bench decides: this model has been optimistic
twice (blueprint §11), and section E tries the cap first with L1 as the
fallback.

**What the card's 0.1% holds can and can't show** (analysis). V_meas /
I_meas against a 0.1% resistor is the voltage channel over the current
channel. An error in the shared 3.300 V reference scales both and cancels,
so it is not an absolute voltage check. Absolute voltage still rests on
2026-11-08's DMM comparison (within its ±0.8%). The holds replace the
±3% of R_DMM, so current gets bounded at ~±0.9% instead of ±3%.

**What a cap-only stabiliser would and wouldn't change** (analysis). It
removes L1's subtraction (1–3 µA per point of noise, ~1.5 µA systematic,
drift as L1 warms) and frees the 7–15 mA that L1 takes from the 40 mA
limit. It doesn't change the current LSB (40.3 µA) or the diode fit's
0.2 mA floor: those are range 1's. It needs a host change, because the
−0.087 mA zero was subtracted only as part of an R_p calibration line:
`--zero MA|CSV|auto`, built 2026-11-09.

**The zero can't be read with nothing drawing current** (analysis,
2026-11-09; corrects the first version of this plan). The current channel
is single-supply and the ADC unipolar, and 11-08's zero is −2.2 counts.
With L1 the channel sat ~20 counts up, so the zero showed. With the cap
alone it sits on its floor, ~~0 counts, and the firmware prints
i_meas ≈ −V / 400 kΩ~~ (**corrected 2026-11-13:** the floor is the
difference stage's lowest output, 0.198 + 0.104 · V mA, 5.7 counts at
0.24 V and 20.8 at 6 V; session 3, (b)). So the card's cap-only holds
(22b–d) confirm the floor rather than measure the zero. The zero comes from (c), where two
0.1% resistors at three holds give gain, zero and the common-mode term
together. The host's `auto` and hold-CSV zeros refused rows under 5 counts
for the same reason; that guard was below the real floor, and since
2026-11-13 it is the measured floor line.
And it doesn't suit MOSFET families: with no resistor, the node discharges
at low levels only through the 33.2 kΩ feedback network (τ ≈ 3 ms), so an
off gate step would start at the previous step's V_DS.

---

### 2026-11-13 — Board 2, session 3: fixture, cap-only stabiliser, 0.1% resistors, diode, 2N7000 (`hardware/MVP_CARD.md` §E)

**Intended parts, on the PCB, C1 still empty.** Everything under *Setup*
and *Results* is measured unless marked. V and I are CSV means (22 rows per
20 s hold), as in earlier entries. The channel model in (c) uses medians,
because one hold (23c) carries two spikes that move its mean by 6 µA.

**Setup**

- **Breadboard fixture.** J6 to the breadboard with M–M jumpers: orange = S
  (the end away from ▲), red = D (middle), brown = G (the ▲ end). Kelvin
  HI and LO plugged into the D and S columns.
- **Stabiliser:** a second 100 nF ceramic, alone across D–S.
- **0.1% resistors:** 100 Ω (DMM 99.1 Ω, 200 Ω range) and 1 kΩ (DMM
  1.002 kΩ). Both readings are inside the DMM's ohms spec; the 0.1% marking
  is the reference.
- Port `/dev/cu.usbmodem1103`. **Power-up 2 mA, CV** (the KORAD resolves
  1 mA). That is one count under step 21's 3 mA band edge; 11-03 and 11-08
  read 3 mA. MCU die 31.1–32.3 °C.
- Scope TDS3034C on TP3, ground TP9, 20 MHz BW, 20 mV/div, 1 µs/div.
- **The breadboard's centre channel splits the columns.** The first 2N7000
  attempt had its legs outside the J6 columns, so the gate was undriven and
  the family came out flat. It was rewired and rerun; only the rerun is kept.

**Runs not kept** (overwritten at the bench; listed so the gaps are explained)

- 23a's first run was the 1N4148, not the 100 Ω (0.851 V, 37.193 mA).
- Two 23b runs and one 24 run were taken with the bench supply off, for
  example 1.475 V, 16.354 mA. The readings looked like data; see (g).
- One 24 run with the diode not conducting (1.504 V, 0.34 mA).
- **Mislabelled, kept:** `s3_22d2_hold_6v_clean.csv` was the 100 Ω at 6 V,
  not a cap-only hold: 4.572 V, 46.08 mA, ~0.21 W in the resistor. Renamed
  `s3_23d_hold_100r_6v_selfheated.csv`, with a `host_note` in its header.
  Its I/V rises 1.1% over 20 s as the part heats. Not used.
- The 1N4148 may have been in the breadboard during 22a–d (columns and
  orientation unknown). 22d3 repeats 22d with it out: 0.8241 against
  0.8238 mA, so it drew nothing the channel can see.

**Results**

| Step | Result | Card pass band | |
|---|---|---|---|
| 22a, idle | 4.8–6.8 mV p-p | no periodic wave | pass |
| 22b, hold 0.2 V | 0.2362 V, 0.2299 mA; 24.8 mV p-p, counter never locked | no periodic wave; 0.17–0.23 V; \|i\| ≤ 0.20 mA | pass on the wave. I over: it is the channel's floor, (b) |
| 22c, hold 1 V | 1.0061 V, 0.2975 mA; 24.4 mV | no wave; 0.96–1.02 V; \|i\| ≤ 0.20 mA | pass; I over, (b) |
| 22d, hold 6 V | 6.0047 V, 0.8238 mA; 23.2 mV | no wave; 5.80–6.10 V; \|i\| ≤ 0.20 mA | pass; I over, (b) |
| 22d3, hold 6 V, diode out | 6.0049 V, 0.8241 mA; 24.4 mV | as 22d | pass |
| 22e, L1 fallback | not needed | | |
| 23a, 100 Ω, 2 V | 1.5290 V, 15.2469 mA; 27.6 mV | no wave (card expected 1.522 V, 15.22 mA) | pass |
| 23b, 1 kΩ, 2 V | 1.9439 V, 1.7843 mA; 26.0 mV | no wave (expected 1.939 V, 1.94 mA) | pass |
| 23c, 1 kΩ, 6 V | 5.8248 V, 5.6150 mA (median 5.6092); 22.8 mV | no wave (expected 5.817 V, 5.82 mA) | pass |
| 24, 1N4148 ‖ cap (`s3_24_diode.csv`) | 100 rows, `end: ok`. Bench extract, no zero: n 5.3, R² 0.91 | ok/ilimit; n 1.0–2.5 | n out of band; see (d) |
| 25a, L1 calibration (`s3_22f_rp.csv`) | R 201.76 ± 0.058 Ω, offset −0.0909 ± 0.0011 mA, max residual 0.0124 mA, floor 0.177 V. 11-08: 201.31 Ω, −0.087 mA | step 14's bands | pass |
| 25c, 2N7000 ‖ L1 (`s3_25_mosfet.csv`) | 960 rows, 16 steps 2.45–2.75 V, `end: ok`, no trip. 16 of 16 steps in the fit | ≥ 10 steps | pass. Scope: "many steady repeating waves" during the sweep; see (f) |
| 25h, hold V_GS 2.6 V, V_DS 1.5 V (`s3_25h_hold.csv`) | 0.9924 V, 16.414 mA total; 30.0 mV p-p, no ref crossing, faint slow ripple | — | see (f) |

#### (a) Stability: 100 nF alone is quiet, for two-terminal parts

*Measured.* With the cap alone across D–S on the fixture, there was no
periodic wave and the frequency counter never locked: at idle, at 0.2, 1
and 6 V, with each 0.1% resistor beside it, and during the diode capture.
Pk-Pk was 22.8–27.6 mV broadband, as on 11-08 (20–22 mV under L1). Sims 16
and 16b predicted this, and this time TI's model's prediction held. As in
Block 1, a pass means no sustained oscillation under a DC hold; it is not a
phase-margin measurement. MOSFET families stay on L1 by design (the cap
alone can't discharge the node below ~0.6 V), so (f) ran on L1.

**The fixture works.** Kelvin sensing at the breadboard columns, with J6's
clamps and the 5 cm jumpers outside the loop, gave quiet holds and the
calibration, resistor and device data below.

#### (b) With nothing drawing current: the difference amp's floor, not the zero

*Measured.* The four cap-only holds lie on one line,
**I = 0.198 + 0.104 · V mA**, to within 5 µA. It repeats: 22d and 22d3
agree to 0.3 µA, and 2026-11-03's open-load holds (9 and 9c: 0.830 and
0.832 mA at 6.006 V) sit 7–8 µA above it, ten days earlier.

The card expected the channel pinned at 0 counts, reading
≈ −V / 400 kΩ (the firmware's divider correction acting on nothing). It
reads 5.7 counts at 0.24 V and 20.8 counts at 6 V instead.

*Analysis, with TI's datasheet.* (c)'s resistor holds put the zero at
−0.13 mA with a small negative common-mode term. At zero current the
difference stage's output would have to sit ~2–3 mV below ground. It can't:
the stage is an OPA2197 channel on the single +15 V supply, negative rail
and reference both at ground.

- **The swing limit.** TI gives the output swing from the negative rail as
  5 mV typical (25 mV max) with no load, and 95 mV typical into 10 kΩ
  (±18 V, ~1.8 mA, so ~50 Ω).
- **Why it rises with V.** With the output at its rail the loop is open.
  R3 (1 kΩ, from the LO buffer at ≈ V) and R4 (20 kΩ, to the output) then
  hold the inverting input at ≈ 20/21 · V. So the output sinks
  V · (20/21) / 20 kΩ ≈ 48 µA per volt of node voltage.
- **The fit.** At the ADC the measured floor is 4.0 mV + 2.08 mV/V, that
  is, 4.0 mV + 44 Ω × 48 µA/V. Both terms are inside TI's typicals (5 mV,
  ~50 Ω). The stage's own offset and the ADC's can't be separated from the
  4.0 mV.

**What it corrects.**

- **2026-11-03:** open-load 9 and 9c (0.830, 0.832 mA) were this floor, not
  oscillation-driven DC error. Those two runs were oscillating on the scope,
  but their DC current moved by under 10 µA. Only 9b, the largest
  oscillation (> 2 V p-p), read 2.17 mA above the floor. The 11-03 entry,
  its "no static current offset" bullet, the CONTINGENCY A3 sheet and the
  README now say so. The card's 0.5 mA band could not have passed at 6 V.
- **2026-11-09's plan** said the channel would read 0 counts. The host's
  guard against floor rows was a fixed 5 counts, and the floor is above it
  at every voltage. So `--zero auto` took tonight's diode's off rows, which
  sit on the floor, for the zero; see (d).

**What it costs.** A reading within ~2 counts of the line is a bound, not a
measurement. With the cap alone, a device at 0.6 V must draw ~0.4–0.5 mA
before it reads at all. L1 lifts the channel 0.9–6.5 mA clear of the
floor, which is why no 11-08 row was ever on it.

#### (c) Current against voltage: the 0.1% holds

*Measured, solved at the desk.* Above the floor the channel reads
I_read = g · I + b + c · V. The three holds solve it exactly (no degrees of
freedom). The uncertainties come from 4000 draws: each resistor uniform
within ±0.1%, one draw per part, and each hold's standard error.

| Term | Value | Meaning |
|---|---|---|
| g | **1.0080 ± 0.0007** | current gain over voltage gain: current reads 0.8% high against the voltage |
| b | **−0.131 ± 0.002 mA** | the zero |
| c | **−0.0225 ± 0.0010 mA/V** | common-mode term |

Daniel's rough solve, a zero of −0.17 mA at +0.8%, is the c = 0 solution of
23a and 23b: g 1.0087, b −0.176 mA. That misses 23c by 90 µA, so c is
needed.

**L1 disagrees by one LSB.** L1's calibration line (25a) reads the same
instrument's zero another way, as its offset: −0.0909 ± 0.0011 mA against
the resistors' −0.131 mA. That is 1.0 LSB, or 20 standard errors. So one
constant g, b and c can't fit the resistors and L1 together. Two
one-parameter extensions fit both exactly, and these holds can't tell them
apart:

- **A voltage-channel offset δ** of **−10.1 ± 0.5 mV** (the channel reads
  10 mV low). Then g = 1.0014 ± 0.0007, b = −0.141 ± 0.002 mA and
  c = −0.016 ± 0.001 mA/V. On 11-08 the voltage read 6–7 mV low against
  the DMM, inside the DMM's ±10 mV digit: the same sign and size, which is
  weak support.
- **A curved common-mode term**, ~+0.0035 mA/V². There is no independent
  evidence either way.

Holding the 100 Ω and the 1 kΩ at 0.5 V would separate them. The 100 Ω
dissipates 2.5 mW there, so it won't self-heat. A −10 mV δ moves its
reading 0.1 mA, and the 1 kΩ's 0.01 mA. That is a ~3 min bench step, not
run.

- **23d** (the self-heated 100 Ω at 46 mA): its first row is within +0.2%
  of the model, and it then drifts 1.1% as the part heats. That is weak
  evidence that the gain holds to 46 mA.
- **CMRR:** c corresponds to 93 dB (δ = 0) or 96 dB (δ fitted). Sim 05's
  Monte Carlo has a median of 88 dB and a p5 of 79 dB. c × 6 V is −0.10 to
  −0.14 mA, against the card's 0.24 mA estimate.

**The current-accuracy result.**

- **Against the voltage:** current reads **0.1–0.8% high** (±0.07% at
  either end; the spread is δ's question). The zero is −0.09 to −0.14 mA
  and the common-mode term −0.016 to −0.023 mA/V. The card's pass is g
  within ±1.5%: **pass**.
- **Absolute:** voltage still rests on 11-08's DMM check (±0.8% + 10 mV).
  So uncorrected current is good to **±1.6%** worst case (0.8% + 0.8%),
  plus the zero, which the host subtracts. That replaces 11-08's ±3%, which
  was set by the DMM's ohms range. Blueprint §7's < 1% now waits on the
  voltage reference, not the current channel.

*Host.* `ct_host channel` fits the model from hold CSVs and writes it.
`h4/s3_channel.txt` has δ fitted (from `s3_22f_rp.csv`);
`h4/s3_channel_nodelta.txt` has δ = 0. `--zero FILE` applies a model on
`extract`, `model`, `plot`, `simulate` and `overlay`: it subtracts
b + c·V, divides by g, takes δ off the voltage, and flags rows on the
floor (`floor`) so no fit uses them. Beside an R_p calibration line it
applies only g and δ, because the line already holds the zero and c,
measured in place. The guard against floor rows in `--zero auto` and in
hold zeros is now this measured line plus 2 counts, not a fixed 5 counts.

#### (d) The diode, and which result is the headline

**Tonight's `--zero auto` result is withdrawn** (n 1.495, I_S 7.8e-11 A,
R_s 2.62 Ω). Its +0.2168 mA came from rows at 0.205–0.296 V, where the
floor line gives 0.220–0.229 mA: it was the floor. Subtracting it took
~0.36 mA too much from every row above the floor. The host now refuses
`auto` on this file.

**Daniel's suspicion was right in kind.** The offset isn't constant near
the bottom of the channel. The reading there isn't shifted, though; it is
clipped: the larger of the floor and the linear reading. The diode's rows
sit on the floor line, within 0.3 counts, up to 0.570 V. They leave it
within two rows (+2.6, then +6.3 counts).

*Refitted through the channel model* (`--zero h4/s3_channel.txt`): 39 rows
on the floor are left out, and 61 rows fit, 0.59–0.82 V, 0.50–22 mA. The
11-08 capture is refitted through the same model: all 100 rows are clear
of the floor, L1's line is kept, and g and δ are applied.

| Capture | Model | n | I_S | R_s |
|---|---|---|---|---|
| 11-13, cap only | δ fitted | 1.949 ± 0.005 | 4.15 nA | 1.644 Ω |
| 11-13, cap only | δ = 0 | 1.941 ± 0.005 | 4.76 nA | 1.672 Ω |
| 11-08, L1 | δ fitted | 1.7885 ± 0.003 | 2.15 nA | 1.137 Ω |
| 11-08, L1 | δ = 0 | 1.7885 ± 0.003 | 2.66 nA | 1.144 Ω |
| 11-08, L1 | as published (no channel model) | 1.7885 | 2.68 nA | 1.135 Ω |

**Choosing the headline.** The rule was set before the values were
compared:

1. The zero must be measured in the fit's own regime: the same node
   voltages and readings, with every fitted row clear of the floor.
2. Of the fits that pass (1), the one whose n moves least under the
   analysis choices: the channel model (δ fitted or not) and the
   low-current cut (0.2, 1 and 3 mA).
3. As a tie-break, the wider current range.

| | 11-08, L1 | 11-13, cap only |
|---|---|---|
| Zero from | L1's own line: 0.18–1.30 V, readings 0.9–6.5 mA, spanning the diode capture's low end | resistor holds at 1.5–5.8 V, or L1; 1 LSB apart |
| Rows on the floor | 0 of 100 (closest 0.57 mA above it) | 39 of 100 |
| (1) | **pass** | **fail** |
| n, δ fitted / δ = 0 | 1.788 / 1.788 | 1.949 / 1.941 |
| n, cut at 0.2 → 1 → 3 mA (δ fitted) | 1.788 → 1.796 → 1.819 | 1.949 → 1.967 → 2.021 |
| Current range fitted | 0.20–20 mA, 60 points | 0.50–22 mA, 61 points |

**11-08 stays the headline**, on all three. Its values stay as published,
from L1's own zero with no channel model. The channel model adds a
systematic to I_S alone: −0.8% from g, and ×0.80 (2.15 nA) if δ = −10 mV
is real. n doesn't move, and R_s moves by ≤ 0.01 Ω. With the zero bracket,
the systematic ranges are **n 1.788–1.831, I_S 2.15–3.69 nA,
R_s 1.01–1.14 Ω**. A −10 mV δ would also move the published-model
comparison by +10 mV: 18–34 mV above LTspice's, and 0–4 mV below
Nexperia's.

**The two diodes disagree, and the instrument doesn't explain it.** At
equal current, tonight's reads higher by 23 mV at 1 mA, 31 mV at 5 mA,
36 mV at 10 mA and 44 mV at 20 mA. The channel model's terms move V at
1 mA by ≤ 2 mV (the zero's 1-LSB spread), and δ applies to both captures
alike. So the gap is the device or its conditions:

- **Same part?** The record doesn't say whether this was the 11-08 diode;
  the card's "same as 11-08?" field is blank.
- **Temperature?** About 11 K colder would give 23 mV at 1 mA
  (−2 mV/K), but not the slope. A colder junction has a smaller n·V_T, and
  tonight's is larger (n 1.95 against 1.79). The 2N7000 shifts the same
  way, by ~90 mV of gate; see (e).
- **The fixture** puts two breadboard contacts inside the Kelvin loop.
  They add to R_s, which is 0.5 Ω higher tonight, but they can't add 23 mV
  at 1 mA.

So 11-13 is a second 1N4148 measurement on a different fixture, not a
repeat of 11-08.

#### (e) The 2N7000: a model card

*Measured, extraction* (`s3_25_mosfet.csv`, L1's calibration line
subtracted; `extract`/`model --vds-slice 1.1 --vgs-range 2.44 2.76`). Card
`h4/s3_25_mosfet.lib`, `.model 2N7000_S3 NMOS (LEVEL=1 VTO=2.19338
KP=0.139949 LAMBDA=0.0276693)`:

| | Value |
|---|---|
| V_th | **2.1934 ± 0.0048 V** (fit); spread over 30 fit-range choices 14.8 mV (±7.4 mV), the larger, so quote it |
| KP·W/L | **0.1400 ± 0.0032 A/V²**, de-embedded from 0.1442 by (1 + λ · 1.1 V) |
| λ | **0.0277 ± 0.0003 /V**; per step 0.026–0.029 |
| R_DS(on) at V_GS 2.75 V | 11.47 ± 0.24 Ω (not a model parameter) |
| √I_D vs V_GS at 1.1 V | 16 of 16 steps, R² 0.998 |
| Valid for | V_GS 2.451–2.750 V, I_D 5.07–22.9 mA at V_DS 1.1 V; **saturation only** |

*Simulated, ngspice-47, the card run back over the capture*
(`h4/s3_25_mosfet_sim.csv`, `media/overlay_2n7000_s3.png`). For
V_DS ≥ 0.5 V it matches the family to **0.24 mA rms**, worst 0.61 mA
(5.7%, on the 2.45 V step). Below ~0.4 V it reads low by up to **4.2 mA**
(30% at V_DS 0.14 V, V_GS 2.75 V). In moderate inversion the measured knee
is sharper than Level 1's V_DS = V_GS − VTO. 11-08 judged a Level-1 fit
unsound over 2.0–2.7 V, and that still holds. Over 2.45–2.75 V in
saturation, sixteen steps 20 mV apart make it sound, and the card says so
in its `valid for` line and its notes.

**Caveats, in the card's header.**

- **V_GS is commanded**, not read back (gate DAC unmeasured). VTO's
  absolute value carries that error.
- **Ripple**; see (f).
- **λ is apparent:** the die self-heats. The 25h hold rose 0.8% in 20 s
  at 11.5 mW.
- **KP is 0.1–0.8% high** from g (not divided out).

**Against 11-08's three-step fit** (2.5–2.7 V, 1 degree of freedom, no card
written):

| | 11-08, 3 steps | 11-13, 16 steps | Change |
|---|---|---|---|
| V_th | 2.1496 V | 2.1934 V | +44 mV |
| KP·W/L | 0.1756 A/V² | 0.1400 A/V² | −20% |
| λ | 0.0287 /V | 0.0277 /V | −3.5% |

Model-free, the raw curves differ more than the fits suggest. **Tonight's
part needs ~90 mV more gate for the same current**: 6.4 mA at 2.40 V on
11-08 against 2.49 V tonight, and 11.1 mA at 2.50 V against 2.59 V (both
at V_DS 1.1 V). At V_GS ≈ 2.6 V it drew 12.3 mA against 18.2 mA. Gate
voltages are commanded on both days, through the same board and gate DAC,
so a gate-DAC error is common to both and cancels. As with the diode, it is
the part or its temperature, and whether it was the 11-08 2N7000 isn't
recorded. The two fits therefore describe two measurements, not one device
fitted twice. The card describes tonight's. (The card's current budget,
from 11-08's curves, expected 32.8 mA at the 2.75 V step; it drew 22.9 mA,
which is why nothing tripped.)

#### (f) The scope during the MOSFET sweep, and the hold

Daniel's read: step transients plus a small ripple, not a sustained
oscillation.

- **The hold: supported.** The counter found no reference crossing (11-08's
  18c locked at 748.5 kHz). With its drift removed, the hold's current
  scatters 5.1 µA rms, the same as the resistor holds (3.6–3.8 µA) and 18c
  (4.8 µA). The drift itself, +91 µA (+0.8%) rising steadily over 20 s, is
  the part warming, not ripple. Its MOSFET current, 11.59 mA, agrees with
  the family interpolated to 2.600 V (11.64 mA). At that operating point
  there is no sustained oscillation.
- **The sweep: not established.** At 1 µs/div, "steady repeating waves"
  during a sweep can't be told from step transients without the frequency
  or a single-shot view, and neither was recorded. So "transients" is a
  plausible reading, not a shown one. What the data do bound: each step's
  saturation region fits a quadratic to 3.8–9.0 µA rms (11-08:
  4.5–7.4 µA). So whatever the waves were, they move the DC rows by under
  ~10 µA.

**The auto-fit cross-check on a MOSFET family** assumes the lowest gate
step is off. Tonight's lowest step, 2.45 V, conducts, and the auto-fit
reported R_p −12% with a +4 mA offset: meaningless. The host now refuses it
when a family's lowest-step line has an offset beyond ±0.5 mA, and says
why. 11-08's family, whose lowest step is off, still cross-checks (−0.15%).

#### (g) Runs with the supply off

Three runs had the bench supply off and produced plausible numbers.

- **What the board can sense:** ADC1 reads the current and ADC2 the Kelvin
  voltage, and the MCU reads its own die temperature. Nothing reads the
  +15 V rail.
- **A host check that the node follows its command would not have caught
  it.** Take the recorded example, 23b at 2 V: 1.475 V and 16.354 mA. The
  series drop predicts 2.0 − 31.4 Ω × 16.354 mA = 1.486 V. That is 11 mV
  off, inside the DAC's −3/+1% (−60/+20 mV). So the check wasn't built.
  What gave the run away was V/I against the known part: 1.475 V across
  1 kΩ is 1.5 mA, not 16 mA.
- **The supply's own display is the reliable check.** The card now asks
  for it after every part swap: output ON, CV, 2–5 mA at idle. The 2 mA
  allows for tonight's power-up reading.
- *Rev 2 option, not added (Daniel's call):* a +15 V divider into a spare
  ADC pin, so the firmware could refuse to sweep without the rail.

#### What this changes elsewhere

- The 2026-11-03 entry, CONTINGENCY's A3 sheet and the README: open-load
  0.830/0.832 mA are the channel's floor.
- The 2026-11-09 entry: the floor isn't 0 counts.
- `hardware/MVP_CARD.md`: §E results, (a)'s expectation corrected, a
  supply check after every part swap, the centre-channel note, step 21's
  band.
- Host: `channel`, `--zero FILE`, the measured floor guard, the MOSFET
  auto-fit refusal, `model --note`. 203 tests.
- README: the cap-only stabiliser, the fixture, the current-accuracy
  result, the 2N7000 card and family. The diode headline is unchanged, with
  I_S's systematic widened.

**Still open after this session**

1. δ or a curved common-mode term: the 100 Ω and 1 kΩ held at 0.5 V
   would decide it.
2. Were tonight's 1N4148 and 2N7000 the 11-08 parts?
3. The waves during the MOSFET sweep: their frequency, and whether they
   were transients.
4. The gate DAC: V_GS is commanded.
5. Blueprint §7's accuracy targets: the voltage reference.
