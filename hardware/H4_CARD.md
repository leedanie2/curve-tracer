# H4 bring-up card

Print this page and `CONTINGENCY.md` Part A. Execute from paper and make no
decisions at the bench: every branch is a numbered goto. Fill in every blank
(`____`) and hand the sheet back. CSV files go in `h4/`, named in the
Record column.

| Board | Date | Operator | Ambient °C | Supply | Scope | DMM | Port (`P=`) |
|---|---|---|---|---|---|---|---|
| ____ | ____ | ____ | ____ | ____ | ____ | ____ | ____ |

Board **1** is the bring-up board. Board 5 is for soldering practice (P3).
Boards 2–4 stay untouched.

**Rules:**

- No held short (Block 4, steps 14–15) unless P4 is done.
- No soldering on board 1 until P3's practice on board 5 is done.
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
| P1 | Flash the firmware: in `firmware/stm32/`, `make drivers` (once), `make`, then `make flash` with the Nucleo on USB (it copies the .bin to the NODE_F303RE drive). `python -m ct_host ports` lists the Nucleo; write the port in the header | fw version ____ |
| P1a | **Nucleo mod: SB21 off, PA5–PA6 shunt on.** USB unplugged, Nucleo not seated. **(a)** On the Nucleo's underside, remove solder bridge **SB21**: wick off the blob, or lift the 0 Ω part. DMM continuity across SB21's two pads: **OL**. **(b)** On the top-side morpho pins, fit a 2.54 mm shunt across **CN10-11 (PA5)** and **CN10-13 (PA6)**. *The F303RE has no DAC2: the sweep DAC is DAC1_OUT2 on PA5, and the board takes it at PA6. With SB21 fitted, LD2 loads PA5 (blueprint §3.5)* | SB21 OL ☐ ; shunt ☐ |
| P1b | **Nucleo check, off the board.** USB in, Nucleo **not seated**: on the board, an unpowered op-amp's inputs would load the DAC. `HOLD --vds 10.96 --seconds 20 --i-limit 165 -o h4/p1b_full.csv`. At **t = 10 s**, DMM black on **CN10-9 (GND)**, red on **CN7-16 (+3V3)**, then **CN10-11 (PA5)**, then **CN10-13 (PA6)**. Watch LD2 throughout. Then `HOLD --vds 0 --seconds 20 --i-limit 165 -o h4/p1b_zero.csv`; at t = 10 s, **CN10-11 (PA5)**, **CN10-13 (PA6)** and **CN7-32 (PA4, the gate DAC)**. Read every value to the mV (0.1 mV if the DMM has it). *`--i-limit 165`: PA0 floats off the board, and 165 mA is the ADC ceiling, so no floating reading can end the hold* | V_3V3 = ____ V ; PA5 full (**DAC max**) = ____ V ; PA6 full = ____ V ; PA5 zero (**DAC min**) = ____ mV ; PA6 zero = ____ mV ; PA4 zero = ____ mV ; LD2 dark ☐ |
| P1b pass | **LD2 dark** throughout; **PA5 full ≥ V_3V3 − 0.20 V**, the top of the buffered DAC's guaranteed range; **PA6 within 5 mV of PA5** at both levels; **PA5 zero ≤ 0.20 V**. Fail: LD2 lit or PA5 low → SB21 still conducting, redo P1a(a). PA6 ≠ PA5 → shunt not seated, redo P1a(b). **The pass is only the datasheet guarantee. The figures are the result:** DAC min and max decide the buffer question (blueprint §3.5, *Range*), and the floor matters more than the ceiling. Write both, and the floor × 3.32 at the feedback node | pass ☐ ; floor × 3.32 = ____ V |
| P2 | Seat the Nucleo on J7/J8; check against README *Footprint orientation*. The CN10-11/13 shunt stays on. J3 and J4 jumpers on **RNG1** | done ☐ |
| P3 | **Practise on board 5; board 1's C1 stays empty.** On **board 5**, unpowered: fit a 3.3 pF to C1, remove it, fit it, remove it: the Block 2 swap, twice. Clean with IPA. Loupe: both C1 pads intact and flat, none lifted. Leave board 5's C1 empty. **Board 1 powers up with C1 empty**: Block 1 is the bare run (CONTINGENCY Part B §2B) | board 5 pads OK ☐ ; board 1 C1 empty ☐ |
| P4 | **Pad, then heatsink on Q1.** Trim the Sil-Pad K-10 (cut for TO-220) to Q1's TO-126 tab. Fit it between the tab and the heatsink (Boyd 577500B00000G, slide-on); the heatsink must still grip firmly with the pad in place. Board unpowered. DMM: **(a)** heatsink to **TP7 (+15 V)**: expect **OL**, which proves the pad insulates. **(b)** heatsink to **TP27**: expect **OL**. Either reading not OL, or a loose heatsink: refit, re-measure; no Block 4 until both pass | grips ☐ ; (a) ____ ; (b) ____ |
| P5 | Build **L1**: 100 nF ceramic ‖ 200 Ω 1 W, leads ≤ 3 cm, to J6 pins 2 (D) and 3 (S). DMM: L1's resistance (used off-bench for the full-scale ADC check against `11_q3.csv`). Build a **jumper** for J6 D–S | R_L1 = ____ Ω |
| P6 | Build the **Kelvin pair**: J5 pin 1 → J6 D, J5 pin 2 → J6 S | done ☐ |
| P7 | Build a **reversed barrel lead**: plug centre to supply −, sleeve to supply + | done ☐ |
| P8 | Kit: C0G 1.5 / 2.2 / 2.7 / 3.3 / 3.9 / 4.7 pF (labelled, on their tape), 330 Ω and 47 Ω axial, IPA, brush, fine iron, thermometer for step 14. For step 13a: a **10 kΩ** resistor (§8 assortment) with a mini-grabber on each lead | done ☐ |
| P9 | Laptop: `mkdir h4`, terminal in `host/`, `P=<port>` | done ☐ |

