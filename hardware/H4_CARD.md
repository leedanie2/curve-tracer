# H4 bring-up card

Print this page and `CONTINGENCY.md` Part A. Execute from paper and make no
decisions at the bench: every branch is a numbered goto. Fill in every blank
(`____`) and hand the sheet back. CSV files go in `h4/`, named in the
Record column.

| Board | Date | Operator | Ambient °C | Supply | Scope | DMM | Port (`P=`) |
|---|---|---|---|---|---|---|---|
| ____ | ____ | ____ | ____ | ____ | ____ | ____ | ____ |

**Rules:**

- No held short (Block 4, steps 14–15) unless P4 is done.
- Nothing on TP6, ever.
- Supply output OFF before touching any part.
- Steps run in order. Stop only at a ■ STOP POINT.

**Commands** run from `host/` with `P` set. `CAP` means:

```
python -m ct_host capture --port $P --vgs 0
```

followed by the flags in the step.

---

## Prep: off-bench, before the visit (no bench time)

| # | Do | Record |
|---|---|---|
| P1 | Flash the firmware. `python -m ct_host ports` lists the Nucleo; write the port in the header | fw version ____ |
| P2 | Seat the Nucleo on J7/J8; check against README *Footprint orientation*. J3 and J4 jumpers on **RNG1** | done ☐ |
| P3 | **Fit C1 = 3.3 pF** (FH 0603CG3R3B500NT), clean with IPA, dry. *As assembled C1 is empty, and the uncancelled IN- pole is predicted to leave ~10–25° of phase margin (CONTINGENCY Part B §2B), so first power-up is with the predicted value* | done ☐ |
| P4 | Heatsink on Q1, with an insulating pad if it can touch anything grounded. DMM continuity, heatsink to TP27: expect **OL** | reading ____ |
| P5 | Build **L1**: 100 nF ceramic ‖ 200 Ω 1 W, leads ≤ 3 cm, to J6 pins 2 (D) and 3 (S). DMM: L1's resistance (used off-bench for the full-scale ADC check against `11_q3.csv`). Build a **jumper** for J6 D–S | R_L1 = ____ Ω |
| P6 | Build the **Kelvin pair**: J5 pin 1 → J6 D, J5 pin 2 → J6 S | done ☐ |
| P7 | Build a **reversed barrel lead**: plug centre to supply −, sleeve to supply + | done ☐ |
| P8 | Kit: C0G 1.5 / 2.2 / 2.7 / 3.9 / 4.7 pF (labelled), 330 Ω and 47 Ω axial, IPA, brush, fine iron, thermometer for step 14 | done ☐ |
| P9 | Laptop: `mkdir h4`, terminal in `host/`, `P=<port>` | done ☐ |

## Setup at the bench (10 min)

| # | Do |
|---|---|
| S1 | Bench supply: **15.00 V, limit 100 mA, output OFF**. Leads not connected to the board yet |
| S2 | Scope CH1: 10× probe on **TP3** (emitter), spring ground on **TP27**. AC, 20 mV/div, BW limit 20 MHz, 1 µs/div, trigger CH1 rising +30 mV, normal mode, holdoff 1 ms, trigger point 1 div from left |
| S3 | J6: **L1** fitted, Kelvin pair fitted. Nucleo USB to the laptop |

---

## Block 1: power and oscillation (≈ 20 min). Highest-information first.

