# Adaptive sampling: phase 1 results (offline, simulated)

**Status: closed after phase 1, 2026-10-20.** These results recommend
against building the firmware session, and the work stopped there. When to
revisit, and how, is in `docs/adaptive_sampling_plan.md`, *Resuming this
work*.

**Every figure in this file is a simulation result.** It comes from
`docs/adaptive/report.md`, which `host/ct_host/adaptive/report.py` generated
from `docs/adaptive/results.csv`: the run of 2026-10-20 00:04, 510 tasks,
6,120 rows, no errors. Figures are quoted from that report, not retyped from
memory. If the study is re-run, re-check this file against the new report
rather than editing numbers by hand. The plan, its open decisions and the
deviations from it are in `docs/adaptive_sampling_plan.md`.

**Nothing here has run on hardware.** The device models, thermal constants,
noise floor and USB latency are assumptions (plan §4.2–4.3). Targets are the
provisional ones from plan Q1: V_th 2 mV, KP 2%, λ 20%, diode n 1%, I_S 10%,
R_s 10%.

---

## The answer

**Do not build the firmware points session (phase 2).** The plan's gate
(§4.6) fails on its decisive criterion for every device: adaptive selection
never beats the best option that needs no firmware change. At 0.5 LSB of
noise, a **raw sparse `SWEEP` of 5–6 points per gate step** reaches the
dense sweep's values within their stated uncertainty in **0.20–0.22 s**, on
`sim-sq`, `sim-theta`, `sim-rsd`, `sim-tail` and `sim-real`. The dense family
takes **4.82 s**. The fastest adaptive method on each mismatched MOSFET took
**0.53–7.92 s** (gate table).

The reason is host compute, not the instrument. One adaptive round costs about
**0.52 s** of host computation uncontended (`--timing`: 0.519 s per round on
`sim-theta`, 0.523 s on `sim-real`). A batch of 8 points costs about 0.06 s
of instrument time. A ramp point costs about 4 ms. The plan's prior
expectation (§0) holds, and the measured compute is worse than the 20–200 ms
per round it assumed.

**Three things from this work are worth keeping, and none needs firmware:**

1. **The GP estimate with calibrated uncertainty.** On the control devices, at
   every noise level including undithered, 96–98% of GP-based estimates fall
   within 2 stated sigma of the generative truth and 72–79% within 1 sigma
   (nominal 95.4% / 68.3%; M3 calibration table). It works on any capture,
   including today's sparse or dense `SWEEP`.
2. **The mismatch statistic Λ for the MOSFET.** It flags every MOSFET
   departure tested in 100% of held-out runs, down to θ = 0.02 /V and
   R_S = R_D = 0.25 Ω (severity table). Its false-positive rate on the control
   is **0.10**, held out, above the plan's 5% target. **It does not work for
   the diode**: true-positive rate 0.15 (`sim-diode2`) and 0.07
   (`sim-diode-heat`). The diode model absorbs both departures; see below.
3. **What it found about the dense sweep itself.** In this model, the
   200-point ramp's self-heating biases its own λ and the diode's R_s by
   several stated uncertainties. The order points are measured in changes the
   answer by up to 18 stated uncertainties. Both carry over to today's
   `SWEEP`; see *Thermal history*.

---

## Speed (M1, M2)

Medians at noise 0.5 LSB, from the M1–M3 table and the gate table:

| | dense | best raw ramp | best ramp + GP | fastest adaptive |
|---|---|---|---|---|
| `sim-sq` | 4.82 s | 30 pts, 0.20 s | 30 pts, 1.05 s | 30 pts, ~1.2 s (all criteria stop on the seeds) |
| `sim-theta` | 4.82 s | 30 pts, 0.20 s | 33 pts, 1.68 s | `us`: 150 pts, 7.92 s |
| `sim-rsd` | 4.82 s | 33 pts, 0.22 s | 48 pts, 1.42 s | `us`: 38 pts, 0.91 s |
| `sim-tail` | 4.82 s | 30 pts, 0.20 s | 30 pts, 1.41 s | `eig-phi`: 62 pts, 3.29 s |
| `sim-real` | 4.82 s | 30 pts, 0.20 s | 30 pts, 1.26 s | `us`: 30 pts, 0.53 s |
| `sim-heat` | 4.82 s | 240 pts, 1.03 s (2 of 10 seeds) | 240 pts, 2.92 s (2 of 10) | never (see thermal) |

- **The dense family is 3.43 s of serial TX and 1.37 s of measurement** (M2
  table). On the link alone, a ramp point costs ~4 ms.
