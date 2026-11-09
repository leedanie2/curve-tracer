# MVP bench card: first power-up, Block 1, one diode

The shortest path from a Nucleo off the board to a powered board, a Block 1
oscillation check, and one diode I-V plot. Print it and fill in every
`____`. Every step has a pass and a fail. This is a cut-down form of
`H4_CARD.md`, and where the two differ this card applies. CSVs go in
`host/h4/`. Sections A–C ran on 2026-11-02/03, and Block 1 failed at open
load. Section D ran on 2026-11-08: **470 Ω across D–S failed** (it
oscillated), and **L1 is the R_p** from then on. Results are in
`docs/characterization.md`. **Section E is session 3**, by 2026-11-15.

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
| 7 | **Baseline, board powered.** Supply output ON from step 6; no `HOLD` running. *Corrected 2026-11-08: the loop is **not** off here. The sweep DAC's floor holds the node at ~0.18 V, so the loop runs at idle, and 470 Ω across D–S oscillated with nothing running.* B is the loop's noise at that floor into L1. Read Pk-Pk. A reading taken with the output OFF is not B | Flat, fuzzy line; Pk-Pk < 10 mV | B = ____ mV | Check the probe tip, the ground clip and 10× in both places. Then record B and go on |
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
J6 with **R_p**, clamped across D–S. **R_p is L1** (200 Ω ‖ 100 nF).

**Ran 2026-11-08.** The first R_p, 470 Ω, oscillated at idle (781 kHz,
> 205 mV p-p) at step 13. L1 was quiet at idle, 0.1 V and 0.3 V and was
used for the rest of the session: 14, 15d–g, 17 and 18 all passed. The
100 nF is what keeps the loop quiet, not L1's bias
(`docs/characterization.md`, 2026-11-08 (a)). The card below is written
for L1 as R_p. The
scope stays on **TP3** for the whole session, with its **ground lead on
TP9** (GND). No soldering. The rules at the top of the card still apply.
Supply output OFF before every change at J6.

| Date | Ambient °C | R_p marked | R_p by DMM (R_DMM) | Diode part no. | MOSFET part no. | Port (`P=`) |
|---|---|---|---|---|---|---|
| 2026-11-08 | not recorded | L1, 200 Ω ‖ 100 nF | 200 Ω (cap not remeasured) | 1N4148 | 2N7000 | /dev/cu.usbmodem1103 |

**Parts.**
- **R_p = L1**, 200 Ω 1 W ‖ 100 nF ceramic, legs ≤ 3 cm. Quiet at idle,
  0.1, 0.3, 2, 4 and 6 V (2026-11-03 and 2026-11-08).
- **Fallback: L1 rebuilt, or any resistor with ~100 nF across it.** The
  100 nF is what keeps the loop quiet: it moves the load's lag far below
  crossover (analysis), and in sim 15 both 470 Ω ‖ 100 nF and
  200 Ω ‖ 100 nF show no ring (`docs/characterization.md`, 2026-11-08 (a)).
  On the bench only L1 itself is tested. A resistor without the capacitor
  is not an R_p while C1 is empty: 470 Ω alone oscillated at idle on
  2026-11-08.
- **L1** was rebuilt for 2026-11-08 with the same part values: DMM
  200 Ω. On 2026-11-02 it read 95.2 nF ‖ 202 Ω.
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

*2026-11-08:* this step first tested 470 Ω, sim 13's prediction. It
oscillated at idle, before 13a ran, so the session went to 13c (L1). As
written below, R_p is L1. **Pass for every hold: no periodic wave on the
scope.** Read the scope at idle first, with R_p clamped in and nothing
running: the loop runs at the DAC floor even then. A periodic wave is a repeating shape: at
1 µs/div, ~1 MHz is about one cycle per division. The broadband fuzz of
step 7 is a pass. Each hold runs 20 s; read the scope and the terminal at
t = 10–15 s.

The expected readings come from R_p's share of the series string:
200 / (200 + 22 + 8.4 + 1) = 0.864 of the command, above the DAC floor.

