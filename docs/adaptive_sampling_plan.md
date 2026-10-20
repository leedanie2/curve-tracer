# Adaptive sampling: plan, and why it stopped after phase 1

**Status: closed after phase 1, 2026-10-20.** Phase 1 (offline, host only:
`host/ct_host/adaptive/` and its tests) was built and evaluated. It
recommends against phase 2, and the work was closed there. Results are in
`docs/adaptive_sampling.md`. Nothing was built into the firmware; the CSV
contract and the existing extractors are unchanged. This file is kept so the
work can be resumed; [*Resuming*](#resuming-this-work) says when and how.

## Resuming this work

**Why it stopped.** In simulation, adaptive point selection never reduced
the number of points needed below a sparse *uniform* `SWEEP` of 5–6 points
per gate step. At best it tied (30 points against 30); usually it needed
more. That ramp reaches the dense sweep's values within their stated
uncertainty in ~0.2 s, against 4.8 s for the dense family. The adaptive loop
also pays ~0.5 s of host computation per round. Since selection bought no
points, faster computation would only have produced a tie. The extractors
need only coarse coverage of each curve, and a short uniform ramp already
provides it. Full figures: `docs/adaptive_sampling.md`.

**Revisit only if one of these becomes true:**

1. **Points become expensive**, so computation stops dominating: current
   ranges 2–3 (long settling, heavy oversampling) or pulsed mode (~10 ms
   off-time per point). Per point, adaptive costs about
   `0.5 s / k + t_point` against `t_point` for a ramp. It pays only if
   selection cuts the point count by more than that ratio.
2. **The region that matters is narrow and not known in advance**, so a
   uniform grid wastes most of its points. Examples: subthreshold slope on
   range 3, locating a breakdown knee, or choosing the gate-step list
   (`vgs_list`) for an unknown part, which is set by hand today.

**How to restart.**

- `python -m ct_host.adaptive.evaluate --quick --out /tmp/a` is a 1-minute
  smoke run. The full study is ~50 min on 7 workers (`--reps 10 --workers 7`).
  `--timing` measures uncontended host compute. `--from-csv FILE --kind mosfet`
  runs the same study on a dense bench capture.
- Instrument cost is in `adaptive/timing.py` (`LinkModel`) and
  `adaptive/frontend.py` (`FrontEnd.settle_us`, `oversample_n`, `shunt`).
  For range 2/3 or pulsed mode, change those and re-run before writing any
  new method. Condition 1 is a question about those numbers.
- Devices are in `adaptive/devices.py`. Every new departure needs a
  "moves the curve" test (`test_adaptive_oracle.py`), per blueprint §11.
- Designs are compared in `evaluate.py` (`plan()`). A new criterion goes in
  `acquire.py` (`CRITERIA`, `select`). Greedy batches are exact there,
  because the posterior covariances do not depend on unmeasured values.
- Quote numbers only from the generated `docs/adaptive/report.md`, and
  re-run rather than edit figures.

**Known weaknesses, measured:**

- The diode's mismatch statistic does not work (true positives 0.15 and
  0.07), because the diode law absorbs the departures.
- The MOSFET false-positive rate is 0.10 held out, against a 5% target.
- The residual map does not localise the subthreshold tail (precision 0.17).
- Host compute is ~0.5 s per round; the Matérn kernel and the extractor
  calls dominate.
- The stopping rule as briefed spends the whole budget when a parameter is
  spread-limited.

**Not built:**

- the firmware points session (§5.2);
- the mismatch mapping budget (§3.7);
- adaptive choice of `vgs_list`;
- range-2/3 front-end constants beyond the shunt.

**Decisions left open, moot unless this resumes:**

- Q1 targets, which are still provisional;
- Q2: whether to move the fit-range spreads into `extract/*.py`;
- Q3–Q6;
- the stopping rule;
- whether to offer the GP estimate and the MOSFET Λ in `extract`.

**Q7 stays open regardless.** The blueprint and firmware README say
5.5 ms per row; rendered rows are ~46 B, so ~4.0 ms. This work does not
depend on it.

**Still worth doing at bring-up, whatever happens to adaptive sampling.**
Blueprint §7 tests B1–B3, which confirm or refute the modelled self-heating
and point-order effects on the bench.

## Deviations from the plan, as implemented

The text from §0 onward is the plan as proposed. Where the implementation
departed from it, the reason is recorded here rather than by rewriting the
plan:

- **Q1 targets** are the recommended values, labelled PROVISIONAL in every
  output. The report also gives points and time to target as data, so the
  targets can be chosen afterwards.
- **Q2 spreads** for β, KP, λ and the diode are computed in the adaptive
  layer, by re-running the unchanged extractors over a grid of fit-range
  choices (slice × saturation margin; diode current window). `extract/*.py`,
  `describe()` and the `.model` cards are untouched. The same grid is
  applied to the dense reference, so the two are compared like for like.
- **F2 corrected:** the header is 30 lines and 741 B, not 33 lines and
  802 B. The first figure counted the SET replies. It is held by a test
  (`test_rendered_header_is_ct_sims`).
- **GP inputs use the exact DAC gate voltage, not `vgs_set_v`.** The CSV's
  1 mV rounding of V_GS moves V_ov by up to 0.5 mV, which is 1–2 LSB at the top
  step. That made the *control* device look mismatched (Λ = 147–520) until
  it was fixed. Held by `test_exact_gate_voltage_not_the_csv_rounding`.
- **`sim-tail` is smooth inversion, not EKV.** The first EKV form was
  normalised to match square-law saturation, which made triode conductance
  n× higher everywhere: a different device, not a tail. The tail now
  departs only within ~0.2 V of V_th. The gate list moved to 2.3–3.3 V so
  one step sits there, and the top step stays below the safety filter
  (~40 mA against 0.9 × 60 mA).
- **The pointwise mismatch map is conditional on θ̂.** The marginal residual
  sd includes θ's uncertainty, which on a mismatched device is large exactly
  where the residual is. A pointwise test then flagged nothing on `sim-theta`
  while Λ was ~2000. This is the identifiability problem, observed directly.
  Λ remains the detector; the map shows where the residual had to add
  structure beyond the fitted model, by more than 3 sd and more than 1 LSB.
- **The stopping check is staged** (mean → spread → linearised stderr →
  64-sample stderr + raw cross-check) because host compute dominated: the
  first version spent ~1.2 s per round. The rule itself is unchanged and is
  decided only on the full check.
- **λ's linearisation includes the derivative of the extractor's
  inverse-variance weights.** Without it, λ's linearisation was 10× wrong on
  mismatched devices. With it, it matches finite differences of the real
  extractor to ≤ 0.13%.
