# host/ — Python host for the curve tracer

Capture, plot, extract, and generate SPICE model cards. Blueprint §5.

MVP scope, matching the firmware: **range 1 only, DC sweep, no pulsed mode.**

```
ct_host/
  transport.py   Transport protocol; pyserial, or a subprocess running ct_sim
  protocol.py    commands, sweep driver, rows delivered as they arrive
  csvio.py       parse and save; the header is preserved verbatim
  recompute.py   raw accumulators + cal_* -> engineering units, and the
                 agreement assertion between host and firmware
  dataset.py     rows -> curves -> slices on a common MEASURED voltage grid
  extract/
    common.py    Estimate, FitRange, LinearFit -- uncertainties and visible ranges
    mosfet.py    V_th, beta / KP, lambda, R_DS(on), subthreshold
    diode.py     n, I_S, R_s
  parallel.py    R_p: a resistor across D-S with the device, and its current
                 taken back out
  zero.py        the instrument's current zero, on its own (--zero)
  channel.py     the current channel's gain, zero, common-mode term, voltage
                 offset and floor, fitted from holds (channel, --zero FILE)
  spice.py       .model cards
  overlay.py     the card simulated in ngspice, and measured vs simulated
  plot.py        live family plot, static plots, series-drop diagnostic
  cli.py         python -m ct_host capture | hold | plot | extract | model |
                 simulate | overlay | annotate | channel | ports
tests/           203 tests, against the simulator and the recorded captures
                 in h4/
```

`parse_cmrr_log.py`, `parse_current_limit.py` and `parse_tran_overshoot.py`
are the LTspice log parsers from Phase 0. They are unrelated to this package.

---

## Quick start, with no instrument

```sh
make -C ../firmware                    # builds ../firmware/build/ct_sim
pip install -r requirements.txt

python -m ct_host capture --sim mosfet --sim-vth 2.15 --sim-k 0.055 \
    --vgs 2.6,2.9,3.2,3.5 --n 200 --vds-max 10 -o data/sim.csv
python -m ct_host extract data/sim.csv --type mosfet
python -m ct_host model   data/sim.csv --type mosfet --name SIM2N7000
python -m ct_host plot    data/sim.csv --save iv.png
```

With hardware, replace `--sim mosfet` with `--port /dev/tty.usbmodemXXXX`.
Nothing else changes; `python -m ct_host ports` lists what is attached.

```sh
pytest tests/          # the whole suite, no instrument needed
```

---

## Testing without hardware

`ct_sim` is not a mock. It is `firmware/core/` — the same sweep engine, CSV
writer, command parser and current limit that runs on the Nucleo — compiled
for the host with a modelled DUT behind `ct_device_t`. So these tests exercise
the real firmware logic and the real wire format.

It also **streams**: each line is written and flushed as produced, so the live
plot is developed and tested against it exactly as it will behave on the
serial link.

### The closed loop

The extraction tests hand the simulator a device with chosen parameters, run a
sweep, extract, and require the values back:

| Fed in | Recovered | Error |
|---|---|---|
| `V_th` = 2.15 V | 2.1502 V | 0.2 mV |
| `k` = 0.055 A/V² | `kp_wl` = 0.05506 | 0.1% |
| `λ` = 0.012 /V | 0.01192 | 0.7% |
| diode `n` = 1.75 | 1.7605 | 0.6% |
| diode `I_S` = 2.5 nA | 2.73 nA | 9% |
| diode `R_s` = 0.6 Ω | 0.5914 Ω | 1.4% |

That closes `physics → measurement → model` in software before it closes on
the bench, which matters because the bench has been blocked since the trainer
fault of 2026-09-24 (`docs/characterization.md`).

---

## Four things this does that a naive implementation would not

### 1. Current and voltage are recomputed from the raw accumulators

`i_acc` and `v_acc` are re-derived through the `cal_*` header fields, and the
result is **asserted against** the firmware's own `i_meas_ma` / `vds_meas_v`.

