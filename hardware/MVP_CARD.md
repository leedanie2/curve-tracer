# MVP bench card: first power-up, Block 1, one diode

The shortest path from a Nucleo off the board to a powered board, a Block 1
oscillation check, and one diode I-V plot. Print it and fill in every
`____`. Every step has a pass and a fail. This is a cut-down form of
`H4_CARD.md`, and where the two differ this card applies. CSVs go in
`host/h4/`. Sections A–C ran on 2026-11-02/03, and Block 1 failed at open
load. **Section D is the next session.**

| Board | Date | Ambient °C | Diode part no. | Port (`P=`) |
|---|---|---|---|---|
| **2** | ____ | ____ | ____ | ____ |

**Board 2 is the bring-up board.** The boards are not physically numbered.
"Board 2" is any of the four untouched boards: C1's two pads bare and flat.
The fifth, the one with solder residue on C1, was the 0603 practice board
and is retired from measurements.

**Rules.**
- Supply output OFF before you touch anything on the board.
- **Don't touch Q1's metal tab.** It sits at +15 V and has no heatsink.
- Nothing goes on TP6. No soldering. No short-circuit test (Block 4).
- On any **STOP**: supply output OFF, then unplug USB.

Commands run in a terminal in `host/`. `HOLD` stands for
`python -m ct_host hold --port $P`. It holds one level and prints a line every
second: `t= N s  vds_meas … V  i_meas … mA`. That `t` is your clock.

## A. Before power (board unpowered)

| # | Do | Pass | Record | Fail → |
|---|---|---|---|---|
| 1a | **Shunt check, from the top**, using the labelled Arduino socket holes. Nucleo off the board, USB unplugged. Push a piece of solid hookup wire into each hole named, clip the DMM leads to the bare wire ends with alligator clips, DMM on continuity (the beep). **(a) Contact check:** the two **GND** holes on the left power socket (CN6) | Beeps | ☐ | The wires aren't making contact. Fix that and redo (a). Don't go on until it beeps |
| 1b | **(b)** **SCK/D13** hole ↔ **MISO/D12** hole. The shunt joins PA5 (D13) to PA6 (D12) | Beeps | ☐ | Move the shunt one row, redo (b) and (c) |
| 1c | **(c)** **SCK/D13** hole ↔ the right socket's **GND** hole | No beep. A faint glow from LD2 is the DMM driving the LED, not a beep | ☐ | The shunt is on GND–PA5. Move it one row, redo (b) and (c). Two moves and still failing: **STOP** |
| 2 | **Seat the Nucleo** on board 2: CN7 into J7, CN10 into J8. Pin 1 of CN7 and CN10 is the end nearest the Nucleo's USB connector; that end goes to the square-pad end of J7 and J8. Every pin goes into a hole and none is left over. J3 and J4 jumpers on **RNG1** | Seated, no pins left over | ☐ | Pull it out and redo |
| 3 | **J6.** Find the pins first: **G is the end by the ▲ mark, D is the middle** (it beeps to TP19), S is the other end. On board 2 the wire openings face into the board, toward D3/TP19; that is how it was assembled and is fine. L1 (100 nF ‖ 200 Ω, leads ≤ 3 cm) goes to D and S. Kelvin pair: J5 pin 1 (HI) to J6 D, J5 pin 2 (LO) to J6 S. G stays empty | All four wires tight | ☐ | Retighten |
| 4 | Nucleo USB to the laptop. Run `python -m ct_host ports`, then set the port, for example `P=/dev/cu.usbmodem103`: use the number `ports` printed | The Nucleo is listed | port above | Replug USB, redo. Still not listed: **STOP** |
| 5 | **Supply (KD3005P).** Its **A display shows the actual current, not the limit**, so the limit is set into a short. **LOCK must be off** (hold the VOLTAGE knob to toggle it). Turn the CURRENT knob fully down. Short the red and black leads together, output ON, and turn CURRENT up until the A display reads **0.100**. Output OFF, remove the short. Set **15.00 V**. Output ON with the leads free. DMM on DC V: red probe on the red lead, black probe on the black lead. Output OFF | +14.90 to +15.10 V | ____ V | Negative: the leads are swapped. Fix and redo. *J2 has no reverse-polarity protection* |

**Scope setup** (once, board still unpowered).
1. Press **Save/Recall**, then **Recall Factory Setup**. The TDS3034C has
   no Default Setup button. Set the switch on the probe body to **10×**.
