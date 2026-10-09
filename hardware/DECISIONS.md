# hardware/DECISIONS.md — where every value on the board came from

One row per component on `curve-tracer.kicad_sch`. Each symbol carries a
`Provenance` field pointing at its row here, so the schematic and this file
cannot drift apart silently.

Written during capture, Oct 5, 2026 (phase H1). Update it in the same commit
as any value change, and say which column moved.

## How to read it

| Source tag | Meaning |
|---|---|
| **Blueprint §x** | The value is stated in `curve_tracer_blueprint.md`. The blueprint is the design record; the row says which paragraph |
| **Sim NN** | The value was chosen on, or confirmed by, an LTspice run in `sim/`. Figures are recorded measurements, quoted from `sim/README.md` with the run date. Do not rescale them by hand |
| **Bench** | Measured on hardware, with the `docs/characterization.md` session date |
| **Datasheet** | Taken from a manufacturer document, named with table or figure |
| **Capture** | Decided while drawing the schematic, because §3 was silent or self-contradictory. Listed under [Capture decisions](#capture-decisions) with their sign-off status |
| **Decision** | Set by Daniel after capture, with the date. The reasoning is quoted in the row |

**No bench measurement on the intended parts exists yet.** The two bench
sessions so far (2026-09-18, stage 3; 2026-09-24, stage 4, no data) were
substitute-part shakedowns and never powered a circuit with these values. So
the **Bench** column is empty on every row. Instead it names the bench
measurement that would confirm the value or move it, and the phase where
that happens.

**Simulations were run at `R_f` = 23.3 kΩ**, not the 23.2 kΩ fitted here. That
is 0.3% in `R_f + R_g`, below the precision of every quoted figure, so the
sims were deliberately not re-run (`docs/characterization.md`, 2026-09-18
entry). Read every Sim figure below with that in mind.

---

## Sweep source — blueprint §3.1

| Ref | Part | Value | Source | Evidence | Bench: what confirms or moves it |
|---|---|---|---|---|---|
| <a id="u1"></a>U1 (A) | OPA2197IDR | — | Blueprint §3.1, §8 | 36 V, RRIO, 10 MHz GBW. The fab fits it (§14.3) | H4 stability gate on the board |
| <a id="r1"></a>R1 | R_f | **23.2 kΩ 0.1%** | Blueprint §3.1 | Gain `1 + 23.2/10` = **3.32**. 23.2 kΩ is the E96 neighbour of the never-orderable 23.3 kΩ. Sims 01–11 ran at 23.3 kΩ (see above). 0603, so the pads add as little as possible to the inverting node (§14.5(2)) | Gain ratio at H4. **Not** the 2026-09-18 bench reading: that session used 5% stand-ins measured at 19.34 k / 9.74 k |
| <a id="r2"></a>R2 | R_g | **10 kΩ 0.1%** | Blueprint §3.1 | As R1 | As R1 |
| <a id="c1"></a>C1 | C_f | **DNP**, footprint only | Blueprint §3.1, §14.4 | `C_f = C_in · R_g / R_f`. The breadboard estimate (`C_in` = 5–10 pF) gave 2.16–4.31 pF. On the PCB the strays shrink, but the OPA2197's own input capacitance dominates: `C_in` ≈ 5–9 pF, so **`C_f` ≈ 2.2–3.9 pF** (3.3–3.9 if TI's 6.4 pF is per input; blueprint §3.1, design finding Oct 8, 2026). Fitted at H4 from a measurement (`CONTINGENCY.md` §2) | **H4**: measure, fit, then sweep both directions. Overshoot near 25% means re-fit `C_f`, not "marginal loop" (§3.1 diagnostic) |
| <a id="r3"></a>R3 | R_B | **330 Ω** 1%, 2512 1 W | Blueprint §3.1. Sims 08, 09, 10, 11. Package: Capture C-3 | **Why 330 and not 680:** sim 08 (re-run 2026-09-22) gives 10.3% small-signal overshoot into 100 nF / 200 Ω at 330 Ω (ζ ≈ 0.59, ~59° PM) against 21.4% at 680 Ω (~44°). The un-simulated 2–3 MHz stray input pole costs ~45°, which is recoverable from 59° with `C_f` and not from 44°. **Why not 100 Ω:** sim 10 (2026-09-18) gives a held-short load current of 107 mA at 330 Ω against 143 mA at 100 Ω, and at 330 Ω the op-amp supplies 32 mA, outside its own 65 mA limit. Clamp discharge peaks at 21.9 mA (sim 09). 680 Ω would have bought nothing that still matters (§3.1, PTC reclassified) | H4: overshoot into 100 nF, with `C_f` swept. With the limiter tripped, the drop across R_B gives op-amp current, to confirm it is out of its limit (§3.1) |
| <a id="r4"></a>R4 | R_B alt | **DNP**, THT axial parallel to R3 | Blueprint §14.4 | 330 Ω was chosen over 680 Ω on a sim-only overshoot difference that no bench measurement has checked. The footprint takes the 0207/0309 axial parts already on hand (§8: 330 Ω ×5) without SMD rework, but only **in parallel, so only downward**. Any value above the SMD part's needs the SMD part removed first. That applies to R6 and R8 as well | **Parallel only: fitting R4 lowers R_B** (330 ‖ 330 = 165 Ω), the right direction for excess overshoot (sim 08). Re-testing 680 Ω, or any value above 330 Ω, means removing R3 and fitting the axial alone (`CONTINGENCY.md` §4) |
| <a id="q1"></a>Q1 | BD139 (ST) | — | Blueprint §3.1, §8. Substitution S-2 | Pass transistor, TO-126. Tab = collector = +15 V. Worst-case dissipation **0.89 W** (sim 11, hard short). **Layout-time check (H2):** ST and onsemi number this part's pins in opposite directions — see [L-1](#layout-time-checks) | H4: thermal under a sustained short |
| <a id="d1"></a>D1 | 1N4148W | — | Blueprint §3.1. Sim 09. Substitution S-3 | B-E clamp, anode at emitter. Unclamped, V_BE reaches −6.3 V (100 pF open) and −9.0 V (100 nF open) against `V_EBO` = 5 V (sim 08). Clamped: −0.58 / −0.74 V (sim 09, 2026-09-18) | H4: falling edge into 100 pF open, against sim 09's 1.7 µs |
| <a id="q2"></a>Q2 | MMBT3904 (JSCJ, C20526, Basic) | — | Sims 10, 11 (§3.1 names only "a second transistor"). Substitution S-4 | Sims use the 2N3904. The fitted Rohm SST3904 model (SOT-23) agrees within 2% (sim 10). V_BE ≈ 752 mV at R_B = 330 Ω (sim 11). Dissipates 53 mW in a held short (sim 10) | H4: trip point, re-measured warm (−2 mV/°C) |
| <a id="r5"></a>R5 | R_sense | **10 Ω** 1%, 1206 0.75 W | Blueprint §3.1. Sim 11. Package: Capture C-3 | Threshold `V_BE / R_sense` = **75.2 mA** (sim 11, 2026-09-18), 50% over the 50 mA spec. 15 Ω is rejected because its threshold of 48.8–50.2 mA sits inside the sweep spec. 12 Ω is rejected on thermal margin: −2 mV/°C over a 20 °C rise takes it to ~57.6 mA, 15% clear (analysis, §3.1). Dissipation 57 mW at the threshold | **H4: trip threshold, cold and warm.** §3.1 calls the drift "the figure most likely to disagree with simulation" |
| <a id="r6"></a>R6 | R_sense alt | **DNP**, THT axial parallel to R5 | Blueprint §14.4 | As R4. §8 has 10 Ω ×5 on hand | **Parallel only: fitting R6 lowers R_sense and raises the trip**, so it corrects a trip that reads *low*. A trip that reads high needs R5 removed and a larger axial fitted alone. Not a stability lever (`CONTINGENCY.md` §4) |
| <a id="r7"></a>R7 | R_iso | **22 Ω** 1%, 2512 1 W | Blueprint §3.1. Phase 0 sim 03 (§12, item 4). Package: Capture C-3 | With 22 Ω, the loop is clean at the emitter and the output from 100 pF to 100 nF. Bare, it is stable only to ~1 nF and oscillates by 2.2 nF. Drop of 1.10 V at 50 mA is uncorrected and made harmless by Kelvin sensing (§3.4). Dissipation 252 mW in a hard short (107 mA, sim 10) | **H4.** Never confirmed on hardware: stage 8 was never reached |
| <a id="r8"></a>R8 | R_iso alt | **DNP**, THT axial parallel to R7 | Blueprint §14.4 | As R4. §8 has 22 Ω ×5 on hand | **Parallel only: fitting R8 lowers R_iso**, toward the bare loop that oscillated by 2.2 nF (§12, item 4). That is not a response to ringing. To *raise* R_iso for ringing into 100 nF, remove R7 and fit the axial alone: **47 Ω**, the only raise value stocked (README shopping list). Then update `CT_R_ISO_OHM` (`CONTINGENCY.md` A6, §4) |
| <a id="c2"></a>C2 | Decoupling, BD139 collector | **100 nF** X7R 50 V | Blueprint §8, §14.5(3) | Within ~5 mm of the collector, measured along the trace | — |
| <a id="r23"></a>R23 | Pull-down, DAC_SWEEP | **DNP, value open** | Capture C-6 | — | — |

