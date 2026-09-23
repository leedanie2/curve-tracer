# Semiconductor Curve Tracer — Build Blueprint

**One-line:** A programmable instrument that sweeps bias across a semiconductor device, measures its I-V characteristics across ~5 decades of current, exports data, and extracts SPICE model parameters.

**Why it's the project:** it closes the loop `physics → measurement → model → design → verification` on a breadboard. Measure a real MOSFET, extract its parameters, simulate a circuit in LTspice with *your* model, build that circuit, show simulation matches bench.

---

## 1. Specifications (target)

| Parameter | Target | Notes |
|---|---|---|
| Sweep voltage (V_DS / V_AK) | 0 – 10 V (low current); **~9.81 V max at 50 mA** | 4096 steps (12-bit DAC), ~2.67 mV/step. Full 10 V is not reachable at full current — see §3.1 |
| Sweep current | 0 – 50 mA | Covers small-signal MOSFETs, BJTs, diodes, LEDs |
| Step voltage (V_GS) | 0 – 10 V | Second DAC channel |
| Current measurement range | 100 nA – 50 mA | 3 switchable ranges, ~5.7 decades |
| Current resolution | ~4 nA (low range) | 12-bit ADC + 64× oversampling |
| Voltage measurement | 0 – 10 V, ~0.4 mV | Kelvin-sensed at DUT |
| Supported devices | N-MOSFET, NPN BJT, diode, LED, Zener | MOSFET + diode = core; BJT = phase 2 |
| Output | CSV over USB serial | Live plot in Python |

**Explicit non-goals:** power devices, negative voltages, P-channel/PNP, >10 V. Scope creep here kills the timeline.

---

## 2. Architecture

```
                    ┌──────────── STM32 ────────────┐
                    │  DAC1 ──► gate/step source    │
                    │  DAC2 ──► sweep source        │
                    │  ADC1 ◄── current sense       │
                    │  ADC2 ◄── voltage sense       │
                    │  USB CDC ──► host             │
                    └───────────────────────────────┘

  DAC2 ──► [scale ×3.32] ──► [composite power buffer] ──► [shunt] ──┬──► DUT drain
                                                          │         │
                                                    [diff amp]   [Kelvin sense
                                                          │        + divider + buffer]
                                                        ADC1          │
                                                                    ADC2
  DAC1 ──► [scale ×3.32] ──► [buffer] ──────────────────────────► DUT gate

                                                   DUT source ──► GND
```

**Signal flow per measurement point:** set gate DAC → set drain DAC → wait settle → oversample both ADCs → record → (pulsed mode: return drain to 0) → next point.

---

## 3. Block-by-block design

### 3.1 Sweep source (the hard block)

DAC output is 0–3.3 V at ~5 mA drive. Needs to become 0–10 V at 50 mA.

**Topology:** non-inverting amp (gain 3.32) with an emitter-follower pass transistor **inside the feedback loop** (composite amplifier). Feedback taken from the follower's emitter, so the op-amp corrects the follower's V_BE drop and nonlinearity.

| Component | Value | Rationale |
|---|---|---|
| Op-amp | OPA2197 (or OPA2196) | 36 V supply capable, rail-to-rail, precision |
| Supply | +15 V single | Headroom above 10 V output |
| Gain resistors | R_f = 23.2 kΩ, R_g = 10 kΩ, 0.1% | Gain = 3.32. E96 value — see below |
| Pass transistor | BD139-16, on a TO-126 heatsink (§8); **tab = collector, tied to +15 V** | Worst-case dissipation **~0.89 W** measured, hard short at 330 Ω / 10 Ω (sim 11) |
| Base resistor | **330 Ω** | Bounds the op-amp's drive during a fault, which Q2 passes straight into the load: held-short load current **107 mA** at 330 Ω vs **143 mA** at 100 Ω, and the op-amp supplies 32 mA and stays out of its own limit (sim 10). Clamp-diode discharge: **21.9 mA** peak sink (sim 09). Overshoot into 100 nF is 10.3% small-signal / 2.2% full-scale — well damped (sim 08). **680 Ω was evaluated and rejected on stability** — see below |
| Sense resistor | `R_sense` = **10 Ω**, 1% | Sets the limiter threshold at **75.2 mA** (sim 11). 12 Ω and 15 Ω were evaluated and rejected — see below |
| B-E clamp diode | 1N4148, anode at emitter, cathode at base | BD139 `V_EBO` is 5 V. Unclamped, falling edges reverse-bias the junction to **−6.3 V** at 100 pF and **−9.0 V** at 100 nF, open load (sim 08). Clamped to −0.74 V, and it gives the follower its only active pull-down (sim 09) — see below |
| Isolation resistor | `R_iso` = 22 Ω, emitter → load | **Required for stability — see Phase 0 findings** |
| Compensation cap | ~~10–100 pF across R_f~~ | **REMOVED — destabilizes this topology (Phase 0)** |

**Gain is 3.32 — 23.3 kΩ was never orderable.** 23.3 kΩ is not an E96 value (E96 goes 22.6, **23.2**, 23.7), which is why it never appeared in a cart. **23.2 kΩ** is E96 and is stocked in the same Yageo MFP-25BRD52 0.1% family as the parts already on hand, giving `1 + 23.2/10` = **3.32** against the 3.33 originally specified. `R_f + R_g` becomes **33.2 kΩ** against the 33.3 kΩ the sims were run at — a 0.3% difference, below the precision of every figure quoted below, so **no simulated result needs restating**.

**The gain must not be lowered to "save" headroom.** At full scale the feedback node reaches 10.96 V, and the DUT sees ~9.81 V at 50 mA. The gap is not waste: the feedback node is tapped after `R_sense` and **ahead of** `R_iso`, so the `R_iso` drop (1.10 V at 50 mA) and the shunt burden (50 mV on range 1) come off it downstream, uncorrected. The gain is sized to compensate them by design — see the trade-off note below. Dropping to gain 3.00 would carry the DUT maximum down to 8.75 V at 50 mA and put the zero-current ceiling below 10 V entirely.

**Interim bench substitute (stages 3–6).** Until the 23.2 kΩ parts are in place, the 0.1% pair on hand is **20 kΩ / 10 kΩ**, measured at **19.89 kΩ** and **9.94 kΩ** → gain **3.001**. Both readings sit ~0.6% low on 0.1% parts; that is a meter scale error, not part error, and it **cancels in the ratio**, which is all the gain depends on. This is a substitute, **not the design value**: at gain 3.00 the feedback node reaches only 9.9 V, so the DUT tops out near **8.75 V at 50 mA**. Ratio, linearity and limiter measurements transfer; **no full-scale or top-of-range figure taken on it does.** (Stages are defined in `docs/characterization.md`.)

**Design issue you will actually hit — corrected by Phase 0 simulation:**

The follower adds a pole inside the loop, but the problem is not what the original plan assumed.