2. CH1 menu: Probe **10×**, Coupling **AC**, Bandwidth limit **ON** (20 MHz).
3. Volts/div **20 mV**. Time/div **1 µs**.
4. Trigger: Source **CH1**, Mode **Auto**, Level **0 mV**.
5. Measure menu: add **Pk-Pk** and **Frequency** for CH1.
6. Hook the probe tip on **TP3**, beside Q1. Clip the probe's ground lead to
   **TP27**'s loop, near TP9. Keep the lead away from Q1.

AC coupling hides the steady DC level, so only ripple or oscillation shows.
In Auto mode the trace is drawn even when nothing triggers it.

## B. Power-up and Block 1 (oscillation, C1 empty)

| # | Do | Pass | Record | Fail → |
|---|---|---|---|---|
| 6 | Push a **female jumper wire** onto each J2 pin, then clip the supply's red lead to the jumper on J2 **"+15V"** and the black lead to the jumper on J2 **"GND"**. Never clip straight onto J2: an alligator clip there can bridge both pins. Output ON. Read the supply's A display (actual current) after 5 s | 3–25 mA, and the supply is not in CC (current limit) | ____ mA | **STOP** |
| 7 | **Baseline, board powered.** Supply output ON from step 6; no `HOLD` running. Nothing is running, so the loop can't oscillate (CONTINGENCY §2B). Read Pk-Pk. A reading taken with the output OFF is not B | Flat, fuzzy line; Pk-Pk < 10 mV | B = ____ mV | Check the probe tip, the ground clip and 10× in both places. Then record B and go on |
| 8 | **L1 load.** `HOLD --vds 6 --seconds 60 -o h4/mvp_08_hold_L1.csv`. Between t = 20 and 40 s: **(a)** scope Pk-Pk; **(b)** one terminal line | (a) ≤ B + 5 mV, trace looks like step 7's. (b) vds_meas 4.8–5.5 V, i_meas 23–29 mA | (a) ____ mV ; (b) ____ V, ____ mA | (a) Read Frequency, f = ____ MHz. (b) Record it. Either way, go to 9 and stop after it |
| 9 | Output OFF. Take L1 off J6; the Kelvin pair stays. Output ON. `HOLD --vds 6 --seconds 60 -o h4/mvp_09_hold_open.csv`. Read as step 8 | (a) ≤ B + 5 mV. (b) vds_meas 5.7–6.2 V, \|i_meas\| ≤ 0.5 mA | (a) ____ mV ; (b) ____ V, ____ mA | As step 8 |

■ **Any fail at step 8 or 9: STOP.** Block 1 failed, and the filled-in rows are
the result. CONTINGENCY A1 sorts f off-bench (A3 if 0.3–20 MHz). Don't run the
diode. **All pass:** Block 1 passed. Go on.

## C. One diode I-V (only if Block 1 passed)

| # | Do | Pass | Record | Fail → |
|---|---|---|---|---|
| 10 | Output OFF. Fit a through-hole silicon diode (1N4148, or a 1N400x) in J6: **anode to pin 2 (D), banded end to pin 3 (S)**. Kelvin pair stays. Output ON. `python -m ct_host capture --port $P --vgs 0 --vds-max 1.5 --n 100 --i-limit 40 --device <part> -o h4/mvp_10_diode.csv`. Then `grep -v '^#' h4/mvp_10_diode.csv \| tail -1 \| cut -d, -f4,5` (the last V and mA). **Output OFF** | Last row 10–40 mA at about 0.6–1.0 V. `end : ok`, or `ilimit` (the rows before it are kept) | ____ V, ____ mA ; end ____ | Under 1 mA: the diode is backwards. Output OFF, flip it, redo once |
| 11 | `python -m ct_host extract h4/mvp_10_diode.csv --type diode` | Prints n, I_S and R_s; n is 1.0–2.5 | n ____ ; I_S ____ ; R_s ____ | Write down the error line |
| 12 | `python -m ct_host plot h4/mvp_10_diode.csv --save h4/mvp_10_diode.png`, then `open h4/mvp_10_diode.png` | One curve, flat near 0, then steep. The title is the part name, **not** "[SIMULATED]" | ☐ | Record what it shows |

■ **Done.** Output OFF, USB out. Hand back this sheet and `host/h4/mvp_*`.

---