The two paths use the same constants from two places — `ct_config.h` and the
CSV header — so a disagreement means one has drifted. A few percent of gain
error does not look wrong in a plot; it looks like a slightly different
transistor, and it would propagate into a SPICE model with nothing to notice.
So a mismatch raises `CalibrationMismatch`, names the worst row, and says
which constant would explain the observed ratio.

Current agreement on simulator data is better than 10⁻⁴ mA, a factor of 20
inside the tolerance, so the tolerance is not quietly doing the work. A 0.1%
shunt error is caught.

Analysis then runs on the recomputed values, not the reported ones.

### 2. A fixed-V_DS slice interpolates onto measured voltage

This is the one that looks like a non-issue and is not. `R_iso`'s drop scales
with current, so at one commanded `vds_set_v` every curve reaches a different
measured `vds_meas_v`:

```
commanded 2.033 V  ->  1.902 V at V_GS = 2.6 V    (5.7 mA)
                   ->  0.890 V at V_GS = 3.6 V   (49.8 mA)
```

Grouping rows by `vds_set_v` — the obvious implementation — compares a
saturated device against one pushed into triode and returns a threshold
voltage that is wrong with a convincing R². `dataset.py` slices on measured
voltage with per-curve interpolation instead, and refuses to extrapolate past
what a curve actually reached. Recorded in blueprint §3.4.

### 3. `beta` is de-embedded, and both conventions are reported

Two conventions differ by a factor of two:

| | |
|---|---|
| `I_D = β(V_GS − V_th)²` | `beta`, what the sqrt-fit gives |
| `I_D = ½·KP·(W/L)·(V_GS − V_th)²` | `kp_wl = 2β`, SPICE Level 1 |

`spice.py` emits `KP` from `kp_wl`. Getting this wrong halves every simulated
current, so both are named explicitly rather than one being called "k".

Separately, saturation current carries `(1 + λV_DS)`, so a fit at a slice
voltage returns `β_fit = β_true(1 + λV_slice)`. At the ~8.5 V slice these
sweeps produce, that is **+10%** — an order of magnitude above the fit's own
standard error and one-signed, so it reads as a good measurement of the wrong
quantity. The extractor divides it out using the fitted λ and keeps the raw
value as `beta_raw`. Blueprint §5.

### 4. Plots use `vds_meas_v`

Never `vds_set_v`. The instrument has a four-wire sense precisely because the
commanded value is wrong by over a volt at full current. `vds_set_v` appears
in exactly one place, the series-drop diagnostic, where the *difference* is
the measurement:

```sh
python -m ct_host plot data/run.csv --diagnostic
```

which fits the delta against current through the origin and reports the
implied series resistance against the expected `R_iso + shunt + R_PTC`, taken
from the header's `cal_*` constants, with the failure interpretations from
`firmware/README.md` (shorted Kelvin leads, bad sense connection, extra
contact resistance). Until the board's PTC is measured, `cal_r_ptc_ohm` reads
`unset` and the report says to measure it, quoting the R_PTC the fit implies.
Pass a fresh measurement after a trip with `--r-ptc OHM` (`extract
--diagnostics`) or `r_ptc_ohm=` (`vds_delta_report`, `plot_vds_delta`).

---

## A resistor across D–S: `--r-parallel`

Board 2's sweep loop oscillates at open load with C1 empty (Block 1,
2026-11-03; `docs/characterization.md`). A diode or MOSFET is an open load
at the bottom of its sweep. Sim 13 predicted that 470 Ω or less clamped
across D–S would keep the loop quiet; on the bench (2026-11-08) 470 Ω
oscillated, and **L1, 200 Ω ‖ 100 nF, is the R_p that works**: the 100 nF
is what quiets it (`docs/characterization.md`). The firmware can't tell
R_p from the device. The host subtracts `V / R_p` from every row, using the
Kelvin-sensed voltage, as the firmware already does for the Kelvin
divider's `V / 400k`. When R_p was fitted, the fit's offset, the
instrument's current zero, is subtracted with it.