- **Dropped test:** "posterior sd within 1.5× of the OLS stderr on dense
  data". The two measure different things: the GP propagates the noise
  model through all the points, while OLS uses the scatter of six slice
  values. Coverage (M3) is the test that matters, and it is in the study.
- **Not implemented:** the mismatch *mapping budget* (§3.7, extra points in
  a flagged region). It would confound points-to-target. The map and Λ are
  reported without it.
- **The flag threshold is held out.** It comes from even seeds of the
  control device; flag rates are measured on odd seeds, so the false-positive
  rate is not 5% by construction.
- **The gate's criterion 2** compares against the best option that needs no
  firmware change: the faster of a raw sparse ramp and a sparse ramp + GP.

Scope: range 1, the MOSFET family and the diode, DC only. Everything is
built and tested against `firmware/build/ct_sim` and Python synthetic devices
before hardware exists (boards due Wed Oct 21; bench blocked since
2026-09-24).

---

## 0. Summary

**Method.** A Gaussian process whose mean is the parametric device model
(square law with λ; diode `V = n V_T ln I + b + R_s I`) and whose residual GP
shows where the device departs from that model. The noise is
heteroscedastic, modelled from ADC quantisation (with the dither condition
handled correctly), a noise floor, and voltage-channel error carried through
the curve's slope. Points are chosen in batches by one of three Bayesian
criteria. They are compared against a sparse ramp and the dense ramp.

**The reported parameters come from the existing extractors, not from the
GP's θ.** Each GP posterior sample is turned into a synthetic dense sweep on
the dense sweep's own grid, and `extract_mosfet` / `extract_diode` runs on
it. The adaptive result therefore estimates exactly what the dense sweep
estimates, and reports a standard error and a fit-range spread in the same
form (§3.4). That matters because of finding F6 below.

**Host-driven, as you expected.** The firmware needs one new capability, a
"measure this list" session. It is built only if the offline results pass a
gate (§4.6).

**My prior expectation, stated so the evaluation can prove it wrong.** On
range 1 the dense family is already fast, about 4.9 s for 6 × 200 points. A
sparse ramp of 20 points per gate step costs about 0.55 s with no round trips
(F11). Adaptive selection pays about 9–32 ms per point once round trips and
host compute are counted, against 4.0 ms per point for a ramp. That is an
estimate at k = 8, assuming 20–200 ms of host compute per round, which phase 1
measures. So it can
win on wall time only if it needs 3–8× fewer points than a sparse ramp at the
same accuracy. I think the larger and more certain value is in the GP
machinery: reconstruction, honest uncertainty, the stopping rule and the
mismatch flag. That machinery works on **any** design, including today's
`SWEEP` with a small `n`. The evaluation is built as a factorial so it can
separate the two effects (§4.4).

**Decisions I need from you are in §8.** The two that block phase 1 are the
stopping targets and whether to give β, λ and the diode parameters a
fit-range spread (today only `V_th` has one).

---

## 1. What the reading turned up

Each of these changes the plan. Figures marked *measured* were taken today
from `ct_sim` output. Figures marked *scratch* come from a throwaway script
with stated assumptions; they motivate the work and are not results.

| # | Finding | Consequence |
|---|---|---|
| F1 | **Only `V_th` has a fit-range spread.** `vth_sensitivity()` is the only sensitivity grid. β, KP and R_DS(on) carry an OLS standard error only. λ carries `max(fit error, between-curve scatter)`. The diode's `n`, `I_S` and `R_s` carry a standard error only (by design: "no window to choose"). | The brief asks the stopping rule to test both numbers for every reported parameter. Today that is possible only for `V_th`. Decision Q2. |
| F2 | **A row is ~46 bytes, not ~64.** *Measured*, 6 × 200 family: mean 46.0 B, max 50 B including CRLF, so **4.0 ms/row** at 115200 8N1, not 5.5 ms. The header is **30 lines including the column line, 741 B, 64 ms**, the cost of ~16 rows. *(Corrected 2026-10-19: the first draft said 33 lines / 802 B / 70 ms, which wrongly counted the three `# ok:` replies to the SET commands.)* | Blueprint §4 and the firmware README *Timing* quote 5.5 ms. The cost model uses rendered byte counts, not a constant. A header per batch would be expensive, which shapes the protocol (§5.2). I have not edited the 5.5 ms figure; see Q7. |
| F3 | **Oversampling reduces quantisation error only when there is dither.** With noise ≪ 1 LSB, all 64 conversions round to the same code. The mean is then off by up to ±½ LSB, and that error is deterministic in the true value, not reduced by √64. `ct_sim`'s default is `--noise 0`, which is exactly this case. | The noise model in §3.1 uses the dithered-quantiser result, which goes smoothly from "LSB/√12, not reduced" to "LSB/√(12N)". Treating it as LSB/√(12·64) on undithered data would claim 8× more precision than exists. |
| F4 | **The dense ramp's own dwell time changes partway through.** The 4 KB TX ring absorbs the header and then the rows, and it fills at **point ~100** (*scratch* timing model). After that, dwell per point goes from **1.14 ms to 3.99 ms**. In a 200-point family that is the middle of the first gate step. | The dense sweep does not have one uniform thermal history either. The reference curve's history has to be modelled, and on the bench it has to be timestamped (§5.2). |
| F5 | **Self-heating is first-order on range 1.** *Scratch*: V_GS = 3.6 V, 200-point ramp, 2N7000 R_thJA = 312.5 K/W (derived from its 400 mW / 150 °C rating; to be confirmed against the datasheet) with an **assumed** four-pole Foster split. The worst current error against an isothermal curve is **1.1 / 1.9 / 3.1 mA = 27 / 47 / 77 LSB** at 0.5× / 1× / 2× R_th. | The thermal comparison will not come out null. Point order is a real variable, so it is evaluated (§4.4, M6) and recorded (§5.2). |
| F6 | **When the model is wrong, the extractor's answer depends on where the points are.** The `√I` slice fit, the per-curve λ line, the R_DS(on) window (whose known +15% bias depends on point placement inside it), and the diode OLS all weight the data by point density. On a device the model cannot describe, a sparse design and the dense design converge to **different** values however many points are taken. | Running the extractors directly on adaptive points cannot in general reach the dense values. That is why the primary estimator is the pushforward (§3.4). Raw-point extraction is kept as a model-free cross-check. |
| F7 | **Arbitrary jumps remove a mitigation that §3.6 relies on.** §3.6 lists "a finer step so no single step is a large jump" as the protection for fragile parts. A ramp trips at the first point just over `i_limit_ma`. An adaptive jump can land anywhere up to the analog limiter's 75.2 mA, for one measurement interval (~1.14 ms). | The host safety filter (§3.6) is advisory only. An optional firmware approach ramp is a decision for you (Q5). |
| F8 | **In triode, voltage-channel quantisation dominates the current error.** At the top step, `1/(k V_ov)` = 12.5 Ω. Then σ_V = 3.22 mV/√12 = 0.93 mV maps to **74 µA ≈ 1.8 LSB**, against the current channel's own 11.6 µA (0.29 LSB), undithered. | The noise model propagates input noise through the slope (§3.1). Without that it would understate triode noise 6.5× in σ, which is about 40× in weight. |
| F9 | The command line is capped at 160 characters (`CT_CMD_LINE_MAX`). | About 20 points fit on one line. Larger batches are sent as several pipelined lines (§5.2). |
| F10 | `ct_sim`'s MOSFET is discontinuous at `V_GS = V_th`: the subthreshold branch gives `k·V_T²` ≈ 37 µA ≈ 0.9 LSB, and the square law gives 0. | Harmless today. The Python twin of `ct_sim` reproduces it (for the bit-exact test), and the "subthreshold tail" device replaces it with a smooth form. |
| F11 | **The dense family is already fast.** *Measured* bytes: 6 × 200 rows plus header take **4.86 s** of TX. A 20-point-per-step ramp takes about **0.55 s**. | This is the bar adaptive selection has to clear. See §0. |
| F12 | The host suite has **135** tests, not the 119 in `host/README.md`. Baseline today: 230 C checks, 135 host and 16 contract tests, all passing. | Phase 3 corrects the count. |