A cap across `R_f` is *transimpedance* compensation. It works in a TIA because the noise gain rises with frequency and `C_f` cancels that rise. This circuit is a non-inverting voltage amp with a resistive divider: `β = Z_g/(Z_g+Z_f)`. A cap across `R_f` lowers `Z_f` at high frequency, pushing `β` toward 1 and *raising* loop gain exactly where the follower's phase lag sits. Simulation confirmed it makes things worse monotonically.

**The actual fix is `R_iso`:** a 22 Ω series resistor between the emitter and the load node, with `R_f` feedback tapped on the **emitter side**. The load pole then sits outside the feedback loop where it costs no phase margin.

**Op-amp datasheets give the same guidance independently.** The ST LM324 datasheet notes that capacitive loads applied directly to an op-amp output reduce loop stability margin (50 pF worst case at unity gain), and recommends resistive isolation for larger loads. Phase 0 reached `R_iso` = 22 Ω empirically; this is the general form of that result.

**Trade-off:** `R_iso`'s drop is outside the loop and therefore uncorrected — 1.1 V at 50 mA. Harmless here *only because* `V_DS` is Kelvin-sensed at the DUT (§3.4). The stability fix and the Kelvin-sensing requirement are coupled decisions, not independent ones.

**Base resistor sizing — what `R_B` actually does (sim 10 plus analysis).** An earlier version of this section argued that at 100 Ω the op-amp's own protection would engage first and make the limit test meaningless. That was wrong. The limiter's threshold is Q2's V_BE across `R_sense`, and op-amp drive enters it only logarithmically, as V_T·ln of Q2's collector-current ratio. Sim 10 confirms it: roughly doubling the drive, from 32 to 65 mA, moves the `R_sense` current from 75.2 to 77.8 mA (3%; V_T·ln 2 predicts 1.8 mA).

**Sim 11 is the third independent confirmation of that same logarithmic term, and the first to measure it across `R_B`.** Implied V_BE (`I(R_sense) × R_sense`) is flat across `R_sense` but falls with `R_B` as the drive falls:

| `R_B` | drive | implied V_BE at `R_sense` = 10 / 12 / 15 Ω | step |
|---|---|---|---|
| 330 Ω | 32.2 mA | 752.0 / 752.4 / 753.0 mV | — |
| 470 Ω | 23.3 mA | 741.0 / 741.6 / 742.5 mV | −11 mV (V_T·ln predicts −8.4) |
| 680 Ω | 16.5 mA | 730.8 / 730.8 / 732.0 mV | −10 mV (V_T·ln predicts −9.0) |

Flat to within **0.1% across `R_sense`** at fixed `R_B` — that is the threshold formula confirmed directly. The ~10 mV fall per `R_B` step is the logarithmic drive term, and V_T·ln of the drive ratio predicts it to within a few mV (the 470 → 680 step agrees closely, 9.0 against 10; the 330 → 470 step predicts 8.4 against a measured 11, so the agreement is order-of-magnitude, not exact). **Quote V_BE for the `R_B` you actually build:** at 330 Ω it is 752 mV, not the 731 mV of the 680 Ω rows. `R_B` still matters, for four reasons:

- **It sets part of the short-circuit current directly.** Q2's emitter returns to the output side of `R_sense`, so the base drive Q2 diverts is delivered to the load. Held-short load current = `R_sense` current + op-amp drive: **107 mA at 330 Ω, 143 mA at 100 Ω** (sim 10, op-amp limit set to the OPA2197's 65 mA typical). This is the largest effect and the main reason `R_B` should be large. It also means the load current keeps rising after the limiter engages: at 330 Ω it is ~81 mA when the output has drooped 1% and 107 mA into a hard short. At the load the limit is neither constant-current nor foldback.
- **It bounds the op-amp's operating point during a sustained fault.** At 330 Ω the op-amp supplies 32 mA with its output near 14.6 V and stays out of its own limit, dissipating ~12 mW. At 100 Ω it sits in its 65 mA limit with its output near 11.3 V, dissipating ~0.24 W — roughly a 30 °C rise in SOIC-8 at ~120 °C/W, on a circuit that will be shorted repeatedly. In a short at the load the BD139 base sits at ~4–5 V, not 0.85 V, because the load current's drop across `R_iso` and `R_sense` lifts it. *These op-amp figures are analysis-grade:* the model rails at exactly 15 V (`Rail=0`) with an ideal current clamp, so its dissipation is a lower bound.
- **It bounds Q2's collector current and dissipation:** 32 mA / 53 mW at 330 Ω, 65 mA / 109 mW at 100 Ω (sim 10).
- **It sets the `R_B · C_jc` pole** (below; ~13 MHz at 330 Ω, unchanged).

**The ≤65 mA load target is abandoned. It is not achievable in this topology.** Every "~65 mA" figure in earlier drafts was a target, never a measurement; the measured figures replace it throughout. Three facts close the question:

- **The threshold is `V_BE / R_sense`,** where V_BE is Q2's base-emitter drop at its operating collector current — ~752 mV at `R_B` = 330 Ω, not the 650 mV the original target assumed. That single error is most of the gap. The generic `2N3904` and the fitted Rohm `SST3904` models agree to within 2%.
- **Load current ≈ threshold + op-amp drive,** because Q2's emitter returns to the output side of `R_sense`, so the drive Q2 diverts is delivered to the load. Sim 11 records a systematic **0.2–0.4 mA less** than that sum on every row, so treat it as a close approximation, not an identity.
- **`R_sense` cannot exceed ~12 Ω.** The threshold falls as `R_sense` rises, and 15 Ω puts it at **48.8–50.2 mA** — inside the 50 mA full-scale sweep spec, so legitimate sweeps would trip the limiter. That sets a hard ceiling on how low the threshold can be pushed.

Closing the remaining gap would need the op-amp drive down near 2 mA, i.e. `R_B` ≈ 5 kΩ, which puts the `R_B·C_jc` pole at **880 kHz — below the ~3 MHz crossover.** The loop would not survive it. **The two targets are incompatible; the load target is the one that yields.**

**Chosen pair: `R_B` = 330 Ω, `R_sense` = 10 Ω.** Threshold **75.2 mA**, hard-short load current **107.0 mA**, **50% margin** over the 50 mA full-scale spec.

| pair | threshold | load, hard short | margin over 50 mA | small-signal overshoot |
|---|---|---|---|---|
| **330 / 10** | **75.2 mA** | **107.0 mA** | **50%** | **10.3%** |
| 680 / 10 | 73.1 mA | 89.2 mA | 46% | 21.4% — rejected |
| 680 / 12 | 60.9 mA | 77.5 mA | 22% | 21.4% — rejected |

**Why `R_sense` = 12 Ω is rejected — thermal margin, not performance.** Q2's V_BE drifts **−2 mV/°C**, so a 20 °C rise costs 40 mV. At 12 Ω that takes the threshold from 60.9 mA to **~57.6 mA — only 15% over a full-scale sweep**, close enough to nuisance-trip a legitimate 50 mA measurement. At 10 Ω the same rise gives 71.2 mA, still 42% clear. And 20 °C is conservative: Q2 sits next to a BD139 dissipating **0.89 W** under a sustained short.

