# H4 bring-up card

Print this page and `CONTINGENCY.md` Part A. Execute from paper and make no
decisions at the bench: every branch is a numbered goto. Fill in every blank
(`____`) and hand the sheet back. CSV files go in `h4/`, named in the
Record column.

| Board | Date | Operator | Ambient °C | Supply | Scope | DMM | Port (`P=`) |
|---|---|---|---|---|---|---|---|
| ____ | ____ | ____ | ____ | ____ | ____ | ____ | ____ |

Board **1** is the bring-up board. Boards 2–5 stay untouched.

**Rules:**

- No held short (Block 4, steps 14–15) unless P4 is done.
- **No soldering on any board.** C1 stays empty for the whole session
  (Daniel, 2026-10-25; `DECISIONS.md` R2-2).
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
| P1a | **Nucleo mod: PA5–PA6 shunt on. SB21 stays fitted.** USB unplugged, Nucleo not seated. On the top-side morpho pins, fit a 2.54 mm shunt across **CN10-11 (PA5)** and **CN10-13 (PA6)**. *The F303RE has no DAC2: the sweep DAC is DAC1_OUT2 on PA5, and the board takes it at PA6. With SB21 fitted, LD2 and its 510 Ω resistor load PA5. Nothing in this session needs the levels where that matters, so SB21 is not removed: measure first (P1b; `DECISIONS.md` R2-3)* | shunt ☐ |
| P1b | **Nucleo check, off the board: map the LED load.** USB in, Nucleo **not seated**: on the board, an unpowered op-amp's inputs would load the DAC. Run one HOLD per row of the **P1b sheet** below, in order: `HOLD --vds <V> --seconds 20 --i-limit 165 -o h4/p1b_<V>.csv`. At **t = 10 s** of each, DMM black on **CN10-9 (GND)**, red on **CN10-11 (PA5)**, then **CN10-13 (PA6)**; note LD2. In the first hold (0 V) also read **CN7-16 (+3V3)** and **CN7-32 (PA4, the gate DAC)**. Last, the **gate row**: `HOLD --vgs 10.95 --vds 0 --seconds 20 --i-limit 165 -o h4/p1b_gate.csv`, step 10's gate level; at t = 10 s read **CN7-32 (PA4)**. Read every value to the mV (0.1 mV if the DMM has it). *`--i-limit 165`: PA0 floats off the board, and 165 mA is the ADC ceiling, so no floating reading can end the hold* | sheet below |
| P1b pass | **PA6 within 5 mV of PA5** at every level, and **PA5 at 0 V ≤ 0.20 V** (the floor of the buffered DAC's guaranteed range). PA6 ≠ PA5 → shunt not seated, redo P1a. **LD2 lighting from the 6.64 V row up is expected, not a fail.** No pass mark on the upper rows: **the shortfall column is the result.** It maps where the LED load starts to bite, and it is the measurement that decides whether SB21 ever comes off (`DECISIONS.md` R2-3). The floor matters more than the ceiling (blueprint §3.5, *Range*): write the floor × 3.32 too | pass ☐ ; floor × 3.32 = ____ V |
| P2 | Seat the Nucleo on J7/J8; check against README *Footprint orientation*. The CN10-11/13 shunt stays on. J3 and J4 jumpers on **RNG1** | done ☐ |
| P3 | **Board 1's C1 is empty.** Loupe: both C1 pads bare and flat. Nothing is fitted to C1 at H4 (Block 2) | C1 empty ☐ |
| P4 | **Pad, then heatsink on Q1.** Trim the Sil-Pad K-10 (cut for TO-220) to Q1's TO-126 tab. Fit it between the tab and the heatsink (Boyd 577500B00000G, slide-on); the heatsink must still grip firmly with the pad in place. Board unpowered. DMM: **(a)** heatsink to **TP7 (+15 V)**: expect **OL**, which proves the pad insulates. **(b)** heatsink to **TP27**: expect **OL**. Either reading not OL, or a loose heatsink: refit, re-measure; no Block 4 until both pass | grips ☐ ; (a) ____ ; (b) ____ |
| P5 | Build **L1**: 100 nF ceramic ‖ 200 Ω 1 W, leads ≤ 3 cm, to J6 pins 2 (D) and 3 (S). DMM: L1's resistance (used off-bench for the full-scale ADC check against `11_q3.csv`). Build a **jumper** for J6 D–S | R_L1 = ____ Ω |
| P6 | Build the **Kelvin pair**: J5 pin 1 → J6 D, J5 pin 2 → J6 S | done ☐ |
| P7 | Build a **reversed barrel lead**: plug centre to supply −, sleeve to supply + | done ☐ |
| P8 | Kit: thermometer for step 14. For step 13a: a **10 kΩ** resistor (§8 assortment) with a mini-grabber on each lead. No soldering iron: nothing is soldered at H4. *The C0G kit on hand is 1.5 / 2.2 / 2.7 / 4.7 pF; the 3.3 and 3.9 pF parts are gone (2026-10-25). None of it is used at the bench* | done ☐ |
| P9 | Laptop: `mkdir h4`, terminal in `host/`, `P=<port>` | done ☐ |

**P1b sheet.** Ideal PA5 = code / 4095 × V_3V3, with V_3V3 as read in the
first hold (the DAC's reference is the Nucleo's 3V3). The codes are what the
firmware sends for each `--vds`. Shortfall = ideal − measured.

| `--vds` (V) | Code | PA5 at 3.300 V (ref.) | Ideal PA5 at your V_3V3 (V) | PA5 measured (V) | Shortfall (mV) | PA6 (V) | LD2 lit? |
|---|---|---|---|---|---|---|---|
| 0 | 0 | 0.000 | 0 | ____ | — | ____ | ____ |
| 6.64 | 2482 | 2.000 | ____ | ____ | ____ | ____ | ____ |
| 8.30 | 3102 | 2.500 | ____ | ____ | ____ | ____ | ____ |
| 9.96 | 3723 | 3.000 | ____ | ____ | ____ | ____ | ____ |
| 10.29 | 3846 | 3.099 | ____ | ____ | ____ | ____ | ____ |
| 10.96 | 4095 | 3.300 | ____ | ____ | ____ | ____ | ____ |

**Gate row** (PA4, DAC1_OUT1; no LED on it):

| `--vgs` (V) | Code | PA4 at 3.300 V (ref.) | Ideal PA4 at your V_3V3 (V) | PA4 measured (V) | Shortfall (mV) | × 3.32 at the gate (mV) |
|---|---|---|---|---|---|---|
| 10.95 | 4093 | 3.298 | ____ | ____ | ____ | ____ |

V_3V3 = ____ V ; PA4 at 0 V = ____ mV

**What the gate row means.** This is the only measurement the gate channel
gets. 10.95 V puts PA4 above the buffered DAC's guaranteed VDDA − 0.2 V
(blueprint §3.5, *Range*). **The gate is not measured**: the CSV carries
`vgs_set_v` only. So a PA4 shortfall makes the real gate lower than
`vgs_set_v` by shortfall × 3.32, and that goes straight into V_th
uncorrected: **V_th reads high by up to shortfall × 3.32 for gate steps at
this level.** It is a bound for steps near full scale only. VDDA − 0.2 V is
a ceiling, not a gain error, so a full-scale shortfall says nothing about
steps inside the guaranteed range (PA4 ≤ 3.1 V, ≤ 10.29 V at the gate). A
2N7000's steps, 2.6–3.6 V, sit at PA4 = 0.78–1.08 V. A family that mixes
steps inside and above the range does not get a pure offset: only its top
steps move, which tilts the fit. Step 10 is affected the same way: its Zener
check runs at the real gate, P1b's PA4 × 3.32, not 10.95 V.

**What the sheet decides.** The buffered DAC is rated for 5 kΩ or more. LD2
and its 510 Ω resistor draw more than that from PA5 ≈ 2.0–2.3 V, which is
**6.6–7.8 V at the feedback node** (depending on the LED's forward voltage;
estimate, not measured). Above that, `vds_set_v` is not what the DAC
produced, and **full-range sweeps to 10 V may fall short until SB21 is
addressed.** The host's series-drop diagnostic (`extract --diagnostics`,
`plot --diagnostic`) therefore fits only rows with `vds_set_v` ≤ 6.6 V by
default; `--vds-set-max` changes the limit once this sheet shows where the
shortfall starts. Nothing in this session's sweeps or measurements needs
the upper rows: Block 1 and steps 11–12 stay at 6 V (PA5 = 1.81 V); steps
14 and 15 go higher, and their notes say why the shortfall does not change
what they test.

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