- **In every adaptive run, compute is most of the wall time.** Across devices
  at this noise, the median `eig-phi` run is 1.229 s of wall time, of which
  0.973 s is compute (M2).
- **Batch size:** larger is better, with no measurable cost from staleness.
  On `sim-theta`, the median time to the dense values falls from 63.41 s at
  k = 2 to 4.12 s at k = 32. Wall time to budget falls from 101.75 s to
  15.79 s. Time is dominated by the number of rounds, and each round is
  mostly compute.
- **Seeds:** 3 per gate instead of 5 reached the dense values on `sim-real`
  at 18 points instead of 30. On `sim-sq` it cost more rounds: 2.84 s against
  1.19 s.

## Stopping (M2)

- **On the control devices, the 30 MOSFET seeds (8 for the diode) already
  meet the provisional targets.** Every criterion stops after round 0 with
  `target_met`. At these targets, no adaptive point is ever chosen on a
  device the model describes.
- **On every mismatched MOSFET, every run spends its 300-point budget.** V_th
  is spread-limited: the extractor's own fit-range choice moves V_th by more
  than 2 mV, so the target cannot be met by measuring more. The dense sweep's
  V_th has the same spread. The linearised standard error met its target at
  the 30 seeds in every case ("rule as briefed" table). A rule that stopped
  when only the spread remained would have stopped at 0.52–1.05 s instead of
  21–39 s. That is a decision about the rule, for you (below).

## Calibration (M3)

Against the generative truth on the control devices (M3 calibration table):

| noise | `sim-sq` within 1σ / 2σ | `sim-diode` within 1σ / 2σ |
|---|---|---|
| 0 (undithered) | 0.77 / 0.97 | 0.72 / 0.96 |
| 0.5 LSB | 0.79 / 0.98 | 0.79 / 0.97 |
| 2 LSB | 0.77 / 0.98 | 0.76 / 0.97 |

The uncertainty is slightly conservative and holds at noise 0. There,
assuming the textbook LSB/√(12·64) would have claimed eight times the
precision (plan F3). On the thermal devices, coverage of the *dense* values
falls to 0.73 (`sim-heat`) and 0.57–0.67 (`sim-diode-heat`). That is because
the dense values are the heated ones (below), not because the uncertainty is
wrong.

## Mismatch (M5): flagged on the MOSFET, absorbed on the diode

| device | Λ median | flagged (held out) | map precision / recall |
|---|---|---|---|
| `sim-sq` (control) | −3.04 | 0.10 false positive | — |
| `sim-theta` | 1299.39 | 1.00 | 0.93 / 0.81 |
| `sim-rsd` | 561.77 | 1.00 | 0.68 / 0.74 |
| `sim-heat` | 86.95 | 1.00 | 0.78 / 0.57 |
| `sim-tail` | 680.54 | 1.00 | 0.17 / 1.00 |
| `sim-real` | 908.74 | 1.00 | 0.93 / 0.88 |
| `sim-diode` (control) | −1.20 | 0.08 false positive | — |
| `sim-diode2` | −0.88 | 0.15 | — |
| `sim-diode-heat` | −1.15 | 0.07 | — |

Thresholds: 2.27 (MOSFET) and 0.42 (diode). Each is the 95th percentile of
the control's Λ on even seeds; rates are measured on odd seeds.

- **The MOSFET residual surfaces mismatch rather than hiding it.** The map
  localises θ, R_SD, heating and their combination (precision 0.68–0.93). It
  does not localise the subthreshold tail: it flags 99% of the plane where
  the departure covers 17%. The tail moves the fitted V_th, and that leaves
  residual everywhere.
- **The diode residual absorbs both mismatches.** Even at 10× the default
  recombination current, Λ stays at the control's level (severity table, flag
  rate 0.00). `V = a·ln I + b + c·I` bends to fit a second ideality
  component, and heating. The departure from the best fit to the noiseless
  truth is below 1 LSB everywhere (true mismatch fraction 0.00). **This is
  the dangerous case:** self-heating shows up in the diode as a biased R_s
  with nothing left over to flag it.

## Thermal history (M6)

*The thermal network is an assumption* (TO-92: 312.5 K/W split across four
poles; DO-35: 350 K/W). The directions below are robust to scaling it ×0.5
and ×2 (thermal-scale table). The magnitudes are not measurements. Medians at
0.5 LSB:

| | `sim-heat` energy | `sim-heat` peak T_j | `sim-heat` λ, (est − isothermal)/u | `sim-diode-heat` R_s, (est − isothermal)/u |
|---|---|---|---|---|
| dense ramp | 329.36 mJ | 335.92 K | 3.14 | −7.47 (R_s 0.50 Ω) |
| raw ramp, 24/gate | 27.80 mJ | 317.76 K | 4.73 | −1.98 |
| raw ramp, 8/gate | 3.71 mJ | 307.64 K | 1.71 | −1.15 |
| `eig-phi` | 2.39 mJ | 305.58 K | 1.32 | −0.91 (R_s 0.62 Ω) |

