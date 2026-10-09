# hardware/CONTINGENCY.md — if the board oscillates at bring-up

Part A is the bench procedure. It is followable from paper, with no
decisions: every branch is a goto, driven by numbers already recorded on the
H4 card (`H4_CARD.md`). Part B, below the line, is why. Nobody needs it at
the bench.

H4 is the first time the whole composite amplifier meets real parasitics.
Phase 1, the breadboard stability gate, was dropped on Oct 8, 2026, as an
accepted risk (blueprint §9). The hedge is on the board: the C_f footprint
and the parallel alternates.

---

# Part A — at the bench

**Rules:**

- Supply output OFF before touching any part.
- Nothing on TP6.
- No held short (H4 step 14 on) while any Part A step is open.

**Entry points:**

- from H4 step 2, 2b or 3 (oscillation) → **A1**;
- from H4 step 7 (gate failed at the best C_f) → **A3**.

| # | min | Condition (from the sheet) | Do | Record | Next |
|---|---|---|---|---|---|
| **A1** | 0 | Oscillation frequency f, recorded at H4 2/2b/3 | — | — | f ≥ 20 MHz → **A2**. 0.3 ≤ f < 20 MHz → **A4**. f < 0.3 MHz → **A1.1** |
| A1.1 | 1 | f < 0.3 MHz | Is the supply in CC? | CC Y/N ____ | Y: output OFF → **STOP**. N: record → **STOP** (off-bench: §6) |
| **A2** | 3 | VHF | Move the probe's spring ground from TP27 to **TP9**. Re-run the H4 step that failed | p-p = ____ mV | < 20 mV: record "probe artefact", go to the H4 step after the failed one. ≥ 20 mV → **A2.1** |
| A2.1 | 1 | VHF persists | Output OFF | — | **STOP** (off-bench: §5, the base stopper needs a prepared part) |
| **A4** | 40 | Loop-band oscillation at C_f 3.3 pF | Run H4 Block 2 (the C_f sweep) exactly as written, recording p-p on every row | (on the H4 sheet) | Any row with p-p < 5 mV → **H4 step 7**. Every row ≥ 5 mV → **A5** |
| **A3** | 0 | Gate failed at H4 step 7 | ΔO = O_L1 − O_open, both from step 7 | ΔO = ____ points | ΔO ≥ 10 → **A6**. ΔO < 10 → **A5** |
| **A5** | 15 | Lower R_B | Output OFF. Fit **R4 = 330 Ω axial** (in parallel: R_B becomes 165 Ω). Output ON. Run the H4 step-5 test at the current C1, then at one kit value either side (at the kit's end, the two nearest) (3 runs, files `a5_<cf>.csv`; refit C1 between runs as in Block 2) | rows below | Any run passes the H4 step-7 rule → fit that C_f, record "R4 fitted", go to **H4 step 8**. None passes: A6 not yet done → **A6**; done → **A7** |
| **A6** | 20 | Raise R_iso | Output OFF. Remove **R7** (2512). Fit **R8 = 47 Ω axial** alone. Output ON. Same 3 runs as A5, files `a6_<cf>.csv` | rows below | Any passes → fit that C_f, record "R_iso = 47 Ω", go to **H4 step 8**. None passes: A5 not yet done → **A5**; done → **A7** |
| **A7** | 1 | Nothing on the board fixes it | Output OFF | — | **STOP.** Off-bench: U1 to OPA2196 (§4), then the rev 2 criteria (§7) |

**Pass rule** (the same as H4 step 7): O ≤ 25%, deviation at +5 µs
≤ 1.0 mV, and p-p from +20 to +100 µs < 5 mV. If several runs pass, take the
lowest O; on a tie within 2 points, the smaller C_f.

**A5 / A6 recording sheet:**

| Step | R_B | R_iso | C1 | File | O (%) | dev (mV) | p-p (mV) |
|---|---|---|---|---|---|---|---|
| A5 | 165 | 22 | ____ | ____ | ____ | ____ | ____ |
| A5 | 165 | 22 | ____ | ____ | ____ | ____ | ____ |
| A5 | 165 | 22 | ____ | ____ | ____ | ____ | ____ |
| A6 | ____ | 47 | ____ | ____ | ____ | ____ | ____ |
| A6 | ____ | 47 | ____ | ____ | ____ | ____ | ____ |
| A6 | ____ | 47 | ____ | ____ | ____ | ____ | ____ |

**Off-bench after A5 or A6 passes:**

- **R4 fitted:** H4 step 14 must be re-run, because the held-short current
  and the op-amp drive both rise (§4).
- **R_iso = 47 Ω:** set `CT_R_ISO_OHM` to 47 in firmware.
  `check_topology.py` fails until you do. Worst-case DUT headroom drops to
  7.81 V (§4).

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

## 2. C_in, and why the board is first powered with C_f = 3.3 pF

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

### 2B. Why not power up with C1 empty

As assembled, C1 is empty (DNP). The uncancelled pole sits at
1 / (2π · 6.99 kΩ · C_in): **4.5 MHz at 5 pF, 2.5 MHz at 9 pF.** Against
~3 MHz crossover that costs roughly **33–50°** of phase, from the ~59° sim 08
implies. That leaves ~10–25°. §3.1 makes the same argument for the
breadboard: "roughly 45° on its own".

A first power-up with C1 empty is therefore predicted to ring hard or
oscillate, and would send the card straight into Part A for a reason
already known. So H4 prep P3 fits the predicted 3.3 pF first, and the sweep
works outward from it. "None" stays in the sweep as a data point. If it
oscillates, that is the pole confirming itself.

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

**The measurement that counts is the minimum of the C_f sweep:** C_in
(effective) = 2.32 × C_f at the minimum. Record it in `DECISIONS.md` (C1)
and `docs/characterization.md`.

## 3. The C_f sweep, and reading it

The values (E12, ~20% steps) bracket C_in from ~3.5 to ~11 pF. H4 runs them
outward from 3.3 pF so a session that ends early has the most informative
points.

The step-7 numbers that H4 records, and what they mean (§3.1 diagnostic):

| On the sheet | Meaning |
|---|---|
| A clear minimum, O falling to **10–15%** at one value | C_f was mis-fitted. Not a marginal loop |
| max O − min O **< 8 points**, all near 25% | The loop itself is short of margin. That is why A3 goes on to R_B or R_iso |
| Best at **none** | C_in < ~3.5 pF: the over-compensated side |
| Best at **4.7 pF** | The node holds more than ~11 pF, more than the op-amp plus a clean layout. Clean it; do §2C |

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
- **Tie-break.** On a tie the card takes the smaller C_f, because the
  over-compensated side is the Phase 0 failure.

## 4. The alternates

**R4, R6 and R8 are wired in *parallel* with R3, R5 and R7**
(`tools/check_topology.py` asserts it). Fitting an alternate **lowers** the
value. To **raise** one, remove the SMD part and fit the axial alone.

### R_B — R3 (330 Ω 2512), alternate R4. The first lever after C_f (A5).

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

That is why H4 step 14 is re-run after A5. **Raise it: never, for
oscillation.** 680 Ω gives 21.4% and ~44° (sim 08).

### R_iso — R7 (22 Ω 2512), alternate R8. Only for a load-dependent problem (A6).

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

**The A3 load test.** R_iso does nothing for the stray *input* pole: it
isolates outputs, and C_f handles the input (§3.7, scope note). That is why
A3 sends a problem that does not depend on the load (ΔO < 10 points) to R_B
first.

### R_sense — R5 (10 Ω 1206), alternate R6. Not a stability lever; not in Part A.

No sim varies R_sense for stability: sims 08 and 09 hold it at 10 Ω. It
sets the limiter threshold, V_BE / R_sense (sim 11).

- **Lower** (R6 in parallel, 10 ‖ 10 = 5 Ω): the threshold rises to
  ~150 mA, and BD139 short-circuit dissipation, which R_sense alone sets
  (sim 11), roughly doubles past the 0.89 W that P-8 budgets for.
- **Raise:** 12 Ω was rejected on thermal margin, and 15 Ω puts the trip
  inside the 50 mA sweep spec (sim 11, §3.1).

Fit R6 only to correct a trip that reads *low* (H4 step 14a, off-bench).

### U1 to OPA2196 — the last component lever (A7, off-bench)

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

A long ground lead rings near 100 MHz by itself, which is why A2 moves the
spring ground first. L1 is built with short leads (H4 P5) for the same
reason: lead inductance into 100 nF is a classic VHF ringer.

**The bodge.** Q1 is hand-soldered through-hole, so a ferrite bead or a
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

1. **Loop-band oscillation, or ≥ 25% overshoot, survives every component
   lever:**
   - the full C_f sweep;
   - R_B at 165 Ω;
   - R_iso at 47 Ω;
   - U1 to OPA2196, if the rework is possible.
2. **The fix that works breaks another constraint.**
   - R_iso at 47 Ω takes worst-case headroom to 7.81 V against the stated
     9.06–9.73 V. Either the spec is restated (blueprint §1, §3.1) or it is
     a rev 2. That is Daniel's call, off-bench; at the bench A6 continues.
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