**This is the bare run** (Daniel, 2026-10-24; CONTINGENCY §2B), and with
no C_f sweep it is the only loop measurement H4 makes. C1 stays empty.
A loop-band oscillation at step 2, 2b or 3 goes to CONTINGENCY A3, which
records it and returns here: Block 1 runs to the end either way, so the
bare record is complete at both loads.

| # | min | Do | Expect | Pass | Record | Fail → |
|---|---|---|---|---|---|---|
| 1 | 1 | Supply output ON, leads free. DMM: red on supply + lead, black on − lead | +15.00 V | +14.90…+15.10 V | V = ____ | Output OFF, swap leads, redo 1 |
| 1b | 1 | Output OFF. Connect + to J2 **"+15V"**, − to J2 **"GND"**. Output ON. Read the supply current after 5 s | ~8 mA, not in CC | 3–25 mA | I = ____ mA | Output OFF → **STOP**, end session |
| 2 | 3 | **Oscillation, L1, C1 empty.** `CAP --vds-max 6 --n 61 --settle-us 50000 -o h4/02_osc_L1.csv`. Scope 20 µs/div, persistence ON, run it **3×**. Cursors at +20 µs and +100 µs after the edge; read the envelope p-p between them | < 2 mV (bare it rings; ringing should be gone by +20 µs) | < 5 mV | p-p = ____ mV | Measure frequency f = ____ → **CONTINGENCY A1** |
| 2b | 2 | Same, **BW limit OFF**, 20 ns/div, trigger auto, persistence 3 s, run once | < 10 mV | < 20 mV | p-p = ____ mV | f = ____ → **CONTINGENCY A1** |
| 3 | 3 | **Oscillation, open load.** Output OFF, remove L1 (Kelvin stays), ON. Repeat 2 → `h4/03_osc_open.csv` | < 2 mV | < 5 mV | p-p = ____ mV | f = ____ → **CONTINGENCY A1** |
| 4 | 3 | **Rails.** DMM: TP7 to TP27; TP8 to TP9; TP9 to TP27; TP28 to TP7 | 15.00; 3.30; 0.0; < 2 mV | 14.90–15.05 V; 3.20–3.40 V; ±1.0 mV; ≤ 2 mV | ____ ; ____ ; ____ ; ____ | Output OFF → **STOP** |
| 5 | 4 | **Step test, C1 empty, L1.** Output OFF, refit L1, ON. Scope back to S2 settings, averaging 16. `CAP --vds-max 6 --n 61 --settle-us 50000 -o h4/05_step_none.csv`. **(a)** Overshoot, automatic, mean. **(b)** 2 mV/div, offset −100 mV, cursor at +5 µs: deviation from the level at +50 µs | (a) ~50–75% (10–25° of phase margin, CONTINGENCY §2B; hand estimate); (b) — | None: it is data, the bare result. Not a stability result (blueprint §3.1: none from C_f empty) | O = ____ % ; dev = ____ mV | Record → STOP POINT A |