```sh
python -m ct_host capture  ... --device R_p -o h4/rp.csv            # R_p alone
python -m ct_host extract  h4/rp.csv --type resistor                # I = V/R + offset
python -m ct_host capture  ... --device 1N4148 --r-parallel h4/rp.csv -o h4/d.csv
python -m ct_host extract  h4/d.csv                                 # R_p applied from the header
```

`--r-parallel` takes one of three sources:

- **A calibration capture of R_p alone** (the primary). The fit uses the
  instrument's own readings, so gain errors in current and voltage cancel:
  what is subtracted is what the instrument reads through R_p. The fit is
  `I = V / R + offset`, and the whole line is subtracted. On board 2 the
  offset was −0.087 mA, 43% of the diode fit's 0.2 mA floor. Left in, it
  read the 1N4148's n as 1.651 instead of 1.789 and I_S 3.2× low.
- **A value in ohms**, for example from a DMM. Gain error in the instrument
  does not cancel against it.
- **`auto`**: R_p fitted from the capture itself, where the device carries
  no current. That means rows below 0.25 V for a diode, and the lowest gate
  step for a MOSFET family. It needs rows down there. A sweep DAC with a
  floor above 0.25 V leaves none, and the fit then says so.

`capture --r-parallel` records the value, its standard error, the offset,
the method and the source in the header (`host_r_parallel_*`). Captures
recorded before 2026-11-08 have no `host_r_parallel_offset_ma`, and only
`V / R_p` is subtracted from them; `annotate --force` with the calibration
file brings them up to date. `annotate` adds the
same record to a capture taken without it. `extract`, `model` and `plot`
apply the recorded R_p by default; `--r-parallel` on them overrides it, and
`none` turns it off. Whenever one is applied, the auto-fit is printed beside
it as a cross-check. The model card and the plot name R_p and its source.
The series-drop diagnostic keeps using the total current, because R_p's
current drops across R_iso like the device's does.

**What it costs.** The subtraction's error is `V · σ_R / R_p²`: a fixed
current at a given voltage, so it matters most at the smallest device
currents. At 0.5% of 470 Ω and 0.6 V it is 6 µA. That is 3% of 0.2 mA,
which is where the diode fit's floor already sits (5 current LSB). On the
simulator a step 14 calibration fits R_p within 0.1%, and the diode
(n = 1.75, I_S = 2.5 nA, R_s = 0.6 Ω, with 470 Ω beside it) comes back as
n = 1.751, I_S = 2.52 nA, R_s = 0.601 Ω. Without the subtraction the
same capture reads n = 7.4 (`tests/test_parallel.py`).

---

## The zero on its own: `--zero`

An R_p calibration carries the instrument's current zero as its offset
(−0.087 mA on board 2). A stabiliser that draws no DC, such as 100 nF alone
(MVP card section E), leaves no line to fit, so `extract`, `model`,
`plot`, `simulate` and `overlay` take the zero directly:

```sh
python -m ct_host extract h4/d.csv --zero -0.0874                          # a value, mA
python -m ct_host extract h4/d.csv --zero h4/z_0v2.csv,h4/z_1v.csv,h4/z_6v.csv  # holds' mean
python -m ct_host extract h4/d.csv --zero auto                             # own off rows
```

- **A value**: from an earlier session, or the intercept of holds into
  known resistors (card section E (c)).
- **Hold CSVs**: their mean, each file's mean listed, so a shift with node
  voltage shows. A hold drawing more than 1.5 mA is refused, as is one
  taken with an R_p.
- **`auto`**: the capture's own rows at or below 0.3 V, where a 1N4148
  carries ~0.6 µA. One gate step only.
- A `--zero` **replaces** an R_p calibration's offset; the two are never
  both subtracted. `--zero-bracket` varies whichever zero was applied.