| # | Do | Pass | Record | Fail → |
|---|---|---|---|---|
| 13a | Output OFF. Clamp R_p (L1) in J6 D–S, with the Kelvin wires. Output ON. Idle reading first, then `HOLD --vds 0.1 --seconds 20 -o h4/mvp_13a_hold_rp_0v1.csv` | No periodic wave | idle Pk-Pk ____ mV ; Pk-Pk ____ mV ; ____ V, ____ mA | Read Frequency: f = ____ MHz. Go to 13c |
| 13b | `HOLD --vds 0.3 --seconds 20 -o h4/mvp_13b_hold_rp_0v3.csv` | No periodic wave | Pk-Pk ____ mV ; ____ V, ____ mA | As 13a |
| 13c | **Only if 13a or 13b failed.** Output OFF. Rebuild L1, or clamp in another resistor with ~100 nF across it (Parts); DMM its resistance for the header. Output ON and redo 13a and 13b once. Still failing: output OFF and **STOP**, the fix is C1 (rev 2). *2026-11-08 ran this step with L1 after 470 Ω failed: idle 22.4 mV, 0.1 V hold 0.189 V, 0.852 mA, 20.0 mV; 0.3 V hold 0.265 V, 1.228 mA, 20.4 mV. Files `mvp_13c_hold_l1_0v1.csv`, `mvp_13c_hold_l1_0v3.csv`* | — | f ____ MHz, Pk-Pk ____ mV | — |
| 13d | **DAC floor.** Look at vds_meas from 13a, on the R_p you ended on | vds_meas ≤ 0.20 V | floor: vds_meas ____ V | Above 0.20 V: record it as the floor. Do 14 and 15, then **STOP before the diode**: skip 16, 17 and 18 |

**The readings at 13a also measure the DAC floor.** With L1, 13a would
read about **0.087 V and 0.43 mA** with no floor, and 13b about
**0.260 V and 1.29 mA**. On 2026-11-08 13a read 0.189 V: the floor, at the
node 0.18–0.19 V. If 13a reads well above 0.087 V, the sweep DAC is holding a floor: its
buffered output is guaranteed only down to 0.2 V, 0.66 V at the node
(blueprint §3.5). The loop then never runs lower than that floor, so the
hold still tests the lowest point the diode sweep can reach. Up to 0.20 V
the floor is a result, not a fail: record it and go on. Above 0.20 V, 13d
stops the session before the diode, so the floor can be checked against
what the diode curve would still show (Daniel, 2026-11-03).

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
R_DMM for R_p and the L1 resistor's DMM reading for L1. **With R_p = L1,
skip 15a–15c**: 15d–15f are the same load.

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
| 15g | Hold off. DMM across **TP8 to TP9** (2026-11-08 used TP27, GNDPWR: the same within mV). This is the Nucleo's 3.3 V, which is the ADC reference | 3.20–3.40 V | ____ V |

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
| 16 | Output OFF. Leave L1 in as R_p. Then the diode: **anode to D (middle), banded end to S**. Twist the leads and tug each wire. Output ON | All wires tight | ☐ | Retighten |
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
  7 mA at 1.5 V and 15 mA at 3 V with L1.
- **R_p's cost.** The host subtracts V / R_p from every reading. Gain
  error in the instrument's current reading cancels, because step 14
  fits R_p with the same current reading. What does not cancel is drift in
  R_p and the fit's own error. At 0.5% of 470 Ω that is ~6 µA at 0.6 V:
  3% of a 0.2 mA diode current, which is where the diode fit's floor sits
  (5 LSB). It scales as 1/R_p: ~15 µA (7%) with L1. *Measured 2026-11-08:* step 14 fitted L1 to 0.03%, not 0.5%,
  so the subtraction's error was ~1.5 µA at 0.755 V, R and zero together.
  Since that session the host also subtracts the fit's offset, the
  instrument's current zero (−0.087 mA that night).
- **L1's expected readings** use the same string: 200 / 231.4 = 0.864 of
  the command (0.865 with the 202 Ω read on 2026-11-02).

---

## E. Session 3: breadboard fixture, stabiliser, 0.1% accuracy, diode (≤ 30 min)

**Parts.**
- A solderless breadboard.
- Three solid-core wires, ~5 cm.
- **A second 100 nF ceramic capacitor**: the stabiliser, alone, legs
  ≤ 1 cm into the D and S rows. **L1 stays intact** as the fallback.