**Why P4(a).** Q1's tab is its collector, tied to **+15 V**. Without the pad,
the heatsink is live at +15 V, and anything grounded touching it shorts the
+15 V rail straight to ground, bypassing the current limiter; only the bench
supply's current limit is left. The heatsink-to-TP27 check (b) does not
catch this: a live heatsink still reads OL to ground when nothing grounded
touches it. Only the reading to TP7 proves the pad insulates.

## Setup at the bench (10 min)

| # | Do |
|---|---|
| S1 | Bench supply: **15.00 V, limit 100 mA, output OFF**. Leads not connected to the board yet |
| S2 | Scope CH1: 10× probe hooked on **TP3** (emitter), ground lead clipped to **TP27**'s loop. No spring ground: TP27 is 50 mm away, and nothing near TP3 takes one safely (`DECISIONS.md` R2-1). AC, 20 mV/div, BW limit 20 MHz, 1 µs/div, trigger CH1 rising +30 mV, normal mode, holdoff 1 ms, trigger point 1 div from left |
| S3 | J6: **L1** fitted, Kelvin pair fitted. Nucleo USB to the laptop |

---

## Block 1: power and oscillation, C1 empty (≈ 20 min). Highest-information first.

**This is the bare run** (Daniel, 2026-10-24; CONTINGENCY §2B). Steps 2, 3 and 5 are
Block 2's "none" row, measured first. C1 is fitted only in Block 2.

| # | min | Do | Expect | Pass | Record | Fail → |
|---|---|---|---|---|---|---|
| 1 | 1 | Supply output ON, leads free. DMM: red on supply + lead, black on − lead | +15.00 V | +14.90…+15.10 V | V = ____ | Output OFF, swap leads, redo 1 |
| 1b | 1 | Output OFF. Connect + to J2 **"+15V"**, − to J2 **"GND"**. Output ON. Read the supply current after 5 s | ~8 mA, not in CC | 3–25 mA | I = ____ mA | Output OFF → **STOP**, end session |
| 2 | 3 | **Oscillation, L1, C1 empty.** `CAP --vds-max 6 --n 61 --settle-us 50000 -o h4/02_osc_L1.csv`. Scope 20 µs/div, persistence ON, run it **3×**. Cursors at +20 µs and +100 µs after the edge; read the envelope p-p between them | < 2 mV (bare it rings; ringing should be gone by +20 µs) | < 5 mV | p-p = ____ mV | Measure frequency f = ____ → **CONTINGENCY A1** |
| 2b | 2 | Same, **BW limit OFF**, 20 ns/div, trigger auto, persistence 3 s, run once | < 10 mV | < 20 mV | p-p = ____ mV | f = ____ → **CONTINGENCY A1** |
| 3 | 3 | **Oscillation, open load.** Output OFF, remove L1 (Kelvin stays), ON. Repeat 2 → `h4/03_osc_open.csv` | < 2 mV | < 5 mV | p-p = ____ mV | f = ____ → **CONTINGENCY A1** |
| 4 | 3 | **Rails.** DMM: TP7 to TP27; TP8 to TP9; TP9 to TP27; TP28 to TP7 | 15.00; 3.30; 0.0; < 2 mV | 14.90–15.05 V; 3.20–3.40 V; ±1.0 mV; ≤ 2 mV | ____ ; ____ ; ____ ; ____ | Output OFF → **STOP** |
| 5 | 4 | **Step test, C1 empty, L1.** Output OFF, refit L1, ON. Scope back to S2 settings, averaging 16. `CAP --vds-max 6 --n 61 --settle-us 50000 -o h4/05_step_none.csv`. **(a)** Overshoot, automatic, mean. **(b)** 2 mV/div, offset −100 mV, cursor at +5 µs: deviation from the level at +50 µs | (a) ~50–75% (10–25° of phase margin, CONTINGENCY §2B; hand estimate); (b) — | None: it is data, Block 2's "none" row | O = ____ % ; dev = ____ mV | Record → STOP POINT A |