- **The channel's floor.** The current channel is single-supply, and board
  2's zero is negative (−0.09 to −0.14 mA). At true zero current it reads
  neither the zero nor 0 counts, but the difference amp's lowest output:
  **0.198 + 0.104 · V mA**, measured 2026-11-13 (`ct_host/channel.py` says
  why). `auto` skips rows within 2 counts of that line, and a hold there is
  refused. Until 2026-11-13 the guard was a fixed 5 counts, below the real
  floor at every voltage. So `auto` took a cap-only diode's floor rows for
  its zero (+0.217 mA) and read n as 1.495. With nothing drawing current,
  use a channel model (below) or a value.

The zero and its source go into the model card, the plot, the overlay's
subtitle and the `simulate` output's header (`like_zero`, with
`like_r_parallel`), as R_p does. `simulate`'s curves depend only on the
capture's voltage range, so the zero changes its header, not its numbers.
The 11-08 overlay drawn with `--zero -0.0873765` matches the published
figure point for point (`tests/test_zero.py`).
On the 11-08 diode, `--r-parallel 201.311 --zero -0.0873765` reproduces the
published n 1.7885, I_S 2.6795 nA and R_s 1.1353 Ω (`tests/test_zero.py`).
`--zero auto` there gives −0.0923 mA and n 1.799, inside the published
bracket.

## The channel model: `channel`, then `--zero FILE`

Board 2's current reading, measured with 0.1% resistors on 2026-11-13, is
`max(floor(V), g·I + b + c·V)`, on a voltage that may read δ low:

```sh
python -m ct_host channel \
    --resistor h4/s3_23a_hold_100r_2v.csv=100 \
    --resistor h4/s3_23b_hold_1k_2v.csv=1000 \
    --resistor h4/s3_23c_hold_1k_6v.csv=1000 \
    --floor h4/s3_22b_hold_0v2.csv,h4/s3_22c_hold_1v.csv,h4/s3_22d_hold_6v.csv \
    --calibration h4/s3_22f_rp.csv -o h4/s3_channel.txt
python -m ct_host extract h4/s3_24_diode.csv --type diode --zero h4/s3_channel.txt
```

- **g, b, c** come from three or more holds into known resistors, using
  their medians. Uncertainties come from 4000 draws over the resistors'
  tolerance (`--tolerance`, default 0.1%, one draw per part) and each
  hold's standard error.
- **The floor** is a line through holds with nothing drawing DC.
- **δ**, a voltage-channel offset, is fitted only with `--calibration`. It
  is chosen so that the R_p line's offset is the same zero as the
  resistors'. On 2026-11-13 the two zeros were 1 LSB apart without it;
  δ = −10.1 mV closes the gap, and so would a curved common-mode term. Both
  solutions are printed. `h4/s3_channel.txt` has δ fitted, and
  `h4/s3_channel_nodelta.txt` doesn't.
- **`--zero FILE`** subtracts b + c·V (at the voltage as read), divides by
  g, and takes δ off the voltage. It flags rows on the floor `floor`: they
  are left out of every fit and drawn grey. Beside an R_p calibration line
  it applies only g and δ, because the line already holds the zero and c,
  measured in place. `--zero-bracket` then varies the line's offset.
- `tests/test_channel.py` plants a channel on the simulator and recovers
  the diode through it. It also checks that 2026-11-13's holds give the
  recorded model, and that the floor matches 2026-11-03's open-load holds.

**R_p's auto-fit on a MOSFET family** assumes the lowest gate step is off.
When that step's line has an offset beyond ±0.5 mA, the step is conducting
and the cross-check is refused, with the reason. On 2026-11-13, 2.45 V
conducted, and the auto-fit had reported R_p −12% with a +4 mA offset.

## From a capture to the overlay

Blueprint §5 item 5 and the end of `device → measurement → model →
simulation`. One command per step, after a capture:

```sh
python -m ct_host model    h4/mvp_17_diode_rp.csv --type diode --name D1N4148_CT -o h4/mvp_17_diode.lib
python -m ct_host simulate h4/mvp_17_diode.lib --like h4/mvp_17_diode_rp.csv -o h4/mvp_17_diode_sim.csv
python -m ct_host overlay  h4/mvp_17_diode_rp.csv h4/mvp_17_diode_sim.csv --save ../media/overlay_diode.png
```

