# Semiconductor Curve Tracer — Build Blueprint

**One-line:** A programmable instrument that sweeps bias across a semiconductor device, measures its I-V characteristics across ~5 decades of current, exports data, and extracts SPICE model parameters.

**Why it's the project:** it closes the loop `physics → measurement → model → design → verification` on hardware you built. Measure a real MOSFET, extract its parameters, simulate a circuit in LTspice with *your* model, build that circuit, show simulation matches bench.

---

## 1. Specifications (target)

| Parameter | Target | Notes |
|---|---|---|
| Sweep voltage (V_DS / V_AK) | 0 – 10 V (low current); **9.06–9.73 V max at 50 mA**, set by the PTC's resistance | 4096 steps (12-bit DAC), ~2.67 mV/step. Full 10 V is not reachable at full current — see §3.1, *Output headroom* |
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

**The gain must not be lowered to "save" headroom.** At full scale the feedback node reaches 10.96 V, and the DUT sees 9.06–9.73 V at 50 mA, depending on the PTC (see *Output headroom* below). The gap is not waste: the feedback node is tapped after `R_sense` and **ahead of** `R_iso`, so the `R_iso` drop (1.10 V at 50 mA), the shunt burden (50 mV on range 1) and the PTC's drop (0.08–0.75 V) come off it downstream, uncorrected. The gain is sized to compensate them by design — see the trade-off note below. Dropping to gain 3.00 would carry the DUT maximum down to 8.00–8.67 V at 50 mA and put the zero-current ceiling below 10 V entirely.

**Interim bench substitute (stages 3–6).** Until the 23.2 kΩ parts are in place, the 0.1% pair on hand is **20 kΩ / 10 kΩ**, measured at **19.89 kΩ** and **9.94 kΩ** → gain **3.001**. Both readings sit ~0.6% low on 0.1% parts; that is a meter scale error, not part error, and it **cancels in the ratio**, which is all the gain depends on. This is a substitute, **not the design value**: at gain 3.00 the feedback node reaches only 9.9 V, so the DUT tops out near **8.75 V at 50 mA**. Ratio, linearity and limiter measurements transfer; **no full-scale or top-of-range figure taken on it does.** (Stages are defined in `docs/characterization.md`.)

**Design issue you will actually hit — corrected by Phase 0 simulation:**

The follower adds a pole inside the loop, but the problem is not what the original plan assumed.

A cap across `R_f` is *transimpedance* compensation. It works in a TIA because the noise gain rises with frequency and `C_f` cancels that rise. This circuit is a non-inverting voltage amp with a resistive divider: `β = Z_g/(Z_g+Z_f)`. A cap across `R_f` lowers `Z_f` at high frequency, pushing `β` toward 1 and *raising* loop gain exactly where the follower's phase lag sits. Simulation confirmed it makes things worse monotonically.

**The actual fix is `R_iso`:** a 22 Ω series resistor between the emitter and the load node, with `R_f` feedback tapped on the **emitter side**. The load pole then sits outside the feedback loop where it costs no phase margin. This is the first of two places the design isolates a capacitive load rather than compensating for it; §3.7 states the rule.

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

**The stability gate, stated numerically.** Sizing decisions above were made against a "well damped" criterion that was never written down. It is defined here so the H4 bench work has something to check against. **This is a design decision, not a measured result** — the numbers are chosen, and choosing differently is legitimate if the reasoning below is challenged.

| | Gate | equivalent ζ | ~PM |
|---|---|---|---|
| **Simulated** (sizing decisions) | small-signal overshoot **≤ 15%** into 100 nF / 200 Ω, and no oscillation or sustained ringing at any load from 100 pF to 100 nF | ≥ 0.52 | ≳ 52° |
| **Bench, H4** (the gate that counts) | overshoot **≤ 25%** at the emitter into 100 nF, decaying to within 1% inside **5 µs**, no sustained ringing | ≥ 0.40 | ≳ 40° |

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

**This gate is measured at H4, on the assembled board** (§9), where the OPA2197 condition is satisfied by construction — the fab fits it. It is also the **first** stability test the loop gets. The narrower Phase 1 breadboard gate was dropped on Oct 8, 2026, as an accepted risk (§9), so this is where the composite amplifier first meets real parasitics. If it fails, `hardware/CONTINGENCY.md` is the response.

**The 65 mA figure is typical, not guaranteed.** The OPA2197's short-circuit current varies with output voltage and temperature, so the 32 mA it supplies at 330 Ω is margin against a typical value, not a worst case. **Sim 10 models the limiter, not the op-amp's own fault behaviour.** The `UniversalOpAmp2` default 25 mA clamp is below the drive in both `R_B` cases, so sim 10 also steps it to 65 mA; either way the model's output stage (hard rail, ideal clamp) is not the OPA2197's. The trip point and Q2's numbers are trustworthy; the op-amp's condition in the fault is not. **Bench verification required:** with the limiter tripped into a short, measure the op-amp output current (the drop across `R_B`) and confirm the op-amp is not in its own current limit.

**Second constraint: clamp-diode discharge.** With the B-E clamp diode, the op-amp *sinks* the load's discharge current through the diode and `R_B` on every falling edge: peak ≈ (V_E − V_f) / (`R_B` + `R_iso`). Sim 09 gives **21.9 mA at 330 Ω** (100 nF, open load, 9 V → 1 V). At 220 Ω the hand estimate is ~33 mA, and the sim's 25 mA op-amp clamp engaged, so the 220 Ω clamped figures in sim 09 show the model's limit, not the circuit. 330 Ω satisfies both constraints.

**The tradeoff:** `R_B · C_jc` forms a pole with the BD139's `C_jc` = 36.1 pF. It sits *inside* the loop, which is why `R_B` is not an instance of the §3.7 isolation rule despite looking like one. At 100 Ω that pole sits near **44 MHz**, far outside the loop; at 330 Ω it is about **13 MHz**, still above the ~3 MHz crossover. Sim 08 (`sim/08_sweep_source_rb_sweep.asc`, `tcase` = 1) measured the effect: 100 mV step overshoot into 100 nF / 200 Ω is 0.3 / 5.3 / 10.3 / 12.7% at 100 / 220 / 330 / 390 Ω. All are well damped, so damping does not set `R_B`; op-amp current does.

**Output headroom.** DAC full scale × 3.32 = **10.96 V** at the feedback node. Three drops come off it downstream of the loop, uncorrected: `R_iso` (1.10 V at 50 mA), the shunt burden (50 mV on range 1), and the PTC (§3.6). An earlier draft quoted **9.81 V at 50 mA**, which counted the first two and left the PTC out.

The PTC is the variable term. The nSMD010 fitted on the board (`hardware/DECISIONS.md`, S-1) is **1.6 Ω minimum and 15 Ω maximum**, and its datasheet specifies the maximum *one hour after reflow* — so a freshly assembled board can sit anywhere in that range, not only one that has tripped, and every trip can move it again. At 50 mA the DUT therefore sees **9.73 V at best (1.6 Ω) and 9.06 V at worst (15 Ω)**. The board's actual value is measurable at bring-up: the drop from TP5 (`LOAD`) to TP17 (`PTC_OUT`) at a known current.

**10 V at 50 mA is not reachable — do not claim it in the specs.** The full 10 V is available only at low current, where all three drops are small.

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

**Design finding (Oct 8, 2026): on the PCB, `C_in` is mostly the op-amp.** The 5–10 pF above is breadboard rows and lead dress only. It never counted the OPA2197's own input capacitance: **1.6 pF differential and 6.4 pF common-mode** (datasheet, typical). With IN+ held by the DAC, the differential part also lands on IN− to AC ground. TI does not say whether the 6.4 pF is per input or for both inputs together, so count 3.2–6.4 pF.

On the PCB the strays shrink to under ~1 pF (no pour under the node, §14.5(2)), and the op-amp dominates:

- **`C_in` ≈ 5–9 pF, so `C_f` ≈ 2.2–3.9 pF.**
- **3.3–3.9 pF if the 6.4 pF is per input**, the upper end of the 2–4 pF above.

The "smaller on a PCB" assumption (§14.4, `hardware/DECISIONS.md` C1) holds for the stray component only. The total is not smaller than the breadboard estimate. On a breadboard it would have been larger than this section assumed: strays plus op-amp, ~10–18 pF. `C_f` is still fitted on the board from a measurement (`hardware/CONTINGENCY.md` §2).

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

Divider `÷4` (**300 kΩ / 100 kΩ**, 0.1%) into a unity-gain buffer into ADC2. The buffer stops the *ADC* loading the divider; it does nothing about the divider loading the DUT. An earlier draft claimed otherwise, and fitted 30 kΩ / 10 kΩ.

**Any resistive divider on the DUT node is counted as DUT current.** The divider hangs from `KELVIN_HI`, which is the DUT's drain, so it sits on the DUT side of the shunt. Its current, `V_DS / (R_top + R_bottom)`, flows through the shunt with the DUT's, and the difference amp cannot tell them apart. At 30k/10k that was 25 µA per volt, 250 µA at 10 V. Nothing in firmware or host corrected it, and a 1 kΩ resistor read at 10 V came out 2.5% high, which fails Phase 2's 1% gate on its own. Two fixes, both applied (Oct 6, 2026):

- **Raise the divider tenfold**, 300k/100k: **2.5 µA per volt**, 25 µA at 10 V, with the ÷4 ratio unchanged. The buffer's input bias (pA, §13) is still negligible against a 75 kΩ source.
- **Subtract it in firmware.** `I_DUT = I_shunt − V_DS / 400 kΩ`, with the measured `V_DS`. The divider resistance travels in the CSV header as `cal_rdiv_ohm`, so any archived capture can be re-derived (`firmware/README.md`, schema 2).

On range 1, 25 µA is 0.6 of an LSB, so the correction is a sub-LSB term there, and a device that is off reads within an LSB of zero on either side. On ranges 2 and 3 it is most of full scale, and the correction is what makes them usable at all.

This is the same mechanism as §13's phantom current, reached by a different path. There, the unbuffered difference-amp bridge drew 475.6 µA through the shunt with no DUT connected; here the sense divider does. **For any network added to the board, check where its current returns: anything connected between the shunt and the DUT's source is measured as DUT current.**

This is a genuine four-wire measurement, and explaining why it's necessary is a strong README paragraph.

**Consequence for analysis: a fixed-`V_DS` slice is not a column lookup.** The drop across `R_iso` plus the shunt burden scales with current (§3.1), so at one commanded `vds_set_v` every gate curve in a family reaches a *different* measured `vds_meas_v` — the higher the gate drive, the larger the drop. In a simulated 2N7000-ish family, a commanded 2.052 V lands at 1.921 V on the `V_GS` = 2.6 V curve and at 0.899 V on the `V_GS` = 3.6 V curve, a spread of over a volt.

So extracting anything at a fixed `V_DS` — `V_th` and `β` from a `√I_D` fit above all — requires **interpolating each curve onto a common measured-`V_DS` grid**. Grouping rows by `vds_set_v` looks correct and is not: it silently compares points taken at different actual bias, and on the example above it would compare a device in saturation against one pushed into triode. Implemented in `host/ct_host/dataset.py`.

### 3.5 ADC and MCU

**Board:** Nucleo-F303RE (2× 12-bit DAC, 4× fast ADC, plentiful RAM) or Nucleo-G474RE. Both have the DAC peripheral — many STM32 lines do not. Verify before ordering.

**PA5 cannot be used as a DAC output on a Nucleo-64 — it drives LD2.** The obvious mapping for two DAC channels is the two channels of peripheral DAC1, `DAC1_OUT1` on **PA4** and `DAC1_OUT2` on **PA5**. PA5 is unusable here: on every Nucleo-64 board it also drives **LD2, the green user LED**, so the LED and its series resistor sit directly on the DAC output as an uncontrolled load. Use the F303RE's *second* DAC peripheral instead — the sweep source goes to **`DAC2_OUT1` on PA6**, the gate/step source stays on `DAC1_OUT1` / PA4.

**The cost of that choice:** DAC1 and DAC2 are separate peripherals, so they cannot perform a **synchronised dual-channel update** the way DAC1's two channels could (`DUALTRIG` / a shared trigger). The sweep engine (§4) sets gate and then drain sequentially, so this costs nothing in DC mode. **It would matter if pulsed mode is ever restored**, where gate and drain ideally step together on one trigger to keep the measurement window tight; that would need either both channels on DAC1 — reworking around LD2, e.g. by lifting solder bridge SB21 — or accepting the skew between two software writes. Record the constraint now rather than rediscovering it when pulsed mode is built.

**ADC config:** 12-bit, longest sampling time, VREF from the board's 3.3 V rail. Add a `10 nF` cap at each ADC pin and clamp diodes (BAT54S) to rails for protection. Each pin is driven from its op-amp through **1 kΩ**. 10 nF is ten times what an OPA2197 at unity gain is rated to drive directly (§3.7), and 1 kΩ also bounds what an op-amp at its rail can push through the BAT54S into the Nucleo's 3.3 V rail: (15 − 3.3 − 0.4) V / 1 kΩ ≈ **11 mA** per channel. Before, the op-amp's own ~65 mA limit was the only bound. It happens on unplugged Kelvin leads, which leave the buffer input floating, and on any over-range on ranges 2–3.

**What 1 kΩ costs.**

- **A DC offset from leakage at the pin.** The BAT54S is the dominant term: ≤ 2 µA at 25 °C (datasheet maximum, at `V_R` = 25 V), so up to **2 mV**, ~1 mV typical, about 2.5 LSB. It is not perfectly fixed. Schottky leakage depends on the reverse voltage across each diode, which moves with the signal, and it rises steeply with temperature. So **calibrate it at zero current at bring-up** (H4, `hardware/README.md`), then re-check at full scale. At ADC2 it is multiplied by 4 at the DUT, up to 8 mV, against the §7 target of 0.5% of reading.
- **A 10 µs time constant** (1 kΩ × 10 nF) against the default `settle_us` of 20 µs. The voltage channel is unaffected: it is sampled after all 64 current conversions, ~550 µs later. The current channel is not. At 20 µs the first conversion still carries 5.9% of the step since the last point, and the 64-sample mean carries 0.16% of it. In practice that is ~80 µA on the first point of each gate step on range 1, where the current falls from up to 50 mA to zero, plus a 0.16% lag on every point-to-point change. `settle_us` ≥ 50 µs makes it 0.008%; 83 µs is ln(4096)·τ, 1 LSB on the first sample. **The default is now 50 µs** (§4).

**Oversampling:** average 64 samples per point → ~3 extra effective bits (~15-bit) at the cost of ~1 ms per point. Standard `√N` noise averaging; state the measured improvement in the README rather than assuming it.

**Reading LTspice results — precision matters when quoting numbers.** Values in a `.raw` file are stored as **float32** (~7 significant digits); `.meas` results in the `.log` are **double**. When quoting a simulated figure in the README, **quote the `.meas` value**, not one read back out of the `.raw`. See `sim/README.md` for the raw layout (float64 first variable, float32 for the rest) and for why stepped `.op` runs need the raw at all.

### 3.6 Protection (required, not optional)

- Constant-current limit on the sweep source (§3.1) — protects the **instrument**
- Firmware current limit (§4, `i_limit_ma`) — protects the **DUT**
- Series PTC resettable fuse (100 mA hold) in the drain path — **fault/fire backstop only; it does not protect the DUT**. The board carries a TECHFUSE **nSMD010** (1206); the RXEF010 originally specified is not in JLCPCB's assembly library. Comparison in `hardware/DECISIONS.md`, S-1
- Clamp diodes on both ADC inputs
- Gate series resistor (1 kΩ) + Zener clamp to protect against ESD-sensitive parts
- DUT socket: 3-pin ZIF or screw terminal, clearly labeled G/D/S

