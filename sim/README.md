# sim/ — LTspice experiments

One file per experiment, and that file is the source of truth. Circuits with
topology worth seeing are LTspice schematics (`.asc`: 00–03, 08, 09); circuits
that are just a resistor network are plain netlists (`.cir`: 04–07). Vendor
models live in `models/`. LTspice's `.log`, `.raw`, `.db`, `.op.raw` and `.net`
outputs are regenerable and gitignored.

Run a file headless (`-b` takes `.asc` and `.cir` alike), then parse its log or
`.raw`. This LTspice is the Windows build
in a CrossOver bottle, so the `/Applications` binary is only a launcher stub —
`-b` against it returns exit 0 without simulating. Drive the bottled `.exe`
instead:

```
CX=/Applications/LTspice.app/Contents/SharedSupport/ltspice/bin
"$CX/cxstart" --bottle ltspice --workdir "$PWD/sim" -- \
  "C:\\Program Files\\ADI\\LTspice\\LTspice.exe" -b "$PWD/sim/06_diffamp_loading.cir"

python3 host/parse_cmrr_log.py sim/05_diffamp_mc.log   # -> media/cmrr_mc.png
```

Note that `.meas` on a stepped `.op` logs only the first step; the remaining
steps are in the `.raw` file (f64 first variable, f32 for the rest).

---

## 04_diffamp_cmrr.cir — CMRR vs resistor tolerance, worst-case corner

**Sweeps:** `VCM` 0–11 V, stepped over `tol` = 1e-6, 1e-3, 1e-2. The four
resistors are skewed to the worst-case sign pattern (`s1..s4` = +, −, −, +) so
each tolerance gives the corner, not a typical case. `E1` gain 1e7 and tightened
`reltol/vntol/abstol` keep the solver from dominating the result.

**Question:** with a plain one-op-amp difference amp, how much common-mode
rejection do resistor tolerances alone cost at the worst-case corner?

**Results:**

| tol  | CMRR |
|------|------|
| 1e-6 | 134.40 dB |
| 0.1% | 74.42 dB |
| 1%   | 54.57 dB |

The 1e-6 row is a **solver-floor control, not a result** — it confirms the
numerical noise floor sits far below the rows that matter.

Closed form for this corner:

```
A_cm = 80t / [(1 - t^2)(1 + b)],   b = 20(1 + t) / (1 - t)
```

The familiar `(1 + G)/(4t)` shortcut agrees to within 0.02 dB at 0.1%.

## 05_diffamp_mc.cir — CMRR Monte Carlo, 0.1% resistors

**Sweeps:** 500 runs (`.step param run 1 500 1`), each resistor drawn
independently via `mc(1, tol)` at `tol` = 1e-3, same `VCM` 0–11 V DC sweep.

**Question:** the corner in 04 is the guaranteed floor — what does the
*distribution* look like across a real production batch?

**Results (n = 500):**

| stat | CMRR |
|------|------|
| min | 76.20 dB |
| p5 | 79.43 dB |
| median | 88.26 dB |
| p95 | 110.51 dB |
| max | 144.73 dB |

Report this as a distribution with **74.4 dB as the floor**, not as a single
number. Note that `mc()` draws uniform and independent values, whereas real
reel-matched resistors are both tighter and correlated — so this spread is
conservative. **Do not cite the max**; it is one lucky draw, not a spec.

Reproduced from a batch run on 2026-09-18: `parse_cmrr_log.py` returns these
figures to the digit, since LTspice seeds `mc()` deterministically. Histogram:
`media/cmrr_mc.png`.

## 06_diffamp_loading.cir — input loading with no DUT connected

**Sweeps:** `Rsh` stepped over 1 Ω, 100 Ω, 10 kΩ at a fixed 10 V source, `.op`
only. `E1` gain is 1e5 here since the question is resistive loading, not CMRR.

**Question:** with nothing plugged into the fixture, does the difference amp's
own input network inject current into the shunt?

**Results:** `V(out) = 9.512 mV` at `Rsh = 1 Ω`, which is **475.6 µA of phantom
current with no DUT connected**. In general:

```
I_err = 0.476 / (1000 + Rsh)   [A]
```