---

## 2. Architecture: host-driven selection

**Recommendation: the host proposes points and the firmware measures a
supplied list.** Reasons, with numbers:

- **Memory and arithmetic.** A GP over n observed points needs an n × n
  Cholesky factor in double precision. At n = 300 that is 720 KB. The F303RE
  has 64 KB SRAM plus 16 KB CCM. In float32 the kernel matrices are
  ill-conditioned (they need jitter and lose the small variances the stopping
  rule depends on). Hyperparameter optimisation and posterior sampling are
  out of reach.
- **Verifiability.** None of the firmware can run on hardware before Oct 21,
  and bring-up will run on this firmware. Keeping the firmware change small
  (a list measurer that reuses the sweep's limit ordering) keeps the untested
  surface small. The host side can be tested completely now.
- **Safety stays where it is.** Firmware still measures, checks `i_limit_ma`
  against the **measured** current before emitting, and zeroes the drain DAC
  first. Who chose the point does not matter to that path.
- **Round trips are the cost, so they are counted and amortised.** One round
  trip with k = 8 costs about 6 ms of command upload, 9 ms of measurement,
  38 ms of row TX and about 2 ms of assumed USB/VCP latency, plus host compute
  (to be measured). Batching spreads the fixed part across k points. §4.4
  measures the trade-off as a function of k.
- **Firmware-side selection would only save the round-trip overhead.** That
  is a few tens of ms per round. Both designs pay the 4 ms per row of TX.

**Fallback that needs no firmware change**, should selection help but the
firmware change not earn its keep: host-chosen ramps, i.e. per-gate `SWEEP`s
with chosen `n` and `vds_max`. They keep a monotonic thermal history, at
64 ms of header per call. This is evaluated only if phase 1 points that way.

---

## 3. Method and mathematics

Notation: `x = (V_GS, V)` with `V` the **measured** `V_DS` (never
`vds_set_v`), `y` = DUT current in mA, Δ_I = 40.29 µA and Δ_V = 3.223 mV the
range-1 current and voltage LSBs, N = `oversample_n`.

### 3.1 Heteroscedastic noise model

For one channel with additive noise σ_n (rms, counts) ahead of the quantiser,
the oversampled mean has error variance

```
σ²_mean = σ_n²/N + (Δ²/12) · [ ρ(σ_n/Δ) + (1 − ρ(σ_n/Δ))/N ]

ρ(s) = Σ_{k≥1} (6/(π²k²)) · exp(−4π²k² s²)        ρ(0) = 1,  ρ(0.25) ≈ 0.05
```

`ρ` is the share of quantisation error that does not average out: its
signal-dependent mean (Widrow & Kollár). With no noise (`ρ = 1`) the error is
`Δ/√12` whatever N is. Once σ_n ≳ 0.3 LSB, `ρ → 0` and the familiar
`Δ²/(12N)` returns. That non-averaging part is a deterministic sawtooth in
the true value, which looks independent across points at different currents.
It is therefore modelled as independent noise, with that interpretation
stated.

The voltage channel's error enters through the curve's slope (first-order
noisy-input GP, McHutchon & Rasmussen 2011):

```
σ_i² = σ²_mean,I + (∂I/∂V |_{x_i})² · σ²_mean,V
```

∂I/∂V comes from the current posterior mean, refreshed each round. σ_n per
channel is an input. Before the bench it is set from the simulator's noise
setting. On the bench it comes from the §7 noise-floor test (1000 samples at
a fixed bias), which this work makes load-bearing. Gain error is systematic,
so it is not in σ_i. It belongs to calibration (`recompute.py`).

### 3.2 GP with a parametric mean

**MOSFET.** The mean is the square law with λ, in the extractor's convention
`I = β V_ov²(1+λV)` (saturation) and `β(2 V_ov V − V²)(1+λV)` (triode),
θ = (V_th, β, λ). The residual δ is a GP:

```
y_i = m(x_i; θ) + δ(x_i) + ε_i,     ε_i ~ N(0, σ_i²)
δ ~ GP(0, k_ψ),   k_ψ(x,x') = [σ_rel² m̂(x) m̂(x') + σ_abs²] · k_M52(x,x'; ℓ_GS, ℓ_DS)
```

The `σ_rel` term scales the discrepancy with current, because θ-degradation,
heating and series resistance all depart roughly in proportion to I. The
`σ_abs` term covers departures where `m → 0`, such as a subthreshold tail.
Matérn-5/2 rather than squared-exponential, because a mismatched device puts
a kink at a different knee position than the mean does.

m is nonlinear in θ, so it is linearised at the current estimate θ̂,
`m(x;θ) ≈ m̂(x) + J(x)(θ − θ̂)`. This makes it a GP with explicit basis
functions (Rasmussen & Williams §2.7). With `C = K_ψ + diag(σ²)` and a vague
prior on θ:

```
Σ_θ = (Jᵀ C⁻¹ J)⁻¹                         θ̄ = θ̂ + Σ_θ Jᵀ C⁻¹ (y − m̂)       (GLS; iterate θ̂ ← θ̄, Gauss–Newton)
μ(x*) = m̂* + J*(θ̄−θ̂) + k*ᵀ C⁻¹ (y − m̂ − J(θ̄−θ̂))
Var(x*) = k** − k*ᵀ C⁻¹ k* + r*ᵀ Σ_θ r*,    r* = J*ᵀ − Jᵀ C⁻¹ k*
```

Σ_θ is computed with the correlated residual included. If the GP could
explain a shape that θ also explains, the parameter uncertainty grows instead
of the discrepancy being silently absorbed into θ. This is the identifiability
problem of model-discrepancy calibration (Kennedy & O'Hagan 2001;
Brynjarsdóttir & O'Hagan 2014). If confounding degrades the θ-based design
criterion, the alternative is an orthogonal discrepancy (Plumlee, JASA 2017);
it is noted here and not planned.

**Diode.** The diode extractor's inverse form is exactly linear in its
parameters. The GP is therefore over `u = ln I`, with `V` as the output:

```
V = a u + b + c eᵘ + δ(u) + ε,   a = n V_T,  I_S = exp(−b/a),  R_s = c
σ_i² = σ²_mean,V + (a + c eᵘⁱ)² · (σ_mean,I / I_i)²
```

No linearisation is needed, so Σ_θ is exact. Points within a few LSB of zero
current get large σ_u and therefore carry little weight. That replaces the
extractor's hard 5-LSB floor with the same idea expressed as a weight.

### 3.3 Hyperparameters

ψ = (σ_rel, σ_abs, ℓ_GS, ℓ_DS) is fitted by MAP-II: the restricted marginal
likelihood, with θ integrated out (R&W §2.7, vague-prior limit), plus weakly informative
log-normal priors. The priors are there because ML-II with 20–40 points
collapses length scales. The noise model is not fitted. It is fixed from the
noise-floor measurement, which keeps the discrepancy from being explained
away as noise. Optimisation uses L-BFGS-B with 3 restarts, refitted every
round, or every r rounds if host compute dominates (measured).

**scipy is justified for this and nothing else:** `scipy.optimize.minimize`
(L-BFGS-B) and `scipy.linalg.cho_factor/cho_solve/solve_triangular`.
Hand-writing a bounded quasi-Newton optimiser in numpy is a correctness risk
with no benefit. scipy 1.13.1 is already in this environment; it would be
added to `host/requirements.txt` as `scipy>=1.10`. **No PyTorch, GPyTorch or
sklearn.** The problem size (≤ ~300 observations, ~1200 grid points) is small
for numpy. sklearn's GP has no explicit-basis mean and no restricted
likelihood. GPyTorch would bring in torch to do what fifty lines of Cholesky
algebra do.

### 3.4 Reported parameters: pushforward through the existing extractors

The estimand is "what `extract_mosfet` (or `extract_diode`) returns on the
dense sweep" (F6). So:

1. Build the dense sweep's own commanded grid: `vgs_list` × the n = 200 ramp
   codes, or whatever dense configuration is being compared against.
2. Draw S = 64 posterior samples of the curve surface on that grid. For each
   commanded point, solve `V = V_set − (f_s(V) + V/R_div)·R̂_ser` for the
   measured coordinate. R̂_ser is the series resistance fitted from the delta
   in the seeds, the same through-origin fit `vds_delta_report` does, so an
   unmeasured PTC is handled. Wrap the result as a `Sweep` whose rows carry
   `i_recomp_ma` / `v_recomp_v`.
3. Run the unchanged extractor on every sample.

Reported, in the existing `Estimate` form, so `describe()` and `spice.py`
work unchanged:

- **value**: the extractor on the posterior-mean sweep;
- **standard error**: the standard deviation over the S samples. This is the
  measurement-limited part. The Monte-Carlo error of the sd is about 9% at
  S = 64;
- **fit-range spread**: the extractor's own sensitivity grid on the
  posterior-mean sweep. This is the procedure-limited part, computed by the
  same code as the dense sweep's;
- **cross-check**: the same extractor run directly on the raw adaptive
  points, with its own standard error and spread, printed alongside. If the
  two disagree by more than 3σ combined, the report flags it and stopping is
  blocked (§3.8). The GP must never be the only path from data to a number.

### 3.5 Acquisition

All three model-based criteria have posterior covariances that do not depend
on the yet-unseen y, given (θ̂, ψ). **Greedy batch selection is therefore
exact sequential selection**, with no fantasised observations needed. The
only cost of batching is that θ̂, ψ and the linearisation go stale for k
points. That is what §4.4 measures against round-trip cost.

- **US: uncertainty sampling** (MacKay 1992). Pick `argmax Var[I(x)|D]` over
  feasible candidates, then rank-one update the variance and repeat k times.
  Expected failure mode, to be measured: it chases the largest-variance
  region, which with the current-scaled kernel is high power, so it heats
  the device most.
- **EIG-θ: Bayesian D-optimal on the model parameters** (Lindley 1956;
  Chaloner & Verdinelli 1995). For one candidate x:

  ```
  EIG(x) = ½ log(1 + r(x)ᵀ Σ_θ r(x) / s²(x)),   r(x) = J(x)ᵀ − Jᵀ C⁻¹ k_x,
                                               s²(x) = k(x,x) − k_xᵀ C⁻¹ k_x + σ²(x)
  ```

  Selection is greedy with rank-one updates of Σ_θ and C. As the residual
  amplitude → 0 this reduces to classical local D-optimality (`J Σ Jᵀ/σ²`).
  **Known risk:** locally D-optimal designs for p parameters tend to collapse
  onto about p support points (Box & Lucas 1959), which are exactly the
  designs blind to model inadequacy (Box & Draper 1959). Two things counter
  this: the discrepancy term in `s²` and `r` (points the GP could explain
  carry less information about θ) and the seeds. The evaluation measures
  whether that is enough.
- **EIG-φ: EIG on the reported parameters.** My addition, and in my view the
  right reading of "Bayesian optimal design on the parameters", because the
  parameters reported and gated are the extractor's φ = (V_th, β, λ, …), not
  the GP's θ. Linearise the extractor about the posterior-mean sweep,
  `φ ≈ φ̂ + G (f_grid − μ_grid)`, and then

  ```
  EIG_φ(B) = ½ log det(G Σ_grid|D Gᵀ) − ½ log det(G Σ_grid|D∪B Gᵀ)
  ```

  Each candidate is a rank-one update of `Σ_grid`. G is sparse. V_th and β
  touch only the two grid points bracketing the slice on each curve; λ
  touches each curve's saturation points; the diode is linear least squares
  and therefore exact. G is derived analytically **and tested against finite
  differences of the real extractor**, so the two cannot drift apart. That
  check exists because of the §11 failure mode. A weighted-A variant,
  `Σ_j Var(φ_j)/t_j²`, is aligned with a per-parameter stopping rule and
  costs nothing extra to evaluate alongside.
- **Batch.** log det is submodular, so greedy batches are within (1 − 1/e)
  of the best batch for the EIG criteria (Krause, Singh & Guestrin 2008).

### 3.6 Candidates, safety filter, ordering

- **Candidates**: `vgs_list` (the same gate steps as the dense sweep, so the
  family structure and slicing still apply) × sweep DAC codes 0..code(vds_max),
  thinned to about 10 mV, which gives ~1000 per gate step. Each candidate is
  mapped to a predicted measured V through R̂_ser. Placement error from a
  wrong R̂_ser costs efficiency, not correctness, because the GP uses the
  measured coordinate.
- **Safety filter (advisory).** Refuse a candidate when
  `μ + 3σ ≥ α · i_limit_ma` (α = 0.9 by default). Every accepted point is
  still measured and limit-checked by firmware, and the filter never stands
  in for that check. With all candidates refused, the run stops with reason
  `no_feasible_points`. The dense reference must be compared on the same
  reachable region, or the difference reported.
- **Order within a batch**: by gate step, then ascending commanded V_DS,
  which is closest to the ramp's thermal history. The alternatives,
  acquisition order and a high/low power interleave, are run in the thermal
  study (M6) so this default is a measured choice.

### 3.7 Mismatch detection

- **Global flag.** `Λ = 2[log p(y|M1) − log p(y|M0)]`, where M0 is the
  parametric model with only a noise-scale factor free and M1 adds the
  residual GP. Fitting a noise scale in M0 makes the test robust to a
  slightly wrong σ_n: only *structured* residual can raise Λ. The null
  distribution sits on a boundary (σ → 0; Self & Liang 1987), so the
  threshold is calibrated by parametric bootstrap on the plain square-law
  device for a 5% false-positive rate.
- **Map.** `z(x) = E[δ(x)|D] / sd[δ(x)|D]` on the grid. Regions with |z| > 3
  are reported as "departs from square law here, by this much".
- **Mapping budget.** When the flag fires, up to M extra points (default 10%
  of the budget) go to uncertainty sampling restricted to the flagged
  region. The report can then show the departure's shape instead of a single
  flag. Those points are labelled as such.

### 3.8 Stopping rule

At the end of each round, stop with reason `target_met` when, for every
gated parameter j:

```
stderr_j ≤ t_j   and   spread_j / 2 ≤ t_j          (spread/2 = the "±" describe() already prints)
```

and the raw-point cross-check agrees within 3σ (§3.4), and every extractor
minimum is met: ≥ 3 curves bracket the slice, ≥ 4 saturation points per
curve for λ, ≥ 4 points in the window on the top step if R_DS(on) is gated.
Otherwise continue, until `budget` (point budget, default ¼ of the dense
count). Other end reasons: `ilimit`, `stopped`, `no_feasible_points`.
The reason is written to the CSV (`# host_stop_reason:`) and to the report.

### 3.9 Seeds

Always measured first, in one batch, as monotonic per-gate ramps. MOSFET:
commanded V_DS at {0.1, 0.25, 0.5, 0.75, 1.0} × `vds_max` on every gate step,
so 5 per step and 30 for a 6-step family. That covers triode, knee and
saturation on every curve and includes the slice endpoint. Diode: 8 points
spread in commanded voltage. Seed count is a factor in the evaluation, at 3
or 5 per step.

---

## 4. Offline evaluation (phase 1, host only)

### 4.1 Oracles: one interface, three back ends

`measure(batch of (gate_index, dac_code)) → rows + timing`

| Oracle | What it is | Used for |
|---|---|---|
| `SyntheticOracle` | Python device + front end (DAC quantisation, `R_iso` + shunt + PTC + divider solve, both ADC channels quantised and oversampled, Gaussian noise) + thermal state + timing model | the whole study |
| `PoolOracle(csv)` | A dense CSV as a candidate pool: a proposal must be a commanded point present in the file, and its row is returned | `ct_sim` dense captures now; **your dense bench sweeps later**, via `--from-csv FILE`, with no rewrite |
| `LiveOracle` | `SimTransport`, later `SerialTransport`, running the §5.2 session | phase 2 only |

**`SyntheticOracle` on `sim-sq` must reproduce `ct_sim` exactly.** With noise
off, it must give the same `i_acc` / `v_acc` for every commanded point,
asserted in a test. That keeps the Python front end from becoming a second
model that drifts from the firmware's.

**What the bench path cannot measure.** Subsampling a dense bench sweep
inherits the dense ramp's thermal history, so `PoolOracle` cannot evaluate
point order. Only a live session on hardware can (bench test B1, §6.4).

### 4.2 Synthetic devices

All named `sim-*`, all saved with `host_source`. Defaults are 2N7000-like
(`V_th` 2.15 V, k = 0.055 A/V², λ = 0.012 /V, the conftest `KNOWN_MOSFET`)
and 1N4148-like for the diode. Every parameter below is assumed, not
measured.

| Device | Departure the fitted model cannot express | Default, swept over |
|---|---|---|
| `sim-sq` | none (control; bit-exact with `ct_sim`) | — |
| `sim-theta` | mobility degradation, `β/(1+θ V_ov)` | θ = 0.2 /V, swept 0.05–0.4 |
| `sim-rsd` | internal source/drain resistance inside the Kelvin sense, solved implicitly | R_S = R_D = 1 Ω, swept 0.5–3 |
| `sim-heat` | Foster thermal network driven by the actual timed power sequence; µ ∝ T^−1.5, `V_th` −3 mV/K | R_thJA 312.5 K/W, swept ×0.5–×2 |
| `sim-tail` | EKV-style smooth inversion (n = 1.5) in place of the square law near threshold | n swept 1.2–1.8 |
| `sim-real` | all four together | — |
| `sim-diode` | none (Shockley + R_s; bit-exact with `ct_sim`) | — |
| `sim-diode2` | recombination component (n = 2) alongside diffusion (n = 1) | ratio swept |
| `sim-diode-heat` | `I_S(T)`, `V_T(T)` on a thermal network (DO-35, R_th assumed) | ×0.5–×2 |

Each mismatch parameter gets a test that sweeping it moves the output. This
is §11's "accepted but not applied" failure mode, which hit this project
twice, applied in advance.

Noise levels: σ_n = 0 (undithered quantisation only, `ct_sim`'s default),
0.5 LSB and 2 LSB, per channel. The bench value replaces these once it is
measured.

### 4.3 Timing model

| Term | Value | Source |
|---|---|---|
| settle + 2 × 64 conversions | 50 µs + 1.092 ms | `ct_config.h`; 614 cycles at 72 MHz |
| TX per byte | 86.8 µs | 115200 8N1 |
| row and header bytes | rendered with the firmware's format | *measured* sizes in F2 |
| TX ring | 4096 B; `emit` blocks when full | `ct_hal_device.c` |
| command upload | bytes × 86.8 µs | — |
| USB/VCP latency | **1 ms per direction, assumed**, sensitivity at 5 and 16 ms | unknown until bring-up; bench test B2 |
| host compute | **measured** wall clock of each round on this machine | — |

Wall time is reported as the sum and as a breakdown: seeds, upload,
measurement, TX, latency, compute.

### 4.4 Methods (factorial)

| Design | Estimator | Why it is there |
|---|---|---|
| dense ramp (n = 200) | existing extractors | the reference |
| sparse ramp, n ∈ {8, 12, 16, 24, 32, 48, 64} per step | existing extractors on raw points | today's cheapest option, **no firmware change** |
| sparse ramp, same n | **GP pushforward + stopping rule** | separates "the GP helps" from "selection helps" |
| US, EIG-θ, EIG-φ (and weighted-A) | GP pushforward | adaptive selection |

The adaptive designs run at batch size k ∈ {1, 4, 8, 16, 32} and seed density
{3, 5} per step. The k sweep is run for the best criterion only, to keep the
compute budget down. Replicates: 10 noise realisations per cell. At
σ_n = 0 the oracle is deterministic, so there the replicates vary the device
parameters within their swept ranges instead.

### 4.5 Metrics

- **M1, points and wall time to reach the dense values.** The first round at
  which every gated parameter is within `u_dense = √(stderr² + (spread/2)²)`
  of the dense sweep's value, and whether it stays there through to the stop.
- **M2, stop outcome.** Points, wall-time breakdown, stop reason.
- **M3, calibration (the condition for trusting the stopping rule).** Coverage
  of the reported ±2σ against the dense values and against the generative
  truth. **A method below 90% coverage is not shipped,** whatever its speed:
  stopping early on understated uncertainty is worse than not stopping.
- **M4, curve reconstruction.** RMSE and max error in LSB against the
  noiseless truth over the reachable domain, plus coverage of the 95% band.
- **M5, mismatch.** False-positive rate on `sim-sq` and `sim-diode`, and
  true-positive rate on each mismatch device. Also whether the |z| > 3 region
  lands where the physics puts it: high V_ov for θ, high current for R_SD,
  high power for heat, V_ov < 0.2 V for the tail. **Whether the residual
  flags the mismatch or absorbs it** is reported per device. Mismatch the
  parametric model can mimic over the sampled region is undetectable in
  principle, and the report says which cases those are.
- **M6, thermal.** On `sim-heat` and `sim-real`: φ under the dense ramp, each
  adaptive method, and each batch ordering, against the isothermal truth.
  Also ∫P dt, peak T_j and per-point dwell. Adaptive batches measure fast and
  then idle at zero drain, which is closer to pulsed operation, so adaptive
  may well read *closer* to isothermal than the dense ramp. Then the dense
  values are the biased ones, and "reach the dense values" stops being the
  right target on those devices. The report shows both comparisons rather
  than choosing one.
- **M7, safety.** Proposals refused, `ilimit` trips, and the largest current
  above `i_limit_ma` reached on a jump.

### 4.6 Gate to phase 2 (firmware): proposed thresholds, yours to change

Build the firmware session only if, at a bench-plausible noise level on the
mismatch devices, the best adaptive method:

1. reaches the dense values in ≤ 50% of the dense wall time, **round trips
   and host compute included**;
2. beats *sparse ramp + GP* at equal accuracy by ≥ 30% in wall time (or by a
   clear margin in device stress, ∫P dt, if that is the argument you want to
   make);
3. has ≥ 90% coverage (M3);
4. keeps the mismatch false-positive rate ≤ 5% and the true-positive rate
   ≥ 80% on the non-tail devices.

If (2) fails, the recommendation is **no firmware change**: ship the GP
pushforward, stopping rule and mismatch flag on top of `SWEEP` with a small
`n`.

### 4.7 Compute and provenance

About 1,400 runs at an estimated 5–10 s each, so 2–4 h, using stdlib
`multiprocessing`. Every results row carries the oracle, device name
(`sim-*`), `host_source`, noise level, seed, code version and timing-model
constants. The report
quotes figures from the results file, never retyped, and labels them as
simulated. If a constant changes later, the figures are re-run or annotated
with what they were taken at, never rescaled.

---

## 5. File-by-file changes

### 5.1 Phase 1: offline, host only (no firmware, protocol or CSV change)

New package `host/ct_host/adaptive/`:

| File | Contents |
|---|---|
| `noise.py` | §3.1: `ρ(s)`, per-point σ for both channels, the slope-propagation term |
| `models.py` | parametric means and Jacobians: square law with λ; diode in `u = ln I` |
| `gp.py` | Matérn-5/2 ARD kernel with current-scaled amplitude; explicit-basis GP (GLS, Gauss–Newton); restricted marginal likelihood; MAP-II via scipy; posterior mean, covariance, sampling; rank-one updates |
| `acquire.py` | US, EIG-θ, EIG-φ, weighted-A; greedy batch; candidate generation through R̂_ser; safety filter; batch ordering |
| `estimate.py` | pushforward (posterior samples → `Sweep` → existing extractors); raw-point cross-check; analytic G with finite-difference verification; mismatch Λ and z-map; stopping rule and reasons |
| `oracle.py` | the `Oracle` protocol; `SyntheticOracle`; `PoolOracle(csv)` |
| `devices.py` | §4.2 devices, with `sim-*` names and provenance strings |
| `timing.py` | §4.3 model, including the TX ring and rendered row bytes |
| `loop.py` | seeds → rounds → stop; returns the transcript-like record and host provenance |
| `evaluate.py` | `python -m ct_host.adaptive.evaluate --devices … --out docs/adaptive/` and `--from-csv FILE` for bench subsampling; writes a results CSV, figures and the report |

Modified, **only if you approve Q2**:

- `extract/mosfet.py`: β's spread from the existing `vth_sensitivity` table
  (slope², de-embedded); λ's spread over a saturation-margin × current-floor
  grid; R_DS(on)'s over a window grid. `describe()` and the `.model` card
  print them, as they already do for `V_th`.
- `extract/diode.py`: spread over a current-floor × upper-cut grid.
- `extract/common.py`: nothing beyond what those need.

Also changed: `dataset.py` gets one helper to build a `Sweep` from arrays
(rows with `i_recomp_ma`/`v_recomp_v`, `recomputed=True`), with no change to
slicing; `host/requirements.txt` gets `scipy>=1.10`.

Report: `docs/adaptive_sampling.md` plus `docs/adaptive/` (results CSV and
figures).

### 5.2 Phase 2: conditional on the §4.6 gate

**Protocol: a points session**, so one header per capture, one `# end:`, and
the transcript is still a single block saved byte for byte:

```
POINTS                     -> full header with "# mode: points", schema 3, column line
PT 0:1024 0:2048 3:512 …   -> measures in the given order; rows; then "# ok: pt=3"
PT …                       -> (lines may be pipelined; each ≤ 160 chars, ~20 points)
END                        -> drain and gate to zero; "# end: ok"
```

- A point is `gate_index:sweep_dac_code`. The code is an integer: exact, no
  float parsing, and the row still reports `vds_set_v`. The gate index points
  into `vgs_list`, which the header already records.
- **The whole line is validated before any DAC write:** gate index <
  `vgs_count`, code ≤ code(`vds_max`), well-formed. Any error rejects the
  line with `! err:` and touches nothing. Setters reject and never clamp,
  and this applies the same rule to a point list.
- **Limit ordering identical to `SWEEP`/`HOLD`:** measure → compare → zero
  the drain DAC → emit the flagged row → `# end: ilimit`, and the session
  closes. Ctrl-C gives `# end: stopped`.
- The drain DAC (and gate) go to zero after every `PT` line, so the device
  idles unbiased between batches. That idle time is part of the thermal
  history and is recorded.
- While a session is open, `SET`/`SWEEP`/`HOLD` are rejected, so parameters
  cannot change mid-capture without a record.
- `# mode: points` is what the firmware did. *Why* is the host's business and
  goes in `host_` keys added at save: `host_design` (`eig-phi`, `us`,
  `ramp-24`…), `host_batch_k`, `host_seed_count`, `host_stop_reason`,
  `host_targets`, `host_adaptive_version`. No firmware field is rewritten.
- Schema 3 columns: see Q4.

Firmware files: `core/ct_points.c/.h` (new engine, structured like
`ct_hold.c`); `core/ct_cmd.c` (verbs and session state); `core/ct_csv.c/.h`
(schema 3, mode, columns); `core/ct_config.h` (`CT_CSV_SCHEMA 3`, limits,
optional `approach_v`); `core/ct_device.h` (`now_us` hook, if Q4 includes a
timestamp); `sim/ct_sim_device.c` (`now_us` from its simulated clock;
optionally `--theta`/`--rsd` for end-to-end realism, each with a moves-the-output
test); `stm32/Core/Src/ct_hal_device.c` (`now_us` from a 32-bit timer,
**unverifiable before the boards**); `Makefile`.

Host files: `csvio.py` (schema 3, per-mode expected columns, schema-2 files
still parse); `protocol.py` (`run_points` session driver: pipelined `PT`
lines, ack accounting, ilimit mid-session); `adaptive/oracle.py`
(`LiveOracle`); `cli.py` (`capture --design … --batch … --budget …`).

### 5.3 Phase 3: documentation

- `firmware/README.md`: contract (schema 3, points mode, columns, end
  reasons, change log), command table, timing (corrected row bytes, if Q7),
  test counts. `ct_csv.h` and the README change in the same commit, per the
  contract.
- `host/README.md`: an adaptive section (estimand, uncertainty, mismatch,
  stopping), the corrected test count, provenance.
- Blueprint: §4 (the points engine and its ordering contract), §5 (adaptive
  extraction and what it reports), §7 (bench tests B1–B3), §11 (jump safety;
  design-dependent estimands under mismatch).
- Every changed section states what was verified in simulation and that
  **none of it has run on hardware**.
- I will not edit the top-level `README.md`, which has uncommitted changes of
  yours, unless you ask.

---

## 6. Test plan

### 6.1 Host, phase 1 (pytest, no instrument)

- **Bit-exact twin**: `SyntheticOracle(sim-sq)` and `SyntheticOracle(sim-diode)`
  give the same `i_acc`/`v_acc` as `ct_sim` at the same commanded points.
- **Parameters wired up**: each mismatch and thermal parameter, swept, moves
  the curve. A zero-valued one reproduces `sim-sq` exactly.
- **Noise model**: `ρ(0) = 1`; σ_mean → Δ/√(12N) for σ_n ≫ Δ; Monte-Carlo
  agreement within 5% at σ_n ∈ {0, 0.1, 0.3, 1} LSB.
- **GP**: hand-computed posterior on a 3-point case; GLS equals OLS when the
  residual amplitude is 0; rank-one updates match full recomputation;
  explicit-basis variance ≥ known-θ variance.
- **Acquisition**: greedy-batch variance equals sequential (y-independence);
  EIG-θ matches a brute-force log det difference; G matches finite
  differences of the real `extract_mosfet` and `extract_diode` to 1e-3;
  every proposal passes the safety filter; refused candidates are never
  proposed.
- **Estimator**: pushforward on dense noiseless `ct_sim` data reproduces the
  dense extraction within its stated uncertainty; posterior sd is within a
  factor of 1.5 of the OLS standard error on dense dithered data
  (σ_n = 2 LSB, where both are noise-limited).
- **Closed loop, small**: on `sim-sq` and `sim-theta`, EIG-φ stops with
  `target_met` within budget, the reason is recorded, and seeds are always
  present.
- **Mismatch**: the bootstrap threshold gives ≤ 10% false positives over 20
  `sim-sq` runs (small-n check; the full figure comes from the study), and
  `sim-theta` at θ = 0.3 is flagged.
- **`PoolOracle`**: rejects proposals not in the pool; runs end-to-end on a
  saved `ct_sim` dense CSV, which is the bench path.
- **Provenance**: every saved artifact carries `sim-*` and `host_source`.
- The existing 135 host tests are unchanged and still pass.

### 6.2 Firmware, phase 2 (C suite in the existing style, `tests/test_points.c`)

Row and field shape; order preserved; **drain DAC zeroed before the flagged
row** (asserted directly, as in `test_sweep.c` and `test_hold.c`); session
closed after ilimit, with a further `PT` rejected; drain zeroed between `PT`
lines; malformed or out-of-range line rejected **with no DAC write**; gate
index validated; `SET` rejected mid-session; Ctrl-C; monotonic `t_us`;
schema-3 header. `test_csv.c` gets the points columns, and
`test_csv_contract.py` gets a points block read by a naive host. **All 230
existing checks are unchanged.**

### 6.3 Host, phase 2 (pytest against `ct_sim`)

Session round trip; pipelined `PT` lines; ilimit mid-session leaves a
complete transcript; schema-2 and schema-3 files both parse; end-to-end
adaptive capture on `ct_sim` via `LiveOracle`, saved and re-extracted.

### 6.4 Bench, after hardware (planned here, not run)

- **B1, thermal ordering A/B.** The same point set measured as a ramp, in
  reverse, interleaved, and batched with idle gaps. The difference at matched
  bias is the thermal-history effect. Needs phase 2.
- **B2, VCP round-trip latency.** It replaces the assumed 1 ms in §4.3.
- **B3, noise floor per channel.** The §7 test, which feeds σ_n in §3.1.
- Then rerun the evaluation with `--from-csv` on dense bench sweeps.

---

## 7. Risks

| Risk | Mitigation |
|---|---|
| **Adaptive does not beat a sparse ramp on time** (F11) | The factorial measures it directly. The gate's criterion (2) turns a loss into a "no firmware change" recommendation, not a slipped one |
| **Understated uncertainty, so the method stops early and wrong** | Coverage (M3) is a hard requirement; noise model fixed from measurement; MAP priors; raw-point cross-check blocks stopping |
| **The GP absorbs model mismatch** | Explicit-basis GLS inflates Σ_θ instead of hiding it; the Λ flag is calibrated on control devices; per-device "flagged or absorbed" verdict (M5) |
| **D-optimal collapse onto p points** | Seeds, discrepancy-aware information, the mapping budget; measured |
| **Estimands depend on design under mismatch** (F6) | Pushforward onto the dense grid; raw cross-check reported |
| **Thermal history confounds dense vs adaptive** (F4, F5) | Isothermal truth on synthetic devices; ordering study; bench B1; timestamps (Q4) |
| **Jump safety** (F7) | Advisory UCB filter; firmware check unchanged; approach ramp (Q5); residual risk written into §3.6 / §11 |
| **Thermal and noise inputs are assumptions** | Swept and labelled; replaced by bench values (B1, B3) |
| **R̂_ser wrong, e.g. a PTC recovering from a trip** | Costs placement efficiency only; R̂_ser refitted each round from the delta |
| **Analytic G drifts from the extractor** | Finite-difference test against the real extractor |
| **The Python front end drifts from `ct_sim`** | Bit-exact test |
| **Firmware parts unverifiable before the boards** (`now_us` on STM32, pipelined RX) | Phase 2 is gated; documented as unverified; Q6 on timing |
| **Schedule.** This is scope beyond phases 0–9 (blueprint §1: "scope creep here kills the timeline"), and boards land in 2 days | Phase 1 is host-only and runs in the background; it does not touch the bring-up firmware. Phase 2 timing is your call (Q6) |

---

## 8. Decisions I need from you

**Q1. Stopping targets and which parameters they gate.** Recommendation,
derived from what §6 needs (assuming the §6 amplifier is biased near
V_ov ≈ 0.5 V, which I have assumed, not taken from the repo):

| Parameter | Target t (on stderr and on spread/2) | Effect on a §6 observable |
|---|---|---|
| `V_th` | 2 mV | I_D ∝ V_ov², so 2·2/500 = 0.8% of bias current |
| KP (β) | 2% | divider (fixed-V_GS) bias: 2% of I_D and of gain; fixed-I_D bias: 1% of g_m |
| λ | 20% | gain via r_o with R_D ≈ 1 kΩ, I_D ≈ 5 mA: about 1.1% |
| R_DS(on) | **not gated**, reported only | not on the §6 path; known +15% window bias |
| diode `n`, `I_S`, `R_s` | 1%, 10%, 10% | not on the §6 path |

The study also reports points-to-target as a curve over t, so you can pick
with data.

**Q2. Fit-range spreads for β, λ and the diode** (F1). (a) Add them to the
extractors (§5.1), which changes `describe()` and `.model` output for dense
captures too; recommended. (b) Gate only `V_th` on its spread and the rest
on standard error alone.

**Q3. Budget and safety margin defaults.** Budget ¼ of the dense count;
α = 0.9 on `i_limit_ma`. Defaults only; change them if you have a reason.

**Q4. CSV schema 3: decide now or at the gate.** (S1) points mode only
appends `batch,t_us`, and `SWEEP`/`HOLD` columns are unchanged;
recommended, since it costs existing captures nothing. (S2) every mode gains
`t_us`: dense sweeps get a thermal timestamp (it would show F4 directly) at
about +20% TX time per row. (S3) no new columns: batches as `#` info lines,
timing reconstructed from the model. Cheapest, and loses the
measured-dwell record.

**Q5. Jump safety** (F7). (a) Host UCB filter plus documented residual risk.
(b) (a) plus a firmware `approach_v` ramp, default off: limit-checked,
unreported steps before a large upward jump. Recommended; the study measures
its time and heating cost. (c) As (b) but on by default.

**Q6. When phase 2 lands.** Recommendation: phase 1 now, since it is
host-only. Phase 2 firmware is not merged until after phase 5 (first MOSFET
family on hardware), so bring-up runs on the firmware that has been stable
since Oct 9.

**Q7. The 5.5 ms/row figure** in blueprint §4 and the firmware README
*Timing* (F2). Rendered rows are ~46 B, so ~4.0 ms. The text calls it an
estimate ("~64-byte"), not a measurement, so correcting it is not a
provenance problem. It does move the "200-point sweep lands near 1.2 s"
figure toward ~0.8 s plus header, and I want you to decide before that
changes.

---

## 9. What will and will not be verified

| Claim | Phase 1 | Phase 2 | Hardware |
|---|---|---|---|
| GP, acquisition, stopping, mismatch on synthetic devices | verified (sim) | — | not until bench |
| Python front end equals `ct_sim` | verified | — | — |
| Points session, limit ordering, schema 3 | — | verified on `ct_sim` | **not verified** |
| `t_us` on STM32, pipelined RX | — | compiles only | **not verified** |
| VCP latency, noise floor, thermal constants | assumed, swept | assumed | B2, B3, B1 |
| Thermal-order effect | modelled | modelled | B1 |

---

## References

- Rasmussen & Williams, *Gaussian Processes for Machine Learning* (2006):
  §2.7 explicit basis functions, ch. 4 Matérn, ch. 5 marginal likelihood.
- Kennedy & O'Hagan, "Bayesian calibration of computer models", JRSS-B 2001.
- Brynjarsdóttir & O'Hagan, "Learning about physical parameters: the
  importance of model discrepancy", Inverse Problems 2014.
- Plumlee, orthogonal-discrepancy calibration, JASA 2017.
- Lindley, "On a measure of the information provided by an experiment", 1956.
- Chaloner & Verdinelli, "Bayesian experimental design: a review", Stat. Sci. 1995.
- Rainforth, Foster, Ivanova & Bickford Smith, "Modern Bayesian experimental
  design", Stat. Sci. 2024.
- Box & Lucas, "Design of experiments in non-linear situations", Biometrika 1959.
- Box & Draper, "A basis for the selection of a response surface design", JASA 1959.
- MacKay, "Information-based objective functions for active data selection", 1992.
- Krause, Singh & Guestrin, "Near-optimal sensor placements in Gaussian
  processes", JMLR 2008.
- McHutchon & Rasmussen, "Gaussian process training with input noise", NeurIPS 2011.
- Widrow & Kollár, *Quantization Noise* (2008).
- Self & Liang, likelihood-ratio tests on the boundary, JASA 1987.