■ **STOP POINT A** (~20 min): supply output OFF, then USB. Blocks 2–4
still to do.

## Block 2: the C_f sweep (≈ 20–40 min). It stops once the best value is bracketed.

**Changed 2026-10-24 (Daniel): Block 2 no longer runs every value.** It
stops once the best value has a worse one on each side. Every row is a
remove-and-refit of an 0603 at C1, whose pads sit on the op-amp's inverting
input, the node §3.1's stability rests on. Fewer solder operations on that
pad are worth more than the extra data points. §3.1's rule still holds (no
stability result from one C_f): a bracketed minimum still varies C_f both
ways (CONTINGENCY §3).

For each row: supply output OFF, remove the old C1 (none on run 1), fit the
new one, clean with IPA, wait 2 min, output ON. Run
`CAP --vds-max 6 --n 61 --settle-us 50000 -o h4/06_cf_<value>.csv`
(`06_cf_3p3.csv`, `06_cf_3p9.csv`, …). Measure (a) and (b) as in step 5,
and the step-2 envelope (p-p, +20…100 µs). Write the run number in the row.

**Best so far:** the lowest O among rows with p-p < 5 mV; on a tie within 2
points, the smaller C1 (the step-7 rule). A row whose p-p is ≥ 5 mV is an
oscillating value: record it and move on. It is data, not a stop.

**Next row, after every row:**

1. Run 1 is **3.3 pF**.
2. No row yet with p-p < 5 mV: the first value not yet run from 3.3, 3.9,
   2.7, 4.7, 2.2, 1.5. None left → **step 7**.
3. Otherwise, take the best's neighbours in kit order,
   none · 1.5 · 2.2 · 2.7 · 3.3 · 3.9 · 4.7 (none and 4.7 have one each).
   A neighbour not yet run → fit it, the larger first. All run → rule 4.
4. **Broad-minimum guard, once** (CONTINGENCY §3). Take the spread,
   max O − min O, over the best and its neighbours. An oscillating row
   counts as 8 or more. **8 points or more → step 7.** Under 8 → fit any not
   yet run of the **five** kit values nearest the best (one beyond each
   neighbour; beside none or 4.7, two on the open side), then go back to
   rule 3, since the best may have moved. When rule 3 stops again, go to
   step 7 without repeating this rule.

If 3.3 pF is best, that is three fits: 3.3, 3.9, 2.7. Five if the guard
widens it: 2.2 and 4.7 as well.

| C1 | Run | File | O (%) | dev @ 5 µs (mV) | p-p +20…100 µs (mV) |
|---|---|---|---|---|---|
| none | 0 (Block 1) | 05_step_none.csv | (from 5) | (from 5) | (from 2) |
| 1.5 pF | ____ | 06_cf_1p5.csv | ____ | ____ | ____ |
| 2.2 pF | ____ | 06_cf_2p2.csv | ____ | ____ | ____ |
| 2.7 pF | ____ | 06_cf_2p7.csv | ____ | ____ | ____ |
| 3.3 pF | 1 | 06_cf_3p3.csv | ____ | ____ | ____ |
| 3.9 pF | ____ | 06_cf_3p9.csv | ____ | ____ | ____ |
| 4.7 pF | ____ | 06_cf_4p7.csv | ____ | ____ | ____ |