**Why `R_B` = 680 Ω is rejected — stability (sim 08, re-run 2026-09-22).** Small-signal overshoot into 100 nF / 200 Ω rises from **10.3% at 330 Ω to 21.4% at 680 Ω**, implying damping ζ ≈ 0.44 and phase margin near **44°**, and 1% settling nearly doubles (0.50 → 0.94 µs). The `R_B·C_jc` pole halves, 13.4 → **6.5 MHz**, against a ~3 MHz crossover. Nothing oscillates in simulation — but the breadboard pole below (stray input capacitance at 2–3 MHz, *not* in this sim) costs roughly 45° on its own where it sits. From 59° that is recoverable with the 2–4 pF `C_f`; from 44° it is not. §12's lesson applies directly.

**Independently of stability: `R_B` never bought any reduction in pass-transistor dissipation.** Worst-case BD139 dissipation is set by `R_sense` alone. Across sim 11's nine rows it groups strictly by `R_sense` — **891–895 mW at 10 Ω, 759–762 mW at 12 Ω, 621–624 mW at 15 Ω** — with a spread of **≤0.5% across `R_B`** inside each group, and it rises very slightly with `R_B` rather than falling:

| pair | `I_C` | implied `V_CE` | BD139 |
|---|---|---|---|
| 330 / 10 | 75.2 mA | 11.85 V | **891 mW** |
| 680 / 10 | 73.1 mA | 12.24 V | **895 mW** |

The two effects cancel: raising `R_B` lowers the threshold current 2.8%, but less total current through `R_iso` lets the emitter sit lower, raising `V_CE` by 3.3%. The product moves 0.45% — the wrong way.

**So what did 680 Ω actually buy?** Only load current below the PTC's 100 mA hold (89.2 mA against 107.0 mA). §3.6 now classifies the PTC as a fire backstop against limiter failure rather than DUT protection, so **that benefit is moot** — nothing downstream depends on the load current sitting under the hold rating. This is independent support for 330 Ω, separate from the stability rejection above: even had 680 Ω passed the stability gate, it would have bought nothing that still matters.

**The limiter's job has narrowed.** With the firmware limit (§4) now carrying DUT protection, the analog limiter only has to protect the *instrument*. That inverts the priority: **margin against nuisance tripping matters more than a tighter ceiling**, which is what picks 10 Ω over 12 Ω and 330 Ω over 680 Ω.

**Bench verification required:** measure the actual trip threshold and confirm it against 75.2 mA, and re-measure after the circuit has been held in limit long enough to warm up — the −2 mV/°C drift is the figure most likely to disagree with simulation.

**The stability gate, stated numerically.** Sizing decisions above were made against a "well damped" criterion that was never written down. It is defined here so the Phase 1 bench work has something to check against. **This is a design decision, not a measured result** — the numbers are chosen, and choosing differently is legitimate if the reasoning below is challenged.

| | Gate | equivalent ζ | ~PM |
|---|---|---|---|
| **Simulated** (sizing decisions) | small-signal overshoot **≤ 15%** into 100 nF / 200 Ω, and no oscillation or sustained ringing at any load from 100 pF to 100 nF | ≥ 0.52 | ≳ 52° |
| **Bench, Phase 1** (the gate that counts) | overshoot **≤ 25%** at the emitter into 100 nF, decaying to within 1% inside **5 µs**, no sustained ringing | ≥ 0.40 | ≳ 40° |

**Why 15% simulated.** `R_B` = 330 Ω sits at 10.3% and 390 Ω at 12.7%, so the gate admits the chosen value with room; 470 Ω (15.6%) is marginal and 680 Ω (21.4%) is out. More to the point, §12 found this loop fails by *cliff*, not by drift: bare, it was stable to ~1 nF and oscillating by 2.2 nF. A loop with that character should be held well clear of the edge, not sized to just clear it.

**Why the bench gate is looser, not tighter — imperfect cancellation, not an uncancelled pole.** `C_f` does cancel the stray input pole (see *Breadboard risks* below), so a board with `C_f` fitted should land near the simulated 10.3%, not at 25%. The allowance is not for the pole; it is for **`C_f` being sized from an estimate**. `C_f = C_in · R_g / R_f` needs `C_in`, and `C_in` is only known as **5–10 pF — a 2× uncertainty** — so the exact `C_f` is anywhere in **2.16–4.31 pF**. One fitted capacitor cannot be right across that span:

| actual `C_in` | exact `C_f` | residual with 3.3 pF fitted | residual pole | phase lost at 3 MHz |
|---|---|---|---|---|
| 5 pF | 2.16 pF | −2.66 pF (**over**-compensated) | 8.6 MHz | ~19° |
| 7.5 pF | 3.23 pF | −0.16 pF | 146 MHz | ~1° |
| 10 pF | 4.31 pF | +2.34 pF (under-compensated) | 9.7 MHz | ~17° |

Losing ~19° from the simulated ~59° leaves ~40°, which is **25.4% overshoot** — the 25% gate is sized directly on that worst case. Lead-dress parasitics, which no estimate of `C_in` captures, sit on top of it. Note the sign matters: below ~7.5 pF a 3.3 pF `C_f` *over*-compensates, pushing `β` up at high frequency, which is the Phase 0 failure mode (§12) rather than a milder version of the under-compensated case.

**Diagnostic — 25% means re-fit `C_f`, not "marginal circuit".** Because the gate is sized on `C_f` mismatch, **overshoot arriving near 25% with `C_f` fitted is evidence that `C_f` is the wrong value, not that the loop is marginal.** The correct response is to re-fit `C_f` and re-measure — try both larger and smaller, since the table above shows the error is two-sided — and only conclude something about stability once overshoot stops responding to it. A board that is genuinely at its margin will sit near 25% across a range of `C_f` values; a mis-fitted one will drop toward 10–15% at the right value. Do not report a stability result from a single `C_f`.

**Two conditions on the bench measurement.** It must be taken on the **OPA2197**, not the LM324 substitute — §8 records that no transient measurement transfers across that swap, and the LM324's 0.4 V/µs slew rate would mask ringing entirely. And it must be taken **with `C_f` fitted and swept** as above. A failure without `C_f`, or at a single untuned `C_f`, is not a failure of `R_B`.

**The 65 mA figure is typical, not guaranteed.** The OPA2197's short-circuit current varies with output voltage and temperature, so the 32 mA it supplies at 330 Ω is margin against a typical value, not a worst case. **Sim 10 models the limiter, not the op-amp's own fault behaviour.** The `UniversalOpAmp2` default 25 mA clamp is below the drive in both `R_B` cases, so sim 10 also steps it to 65 mA; either way the model's output stage (hard rail, ideal clamp) is not the OPA2197's. The trip point and Q2's numbers are trustworthy; the op-amp's condition in the fault is not. **Bench verification required:** with the limiter tripped into a short, measure the op-amp output current (the drop across `R_B`) and confirm the op-amp is not in its own current limit.

