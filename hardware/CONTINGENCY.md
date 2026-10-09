# hardware/CONTINGENCY.md — if the board oscillates at bring-up

H4 is the first time the whole composite amplifier meets real parasitics. That
means the OPA2197, R_B, the BD139, R_sense, R_iso, the B-E clamp and the
limiter, with the board's own stray capacitance at the inverting node. No
breadboard has had any of it. Phase 1, the breadboard stability gate, was
dropped on Oct 8, 2026, as an accepted risk (blueprint §9). The hedge is on
the board: the C_f footprint and the parallel alternates. Every stability number below
is from simulation or analysis, and this document says which.

**Three rules before anything else:**

- **No held-short test while the loop is unstable.** An oscillating loop
  dissipates in the BD139 in ways P-8 never budgeted. Fit the heatsink anyway
  (`README.md`, H4).
- **Nothing on TP6 during a step test.** TP6 is the IN- node, and a probe
  adds 10+ pF there, which is more than the stray being measured.
- **Never judge stability on one C_f.** It is the §3.1 rule, and the reason
  most of this document exists.

---

## Decision tree

Power up through J2 at a 100 mA limit (H4). Run the step test in
[§0](#0-the-test). Then:

```
Is TP3 (emitter) oscillating with the output held steady?
│
├─ YES ── measure the frequency
│   ├─ above ~20 MHz ............ not the loop: VHF at the follower → §5
│   ├─ ~0.5–10 MHz .............. the loop (crossover ~3 MHz) → step 1 below
│   ├─ below ~100 kHz, or bursts  supply or limiter → §6
│   └─ only while in current limit  limiter loop → §6
│
└─ NO ── run the §0 step test
    ├─ overshoot ≤ 25%, 1% in ≤ 5 µs, no ringing → still do the C_f sweep (§3); done
    └─ fails → step 1

Step 1. Fit C_f = 3.3 pF (the §2 estimate). Re-test.
Step 2. C_f sweep, §3: none, 1.5, 2.2, 2.7, 3.3, 3.9, 4.7 pF. Plot overshoot against C_f.
   ├─ clear minimum, ≤ ~15% ............ mis-fit; fit the minimum. DONE
   ├─ worse at every step up from none .. C_in small, over-compensation side; fit the smallest that passes
   ├─ still improving at 4.7 pF ......... node larger than any plausible C_in; find out why (§2B). Do not exceed 4.7
   ├─ flat near 25%, barely responds ..... genuinely marginal → step 3
   └─ oscillates at every value ......... step 3
Step 3. Does it depend on the load? Compare open, 100 pF, and 100 nF ‖ 200 Ω at J6.
   ├─ worse with large C_load ........... R_iso up, §4
   └─ independent of load ............... R_B down, §4
Step 4. Still failing → U1 to OPA2196 (§4, needs SOIC rework), then re-sweep C_f.
Step 5. Still failing, or the fix breaks another constraint → §7: a rev 2 problem.
```

After every change, re-run §0 and log it ([template](#bench-log)).

---

## Have on the bench before the boards arrive

None of the first three items is in the blueprint §8 BOM.

- **C0G 0603 capacitors** for C1: 1.5, 2.2, 2.7, 3.3, 3.9 and 4.7 pF,
  several of each. Rework kills some.
- **Axial resistors, 33 Ω and 47 Ω, ≥ 0.6 W**: R_iso upward (§4).
- **OPA2196IDR ×2**: the last component lever (§4).
- On hand per §8: 330 Ω axial (for R4), 200 Ω 1 W (load), 100 nF ceramic.
- IPA and a brush. Flux on a 7 kΩ node adds both leakage and capacitance.
- Scope ≥ 50 MHz (100 MHz for §2B), 10× probe with a spring ground. An
  active probe (≤ 1 pF) if one exists, for §2B only.

---

## 0. The test

**Load:** 100 nF ‖ 200 Ω 1 W across J6 D–S, with short leads. Range 1
(J3/J4 on RNG1). This matches sim 08's load, so its **10.3%** at R_B =
330 Ω is the reference. The bench path also carries the PTC and the 1 Ω
shunt, a little extra isolation.

**Stimulus:** the firmware has no step command, but a sweep is a staircase
of 100 mV steps:

```
SET vgs_list 0
SET vds_max 6
SET n 61
SET settle_us 20000
SET i_limit_ma 60
SWEEP
```

That is 100 mV steps, held for 20 ms each, peaking at 30 mA into 200 Ω.
Look at steps in the 3–5 V region. Below ~1 V the follower runs at µA bias,
which no sim covers (§3.1, "Not yet simulated").

To hold a DC level for the oscillation check: `SET n 2`, `SET vds_max 5`,
`SET settle_us 1000000`, `SWEEP`. That holds 5 V for 1 s.

**Probe:** TP3 (BD139_E, the emitter) AC-coupled at 5 mV/div, spring ground
to TP27 (GNDPWR).

**Pass (§3.1 bench gate):**

- overshoot **≤ 25%**;
- within 1% inside **5 µs**;
- no sustained ringing.

A correctly fitted C_f should land near sim 08's 10.3%, not at 25%. The 25%
allowance is for C_f mis-fit (§3.1).

**Also check** open and 100 pF at J6 for sustained ringing. The simulated
gate covers 100 pF to 100 nF (§3.1), and 100 pF open is the range-3
operating condition.

---

## 1. The relation

`C_f = C_in · R_g / R_f = C_in × 10 / 23.2 = 0.431 · C_in`, and inversely
`C_in = 2.32 · C_f` (§3.1).

C1 is the C_f footprint across R1 (R_f). Exact cancellation holds β flat with
frequency. **This is analysis, not simulation.** §3.1 states that the stray
input pole is not in sim 08, the sim behind every overshoot figure here.
Treat everything about C_in in this document as analysis.

---

## 2. Measure C_in

**The measurement that counts is in-loop: the minimum of the §3 sweep.** A
and B only set the starting value and catch a node that is wrong.

### 2A. Estimate (no instruments)

OPA2197 datasheet input impedance, typical:

- **1.6 pF differential.** IN+ is held by the DAC, so this lands on IN- to
  AC ground.
- **6.4 pF common-mode.** TI's figure may be for both inputs together, so
  count 3.2–6.4 pF per input.

Board share: R1, R2 and C1 pads, the TP6 pad and millimetres of trace, with
no copper pour under the node (§14.5(2)). Under ~1 pF, estimated.

**C_in ≈ 5–9 pF, so C_f ≈ 2.2–3.9 pF. Start at 3.3 pF**, the value §3.1
already sized its table on.

Blueprint §3.1 records this as a design finding. Its 5–10 pF estimate
covered breadboard rows and leads, not the op-amp, so "smaller on the PCB"
holds for the strays only. **3.3–3.9 pF if TI's 6.4 pF is per input**,
which the datasheet does not say.

### 2B. Board share, unpowered (optional; needs fast edges and ideally an active probe)

1. C1 empty, board unpowered, no probe anywhere else.
2. Generator: 0.5 V square wave, 100 kHz, ≤ 5 ns edges, into **TP4**
   (FB_SENSE). Generator ground to **TP9** (GND_STAR, where R2 returns).
3. Probe **TP6** (IN-) against TP9. The settled amplitude must be
   **0.301 ×** the input (10 / 33.2). That confirms the right nodes. 0.5 V
   keeps IN- at 0.15 V, below the op-amp's ESD diodes.
4. Measure the 10–90% rise time. The node sees R_f ‖ R_g = 6.99 kΩ, so
   **C (pF) = t_r (ns) / 15.4**. Subtract the probe's tip capacitance.

What this gives: board stray plus the *unpowered* op-amp input. That is not
the powered value, so it does not replace 2A. Its job is to flag a node far
above ~3–4 pF unpowered (flux, a bridge, a wrong part) before the sweep
wastes an hour.

With only a passive 10× probe (~10–15 pF) the probe dominates and the result
is too loose to use. Skip 2B.

### 2C. In-loop

Run §3. Then **C_in (effective) = 2.32 × C_f at the minimum.** Record it in
`DECISIONS.md` (C1) and `docs/characterization.md`.

---

## 3. The C_f sweep

**Values:** none, 1.5, 2.2, 2.7, 3.3, 3.9, 4.7 pF (E12, ~20% steps). That
brackets C_in from ~3.5 to ~11 pF.

**Each value:**

1. Fit C1 and clean with IPA. Let it dry.
2. Run §0 at 100 nF ‖ 200 Ω.
3. Log overshoot, 1% settling time and ring frequency.
4. Spot-check open and 100 pF.

**Reading the plot (§3.1 diagnostic):**

| Shape | Meaning | Action |
|---|---|---|
| V-shaped, dropping toward **10–15%** at one value | C_f was mis-fitted. Not a marginal loop | Fit the minimum. Done |
| Sits near **25% across a range** of C_f, little response | The loop itself is short of margin | §4 |
| Worse at every step up from none | You start on the over-compensated side: C_in < ~3.5 pF | Fit none or the smallest passing value; check §2A's assumptions |
| Still improving at 4.7 pF | The node holds more than ~11 pF: more than the op-amp plus a clean layout | Stop at 4.7; clean the node, do §2B |

**The error is two-sided, and the two sides are different failures.**

- **Too little C_f** (C_f < 0.431 · C_in). The stray pole is under-cancelled.
  β *falls* at high frequency and the uncancelled pole costs phase near
  crossover: ~17° for 2.34 pF too little (§3.1 table, analysis).
- **Too much C_f** (C_f > 0.431 · C_in). β *rises* at high frequency,
  raising loop gain exactly where the follower's phase lag sits. **That is
  the Phase 0 C_comp mechanism** (§12, item 1; sim 02: every C_comp from
  1 to 100 pF oscillated, worse as it grew). It is not a milder version of
  too little. §3.1 puts 2.66 pF too much at ~19° lost, **25.4% overshoot**,
  and the 25% gate is sized on that case.
  - Sim 02 shows the mechanism, not the size on this board: it had no stray
    C_in and no R_iso. The magnitudes are §3.1's analysis.
- **On the bench:** on the over side, removing C_f helps; on the under side,
  adding it helps. If a change of one step in either direction makes it
  worse, you are at the minimum.

---

## 4. If C_f does not fix it: the alternates

**R4, R6 and R8 are wired in *parallel* with R3, R5 and R7**
(`tools/check_topology.py` asserts it). Fitting an alternate **lowers** the
value. To **raise** one, remove the SMD part and fit the axial alone.

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

After fitting R4, re-measure the trip point warm and the op-amp current
(the drop across R_B) in a held short (§3.1, H4).

**Raise it: never, for oscillation.** 680 Ω gives 21.4% and ~44° (sim 08).

### R_iso — R7 (22 Ω 2512), alternate R8. Only for a load-dependent problem.

**Lower it (R8 in parallel): wrong direction.** It moves toward the bare
loop, stable to ~1 nF and oscillating by 2.2 nF (§12, item 4; sim 03).

DECISIONS R8 reads "fit if H4 shows ringing into 100 nF". Because R8 is in
parallel, that fit *reduces* R_iso. For ringing, raise it instead.

**Raise it (remove R7, fit 33 or 47 Ω axial):** more isolation of the load
pole. **Not simulated above 22 Ω**; sim 03 compares only 22 Ω with bare.
Costs at 33 / 47 Ω:

| | 22 Ω (now) | 33 Ω | 47 Ω |
|---|---|---|---|
| Uncorrected drop at 50 mA | 1.10 V | 1.65 V | 2.35 V |
| Worst-case DUT headroom (from 9.06 V) | 9.06 V | 8.51 V | 7.81 V |
| Held-short dissipation (107 mA² · R) | 0.25 W | 0.38 W | 0.54 W |

Check the axial's rating against the last row. **Firmware: set
`CT_R_ISO_OHM` to the fitted value.** `check_topology.py` fails until you
do, and the host's V_DS check uses it.

R_iso does nothing for the stray *input* pole: it isolates outputs, and C_f
handles the input (§3.7, scope note). If the problem does not change with
the load, R_iso is not the lever.

### R_sense — R5 (10 Ω 1206), alternate R6. Not a stability lever.

No sim varies R_sense for stability: sims 08 and 09 hold it at 10 Ω. It
sets the limiter threshold, V_BE / R_sense (sim 11).

- **Lower** (R6 in parallel, 10 ‖ 10 = 5 Ω): the threshold rises to
  ~150 mA, and BD139 short-circuit dissipation, which R_sense alone sets
  (sim 11), roughly doubles past the 0.89 W that P-8 budgets for.
- **Raise:** 12 Ω was rejected on thermal margin, and 15 Ω puts the trip
  inside the 50 mA sweep spec (sim 11, §3.1).

**Fit R6 only if the measured trip point disagrees with 75.2 mA.**

### U1 to OPA2196 — the last component lever

The OPA2196 has a **2.5 MHz** GBW against the OPA2197's 10 MHz (TI), in the
same SOIC-8 dual pinout, rated 4.5–36 V.

- Crossover drops from ~3 MHz to ~0.75 MHz (GBW / 3.32). That is below the
  2–3 MHz stray pole and far below R_B·C_jc.
- Cost: slew 7.5 V/µs rising and 5.5 V/µs falling (TI SBOS869, 10 V step)
  against 20 V/µs. A 10 V step still slews in under ~2 µs, well inside
  `settle_us` = 50 µs.
- Same input capacitance as the OPA2197 (1.6 pF differential, 6.4 pF
  common-mode, SBOS869), so the §2A C_f estimate does not move.
- U1B, the gate amp, changes with it, so the two channels stay identical.
- **Nothing is simulated with it.** Sims 08–11 all model the faster part.
  Re-fit C_f (§3) and re-run the whole H4 list: limiter, clamp discharge,
  short recovery.
- **It needs SOIC rework,** which §14.3 ruled out by hand: hot air, or
  someone who has it.

---

## 5. Not the loop: VHF at the follower

**Signature:** tens to hundreds of MHz. It often shows as fuzz or a DC shift
at the emitter, and changes when the board or the probe is touched. An
emitter follower driving capacitance can oscillate locally there. C_f cannot
reach it, and **no sim covers it**: the models have no lead or trace
inductance.

1. **Make sure it is real.** A long scope ground lead rings near 100 MHz by
   itself. Use the spring ground and move the ground point.
2. **Shorten the load leads at J6.** Lead inductance into 100 nF is a
   classic VHF ringer.
3. **Base stopper at the leg.** Q1 is hand-soldered through-hole, so a small
   ferrite bead or 22–47 Ω resistor can go in series with the base leg at
   the transistor, without cutting copper. This is a bodge, not a design
   value.

---

## 6. Not the loop: low frequency, supply or limiter

**Bursts or motorboating at kHz:**

- First check the bench supply is not in current limit. At the 100 mA
  first-power-up limit a brownout cycle looks like oscillation. The board
  idles at ~8 mA (P-14).
- Then check the decoupling: C5 bulk at the entry, C2 at Q1's collector,
  100 nF at each op-amp.

**Only while in current limit:** Q2 and the BD139 form their own loop in
limit. Sim 10 sizes its trip and its short recovery (+48% at 100 pF), but no
sim was examined for oscillation *in* limit. No alternate moves it without
also moving the threshold out of the window sim 11 allows. Treat it as §7
unless something obvious turns up (supply, leads).

---

## 7. When it is a rev 2, not a component change

**Any one of these:**

1. **Loop-band oscillation, or ≥ 25% overshoot, survives every component
   lever:**
   - the full C_f sweep;
   - R_B at 165 Ω;
   - R_iso raised, if the problem depends on the load;
   - U1 to OPA2196, if the rework is possible.

   The margin is then not in the parts.
2. **The fix that works breaks another constraint.**
   - R_iso high enough to stop ringing takes worst-case headroom below
     what the spec states.
   - R_B low enough to stop it puts the op-amp in its own limit in a held
     short (sim 10's 100 Ω case).
   - R_sense moved out of sim 11's window.
3. **It depends on ground.** It changes when the scope ground moves between
   TP9 and TP27, or when a bodge wire joins GND and GNDPWR anywhere but NT2.
   The star ground (P-1) is then the problem, and that is copper.
4. **VHF that a base stopper at Q1's leg does not stop.** Trace inductance
   at the follower is layout.
5. **The fix needs a net change.** Moving the feedback tap (§14.5(5)),
   re-ordering R_sense and R_iso, or a part with no footprint.

**A large C_in on its own is not a rev 2.** C_f cancels it at any size. It
matters only as the explanation for criterion 1. In-loop C_in above
~12 pF, or §2B reading far above the op-amp-free estimate, points at the
IN- node layout.

**What a rev 2 costs in time.** There is one revision in the plan (§11,
§14.4). Boards arrive by Nov 3 at the latest; the repo freezes Nov 16. §9's
own figure for an express turn is ~7 days, so a rev 2 decided at bring-up
lands with a week or less before the freeze. The alternative is §9's
fallback: document the board's failure and finish on the staged breadboard
plan (stages 7–8 of `docs/characterization.md`), which needs a working bench
(§9). Which one is Daniel's
call. This document only says when the question has been reached.

---

## Bench log

| Date | C_f | R_B | R_iso | Load | Overshoot | 1% settle | Ring freq | Notes |
|---|---|---|---|---|---|---|---|---|
| | none | 330 | 22 | 100 nF ‖ 200 Ω | | | | |
| | 3.3 pF | 330 | 22 | 100 nF ‖ 200 Ω | | | | |

Copy the final rows into `docs/characterization.md`. Record the fitted C_f,
and C_in = 2.32 × C_f, in `DECISIONS.md` (C1).