- If on hand: **0.1% resistors, 100 Ω and 1 kΩ**, any wattage ≥ 1/8 W
  (the most either sees is 34 mW).
- **The 1N4148 from 2026-11-08.**
- **The 2N7000 from 2026-11-08**, only for the optional (f).
- The DMM isn't needed.

Board 2, C1 still empty. By 2026-11-15. No soldering; the rules at the top
of the card still apply. Supply output OFF before every change on the
breadboard or at J6. The scope stays on **TP3**, ground on **TP9**, set up
as section A (20 mV/div, 1 µs/div, AC, BW limit, Pk-Pk and Frequency).

| Date | Ambient °C | Stabiliser used | 0.1% parts on hand? | Diode (same as 11-08?) | Port (`P=`) |
|---|---|---|---|---|---|
| ____ | ____ | cap / L1 | yes / no | ____ | ____ |

**What this session is for.**
- A fixture where parts plug into a breadboard, not three wires twisted
  into one J6 clamp.
- Whether **100 nF alone across D–S**, with no resistor, keeps the loop
  quiet from the DAC floor up. Sim 16 says it does. If so, no current
  needs subtracting except the instrument's zero.
- The zero, and the current's gain against the voltage's, from 0.1%
  resistors instead of the DMM's ±3% ohms reading.
- The 1N4148 again, on the fixture, for the README figure.
- Optional, (f): the 2N7000 again with fine gate steps, for a MOSFET card
  with at least 10 steps in its fit.

**Time plan.**

| Fixture and setup | (a) stability | (c) 0.1% holds | (d) diode | Spare |
|---|---|---|---|---|
| 8 min | 6 min | 6 min | 4 min | 6 min |

(f) is optional and comes on top: about 6 min, or about 4 if the session
is already on L1. If time runs short, drop (c). With the cap alone, (c) is where the zero
comes from, so without it the diode takes 11-08's zero (−0.087 mA) as
given, from a session at another temperature.

### (b) Before the session, off-bench: sim 16

*Simulation (sims 16 and 16b, TI's OPAx197 model, sim 15's setup, C1
empty).* **100 nF alone across D–S is quiet in every case
simulated.** At the floor (0.205 V, where Q1 carries ~6 µA) it settles
with no ring, and a 15 mV step up and back down rings neither way. At
1 V and 6 V the start-up charge settles without ringing. With the cap on
the fixture, behind ~100 nH of wire, the result is the same, apart from an
overshoot during the 0 → 6 V start-up charge that is gone by 8 µs. Under
the same steps, open load at the floor rings at 155–290 kHz (half-cycle
ratio 0.44–0.72), so the method would have seen a ring. One side effect:
at the floor the cap can only discharge through the 33.2 kΩ feedback
network, so 20 µs after a 15 mV step down the node has hardly moved
(0.219 V). That is why (a) tries the cap alone first, with L1 as
the fallback. The same model was optimistic twice before (blueprint §11),
so the sim chooses what to try first and the bench decides.

### Setup and the fixture

| # | Do | Pass | Record | Fail → |
|---|---|---|---|---|
| 20 | Board unpowered. Pick three breadboard rows a few holes apart and call them **G, D, S**. Run one ~5 cm solid wire from each J6 terminal (G by the ▲ mark, D the middle, S the other end) to its row. Plug J5's Kelvin jumpers into the breadboard **at the device's holes**: HI into the **D row**, LO into the **S row**. Plug the stabiliser into D and S and leave it there all session. G row empty | Every wire tight in J6; each lead firm in its row | ☐ | Retighten. A loose breadboard contact reads as noise or a step in the data |
| 21 | Steps 4–7 of sections A–B (port, supply 15.00 V, power-up, baseline). Power-up current after 5 s | 3–25 mA, not CC | ____ mA | **STOP** |

The Kelvin pair senses at the device's own breadboard row. So the 5 cm
wires and J6's clamps are outside the measurement, and only the
row-to-lead contacts (~10–30 mΩ) are inside it.

### (a) Is the fixture quiet with the stabiliser?

