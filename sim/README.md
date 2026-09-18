# sim/ — LTspice experiments

One netlist per experiment. `.cir` files are the source of truth and the only
sim artifacts in git; LTspice's `.log`, `.raw`, `.db`, `.op.raw` and `.net`
outputs are regenerable and gitignored.

Run a netlist, then parse its log:

```
python3 host/parse_cmrr_log.py sim/05_diffamp_mc.log   # -> media/cmrr_mc.png
```

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