Against full scale that is **0.95% / 43% / 433%** on ranges 1 / 2 / 3.

**Conclusion:** unity-gain input buffers are required — move to the 3-op-amp
instrumentation topology. BOM goes from 3 to 4 × OPA2197.

## 07_diffamp_buffered.cir — same loading test, with input buffers

**Sweeps:** identical to 06 — `Rsh` over 1 Ω, 100 Ω, 10 kΩ, fixed 10 V source,
`.op` only. Node names are kept the same as 06 so the two files diff cleanly;
the only change is `Eba`/`Ebb`, unity-gain buffers inserted between the source
nodes (`na`, `nb`) and the bridge resistors, which now feed from `bufa`/`bufb`.

**Question:** does the 3-op-amp instrumentation topology remove the phantom
current that 06 measured?

**Read this before citing a number from it:** the buffers here are ideal
`E` sources, so they draw **zero input current by construction**. The sim
returns zero because that is what an ideal VCVS does, not because it measured
anything. It demonstrates the topology change — the bridge no longer loads the
shunt — and nothing more.

The real-world figure is the **OPA2197 input bias current, ~5 pA typical**,
which comes from the datasheet, not from this netlist. **This sim does not
prove pA-level performance.** To simulate that, swap the `E` sources for the
vendor OPA2197 model.

**Measured (batch run, 2026-09-18):**

| Rsh | 06 unbuffered V(out) | 07 buffered V(out) |
|-----|----------------------|--------------------|
| 1 Ω | 9.5123 mV | 0 |
| 100 Ω | 0.86563 V | 0 |
| 10 kΩ | 8.6578 V | 0 |

07 returns exact zero at every step, which is the expected output of an ideal
VCVS and confirms the netlist is wired as intended — it is **not** evidence of
any particular bias-current performance. Read it as: the error term 06 found
is gone once the bridge stops drawing from the shunt. Sizing the residual
needs the vendor model.

## 08_sweep_source_rb_sweep.asc — base resistor and falling edge, no clamp

**Sweeps:** three nested steps, 32 runs in all:
- `Rb` over 100, 220, 330 and 390 Ω.
- Four load cases, stepped as `lcase` 1–4 with `Cload` and `RL` set by
  `table()`: 100 nF / 200 Ω, 100 nF / open (1 GΩ), 100 pF / 200 Ω, 100 pF / open.
- Two drive cases, stepped as `tcase` with the `V2` pulse levels set by
  `table()`: `tcase` = 1 is a 100 mV small-signal step, `PULSE(1.5 1.6 ...)`,
  5.0 V → 5.33 V at the emitter; `tcase` = 2 is full scale, `PULSE(0.3 2.7 ...)`,
  1 V → 9 V.

LTspice sets `.tran` once per run, not per step, so both drive cases share
`.tran 0 20m 0 10n`. That is long enough for the full-scale passive fall to
finish while keeping the 10 ns max timestep (blueprint §12, item 3); the
small-signal measurements only use 0–90 µs. `.save` limits output to
`V(emitter)`, `V(n004)` (the BD139 base, which has no FLAG) and `I(Rbase)`.
Even so the `.raw` is ~1.3 GB and a batch run takes ~7 min.

**Question:** which base resistor, and what does the falling edge do when the
follower can only source current?

**Results — `Rb` vs small-signal overshoot** (`tcase` = 1, 100 nF / 200 Ω;
batch run, 2026-09-18):

| Rb | Overshoot | 1% settling |
|----|-----------|-------------|
| 100 Ω | 0.28% | 0.23 µs |
| 220 Ω | 5.28% | 0.36 µs |
| 330 Ω | 10.34% | 0.50 µs |
| 390 Ω | 12.73% | 0.56 µs |

All four are well damped; damping does not set `Rb`. It is set by op-amp
current when the current limiter trips (~13.95 V / `Rb`), which this netlist
does not model — see blueprint §3.1. That picks **330 Ω**.

