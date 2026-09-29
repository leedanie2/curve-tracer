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
  spice.py       .model cards
  plot.py        live family plot, static plots, series-drop diagnostic
  cli.py         python -m ct_host capture | plot | extract | model | ports
tests/           119 tests, every one against the simulator
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
| `V_th` = 2.15 V | 2.1498 V | 0.2 mV |
| `k` = 0.055 A/V² | `kp_wl` = 0.05493 | 0.1% |
| `λ` = 0.012 /V | 0.01207 | 0.5% |
| diode `n` = 1.75 | 1.7559 | 0.3% |
| diode `I_S` = 2.5 nA | 2.63 nA | 5% |
| diode `R_s` = 0.6 Ω | 0.5948 Ω | 0.9% |

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
commanded 2.052 V  ->  1.921 V at V_GS = 2.6 V    (5.7 mA)
                   ->  0.899 V at V_GS = 3.6 V   (50.1 mA)
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
implied series resistance against the expected 23 Ω, with the failure
interpretations from `firmware/README.md` (shorted Kelvin leads, bad sense
connection, extra contact resistance).

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
  V_th   = 2.1498 ± 0.00032106 V
           fit standard error   ± 0.00032106 V
           fit-range spread     ± 0.00088074 V (full spread 0.0017615 V over 30 choices)
           fit-range choice dominates: the spread is 5x the fit error, so quote the spread
```

On noiseless simulator data the spread is already ~5× the fit error. On bench
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
          to get a provisional V_th = 2.1498 V, then keep steps satisfying
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
  R_DS(on) = 14.366 ± 0.31241 ohm
             range   : 5 of 60 points over 0.06125 .. 0.3223 V (V_DS)  [default]
             rule    : highest gate step (V_GS = 3.601 V), 0 < V_DS <= 0.25*V_ov
  ```

  It is left uncorrected because **`R_DS(on)` is not on the closed-loop path.**
  The validation in blueprint §6 runs on `V_th`, `beta`/`KP` and `lambda` —
  the parameters that go into the `.model` card and therefore into the LTspice
  comparison. `R_DS(on)` is reported for reference and is labelled as such in
  the generated card. Fitting the full triode equation would remove the bias
  and is the right fix if it ever becomes load-bearing; doing it now would add
  a nonlinear solve to serve a number nothing downstream consumes.
- **`I_S` carries a few percent bias** from quantisation at the low-current
  end of the fit, where the lowest points sit near the ADC LSB.
- **Overlay comparison against LTspice** (blueprint §5 item 5) is not
  implemented.
- **Nothing here has been run against hardware.** Every figure in this file
  comes from the simulator. The serial transport in particular has never
  opened a real port.