■ **STOP POINT B**, after run 3 if the sweep is still going (~20 min):
output OFF, USB. Leave the last C1 fitted and note it: ____

| # | min | Do | Pass | Record | Fail → |
|---|---|---|---|---|---|
| 7 | 6 | **Fit the best C1** (no swap if it is already fitted; for none, remove C1). Re-run the step test on **L1** (`h4/07_best_L1.csv`) and on **open** (`h4/07_best_open.csv`) | L1: O ≤ 25%, dev ≤ 1.0 mV, p-p < 5 mV. Open: p-p < 5 mV | C_f = ____ pF; O_L1 = ____ %; O_open = ____ %; best at an end (none or 4.7)? Y/N ____; rows run ____; spread over the best and its neighbours = ____ points; widened (rule 4)? Y/N ____; spread over the five nearest the best = ____ points | No row with p-p < 5 mV → **CONTINGENCY A4**. Otherwise → **CONTINGENCY A3** |

■ **STOP POINT C** (~20 min): output OFF, USB. The loop result is now on
paper.

## Block 3: calibration and protection (≈ 13 min). J6 open, Kelvin pair on.

| # | min | Do | Expect | Pass | Record | Fail → |
|---|---|---|---|---|---|---|
| 8 | 2 | **ADC zero.** Remove L1. `CAP --vds-max 1 --n 2 --settle-us 100000 -o h4/08_zero.csv`, then `grep -v '^#' h4/08_zero.csv \| head -1 \| cut -d, -f4,5` (prints vds_meas_v, i_meas_ma at 0 V) | ~0, ~0 | \|v\| ≤ 0.008 V; \|i\| ≤ 0.10 mA | v = ____ V ; i = ____ mA | Record, continue |
| 9 | 1 | **+3V3, clamp conducting.** Unplug the Kelvin pair at J5, wait 5 s, DMM TP8 to TP9, plug back | 3.30 V | 3.20–3.40 V | ____ V | Plug J5 back at once, record, continue |
| 10 | 1 | **Zener knee.** `HOLD --vgs 10.95 --vds 0.1 --seconds 20 -o h4/10_zener.csv`. At host **t = 10 s**: DMM red TP16, black TP18 | ~0 mV | ≤ 10 mV | ____ mV | Record, continue |
| 11 | 1 | **Q3 drop under load.** Fit L1. `HOLD --vds 6 --seconds 20 -o h4/11_q3.csv`. At **t = 10 s**: DMM red TP28, black TP7; supply current; the host's i_meas | ≤ 6.5 mV at ~34 mA | ≤ 7 mV | V = ____ mV ; I_supply = ____ mA ; i_meas = ____ mA | Record, continue |
| 12 | 1 | **R_PTC.** `HOLD --vds 6 --seconds 20 -o h4/12_rptc.csv`. At **t = 10 s**: DMM red TP5, black TP17; the host's i_meas | 40–400 mV at ~26 mA | R = V / i_meas in 1.6–15 Ω | V = ____ mV ; i = ____ mA ; R = ____ Ω | Record, continue |
| 13 | 3 | **Reverse polarity, J1.** Output OFF; disconnect the J2 leads; limit **20 mA**; connect the reversed barrel lead to J1. Output ON for 5 s: read the supply current and TP7 to TP27. Output OFF, remove the lead, reconnect J2, limit back to **100 mA** | 0 mA ; 0.00 V | ≤ 1 mA ; ≤ ±0.10 V | I = ____ ; V = ____ | Output OFF → record → **STOP**, end session |
| 13a | 3 | **D3 present and the right way round.** Output OFF. Pull the **J3** jumper (this disconnects the sweep output from DUT_D) and unplug the Kelvin pair at **J5**. Clip the 10 kΩ between **TP7** (+15 V) and **TP19** (DUT_D). Output ON, wait 5 s. DMM: TP19 to TP27, then TP7 to TP27. Output OFF, remove the 10 kΩ, J3 back on **RNG1**, J5 back on | TP19 = V_D3 ≈ 13.3–14.7 V (D3 in breakdown at 0.03–0.3 mA) | **TP19 12.0–14.8 V, and ≥ 0.2 V below TP7** | V_D3 = ____ V ; TP7 = ____ V | Record, continue; off-bench, inspect D3 (README *Footprint orientation*). Within 0.2 V of TP7 = D3 missing or open; below 1 V = reversed or shorted |