At full scale (`tcase` = 2), rising edges are slew-limited at 9.1–9.95 V/µs
and settle to 1% in 0.87–1.18 µs across all four loads and all four `Rb`.
Overshoot at 100 nF is 0.22 / 1.25 / 2.18 / 2.65% at 100 / 220 / 330 / 390 Ω,
and zero at 100 pF. The op-amp sources under 3 mA on the rise. Falling edges
do not depend on `Rb` without the clamp; they are tabulated under 09.

Even the 100 mV small-signal fall reverse-biases the base-emitter junction to
−5.3 V at 100 nF open load, because the op-amp output still slams to its low
rail while the load holds the emitter up. The swing size does not protect the
junction; the clamp in 09 does.

**Convergence:** 24 of the 32 steps need Gmin stepping to find the initial
operating point. All succeed, with no timestep failures. The op-amp is
`UniversalOpAmp2` with default parameters: 10 V/µs slew and a 25 mA output
clamp, against the OPA2197's ~20 V/µs and ~65 mA typical.

```
python3 host/parse_tran_overshoot.py sim/08_sweep_source_rb_sweep.raw
```

## 09_sweep_source_clamped.asc — 08 plus a B-E clamp diode

**Sweeps:** 08's full-scale case only: `Rb` over 220 and 330 Ω, the same four
loads, `PULSE(0.3 2.7 ...)`, same `.tran`. The only circuit change is `D1`, a 1N4148 across the
BD139 base-emitter junction, anode at the emitter and cathode at the base
(`D1 emitter N004 1N4148` in the netlist). It uses the stock LTspice
`standard.dio` model (`Is=2.52n Rs=.568 N=1.752 Cjo=4p M=.4 tt=20n`). Those
are fitted-looking values, not placeholders. `Cjo` matches the datasheet, but
`tt` implies ~14 ns reverse recovery against the datasheet's 4 ns, so the sim
is pessimistic there. Reverse breakdown is not modelled; the clamp never gets
near it.

**Question:** does the clamp keep V_BE inside the BD139's 5 V `V_EBO`, and what
does the active pull-down it creates cost the op-amp?

**Results — falling edge, 9 V → 1 V, `Rb` = 330 Ω** (batch run, 2026-09-18):

| Load | 08 τ | 08 settle | 08 min V_BE | 09 τ | 09 settle | 09 min V_BE | 09 op-amp sink |
|------|------|-----------|-------------|------|-----------|-------------|----------------|
| 100 nF, 200 Ω | 19.9 µs | 45.1 µs | −7.72 V | 12.9 µs | 33 µs | −0.73 V | 18.6 mA |
| 100 nF, open | 3.33 ms | 7.06 ms | −8.98 V | 36.6 µs | 103 µs | −0.74 V | 21.9 mA |
| 100 pF, 200 Ω | driven | 0.88 µs | +0.83 V | driven | 0.88 µs | +0.83 V | 0.2 mA |
| **100 pF, open** | 3.05 µs | **9.4 µs** | **−6.28 V** | driven | **1.7 µs** | −0.58 V | 1.0 mA |

"Driven" means the op-amp pulls the emitter down at its slew rate: through the
BJT, which stays on, at 100 pF / 200 Ω; and through the diode, with the BJT
off, in 09 at 100 pF open. Everywhere else in 08 the BJT cuts off and the load
discharges passively. At 100 nF, τ matches `C·(RL ‖ 33.3 kΩ)` to 3 significant figures.
In 09 the diode path runs in parallel, giving `τ ≈ C·[RL ‖ (R_iso + Rb)]`:
12.7 / 34.9 µs predicted, 12.9 / 36.6 µs fitted.

100 pF open is current range 3's real operating condition. Unclamped, it
reverse-biases the junction past `V_EBO` on every falling step; the clamp fixes
that and cuts settling from 9.4 to 1.7 µs. Rising edges are unchanged:
overshoot, sustained slew and settling are identical to 08's `tcase` = 2 rows.

**Read this before citing the 220 Ω rows** (in the parser output, not the table
above): the discharge would need ~33 mA at 220 Ω. The op-amp model clamps at
25 mA and hit exactly 25.00 mA, so those rows show the model's limit, not the
circuit's.

```
python3 host/parse_tran_overshoot.py sim/09_sweep_source_clamped.raw
```