■ **STOP POINT A** (~20 min): supply output OFF, then USB.

- **CONTINGENCY A3 was entered** (loop-band oscillation): **STOP. Session
  complete.** Hand back this sheet and `h4/`. Blocks 2–4 do not run on an
  oscillating loop.
- **Otherwise:** Block 2 does not run. Next is Block 3.

## Block 2: no C_f sweep (Daniel, 2026-10-25)

**If Block 1 showed no oscillation, Block 2 does not run and C1 stays
empty.** Go to Block 3.

**If Block 1 showed oscillation, there is no C_f sweep either.** CONTINGENCY
A3 has recorded the frequency and amplitude, and the session has stopped at
STOP POINT A. The predicted C_f is computed off-bench from that record
(CONTINGENCY §3). How it is resolved is Daniel's call, off-bench.

Nothing is fitted to C1 at H4. The sweep this block used to run was a
remove-and-refit of an 0603 at C1 for every row, by hand, and that is not
being done (`DECISIONS.md` R2-2). Steps 6 and 7 are retired; the later
step numbers are unchanged.

## Block 3: calibration and protection (≈ 13 min). J6 open, Kelvin pair on.

| # | min | Do | Expect | Pass | Record | Fail → |
|---|---|---|---|---|---|---|
| 8 | 2 | **ADC zero.** Remove L1. `CAP --vds-max 1 --n 2 --settle-us 100000 -o h4/08_zero.csv`, then `grep -v '^#' h4/08_zero.csv \| head -1 \| cut -d, -f4,5` (prints vds_meas_v, i_meas_ma at 0 V) | ~0, ~0 | \|v\| ≤ 0.008 V; \|i\| ≤ 0.10 mA | v = ____ V ; i = ____ mA | Record, continue |
| 9 | 1 | **+3V3, clamp conducting.** Unplug the Kelvin pair at J5, wait 5 s, DMM TP8 to TP9, plug back | 3.30 V | 3.20–3.40 V | ____ V | Plug J5 back at once, record, continue |
| 10 | 1 | **Zener knee.** `HOLD --vgs 10.95 --vds 0.1 --seconds 20 -o h4/10_zener.csv`. At host **t = 10 s**: DMM red TP16, black TP18. *The gate DAC is DAC1_OUT1 on **PA4**, which carries no LED; LD2 loads PA5 only. This step is not affected by SB21. (10.95 V is code 4093, PA4 ≈ 3.298 V, above the buffered DAC's guaranteed VDDA − 0.2 V. That ceiling is a separate open question, blueprint §3.5, and applies to both channels)* | ~0 mV | ≤ 10 mV | ____ mV | Record, continue |
| 11 | 1 | **Q3 drop under load.** Fit L1. `HOLD --vds 6 --seconds 20 -o h4/11_q3.csv`. At **t = 10 s**: DMM red TP28, black TP7; supply current; the host's i_meas | ≤ 6.5 mV at ~34 mA | ≤ 7 mV | V = ____ mV ; I_supply = ____ mA ; i_meas = ____ mA | Record, continue |
| 12 | 1 | **R_PTC.** `HOLD --vds 6 --seconds 20 -o h4/12_rptc.csv`. At **t = 10 s**: DMM red TP5, black TP17; the host's i_meas. *6 V is below the 6.6 V limit, so `vds_set_v` is trustworthy here; the host's series-drop check on this file uses it as is (P1b sheet note)* | 40–400 mV at ~26 mA | R = V / i_meas in 1.6–15 Ω | V = ____ mV ; i = ____ mA ; R = ____ Ω | Record, continue |
| 13 | 3 | **Reverse polarity, J1.** Output OFF; disconnect the J2 leads; limit **20 mA**; connect the reversed barrel lead to J1. Output ON for 5 s: read the supply current and TP7 to TP27. Output OFF, remove the lead, reconnect J2, limit back to **100 mA** | 0 mA ; 0.00 V | ≤ 1 mA ; ≤ ±0.10 V | I = ____ ; V = ____ | Output OFF → record → **STOP**, end session |
| 13a | 3 | **D3 present and the right way round.** Output OFF. Pull the **J3** jumper (this disconnects the sweep output from DUT_D) and unplug the Kelvin pair at **J5**. Clip the 10 kΩ between **TP7** (+15 V) and **TP19** (DUT_D). Output ON, wait 5 s. DMM: TP19 to TP27, then TP7 to TP27. Output OFF, remove the 10 kΩ, J3 back on **RNG1**, J5 back on | TP19 = V_D3 ≈ 13.3–14.7 V (D3 in breakdown at 0.03–0.3 mA) | **TP19 12.0–14.8 V, and ≥ 0.2 V below TP7** | V_D3 = ____ V ; TP7 = ____ V | Record, continue; off-bench, inspect D3 (README *Footprint orientation*). Within 0.2 V of TP7 = D3 missing or open; below 1 V = reversed or shorted |

■ **STOP POINT D** (~13 min): output OFF, USB.

## Block 4: held short (≈ 8 min). Only with P4 done.

Supply limit **150 mA**. J6: L1 off, **jumper D–S on**. Kelvin pair on.
Scope CH1 on TP3: AC, 50 mV/div, 1 µs/div, trigger auto.

| # | min | Do | Expect | Pass | Record | Fail → |
|---|---|---|---|---|---|---|
| 14 | 4 | `HOLD --vds 10.96 --seconds 200 --i-limit 165 -o h4/14_short.csv`. The jumper is on, so the limiter is engaged from the first row. The host's t is the clock; the hold ends itself at 200 s. *LD2 lights. The limiter sets every figure in step 14, not the command: it needs only ~4 V at the node to engage (~107 mA through R_iso, shunt and PTC), and LD2 cannot pull PA5 below its own ~1.7 V turn-on, 5.6 V at the node* At **t = 5 s**: supply current | ~115 mA (107 load + idle, sim 10) | 100–130 mA | I = ____ mA | Output OFF, record, → 15 |
| 14a | — | **t = 10 s**: DMM red **TP3**, black **TP4** (R_sense) | 0.752 V (sim 11) | 0.68–0.83 V | V_cold = ____ | Record, continue |
| 14b | — | **t = 20 s**: DMM red **TP1**, black **TP2** (R_B) | ~10.6 V (32 mA, sim 10) | ≤ 14.85 V (≤ 45 mA) | V_RB = ____ | Record, continue |
| 14c | — | **t = 30 s**: scope p-p on TP3; the host's i_meas | < 10 mV ; ~107 mA | < 20 mV ; 95–120 mA | p-p = ____ ; i = ____ | Record, continue |
| 14d | — | **t = 180 s**: TP3–TP4 again; thermometer on the heatsink at the tab | ≤ V_cold ; ~48 °C (26 °C/W) | ≥ 0.60 V ; ≤ 70 °C | V_warm = ____ ; T = ____ °C | **T > 70 °C: output OFF at once** → record → **STOP** |
| 15 | 2 | **Short recovery: verify the bound.** Jumper on. Scope CH1 → **TP19** (DUT_D), DC, 2 V/div, vertical offset so the **screen centre is +10 V** (shows +2…+18 V), 1 µs/div, trigger rising **10.5 V**, single, armed. `HOLD --vds 10 --seconds 60 --i-limit 165 -o h4/15_recovery.csv`. Any time after host t = 5 s, **pull the jumper**. Read the peak. *`--vds 10` is code 3738, PA5 ≈ 3.01 V, inside the LED-loaded range. The level the node recovers to is about P1b's 9.96 V row, measured PA5 × 3.32 (15 codes lower, ~40 mV), not 10 V. A short level makes the 16 V bound easier to meet, so write it next to the peak* | 13.3–14.8 V: D3 clamping at its breakdown voltage (sim 10's unclamped peak is 14.8 V) | **≤ 16.0 V** | peak = ____ V (no trigger: write "< 10.5"; off the top: write "> 18") ; level from P1b = ____ V | **> 16.0 V: something other than the predicted overshoot is happening.** Save the scope screen to `h4/15_peak.png`, record, continue. Off-bench: find the cause |

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
