# Semiconductor Curve Tracer — Build Blueprint

**One-line:** A programmable instrument that sweeps bias across a semiconductor device, measures its I-V characteristics across ~5 decades of current, exports data, and extracts SPICE model parameters.

**Why it's the project:** it closes the loop `physics → measurement → model → design → verification` on a breadboard. Measure a real MOSFET, extract its parameters, simulate a circuit in LTspice with *your* model, build that circuit, show simulation matches bench.

---

## 1. Specifications (target)

| Parameter | Target | Notes |
|---|---|---|
| Sweep voltage (V_DS / V_AK) | 0 – 10 V | 4096 steps (12-bit DAC), ~2.7 mV/step |
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

  DAC2 ──► [scale ×3.33] ──► [composite power buffer] ──► [shunt] ──┬──► DUT drain
                                                          │         │
                                                    [diff amp]   [Kelvin sense
                                                          │        + divider + buffer]
                                                        ADC1          │
                                                                    ADC2
  DAC1 ──► [scale ×3.33] ──► [buffer] ──────────────────────────► DUT gate

                                                   DUT source ──► GND
```

**Signal flow per measurement point:** set gate DAC → set drain DAC → wait settle → oversample both ADCs → record → (pulsed mode: return drain to 0) → next point.

---

## 3. Block-by-block design

### 3.1 Sweep source (the hard block)

DAC output is 0–3.3 V at ~5 mA drive. Needs to become 0–10 V at 50 mA.

**Topology:** non-inverting amp (gain 3.33) with an emitter-follower pass transistor **inside the feedback loop** (composite amplifier). Feedback taken from the follower's emitter, so the op-amp corrects the follower's V_BE drop and nonlinearity.

| Component | Value | Rationale |
|---|---|---|
| Op-amp | OPA2197 (or OPA2196) | 36 V supply capable, rail-to-rail, precision |
| Supply | +15 V single | Headroom above 10 V output |
| Gain resistors | R_f = 23.3 kΩ, R_g = 10 kΩ, 0.1% | Gain = 3.33 |
| Pass transistor | BD139 or TIP31C, on heatsink | Worst-case dissipation ~0.75 W |
| Base resistor | 100 Ω | Damps follower, limits op-amp output current |
| Isolation resistor | `R_iso` = 22 Ω, emitter → load | **Required for stability — see Phase 0 findings** |
| Compensation cap | ~~10–100 pF across R_f~~ | **REMOVED — destabilizes this topology (Phase 0)** |

**Design issue you will actually hit — corrected by Phase 0 simulation:**

The follower adds a pole inside the loop, but the problem is not what the original plan assumed.

A cap across `R_f` is *transimpedance* compensation. It works in a TIA because the noise gain rises with frequency and `C_f` cancels that rise. This circuit is a non-inverting voltage amp with a resistive divider: `β = Z_g/(Z_g+Z_f)`. A cap across `R_f` lowers `Z_f` at high frequency, pushing `β` toward 1 and *raising* loop gain exactly where the follower's phase lag sits. Simulation confirmed it makes things worse monotonically.

**The actual fix is `R_iso`:** a 22 Ω series resistor between the emitter and the load node, with `R_f` feedback tapped on the **emitter side**. The load pole then sits outside the feedback loop where it costs no phase margin.

**Trade-off:** `R_iso`'s drop is outside the loop and therefore uncorrected — 1.1 V at 50 mA. Harmless here *only because* `V_DS` is Kelvin-sensed at the DUT (§3.4). The stability fix and the Kelvin-sensing requirement are coupled decisions, not independent ones.

**Current limiting:** series 10 Ω sense resistor in the pass transistor emitter + a second transistor whose base-emitter sees that drop; at ~65 mA it turns on and steals base drive. Simple foldback protection. Non-negotiable — students and mistakes will short the DUT terminals.

### 3.2 Gate / step source

Same scaling (×3.33) but no power buffer — MOSFET gates draw essentially no DC current. A single OPA2197 channel suffices.

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

**Difference amp:** discrete, four resistors around one op-amp.

- `R1 = R3 = 1 kΩ`, `R2 = R4 = 20 kΩ`, all **0.1%** → gain 20.
- **CMRR is set by resistor matching, not the op-amp.** `CMRR ≈ (1 + R2/R1) / (4t)`. At `t = 0.1%`: ~74 dB. At `t = 1%`: ~54 dB. Measure both and put the comparison in the README — it's a clean, quantitative result.
- Optional phase 2: swap in an INA828 instrumentation amp and compare measured CMRR against your discrete build.

### 3.4 Voltage sense (Kelvin)

Because shunt burden voltage can reach 100 mV, the voltage across the DUT is **not** the sweep source output. Sense `V_DS` directly at the DUT terminals with separate wires.

Divider `÷4` (30 kΩ / 10 kΩ, 0.1%) into a unity-gain buffer (high input Z so the divider doesn't load the DUT) into ADC2.

This is a genuine four-wire measurement, and explaining why it's necessary is a strong README paragraph.

### 3.5 ADC and MCU

**Board:** Nucleo-F303RE (2× 12-bit DAC, 4× fast ADC, plentiful RAM) or Nucleo-G474RE. Both have the DAC peripheral — many STM32 lines do not. Verify before ordering.

**ADC config:** 12-bit, longest sampling time, VREF from the board's 3.3 V rail. Add a `10 nF` cap at each ADC pin and clamp diodes (BAT54S) to rails for protection.

**Oversampling:** average 64 samples per point → ~3 extra effective bits (~15-bit) at the cost of ~1 ms per point. Standard `√N` noise averaging; state the measured improvement in the README rather than assuming it.

### 3.6 Protection (required, not optional)

- Foldback current limit on the sweep source (§3.1)
- Series PTC resettable fuse (100 mA hold) in the drain path
- Clamp diodes on both ADC inputs
- Gate series resistor (1 kΩ) + Zener clamp to protect against ESD-sensitive parts
- DUT socket: 3-pin ZIF or screw terminal, clearly labeled G/D/S

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
        emit_csv(V_GS, V, I, range)
        if pulsed_mode: set DAC2 = 0; delay(duty_off_us)
    set DAC2 = 0
```

