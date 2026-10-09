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

**Commands** run from `host/` with `P` set. `CAP` means

```
python -m ct_host capture --port $P --vgs 0
```

and `HOLD` means

```
python -m ct_host hold --port $P
```

each followed by the flags in the step. HOLD keeps the level until its
`--seconds` run out, printing one line a second: **"t = N s" on that
printout is the step's clock**. No stopwatch. `--vgs` defaults to 0.

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

## Block 3: calibration and protection (≈ 10 min). J6 open, Kelvin pair on.

| # | min | Do | Expect | Pass | Record | Fail → |
|---|---|---|---|---|---|---|
| 8 | 2 | **ADC zero.** Remove L1. `CAP --vds-max 1 --n 2 --settle-us 100000 -o h4/08_zero.csv`, then `grep -v '^#' h4/08_zero.csv \| head -1 \| cut -d, -f4,5` (prints vds_meas_v, i_meas_ma at 0 V) | ~0, ~0 | \|v\| ≤ 0.008 V; \|i\| ≤ 0.10 mA | v = ____ V ; i = ____ mA | Record, continue |
| 9 | 1 | **+3V3, clamp conducting.** Unplug the Kelvin pair at J5, wait 5 s, DMM TP8 to TP9, plug back | 3.30 V | 3.20–3.40 V | ____ V | Plug J5 back at once, record, continue |
| 10 | 1 | **Zener knee.** `HOLD --vgs 10.95 --vds 0.1 --seconds 20 -o h4/10_zener.csv`. At host **t = 10 s**: DMM red TP16, black TP18 | ~0 mV | ≤ 10 mV | ____ mV | Record, continue |
| 11 | 1 | **Q3 drop under load.** Fit L1. `HOLD --vds 6 --seconds 20 -o h4/11_q3.csv`. At **t = 10 s**: DMM red TP28, black TP7; supply current; the host's i_meas | ≤ 6.5 mV at ~34 mA | ≤ 7 mV | V = ____ mV ; I_supply = ____ mA ; i_meas = ____ mA | Record, continue |
| 12 | 1 | **R_PTC.** `HOLD --vds 6 --seconds 20 -o h4/12_rptc.csv`. At **t = 10 s**: DMM red TP5, black TP17; the host's i_meas | 40–400 mV at ~26 mA | R = V / i_meas in 1.6–15 Ω | V = ____ mV ; i = ____ mA ; R = ____ Ω | Record, continue |
| 13 | 3 | **Reverse polarity, J1.** Output OFF; disconnect the J2 leads; limit **20 mA**; connect the reversed barrel lead to J1. Output ON for 5 s: read the supply current and TP7 to TP27. Output OFF, remove the lead, reconnect J2, limit back to **100 mA** | 0 mA ; 0.00 V | ≤ 1 mA ; ≤ ±0.10 V | I = ____ ; V = ____ | Output OFF → record → **STOP**, end session |

■ **STOP POINT D** (~10 min): output OFF, USB.

## Block 4: held short (≈ 8 min). Only with P4 done.

Supply limit **150 mA**. J6: L1 off, **jumper D–S on**. Kelvin pair on.
Scope CH1 on TP3: AC, 50 mV/div, 1 µs/div, trigger auto.

| # | min | Do | Expect | Pass | Record | Fail → |
|---|---|---|---|---|---|---|
| 14 | 4 | `HOLD --vds 10.96 --seconds 200 --i-limit 165 -o h4/14_short.csv`. The jumper is on, so the limiter is engaged from the first row. The host's t is the clock; the hold ends itself at 200 s. At **t = 5 s**: supply current | ~115 mA (107 load + idle, sim 10) | 100–130 mA | I = ____ mA | Output OFF, record, → 15 |
| 14a | — | **t = 10 s**: DMM red **TP3**, black **TP4** (R_sense) | 0.752 V (sim 11) | 0.68–0.83 V | V_cold = ____ | Record, continue |
| 14b | — | **t = 20 s**: DMM red **TP1**, black **TP2** (R_B) | ~10.6 V (32 mA, sim 10) | ≤ 14.85 V (≤ 45 mA) | V_RB = ____ | Record, continue |
| 14c | — | **t = 30 s**: scope p-p on TP3; the host's i_meas | < 10 mV ; ~107 mA | < 20 mV ; 95–120 mA | p-p = ____ ; i = ____ | Record, continue |
| 14d | — | **t = 180 s**: TP3–TP4 again; thermometer on the heatsink at the tab | ≤ V_cold ; ~45 °C | ≥ 0.60 V ; ≤ 70 °C | V_warm = ____ ; T = ____ °C | **T > 70 °C: output OFF at once** → record → **STOP** |
| 15 | 2 | **Short recovery.** Jumper on. Scope CH1 → **TP19** (DUT_D), DC, 2 V/div, 1 µs/div, trigger rising **10.5 V**, single, armed. `HOLD --vds 10 --seconds 60 --i-limit 165 -o h4/15_recovery.csv`. Any time after host t = 5 s, **pull the jumper**. Read the peak | ≈ 14.8 V (sim 10, +48% at 100 pF) | **≤ 12.0 V** | peak = ____ V (no trigger: write "< 10.5") | **> 12.0 V: D3 needed.** Record; the part is not chosen yet (DECISIONS O-3), so the fit is off-bench. Continue |

**Step 15 threshold** (Daniel, 2026-10-09). §1 caps the instrument at 10 V,
and every DUT is selected against that ceiling. Sim 10 measured 14.8 V at
100 pF. So 12 V is 20% headroom over spec while still catching the
structural overshoot. Below 12 V, record and continue; above it, fit D3.

D3 is an SMAJ12A, fitted off-bench. It clamps at its breakdown voltage,
**13.3–14.8 V**, not at its 12 V standoff (`DECISIONS.md` D3). So after D3 is
fitted, a re-run of step 15 is expected to read 13.3–14.8 V. Record it; do
not treat it as a new failure.

■ **STOP POINT E**: supply output OFF, USB. Session complete. Hand back
this sheet and `h4/`.