The stabiliser is the 100 nF alone, tested first; L1 is the fallback
(22e). The cap draws no DC, so each hold reads the node at the command.
**The current does not read the zero.** The channel is single-supply and
11-08's zero is −2.2 counts, so with nothing drawing current it sits on
its floor at 0 counts. The firmware then prints i_meas ≈ −V / 400 kΩ, its
divider correction acting on nothing: −0.0005, −0.0025 and −0.015 mA at
0.2, 1 and 6 V. That reading confirms the floor. A reading near −0.09 mA
would mean the channel can go below zero after all, and the holds then
give the zero (`--zero` with these files). Either way, record it. (c)
measures the zero with the channel lifted.

**Pass for every line: no periodic wave on the scope**, and the Frequency
readout not locked on a steady value. A periodic wave is a repeating
shape: at 1 µs/div, ~1 MHz is about one cycle per division. Broadband fuzz
like 2026-11-08's 20–22 mV is a pass. Each hold runs 20 s; read the scope
and the terminal at t = 10–15 s. A current outside its band with no
periodic wave is not a fail: record it and go on. Only a periodic wave
sends you to 22e.

| # | Do | Pass | Record | Fail → |
|---|---|---|---|---|
| 22a | **Idle**, nothing running, stabiliser in. Read the scope for 10 s | No periodic wave | Pk-Pk ____ mV ; f ____ | 22e |
| 22b | `HOLD --vds 0.2 --seconds 20 -o h4/s3_22b_hold_0v2.csv` | No periodic wave; vds_meas 0.17–0.23 V (the floor); \|i_meas\| ≤ 0.20 mA | Pk-Pk ____ mV ; ____ V, ____ mA | 22e |
| 22c | `HOLD --vds 1 --seconds 20 -o h4/s3_22c_hold_1v.csv` | No periodic wave; vds_meas 0.96–1.02 V; \|i_meas\| ≤ 0.20 mA | Pk-Pk ____ mV ; ____ V, ____ mA | 22e |
| 22d | `HOLD --vds 6 --seconds 20 -o h4/s3_22d_hold_6v.csv` | No periodic wave; vds_meas 5.80–6.10 V; \|i_meas\| ≤ 0.20 mA | Pk-Pk ____ mV ; ____ V, ____ mA | 22e |
| 22e | **Only on a fail in 22a–d.** Read Frequency (f ____ MHz) and Pk-Pk. Output OFF. Swap the cap for **L1** in the same rows. Output ON; redo 22a–d once (expect 0.19 V, 0.9 mA; 0.865 V, 4.30 mA; 5.19 V, 25.8 mA). If L1 fails here too, the fixture is the difference from 2026-11-08: move L1 to J6 itself, clamped in D–S with the fixture wires, and redo once | Both pass | which stabiliser, where: ____ | Still failing: output OFF and **STOP**. Record f and Pk-Pk |

**If you end on L1:** it must be calibrated on the fixture before (c) and
(d). `python -m ct_host capture --port $P --vgs 0 --vds-max 1.5 --n 100
--i-limit 40 --device L1_Rp -o h4/s3_22f_rp.csv` (1 min); the same three
pass bands as section D's step 14.

### (c) 0.1% resistors: the zero, and current against voltage

Only if 0.1% parts are on hand. Each plugs into the D and S rows
**beside** the stabiliser, which stays in.

**What this measures.** Three holds, two resistors, solved at the desk for
I_meas = g·V/R + b + c·V:
- **g**, the current channel's gain against the voltage channel's. The
  shared 3.300 V reference cancels, so this is **not** the voltage's
  absolute accuracy. That still rests on 2026-11-08's DMM check (−6 mV,
  inside the DMM's ±0.8%); no new DMM reading is needed. What it replaces
  is R_DMM's ±3%: current is then known to the voltage's ±0.8% plus 0.1%.
- **b, the zero.** With the cap alone this is the zero's only source: the
  resistors lift the channel 48–380 counts clear of its floor.