The MOSFET path is the same three commands with `--type mosfet`.

- **`model`** extracts and writes the `.model` card. Its comments carry the
  uncertainties, the fit range, R_p and the source capture. For a diode,
  `--zero-bracket MA MA` refits with the instrument's zero at each value
  and adds the spread in n, I_S and R_s: the systematic, beside the
  statistical errors. `extract` takes the same option.
  For a MOSFET, `--vds-slice V`, `--vgs-range LO HI` and
  `--saturation-margin V` choose the fit window, as on `extract` and with
  the same defaults (the highest V_DS every curve reached; two-pass
  saturation filter; 0.5 V). A Level-1 square law holds only above
  moderate inversion, so on a real part restrict it to the top steps. The
  card's `valid for` line gives the V_GS and I_D span of the points
  actually fitted, read from the fit rather than the arguments, and a
  `WARNING` follows when the V_th fit has one degree of freedom or fewer
  (three steps). With `--vgs-range`, λ is fitted over the same steps, so
  `LAMBDA` and the de-embedded `KP` describe the window `VTO` does; the
  comments list λ's steps. The V_th spread over fit-range choices is drawn
  from inside the window too, and the card says so; with three steps in
  the window no step can be dropped, so only the slice varies. R_DS(on) stays a comment, never in the
  `.model` body, and is marked when its gate step (the top one) is
  outside the window. V_GS is the commanded value: the gate DAC's
  accuracy is unmeasured, and the card says so.
- **`simulate`** runs the card in **ngspice** (batch, `brew install
  ngspice`). A voltage source sits directly across the device, swept over
  the capture's Kelvin-measured range, with the gate at each step's
  commanded V_GS. R_iso, the PTC and the shunt are outside the Kelvin sense
  and so are not in the comparison. The device's own R_s is in the card as
  `RS`, the value the extraction fitted. Blueprint §6 names LTspice; the
  card is plain SPICE and runs unchanged there.
- **`overlay`** draws measured points (R_p subtracted) over the simulated
  curve, linear and semilog for a diode, with residuals underneath. For a
  diode the residual is `V_meas − V_model(I_meas)` in mV; for a MOSFET it
  is `I_meas − I_model(V_meas)` in mA per gate step. Points below the
  extraction's floor are drawn hollow. A ct_sim capture is titled
  `[SIMULATED]`, and so is its legend.

`demo/run.sh` runs the whole path on ct_sim data: an R_p calibration, then
a diode and a 2N7000-like MOSFET, each with 470 Ω beside it. Its outputs are
in `demo/`, and the figures are
[`media/demo_overlay_diode_SIMULATED.png`](../media/demo_overlay_diode_SIMULATED.png)
and [`media/demo_overlay_mosfet_SIMULATED.png`](../media/demo_overlay_mosfet_SIMULATED.png).
They show that the pipeline works. They say nothing about the hardware.

| Simulated device | Fed in | Recovered through R_p, card, ngspice |
|---|---|---|
| Diode | n 1.75, I_S 2.5 nA, R_s 0.6 Ω | n 1.751, I_S 2.52 nA, R_s 0.601 Ω; residual 0.63 mV rms |
| MOSFET | V_th 2.1 V, KP 0.05, λ 0.01 | V_th 2.099 V, KP 0.0499, λ 0.0101; residual ≤ 0.058 mA (1.4 LSB) |

