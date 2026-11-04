# hardware/CONTINGENCY.md — if the board oscillates at bring-up

Part A is the bench procedure. It is followable from paper, with no
decisions: every branch is a goto, driven by numbers already recorded on the
H4 card (`H4_CARD.md`). Part B, below the line, is why. Nobody needs it at
the bench.

H4 is the first time the whole composite amplifier meets real parasitics.
Phase 1, the breadboard stability gate, was dropped on Oct 8, 2026, as an
accepted risk (blueprint §9). The hedge was meant to be on the board: the
C_f footprint and the parallel alternates. **Nothing in this document is
soldered at the bench** (Daniel, 2026-10-25). Using either hedge means hand
rework, so it is an off-bench resolution, not a bench step (`DECISIONS.md`
R2-2).

---

# Part A — at the bench

**Rules:**

- Supply output OFF before touching any part.
- Nothing on TP6.
- No soldering. Nothing here fits, removes or swaps a part.

**Entry point:** from H4 step 2, 2b or 3 (oscillation, C1 empty) → **A1**.

| # | min | Condition (from the sheet) | Do | Record | Next |
|---|---|---|---|---|---|
| **A1** | 0 | Oscillation frequency f, recorded at H4 2/2b/3 | — | — | f ≥ 20 MHz → **A2**. f < 0.3 MHz → **A1.1**. 0.3 ≤ f < 20 MHz: loop band → **A3** |
| A1.1 | 1 | f < 0.3 MHz | Is the supply in CC? | CC Y/N ____ | Y: output OFF → **STOP**. N: record → **STOP** (off-bench: §6) |
| **A2** | 3 | VHF | Move the probe's ground lead from TP27 to **TP9**, dressed flat along the board. Re-run the H4 step that failed | p-p = ____ mV | < 20 mV: record "probe artefact", go to the H4 step after the failed one. ≥ 20 mV → **A2.1** |
| A2.1 | 1 | VHF persists | Output OFF | — | **STOP** (off-bench: §5, the base stopper needs a prepared part) |
| **A3** | 2 | **Loop-band oscillation, C1 empty** | Scope as the failed step, 1 cycle ≈ 4 div. Measure **f** (scope's frequency readout, mean of 16) and **amplitude**, p-p at TP3. Record in the sheet below, one row per H4 step that oscillated | rows below | Go to the H4 step after the failed one. Block 1 runs to the end; the session stops at **STOP POINT A**. C_f is computed off-bench (§3) |

**A3 recording sheet** (C1 empty, R_B 330 Ω, R_iso 22 Ω as assembled):

| H4 step | Load | f (MHz) | p-p at TP3 (mV) | File |
|---|---|---|---|---|
| 2 | L1 | ____ | ____ | 02_osc_L1.csv |
| 2b | L1, BW off | ____ | ____ | — |
| 3 | open | ____ | ____ | 03_osc_open.csv |

**Filled in, 2026-11-03, board 2, from `MVP_CARD.md`** (its steps 8–9 stand
in for H4 2 and 3; 2b was not run). All measured. 6 V hold, BW limit 20 MHz,
AC coupling, 10× probe on TP3. Idle baseline B = 12.0 mV p-p, powered.

| MVP step | Load | Probe ground | f (MHz) | p-p at TP3 | vds_meas, i_meas | File |
|---|---|---|---|---|---|---|
| 8 | L1 (202 Ω ‖ 95.2 nF, measured) | TP27 | none: broadband, counter read noise | 12–30 mV over t = 20–40 s | 5.193 V, 25.74 mA | `mvp_08_hold_L1.csv` |
| 8b | L1 | TP27 | none at 1 µs/div (counter: 235 MHz, i.e. noise) | 26.8 mV | 5.192 V, 25.75 mA | `mvp_08b_hold_L1.csv` |
| 8c (A2) | L1 | TP9, lead flat | "no ref crossing" | 26.0 mV | 5.192 V, 25.74 mA | `mvp_08c_hold_L1.csv` |
| 9 | open, Kelvin pair in | TP9 | ~0.787 (read while clipped) | > 205 mV (clipped at 20 mV/div) | 6.006 V, 0.830 mA | `mvp_09_hold_open.csv` |
| 9b | open | TP9 | 1.149 (~4.3 div/cycle at 200 ns/div) | > 2.05 V (clipped at 200 mV/div) | 6.192 V, 2.998 mA | `mvp_09b_hold_open.csv` |
| 9c | open | TP9 | not cleanly periodic (trigger Auto) | ~0.56 V at 1 V/div | 6.007 V, 0.832 mA | `mvp_09c_hold_open.csv` |

V and I are the 62-row means of each CSV. A1 sorts both open-load
frequencies into A3 (0.3–20 MHz). Step 8's excess over B is broadband and
did not move with the probe ground (A2), so it is not an oscillation. The
amplitude at open load changed from run to run, and the run with the largest
oscillation (9b) had the largest DC errors. The session stopped there (card
step 9 fail branch); the diode was not run.

Predicted C_f, filled in off-bench from §3: **C_in (effective) = 20–30 pF ;
C_f = 8.6–12.9 pF by §1, not to be fitted.** Analysis and simulation (sims
12–14), 2026-11-03: see §3A below for why this is not a fit value.

**Off-bench after A3.** The predicted C_f is the record. Turning it into a
fix is one of three routes (§7), and the choice is Daniel's:

1. **A rev 2 board with C1 populated** at the computed value, by JLCPCB
   (`DECISIONS.md` R2-2).
2. **Assembly by someone with fine-pitch experience**, fitting C1 at the
   computed value to a board from this order, then re-running H4.
3. **Report it as a measured finding**: the bare loop oscillates at f,
   the C_f that cancels it is analysed, and the fix is not implemented.

---
---

# Part B — why. Not needed at the bench.

Every stability number below is from simulation or analysis, and each says
which.

## 1. The relation

`C_f = C_in · R_g / R_f = C_in × 10 / 23.2 = 0.431 · C_in`, and inversely
`C_in = 2.32 · C_f` (§3.1).

C1 is the C_f footprint across R1 (R_f). Exact cancellation holds β flat with
frequency. **This is analysis, not simulation.** §3.1 states that the stray
input pole is not in sim 08, the sim behind every overshoot figure here.
Treat everything about C_in in this document as analysis.

## 2. C_in, and why the board is first powered with C1 empty

### 2A. Estimate

OPA2197 datasheet input impedance, typical:

- **1.6 pF differential.** IN+ is held by the DAC, so this lands on IN- to
  AC ground.
- **6.4 pF common-mode.** TI's figure may be for both inputs together, so
  count 3.2–6.4 pF per input.

Board share: R1, R2 and C1 pads, the TP6 pad and millimetres of trace, with
no copper pour under the node (§14.5(2)). Under ~1 pF, estimated.

**C_in ≈ 5–9 pF, so C_f ≈ 2.2–3.9 pF**, and **3.3–3.9 pF if TI's 6.4 pF
is per input**, which the datasheet does not say. Blueprint §3.1 records
this as a design finding.

### 2B. First power-up with C1 empty (Daniel, 2026-10-24)

As assembled, C1 is empty (DNP). The uncancelled pole sits at
1 / (2π · 6.99 kΩ · C_in): **4.5 MHz at 5 pF, 2.5 MHz at 9 pF.** Against
~3 MHz crossover that costs roughly **33–50°** of phase, from the ~59° sim 08
implies. That leaves ~10–25°, so the bare loop is predicted to ring hard,
~50–75% overshoot as a second-order estimate, or to oscillate. §3.1 makes
the same argument for the breadboard: "roughly 45° on its own".

The card used to fit the predicted 3.3 pF before first power-up, so that a
known ringing would not send it into Part A. It now powers up bare, for
two reasons:

- **Nothing is at risk.** These are hand estimates, not simulation. At idle
  the firmware holds both DACs at 0, so the follower is off and the loop has
  no gain: nothing can oscillate until a sweep runs. During one, the
  OPA2197's 20 V/µs slew limits a ~3 MHz swing to about 1 V peak, about
  46 mA peak into L1 through R_iso on ~27 mA DC: normal sweep currents. The
  limiter (~75 mA, sim 11) and the 100 mA supply limit (1.5 W for the whole
  board) bound everything else. Q1's worst case is the held short it is
  built for, 0.89 W, ~53 °C on the heatsink (`DECISIONS.md` P-8). D3 clamps
  the DUT node, and the ADC inputs are clamped. P4 (heatsink) and S1
  (100 mA limit) stay preconditions.
- **The bare run is data, not a detour.** A loop-band oscillation there is
  the pole confirming itself: A3 records it.

**Since 2026-10-25 the bare run is the only loop measurement** (Daniel).
C1 is never fitted at H4, so there is no C_f sweep (§3) and no first solder
operation on the bring-up board.

### 2C. Unpowered board-share measurement (optional; needs fast edges and an active probe)

1. C1 empty, board unpowered, no probe anywhere else.
2. Generator: 0.5 V square wave, 100 kHz, ≤ 5 ns edges, into **TP4**
   (FB_SENSE). Generator ground to **TP9** (GND_STAR, where R2 returns).
3. Probe **TP6** (IN-) against TP9. The settled amplitude must be
   **0.301 ×** the input (10 / 33.2), which confirms the right nodes. 0.5 V
   keeps IN- at 0.15 V, below the op-amp's ESD diodes.
4. Measure the 10–90% rise time. The node sees R_f ‖ R_g = 6.99 kΩ, so
   **C (pF) = t_r (ns) / 15.4**. Subtract the probe's tip capacitance.

This gives board stray plus the *unpowered* op-amp input. That is not the
powered value, so it does not replace 2A. It flags a node far above
~3–4 pF unpowered (flux, a bridge, a wrong part). With only a passive 10×
probe (~10–15 pF), the probe dominates and the result is too loose to use.

### 2D. In-loop

This used to be the minimum of the C_f sweep, C_in (effective) = 2.32 ×
C_f at the minimum. With no sweep, the in-loop figure is the one §3 derives
from A3's oscillation frequency. It is model-fitted, not swept, and is
recorded as such in `DECISIONS.md` (C1) and `docs/characterization.md`.

## 3. No C_f sweep: from the oscillation to a predicted C_f (Daniel, 2026-10-25)

**The sweep is retired.** Every row was a hand remove-and-refit of an 0603
on the inverting node. Hand-fitting 0603 parts is not a skill on hand: the
P3 practice, on one board, lost the 3.3 pF parts and could not place an 0603
reliably (`DECISIONS.md` R2-2). The C0G kit left is 1.5, 2.2, 2.7 and
4.7 pF; the 3.3 and 3.9 pF parts are gone.

**No oscillation at the bare run:** C1 stays empty and nothing is computed.
The bare step result (H4 step 5) is recorded as data.

**Oscillation (A3):** §1's relation, `C_f = 0.431 · C_in`, needs C_in.
**f does not give C_in in closed form.** A loop oscillates where its total
phase reaches −180°, which depends on the op-amp, the follower, R_B·C_jc
and the load as well as the C_in pole. So off-bench:

1. Add a capacitor C_in from IN− to ground in sim 08, C1 empty (§3.1:
   the stray pole is not in sim 08, so this is a new run).
2. Step C_in until the simulated bare oscillation frequency matches A3's f
   into L1. Check it against the open-load f.
3. `C_f = 0.431 · C_in`. Round to a stocked 0603 C0G ±0.1 pF value for
   R2-2.
4. Cross-check against §2A's 5–9 pF. If no C_in in ~2–20 pF reproduces f,
   the oscillation is not the C_in pole and C_f is not the fix: §7.

Until that sim is run, the only C_f figure is §2A's estimate, 2.2–3.9 pF.

### 3A. Board 2, 2026-11-03: what §3 gave, and why it is not a fit value

*Analysis and simulation, sims 12–14 (`sim/README.md`). The full write-up is
in `docs/characterization.md`, under the 2026-11-02/03 bench log entry.*

- **Step 2 had to change.** L1 did not oscillate, so f was matched at open
  load. L1 was then checked, rather than the other way round. Sim 12 (sim
  10/11's topology plus the PTC, shunt, D3, Kelvin divider and probe; the
  generic op-amp macro-model) sustains an oscillation only at open load, and
  only from **C_in ≈ 20–30 pF**: 0.67–0.99 MHz against the bench's
  0.79–1.15 MHz. L1 stays quiet at every C_in up to 30 pF. Step 3 then gives
  C_f = 8.6–12.9 pF.
- **Step 4's cross-check fails in spirit.** 20–30 pF is 2–4× §2A's 5–9 pF,
  and it sits at the edge of the 2–20 pF window. The measured f is well below
  the ~3 MHz crossover of §2B, so the phase runs out at ~1 MHz. The C_in pole
  alone cannot do that. Sim 12 rings near 0.8 MHz at open load with
  C_in = 0. That mode is Q1 at ~0.2 mA bias driving D3's ~1 nF, and C_in
  only erodes its damping.
- **With TI's model the fit value falls away.** Sim 14 uses TI's OPAx197
  model, which has its own input capacitance (6.4 pF per input, 1.6 pF
  across them) and adds no C_in. At open load with C1 empty it rings at
  0.91 MHz, each half-cycle 0.83× the last: near-marginal, as on the bench.
  So sim 12's 20–30 pF is mostly excess phase the macro-model lacks. Under
  L1 it is quiet (sim 14b). §1 with the model's 8 pF plus the board's
  ≤ 1 pF gives **C_f ≈ 3.4–3.9 pF**, §2A's upper bracket. 3.3 pF cuts the
  open-load ring to 0.40× per half-cycle (sim 14, one point: 6 V, D3
  1.2 nF). 8.6–12.9 pF would be the *too much C_f* failure below.
  Sims 14c and 14d (2026-11-03) bracket it: at 6 V the ring damps
  steadily from 2.2 to 4.7 pF, with no sign of the too-much side at
  4.7 pF, and 3.3 pF is quiet at 0.1 and 0.3 V too. Same model, open load
  only.
- **The load test (§4) applies.** The fault depends on the load: quiet into
  L1, oscillating open. That points away from R_B and at the load side. A
  resistor across D–S quiets it in simulation: ≤ 470 Ω from 0.1 V up
  (sim 13).

**What H4 can and cannot claim.** Blueprint §3.1 asks for the loop to be
measured with C_f fitted and swept, and for no stability result to come
from one C_f. With C1 empty throughout, H4 meets neither condition. Its loop
result is the bare loop, oscillating or not, and §3.1's R_B conclusion is
not tested.

**The error is two-sided, and the two sides are different failures.**

- **Too little C_f** (C_f < 0.431 · C_in). β *falls* at high frequency, and
  the under-cancelled pole costs phase near crossover: ~17° for 2.34 pF too
  little (§3.1 table, analysis).
- **Too much C_f** (C_f > 0.431 · C_in). β *rises* at high frequency,
  raising loop gain exactly where the follower's phase lag sits. **That is
  the Phase 0 C_comp mechanism** (§12, item 1; sim 02: every C_comp from 1 to
  100 pF oscillated, worse as it grew). It is not a milder version of too
  little. §3.1 puts 2.66 pF too much at ~19° lost and **25.4% overshoot**,
  and the 25% gate is sized on that case. Sim 02 shows the mechanism, not
  the size on this board: it had no stray C_in and no R_iso.
- **Rounding.** §3's computed C_f rounds to the smaller stocked value
  when it falls between two, because the over-compensated side is the Phase
  0 failure. **Superseded for rev 2's C1** (4.7 pF, not 3.3 pF;
  DECISIONS R2-4, 2026-11-03): the bench is less damped than TI's model,
  and that model shows no over-compensation at 4.7 pF.