## Gate / step source — blueprint §3.2, §3.6

| Ref | Part | Value | Source | Evidence | Bench |
|---|---|---|---|---|---|
| U1 (B) | OPA2197IDR | — | Blueprint §3.2 | "A single OPA2197 channel suffices" | — |
| <a id="r9"></a>R9 | R_f, gate | **23.2 kΩ 0.1%** | Blueprint §3.2, §8 | Same scaling as the sweep. §8: "both channels use it, so the BOM carries one value" | Gate gain at H4 |
| <a id="r10"></a>R10 | R_g, gate | **10 kΩ 0.1%** | Blueprint §3.2 (same ×3.32 scaling) | — | — |
| <a id="r11"></a>R11 | Gate series R | **1 kΩ** 1%, 2512 1 W | Blueprint §3.6. Package: Capture C-3 | Value from §3.6. A DUT with a gate-source short puts up to ~14.6 V across it (op-amp at rail), which is **0.21 W**. That is why it is a 2512 | — |
| <a id="d2"></a>D2 | Gate Zener | **12 V**, BZT52C12, SOD-123, 500 mW (MDD, C173429) | Blueprint §3.6 (part type). **Decision, 2026-10-06** (voltage, package, rating) | Daniel: "the gate source swings to ~11 V, so a lower clamp conducts in normal operation; 2N7000 V_GS limit is ±20 V." **Margin below:** gate full scale 3.3 V × 3.32 = 10.956 V against V_Z min 11.4 V (at I_ZT = 5 mA) → **0.44 V**. Leakage is specified only to V_R = 9 V (0.1 µA max). At 10.96 V the knee current is unspecified, and any that flows shows up as I × 1 kΩ at the gate. **Margin above:** V_Z max 12.6 V against the 2N7000's ±20 V V_GS → **7.4 V**. **Fault:** with the op-amp near its 15 V rail, 2.0–3.2 mA flows, 25–37 mW in a 500 mW part. JLCPCB's *preferred* BZT52C12 (C19077410) is 350 mW, so it fails the ≥500 mW requirement | **H4:** at full-scale gate code, any difference between TP16 (GATE_AMP) and TP18 (DUT_G) is Zener knee current × 1 kΩ |
| <a id="r24"></a>R24 | Pull-down, DAC_GATE | **DNP, value open** | Capture C-6 | — | — |

## Drain path — blueprint §3.3, §3.6, §14.2

| Ref | Part | Value | Source | Evidence | Bench |
|---|---|---|---|---|---|
| <a id="f1"></a>F1 | PTC | **100 mA hold** | Blueprint §3.6. **Substitution S-1, accepted 2026-10-06** | Fault and fire backstop against a failed limiter only. It does not protect the DUT (§3.6). Its 1.6–15 Ω is now in the §1 / §3.1 headroom figure | **H4:** measure R_PTC as the TP5 → TP17 drop at a known current. Re-measure after any trip |
| <a id="r12"></a>R12 | Shunt, range 1 | **1 Ω 1% 1 W** | Blueprint §3.3, §8 | 50 mV burden at 50 mA | **Phase 2**: reads a known resistor within 1% |
| <a id="r13"></a>R13 | Shunt, range 2 | **100 Ω 0.1%** | Blueprint §3.3, §14.2 | Fitted although range 2 is outside the MVP, so reaching it needs no board revision | Phase 3, if reached |
| <a id="r14"></a>R14 | Shunt, range 3 | **10 kΩ 0.1%** | Blueprint §3.3, §14.2 | As R13 | Phase 3, if reached |
| <a id="j3"></a>J3 | Range select, force | 2×3 header | Capture C-1, **accepted 2026-10-06** | Footprint `curve-tracer:PinHeader_2x03_P2.54mm_Vertical_RangeSelect` puts RNG1–RNG3 against each row and "J3+J4: SAME POSITION" on the silkscreen | — |
| <a id="j4"></a>J4 | Range select, sense | 2×3 header | Capture C-1, **accepted 2026-10-06** | Same footprint and silkscreen as J3 | — |
| <a id="nt1"></a>NT1 | Net tie, SHUNT_LO | — | **Capture C-2** | Kelvin tap at R12's pad (§14.5(6)) | — |
| <a id="j6"></a>J6 | DUT socket | 3-pin screw terminal, 5.0 mm | Blueprint §3.6 ("3-pin ZIF or screw terminal, clearly labeled G/D/S"), §14.4 | Pin 1 G, 2 D, 3 S | — |
| <a id="d3"></a>D3 | Output clamp | **DNP, type open** | Blueprint §14.6 | Footprint for §3.6's +48% short-recovery overshoot: 14.8 V at the socket on a 10 V setpoint (sim 10, peak trustworthy, duration not). Mitigation unresolved — open O-3. **Fit threshold (Daniel, 2026-10-09): 12 V peak at the DUT node.** §1 caps the instrument at 10 V and every DUT is selected against that ceiling; sim 10 measured 14.8 V at 100 pF. 12 V gives 20% headroom over spec while still catching the structural overshoot. **The part is still open (O-3):** a step-15 failure needs one chosen before it can be fitted | **H4 step 15** (`H4_CARD.md`): peak ≤ 12.0 V, record and continue; > 12.0 V, fit D3 |
| <a id="j5"></a>J5 | Kelvin leads | 1×2 header | Blueprint §14.4 | — | — |