**Division of responsibility — three mechanisms, three jobs, no substitutions.**

| Mechanism | Protects | Timescale | Trips at |
|---|---|---|---|
| Analog limiter (§3.1) | the **instrument** | ~µs, continuous | 75.2 mA at `R_sense` |
| Firmware limit (§4) | the **DUT** | one measurement interval, ~ms | `i_limit_ma`, per device |
| PTC (nSMD010) | against **limiter failure** | seconds | 250 mA guaranteed |

**Neither of the first two substitutes for the other.** The analog limiter reacts in microseconds but its threshold is fixed in hardware at 75.2 mA — far above what a small-signal DUT survives, and not adjustable per device. The firmware limit is per-device and arbitrarily low, but it can only act *after* a measurement completes.

**The gap is real and must be stated.** Firmware cannot react faster than one measurement interval: `settle_us` plus 64× oversampling, on the order of **1 ms** per point. Between the DAC step and the comparison, the DUT sees whatever the analog limiter allows — up to 75.2 mA through `R_sense`, and up to 107 mA at the load into a hard short. **A fragile DUT can therefore be destroyed by a single sweep point before firmware sees it.** Lowering `i_limit_ma` does not close this gap; it only stops the *second* bad point. For genuinely fragile parts the mitigations are a lower `V_max`, a finer step so no single step is a large jump, or an external series resistor — not a firmware value.

**Short-recovery overshoot (sim 10).** When a heavy load current stops abruptly, the op-amp is at its rail and the output overshoots before the loop recovers. At 100 pF the load node reaches 14.8 V on a 10 V setpoint (+48%), holds near 14.2 V for ~1 µs, and settles within 1% by 1.9 µs. At 100 nF there is no overshoot and recovery takes 12–14 µs. The peak is structural and trustworthy; the duration depends on the op-amp model's overload recovery and is not. Sim 11 gives the same peak (+48%) for every `R_B` / `R_sense` pair it tried, so resizing the limiter does not change it. This is not only a fault case: a MOSFET DUT sitting in the current limit and then switching off produces the same edge. Every DUT is selected against the instrument's 10 V ceiling (§1 non-goals), so 14.8 V at the socket can exceed a DUT's rating. **Mitigation (Oct 9, 2026): D3, an SMAJ12A TVS across the DUT socket, fitted if H4 step 15 measures a peak above 12 V** (`hardware/DECISIONS.md` D3). At this circuit's ≤ ~0.1 A it clamps at its breakdown voltage, 13.3–14.8 V. It does not clamp at its 12 V standoff, so it trims the peak rather than holding it under 12 V. Bench-verify the real magnitude at H4 step 15 (Phase 1 was dropped, §9); do not rely on the PTC or the ADC clamps to cover it.

**The PTC does not protect the DUT. Do not count it as DUT protection.** The nSMD010 holds **100 mA** and is only guaranteed to open at its **250 mA** trip current (the RXEF010 it replaced: 200 mA). The limiter's sustained-short load current is **107 mA** (sim 11), which sits between the two: above hold, far below trip. It may or may not open there, depending on ambient temperature and how long the fault persists, and either outcome is safe — the limiter already bounds the current, and a tripped PTC only removes it.

**The problem is that no PTC can fill this role.** A device that reliably tripped near the limiter's 107 mA would also trip during a legitimate 50 mA sweep, because PTC hold ratings are specified at 23 °C and derate sharply with ambient — a part chosen to open at 107 mA has a hold current near the top of the instrument's own operating range. **There is no PTC that trips on a DUT-damaging current but not on a valid measurement.** The PTC is therefore reclassified: it is a **fault and fire backstop** against a failure *of the limiter itself* — a shorted Q2, a mis-stuffed `R_sense` — and nothing else. DUT protection is the firmware limit's job (§4).

**A tripped PTC costs headroom, not accuracy, until it recovers.** Tripping raises its resistance sharply; it then recovers toward a value anywhere up to its 15 Ω post-trip maximum, not necessarily the value it had before. The *measurement* is unaffected throughout: `V_DS` is Kelvin-sensed at the DUT and current is read at the shunt, and both sit downstream of the PTC. What degrades is how much of the `V_DS` range is reachable at a given current (§3.1, *Output headroom*) and where each commanded point lands. Two practical consequences: a sweep taken while the PTC recovers covers less of the curve than it was asked to, and the `vds_set_v − vds_meas_v` diagnostic (`firmware/README.md`) reads the extra resistance as series resistance in a lead.


### 3.7 Capacitive load: isolate, don't compensate

**The rule.** When an op-amp output has to drive capacitance, put a resistor in series between the output and the capacitance, and take the feedback from the op-amp's side of that resistor. The load's pole then sits outside the loop and costs no phase margin. Do not try to fix it with a capacitor in the feedback network.

It appears twice in this design, found independently each time:

| Where | Resistor | Capacitance it isolates | How the value was set |
|---|---|---|---|
| Sweep source, emitter → `LOAD` (§3.1) | **`R_iso` = 22 Ω** | The DUT and its leads, 100 pF – 100 nF | **Phase 0 simulation** (§12): bare, the loop is stable to ~1 nF and oscillating by 2.2 nF; with 22 Ω it is clean from 100 pF to 100 nF. Feedback is tapped at `FB_SENSE`, ahead of `R_iso` (§14.5(5)) |
| ADC buffer outputs → ADC pins (§3.5) | **1 kΩ** each (`R19`, `R22` on the board) | The 10 nF §3.5 places at each ADC pin | **The OPA2197 datasheet** sets the floor: unity-gain direct drive is rated to 1 nF (§7.3.5), and Table 3 gives 20 Ω for 45° and 51 Ω for 60° phase margin at 10 nF. 51 Ω was fitted first, then raised to **1 kΩ** to bound the clamp current into the 3.3 V rail (§3.5). More resistance only adds phase margin |

**The "don't compensate" half is measured, not advice.** Phase 0 tried the obvious alternative first — a cap across `R_f` (`C_comp`) — and every value from 1 pF to 100 pF oscillated, monotonically worse as the capacitance grew (§12, sim 02). §3.1 explains the mechanism: in a non-inverting stage, a feedback cap raises `β` exactly where the load pole's phase lag sits.

**What the larger resistor costs.** 51 Ω cost nothing measurable (2 µA × 51 Ω = 0.10 mV). 1 kΩ costs up to 2 mV of leakage offset and a 10 µs settling constant; §3.5 quantifies both and says how each is handled.

**`R_B` looks like a third instance and is not one.** `R_B` (330 Ω, §3.1) also sits between an op-amp output and a capacitance — the BD139's `C_jc` — but the feedback is taken *after* it, at the emitter. So `R_B · C_jc` is a pole *inside* the loop, and it costs phase as `R_B` grows. That is exactly why 680 Ω was rejected (sim 08: 10.3% overshoot at 330 Ω against 21.4% at 680 Ω). `R_B`'s value is set by fault current (sim 10), not by isolation. **The tell is where the feedback is taken relative to the resistor.** Before the resistor, the resistor isolates. After it, the resistor adds a pole.