| # | min | Do | Expect | Pass | Record | Fail → |
|---|---|---|---|---|---|---|
| 1 | 1 | Supply output ON, leads free. DMM: red on supply + lead, black on − lead | +15.00 V | +14.90…+15.10 V | V = ____ | Output OFF, swap leads, redo 1 |
| 1b | 1 | Output OFF. Connect + to J2 **"+15V"**, − to J2 **"GND"**. Output ON. Read the supply current after 5 s | ~8 mA, not in CC | 3–25 mA | I = ____ mA | Output OFF → **STOP**, end session |
| 2 | 3 | **Oscillation, L1.** `CAP --vds-max 6 --n 61 --settle-us 50000 -o h4/02_osc_L1.csv`. Scope 20 µs/div, persistence ON, run it **3×**. Cursors at +20 µs and +100 µs after the edge; read the envelope p-p between them | < 2 mV | < 5 mV | p-p = ____ mV | Measure frequency f = ____ → **CONTINGENCY A1** |
| 2b | 2 | Same, **BW limit OFF**, 20 ns/div, trigger auto, persistence 3 s, run once | < 10 mV | < 20 mV | p-p = ____ mV | f = ____ → **CONTINGENCY A1** |
| 3 | 3 | **Oscillation, open load.** Output OFF, remove L1 (Kelvin stays), ON. Repeat 2 → `h4/03_osc_open.csv` | < 2 mV | < 5 mV | p-p = ____ mV | f = ____ → **CONTINGENCY A1** |
| 4 | 3 | **Rails.** DMM: TP7 to TP27; TP8 to TP9; TP9 to TP27; TP28 to TP7 | 15.00; 3.30; 0.0; < 2 mV | 14.90–15.05 V; 3.20–3.40 V; ±1.0 mV; ≤ 2 mV | ____ ; ____ ; ____ ; ____ | Output OFF → **STOP** |
| 5 | 4 | **Step test, C_f 3.3 pF, L1.** Output OFF, refit L1, ON. Scope back to S2 settings, averaging 16. `CAP --vds-max 6 --n 61 --settle-us 50000 -o h4/05_step_3p3.csv`. **(a)** Overshoot, automatic, mean. **(b)** 2 mV/div, offset −100 mV, cursor at +5 µs: deviation from the level at +50 µs | (a) 10–20%; (b) < 0.5 mV | (a) ≤ 25%; (b) ≤ 1.0 mV; and step 2 passed | O = ____ % ; dev = ____ mV | Pass or fail → 6 (always) |

■ **STOP POINT A** (~20 min): supply output OFF, then USB. Blocks 2–4
still to do.

## Block 2: the C_f sweep (≈ 40 min). Always run it (§3.1: no stability result from one C_f).

For each row: supply output OFF, remove the old C1, fit the new one, clean
with IPA, wait 2 min, output ON. Run the step-5 command with the file named
in the row, then measure (a) and (b) as in step 5 and the step-2 envelope.
Order is outward from the prediction, so the most informative values come
first.

| # | min | C1 | File | O (%) | dev @ 5 µs (mV) | p-p +20…100 µs (mV) |
|---|---|---|---|---|---|---|
| 5 | — | 3.3 pF | 05_step_3p3.csv | (from 5) | (from 5) | (from 2) |
| 6a | 6 | 3.9 pF | 06a_cf_3p9.csv | ____ | ____ | ____ |
| 6b | 6 | 2.7 pF | 06b_cf_2p7.csv | ____ | ____ | ____ |
| 6c | 6 | 4.7 pF | 06c_cf_4p7.csv | ____ | ____ | ____ |

■ **STOP POINT B** (~20 min): output OFF, USB. Leave the last C1 fitted
and note it: ____

| # | min | C1 | File | O (%) | dev @ 5 µs (mV) | p-p +20…100 µs (mV) |
|---|---|---|---|---|---|---|
| 6d | 6 | 2.2 pF | 06d_cf_2p2.csv | ____ | ____ | ____ |
| 6e | 6 | 1.5 pF | 06e_cf_1p5.csv | ____ | ____ | ____ |
| 6f | 6 | none | 06f_cf_none.csv | ____ | ____ | ____ |

A row whose p-p is ≥ 5 mV is an oscillating value: record it and move on.
It is data, not a stop.

| # | min | Do | Pass | Record | Fail → |
|---|---|---|---|---|---|
| 7 | 6 | **Fit the best C_f**: the lowest O among rows with p-p < 5 mV; on a tie within 2 points, take the smaller value. Re-run the step test on **L1** (`h4/07_best_L1.csv`) and on **open** (`h4/07_best_open.csv`) | L1: O ≤ 25%, dev ≤ 1.0 mV, p-p < 5 mV. Open: p-p < 5 mV | C_f = ____ pF; O_L1 = ____ %; O_open = ____ %; best at an end (none or 4.7)? Y/N ____; max O − min O = ____ points | **CONTINGENCY A3** |

■ **STOP POINT C** (~20 min): output OFF, USB. The loop result is now on
paper.

## Block 3: calibration and protection (≈ 15 min). J6 open, Kelvin pair on.