## Current sense — blueprint §3.3

| Ref | Part | Value | Source | Evidence | Bench |
|---|---|---|---|---|---|
| <a id="u2"></a>U2 (A, B) | OPA2197IDR, input buffers | — | Blueprint §3.3. Sims 06, 07. §13 | Unbuffered, the bridge draws **475.6 µA** of phantom current with no DUT connected (sim 06, 2026-09-18): 0.95% of range 1 full scale. Sim 07's buffered "0" comes from ideal E sources and proves the topology only, not bias-current performance | Phase 2 |
| <a id="u3"></a>U3 (A) | OPA2197IDR, difference stage | — | Blueprint §3.3 | — | — |
| <a id="r15"></a>R15, <a id="r17"></a>R17 | R3, R1 | **1 kΩ 0.1%** | Blueprint §3.3. Sims 04, 05 | Gain `R2/R1` = 20. CMRR comes from resistor matching: **74.4 dB** worst-case corner at 0.1% (sim 04). Monte Carlo median **88.26 dB** (sim 05, n = 500, 2026-09-18) | **H4 / Phase 2**: measured CMRR against the 74.4 dB floor |
| <a id="r16"></a>R16, <a id="r18"></a>R18 | R4, R2 | **20 kΩ 0.1%** | Blueprint §3.3. Sims 04, 05 | As above. All four resistors are the same Yageo RT0805 25 ppm family, for matching | As above |
| <a id="r19"></a>R19 | Isolation, ADC1 | **1 kΩ 1%** 0603 (C21190, Basic) | Datasheet: OPA2197 §7.3.5 and Table 3 (floor). **Decision, 2026-10-06**, made twice: 51 Ω (60° phase margin), then raised to 1 kΩ to close F-2. Blueprint §3.5, §3.7 | U3A drives 10 nF at the ADC pin. Table 3: 20 Ω gives 45° and 51 Ω gives 60°; more resistance only adds margin. 1 kΩ bounds the clamp current into +3V3 at (15 − 3.3 − 0.4) V / 1 kΩ ≈ **11 mA**. Costs: up to **2 mV** leakage offset (BAT54S ≤ 2 µA × 1 kΩ), which varies with signal and temperature, and τ = 10 µs, which set `settle_us` to 50 µs (§4): at the old 20 µs the 64-sample mean carried 0.16% of each step, at 50 µs 0.008% | **H4:** ADC1 reading at zero current → offset calibration; re-check at full scale |
| <a id="c3"></a>C3 | ADC1 cap | **10 nF** | Blueprint §3.5 | "10 nF cap at each ADC pin" | — |
| <a id="d4"></a>D4 | ADC1 clamp | BAT54S (R+O, C7420333, Preferred) | Blueprint §3.5, §3.6 | Clamped to GND and +3V3. Pinout 1 = A, 2 = K, 3 = common, matching onsemi STYLE 11; I_R ≤ 2.0 µA at 25 V, as onsemi | **H4:** +3V3 at TP8 with the clamp conducting (unplug the Kelvin leads) |

## Voltage sense — blueprint §3.4

| Ref | Part | Value | Source | Evidence | Bench |
|---|---|---|---|---|---|
| <a id="r20"></a>R20 | Divider top | **300 kΩ 0.1%** 0603 25 ppm (Yageo RT0603BRD07300KL, C705762) | Blueprint §3.4 (ratio). **Decision, 2026-10-06** (value), closing F-1 | ÷4: 10 V → 2.5 V at ADC2. Was 30 kΩ: the divider's current is counted as DUT current, and 400 kΩ total cuts it from 25 to **2.5 µA per volt**. The firmware subtracts the remainder (`cal_rdiv_ohm`). Same family, size and TCR as R21, so the ratio tracks with temperature. VDIV is now a 75 kΩ node: keep it short at layout | **Phase 3**: Kelvin V_DS tracks a DMM within 0.5% |
| <a id="r21"></a>R21 | Divider bottom | **100 kΩ 0.1%** 0603 25 ppm (Yageo RT0603BRD07100KL, C122538) | Blueprint §3.4. **Decision, 2026-10-06**, with R20 | No longer shares a reel with R14 (10 kΩ shunt), so it adds one extended line (+$3).  Returned to **KELVIN_LO**, not GND, because the README's routing table runs KELVIN_HI/LO as a pair into the divider. ADC2 is ground-referenced, so it reads `V_LO + V_DS/4`. The source-lead drop therefore enters at ¾ weight rather than full weight. That is a §3.4 limitation, not a capture error | As R20 |
| U3 (B) | Kelvin buffer | — | Blueprint §3.4 | Unity gain | — |
| <a id="r22"></a>R22 | Isolation, ADC2 | **1 kΩ 1%** 0603 (C21190, Basic) | As R19 | U3B is a **unity-gain** buffer, the configuration the datasheet rates to only 1 nF of direct drive. It is also the buffer that rails when the Kelvin leads are unplugged, which is F-2's commonest route. Its leakage offset is ×4 at the DUT: up to 8 mV | **H4:** ADC2 reading at V_DS = 0 → offset calibration |
| <a id="c4"></a>C4 | ADC2 cap | **10 nF** | Blueprint §3.5 | — | — |
| <a id="d5"></a>D5 | ADC2 clamp | BAT54S (R+O, C7420333, Preferred) | As D4 | — | As D4 |

## Power, ground, MCU