## 4. The alternates

**R4, R6 and R8 are wired in *parallel* with R3, R5 and R7**
(`tools/check_topology.py` asserts it). Fitting an alternate **lowers** the
value. To **raise** one, remove the SMD part and fit the axial alone.
**Every alternate is hand rework, so none is a bench step** (2026-10-25).
They stay as analysis for an off-bench resolution or a rev 2.

### R_B — R3 (330 Ω 2512), alternate R4. The first lever after C_f.

**Lower it: it helps.** R_B·C_jc is a pole inside the loop.

- Sim 08 overshoot into 100 nF / 200 Ω: **0.3 / 5.3 / 10.3 / 12.7%** at
  100 / 220 / 330 / 390 Ω.
- 330 ‖ 330 (on hand) = **165 Ω**, between sim 08's 100 and 220 Ω rows.
  The pole moves from 13.4 MHz to ~27 MHz, scaled from §3.1, not
  simulated.

Costs, from sim 10 at 100 Ω and 330 Ω (165 Ω sits between, unsimulated):

- held-short load current rises from 107 toward **143 mA**;
- the op-amp's drive rises from 32 mA toward its own 65 mA typical limit (at
  100 Ω it sits in it, ~0.24 W);
- clamp discharge rises: 21.9 mA at 330 Ω (sim 09), ~33 mA at 220 Ω (hand
  estimate);