- **c, the common-mode term** (the difference amp's CMRR): how far the
  zero moves with node voltage.

23a and 23b sit at nearly the same node voltage (1.5 and 1.9 V), so they
fix g and b almost free of c; 23c moves only the voltage, which gives c.

| # | Do | Expected | Pass | Record: vds_meas ; i_meas |
|---|---|---|---|---|
| 23a | Output OFF. Plug the **0.1% 100 Ω** into D–S beside the stabiliser. Output ON. `HOLD --vds 2 --seconds 20 -o h4/s3_23a_hold_100r_2v.csv` | Cap: 1.522 V, 15.22 mA. L1: 1.361 V, 20.36 mA total | No periodic wave | ____ V ; ____ mA |
| 23b | Output OFF. Swap it for the **0.1% 1 kΩ**. Output ON. `HOLD --vds 2 --seconds 20 -o h4/s3_23b_hold_1k_2v.csv` | Cap: 1.939 V, 1.94 mA | No periodic wave | ____ V ; ____ mA |
| 23c | Same 1 kΩ. `HOLD --vds 6 --seconds 20 -o h4/s3_23c_hold_1k_6v.csv` | Cap: 5.817 V, 5.82 mA | No periodic wave | ____ V ; ____ mA |

**With L1, run 23a only**, against the `s3_22f` calibration: beside a
1 kΩ, L1 carries 80–83% of the current, and its warming alone would move
the 1 kΩ's share by ~1%.

Output OFF and take the resistor out before (d).

**At the desk:** solve 23a–c for g, b and c. **Pass: g within ±1.5% of 1**:
the 1% shunt plus the 0.1% gain and divider resistors. Out of band is a
measurement, not a fault: it is the shunt's calibration factor, and the
host can carry it. b is the zero: compare it with 11-08's −0.087 mA and
give it to (d) as `--zero`. c × 6 V compares with sim 05's 0.24 mA median.

### (d) The 1N4148 on the fixture

| # | Do | Pass | Record | Fail → |
|---|---|---|---|---|
| 24 | Output OFF. Plug the diode in: **anode in the D row, banded end in the S row**, beside the stabiliser. Output ON. `python -m ct_host capture --port $P --vgs 0 --vds-max 1.5 --n 100 --i-limit 40 --device 1N4148 -o h4/s3_24_diode.csv` (with L1, add `--r-parallel h4/s3_22f_rp.csv`). **Output OFF.** Then `python -m ct_host extract h4/s3_24_diode.csv --type diode` | `end : ok` or `ilimit`; no periodic wave during the capture; n is 1.0–2.5 | end ____ ; n ____ ; I_S ____ ; R_s ____ | n near 0 or negative: the diode is backwards. Flip it and redo once. A periodic wave: record f and Pk-Pk, keep the file |

The bench `extract` has no zero, so its n reads low (~1.65 on 11-08). That
is fine for the pass band; the desk run gives the real figure with
`--zero` (b from (c), or −0.087 if (c) was skipped).

### (f) Optional: the 2N7000 with fine gate steps

Only after (d), and only if 6 minutes are left. MOSFET families can't use
the cap-only stabiliser (see *Not for MOSFET families* below), so this
step runs on **L1**. Use **the same 2N7000 as 2026-11-08**: the drain
range and the current budget below come from its 11-08 curves.

**What it's for.** On 11-08 a Level-1 fit held only over the top three
steps (2.5–2.7 V): one degree of freedom, too thin for a card. Sixteen
steps 0.02 V apart across 2.45–2.75 V put ≥ 10 in the same window.

| # | Do | Pass | Record | Fail → |
|---|---|---|---|---|
| 25a | **Skip if (a) ended on L1** (22e): it is already in and calibrated. Otherwise output OFF, pull the cap out of D–S and plug **L1** into the same rows. Output ON. Read the scope idle for 10 s. Then calibrate it, watching the scope: `python -m ct_host capture --port $P --vgs 0 --vds-max 1.5 --n 100 --i-limit 40 --device L1_Rp -o h4/s3_22f_rp.csv` (1 min) | No periodic wave, idle or during the capture; section D's step 14 bands | Pk-Pk ____ mV ; R ____ Ω | A periodic wave: record f and Pk-Pk, output OFF, and skip (f) |
| 25b | Output OFF. Plug the 2N7000 in **beside L1**. Flat face toward you, legs down, it is S, G, D left to right: spread the legs so each lands in its own row, **S in S, G in G, D in D**. If the rows' order won't allow it, put G in an empty row and jumper that row to the G row: the gate carries no DC, so the jumper is outside the measurement. Tug each leg | Each leg firm in its row | ☐ | Reseat |
| 25c | Output ON. `python -m ct_host capture --port $P --vgs 2.45,2.47,2.49,2.51,2.53,2.55,2.57,2.59,2.61,2.63,2.65,2.67,2.69,2.71,2.73,2.75 --vds-max 2.5 --n 60 --i-limit 40 --device 2N7000 --r-parallel h4/s3_22f_rp.csv -o h4/s3_25_mosfet.csv` (~10 s). **Output OFF.** Then `python -m ct_host extract h4/s3_25_mosfet.csv --type mosfet --vds-slice 1.1 --vgs-range 2.44 2.76` | `end : ok` or `ilimit`; no periodic wave during the capture; under *V_th fit*, the `range :` line ending `(V_GS)` reads **≥ 10 of** … points; on `ilimit`, the capture's `flagged:` line shows V_DS ≥ 1.1 V | end ____ ; flagged V_GS ____ V_DS ____ ; range ____ of ____ ; V_th ____ ; KP*W/L ____ | A trip below 1.1 V, or fewer than 10: the part draws more than on 11-08. Keep the file and redo once with every step 0.04 V lower (2.41 … 2.71), `-o h4/s3_25b_mosfet.csv`. A periodic wave: record f and Pk-Pk, keep the file, go on |

**A trip above the slice is a pass.** Expect `end : ilimit` at the top
step. If its `flagged:` line shows V_DS above 1.1 V, that step's slice
point is already recorded and every lower step is complete, so the file
is good. The redo is only for a trip below 1.1 V, or one that leaves fewer
than 10 steps. Rows near the slice are ~0.037 V apart, so a trip flagged
at 1.10–1.14 V may leave that step's last good row just short of the
slice. The step then drops out of the fit, and the `range :` count shows
it.

The card itself is desk work: `python -m ct_host model h4/s3_25_mosfet.csv
--type mosfet --vds-slice 1.1 --vgs-range 2.44 2.76`. Its `valid for`
line states the window it was fitted over.

■ **Done.** Output OFF, USB out. Hand back this sheet and `host/h4/s3_*`.
The zero, the model card, the overlay and the README figure are desk work.

**Where section E's numbers come from.**
- **Series string** as section D: R_iso 22 Ω + PTC 8.4 Ω + shunt 1 Ω =
  31.4 Ω between FB_SENSE and the node.
- **With the cap alone** there is no DC load, so the node reads the command
  (the DAC's −3 to +1%). A command of 0.2 V sits at the DAC floor,
  0.18–0.19 V with code 0. The current sits on the channel's floor (see
  (a)). The 0.20 mA band is 5 LSB. It is there to catch Block 1's kind of
  oscillation-driven DC error (+0.8 to +3 mA).
- **The zero's common-mode term.** Finite CMRR moves the zero with the
  node voltage. At sim 05's median 88 dB, 6 V gives ~0.24 mA; at its
  74 dB worst corner, ~1.1 mA. Session 2 could not see it: with L1 in
  place, a zero that moves in proportion to V looks exactly like a change
  in 1/R (0.24 mA at 6 V is 1% of L1's current). It may be part of the
  +0.66% between L1's fit and its DMM reading. (c)'s 23b–c measure it.
- **L1's readings**: 200 / 231.4 = 0.864 of the command, above the floor.
- **0.1% holds**: 2 × 100 / 131.4 = 1.522 V and 15.22 mA (23 mW);
  2 × 1000 / 1031.4 = 1.939 V and 1.94 mA (48 counts);
  6 × 1000 / 1031.4 = 5.817 V and 5.82 mA (34 mW). With L1 beside the
  100 Ω: 66.7 Ω, 1.361 V, 20.36 mA total.
- **The ±1.5% ratio band** is the shunt's 1% plus the 0.1% resistors in
  the difference amp and the Kelvin divider. Breadboard contacts inside
  the Kelvin loop add ~0.05 Ω, 0.05% of 100 Ω.
- **A sweep with the cap alone.** With no resistor, Q1 runs at µA at the
  floor and the node settles slowly. Each 15 mV step puts 1.5 nC into the
  cap, and spread over the ~0.55 ms of sampling per point that is at most
  2.7 µA (0.07 LSB). Holds have no steps.
- **Sim 16**: see (b).
- **(f)'s gate steps.** 16 is the firmware's longest gate list
  (`CT_VGS_LIST_MAX`). One gate DAC code is 3.3 / 4095 × 3.32 = 2.68 mV, so
  steps commanded 0.02 V apart land 18.7 or 21.4 mV apart. V_GS is the
  commanded value; the gate DAC's accuracy is unmeasured, and that moves
  V_th's absolute value but not the spacing.
- **(f)'s slice.** Saturation with the host's 0.5 V margin needs
  V_DS ≥ V_GS − V_th + 0.5 V: 1.10 V at 2.75 V, with V_th 2.15 V from
  11-08's three-step fit. Every lower step needs less.
- **(f)'s current budget, L1's share counted.** Scaled from the 11-08
  2.70 V curve by the square law, with L1's V / 201.3 Ω and the −0.09 mA
  zero. At 1.1 V the 2.75 V step draws 32.8 mA and L1 5.5 mA: 38.1 mA
  total. The node sits 31.7 Ω × I below the command (fitted to 11-08's
  rows), so with `--vds-max 2.5` the 2.75 V step ends near 1.27 V and
  39.2 mA, the 2.73 V step peaks at 37.3 mA, and the 2.45 V step reaches
  1.94 V. The top step dissipates ~42 mW.
- **Why `--vds-max 2.5`.** The first row over 40 mA ends the whole sweep,
  not only its step, so a trip below the top step loses every step above
  it. At `--vds-max 4` the 2.69 V step trips (at 2.5 V), and 2.71–2.75 V
  are never swept. At 2.5 V, with 5% more current than 11-08 (a warmer
  part), the 2.73 V step peaks at 38.6 mA and only the 2.75 V step trips,
  at 1.13 V: still past the slice. The redo's 0.04 V shift takes ~13% off
  the top step's current.
- **(f)'s time.** 960 rows at ~6 ms each (firmware README, *Timing*) is
  ~6 s of sweep. The rest is handling: 25a ~2 min, 25b ~2 min, 25c and
  its extract ~1–2 min.

**If the cap alone passes (a): what changes at the desk.** Nothing here
needs the bench.
- **Host.** `extract`, `model`, `plot`, `simulate` and `overlay` take
  `--zero MA|CSV|auto` (2026-11-09), recorded in each output. With the cap alone, give
  (c)'s b as `--zero MA`, and no `--r-parallel`. `auto` and hold CSVs refuse
  rows on the channel's floor, so neither works with the cap alone; both
  work with a resistor lifting the channel, as on 11-08. Without a zero,
  (d)'s diode reads n ≈ 1.65 again, as it did on 2026-11-08 before the
  zero came out.
- **What it gains.** No V / R_p subtraction: its ~1–3 µA per point of noise
  and ~1.5 µA systematic go, and so does L1's drift as it warms. The device
  gets the whole 40 mA limit, where L1 took 7 mA at 1.5 V. **What it
  doesn't:** the current LSB stays 40.3 µA on range 1, and the diode fit's
  floor stays 0.2 mA (5 LSB). Low-current resolution is set by the range,
  not the stabiliser.
- **Not for MOSFET families.** With no resistor, the node discharges at
  low levels only through the 33.2 kΩ feedback network (τ ≈ 3 ms; the B-E
  clamp can't sink below ~0.6 V). An off gate step would start at the last
  step's V_DS and read ~−85 µA of discharge current. MOSFETs keep L1 until
  C1 is fitted.
- **README.** The *Until rev 2* row and *Working around it* (the stabiliser
  is 100 nF alone for two-terminal parts); the status table (cap-only
  measured quiet, L1 the MOSFET stabiliser); the headline figure and its
  numbers from (d), with the zero bracket redone; the accuracy rows and the
  *Limitations* entry from (c).