| Ref | Part | Value | Source | Evidence | Bench |
|---|---|---|---|---|---|
| <a id="j1"></a>J1 | Barrel jack | DC-005, 2.0 mm pin | Blueprint §8 (15 V / 1 A adapter + barrel jack) | Check the adapter's plug before ordering: a 2.0 mm pin takes 5.5×2.1 plugs, not 5.5×2.5. The centre pin is net VIN, behind Q3 ([P-11](#layout-decisions-h2-pass-2-2026-10-06)) | — |
| <a id="j2"></a>J2 | Supply header | 1×2 | Blueprint §14.4 ("headers, not soldered connections, for the supply") | On the +15V rail, **deliberately unprotected** (Daniel, 2026-10-07; [P-14](#layout-decisions-h2-pass-2-2026-10-06)). Silkscreen "+15V" and "GND" beside its pads | **H4:** polarity by meter before first power-up |
| <a id="c5"></a>C5 | Bulk | **10 µF**, 50 V aluminium electrolytic | Blueprint §8 (≥25 V), §14.5(3) | 50 V is what is stocked in 5×5.4 mm, above the ≥25 V floor | — |
| <a id="q3"></a>Q3 | J1 reverse-polarity FET | **HL2303** P-channel, SOT-23 (R+O, C7420345, Preferred) | **Decision, 2026-10-06**: Daniel ("P-channel MOSFET in the high side, not a Schottky"). Part: P-11 | −30 V V_DS, **±20 V V_GS**, R_DS(on) ≤ 190 mΩ at −10 V → ≤ 28.5 mV at 150 mA (≤ 50 mV asked). Drain = VIN (J1), source = +15V | **H4:** TP28 − TP7 at a known current; reversed supply on J1 |
| <a id="d6"></a>D6 | Q3 gate clamp | **12 V**, BZT52C12, SOD-123 (C173429, D2's line) | P-11 | Cathode at source (+15V), anode at gate: holds V_GS at −12 V against hot-plug ringing past the 20 V rating | — |
| <a id="r25"></a>R25 | Q3 gate pull-down | **10 kΩ** 1% 0603 (C25804, Basic) | P-11 | Gate to GNDPWR. D6 current (15 − 12) V / 10 kΩ = 0.3 mA | — |
| <a id="c6"></a>C6, <a id="c7"></a>C7, <a id="c8"></a>C8 | Op-amp decoupling | **100 nF** X7R 50 V | Blueprint §8, §14.5(3) | One per OPA2197 V+, within ~5 mm | — |
| <a id="nt2"></a>NT2 | Star point | — | **Capture C-2** | §14.5(4) | — |
| <a id="j7"></a>J7, <a id="j8"></a>J8 | Nucleo CN7 / CN10 | 2×19 sockets | Blueprint §14.4. `firmware/README.md` pin table | PA0 = CN7-28 (ADC1_IN1), PA4 = CN7-32 (DAC1_OUT1), PC0 = CN7-38 (ADC2_IN6, default solder bridges), PA6 = CN10-13 (DAC2_OUT1). Verified against **UM1724 Rev 14 Table 26**. PA5 unused (LD2, §3.5). Nucleo is USB-powered: +15 V exceeds VIN max | — |
| <a id="tp"></a>TP1–TP28 | Test points | Keystone 5001 loops; TP6 and TP28 bare pads | Blueprint §14.4. TP6: Capture C-4. TP28 (VIN): a 1 mm pad because a loop does not fit by J1 (P-11) | Every node §14.4 lists, plus every other named net except Q3's gate (RP_GATE), the op-amp input nodes DA_P, DA_N, GATE_IN- and the per-shunt pads SH1–3_TOP, which SHUNT_HI reaches when selected | — |

`BD139_C` from the README routing table is not a separate net: the collector
is tied directly to +15 V (§3.1), so it is net `+15V`, probed at TP7.

---

## Capture decisions

Each one either fills a gap in §3 or resolves a conflict inside it. C-1 and
C-5 are signed off (2026-10-06). C-2, C-3, C-4 and C-6 are not yet
explicitly signed off.

**C-1 — Range selection is two 2×3 headers, not one 3-pin header.** *Accepted 2026-10-06; silkscreen added.* §3.3 and
§14.2 call for "a 3-pin selection header". One jumper on a 1×3 header has
two positions, not three. More importantly, a jumper in the force path puts
its contact resistance (~10–20 mΩ) in series with the 1 Ω range-1 shunt. If
the sense tap sits on the far side of that jumper, the error is 1–2%, against
Phase 2's 1% gate. So J3 switches the force current and J4 switches the
Kelvin sense line, each at the shunt pad. J4 carries only buffer input
current, so its contact resistance does not matter. **Cost:** two jumpers
that must sit in the same position. Range 1 is pins 1–2 on both.

**C-2 — Star ground and the shunt Kelvin tap are net ties.** §14.5(4) and (6)
are geometric rules that DRC cannot see unless the nets are distinct. GNDPWR
(supply return, DUT source, BD139 decoupling, gate Zener) and GND (op-amps,
R_g, diff-amp REF, ADC caps and clamps, Nucleo) meet only at NT2. NT1 makes
SHUNT_LO a separate net, tied to DUT_D at R12's pad.

**C-3 — R_B, R_iso, R_sense and the gate resistor are sized for fault
dissipation.** §8 gives none of them a power rating. Calculated from sim 10
currents:

| | fault current | dissipation | fitted |
|---|---|---|---|
| R_B (330 Ω) | 32.2 mA op-amp drive, held short | **342 mW** | 2512, 1 W |
| R_iso (22 Ω) | 107 mA, hard short | **252 mW** | 2512, 1 W |
| R_sense (10 Ω) | 75.2 mA, threshold | 57 mW | 1206, 0.75 W |
| Gate 1 kΩ | ~14.6 mA, gate shorted to source | 213 mW | 2512, 1 W |

An 0603 (100 mW) would fail at R_B and R_iso on the first sustained short.
§3.1 expects such shorts to happen often ("students and mistakes will short
the DUT terminals").

**C-4 — TP6 (OPA_SWEEP_IN-) is a 1 mm SMD pad, not a loop.** §14.4 lists
the inverting node as a test point, and §14.5(2) says to minimise copper on
it. A pad satisfies both. Note that **scoping this node changes it**: a 10×
probe adds ~10 pF against the 5–10 pF the `C_f` calculation is trying to
cancel. Use it for DC checks, not for transient measurement.

**C-5 — Series resistors between each output op-amp and its ADC pin (R19,
R22).** *Resolved 2026-10-06: 51 Ω. The rule is now blueprint §3.7.* §3.5 puts 10 nF directly at each ADC pin. U3B is a unity-gain
buffer, and the OPA2197 datasheet (§7.3.5) rates unity-gain direct drive to
**1 nF**: 10 nF is ten times that. Datasheet Table 3 gives an isolation
resistor for 10 nF of **20 Ω for 45° phase margin, 51 Ω for 60°**. This is
the same mechanism as the §3.1 `R_iso` finding, on a different op-amp.
Originally captured as 0 Ω placeholders (§3.5 as written); now fitted at
51 Ω.

**C-6 — DNP pull-down footprints on DAC_SWEEP and DAC_GATE (R23, R24).** The
Nucleo is on headers (§14.4) and is "the single most likely part to be
swapped or destroyed". With +15 V applied and the Nucleo removed, or during
MCU reset when the DAC pins are high-impedance, both op-amp inputs float.
The sweep output can then sit anywhere up to the limiter at the DUT. The
footprints cost nothing. **The value is open**, and they ship unstuffed.

## Open values — no value on the board yet

| Id | Ref | What is open | Why it is not filled |
|---|---|---|---|
| ~~O-1~~ | D2 | Gate Zener voltage | **Closed 2026-10-06: 12 V**, see [D2](#d2) |
| ~~O-2~~ | R19, R22 | ADC isolation resistance | **Closed 2026-10-06: 51 Ω**, see [R19](#r19) |
| **O-3** | D3 | Output clamp type and voltage | §3.6/§14.6: mitigation unresolved. Ships unstuffed, as §14.6 allows |
| O-4 | R23, R24 | Pull-down value | Ships unstuffed (C-6) |

## Substitutions — what the blueprint names vs what JLCPCB can fit

| Id | Blueprint part | Fitted part | Why | What changes |
|---|---|---|---|---|
| **S-1** | Littelfuse **RXEF010** (radial, THT) | **TECHFUSE nSMD010** (1206, C70065) | RXEF010 is not in JLCPCB's assembly library. LCSC lists RXEF010S (C1562110) at **0 stock** | See the comparison below |
| S-2 | BD139**-16** | ST **BD139** (C27866) | No -16 stocked at JLCPCB. Same ST die and SOT-32 package; the ST model is the one Phase 0 used (§12) | h_FE bin only. §3.1 relies on the follower being inside the loop, not on gain |
| S-3 | 1N4148 (DO-35) | 1N4148W (SOD-123, C81598, Basic) | SMD for PCBA | Same junction. Sim 09 used the generic `standard.dio` model, not a package-specific one |
| S-4 | 2N3904 (sim part) | JSCJ MMBT3904 (SOT-23, C20526, Basic) | SMD for PCBA; a Basic part since 2026-10-06 (was onsemi MMBT3904LT1G, extended) | Same die. The SST3904 cross-check in sim 10 was already a SOT-23 part. JSCJ pinout 1 = B, 2 = E, 3 = C, matching the symbol; 200 mW against 53 mW in a held short. Vendor V_BE spread enters the limiter threshold, within the ~2% §3.1 already carries between models |
| S-5 | Yageo MFP-25 0.1% THT (§3.1, §8) | Yageo RT thin-film 0.1% SMD | PCBA. R1/R9 23.2 kΩ is RT0603**BRE** (50 ppm, the only 0603 23.2 kΩ 0.1% stocked) | Ratio drift at most 75 ppm/°C between R_f and R_g: negligible against the 0.1% tolerance |

**S-1 datasheet comparison** — RXEF010 figures from the Littelfuse RXEF
series datasheet; nSMD010 figures from TECHFUSE's datasheet as synced to
`datasheets/` (LUTE's 1206L010/60NRL, C18198325, lists identical figures and is
the second source):

| | RXEF010 | nSMD010 | effect |
|---|---|---|---|
| I_hold | 0.10 A | 0.10 A | same |
| I_trip | **0.20 A** | **0.25 A** | guaranteed trip 25% higher. 107 mA still sits between hold and trip, so §3.6's "may or may not open, either is safe" stands |
| V_max | 60 V | 60 V | same |
| Time to trip | 4.0 s max | 1.0 s max at 0.5 A | faster |
| R_min / R_max (initial) | 2.5 / 4.5 Ω | 1.6 Ω min | lower drop before any trip |
| R1_max (1 h after trip) | 7.5 Ω | **15 Ω** | higher drop after a trip — see below |
| Package | radial THT | 1206 SMD | PCBA-fittable |

**The PTC resistance is missing from the §3.1 headroom figure, with either
part.** F1 sits between the feedback tap and the Kelvin point, so its
resistance is outside the loop and uncorrected, like R_iso. §3.1's
**9.81 V at 50 mA** (10.956 − 0.05 × 23) counts R_iso and the shunt only:

| R_PTC | DUT max at 50 mA |
|---|---|
| none (§3.1 as written) | 9.806 V |
| nSMD010, 1.6 Ω initial | 9.726 V |
| RXEF010, 2.5–4.5 Ω initial | 9.68–9.58 V |
| RXEF010, 7.5 Ω after a trip | 9.431 V |
| nSMD010, 15 Ω after a trip | 9.056 V |

The same term breaks `firmware/README.md`'s diagnostic "delta ≈ I × 23 Ω".
It should be I × (23 Ω + R_PTC), and R_PTC changes after every trip.

**Resolved 2026-10-06** by fixing the record, not the circuit. Blueprint §1
and §3.1 now give **9.73 V (at 1.6 Ω) to 9.06 V (at 15 Ω)** at 50 mA. §3.6
notes that a tripped PTC costs headroom, not accuracy. `firmware/README.md`'s
delta check now reads I × (23 Ω + R_PTC). One correction to the request as
given: it labelled 9.73 V "fresh" and 9.06 V "after a trip". The nSMD010
datasheet specifies the 15 Ω maximum *one hour after reflow*, so a fresh
board can already sit anywhere in the band. The record says best case and
worst case instead.

## Blueprint discrepancies found during capture

Items 1, 2 and 4 were corrected in the blueprint on 2026-10-06. Item 3 is a
property of the parts, not an error, and stays here as layout check L-1.

1. **OPA2197 count.** §8, §13 ("3 to 4 × OPA2197") and §14.3 ("the board
   needs four") say four. The circuit has six channels: sweep, gate, two
   input buffers, the difference stage and the Kelvin buffer. That is
   **three duals**, all channels used, no spare. If "four" includes a
   spare, it is an order quantity, not a board count.
2. **BD139 h_FE bin.** §8 says "-16 suffix is the h_FE bin, 63–160". ST's
   datasheet (BD135-BD140, Rev 5, Table 4 "On/off states", h_FE groups) gives **-10 = 63–160,
   -16 = 100–250**. No design consequence.
3. **BD139 pin numbering differs between vendors.** ST Rev 5 Figure 1 numbers
   B(1) C(2) E(3). onsemi (STYLE 1) and KiCad's `BD139` symbol number
   E(1) C(2) B(3). The physical lead order is the same E-C-B (front view)
   in both drawings. **At layout, check the TO-126 footprint against the
   physical lead order, not ST's pin numbers.**
4. **PTC resistance missing from headroom.** See S-1 above.

## Layout-time checks

Things the schematic cannot settle and the layout must.

**L-1 — BD139 pins: check the footprint against the physical leads, not
against pin numbers.** ST and onsemi number this part in opposite
directions. ST's BD135–BD140 datasheet (Rev 5, Figure 1) has **B = 1,
C = 2, E = 3**. onsemi's BD139 (TO-225, STYLE 1) and KiCad's `BD139` symbol
have **E = 1, C = 2, B = 3**. Both drawings show the same physical order,
E-C-B, looking at the marked face with the leads down. The fitted part is ST
(C27866), so its datasheet's pin numbers disagree with the schematic's.
Checking by number will find a "mismatch" that isn't one, or miss a real
one. At H2, put the physical part on the printed footprint and confirm
emitter, collector and base land on the BD139_E, +15V and BD139_B pads.

**L-1 resolved (2026-10-06) — the footprint is right.** Both
manufacturers' front views agree on the physical order: onsemi pins 1-2-3
left to right are E-C-B, and ST's 3-2-1 are E-C-B under ST's own numbering.
KiCad's TO-126-3_Vertical 3D model shows the exposed metal tab on the −y
face. So the front faces +y, and from the front the pads read 1-2-3, i.e.
E-C-B, which is what the `BD139` symbol assumes. On the board the tab
(collector, +15 V) faces −y, toward the heatsink keep-out.

**L-2 — The Nucleo morpho sockets need mirrored pad numbering.** KiCad's
stock `PinSocket_2x19` puts pin 2 at −2.54 mm from pin 1; its sockets are
drawn as the mirror image of its headers. Seen from above, the Nucleo's
CN7/CN10 pins have pin 2 at **+**2.54 mm (KiCad's own
`STM32_Nucleo-64_Morpho` template, UM1724 Table 26), and so must any board
the Nucleo plugs into. A stock socket on our top side would have put every
morpho pin in the wrong column, and ERC/DRC would both pass. J7/J8 use
`curve-tracer:PinSocket_2x19_P2.54mm_Vertical_NucleoCarrier`, the stock
socket with its pads mirrored. `tools/check_topology.py` asserts it.

The footprint reuses the stock socket's 3D model, shifted **+2.54 mm in x**.
Unshifted, the model sat one column off the pads, and nothing automated
noticed that either: it showed up in the Pass 2 render (2026-10-06) as a
column of bare pads beside each socket body. The copper was right
throughout. The pre-order footprint-orientation check (`README.md`) exists
because of this class of error.

## Layout decisions (H2, Pass 1, 2026-10-06)

**P-1 — One back pour, two regions, one tie.** The back layer is poured
everywhere. It is split along x = 30.25 mm into **GNDPWR**, under the force
path (supply entry, Q1, R_sense, R_iso, PTC, shunts, DUT socket), and
**GND**, under the op-amps, ADC lines and Nucleo. The two meet only through
NT2 (blueprint §14.5(4)). Not a single GND pour with GNDPWR as top traces,
because of the Q1 geometry: the collector is the middle lead, and D1 and Q2
both bridge emitter and base on the front side, so C2's GNDPWR return cannot
leave the collector pocket on the top layer without a via. With GNDPWR as a
region it drops straight through, and the load current returns directly
under its own force traces. Signals crossing the split are the feedback tap,
the base drive, SHUNT_HI/LO, the Kelvin pair, DUT_G and a probe stub on
LOAD. Kept after the Pass 1 review (Daniel, 2026-10-06): the alternative
routes up to 107 mA of load return under the input node.

**Where each net crosses, measured on the routed board.** A trace crossing
the split has no copper under it at the gap. Its return goes along the gap
to NT2 and back, so the detour is twice the distance below.

| Net | Crosses at y | To NT2 (y = 76.5) | Current in it |
|---|---|---|---|
| BD139_B | 20.68 | **55.8 mm** | base drive, ≤ 21.9 mA peak (sim 09) |
| **FB_SENSE** | 32.33 | **44.2 mm** | R_f + R_g string only: ≤ 0.5 mA |
| DUT_G | 39.48 | 37.0 mm | gate charge |
| LOAD | 46.20 | 30.3 mm | none: R8 → TP5 probe stub; the 107 mA path stays on GNDPWR |
| SHUNT_LO | 47.77 | 28.7 mm | buffer input, pA |
| SHUNT_HI | 52.87 | 23.6 mm | buffer input, pA |
| KELVIN_LO | 84.20 | 7.7 mm | divider input, µA |
| KELVIN_HI | 85.00 | 8.5 mm | divider input, µA |

**The feedback tap at ~3 MHz.** The detour is ~88 mm of return along the
0.6 mm gap (fills end at x = 29.95 and 30.55): of order 1 nH/mm, so ~90 nH, ~1.7 Ω at 3 MHz. It sits in series
with the 33.2 kΩ R_f + R_g string. That is 5 × 10⁻⁵ of the divider and a
few thousandths of a degree at crossover. Ten times the estimate would still
be 0.03°. The 2–3 MHz pole is the capacitance at OPA_SWEEP_IN−, and that
node does not cross: R1, R2, C1 and U1A sit together on the GND side, in the
no-pour area. FB_SENSE is driven from the emitter side, a low-impedance
source. **The crossing is not a stability term.** The base drive is the
crossing with real current at 3 MHz. Its ~110 nH (~2 Ω) is in series with
R_B = 330 Ω: 0.6%, with an L/R corner near 500 MHz, far above the ~13 MHz
R_B·C_jc pole.

**NT2 stays where it is (Daniel, 2026-10-06), on these numbers.** Moving it
up to y ≈ 28 would cut the FB and base detours to a few mm. It would also
lengthen the Kelvin, shunt and DUT_G detours to 20–57 mm, and pull the star
away from the DUT socket returns, which is where §14.5(4) wants it.

Neither crossing that sees 3 MHz is a stability term where it is now:

- feedback tap: 5 × 10⁻⁵ of the R_f + R_g string, a few thousandths of a
  degree at crossover;
- base drive: 0.6% of R_B, with its L/R corner near 500 MHz.

So the move buys nothing. There is also no room for the tie at y ≈ 28
without re-clearing GNDPWR around BD139_B and OPA_SWEEP_OUT by R3/TP1.

**P-2 — Shunt Kelvin sense on the back.** Each SHx_TOP sense line leaves its
shunt pad through a via and runs on the back to J4. The pad is the only point
it shares with the force current, which arrives on the front.

**P-3 — Four M3 mounting holes** (H1–H4, schematic `Mechanical`, not in the
BOM), because the board carries a Nucleo on 8.5 mm sockets.

**P-4 — SHUNT_HI and SHUNT_LO are not length-matched** (58 vs 47 mm). They
start in different places (J4's sense pins and NT1) and enter U2 from
opposite sides, because pin 3 and pin 5 of a dual op-amp are on opposite
sides of the package. Both drive unity-gain buffers drawing pA, so their
resistance does not enter the measurement. What matching would buy is
symmetric pickup. Both run over the same ground region at low frequency.
Confirmed at the Pass 1 review (Daniel, 2026-10-06): DC signal, picoamp
inputs, ignore.

## Layout decisions (H2, Pass 2, 2026-10-06)

**P-5 — Board 135 × 92 mm** (from 160 × 92 at Pass 1, Daniel's call). JLCPCB
bare-board quotes, read from the public quote page on 2026-10-06. Settings:
2 layers, FR-4, 1.6 mm, qty 5, green, HASL, 2-day build, no login. Prices
in USD:

| Size | Board | Engineering fee | Total |
|---|---|---|---|
| 160 × 92 | 7.10 | 4.00 | **11.10** |
| 135 × 92 | 6.00 | 4.00 | **10.00** |
| 100 × 100 | 6.00 | 4.00 | 10.00 entered by hand; **4.00** as the page's default "Special Offer" |

135 × 92 saves **$1.10** on 160 × 92. Against 100 × 100 it costs **$6.00
more** if the promotional $4.00 applies, nothing if it does not. The page
showed $4.00 only in its untouched default state. Shipping, $31.23 by DHL,
is the same for all three and dominates either way. PCBA charges are not in
these numbers.

100 × 100 is not reachable without compromising Pass 1. The two morpho
sockets fix x from 67.7 to 133.0. The front end (Q1 with its heatsink
keep-out, the force path, the GNDPWR region and the DUT socket) occupies
x = 0–60. At 100 mm, about 35 mm of it would have to move under the
Nucleo, which sits 8.5 mm above the board. Those parts would lose
test-point access (§14.4), Q1 would lose its heatsink clearance, and every
Pass 1 net would have to be re-placed and re-routed.

**P-6 — Freerouting v2.5.0 for the non-critical nets.** It ran headless on
a SPECCTRA export with:

- every Pass 1 track and the pre-routes locked (exported as `fix`);
- a layer cost of 1 on F.Cu and 8–10 on B.Cu;
- +15V in a 0.5 mm / 0.25 mm power class, 0.25 mm default width;
- the boundary inset by 0.4 mm for edge clearance.

The first run without layer costs put 268 mm of copper on B.Cu and cut the
GND pour into pieces. The costed run put ~12 mm there. T-junctions in the
locked copper were split at their meeting points before export, because
SPECCTRA only joins track ends. KiCad's session import replaces every
track, so the routed session was imported into a copy, and only the new
tracks and vias were merged back. Afterwards: four dangling vias removed,
DAC_SWEEP joined to TP20, D3's GNDPWR via moved off its pad (VP-001).

**P-7 — +15V spine routed by hand.** SHUNT_LO's loop around U2 encloses C7,
so the autorouter could not reach C7's +15V pad. The spine runs at
x = 57 mm with one back-layer hop into C7, and was locked before
autorouting.

**P-8 — Q1 collector pour and thermals.** +15V has a 379 mm² F.Cu pour with
a solid (not thermal-relief) connection on Q1's collector. Its bottom edge
moved to y = 18 so the collector is not starved. That pour carries current,
not heat: a vertical TO-126 sheds very little through its leads. Junction
temperature in the §3.1 sustained short, 0.89 W, from ST's figures
(R_th j-a 100 °C/W, R_th j-c 10 °C/W, T_j max 150 °C):

- no heatsink: 25 + 0.89 × 100 = **114 °C**, or 129 °C at 40 °C ambient;
- ~20 °C/W clip-on heatsink plus ~1 °C/W interface: 25 + 0.89 × 31 ≈
  **53 °C**.

**The heatsink is required for the short test** (Daniel, 2026-10-06).
Without it, 129 °C at 40 °C ambient leaves 21 °C of margin. That is a hand
calculation, on the part the H4 short tests stress deliberately (limiter
trip, held short, short recovery), and it is not enough to rely on. So:

- `README.md` states the rule.
- H4 makes the heatsink a verified item, not a BOM line: tab isolation, and
  the case temperature in the first held short.
- The silkscreen inside the keep-out reads "FIT Q1 HEATSINK / BEFORE SHORT
  TEST / TAB = +15 V". It sits where the heatsink goes, so it is legible
  exactly when the heatsink is missing.

The keep-out (x 17.5–35, y 1–15.5) is there for the heatsink, and the tab is
+15 V (§8). The thermal analyzer skipped Q1, so these are hand numbers.

**P-9 — Silkscreen references hidden where there is no room**: J3, Q2, R5,
TP1, and (P-11) Q3, D6, R25, TP28 and H1. They are still on the fab layer
and in the renders. J1's reference moved below the jack, beside C5.

**P-10 — CPL rotations.** `tools/export_fab.py` adds −90° to SOT-23 (Q2,
D4, D5) and 270° to SOIC (U1–U3), from the community table that
`kicad-jlcpcb-tools` also uses. Both values are for KiCad 6+ footprints;
the +180° quoted for SOT-23 dates from KiCad 5. C5's CP_Elec_5x5.4 is not
in that table, and every listed CP_Elec size is 180°, so C5 gets 180°.
These are not JLCPCB's numbers. JLCPCB's placement preview is where each
polarised part gets checked (README, footprint orientation).

**P-11 — J1 reverse-polarity protection: high-side P-FET Q3** (Daniel,
2026-10-06). Q3's drain is on J1's centre pin (net VIN) and its source on
+15V. Forward, the body diode conducts first, then the gate, pulled to
GNDPWR through R25, turns the channel on. Reversed, the gate sits at the
source, the body diode is reverse-biased, and nothing flows.

- **Part: HL2303 (R+O, C7420345).** JLCPCB Preferred, so no loading fee;
  408k in stock. −30 V V_DS, ±20 V V_GS, R_DS(on) ≤ 190 mΩ at V_GS = −10 V.
  At 150 mA that is **≤ 28.5 mV**, or ~43 mV allowing 1.5× for
  temperature, against the ≤ 50 mV asked for. V_GS(th) is −1 to −3 V,
  against a −12 V drive. 150 mA is a sound ceiling: ~107 mA into a held
  short, plus ~8 mA of op-amp and divider current.
- **Rejected:** AO3401A (Basic, 47 mΩ) and HL3401A (Preferred) both have
  **±12 V** gates, and a 15 V input puts −15 V across them. AO3407A (±20 V,
  48 mΩ) would work, but it is extended (+$3) for margin the HL2303 already
  has.
- **D6 and R25.** D6 is a 12 V Zener from gate to source; R25 is 10 kΩ from
  gate to GNDPWR. A barrel jack hot-plugged into a 10 µF bulk cap rings,
  and the overshoot can pass the 20 V gate rating. D6 holds V_GS at −12 V,
  and R25 sets its current at (15 − 12) V / 10 kΩ = 0.3 mA in normal
  running. D6 reuses D2's BZT52C12 line and R25 is Basic, so neither adds a
  loading fee.
- **The stated reason for a P-FET over a Schottky does not hold.** The
  request was "not a Schottky — headroom is already at 9.06 V". The 9.06 V
  does not depend on the supply. It is the 10.96 V feedback-node full scale
  less R_iso, the shunt and the PTC, all downstream of the loop (§3.1).
  - What the supply sets is the op-amp's room above the base drive. At full
    scale the op-amp output needs 10.96 + 0.5 (R_sense) + 0.75 (V_BE) +
    0.17 (R_B × I_B at h_FE 100) ≈ **12.4 V**. It reaches ~14.6 V even
    sourcing 32 mA (§3.1): ~2.2 V of margin.
  - A Schottky's ~0.4 V would leave ~1.8 V and the 9.06 V untouched.
  - The P-FET is still the better part: ≤ 28.5 mV and ≤ 4 mW, against
    ~0.4 V and ~60 mW for a Schottky.
- **J2 is not behind Q3**, by decision (P-14).
- **Layout.** The parts sit in the free patch above J1 (x 7.5–17.5,
  y 0–7). The +15V pour's left edge moved from x = 12 to x = 17, so J1's
  centre pin and the new parts sit outside it. The pour went from 379 to
  299 mm² and is still one region. One +15V stub keeps the J1-side feed to
  C5 on the pour. A diff against the board before the change shows 11 items
  added and **0 removed or moved**; no Pass 1 copper is involved.
- **Checks.** `check_topology.py` asserts Q3's pins and D6/R25, and plants
  two new faults, both caught. One swaps drain and source: the board still
  powers up through the channel, and nothing is protected. The other
  reverses D6. H4 measures the drop (TP28 to TP7) and the reversed-supply
  case.

**P-12 — No EMI filter at the supply input** (Daniel, 2026-10-06; it closes
IO-001 on J1):

- The input is DC, from a bench supply or a 15 V adapter, and nothing on
  this board switches. The Nucleo, the only clocked circuitry, is
  USB-powered and never sees +15 V (`check_topology.py` asserts that).
- The rail is already decoupled where it is used: C5 (10 µF) at the entry,
  C2 (100 nF) at Q1's collector, and 100 nF at each op-amp.
- A ferrite or inductor would sit in series with the pass transistor's
  collector supply, which carries the load current. With C5 and C2 it adds
  an LC that the §3.1 stability work never included.
- No emissions or immunity standard applies to a one-off bench instrument.

**P-13 — No fiducials** (Daniel, 2026-10-06; it closes FD-001). JLCPCB does
not require board fiducials for Economic PCBA, and the finest pitch here is
the SOIC-8's 1.27 mm.

**P-14 — J2 is deliberately unprotected** (Daniel, 2026-10-07). J2 is for a
bench supply, where polarity is set deliberately and verified before
connecting. J1 takes an arbitrary wall adapter, whose polarity nobody
checks; that is the case Q3 covers.

- J2's pads are labelled in silkscreen, "+15V" and "GND", beside each pad
  rather than with a plus sign alone.
- H4 verifies J2's polarity with a meter before first power-up.
- The first power-up goes through J2, current-limited to 100 mA, rather
  than through J1. The board idles at ~8 mA (three OPA2197s at ~1.2 mA per
  channel, plus 0.3 mA in Q3's gate network), so 100 mA is ample.

Routing J2 through Q3 would have needed ~25 mm of VIN along the left edge,
on the back, through the GNDPWR pour.

## Layout review (H2, 2026-10-06)

`kicad-happy` v2.3.0 on the routed board: schematic, PCB `--full`, cross,
EMC, thermal, SPICE, gerbers. Raw output is in `analysis/` (gitignored).
DRC (`--severity-all --schematic-parity`), ERC and `check_topology.py
--self-test` are clean: 55/55, with all 11 planted faults caught. Re-run
after P-11: no new findings except RS-001 below.

| Finding | Where | Verdict |
|---|---|---|
| KO-001 ×4 (error) | C1, R1, R2, TP6 inside the IN− no-pour area | False positive. The rule area forbids copper pour only; these parts *are* the node §14.5(2) protects |
| GP-001 ×8 error, ×12 warning | Nets without plane under them or crossing the split | By design. IN− has no plane (§14.5(2)); the rest are the P-1 crossings or the P-2 back-layer sense lines. All DC or low frequency; P-1 quantifies the two that see 3 MHz |
| GP-005 | Two ground domains | Intended: P-1 |
| PS-002 (cross) | "+15V split into 3 islands" | False positive. One 379 mm² fill outline, 0 unconnected items in DRC |
| RP-001 ×8 | Layer change without a stitching via | Not applicable. Two layers with one reference plane (B.Cu) |
| IO-001 (error) J6 | No filtering at the DUT socket | Intended. The DUT terminals must not be filtered |
| IO-001 (error) J1 | No filtering at the supply input | Decided: no filter (P-12). Reverse-polarity protection added instead (P-11) |
| FD-001 | No fiducials | Decided: none (P-13) |
| RS-001 (schematic) | "VIN has no declared source" | False positive. VIN is sourced by J1, a connector; ERC is clean |
| PM-002 | J5 0.73 mm from the edge | Intended: Kelvin leads exit at the edge |
| TE-001 | Test points on 23 of 93 nets | Informational. §14.4's list is covered; `check_topology.py` asserts it |
| CG-AUD ×2 | J3/J4 have no ground pin | False positive: range-select headers |
| GR-004 | Paste on 99 of 267 copper pads | Expected: the rest are through-hole |
| Thermal | Q1 skipped by the analyzer | Hand estimate, P-8 |
| SPICE | 7 pass, 2 skip: R1/R2 and R9/R10 (operating point did not converge) | The skipped pair are op-amp gain networks, with no source in isolation. `check_topology.py` asserts both ratios |

**Lifecycle.** `lifecycle_audit.py` returned *unknown* for all 29 lines.
LCSC is the only source here, and the audit's LCSC path exposes no
lifecycle field. DigiKey, Mouser and element14 need API keys that are not
set up. Substitute: LCSC's own product record has `productCycle`, which
reads **normal for all 29**. Thinnest stock on 2026-10-06:

- R1/R9 23.2 kΩ 0.1% (C861768): 2,253 at JLCPCB, 860 at LCSC.
- Q1 BD139 (C27866): 128 at JLCPCB, but it is hand-soldered from LCSC, which
  has 5,075.
- J7/J8 sockets (C2897420): 2,962.

Nothing is short at qty 5. That is a stock check, not a manufacturer's
lifecycle statement.

## Findings resolved 2026-10-06

**F-1 — The Kelvin divider's current was measured as DUT current.**
*Resolved both ways.* R20 + R21 hang from KELVIN_HI, the DUT drain, on the
DUT side of the shunt, so the shunt carries `I_DUT + V_DS / (R20 + R21)`. At
30k/10k that was **25 µA per volt**, uncorrected anywhere: 2.5% on a 10 mA
reading, which would fail Phase 2's 1% gate on its own. Now:

- **300k/100k**: 2.5 µA per volt, ratio unchanged (R20, R21).
- **Firmware subtracts it** (CSV schema 2): `i_meas_ma = I_shunt − V_DS /
  cal_rdiv_ohm`. The host's recomputation does the same and checks it
  agrees. `host/tests/test_divider_correction.py` shows the correction fires,
  and that an uncorrected sweep of a 40 kΩ load reads 36.4 kΩ (40k ‖ 400k),
  9% low. `hardware/tools/check_topology.py` now also requires the board's
  divider to match `CT_RDIV_OHM`.

**The same mechanism as §13's phantom current, reached by a different
path.** In §13 the unbuffered difference-amp bridge drew 475.6 µA through
the shunt with no DUT connected, and the input buffers were the fix. Here
the sense divider does the same from the other side of the DUT. The buffers
fixed the first and could not touch the second, because the divider sits
upstream of its own buffer. The general rule is now blueprint §3.4: **any
resistive divider on the DUT node is counted as DUT current**. For any new
network, check where its current returns.

**F-2 — An op-amp at its rail back-fed the Nucleo's 3.3 V rail through the
ADC clamp.** *Resolved by R19, R22 = 1 kΩ.* The BAT54S high-side diode
conducts into +3V3 whenever an ADC buffer output passes ~3.6 V. At 51 Ω only
the OPA2197's own ~65 mA limit bounded it. At 1 kΩ it is ≈ 11 mA per
channel, which the 3.3 V rail absorbs as long as the Nucleo draws more than
it is fed. **That condition is not verified**: it is an H4 measurement (TP8,
Kelvin leads unplugged). The routes are unchanged: unplugged Kelvin leads on
any range, and over-range on ranges 2–3.

## Assembly — what JLCPCB places and what is hand-soldered

Decided 2026-10-06. Each symbol's `Assembly` field is `PCBA`, `hand` or
`DNP`, and the BOM carries the column.

**Hand-soldered (through-hole, not on the PCBA order):** J1 barrel jack, J2
and J5 1×2 headers, J3 and J4 2×3 headers, J6 screw terminal, J7 and J8
morpho sockets, Q1 BD139, and the TP1–TP27 test loops. Through-hole
soldering is within reach; SOIC is what §14.3 ruled out. This removes six
extended-part fees and JLCPCB's through-hole assembly charge.

**Moved to fee-free tiers, no design consequence:** Q2 to JSCJ MMBT3904
(Basic, S-4) and D4/D5 to R+O BAT54S (Preferred: no loading fee on Economic
PCBA — confirm on the quote).

**Kept as extended, Daniel's call (2026-10-06):**

- R5 R_sense: the Basic part's 400 ppm/°C feeds the limiter threshold.
- R11 gate 1 kΩ: 213 mW in a 250 mW 1206 has no margin.
- C5: the electrolytic damps the supply lead, and a ceramic will not.
- D2: stays at 500 mW.

**Net:** 23 PCBA lines — 5 Basic, 1 Preferred, **17 extended → $51** in
loading fees, from 24 extended ($72) before. The planned eight moves would
have saved $24. The F-1 divider gives $3 of it back: R21 no longer shares
the 10 kΩ reel with R14. P-11 adds two lines, Q3 (Preferred) and R25
(Basic), and D6 joins D2's line: **25 lines, 6 Basic, 2 Preferred, 17
extended, still $51**, and the placed parts go to $3.47. Part costs at
JLCPCB/LCSC unit prices, before P-11: **$3.42**
placed by JLCPCB (the three OPA2197s are $2.48 of it) and **$1.79**
hand-soldered from LCSC. Not priced: 26 Keystone 5001 test loops (not
stocked at LCSC; TP6 is a bare pad, C-4), two jumper shunts, the TO-126 heatsink. JLCPCB adds
attrition and any minimum-quantity rounding at quote.