**Second constraint: clamp-diode discharge.** With the B-E clamp diode, the op-amp *sinks* the load's discharge current through the diode and `R_B` on every falling edge: peak ≈ (V_E − V_f) / (`R_B` + `R_iso`). Sim 09 gives **21.9 mA at 330 Ω** (100 nF, open load, 9 V → 1 V). At 220 Ω the hand estimate is ~33 mA, and the sim's 25 mA op-amp clamp engaged, so the 220 Ω clamped figures in sim 09 show the model's limit, not the circuit. 330 Ω satisfies both constraints.

**The tradeoff:** `R_B · C_jc` forms a pole with the BD139's `C_jc` = 36.1 pF. At 100 Ω that pole sits near **44 MHz**, far outside the loop; at 330 Ω it is about **13 MHz**, still above the ~3 MHz crossover. Sim 08 (`sim/08_sweep_source_rb_sweep.asc`, `tcase` = 1) measured the effect: 100 mV step overshoot into 100 nF / 200 Ω is 0.3 / 5.3 / 10.3 / 12.7% at 100 / 220 / 330 / 390 Ω. All are well damped, so damping does not set `R_B`; op-amp current does.

**Output headroom.** DAC full scale × 3.32 = **10.96 V** at the feedback node. After the `R_iso` drop and the shunt burden, the DUT sees about **9.81 V at 50 mA**. **10 V at 50 mA is not reachable — do not claim it in the specs.** The full 10 V is available only at low current, where the `R_iso` and shunt drops are small.

**The follower sources current only — falling edges and the clamp diode (sims 08, 09).** An emitter follower can pull its output up but not down. Without a clamp, once the op-amp drives the base low the BD139 cuts off and the load discharges *passively* through `R_L ‖ (R_f + R_g + R_iso ≈ 33.3 kΩ)`, while the base-emitter junction is reverse-biased by nearly the full output swing. Full-scale step, 9 V → 1 V at the emitter, `R_B` = 330 Ω:

| Load | No clamp (sim 08) | 1% settle | min V_BE | With 1N4148 (sim 09) | 1% settle | min V_BE | Op-amp sink |
|---|---|---|---|---|---|---|---|
| 100 nF, 200 Ω | τ = 19.9 µs, passive | 45 µs | −7.7 V | τ = 12.9 µs | 33 µs | −0.73 V | 18.6 mA |
| 100 nF, open | τ = 3.33 ms, passive | 7.06 ms | −9.0 V | τ = 36.6 µs | 103 µs | −0.74 V | 21.9 mA |
| 100 pF, 200 Ω | driven, BJT stays on | 0.88 µs | +0.83 V | driven, BJT stays on | 0.88 µs | +0.83 V | 0.2 mA |
| **100 pF, open** | τ = 3.05 µs, passive | **9.4 µs** | **−6.3 V** | driven, ~10 V/µs | **1.7 µs** | −0.58 V | 1.0 mA |

At 100 nF the unclamped τ matches `C·(R_L ‖ 33.3 kΩ)` to 3 significant figures (3.33 ms open, 19.9 µs at 200 Ω). At 100 pF open it is 3.05 µs against 3.33 µs predicted and not a clean single exponential. With the clamp, a second path — emitter → diode → `R_B` → op-amp — runs in parallel, giving τ ≈ `C·[R_L ‖ (R_iso + R_B)]`: 12.7 / 34.9 µs predicted, 12.9 / 36.6 µs fitted. The remaining ~5% open-load is diode resistance plus the model op-amp's 10 Ω output switch. The clamped decay heads toward ~0.6 V (V_f above the op-amp's low rail) and hands back to the loop at the setpoint. At 100 pF the clamp makes the fall op-amp slew-limited (~10 V/µs).

**Current range 3 is the case that matters.** 100 pF with no load is the actual operating condition for range 3 (100 nA – 10 µA, subthreshold MOSFET). There, unclamped, the BD139 turns off and sees **−6.3 V — over its 5 V `V_EBO` — on every falling step**, and the fall takes 9.4 µs to settle. The clamp holds V_BE at −0.58 V and settles in 1.7 µs. Rising edges are unchanged by the diode (overshoot, sustained slew and settling identical across sims 08 and 09): slew-limited at ~9.2–9.9 V/µs, settling in 0.87–1.14 µs across all four loads.

**Not yet simulated:** both sims step 1 V → 9 V. Below ~1 V the follower's bias current (V_E / 33.3 kΩ through the feedback divider) falls into the µA range, where `r_e = V_T / I_E` reaches kilohms, so the **1.3 µs Phase 0 settling figure is still one operating point**, not a specification. The 1N4148 is LTspice's stock `standard.dio` model (`Cjo` = 4 pF, `tt` = 20 ns). Its `tt` implies ~14 ns reverse recovery against the datasheet's 4 ns, so the sim is pessimistic there; it does not model reverse breakdown, which the clamp never approaches.

**Current limiting (constant-current limit — not foldback):** series 10 Ω sense resistor in the pass transistor emitter + a second transistor whose base-emitter sees that drop; at **75.2 mA** (sim 11) it turns on and steals base drive. Non-negotiable — students and mistakes will short the DUT terminals.

**This is a constant-current limit, not foldback.** Foldback requires an output-to-base divider that *reduces* the limit threshold as the output collapses. The circuit as drawn has no such divider, so under a hard short the `R_sense` current holds at **75.2 mA** instead of folding back to a lower value — which is exactly why worst-case BD139 dissipation is **~0.89 W** (sim 11) and not lower. Do not call it foldback in the README or specs.

**Feedback must be tapped after the 10 Ω sense resistor,** not before it. Tapping ahead of the sense resistor puts the sense drop inside the loop, so the op-amp corrects it away and the limiter never sees the voltage it needs to trip on.

**Breadboard risks specific to this block.** Stray capacitance at the inverting input (**~5–10 pF** from breadboard rows and lead dress) works against `R_f ‖ R_g` = 7 kΩ, placing a pole at roughly **2–3 MHz** — right at crossover. This is the one case where a small capacitor across `R_f` is **correct**: `C_f = C_in · R_g / R_f` ≈ **2–4 pF**.

**This does not contradict the Phase 0 `C_comp` finding — the two address different poles.** Phase 0 removed a 10–100 pF cap that was attempting to compensate *the follower's output pole inside the loop*; that raised `β` toward 1 exactly where the follower's phase lag sat and made things monotonically worse (§12). The 2–4 pF `C_f` here does something else entirely: it **flattens the feedback divider** against the stray input capacitance, holding `β` constant with frequency instead of letting it rise. Same component, same location, opposite purpose — and two orders of magnitude different in value. State the distinction explicitly in the README; it is a good illustration of why "add a feedback cap" is not a general-purpose fix.

### 3.2 Gate / step source

Same scaling (×3.32) but no power buffer — MOSFET gates draw essentially no DC current. A single OPA2197 channel suffices.

**BJT mode (phase 2):** base needs *current*, not voltage. Add a simple op-amp V-to-I converter: op-amp drives a transistor, emitter resistor `R_E` sets `I_B = V_DAC_scaled / R_E`. With `R_E = 100 kΩ`, 0–10 V gives 0–100 µA of base current in 24 nA steps.