**On the bench (2026-11-08, board 2, measured).** A 1N4148 beside L1:
`h4/mvp_17_diode.lib` gives n 1.789, I_S 2.68 nA, R_s 1.14 Ω, and the
card run back through ngspice overlays the measurement to 0.51 mV rms.
The instrument's zero is uncertain between −0.087 and −0.099 mA, and
`model --zero-bracket -0.087 -0.099` refits at both and writes the spread
into the card's header: n 1.788–1.831, I_S 2.66–3.69 nA, R_s 1.01–1.14 Ω
([`media/overlay_diode_1n4148.png`](../media/overlay_diode_1n4148.png)).
The 2N7000 family is in moderate inversion over range 1's span and a
Level-1 card does not fit it, so none was written
(`docs/characterization.md`).

---

## Uncertainty, and why two numbers are printed

Every fitted quantity is an `Estimate` with a standard error. The x-intercept
error — which is what `V_th` is — propagates the slope/intercept covariance
rather than dividing the intercept error by the slope; ignoring the
correlation understates it, by more than a factor of two on a realistic gate
spread. `tests/test_fit.py` checks the implementation against the independent
inverse-prediction formula.

**But the fit's standard error is not the uncertainty on `V_th`.** Which
points enter the fit moves it more than measurement noise does. So every
extraction also recomputes `V_th` across a grid of plausible fit ranges — slice
voltages and gate-point subsets — and `describe()` prints both:

```
  V_th   = 2.1502 ± 0.0007059 V
           fit standard error   ± 0.0007059 V
           fit-range spread     ± 0.0015714 V (full spread 0.0031428 V over 30 choices)
           fit-range choice dominates: the spread is 4x the fit error, so quote the spread
```

On noiseless simulator data the spread is already ~4× the fit error. On bench
data it should dominate outright. Both numbers appear in the printed report
and in the generated `.model` card, so a reader who does not know to ask still
sees them. `vth_sensitivity()` returns the full table; `extract --sensitivity`
prints it.

### Fit ranges are part of the result

No hidden heuristics. Every fit carries a `FitRange` stating the literal rule,
whether the caller chose it or a default did, how many points were used of how
many available, and one line per dropped point saying why:

```
range   : 6 of 6 points over 2.601 .. 3.601 V (V_GS)  [default]
rule    : highest measured V_DS reached by every curve (common span
          0.000..8.532 V); two-pass: fit all steps with I_D >= 5 current LSB
          to get a provisional V_th = 2.1502 V, then keep steps satisfying
          V_DS >= V_GS - V_th + 0.50 V and refit
```

The two-pass iteration is stated rather than hidden, because it is a real
choice: the saturation filter needs a threshold, and the threshold is what is
being measured.

---

## Subthreshold slope is unavailable on range 1

Deliberately, and the extractor says so instead of returning a number:

```
subthreshold slope
  unavailable: only 0 gate steps below V_th carry non-zero current. Range 1's
  current LSB is 40.3 uA, and subthreshold currents are nanoamps, so they
  quantise to exactly zero. This needs range 3 (blueprint §5)
```

Blueprint §5 claims "subthreshold slope needs the low current range — this is
the measurement that justifies building three ranges instead of one." Three
tests turn that claim into a checked result: that the gate steps below `V_th`
really do read `i_acc == 0`, that the extractor reports unavailable rather
than fitting quantisation noise, and that the reason quotes the actual LSB.

---

## Diode extraction fits R_s jointly, not around it

The windowed semilog fit blueprint §5 describes does not work when `R_s` is
present, because there is no clean boundary — `R_s` bends the curve as soon as
`I·R_s` is an appreciable fraction of `n V_T`, a few milliamps for a 0.6 Ω
bulk resistance. On the simulator with a known `n` = 1.75 that window fit
returns **n = 1.97 at R² = 0.9965**: 13% wrong, and nothing in the output
suggests a problem.

Inverting the diode law instead,

```
V = n·V_T·ln(I/I_S + 1) + I·R_s   ->   V = a·ln(I) + b + c·I
```

(exact wherever `I >> I_S`, true by six decades here) makes it an ordinary
three-parameter least squares with `n = a/V_T`, `I_S = exp(-b/a)` and
`R_s = c`. One solve, no window to choose, every resolvable point used, full
covariance. `test_windowed_fit_is_biased_by_series_resistance` pins the old
failure so it cannot be simplified back.