- BD139 dissipation does not change: R_sense sets it (sim 11).

That is why H4 step 14 is re-run after fitting R4. **Raise it: never, for
oscillation.** 680 Ω gives 21.4% and ~44° (sim 08).

### R_iso — R7 (22 Ω 2512), alternate R8. Only for a load-dependent problem.

**Lower it (R8 in parallel): wrong direction.** It moves toward the bare
loop, stable to ~1 nF and oscillating by 2.2 nF (§12, item 4; sim 03).

**Raise it: remove R7, fit 47 Ω alone.** That gives more isolation of the
load pole. **Not simulated above 22 Ω**; sim 03 compares only 22 Ω with
bare.

**Why 47 Ω and no intermediate value.** R_iso can only go up by replacing
R7 with one axial part, so what matters is bracketing the range, and
22 → 47 Ω does that (Daniel, 2026-10-09). The only 1 W 1% 33 Ω in stock was
$4.43 with 7 left (README shopping list).

Costs:

| | 22 Ω (now) | 47 Ω |
|---|---|---|
| Uncorrected drop at 50 mA | 1.10 V | 2.35 V |
| Worst-case DUT headroom (from 9.06 V) | 9.06 V | 7.81 V |
| Held-short dissipation (107 mA² · R) | 0.25 W | 0.54 W (the 1 W part covers it) |

