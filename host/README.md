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
  adaptive/      adaptive sampling: offline study, closed after phase 1
    devices.py   synthetic devices that depart from the fitted models
    frontend.py  the signal chain in Python, held to ct_sim count for count
    timing.py    serial link, TX ring and round trips
    oracle.py    synthetic device, or a dense CSV as a pool (the bench path)
    noise.py     per-point noise, with the dither condition
    models.py    square law and diode as GP means, with Jacobians
    gp.py        GP with a physical mean and a residual that shows mismatch
    estimate.py  parameters via the unchanged extractors; stopping rule
    acquire.py   uncertainty sampling, EIG on theta, EIG on the extractor's
                 outputs, weighted A; greedy batches; safety filter
    loop.py      the capture loop and the fixed designs it is compared with
    evaluate.py  the study; --from-csv for dense bench sweeps
    report.py    tables and figures from the results file
tests/           183 tests, every one against the simulator
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
implied series resistance against the expected `R_iso + shunt + R_PTC`, taken
from the header's `cal_*` constants, with the failure interpretations from
`firmware/README.md` (shorted Kelvin leads, bad sense connection, extra
contact resistance). Until the board's PTC is measured, `cal_r_ptc_ohm` reads
`unset` and the report says to measure it, quoting the R_PTC the fit implies.
Pass a fresh measurement after a trip with `--r-ptc OHM` (`extract
--diagnostics`) or `r_ptc_ohm=` (`vds_delta_report`, `plot_vds_delta`).

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

## Adaptive sampling (phase 1: offline evaluation only; closed 2026-10-20)

Closed after phase 1: the results below recommend against the firmware
session. The code stays so the work can be resumed if points become
expensive (ranges 2–3, pulsed mode), or if the region of interest is narrow
and unknown in advance. See `docs/adaptive_sampling_plan.md`, *Resuming this
work*.

`ct_host/adaptive/` asks whether the instrument should pick each next point
where it is most informative and stop once the parameters are known well
enough, instead of running a fixed 200-point ramp. The plan, with its open
decisions, is `docs/adaptive_sampling_plan.md`. The results are
`docs/adaptive_sampling.md`, with every table generated in
`docs/adaptive/report.md`. **Nothing here talks to the firmware or changes
the CSV.** The points session it models (`POINTS` / `PT` / `END`) does not
exist on the instrument.

What it does:

- **A GP whose mean is the device model** (square law with λ; the diode's
  `V = a ln I + b + c I`), with a GP on the residual. The residual shows
  where the device departs from the model. The parameter uncertainty is
  computed with the residual included, so mismatch inflates it rather than
  being absorbed silently.
- **Per-point noise** from ADC quantisation done properly: oversampling only
  helps when there is dither. It includes the voltage channel's error,
  carried through the curve's slope, which dominates in triode.
- **Reported parameters come from the existing extractors.** GP posterior
  samples are pushed through `extract_mosfet` / `extract_diode` on the dense
  sweep's own grid, so the adaptive answer estimates exactly what a dense
  capture would. The standard error and fit-range spread are reported in the
  same form as for a dense capture. The extractors are also run on the raw
  points, as a model-free cross-check that can block stopping.
- **Four ways to choose points:** uncertainty sampling, D-optimal / EIG on the
  model's θ, EIG on the extractor's outputs, and weighted A-optimal. They are
  compared against a sparse `SWEEP` (raw, and with the GP) and the dense
  ramp, in batches of k per round trip.
- **The stopping rule** as briefed: every gated parameter's standard error
  and half-spread under target, or the point budget. The stop reason is
  recorded.
- **A timing model that counts the link.** Rendered row and header bytes, the
  firmware's 4 KB TX ring, command uploads, USB latency (assumed 1 ms), and
  host compute measured with the wall clock.

How it is checked: the Python model of the signal chain is held to `ct_sim`
count for count (`test_adaptive_oracle.py`). Every synthetic departure is
tested to move the curve, because of the §11 failure mode. The linearisation
used for design is held to finite differences of the real extractors. The
greedy batch update is held to refitting with the point added.

```sh
python -m ct_host.adaptive.evaluate --out ../docs/adaptive          # the study, ~2 h
python -m ct_host.adaptive.evaluate --quick --out /tmp/adaptive    # a smoke run
python -m ct_host.adaptive.evaluate --timing --out ../docs/adaptive # uncontended compute
# later, with hardware: subsample a dense bench sweep instead of a model
python -m ct_host.adaptive.evaluate --from-csv data/2n7000_dense.csv --kind mosfet \
    --noise-lsb <measured> --out ../docs/adaptive-bench
```

**Result (simulated, 2026-10-20): don't build the firmware session.** A raw
sparse `SWEEP` of 5–6 points per gate step reaches the dense sweep's values
within their stated uncertainty in ~0.2 s, against 4.8 s for the dense
family. No adaptive criterion beats it: host compute is ~0.5 s per round
even uncontended. Worth keeping:

- **The GP estimate.** Its uncertainty is calibrated: 96–98% of estimates
  fall within 2σ of the truth on the control devices, at every noise level.
- **The MOSFET mismatch statistic.** Every departure tested is flagged,
  with a 10% held-out false-positive rate. It does not work for the diode,
  whose law absorbs the departures.
- **What it found about the dense ramp.** Its self-heating biases λ and the
  diode's R_s, and point order moves KP by up to ~18 u.

Full numbers are in `docs/adaptive_sampling.md`. Results are written gzipped
(`results.csv.gz`, `traces.csv.gz`); pandas reads them as they are.

**Verified in simulation only.** The device models, thermal constants, USB
latency and noise floor are assumptions, swept where it matters. Subsampling
a bench file inherits that capture's thermal history, so only a live session
on hardware can test point order. That needs phase 2, which is not built.

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