■ **STOP POINT D** (~13 min): output OFF, USB.

## Block 4: held short (≈ 8 min). Only with P4 done.

Supply limit **150 mA**. J6: L1 off, **jumper D–S on**. Kelvin pair on.
Scope CH1 on TP3: AC, 50 mV/div, 1 µs/div, trigger auto.

| # | min | Do | Expect | Pass | Record | Fail → |
|---|---|---|---|---|---|---|
| 14 | 4 | `HOLD --vds 10.96 --seconds 200 --i-limit 165 -o h4/14_short.csv`. The jumper is on, so the limiter is engaged from the first row. The host's t is the clock; the hold ends itself at 200 s. At **t = 5 s**: supply current | ~115 mA (107 load + idle, sim 10) | 100–130 mA | I = ____ mA | Output OFF, record, → 15 |
| 14a | — | **t = 10 s**: DMM red **TP3**, black **TP4** (R_sense) | 0.752 V (sim 11) | 0.68–0.83 V | V_cold = ____ | Record, continue |
| 14b | — | **t = 20 s**: DMM red **TP1**, black **TP2** (R_B) | ~10.6 V (32 mA, sim 10) | ≤ 14.85 V (≤ 45 mA) | V_RB = ____ | Record, continue |
| 14c | — | **t = 30 s**: scope p-p on TP3; the host's i_meas | < 10 mV ; ~107 mA | < 20 mV ; 95–120 mA | p-p = ____ ; i = ____ | Record, continue |
| 14d | — | **t = 180 s**: TP3–TP4 again; thermometer on the heatsink at the tab | ≤ V_cold ; ~48 °C (26 °C/W) | ≥ 0.60 V ; ≤ 70 °C | V_warm = ____ ; T = ____ °C | **T > 70 °C: output OFF at once** → record → **STOP** |
| 15 | 2 | **Short recovery: verify the bound.** Jumper on. Scope CH1 → **TP19** (DUT_D), DC, 2 V/div, vertical offset so the **screen centre is +10 V** (shows +2…+18 V), 1 µs/div, trigger rising **10.5 V**, single, armed. `HOLD --vds 10 --seconds 60 --i-limit 165 -o h4/15_recovery.csv`. Any time after host t = 5 s, **pull the jumper**. Read the peak | 13.3–14.8 V: D3 clamping at its breakdown voltage (sim 10's unclamped peak is 14.8 V) | **≤ 16.0 V** | peak = ____ V (no trigger: write "< 10.5"; off the top: write "> 18") | **> 16.0 V: something other than the predicted overshoot is happening.** Save the scope screen to `h4/15_peak.png`, record, continue. Off-bench: find the cause |

**Steps 13a and 15** (D3 fitted by default, Daniel 2026-10-11;
`DECISIONS.md` D3). Step 15 verifies a bound; it does not decide anything.
It **cannot by itself show that D3 is working**: the unprotected peak sim 10
predicts is the same ~14.8 V that a D3 at the top of its tolerance clamps
to, so the two read alike. Step 13a is the check that tells them apart. It
drives D3 into DC breakdown, and only a fitted, correctly oriented D3 holds
TP19 well below +15 V. Step 13a shows D3 is present and breaks down at the
right voltage; step 15 shows the transient stays under 16 V. Neither shows
D3 is fast enough to catch the edge. That would take step 15 run twice,
with D3 fitted and removed, and the two peaks only separate if V_D3 is well
below the unclamped ~14.8 V. It needs D3 off the board, so it is not on
this card.

Threshold 16 V (was 12 V, from the spec ceiling; no TVS holds 12 V without
leaking at the 10.96 V full scale). With D3 fitted, 13.3–14.8 V is the part
working as specified. Above 16 V is not the overshoot sim 10 predicted. D3
bounds a microsecond transient; it does not enforce the 10 V ceiling, and
sustained overcurrent is the firmware limit's job, not D3's.

Probe off TP19 after this step: a 10 MΩ probe on the DUT node draws 1 µA
at 10 V, and reads as DUT current on ranges 2–3 (blueprint §3.3).

■ **STOP POINT E**: supply output OFF, USB. Session complete. Hand back
this sheet and `h4/`.