### 3.3 Current sense

Shunt in the drain path, high-side, measured by a discrete difference amplifier at gain 20.

| Range | Shunt | Current span | Burden @ full scale | Resolution* |
|---|---|---|---|---|
| 1 (high) | 1 Ω, 1% | 1 – 50 mA | 50 mV | ~40 nA... realistically ~2 µA |
| 2 (mid) | 100 Ω, 0.1% | 10 µA – 1 mA | 100 mV | ~50 nA |
| 3 (low) | 10 kΩ, 0.1% | 100 nA – 10 µA | 100 mV | ~4 nA |

\*with 64× oversampling; without it, divide resolution by ~8.

**Range switching:** v1 uses a manual 3-pin jumper. Phase 2 uses small signal relays (e.g. TQ2-5V) driven by GPIO for auto-ranging. Do **not** use CD4066 analog switches — their on-resistance (~100 Ω, temperature dependent) sits in series with your shunt and corrupts the measurement.

**Difference amp: 3-op-amp instrumentation topology. Input buffers are required — this is not optional.** Simulated in Phase 0; see §13.

- `R1 = R3 = 1 kΩ`, `R2 = R4 = 20 kΩ`, all **0.1%** → gain 20.
- **CMRR is set by resistor matching, not the op-amp.** `CMRR ≈ (1 + R2/R1) / (4t)` is the four-resistor worst case: ~**74.4 dB** at `t = 0.1%` (sim: 74.42 dB) and ~**54.4 dB** at `t = 1%` (sim: 54.57 dB).
- **Report the distribution, not a single number.** A 500-run Monte Carlo at 0.1% gives median **88.26 dB**, p5 **79.43 dB**, min **76.20 dB**. The worst-case corner (74.4 dB) is the floor you design to; the median is what a typical build achieves. Quoting either one alone misrepresents the part. Do not quote the Monte Carlo maximum.
- **Buffers make range 3 functional, not merely more accurate.** Unbuffered, the bare four-resistor bridge loads the shunt: with **no DUT connected at all**, the 10 kΩ range sits at **8.66 V** output — near the rail on a 15 V supply, leaving almost no usable span. The buffers are what make that range work, not a refinement on top of a working range.
- Optional phase 2: swap in an INA828 instrumentation amp and compare measured CMRR against your discrete build.

### 3.4 Voltage sense (Kelvin)

Because shunt burden voltage can reach 100 mV, the voltage across the DUT is **not** the sweep source output. Sense `V_DS` directly at the DUT terminals with separate wires.