- **The dense sweep heats the part ~36 K and reads a different device.** Its
  λ is 3.1 u from the isothermal value. Its diode R_s reads 0.50 Ω against a
  device near 0.6 Ω, −7.5 u. Designs that take fewer points run cooler and
  read closer to isothermal. That is because they measure less, not because
  of how they choose points (`us` and `eig-phi` are indistinguishable here).
- **Point order changes the answer, not just the temperature.** With the same
  part measured three ways (forced to a 150-point budget, paired by seed), on
  `sim-heat`:
  - interleaving high and low power moves V_th by a median −10.47 u, KP by
    −17.62 u and λ by −4.91 u, relative to measuring in sorted (ascending)
    order;
  - acquisition order moves them by −7.53 u, −11.95 u and −4.06 u.

  The sorted order also dissipates the least: 16.29 mJ against 23.43–24.38 mJ.
  On `sim-real`, interleaving moves KP by −10.38 u. On the diode the effect is
  ~1–2 u. Sorted ascending was the plan's default; this is the evidence for
  it.
- **The dense ramp's dwell time changes mid-sweep** (plan F4, held by
  `test_dense_sweep_dwell_changes_when_the_tx_ring_fills`). The model gives
  3.70 ms median dwell for the dense ramp against 1.14 ms for the sparse
  designs.

## Reconstruction (M4) and safety (M7)

- **Curves are reconstructed to a small fraction of an LSB on the control and
  on the non-thermal mismatched devices** (RMSE 0.02–0.04 LSB on `sim-sq` and
  `sim-theta`; ≤ 0.71 on `sim-rsd`). The 95% band holds 0.89–1.00 of the
  truth. On the heating devices, the GP reconstructs the *cooler* curve it
  measured: 7 LSB from the dense ramp's heated curve, but 1.3 LSB from the
  isothermal one.
- **No adaptive run in the study tripped the current limit.** Against a limit
  set to 1.05× each part's own peak, the advisory filter refused ~228–238
  candidates per round, again with no trips. The highest current measured was
  0.95–0.96 of the limit: the seed at each curve's peak, which the filter
  does not see. A MOSFET's seeds include every curve's maximum. So a limit
  below the part's peak trips on the seeds and ends the session, just as it
  aborts a dense `SWEEP`.

---

## What this changes, and what is yours to decide

1. **Phase 2 (firmware points session): recommend not building it.** The gate
   fails on criterion 2 for every device. Q4–Q6 (schema, jump safety, timing)
   become moot unless you want it for another reason. One candidate reason:
   the B1 point-order experiment on the bench needs arbitrary point order,
   which `SWEEP` cannot do.
2. **The GP estimate and Λ could go into `extract` as an option on any
   capture.** That is host-only, and a separate change I have not made. The
   diode Λ should not be offered as a check, because it does not work.
3. **The stopping rule.** As briefed, it spends the whole budget whenever a
   parameter is spread-limited. A spread-aware rule ("stderr under target and
   only spread left") would stop at the seeds on every device tested here.
4. **The targets (Q1).** At the provisional targets, 30 seed points suffice on
   every device the model describes. They are loose against the dense
   sweep's own uncertainty: the adaptive runs on `sim-sq` meet target, but
   reach the dense *values* only 30–70% of the time.
5. **Self-heating in the dense `SWEEP`.** If the bench confirms even part of
   the modelled effect (B1, B3), the cheapest fix is the one this study points
   at: fewer points per ramp, ascending order, and §4's `settle_us` alone
   between points, with no ring-full dwell. That is a firmware or default
   change for you to weigh, not something this phase does.

## Verified, and not

| Claim | Status |
|---|---|
| Python signal chain equals `ct_sim` | verified: 2,219 of 2,220 rows count for count; the other differs by one code per sample at a float32 rounding tie |
| GP, estimator, acquisition, stopping, mismatch | verified in simulation (`host/tests/test_adaptive_*.py`; this study) |
| Thermal effects | modelled with assumed constants; bench test B1 needed |
| Noise floor, USB/VCP latency | assumed (0, 0.5, 2 LSB; 1 ms per direction); B3, B2 |
| Host compute | measured on this machine: 0.52 s per round uncontended, ~1.0–1.1 s with 7 workers |
| Anything on hardware | **nothing**; the boards arrive 2026-10-21 |