**Scope.** This rule is about capacitance on an output. `C_f` (§3.1) addresses capacitance on the inverting *input* — the stray pole that isolation cannot reach — and is not an exception to it.

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
| `settle_us` | **50 µs** | The binding constraint is the **ADC front end**, not the DUT: the 1 kΩ × 10 nF filter at the ADC1 pin (τ = 10 µs, §3.5). At 20 µs the 64-sample mean still carries **0.16%** of the point-to-point step. That is a systematic lag toward the previous point, not noise, so a rising sweep reads consistently low (and the first point of each gate step, which falls to zero, reads high). At 50 µs it is **0.008%**. Cost: 30 µs × 1600 points = **48 ms** per family, against ~5.5 ms per row of serial transmission. *This supersedes the original rationale* — "sweep source settles in ~1.3 µs (Phase 0); the binding constraint is DUT settling and thermal response" — which stopped being true on the current channel when the 1 kΩ went in (Oct 6, 2026). A slow DUT can still need more |
| `N` (points/sweep) | 200 | Tradeoff: resolution vs. total sweep time vs. heating |
| `duty_off_us` | 10 ms | Pulsed mode: lets the DUT cool between points |
| `oversample_n` | 64 | Noise floor vs. speed |
| `i_limit_ma` | 60 | **DUT protection ceiling, per device, from the sweep config.** Exceeded → zero DAC2 and abort the sweep. The default sits above the 50 mA full-scale spec so a legitimate sweep cannot trip it, and below the analog limiter so firmware acts first on anything it can catch (§3.6). Fragile parts want a much lower value — set it per DUT, not once |

**Pulsed vs. DC mode is a headline feature.** In DC mode a power device self-heats during the sweep, and its curves visibly droop in saturation — you're measuring thermal effects, not the device. Pulsed mode (bias applied only during the measurement window, ~1% duty cycle) suppresses this. **Overlaying a DC sweep and a pulsed sweep of the same device on one plot is one of the best figures in the project.**

**Transport: USART2 through the ST-LINK Virtual COM Port, not a USB device stack.** Plain CSV lines, `115200` baud. Text protocol keeps debugging trivial.

Earlier drafts said "USB CDC virtual COM", which is right about what the *host* sees and wrong about what the MCU does. The F303RE does have a native USB device peripheral on PA11/PA12, but **the Nucleo-64 does not route it to a connector** — there is no USB device socket and no 1.5 kΩ pull-up. What the board provides is the ST-LINK's Virtual COM Port, hard-wired to **USART2 (PA2/PA3)**, which enumerates on the PC as a USB CDC serial port. So the host still opens an ordinary CDC serial device; the firmware side is a plain UART and needs no USB stack, no descriptors and no middleware. Do not add USB device middleware to this project — on this board it would have nothing to connect to.

**Timing: transmission dominates, not conversion.** At 115200 baud a ~64-byte CSV row takes **~5.5 ms** to send, against ~1.1 ms for 128 ADC conversions (2 channels × 64× oversampling). A blocking write would therefore hold the DUT at each bias point roughly 5× longer than the measurement itself needs — which is precisely the self-heating that pulsed mode exists to suppress. **Use interrupt- or DMA-driven TX with a ring buffer** so conversion overlaps transmission. A 200-point sweep then lands near 1.2 s.

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
| `β` (transconductance param) | Slope² of that same fit, in the convention `I_D = β(V_GS − V_th)²`. **See the note on conventions below** — this is a factor of 2 away from SPICE's |
| `λ` (channel-length mod.) | Slope of `I_D` vs `V_DS` in saturation; `V_A = 1/λ` |
| Subthreshold slope | `dV_GS / d(log₁₀ I_D)` in weak inversion, mV/decade. Theoretical floor is ~60 mV/dec at 300 K — measure how close a real device gets |
| `R_DS(on)` | Slope of the linear region at high `V_GS` |

**Two corrections the fit needs, both of which change the answer.**

*The transconductance convention is ambiguous, so state it.* Two are in common use and they differ by a factor of two:

| Convention | Expression | Name here |
|---|---|---|
| Fit-natural | `I_D = β(V_GS − V_th)²` | `β` — the slope² above |
| SPICE Level 1 | `I_D = ½·KP·(W/L)·(V_GS − V_th)²` | `KP·(W/L) = 2β` |

Writing "k = slope²" without saying which one is an invitation to a silent 2× error in a `.model` card. The host extractor reports **both**, named `beta` and `kp_wl`, and `host/ct_host/spice.py` emits `KP` from the latter.

*`β` fitted at a nonzero `V_DS` slice is inflated by channel-length modulation.* The saturation current carries the `(1 + λV_DS)` factor, so a fit at slice voltage `V_DS,slice` returns

```
β_fit = β_true · (1 + λ · V_DS,slice)
```

This is not a small correction at the voltages this instrument works in. **At a 7 V slice with λ = 0.012 V⁻¹ it is 8.4%** — an order of magnitude larger than the fit's own standard error, and in a consistent direction, so it reads as a good measurement of the wrong quantity. Verified against the host simulator: feeding a known `k` = 0.055 A/V² and recovering 0.0597 before de-embedding, 0.0275 = `k`/2 after. The extractor de-embeds using the fitted `λ` and reports both values.

`V_th` is unaffected — it is the x-intercept, and a multiplicative factor on `√I_D` does not move it.

**Parameter extraction — diode**

Fit `I = I_S(exp(V/nV_T) − 1)` on a semilog plot. Slope gives ideality factor `n`, intercept gives `I_S`. Series resistance shows as high-current roll-off from the ideal line.

**Subthreshold slope needs the low current range** — this is the measurement that justifies building three ranges instead of one.

---

## 6. The closed-loop validation (the payoff)

This sequence is the whole point of the project. Do it, document it, lead the README with it.

1. Measure a 2N7000 MOSFET on your tracer.
2. Extract `V_th`, `β`, `λ` with your Python script.
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
| OPA2197 (dual, 36 V, precision) — six channels, three duals (§13) | 3 | $18 |
| SOIC-8 to DIP adapter — the OPA2197 is SOIC-only (see below) | 4 | ~$6 |
| BD139-16 + TO-126 heatsink (see package note) | 3 | $6 |
| 0.1% resistor assortment (1 k, 10 k, 20 k, 100 k, 300 k, 100 Ω, 10 k shunt) | — | $15 |
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
| **Total** | | **~$115** |

Order **two of every active component.** You will destroy at least one op-amp and one pass transistor.

**`R_f` is 23.2 kΩ, an E96 value — 23.3 kΩ does not exist.** Earlier drafts specified 23.3 kΩ, which is in neither E24 nor E96 (E96 runs 22.6, **23.2**, 23.7), so it was never orderable and never shipped. 23.2 kΩ 0.1% is stocked in the same Yageo MFP-25BRD52 family as the parts on hand. **Both** the sweep source (§3.1) and the gate/step source (§3.2) use it, so the two channels stay identical and the BOM carries one value, not two.

**Package note — the BD139-16 is SOT-32 / TO-126, not TO-220.** The part that shipped is a **BD139-16** in **SOT-32**, which is ST's name for the JEDEC **TO-126** outline. TO-126 has a smaller tab and a different hole pattern than TO-220, so **TO-220 clip-on heatsinks and mounting hardware will not fit** — buy TO-126 heatsinks. As on TO-220, **the tab is the collector**, and in this circuit the collector is tied to **+15 V**: the tab is live at 15 V, so it must not contact a grounded chassis, and it cannot share an un-insulated heatsink with anything else. Use an insulating pad and shoulder washer if either applies. (The `-16` suffix is the h_FE bin, 100–250 — 63–160 is the `-10` bin (ST BD135–BD140 datasheet, Rev 5, Table 4); it does not affect the design, which relies on the follower being inside the feedback loop rather than on any particular gain.)

**The OPA2197 has no DIP package.** It ships in SOIC-8 and VSSOP-8 only, so breadboard work needs a SOIC-8 to DIP adapter and fine-pitch soldering.

**Bench substitute path.** Until the adapters are on hand, use an **LM324** (quad, DIP-14). It runs on the single +15 V rail with inputs down to ground, so it covers breadboard stages 3–8 of the sweep source (stages are defined in `docs/characterization.md`). The **TL074 does not work** here: its input common-mode range excludes ground, which single-supply operation requires.