**Firmware:** set `CT_R_ISO_OHM` to 47. `check_topology.py` fails until you
do, and the host's V_DS check uses it.

**The load test.** R_iso does nothing for the stray *input* pole: it
isolates outputs, and C_f handles the input (§3.7, scope note). A problem
that does not depend on the load (A3's f and p-p alike into L1 and open)
points to R_B first.

### R_sense — R5 (10 Ω 1206), alternate R6. Not a stability lever; not in Part A.

No sim varies R_sense for stability: sims 08 and 09 hold it at 10 Ω. It
sets the limiter threshold, V_BE / R_sense (sim 11).

- **Lower** (R6 in parallel, 10 ‖ 10 = 5 Ω): the threshold rises to
  ~150 mA, and BD139 short-circuit dissipation, which R_sense alone sets
  (sim 11), roughly doubles past the 0.89 W that P-8 budgets for.
- **Raise:** 12 Ω was rejected on thermal margin, and 15 Ω puts the trip
  inside the 50 mA sweep spec (sim 11, §3.1).

Fit R6 only to correct a trip that reads *low* (H4 step 14a, off-bench).

### U1 to OPA2196 — the last component lever (off-bench)

The OPA2196 has a **2.5 MHz** GBW against the OPA2197's 10 MHz (TI), in the
same SOIC-8 dual pinout, rated 4.5–36 V.

- Crossover drops from ~3 MHz to ~0.75 MHz (GBW / 3.32), below the 2–3 MHz
  stray pole and far below R_B·C_jc.
- Slew is 7.5 V/µs rising and 5.5 V/µs falling (TI SBOS869, 10 V step),
  against 20 V/µs. A 10 V step still slews in under ~2 µs, well inside
  `settle_us` = 50 µs.
- Same input capacitance as the OPA2197 (SBOS869), so the §2A C_f estimate
  does not move.
- U1B, the gate amp, changes with it, so the two channels stay identical.
- **Nothing is simulated with it.** Re-fit C_f and re-run the whole H4 card.
- **It needs SOIC rework,** which §14.3 ruled out by hand.

## 5. Not the loop: VHF at the follower (A2)

**Signature:** tens to hundreds of MHz, at the emitter. It changes when the
board or the probe is touched. An emitter follower driving capacitance can
oscillate locally there. C_f cannot reach it, and **no sim covers it**: the
models have no lead or trace inductance.

A long ground lead rings near 100 MHz by itself, which is why A2 changes
the ground path first: a reading that moves with the ground lead is the
probe. A spring ground would settle it, but the board has no safe point for
one near TP3: the nearest ground, C2's GNDPWR pad, is 1.6 mm from C2's
+15 V pad. The S2 setup's earlier "spring ground on TP27" could never reach
either: TP27 is 50 mm from TP3. So a VHF reading at TP3 is always taken on
a clip lead, and its inductance can make ringing that is not in the
circuit. Rev 2 adds a ground point there (`DECISIONS.md` R2-1). L1 is built with short leads (H4 P5) for the same
reason: lead inductance into 100 nF is a classic VHF ringer.

**The bodge.** Q1 is through-hole (soldered by JLCPCB), so a ferrite bead or a
22–47 Ω resistor can go in series with the base leg at the transistor
without cutting copper. That needs a prepared part, hence STOP.

## 6. Not the loop: low frequency, supply or limiter (A1.1)

At the 100 mA first-power-up limit, a supply in CC brownout-cycles and looks
like oscillation. The board idles at ~8 mA (P-14). Otherwise suspect the
decoupling: C5 bulk at the entry, C2 at Q1's collector, 100 nF at each
op-amp.

**In current limit** (H4 step 14c records it): Q2 and the BD139 form their
own loop. Sim 10 sizes its trip and its short recovery (+48% at 100 pF), but
no sim was examined for oscillation *in* limit. No alternate moves it
without also moving the threshold out of sim 11's window. Treat it as §7.

## 7. When it is a rev 2, not a component change

**Any one of these:**

1. **Loop-band oscillation at the bare run (A3).** Since 2026-10-25 no
   component lever is tried at the bench, so this is a decision point, not
   a verdict. The three routes are in Part A, *Off-bench after A3*: a rev 2
   with C1 populated at §3's computed value (R2-2), assembly by someone with
   fine-pitch experience, or a measured finding with the fix analysed but
   not implemented. Daniel chooses, off-bench. R_B at 165 Ω, R_iso at 47 Ω
   and U1 to OPA2196 are analysed in §4 for whichever route is taken.
2. **The fix that works breaks another constraint.**
   - R_iso at 47 Ω takes worst-case headroom to 7.81 V against the stated
     9.06–9.73 V. Either the spec is restated (blueprint §1, §3.1) or it is
     a rev 2. That is Daniel's call, off-bench.
   - R_B low enough to stop it puts the op-amp in its own limit in a held
     short (sim 10's 100 Ω case).
   - R_sense moved out of sim 11's window.
3. **It depends on ground.** It changes when the scope ground moves between
   TP9 and TP27 (A2), or when a bodge wire joins GND and GNDPWR anywhere but
   NT2. The star ground (P-1) is then the problem, and that is copper.
4. **VHF that a base stopper at Q1's leg does not stop.** Trace inductance
   at the follower is layout.
5. **The fix needs a net change.** Moving the feedback tap (§14.5(5)),
   re-ordering R_sense and R_iso, or a part with no footprint.

**A large C_in on its own is not a rev 2.** C_f cancels it at any size. It
matters only as the explanation for criterion 1.

**What a rev 2 costs in time.** There is one revision in the plan (§11,
§14.4). Boards arrive by Nov 3 at the latest; the repo freezes Nov 16. §9's
own figure for an express turn is ~7 days, so a rev 2 decided at bring-up
lands with a week or less before the freeze. The alternative is §9's
fallback, the staged breadboard plan, which needs a working bench (§9).
Which one is Daniel's call. This document only says when the question has
been reached.