Divider `÷4` (30 kΩ / 10 kΩ, 0.1%) into a unity-gain buffer (high input Z so the divider doesn't load the DUT) into ADC2.

This is a genuine four-wire measurement, and explaining why it's necessary is a strong README paragraph.

### 3.5 ADC and MCU

**Board:** Nucleo-F303RE (2× 12-bit DAC, 4× fast ADC, plentiful RAM) or Nucleo-G474RE. Both have the DAC peripheral — many STM32 lines do not. Verify before ordering.

**ADC config:** 12-bit, longest sampling time, VREF from the board's 3.3 V rail. Add a `10 nF` cap at each ADC pin and clamp diodes (BAT54S) to rails for protection.

**Oversampling:** average 64 samples per point → ~3 extra effective bits (~15-bit) at the cost of ~1 ms per point. Standard `√N` noise averaging; state the measured improvement in the README rather than assuming it.

**Reading LTspice results — precision matters when quoting numbers.** Values in a `.raw` file are stored as **float32** (~7 significant digits); `.meas` results in the `.log` are **double**. When quoting a simulated figure in the README, **quote the `.meas` value**, not one read back out of the `.raw`. See `sim/README.md` for the raw layout (float64 first variable, float32 for the rest) and for why stepped `.op` runs need the raw at all.

### 3.6 Protection (required, not optional)

- Constant-current limit on the sweep source (§3.1) — protects the **instrument**
- Firmware current limit (§4, `i_limit_ma`) — protects the **DUT**
- Series PTC resettable fuse (RXEF010, 100 mA hold) in the drain path — **fault/fire backstop only; it does not protect the DUT**
- Clamp diodes on both ADC inputs
- Gate series resistor (1 kΩ) + Zener clamp to protect against ESD-sensitive parts
- DUT socket: 3-pin ZIF or screw terminal, clearly labeled G/D/S

**Division of responsibility — three mechanisms, three jobs, no substitutions.**

| Mechanism | Protects | Timescale | Trips at |
|---|---|---|---|
| Analog limiter (§3.1) | the **instrument** | ~µs, continuous | 75.2 mA at `R_sense` |
| Firmware limit (§4) | the **DUT** | one measurement interval, ~ms | `i_limit_ma`, per device |
| PTC (RXEF010) | against **limiter failure** | seconds | 200 mA guaranteed |

**Neither of the first two substitutes for the other.** The analog limiter reacts in microseconds but its threshold is fixed in hardware at 75.2 mA — far above what a small-signal DUT survives, and not adjustable per device. The firmware limit is per-device and arbitrarily low, but it can only act *after* a measurement completes.

**The gap is real and must be stated.** Firmware cannot react faster than one measurement interval: `settle_us` plus 64× oversampling, on the order of **1 ms** per point. Between the DAC step and the comparison, the DUT sees whatever the analog limiter allows — up to 75.2 mA through `R_sense`, and up to 107 mA at the load into a hard short. **A fragile DUT can therefore be destroyed by a single sweep point before firmware sees it.** Lowering `i_limit_ma` does not close this gap; it only stops the *second* bad point. For genuinely fragile parts the mitigations are a lower `V_max`, a finer step so no single step is a large jump, or an external series resistor — not a firmware value.

**Short-recovery overshoot (sim 10).** When a heavy load current stops abruptly, the op-amp is at its rail and the output overshoots before the loop recovers. At 100 pF the load node reaches 14.8 V on a 10 V setpoint (+48%), holds near 14.2 V for ~1 µs, and settles within 1% by 1.9 µs. At 100 nF there is no overshoot and recovery takes 12–14 µs. The peak is structural and trustworthy; the duration depends on the op-amp model's overload recovery and is not. Sim 11 gives the same peak (+48%) for every `R_B` / `R_sense` pair it tried, so resizing the limiter does not change it. This is not only a fault case: a MOSFET DUT sitting in the current limit and then switching off produces the same edge. Every DUT is selected against the instrument's 10 V ceiling (§1 non-goals), so 14.8 V at the socket can exceed a DUT's rating. Mitigation is unresolved; bench-verify the real magnitude in Phase 1 before relying on the PTC or the ADC clamps to cover it.

**The PTC does not protect the DUT. Do not count it as DUT protection.** The RXEF010 holds **100 mA** and is only guaranteed to open at its **200 mA** trip current. The limiter's sustained-short load current is **107 mA** (sim 11), which sits between the two: above hold, far below trip. It may or may not open there, depending on ambient temperature and how long the fault persists, and either outcome is safe — the limiter already bounds the current, and a tripped PTC only removes it.

**The problem is that no PTC can fill this role.** A device that reliably tripped near the limiter's 107 mA would also trip during a legitimate 50 mA sweep, because PTC hold ratings are specified at 23 °C and derate sharply with ambient — a part chosen to open at 107 mA has a hold current near the top of the instrument's own operating range. **There is no PTC that trips on a DUT-damaging current but not on a valid measurement.** The PTC is therefore reclassified: it is a **fault and fire backstop** against a failure *of the limiter itself* — a shorted Q2, a mis-stuffed `R_sense` — and nothing else. DUT protection is the firmware limit's job (§4).

---

## 4. Firmware (STM32, C)

**Sweep engine**

```
for each V_GS in step_list:
    set DAC1 = V_GS
    for V_DS from 0 to V_max in N steps:
        set DAC2 = V_DS
        delay(settle_us)
        I = oversample(ADC1, 64)
        V = oversample(ADC2, 64)
        if I > i_limit_ma:              # DUT protection — see §3.6
            set DAC2 = 0
            emit_csv_error("ilimit", V_GS, V, I)
            break out of both loops
        emit_csv(V_GS, V, I, range)
        if pulsed_mode: set DAC2 = 0; delay(duty_off_us)
    set DAC2 = 0
```

**The current check is not optional and belongs before `emit_csv`, not after.** Every sweep point already measures current, so the check costs one comparison. Zeroing DAC2 must happen before the point is emitted and before the next `set DAC2`, or the sweep walks one further up the curve into a DUT that is already over its ceiling.

**Key parameters to expose and tune:**

| Parameter | Starting value | Why it matters |
|---|---|---|
| `settle_us` | 20 µs | Sweep source settles in ~1.3 µs (Phase 0); the binding constraint is DUT settling and thermal response, not the amplifier |
| `N` (points/sweep) | 200 | Tradeoff: resolution vs. total sweep time vs. heating |
| `duty_off_us` | 10 ms | Pulsed mode: lets the DUT cool between points |
| `oversample_n` | 64 | Noise floor vs. speed |
| `i_limit_ma` | 60 | **DUT protection ceiling, per device, from the sweep config.** Exceeded → zero DAC2 and abort the sweep. The default sits above the 50 mA full-scale spec so a legitimate sweep cannot trip it, and below the analog limiter so firmware acts first on anything it can catch (§3.6). Fragile parts want a much lower value — set it per DUT, not once |

**Pulsed vs. DC mode is a headline feature.** In DC mode a power device self-heats during the sweep, and its curves visibly droop in saturation — you're measuring thermal effects, not the device. Pulsed mode (bias applied only during the measurement window, ~1% duty cycle) suppresses this. **Overlaying a DC sweep and a pulsed sweep of the same device on one plot is one of the best figures in the project.**

**Transport:** USB CDC virtual COM, plain CSV lines, `115200` baud minimum. Text protocol keeps debugging trivial.

---

## 5. Host software (Python)

**Stack:** `pyserial`, `numpy`, `pandas`, `matplotlib`.

**Functions:**
1. Serial capture → CSV with metadata header (device, date, range, mode, temperature)
2. Live plot of the I-V family as it sweeps
3. Parameter extraction (below)
4. SPICE `.model` card generation
5. Overlay comparison: measured vs. LTspice-simulated

**Parameter extraction — MOSFET**

| Parameter | Method |
|---|---|
| `V_th` | Linear extrapolation of `√I_D` vs `V_GS` in saturation → x-intercept |
| `k` (transconductance param) | Slope² of that same fit |
| `λ` (channel-length mod.) | Slope of `I_D` vs `V_DS` in saturation; `V_A = 1/λ` |
| Subthreshold slope | `dV_GS / d(log₁₀ I_D)` in weak inversion, mV/decade. Theoretical floor is ~60 mV/dec at 300 K — measure how close a real device gets |
| `R_DS(on)` | Slope of the linear region at high `V_GS` |

**Parameter extraction — diode**

Fit `I = I_S(exp(V/nV_T) − 1)` on a semilog plot. Slope gives ideality factor `n`, intercept gives `I_S`. Series resistance shows as high-current roll-off from the ideal line.

**Subthreshold slope needs the low current range** — this is the measurement that justifies building three ranges instead of one.

---

## 6. The closed-loop validation (the payoff)

This sequence is the whole point of the project. Do it, document it, lead the README with it.

1. Measure a 2N7000 MOSFET on your tracer.
2. Extract `V_th`, `k`, `λ` with your Python script.
3. Generate a SPICE `.model` card from those numbers.
4. In LTspice, build a common-source amplifier using **your** model. Simulate gain and bias point.
5. Build that exact amplifier on the breadboard.
6. Measure gain and bias point on the scope.
7. Plot: simulated vs. measured. Report the discrepancy and explain it.

If the numbers agree within a few percent, you have demonstrated the entire chip design workflow — device characterization, model extraction, simulation, silicon (well, breadboard) correlation — end to end. If they *don't* agree, diagnosing why is an even better README section.

---

## 7. Validation & characterization

| Test | Method | Target |
|---|---|---|
| Voltage accuracy | Compare ADC2 reading vs. 5.5-digit DMM across range | <0.5% error |
| Current accuracy | Sweep into 0.1% precision resistors of known value | <1% error, all 3 ranges |
| Noise floor | 1000 samples at fixed bias, compute σ | Report per range |
| CMRR | Common-mode step, measure output shift; repeat with 1% resistors | ~74 dB (0.1%) vs ~54 dB (1%) |
| Settling time | Step drain DAC, scope the buffer output | Sets minimum `settle_us` |
| Linearity | Sweep across a precision resistor, fit residuals | Report INL |
| Self-heating | DC vs. pulsed sweep, same device | Visible droop difference |
| Known-device check | 2N7000, 2N3904, 1N4148 vs. datasheet curves | Qualitative match |

---

## 8. Bill of materials

| Item | Qty | Est. |
|---|---|---|
| Nucleo-F303RE (or G474RE) | 1 | $18 |
| OPA2197 (dual, 36 V, precision) | 4 | $24 |
| SOIC-8 to DIP adapter — the OPA2197 is SOIC-only (see below) | 4 | ~$6 |
| BD139-16 + TO-126 heatsink (see package note) | 3 | $6 |
| 0.1% resistor assortment (1 k, 10 k, 20 k, 30 k, 100 Ω, 10 k shunt) | — | $15 |
| 23.2 kΩ 0.1% — `R_f`, sweep **and** gate (E96, see note) | 5 | ~$3 |
| 1 Ω 1% 1 W shunt | 2 | $2 |
| 15 V / 1 A wall adapter + barrel jack | 1 | $10 |
| 22 Ω 1% (`R_iso`) | 5 | $1 |
| 10 Ω 1% — `R_sense`, sets the **75.2 mA** limiter trip; no substitute (§3.1) | 5 | ~$1 |
| 330 Ω — `R_B` | 5 | ~$1 |
| 200 Ω 1 W — 50 mA load test (0.5 W dissipated; wattage matters) | 3 | ~$2 |
| 100 nF ceramic — decoupling at every op-amp and at the BD139 collector | 20 | ~$3 |
| 10 µF electrolytic, ≥25 V — bulk decoupling | 5 | ~$2 |
| 10 kΩ trimpot — manual input before the DAC drives it | 3 | ~$3 |
| BAT54S clamp diodes | 10 | $3 |
| 1N4148 — B-E clamp; buy extras, they're also useful as DUTs for diode I-V curves | 10 | ~$1 |
| PTC resettable fuse, 100 mA | 5 | $3 |
| DUT devices: 2N7000, BS170, 2N3904, LEDs, Zeners (1N4148 above) | — | $8 |
| Small-signal relays (phase 2 auto-ranging) | 3 | $9 |
| Breadboard, jumpers, headers | — | on hand |
| **Total** | | **~$121** |

Order **two of every active component.** You will destroy at least one op-amp and one pass transistor.

**`R_f` is 23.2 kΩ, an E96 value — 23.3 kΩ does not exist.** Earlier drafts specified 23.3 kΩ, which is in neither E24 nor E96 (E96 runs 22.6, **23.2**, 23.7), so it was never orderable and never shipped. 23.2 kΩ 0.1% is stocked in the same Yageo MFP-25BRD52 family as the parts on hand. **Both** the sweep source (§3.1) and the gate/step source (§3.2) use it, so the two channels stay identical and the BOM carries one value, not two.

**Package note — the BD139-16 is SOT-32 / TO-126, not TO-220.** The part that shipped is a **BD139-16** in **SOT-32**, which is ST's name for the JEDEC **TO-126** outline. TO-126 has a smaller tab and a different hole pattern than TO-220, so **TO-220 clip-on heatsinks and mounting hardware will not fit** — buy TO-126 heatsinks. As on TO-220, **the tab is the collector**, and in this circuit the collector is tied to **+15 V**: the tab is live at 15 V, so it must not contact a grounded chassis, and it cannot share an un-insulated heatsink with anything else. Use an insulating pad and shoulder washer if either applies. (The `-16` suffix is the h_FE bin, 63–160; it does not affect the design, which relies on the follower being inside the feedback loop rather than on any particular gain.)

**The OPA2197 has no DIP package.** It ships in SOIC-8 and VSSOP-8 only, so breadboard work needs a SOIC-8 to DIP adapter and fine-pitch soldering.

**Bench substitute path.** Until the adapters are on hand, use an **LM324** (quad, DIP-14). It runs on the single +15 V rail with inputs down to ground, so it covers breadboard stages 3–8 of the sweep source (stages are defined in `docs/characterization.md`). The **TL074 does not work** here: its input common-mode range excludes ground, which single-supply operation requires.

Substitutes are acceptable through Phase 6 for bring-up, firmware and host work. The OPA2197 must be installed before **Phase 7** parameter extraction, because every accuracy figure in §7 assumes it.

**No transient measurement on the LM324 transfers.** It slews at **0.4 V/µs** typical (V+ = 15 V, unity gain, R_L = 2 kΩ, C_L = 100 pF), ~25× slower than the 9.2–9.9 V/µs edges sim 08 measured. Every step-response, settling-time and edge-shape measurement taken on the substitute is slew-limited and says nothing about the OPA2197 circuit. Only DC measurements — gain ratio, linearity, limiter trip point — transfer, and those only with the caveats below.

What else an LM324 result does *not* carry over to the OPA2197:

- **Loop stability (stage 5).** The LM324's 1.3 MHz GBW puts crossover about 8× lower than the OPA2197's 10 MHz, well away from the follower pole that forced `R_iso` in Phase 0 (§12). A stable LM324 loop says nothing about the OPA2197 loop. Repeat the stage 5 oscillation check and settling after the swap.
- **Clamp diode discharge (stage 7).** Sim 09 has the op-amp sinking **21.9 mA** through the clamp on every falling edge (100 nF, open load). The LM324 sinks only **10 mA min / 20 mA typ**. It also sinks weakly near ground, a documented characteristic. TI's applications guidance puts its sink capability at roughly 30 µA with the output at 0.2 V, so a load demanding more holds the output up near 0.7 V. The datasheet recommends a resistor from output to ground in output-sinking applications, to bias the on-chip vertical PNP and prevent crossover distortion. With the output held near 0.7 V, the clamp path stops pulling the emitter at about 0.7 V + V_f ≈ 1.3 V. Fast discharge toward 0 V is exactly what the clamp exists to do, so on an LM324 the falling edge will read slow and floor early. That is the op-amp, not the circuit. The stage 7 clamp measurement, and any comparison against sim 09's 1.7 µs, require the OPA2197.
- **Short test (stage 8).** The LM324's own output source current is **20 mA min, 40 mA typ**; the minimum is below the ~32 mA the OPA2197 supplies through `R_B` = 330 Ω in a short (sim 10). The limiter's threshold still transfers: it is Q2's V_BE across `R_sense`, and drive enters it only logarithmically, so the `R_sense` current measured on an LM324 is within a few percent of the OPA2197's. The *load* current transfers less well — it also carries the op-amp's drive through Q2, so on an LM324 it reads roughly 5–12 mA low. What does not transfer at all is the op-amp's own condition during the fault: the LM324 may sit in its short-circuit limit where the OPA2197 at 330 Ω does not. *Analysis; sim 10 checks the threshold and the drive routing, not the LM324 itself.*
- **Phase 2–3 gates.** 20 nA typical input bias current and mV-level offset swamp current range 3 (100 nA – 10 µA). Rerun the "within 1%" and "5-decade span" gates on the OPA2197 before counting them as passed.

---

## 9. Build phases

| Phase | Deliverable | Gate to proceed |
|---|---|---|
| **0** | ~~LTspice model of sweep source~~ **DONE** — sweep source (§12) *and* difference amp CMRR + input loading (§13) | Sweep source settles cleanly into ≥100 nF with `R_iso`; diff amp buffering decided |
| **1** | Sweep source on breadboard, current limit working | 0–10 V linear at low current; current limit trips at **~75 mA** (§3.1), re-measured warm; **stability gate met** — ≤25% overshoot into 100 nF, 1% in 5 µs, on the OPA2197 with `C_f` fitted (§3.1) |
| **2** | Current sense, range 1 only | Reads a known resistor within 1% |
| **3** | Ranges 2 & 3 + Kelvin sense | 5-decade span verified against precision resistors |
| **4** | Firmware sweep + serial CSV | First complete diode I-V curve |
| **5** | Host live plot + CSV export | First MOSFET curve family |
| **6** | Pulsed mode | DC vs. pulsed overlay figure |
| **7** | Parameter extraction | SPICE model card generated |
| **8** | Closed-loop validation | Simulated vs. measured amplifier plot |
| **9** | Characterization + README | Repo publishable |
| **P2** | BJT support, relay auto-ranging, INA828 comparison | Only if phases 0–9 are polished |

---

## 10. Repository structure

```
curve-tracer/
├── README.md              ← lead with the closed-loop result figure
├── docs/
│   ├── design.md          ← topology, tradeoffs, equations
│   ├── characterization.md← §7 results table + plots
│   └── schematic.pdf
├── sim/                   ← LTspice .asc files, compensation sweep
├── firmware/              ← STM32 C, CubeIDE project
├── host/                  ← Python capture, plot, extraction
├── data/                  ← raw CSVs of measured devices
└── media/                 ← scope captures, demo video
```

**README section order:** closed-loop headline figure → what it is → why I built it → architecture → three design decisions with the math → measured performance table → what I'd do differently → build instructions.

The "what I'd do differently" section is the one interviewers respond to. Write it honestly.

---

## 11. Known risks

| Risk | Mitigation |
|---|---|
| Composite amp oscillates | Simulate compensation first (Phase 0); scope every stage before adding the next |
| Breadboard noise floor limits low range | Star-ground, short leads, decoupling at every op-amp; if range 3 is unusable, report the measured limitation honestly — that's a legitimate finding |
| STM32 ADC noisier than spec | Oversample; if still poor, add an external ADC (ADS1115) as phase 2 |
| Scope creep into BJT/auto-ranging | Phases 0–9 first. Phase 2 is optional |
| Blown parts stall progress | Duplicates of every active component on hand from day one |

---

## 12. Phase 0 results (completed Sep 4, 2026)

Simulation files: `sim/01_sweep_source_compensation.asc` (2N2222), `sim/02_sweep_source_bd139.asc` (BD139 + `C_comp`, oscillates), `sim/03_sweep_source_load_sweep.asc` (final).

**1. `C_comp` across `R_f` was wrong and is removed.** With the BD139 model, every `C_comp` value from 1 pF to 100 pF oscillated, monotonically worse with increasing capacitance. Mechanism in §3.1. Correct fix is `R_iso`.

**2. Model fidelity determined the conclusion.** With a generic 2N2222 (`fT` ~300 MHz) the loop was unconditionally stable and the `C_comp` error was invisible. The ST-published BD139 model (`Tf` = 2.96 ns → `fT` ≈ 54 MHz, `Cjc` = 36.1 pF, `Cje` = 10.2 pF) exposed it immediately. A MODPEX-generated BD139 model found online had `CJE = CJC = 1e-11` exactly — placeholder values — and would have given a misleading answer.

**3. Solver settings produced a false result.** The first compensation sweep showed 9% overshoot at `C_comp` = 1 pF. Capping max timestep (`.tran 0 200u 0 10n`) removed it entirely — it was an interpolation artifact of the adaptive timestep, not circuit behavior.

**4. Capacitive load limit.** Bare (no `R_iso`): stable to ~1 nF, oscillating by 2.2 nF. Sharp threshold, characteristic of a phase-margin cliff. With 22 Ω `R_iso`: clean at both emitter and output nodes across 100 pF – 100 nF, i.e. at least 50× more headroom for one part.

**5. Settling time.** Small-signal settling ~1.3 µs at the emitter. `settle_us` in firmware will be set by DUT physics, not the sweep source.

**Falling edges, `R_B` = 330 Ω and the B-E clamp diode** were simulated later (Sep 18, 2026, `sim/08_sweep_source_rb_sweep.asc`, `sim/09_sweep_source_clamped.asc`); results are in **§3.1**.

**Previously open, now closed:** difference amplifier CMRR simulation — completed Sep 18, 2026, results in **§13**.

**Bench items carried forward to Phase 1:** confirm `R_iso` behavior with the real BD139 and real breadboard parasitics; measure actual settling; verify the current limit trips at **~75 mA** (sim 11; the ~65 mA in earlier drafts was a target, never a measurement — see §3.1).

---

## 13. Phase 0 results — difference amplifier (completed Sep 18, 2026)

Simulation files: `sim/04_diffamp_cmrr.cir` (worst-case tolerance corner), `sim/05_diffamp_mc.cir` (500-run Monte Carlo), `sim/06_diffamp_loading.cir` (input loading, unbuffered), `sim/07_diffamp_buffered.cir` (input loading, buffered). Per-file detail in `sim/README.md`.

**1. CMRR at the worst-case corner is set by resistor tolerance.** Skewing all four resistors to the worst sign pattern gives **134.40 dB** at `t` = 1e-6, **74.42 dB** at 0.1%, and **54.57 dB** at 1%. The 1e-6 row is a **solver-floor control, not a result** — it confirms numerical noise sits far below the rows that matter. Closed form for this corner: `A_cm = 80t/[(1-t²)(1+b)]` with `b = 20(1+t)/(1-t)`; the familiar `(1+G)/(4t)` shortcut agrees within 0.02 dB at 0.1%.

**2. Report the distribution, not a single number.** 500 runs at 0.1% (n = 500): min **76.20**, p5 **79.43**, median **88.26**, p95 **110.51**, max **144.73** dB. The worst-case 74.4 dB is the floor to design against; 88 dB is what a typical build gets. Note that LTspice's `mc()` draws **uniform and independent** values, whereas real reel-matched resistors are both tighter and correlated — so this spread is **conservative**. **Do not cite the max**; it is one lucky draw, not a spec. Histogram: `media/cmrr_mc.png`.

**3. The unbuffered difference amp loads the shunt — this is the finding that changes the BOM.** With **no DUT connected at all**, the bare four-resistor bridge draws current through the shunt: `V(out)` = **9.512 mV** at `Rsh` = 1 Ω, i.e. **475.6 µA** of phantom current. In general `I_err = 0.476/(1000 + Rsh)` A. Against full scale that is **0.95% / 43% / 433%** on ranges 1 / 2 / 3. Range 3 is not merely inaccurate, it is unusable — the unbuffered output sits at **8.66 V** at `Rsh` = 10 kΩ, near the rail on a 15 V supply.

**4. Conclusion: unity-gain input buffers are required.** Move to the **3-op-amp instrumentation topology**. BOM goes from 3 to 4 × OPA2197 (§8). This is a functional requirement for range 3, not an accuracy refinement.

**5. What sim 07 does and does not show.** The buffered netlist returns `V(out)` = **0 at all three `Rsh` values**. That zero comes from **ideal `E`-source buffers, which draw no input current by construction** — it confirms the topology is wired as intended and that the bridge no longer loads the shunt, and **nothing more**. It is **not** evidence of any particular bias-current performance. The real residual is the **OPA2197 input bias current, ~5 pA typical — a datasheet figure, not a simulated one**. Sizing it properly requires swapping the `E` sources for the vendor OPA2197 model.

**Method note.** This LTspice is the Windows build in a CrossOver bottle; `-b` against the `/Applications` binary exits 0 without simulating. The working headless invocation is recorded in `sim/README.md`. `.meas` on a stepped `.op` logs only the first step, so per-step values come from the `.raw` file — and `.raw` is float32 while `.meas` is double (§3.5).

**Bench items carried forward to Phase 1:** verify the buffered difference amp's actual CMRR against the 74.4 dB floor with real 0.1% parts; confirm range 3 is usable with buffers on a real breadboard; measure input bias current contribution directly rather than trusting the datasheet typ.