Substitutes are acceptable for firmware and host work. The OPA2197 must be installed before **Phase 7** parameter extraction, because every accuracy figure in §7 assumes it — and on the PCB it always is, since the board is assembled by the fab with OPA2197s fitted (§14.3).

*Phase 1 was dropped on Oct 8, 2026 (§9). This paragraph and the LM324 notes below now apply only to bench work after bring-up and to the Oct 26 fallback.*

**The SOIC-8 adapters are no longer on the critical path.** They were, while Phase 1 required an OPA2197 on a breadboard; §14.3 withdrew that requirement. Phase 1 now runs on **the fastest DIP-8 op-amp in the lab, ≥8 MHz GBW** — enough to keep crossover inside the 2–3 MHz band where the stray input pole sits, which is the only thing that gate asks. **The LM324 is still not that part:** at 1.3 MHz GBW its crossover lands ~8× below the pole, so it cannot see the interaction at all, independently of the slew-rate problem below. Adapters are a nice-to-have for post-bring-up bench work.

**No transient measurement on the LM324 transfers.** It slews at **0.4 V/µs** typical (V+ = 15 V, unity gain, R_L = 2 kΩ, C_L = 100 pF), ~25× slower than the 9.2–9.9 V/µs edges sim 08 measured. Every step-response, settling-time and edge-shape measurement taken on the substitute is slew-limited and says nothing about the OPA2197 circuit. Only DC measurements — gain ratio, linearity, limiter trip point — transfer, and those only with the caveats below.

What else an LM324 result does *not* carry over to the OPA2197:

- **Loop stability (stage 5).** The LM324's 1.3 MHz GBW puts crossover about 8× lower than the OPA2197's 10 MHz, well away from the follower pole that forced `R_iso` in Phase 0 (§12). A stable LM324 loop says nothing about the OPA2197 loop. Repeat the stage 5 oscillation check and settling after the swap.
- **Clamp diode discharge (stage 7).** Sim 09 has the op-amp sinking **21.9 mA** through the clamp on every falling edge (100 nF, open load). The LM324 sinks only **10 mA min / 20 mA typ**. It also sinks weakly near ground, a documented characteristic. TI's applications guidance puts its sink capability at roughly 30 µA with the output at 0.2 V, so a load demanding more holds the output up near 0.7 V. The datasheet recommends a resistor from output to ground in output-sinking applications, to bias the on-chip vertical PNP and prevent crossover distortion. With the output held near 0.7 V, the clamp path stops pulling the emitter at about 0.7 V + V_f ≈ 1.3 V. Fast discharge toward 0 V is exactly what the clamp exists to do, so on an LM324 the falling edge will read slow and floor early. That is the op-amp, not the circuit. The stage 7 clamp measurement, and any comparison against sim 09's 1.7 µs, require the OPA2197.
- **Short test (stage 8).** The LM324's own output source current is **20 mA min, 40 mA typ**; the minimum is below the ~32 mA the OPA2197 supplies through `R_B` = 330 Ω in a short (sim 10). The limiter's threshold still transfers: it is Q2's V_BE across `R_sense`, and drive enters it only logarithmically, so the `R_sense` current measured on an LM324 is within a few percent of the OPA2197's. The *load* current transfers less well — it also carries the op-amp's drive through Q2, so on an LM324 it reads roughly 5–12 mA low. What does not transfer at all is the op-amp's own condition during the fault: the LM324 may sit in its short-circuit limit where the OPA2197 at 330 Ω does not. *Analysis; sim 10 checks the threshold and the drive routing, not the LM324 itself.*
- **Phase 2–3 gates.** 20 nA typical input bias current and mV-level offset swamp current range 3 (100 nA – 10 µA). Rerun the "within 1%" and "5-decade span" gates on the OPA2197 before counting them as passed.

---

## 9. Build phases

**The deliverable is an assembled PCB, not a breadboard** (§14). That changes
what the breadboard is for. It is no longer the build platform staged through
phases 1–3. It was kept for **one measurement**, a stability GO/NO-GO on the
composite amplifier before layout froze, and that measurement has now been
dropped too (Oct 8, 2026; *Phase 1 dropped*, below). Everything is built and
validated on the board.

| Phase | Deliverable | Gate to proceed |
|---|---|---|
| **0** | ~~LTspice model of sweep source~~ **DONE** — sweep source (§12) *and* difference amp CMRR + input loading (§13) | Sweep source settles cleanly into ≥100 nF with `R_iso`; diff amp buffering decided |
| **1** | ~~Composite amplifier on breadboard — stability GO/NO-GO~~ **Dropped Oct 8, 2026** (*Phase 1 dropped*, below). The oscillation test moves to H4 | — |
| **H1** | KiCad schematic, in `hardware/` | Every §3 block drawn; test points placed on every node §3 names (§14); alternate-value footprints placed (§14) |
| **H2** | KiCad layout | §14 layout constraints met; the analog-critical nets listed in `hardware/README.md` routed **by hand**, not autorouted; **DRC clean** |
| **H3** | Design freeze → PCBA ordered, **express shipping** (§14.3) | The date gates below. Order as soon as H2 is DRC-clean *and* the pre-order checklist in `hardware/README.md` is clear — do not wait for a calendar date |
| **H4** | Board bring-up | Rails and star ground first. Then sweep source: 0–10 V linear at low current; limiter trips at **~75 mA** (§3.1), **re-measured warm**; **§3.1 stability gate** — ≤25% overshoot into 100 nF, 1% in 5 µs, `C_f` fitted *and swept*. Also the §3.6 short-recovery overshoot, bench-verified. **This is the loop's first stability test** (Phase 1 dropped); if it fails, `hardware/CONTINGENCY.md`. Run from `hardware/H4_CARD.md` |
| **2** | Current sense, range 1 — **on the PCB** | Reads a known resistor within 1% |
| **3** | Kelvin sense — **on the PCB**. Ranges 2 & 3 only if the board gets there (MVP is range 1 — §14) | Kelvin `V_DS` tracks a DMM at the DUT within 0.5%. Ranges 2–3, if reached: 5-decade span against precision resistors |
| **4** | Firmware sweep + serial CSV | First complete diode I-V curve |
| **5** | Host live plot + CSV export | First MOSFET curve family |
| **6** | ~~Pulsed mode~~ — **out of MVP scope** (§14) | — |
| **7** | Parameter extraction | SPICE model card generated |
| **8** | Closed-loop validation | Simulated vs. measured amplifier plot |
| **9** | Characterization + README | Repo publishable |
| **P2** | BJT support, relay auto-ranging, INA828 comparison, pulsed mode | Only if the board works and phases 0–9 are polished |

**Phase 1 dropped (Oct 8, 2026): a deliberate, accepted risk, not an
oversight.** The breadboard stability GO/NO-GO due Oct 12 will not be run.

- **No part for it.** As narrowed, the gate needed a DIP-8 op-amp of
  ≥ 8 MHz GBW (§14.3), and there is none on hand.
- **No working bench.**
- **It tested less than it seemed to.** Narrowed, it covered only the bare
  loop: stages 1–6, with no `R_iso`, no clamp, no limiter and no 100 nF
  load, on a substitute op-amp and probably on different rails. The §3.1
  overshoot gate was already at H4. A GO would have said only that the bare
  loop, on a different part, did not oscillate.

**The oscillation test moves to H4, on the assembled board.** That is where
the composite amplifier meets real parasitics for the first time, and
`hardware/CONTINGENCY.md` is the response if it oscillates or misses the
§3.1 gate.

**The hedge is on the board:**

- the `C_f` footprint, fitted after measuring (§3.1, §14.4);
- alternate-value footprints on `R_B`, `R_sense` and `R_iso` (§14.4). They
  are parallel-only, which fixes the direction each can move
  (`hardware/DECISIONS.md` R4, R6, R8).