**Key parameters to expose and tune:**

| Parameter | Starting value | Why it matters |
|---|---|---|
| `settle_us` | 20 µs | Sweep source settles in ~1.3 µs (Phase 0); the binding constraint is DUT settling and thermal response, not the amplifier |
| `N` (points/sweep) | 200 | Tradeoff: resolution vs. total sweep time vs. heating |
| `duty_off_us` | 10 ms | Pulsed mode: lets the DUT cool between points |
| `oversample_n` | 64 | Noise floor vs. speed |

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
| OPA2197 (dual, 36 V, precision) | 3 | $18 |
| BD139 / TIP31C + TO-220 heatsink | 2 | $4 |
| 0.1% resistor assortment (1 k, 10 k, 20 k, 23.3 k, 30 k, 100 Ω, 10 k shunt) | — | $15 |
| 1 Ω 1% 1 W shunt | 2 | $2 |
| 15 V / 1 A wall adapter + barrel jack | 1 | $10 |
| 22 Ω 1% (`R_iso`) | 5 | $1 |
| BAT54S clamp diodes | 10 | $3 |
| PTC resettable fuse, 100 mA | 5 | $3 |
| DUT devices: 2N7000, BS170, 2N3904, 1N4148, LEDs, Zeners | — | $8 |
| Small-signal relays (phase 2 auto-ranging) | 3 | $9 |
| Breadboard, jumpers, headers | — | on hand |
| **Total** | | **~$90** |

Order **two of every active component.** You will destroy at least one op-amp and one pass transistor.

---

## 9. Build phases

| Phase | Deliverable | Gate to proceed |
|---|---|---|
| **0** | ~~LTspice model of sweep source~~ **DONE** — see §12; diff amp CMRR sim still open | Sweep source settles cleanly into ≥100 nF with `R_iso` |
| **1** | Sweep source on breadboard, current limit working | 0–10 V linear, foldback trips at ~65 mA |
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

**Still open in Phase 0:** difference amplifier CMRR simulation (ideal vs 1% vs 0.1% resistor mismatch). Note that `(1+R2/R1)/(4t)` is the four-resistor worst case (~74 dB at 0.1%); perturbing a single resistor gives ~86 dB. Report both and label which is which.

**Bench items carried forward to Phase 1:** confirm `R_iso` behavior with the real BD139 and real breadboard parasitics; measure actual settling; verify foldback trips at ~65 mA.