**Where the pass bands come from.** Step 8: 6 V across L1 (200 Ω ±5%), with
R_iso 22 Ω, the 1 Ω shunt and the PTC (1.6–15 Ω) in series, and the DAC
between −3% and +1%. That gives 23.5–28.2 mA and 4.85–5.42 V. Step 9: no load
current, so the node reads the command. The band is wide on purpose: it shows
the command reaches the board (step 1's shunt) and both ADCs read, not their
accuracy. The 5 mV band is H4 step 2's. The predicted loop-band oscillation
is far larger than that, ~1 V peak at the op-amp (CONTINGENCY §2B).

**What a pass means.** A pass at steps 8–9 shows no sustained oscillation
under a DC hold. It does not measure phase margin or ringing (H4 step 5, not
run).

**No heatsink (no Sil-Pad).** CONTINGENCY §2B listed the heatsink as a
precondition of the bare power-up. This card runs without one, on this hand
estimate (R_th j-a 100 °C/W, `DECISIONS.md` P-8). Q1 dissipates 0.24 W in
steps 8–9, about 49 °C at the junction. At the step 10 sweep's 40 mA limit
it is 0.51 W, about 76 °C, and only for a few seconds. Even a held short,
bare, is 114 °C against a 150 °C limit.

**Not checked here** (it stays on `H4_CARD.md`): the BW-off VHF check (2b),
the step-test overshoot (5), the rail voltages (4), and Blocks 3–4.

---

## D. Session 2: parallel load, accuracy, diode, MOSFET (~45 min)

Board 2, C1 still empty. Block 1 failed at open load on 2026-11-03, so
nothing goes in J6 on its own again. In this section every device shares
J6 with **R_p**, a resistor clamped across D–S, except L1 in step 15. The
scope stays on **TP3** for the whole session, with its **ground lead on
TP9** (GND). No soldering. The rules at the top of the card still apply.
Supply output OFF before every change at J6.

| Date | Ambient °C | R_p marked | R_p by DMM (R_DMM) | Diode part no. | MOSFET part no. | Port (`P=`) |
|---|---|---|---|---|---|---|
| ____ | ____ | ____ Ω | ____ Ω | ____ | ____ | ____ |

**Parts.**
- **R_p**: 470 Ω, any wattage, from the drawers. Fallbacks, in hand: 330 Ω
  1 W (the R4 spares, LCSC C172941) and 200 Ω 1 W (L1's resistor, C172930).
- **L1**: as measured on 2026-11-02, 95.2 nF ‖ 202 Ω.
- One 1N4148 or 1N400x.
- Optional, for step 18: a 2N7000 or BS170.

**Three wires in one J6 clamp.** From step 17 on, D and S each hold the
Kelvin wire, a lead of R_p and a lead of the device. Twist R_p's lead
around the device's lead before you clamp them. Then tug each of the three
wires: none may move.

**Time plan.**

| Setup | 13 (a) | 14 (b) | 15 (c) | 16–17 (d) | 18 (e) |
|---|---|---|---|---|---|
| 10 min | 3 min | 2 min | 10 min | 5 min | 6 min |

If time runs short, drop step 18 first, then 15's L1 rows (15d–15f).

### Setup

Steps 2–7 of section A/B, with three changes:
- In step 3, J6 is empty: the Kelvin pair goes to J6 D and S, G stays
  empty, and there is no L1.
- In step 6 of the scope setup, the ground lead goes on **TP9**.
- In step 7, record B again: B = ____ mV.

Before you clamp anything, measure R_p on the DMM's Ω range with the leads
clipped on and fill in R_DMM in the header. A 5% part reads 446–494 Ω, a
1% part 465–475 Ω.

### 13 (a). R_p alone: is the loop quiet at the bottom of the range?

This tests the sim 13 prediction that a 470 Ω resistor across D–S keeps the
loop quiet from 0.1 V up. That prediction rests on the generic op-amp model
with 20–30 pF of fitted input capacitance. **Pass for every hold: no
periodic wave on the scope.** A periodic wave is a repeating shape: at
1 µs/div, ~1 MHz is about one cycle per division. The broadband fuzz of
step 7 is a pass. Each hold runs 20 s; read the scope and the terminal at
t = 10–15 s.

The expected readings come from R_p's share of the series string:
470 / (470 + 22 + 8.4 + 1) = 0.937 of the command.

| # | Do | Pass | Record | Fail → |
|---|---|---|---|---|
| 13a | Output OFF. Clamp R_p in J6 D–S, with the Kelvin wires. Output ON. `HOLD --vds 0.1 --seconds 20 -o h4/mvp_13a_hold_rp_0v1.csv` | No periodic wave | Pk-Pk ____ mV ; ____ V, ____ mA | Read Frequency: f = ____ MHz. Go to 13c |
| 13b | `HOLD --vds 0.3 --seconds 20 -o h4/mvp_13b_hold_rp_0v3.csv` | No periodic wave | Pk-Pk ____ mV ; ____ V, ____ mA | As 13a |
| 13c | **Only if 13a or 13b failed.** Output OFF. Swap R_p for the 330 Ω 1 W. Redo 13a and 13b. If either fails again, swap to the 200 Ω 1 W and redo them once more. Record the R_p you end on in the header, and use it from here on | Both holds pass | R_p used: ____ Ω ; Pk-Pk ____ / ____ mV | 200 Ω also oscillates: skip 14, 15a–c, 16, 17 and 18. Do 15d–15f (L1), then **STOP** |

**The readings at 13a also measure the DAC floor.** With 470 Ω, 13a should
read about **0.094 V and 0.20 mA**, and 13b about **0.281 V and 0.60 mA**.
If 13a reads well above 0.094 V, say 0.15 V or more, the sweep DAC is
holding a floor: its buffered output is guaranteed only down to 0.2 V,
0.66 V at the node (blueprint §3.5). That is a result, not a fail. Record
it. The loop then never runs lower than that floor, so the hold still tests
the lowest point the diode sweep can reach.

### 14 (b). R_p alone: calibrate it

| # | Do | Pass | Record | Fail → |
|---|---|---|---|---|
| 14 | `python -m ct_host capture --port $P --vgs 0 --vds-max 1.5 --n 100 --i-limit 40 --device R_p -o h4/mvp_14_rp.csv`, then `python -m ct_host extract h4/mvp_14_rp.csv --type resistor` | A straight line through zero: (i) R_fit within ±3% of R_DMM; (ii) \|offset\| ≤ 0.10 mA; (iii) max residual ≤ 0.05 mA | R_fit ____ Ω ; offset ____ mA ; max residual ____ mA ; lowest V ____ V | (i) or (ii) out of band: record it and go on (step 15 says whether voltage or current is off). (iii) out of band: look at the scope. Run it once more. Still out of band: go on, and in 17 use `--r-parallel <R_DMM>` in place of the file |

`extract --type resistor` fits I = V / R_fit + offset over every row. The
offset is the instrument's current zero; it is a result. The lowest V is
where the sweep starts, which is the DAC floor again.

### 15 (c). Accuracy points: the instrument against the DMM

During each hold, at t = 10–15 s, read the terminal line, then put the DMM
(DC V) across **J6 D and S**. D is the middle screw and S is the end away
from ▲. The instrument's current is compared with V_DMM / R, where R is
R_DMM for R_p and 202 Ω for L1.

**Pass, per row:** |vds_meas − V_DMM| ≤ 2% of V_DMM + 10 mV, and
|i_meas − V_DMM / R| ≤ 3% + 0.10 mA. The bands allow for the firmware's
assumed 3.300 V ADC reference, the 1% shunt and the ADC's offset. Out of
band is still a measurement: record it and carry on.

| # | Do | Expected | Record: vds_meas ; i_meas ; V_DMM |
|---|---|---|---|
| 15a | R_p in. `HOLD --vds 0.5 --seconds 20 -o h4/mvp_15a_hold_rp_0v5.csv` | 0.469 V, 1.00 mA | ____ V ; ____ mA ; ____ V |
| 15b | `HOLD --vds 1.5 --seconds 20 -o h4/mvp_15b_hold_rp_1v5.csv` | 1.406 V, 2.99 mA | ____ ; ____ ; ____ |
| 15c | `HOLD --vds 4 --seconds 20 -o h4/mvp_15c_hold_rp_4v.csv` | 3.75 V, 7.98 mA | ____ ; ____ ; ____ |
| 15d | Output OFF. Take R_p out; clamp L1 in D–S. Output ON. `HOLD --vds 2 --seconds 20 -o h4/mvp_15d_hold_l1_2v.csv` | 1.731 V, 8.57 mA | ____ ; ____ ; ____ |
| 15e | `HOLD --vds 4 --seconds 20 -o h4/mvp_15e_hold_l1_4v.csv` | 3.462 V, 17.14 mA | ____ ; ____ ; ____ |
| 15f | `HOLD --vds 6 --seconds 20 -o h4/mvp_15f_hold_l1_6v.csv` | 5.19 V, 25.7 mA (step 8) | ____ ; ____ ; ____ |
| 15g | Hold off. DMM across **TP8 to TP9**. This is the Nucleo's 3.3 V, which is the ADC reference | 3.20–3.40 V | ____ V |

**15g fail branch, and how to read the rows.** If voltage and current are
off by the same percentage, and the sign and size match V_TP8 / 3.300 − 1,
the reference explains the error. Record it; the host can rescale. Errors
that differ between voltage and current point at the divider or at the
shunt.

The levels stop at 6 V on purpose. Above about 6.6 V at the node the
Nucleo's LED loads the DAC (DECISIONS R2-3). So current accuracy is
measured only up to ~26 mA.

### 16–17 (d). Diode ‖ R_p

| # | Do | Pass | Record | Fail → |
|---|---|---|---|---|
| 16 | Output OFF. Take L1 out. Clamp R_p back in D–S, then the diode: **anode to D (middle), banded end to S**. Twist the leads and tug each wire. Output ON | All wires tight | ☐ | Retighten |
| 17 | `python -m ct_host capture --port $P --vgs 0 --vds-max 1.5 --n 100 --i-limit 40 --device <part> --r-parallel h4/mvp_14_rp.csv -o h4/mvp_17_diode_rp.csv`. **Output OFF.** Then `python -m ct_host extract h4/mvp_17_diode_rp.csv --type diode`. The R_p current is subtracted using the step 14 fit, and the header records it | `end : ok` or `ilimit`; no periodic wave during the capture; n is 1.0–2.5 | end ____ ; n ____ ; I_S ____ ; R_s ____ ; R_p auto ____ Ω | n is near 0 or negative: the diode is backwards. Flip it and redo once. A periodic wave: record f and Pk-Pk, keep the file, go on |

`R_p auto` is the host's cross-check: R_p fitted from this capture's own
points below 0.25 V. It prints with the extraction. Expect it within a few
percent of step 14's value. It reads "unavailable" if the DAC floor sits
above 0.25 V.

### 18 (e). Stretch: one N-MOSFET ‖ R_p

Only if 17 passed and at least 6 minutes are left.

| # | Do | Pass | Record | Fail → |
|---|---|---|---|---|
| 18a | Output OFF. Remove the diode, keep R_p. Find the pins on the datasheet for the part in hand. Flat face toward you, legs down: the **2N7000** is S, G, D left to right, and the **BS170** is the reverse, D, G, S. **G to J6 G (▲ end), D to the middle, S to the other end.** Tug each wire | All wires tight | part ____ | Retighten |
| 18b | Output ON. `python -m ct_host capture --port $P --vgs 1.5,1.6,1.7,1.8,1.9,2.0,2.1,2.2,2.3,2.4,2.5,2.6,2.7,2.8,2.9,3.0 --vds-max 3 --n 40 --i-limit 40 --device <part> --r-parallel h4/mvp_14_rp.csv -o h4/mvp_18_mosfet_rp.csv`. **Output OFF.** Then `python -m ct_host plot h4/mvp_18_mosfet_rp.csv --save h4/mvp_18_mosfet_rp.png` and `open h4/mvp_18_mosfet_rp.png` | At least 3 curves rise above zero. `end : ilimit` is expected: the sweep stops at the first step that passes 40 mA, and the rows before it are kept | end ____ ; curves above zero ____ | Every curve flat: the threshold is above 3.0 V. Redo once with the list shifted up 1.0 V (2.5 … 4.0) |

The gate list is fine-grained so that whatever the part's threshold
(0.8–3 V for a 2N7000), 3–5 steps land between turn-on and the 40 mA
limit. The steps below threshold cost about a second each.

■ **Done.** Output OFF, USB out. Hand back this sheet and `host/h4/mvp_1*`.
The model, the simulation and the overlay are desk work
(`host/README.md`, *From a capture to the overlay*).

**Where section D's numbers come from.**
- **The expected readings** use the series string R_iso 22 Ω + PTC 8.4 Ω
  (implied by Block 1) + shunt 1 Ω, and the measured L1.
- **The 40 mA limit** is the total current, and R_p takes its share:
  3 mA at 1.5 V and 6 mA at 3 V.
- **R_p's cost.** The host subtracts V / R_p from every reading. Gain
  error in the instrument's current reading cancels, because step 14
  fits R_p with the same current reading. What does not cancel is drift in
  R_p and the fit's own error. At 0.5% of 470 Ω that is ~6 µA at 0.6 V:
  3% of a 0.2 mA diode current, which is where the diode fit's floor sits
  (5 LSB).