**What the risk costs if it lands:** a loop the alternates cannot fix is a
rev 2 (CONTINGENCY §7), with a week or less before Nov 16. The question
Phase 1 existed to ask, the §12 cliff with real stray capacitance at the
inverting node, is still the first thing H4 checks.

### Date gates

Hard dates. Each row is a gate, not a milestone. **The order is event-driven,
not calendar-driven** — it goes out the moment layout is DRC-clean and the
pre-order checklist is clear, which is why the two order rows read "target" and "no later than"
rather than naming one day.

| Date | Gate | Missed → |
|---|---|---|
| ~~Mon Oct 12~~ | ~~Breadboard stability GO/NO-GO (Phase 1)~~ **Dropped Oct 8, 2026** (*Phase 1 dropped*, above) | — |
| **Tue Oct 13** | **Target: design freeze and PCBA ordered**, express shipping. Requires H2 DRC-clean *and* the pre-order checklist clear | Falls through to the two backstop rows below, spending slack |
| **Mon Oct 19** | **Design freeze — backstop.** Schematic and layout final, `hardware/` committed | Slip eats the Oct 20 → Oct 26 slack directly |
| **Tue Oct 20** | **PCBA ordered — no later than this.** Still express | Slack runs to Oct 26 |
| **Mon Oct 26** | **Checkpoint — if not ordered, abandon the PCB and finish on breadboard.** No further extension | — (this *is* the decision point) |
| **Tue Nov 3** | **Boards expected — backstop arrival.** Derived from the Oct 20 backstop order plus 14 days of standard fab + assembly + shipping. The target path beats it twice over: **7 days** from ordering on Oct 13 instead, plus whatever express saves on the shipping leg. Take the real number from the fab's quote at order time rather than trusting either figure here | Re-check against the Nov 16 freeze the day the slip is known, not later |
| **Mon Nov 16** | **Repo freeze** | — |

**Why order early rather than freeze late.** Nothing improves between a
DRC-clean layout and Oct 20 — the board does not get better by being looked
at, and §14.4's whole strategy is to make the uncertain parts *adjustable on
the board* rather than resolved before it. With Phase 1 dropped, the wait buys
nothing at all: every day held is a day subtracted from bring-up.

**Where this plan is tight: the window from arrival to Nov 16.** Against the
Nov 3 backstop that is **13 days**, carrying board bring-up (H4), phases 2 and
3, and phases 4, 5, 7, 8 and 9. The front half of the schedule has 6 days of
ordering slack and the back half has none, so **a slip in arrival comes
straight out of phases 7–9** — extraction, closed-loop validation and the
README, which are the phases the project exists to produce. Two consequences:

- **Express shipping is bought for this reason** (§14.3), not for comfort.
- **Firmware and host work (phases 4, 5, 7) do not depend on the board** and
  should be finished *during* the fab window, against the simulated DUT
  already in `firmware/sim/`, so that arrival day opens with bring-up as the
  only unstarted work.

**The Oct 26 fallback is the old staged breadboard plan.** Stages 7–8 of
`docs/characterization.md` stay in that document for exactly this reason: if
the PCB is abandoned, Phase 1 reverts to its full scope (clamp, limiter,
`R_iso`, load and short tests) and phases 2–3 are built on the breadboard as
originally planned. That path is not deleted, only deprioritised. **It needs a working bench,
which is one of the reasons Phase 1 was dropped.** Until there is one, the
fallback is notional and the board is the only path.

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
├── hardware/              ← KiCad schematic + layout, fab outputs (§14)
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
| Composite amp oscillates | Simulated first (Phase 0). The breadboard GO/NO-GO (Phase 1) was **dropped** on Oct 8, 2026, as an accepted risk (§9). The first test is at H4, with the `C_f` footprint and the parallel alternates on the board and `hardware/CONTINGENCY.md` as the response |
| Noise floor limits low range | Star-ground, short leads, decoupling at every op-amp — §14.5 makes these layout constraints rather than breadboard hygiene. Range 3 is outside MVP scope (§14.2); if it is reached and unusable, report the measured limitation honestly — that's a legitimate finding |
| **One PCB revision, and the analog front end goes to layout validated in simulation only** | `R_iso`, `R_B` and `R_sense` get alternate-value footprints; `C_f` gets a footprint and is fitted after measuring; test points on every §3 node (§14.4). The Oct 26 checkpoint (§9) is the abandon path |
| **Fab slips, or arrival lands late** | Only 13 days separate the Nov 3 backstop arrival from the Nov 16 freeze, and they carry bring-up plus phases 2–9. Three mitigations, all already decided: order **event-driven** the moment layout is DRC-clean (target Oct 13, §9); pay for **express shipping** (§14.3a); and finish phases 4, 5 and 7 against the simulated DUT *during* the fab window, not after |
| STM32 ADC noisier than spec | Oversample; if still poor, add an external ADC (ADS1115) as phase 2 |
| Scope creep into BJT/auto-ranging | Phases 0–9 first. Phase 2 is optional |
| Blown parts stall progress | Duplicates of every active component on hand from day one |
| A model parameter is documented but never applied | Check that changing a parameter changes the output before trusting a result that depends on it — see below |

**A recurring failure mode: the parameter that is accepted but not applied.** Twice now a model has carried a parameter that was documented, accepted, and silently ignored, and both times the simulation output looked correct. In Phase 0 a MODPEX-generated BD139 model had `CJE = CJC = 1e-11` exactly — placeholders standing in for real junction capacitances — and with it the composite amplifier appeared unconditionally stable, hiding the `C_comp` error that the ST model exposed immediately (§12.2). In September 2026 the host simulator's `--rs` flag was parsed, stored, listed in `firmware/README.md`, and never read by the diode current function; the diode nevertheless showed a convincing high-current roll-off from the ideal line, so nothing looked wrong.

The tell was the same both times: **a physical effect appeared, and it was attributed to the wrong cause.** The placeholder `Cjc` did not remove the follower's pole, it just made a different circuit that happened to be stable. The missing `rs` did not remove the roll-off, because `R_iso`'s drop was producing one — the front-end series resistance masquerading as device bulk resistance, and the two are only distinguishable by remembering that the Kelvin sense sits between them.

Neither bug is detectable by reading the output, because the output is plausible. Both are detectable in one step: **sweep the parameter and confirm the result moves.** A parameter that changes nothing is either irrelevant to the question being asked, in which case it should not be in the model, or it is not wired up. The host's diode tests now parametrise over four devices with different `rs` values for exactly this reason, and a zero `rs` is required to come back as *unresolved* rather than as a small number.

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

**Bench items carried forward — split by phase after the §9 restructure.** These go to **H4** as well, since Phase 1 was dropped (§9): measure actual settling, and confirm the loop does not oscillate with real parasitics. To **H4** (PCB bring-up), because stages 7–8 are no longer breadboarded: confirm `R_iso` behavior with the real BD139; verify the current limit trips at **~75 mA** (sim 11; the ~65 mA in earlier drafts was a target, never a measurement — see §3.1), re-measured warm.

---

## 13. Phase 0 results — difference amplifier (completed Sep 18, 2026)

Simulation files: `sim/04_diffamp_cmrr.cir` (worst-case tolerance corner), `sim/05_diffamp_mc.cir` (500-run Monte Carlo), `sim/06_diffamp_loading.cir` (input loading, unbuffered), `sim/07_diffamp_buffered.cir` (input loading, buffered). Per-file detail in `sim/README.md`.

**1. CMRR at the worst-case corner is set by resistor tolerance.** Skewing all four resistors to the worst sign pattern gives **134.40 dB** at `t` = 1e-6, **74.42 dB** at 0.1%, and **54.57 dB** at 1%. The 1e-6 row is a **solver-floor control, not a result** — it confirms numerical noise sits far below the rows that matter. Closed form for this corner: `A_cm = 80t/[(1-t²)(1+b)]` with `b = 20(1+t)/(1-t)`; the familiar `(1+G)/(4t)` shortcut agrees within 0.02 dB at 0.1%.