---

## Provenance

A capture from the simulator must never be mistakable for a bench
measurement. Two independent markers, because either alone can be defeated:

- the simulator names the part `sim-mosfet` / `sim-diode` / `sim-resistor`;
- the host records `# host_source: ct_sim ...` on save, which survives
  `--device 2N7000` overwriting the name.

Generated `.model` cards from simulated data carry a `WARNING` block. Saved
files also get `# host_date` when the firmware reported `date: unset` (a
Nucleo has no RTC time source). All host-added keys are prefixed `host_` and
inserted after the instrument's own header; **no firmware field is ever
rewritten**, and the transcript is otherwise saved byte-for-byte, flagged rows
included.

---

## Known limitations

- **Range 1 only**, matching the firmware. No auto-ranging, no pulsed mode.
- **`R_DS(on)` is biased high by its fit window, deliberately uncorrected.**
  Blueprint §5 defines it as the slope of the linear region, and it is fitted
  over `0 < V_DS <= 0.25·V_ov`. Across that window the triode expression
  `I_D = k(V_ov·V_DS − ½V_DS²)` is still curving, so a straight-line slope
  understates the conductance: on the simulator it reads **14.4 Ω against a
  12.5 Ω small-signal value** (`1/(k·V_ov)` at `V_DS → 0`, with `V_ov` = 1.45 V
  at the top gate step), a **+15%** overestimate. It is consistent rather than
  random — a second sweep at a lower top gate step gave 15.3 Ω against 13.5 Ω,
  the same +14% — so it is bias, not noise, and narrowing the window would
  reduce it at the cost of having only two or three points left to fit.

  The bias is **visible rather than hidden** — `describe()` prints the window
  bounds, the point count and the rule, so the number is always read alongside
  what produced it:

  ```
  R_DS(on) = 14.366 ± 0.31244 ohm
             range   : 5 of 60 points over 0.06125 .. 0.3223 V (V_DS)  [default]
             rule    : highest gate step (V_GS = 3.601 V), 0 < V_DS <= 0.25*V_ov = 0.363 V
  ```

  It is left uncorrected because **`R_DS(on)` is not on the closed-loop path.**
  The validation in blueprint §6 runs on `V_th`, `beta`/`KP` and `lambda` —
  the parameters that go into the `.model` card and therefore into the LTspice
  comparison. `R_DS(on)` is reported for reference and is labelled as such in
  the generated card. Fitting the full triode equation would remove the bias
  and is the right fix if it ever becomes load-bearing; doing it now would add
  a nonlinear solve to serve a number nothing downstream consumes.
- **`I_S` is off by 4–10% on the noiseless simulator** (9% on the fixture),
  from quantisation at the low-current end of the fit, where the lowest
  points sit a few LSB above the floor. With no noise every sample rounds
  the same way, and `I_S = exp(-b/a)` extrapolates that rounding error
  across six decades. The size is set by where the rounding happens to
  fall, not by any current the instrument adds. The Kelvin divider
  correction is not the cause: with the divider's current (0.04 LSB at
  0.7 V) modelled and the subtraction turned off, the error is 10.6%; with
  the subtraction on, 9.3%; with no divider at all, 5.2%, the pre-F-1
  figure. Shifting that current by 0.005 LSB moves the error by 5 points,
  in either direction. With ±0.5 to ±4 counts of dither (`--noise`), the
  error is under 2% with or without the divider. A real ADC's noise
  should supply that dither. Until it is measured, read a simulator
  `I_S` to about ±10%.
- **Only the serial link has run on hardware.** On 2026-10-30 `hold` ran
  against a Nucleo-F303RE over the ST-LINK VCP (macOS), after the transport
  was changed to pace its writes. A single write of 16 bytes or more wedges
  the VCP until a USB replug, so `SerialTransport` writes 8-byte chunks
  5 ms apart (commit `2debc57`). No device has been measured, and every
  figure in this file comes from the simulator.
