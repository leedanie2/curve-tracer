# MVP bench card: first power-up, Block 1, one diode

The shortest path from a Nucleo off the board to a powered board, a Block 1
oscillation check, and one diode I-V plot. Print it and fill in every
`____`. Every step has a pass and a fail. This is a cut-down form of
`H4_CARD.md`, and where the two differ this card applies. CSVs go in
`host/h4/`.

| Board | Date | Ambient °C | Diode part no. | Port (`P=`) |
|---|---|---|---|---|
| **2** | ____ | ____ | ____ | ____ |

**Board 2 is the bring-up board** (`H4_CARD.md` still says board 1).

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
| 2 | **Seat the Nucleo** on board 2: CN7 into J7, CN10 into J8, each pin 1 at the socket's square-pad end. Every pin goes into a hole and none is left over. J3 and J4 jumpers on **RNG1** | Seated, no pins left over | ☐ | Pull it out and redo |
| 3 | **J6.** L1 (100 nF ‖ 200 Ω, leads ≤ 3 cm) goes to pin 2 (D) and pin 3 (S). Kelvin pair: J5 pin 1 to J6 D, J5 pin 2 to J6 S. Pin 1 (G) stays empty | All four wires tight | ☐ | Retighten |
| 4 | Nucleo USB to the laptop. Run `python -m ct_host ports`, then `P=<the port>` | The Nucleo is listed | port above | Replug USB, redo. Still not listed: **STOP** |
| 5 | **Supply:** 15.00 V, current limit **100 mA**. Output ON with the leads free. DMM on DC V: red probe on the red lead, black probe on the black lead. Output OFF | +14.90 to +15.10 V | ____ V | Negative: the leads are swapped. Fix and redo. *J2 has no reverse-polarity protection* |

**Scope setup** (once, board still unpowered).
1. Press **Default Setup**. Set the switch on the probe body to **10×**.
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
| 6 | Supply red lead to J2 **"+15V"**, black lead to J2 **"GND"**. Output ON. Read the supply's current display after 5 s | 3–25 mA, and the supply is not in CC (current limit) | ____ mA | **STOP** |
| 7 | **Baseline.** Nothing is running, so the loop can't oscillate (CONTINGENCY §2B). Read Pk-Pk | Flat, fuzzy line; Pk-Pk < 10 mV | B = ____ mV | Check the probe tip, the ground clip and 10× in both places. Then record B and go on |
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