**2. Report the distribution, not a single number.** 500 runs at 0.1% (n = 500): min **76.20**, p5 **79.43**, median **88.26**, p95 **110.51**, max **144.73** dB. The worst-case 74.4 dB is the floor to design against; 88 dB is what a typical build gets. Note that LTspice's `mc()` draws **uniform and independent** values, whereas real reel-matched resistors are both tighter and correlated — so this spread is **conservative**. **Do not cite the max**; it is one lucky draw, not a spec. Histogram: `media/cmrr_mc.png`.

**3. The unbuffered difference amp loads the shunt — this is the finding that changes the BOM.** With **no DUT connected at all**, the bare four-resistor bridge draws current through the shunt: `V(out)` = **9.512 mV** at `Rsh` = 1 Ω, i.e. **475.6 µA** of phantom current. In general `I_err = 0.476/(1000 + Rsh)` A. Against full scale that is **0.95% / 43% / 433%** on ranges 1 / 2 / 3. Range 3 is not merely inaccurate, it is unusable — the unbuffered output sits at **8.66 V** at `Rsh` = 10 kΩ, near the rail on a 15 V supply.

**4. Conclusion: unity-gain input buffers are required.** Move to the **3-op-amp instrumentation topology**. The op-amp count goes from four channels to six — sweep, gate, two input buffers, the difference stage and the Kelvin buffer — so from 2 to 3 × OPA2197 (§8). This is a functional requirement for range 3, not an accuracy refinement.

**5. What sim 07 does and does not show.** The buffered netlist returns `V(out)` = **0 at all three `Rsh` values**. That zero comes from **ideal `E`-source buffers, which draw no input current by construction** — it confirms the topology is wired as intended and that the bridge no longer loads the shunt, and **nothing more**. It is **not** evidence of any particular bias-current performance. The real residual is the **OPA2197 input bias current, ~5 pA typical — a datasheet figure, not a simulated one**. Sizing it properly requires swapping the `E` sources for the vendor OPA2197 model.

**Method note.** This LTspice is the Windows build in a CrossOver bottle; `-b` against the `/Applications` binary exits 0 without simulating. The working headless invocation is recorded in `sim/README.md`. `.meas` on a stepped `.op` logs only the first step, so per-step values come from the `.raw` file — and `.raw` is float32 while `.meas` is double (§3.5).

**Bench items carried forward to H4 / Phase 2 — on the PCB, not a breadboard** (§9: no breadboard phase remains): verify the buffered difference amp's actual CMRR against the 74.4 dB floor with real 0.1% parts; measure input bias current contribution directly rather than trusting the datasheet typ. The range-3 usability question moves with it, and is now **outside MVP scope** (§14.2) — the buffers are still required, because unbuffered error is 0.95% on range 1 alone.

---

## 14. PCB revision

**Decided Oct 5, 2026.** The project targets an assembled PCB by Nov 16, not a
breadboard. §9 carries the phases and dates; this section carries the why, the
scope, and the constraints the layout has to honour.

### 14.1 Why

**The deliverable is a usable instrument, not a demonstration rig.** A
breadboard that produces one good curve family proves the design closes; it
does not produce a thing that can be picked up and used, and it cannot be
honestly photographed as one. Every §7 accuracy figure is also easier to
defend on a board: §11 already lists "breadboard noise floor limits low range"
as a live risk with "report the measured limitation honestly" as its
mitigation, which is a graceful way of saying range 3 might not work. A board
with a star ground and short feedback traces removes the excuse rather than
documenting it.

The breadboard keeps exactly one job — the Phase 1 stability GO/NO-GO — because
that is the one question a PCB answers *worse*: it is unchangeable once
fabricated, and §12 found this loop fails by cliff.

**Update, Oct 8, 2026: it no longer has even that job.** Phase 1 was dropped
(§9): no ≥ 8 MHz DIP-8 part, no working bench, and the narrowed gate tested
only the bare loop on a substitute. The reason above still holds. A PCB
answers the stability question worse because it cannot be changed, which is
why the board carries the `C_f` footprint and the alternate values, and why
`hardware/CONTINGENCY.md` exists.

### 14.2 Scope

**MVP only.** Identical to the scope `firmware/README.md` already states:

- **Range 1 is the only range inside the Nov 16 gate** (1 Ω shunt, 1–50 mA).
  **The board nevertheless carries all three shunts — 1 Ω, 100 Ω and 10 kΩ —
  and §3.3's 3-pin selection header.** All three are populated, deliberately:
  the point is that **reaching ranges 2–3 must not require a board
  revision**, and there is only one revision. Three resistors and a header are
  the cheapest insurance on the board. §8 already carries all three values
  (the 1 Ω 1% 1 W shunt, and 100 Ω and 10 kΩ from the 0.1% assortment), so
  this costs nothing in the BOM either. What is *not* in the MVP is the
  switching: selection is the manual jumper, and only range 1 is validated.
- **DC sweep only.**
- **No auto-ranging.** No relays. §3.3's relay auto-ranging stays Phase 2.
- **No pulsed mode.** Phase 6 is dropped from the MVP (§9). Note the §3.5
  consequence: with the sweep DAC on `DAC2_OUT1`/PA6 and the gate on
  `DAC1_OUT1`/PA4, the two channels cannot take a synchronised dual-channel
  update, so restoring pulsed mode later needs rework around LD2 regardless.
  Dropping it now costs nothing that was reachable anyway.

Anything not on this list is not on the board. Scope creep here does not cost
timeline, it costs a **board revision**, and there is only one.

### 14.3 Assembly: PCBA

**Assembled by the fab, not by hand.** The driver is §8: the OPA2197 has no DIP
package and ships SOIC-8 / VSSOP-8 only, and the board needs three of them
(six channels: sweep, gate, two input buffers, the difference stage and the
Kelvin buffer).
Hand-soldering SOIC is **not a skill I have, and acquiring it on the critical
path is the wrong place to learn it** — a cold joint on an op-amp supply pin
presents as a stability or offset problem, i.e. as a *design* fault, and
debugging it would burn the arrival-to-freeze window — 13 days against the
Nov 3 backstop (§9) — diagnosing the assembly instead of the circuit.

**The SOIC-8 adapters are off the critical path.** An earlier draft of this
section had the Oct 12 GO/NO-GO requiring an OPA2197, which on a breadboard
means a SOIC-8-to-DIP adapter — the hand-soldering this section just declined,
needed in the same week as the gate it was blocking. **That requirement is
withdrawn.** Since the board is assembled by the fab, every OPA2197 that
matters arrives already soldered, and the adapters become a **nice-to-have**:
useful for bench experiments after bring-up, not a prerequisite for anything
dated. Buy them or don't; nothing in §9 waits on them.

*Superseded Oct 8, 2026: Phase 1 was dropped (§9). The reasoning below stays as the
record of what the gate could and could not have shown.*

**What Phase 1 runs on instead: the fastest DIP-8 op-amp in the lab, ≥8 MHz
GBW.** The justification is the narrowing in §9. Phase 1 tests the **§12
cliff at light load** — does the bare loop, with real breadboard stray
capacitance at the inverting node, oscillate at all — and it does **not**
measure the §3.1 overshoot spec, which needs `R_iso`, the clamp and a 100 nF
load and has moved to H4. A gate that narrow cannot justify putting
hand-soldered SOIC on the critical path.

**The question being asked is GBW against the follower pole, and that is what
the ≥8 MHz threshold protects.** Closed-loop crossover is roughly GBW / 3.32:

| Part | GBW | ≈ crossover | vs. the 2–3 MHz stray pole |
|---|---|---|---|
| OPA2197 (design part) | 10 MHz | ~3.0 MHz | the pole sits *at* crossover — §3.1 |
| **≥8 MHz DIP-8 substitute** | ≥8 MHz | **≥2.4 MHz** | still inside the band — **the question survives** |
| LM324 | 1.3 MHz | ~0.39 MHz | ~8× below it — **the pole is invisible** |

That is the whole criterion. At ≥8 MHz the substitute's crossover lands inside
the same 2–3 MHz band where §3.1 puts the stray pole, so the interaction Phase 1
exists to find is still in range. **The LM324 remains unsuitable** — and not
only for its 0.4 V/µs slew rate (§8), but for the more basic reason that its
crossover sits nearly an order of magnitude below the pole, so a quiet LM324
loop is evidence of nothing.

**This changes the supply topology, not the question.** Most fast DIP-8 parts
do not include ground in their input common-mode range, which single-supply
operation requires — the same property that ruled out the TL074 in §8. So the
Phase 1 breadboard may need to run on a **dual supply** where the design runs
on +15 V single. Record it when logging the result: the rails differ from the
design, and therefore **no DC figure from Phase 1 — offset, output swing near
ground, low-end linearity — transfers to the board.** The stability question
does transfer, because it is set by GBW and the loop's poles, and neither
depends on where the negative rail sits.

### 14.3a Cost

§8's **~$115** is the parts BOM and **excludes the board entirely** — no fab,
no assembly, no shipping. The real project cost is that plus:

| Item | Note |
|---|---|
| PCB fab + PCBA | Assembly is the §14.3 decision; quote at order time |
| **Express fab shipping** | **Bought deliberately.** See below |
| Stencil / setup fees, if the fab charges them | Quote at order time |

**Why express shipping is not optional.** The schedule's slack is all in the
front half: 6 days between the Oct 13 order target and the Oct 20 backstop,
and **zero** between arrival and the Nov 16 freeze (§9). Standard shipping
spends a week of the one window that has no give, and it spends it on the
phases the project exists to produce — extraction, closed-loop validation and
the README. **A week of fab time is worth more than $30**, and the trade is
not close: $30 is about a quarter of the parts BOM, while a week is more than
half the 13-day backstop window. Order express even if the layout finishes
early; arriving early is itself the hedge against bring-up going badly.

### 14.4 One revision only — design for it

There is budget for **one** board. The design therefore spends area and parts
on adjustability wherever a simulated result has not been confirmed on
hardware, which after the §9 restructure is most of the analog front end.

- **Test points on every node §3 names.** At minimum: op-amp output, BD139
  base, BD139 emitter, the `R_sense` feedback tap, the load node after
  `R_iso`, the inverting-input node, +15 V and +3.3 V rails, star-ground
  reference, both shunt terminals, difference-amp output (ADC1), both Kelvin
  sense lines at the DUT, divider/buffer output (ADC2), gate-source output,
  and both PTC terminals. A node that cannot be scoped cannot be debugged, and
  there is no second board on which to add the pad.
- **Footprints for alternate values wherever a sim result is uncertain.**
  Specifically `R_iso` (22 Ω, never confirmed on hardware — stage 8 was never
  reached), `R_B` (330 Ω, chosen over 680 Ω on a simulated 10.3% vs 21.4%
  overshoot that no bench measurement has checked), and `R_sense` (10 Ω, which
  sets the limiter trip at a threshold whose −2 mV/°C drift §3.1 flags as "the
  figure most likely to disagree with simulation").
- **Headers, not soldered connections**, for the supply, the DUT socket, the
  shunt selection, and the Kelvin leads.
- **The Nucleo sits on headers, not soldered down.** It is $18 of the BOM and
  the single most likely part to be swapped (F303RE ↔ G474RE, §3.5) or
  destroyed.

**`C_f` gets a footprint even though its value is not yet knowable.** §3.1
sizes it at **2–4 pF** from `C_f = C_in · R_g / R_f`, and `C_in` is known only
as 5–10 pF — a 2× uncertainty that puts the exact value anywhere in
2.16–4.31 pF. On a PCB the breadboard rows are gone, but the
estimate never counted the op-amp's own input capacitance, which then
dominates: §3.1's design finding puts the PCB `C_in` at ~5–9 pF and `C_f` at
2.2–3.9 pF. So the value cannot be
chosen before the board exists: **place the footprint, leave it unstuffed, and
fit `C_f` after measuring, per §3.1.** Bring-up sweeps it in both directions —
§3.1's residual table is two-sided, and below ~7.5 pF of `C_in` a 3.3 pF `C_f`
*over*-compensates, which is the §12 failure mode rather than a milder version
of the under-compensated one. Keep the pads close to `R_f`; a footprint reached
by a long trace adds its own stray capacitance to the node it is correcting.

### 14.5 Layout constraints — not negotiable

These come out of §3.1 and are the reason the analog nets are hand-routed
rather than autorouted (`hardware/README.md`).

1. **The feedback trace from the `R_sense` tap back to the op-amp inverting
   input must be short, and must not run near the collector.** It is a
   high-impedance node (`R_f ‖ R_g` = 7 kΩ) carrying the loop's only error
   signal, and the collector is the node with the largest `dV/dt` and the full
   load current.
2. **Minimise stray capacitance at the inverting node.** This is not a
   general tidiness request: §3.1 identifies it as the pole at **2–3 MHz**,
   which sits **right at the ~3 MHz crossover**. It is the single parasitic
   that can cost ~45° of phase margin, and `C_f` only partly cancels it. No
   ground pour under the inverting-input node or under `R_f`/`R_g`; keep the
   copper at that node to the minimum the pads require.
3. **Decoupling within ~5 mm of the BD139 collector and of every op-amp supply
   pin.** 100 nF ceramic each (§8), plus the bulk 10 µF on the rail. "Within
   5 mm" means the cap body, measured along the actual trace, not the
   schematic.
4. **Star ground.** One reference point. The BD139 emitter/`R_sense` return
   carries up to 107 mA into a hard short (§3.1) and must not share copper
   with the difference-amp or Kelvin returns — a shared millohm of return
   impedance at 107 mA is millivolts injected directly into a sense path whose
   range-3 full scale is 100 mV.

Two further constraints follow from §3 and are recorded here so layout does not
have to rediscover them:

5. **The feedback tap goes after `R_sense` and before `R_iso`.** §3.1 is
   explicit in both directions: tapping ahead of `R_sense` puts the sense drop
   inside the loop and the limiter never trips; tapping after `R_iso` puts the
   load pole back inside the loop and undoes the Phase 0 fix. The tap point is
   a single via's worth of freedom and it has exactly one correct position.
6. **The shunt is Kelvin-connected and its two sense traces run as a matched
   differential pair** to the difference-amp inputs. §13 puts worst-case CMRR
   at 74.4 dB from resistor tolerance alone; asymmetric sense routing degrades
   it further and is not recoverable by trimming.

### 14.6 Carried-forward consequences

Recorded so they are not rediscovered during bring-up:

- The BD139's **tab is the collector and is live at +15 V** (§8). On a PCB this
  means the heatsink is at +15 V: it cannot touch a grounded enclosure, cannot
  be shared, and needs clearance to every adjacent net. TO-126 footprint, not
  TO-220 — different tab and hole pattern.
- Worst-case BD139 dissipation is **~0.89 W** sustained (§3.1), set by
  `R_sense` alone. The TO-126 heatsink must fit in the layout, with its
  keep-out drawn, before the board is called frozen.
- **§3.6's short-recovery overshoot reaches 14.8 V at the load node on a 10 V
  setpoint** (+48%, structural, every `R_B`/`R_sense` pair). Its mitigation is
  now D3, an SMAJ12A TVS, fitted if H4 step 15 reads above 12 V (§3.6). On a one-revision board, place the ADC clamp diodes
  (BAT54S) and the gate Zener before freeze and leave a footprint for an output
  clamp at the DUT socket, even if it ships unstuffed.