| # | min | Do | Expect | Pass | Record | Fail → |
|---|---|---|---|---|---|---|
| 8 | 2 | **ADC zero.** Remove L1. `CAP --vds-max 1 --n 2 --settle-us 100000 -o h4/08_zero.csv`, then `grep -v '^#' h4/08_zero.csv \| head -1 \| cut -d, -f4,5` (prints vds_meas_v, i_meas_ma at 0 V) | ~0, ~0 | \|v\| ≤ 0.008 V; \|i\| ≤ 0.10 mA | v = ____ V ; i = ____ mA | Record, continue |
| 9 | 1 | **+3V3, clamp conducting.** Unplug the Kelvin pair at J5, wait 5 s, DMM TP8 to TP9, plug back | 3.30 V | 3.20–3.40 V | ____ V | Plug J5 back at once, record, continue |
| 10 | 2 | **Zener knee.** `CAP --vgs 10.95 --vds-max 0.1 --n 10 --settle-us 1000000 -o h4/10_zener.csv` (the `--vgs` overrides CAP's 0; 10 s). During it, DMM red TP16, black TP18 | ~0 mV | ≤ 10 mV | ____ mV | Record, continue |
| 11 | 2 | **Q3 drop under load.** Fit L1. `CAP --vds-max 6 --n 31 --settle-us 1000000 -o h4/11_q3.csv` (31 s). DMM red TP28, black TP7: record the last reading before it falls at the end, and the supply current at the same moment | ≤ 6 mV at ~34 mA | ≤ 7 mV | V = ____ mV ; I = ____ mA | Record, continue |
| 12 | 2 | **R_PTC.** Same command → `h4/12_rptc.csv`. DMM red TP5, black TP17: last reading before the fall | 40–400 mV at ~26 mA | 1.6–15 Ω (off-bench: V / last-row i_meas) | V = ____ mV | Record, continue |
| 13 | 3 | **Reverse polarity, J1.** Output OFF; disconnect the J2 leads; limit **20 mA**; connect the reversed barrel lead to J1. Output ON for 5 s: read the supply current and TP7 to TP27. Output OFF, remove the lead, reconnect J2, limit back to **100 mA** | 0 mA ; 0.00 V | ≤ 1 mA ; ≤ ±0.10 V | I = ____ ; V = ____ | Output OFF → record → **STOP**, end session |

■ **STOP POINT D** (~15 min): output OFF, USB.

## Block 4: held short (≈ 15 min). Only with P4 done.

Supply limit **150 mA**. J6: L1 off, **jumper D–S on**. Kelvin pair on.
Scope CH1 on TP3: AC, 50 mV/div, 1 µs/div, trigger auto.

| # | min | Do | Expect | Pass | Record | Fail → |
|---|---|---|---|---|---|---|
| 14 | 5 | `CAP --vds-max 10.96 --n 250 --settle-us 1000000 --i-limit 165 -o h4/14_short.csv` (~4.2 min; ends by itself). Start a stopwatch when the supply current jumps to ~115 mA (t = 0) | — | Jump occurs within 90 s | t0 clock time ____ | No jump by 90 s → record, → 15 |
| 14a | — | t ≈ 5 s: DMM red **TP3**, black **TP4** (R_sense) | 0.752 V (sim 11) | 0.68–0.83 V | V_cold = ____ | Record, continue |
| 14b | — | t ≈ 20 s: DMM red **TP1**, black **TP2** (R_B) | ~10.6 V (32 mA, sim 10) | ≤ 14.85 V (≤ 45 mA) | V_RB = ____ | Record, continue |
| 14c | — | t ≈ 30 s: supply current; scope p-p on TP3 | ~115 mA ; < 10 mV | 100–130 mA ; < 20 mV | I = ____ ; p-p = ____ | Record, continue |
| 14d | — | t = 180 s: TP3–TP4 again; thermometer on the heatsink at the tab | ≤ V_cold ; ~45 °C | ≥ 0.60 V ; ≤ 70 °C | V_warm = ____ ; T = ____ °C | **T > 70 °C: output OFF at once** → record → **STOP** |
| 15 | 4 | **Short recovery.** Scope CH1 → **TP19**, DC, 2 V/div, 1 µs/div, trigger rising 12 V, **single**. `CAP --vds-max 10 --n 100 --settle-us 1000000 --i-limit 165 -o h4/15_recovery.csv`. At t = 92 s from the run's start (setpoint ≥ 9.1 V), pull the jumper | ≈ 14.8 V peak (sim 10, +48%) | No threshold: this feeds the D3 decision, off-bench | peak = ____ V ; time to 1% = ____ µs | — |

■ **STOP POINT E**: supply output OFF, USB. Session complete. Hand back
this sheet and `h4/`.
