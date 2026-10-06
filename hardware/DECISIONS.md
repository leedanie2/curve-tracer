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
| <a id="c1"></a>C1 | C_f | **DNP**, footprint only | Blueprint §3.1, §14.4 | `C_f = C_in · R_g / R_f`. With the breadboard estimate `C_in` = 5–10 pF that gives **2.16–4.31 pF**. On the PCB `C_in` is different and smaller, so no value can be chosen yet | **H4**: measure, fit, then sweep both directions. Overshoot near 25% means re-fit `C_f`, not "marginal loop" (§3.1 diagnostic) |
| <a id="r3"></a>R3 | R_B | **330 Ω** 1%, 2512 1 W | Blueprint §3.1. Sims 08, 09, 10, 11. Package: Capture C-3 | **Why 330 and not 680:** sim 08 (re-run 2026-09-22) gives 10.3% small-signal overshoot into 100 nF / 200 Ω at 330 Ω (ζ ≈ 0.59, ~59° PM) against 21.4% at 680 Ω (~44°). The un-simulated 2–3 MHz stray input pole costs ~45°, which is recoverable from 59° with `C_f` and not from 44°. **Why not 100 Ω:** sim 10 (2026-09-18) gives a held-short load current of 107 mA at 330 Ω against 143 mA at 100 Ω, and at 330 Ω the op-amp supplies 32 mA, outside its own 65 mA limit. Clamp discharge peaks at 21.9 mA (sim 09). 680 Ω would have bought nothing that still matters (§3.1, PTC reclassified) | H4: overshoot into 100 nF, with `C_f` swept. With the limiter tripped, the drop across R_B gives op-amp current, to confirm it is out of its limit (§3.1) |
| <a id="r4"></a>R4 | R_B alt | **DNP**, THT axial parallel to R3 | Blueprint §14.4 | 330 Ω was chosen over 680 Ω on a sim-only overshoot difference that no bench measurement has checked. The footprint takes the 0207/0309 axial parts already on hand (§8: 330 Ω ×5) without SMD rework | Fit only if H4 overshoot disagrees with sim 08 |
| <a id="q1"></a>Q1 | BD139 (ST) | — | Blueprint §3.1, §8. Substitution S-2 | Pass transistor, TO-126. Tab = collector = +15 V. Worst-case dissipation **0.89 W** (sim 11, hard short). **Layout-time check (H2):** ST and onsemi number this part's pins in opposite directions — see [L-1](#layout-time-checks) | H4: thermal under a sustained short |
| <a id="d1"></a>D1 | 1N4148W | — | Blueprint §3.1. Sim 09. Substitution S-3 | B-E clamp, anode at emitter. Unclamped, V_BE reaches −6.3 V (100 pF open) and −9.0 V (100 nF open) against `V_EBO` = 5 V (sim 08). Clamped: −0.58 / −0.74 V (sim 09, 2026-09-18) | H4: falling edge into 100 pF open, against sim 09's 1.7 µs |
| <a id="q2"></a>Q2 | MMBT3904 | — | Sims 10, 11 (§3.1 names only "a second transistor"). Substitution S-4 | Sims use the 2N3904. The fitted Rohm SST3904 model (SOT-23) agrees within 2% (sim 10). V_BE ≈ 752 mV at R_B = 330 Ω (sim 11). Dissipates 53 mW in a held short (sim 10) | H4: trip point, re-measured warm (−2 mV/°C) |
| <a id="r5"></a>R5 | R_sense | **10 Ω** 1%, 1206 0.75 W | Blueprint §3.1. Sim 11. Package: Capture C-3 | Threshold `V_BE / R_sense` = **75.2 mA** (sim 11, 2026-09-18), 50% over the 50 mA spec. 15 Ω is rejected because its threshold of 48.8–50.2 mA sits inside the sweep spec. 12 Ω is rejected on thermal margin: −2 mV/°C over a 20 °C rise takes it to ~57.6 mA, 15% clear (analysis, §3.1). Dissipation 57 mW at the threshold | **H4: trip threshold, cold and warm.** §3.1 calls the drift "the figure most likely to disagree with simulation" |
| <a id="r6"></a>R6 | R_sense alt | **DNP**, THT axial parallel to R5 | Blueprint §14.4 | As R4. §8 has 10 Ω ×5 on hand | Fit if H4 trip point disagrees with 75.2 mA |
| <a id="r7"></a>R7 | R_iso | **22 Ω** 1%, 2512 1 W | Blueprint §3.1. Phase 0 sim 03 (§12, item 4). Package: Capture C-3 | With 22 Ω, the loop is clean at the emitter and the output from 100 pF to 100 nF. Bare, it is stable only to ~1 nF and oscillates by 2.2 nF. Drop of 1.10 V at 50 mA is uncorrected and made harmless by Kelvin sensing (§3.4). Dissipation 252 mW in a hard short (107 mA, sim 10) | **H4.** Never confirmed on hardware: stage 8 was never reached |
| <a id="r8"></a>R8 | R_iso alt | **DNP**, THT axial parallel to R7 | Blueprint §14.4 | As R4. §8 has 22 Ω ×5 on hand | Fit if H4 shows ringing into 100 nF |
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
| <a id="d3"></a>D3 | Output clamp | **DNP, type open** | Blueprint §14.6 | Footprint for §3.6's +48% short-recovery overshoot: 14.8 V at the socket on a 10 V setpoint (sim 10, peak trustworthy, duration not). Mitigation unresolved — open O-3 | **H4**: bench-verify the overshoot magnitude (§3.6) |
| <a id="j5"></a>J5 | Kelvin leads | 1×2 header | Blueprint §14.4 | — | — |

## Current sense — blueprint §3.3

| Ref | Part | Value | Source | Evidence | Bench |
|---|---|---|---|---|---|
| <a id="u2"></a>U2 (A, B) | OPA2197IDR, input buffers | — | Blueprint §3.3. Sims 06, 07. §13 | Unbuffered, the bridge draws **475.6 µA** of phantom current with no DUT connected (sim 06, 2026-09-18): 0.95% of range 1 full scale. Sim 07's buffered "0" comes from ideal E sources and proves the topology only, not bias-current performance | Phase 2 |
| <a id="u3"></a>U3 (A) | OPA2197IDR, difference stage | — | Blueprint §3.3 | — | — |
| <a id="r15"></a>R15, <a id="r17"></a>R17 | R3, R1 | **1 kΩ 0.1%** | Blueprint §3.3. Sims 04, 05 | Gain `R2/R1` = 20. CMRR comes from resistor matching: **74.4 dB** worst-case corner at 0.1% (sim 04). Monte Carlo median **88.26 dB** (sim 05, n = 500, 2026-09-18) | **H4 / Phase 2**: measured CMRR against the 74.4 dB floor |
| <a id="r16"></a>R16, <a id="r18"></a>R18 | R4, R2 | **20 kΩ 0.1%** | Blueprint §3.3. Sims 04, 05 | As above. All four resistors are the same Yageo RT0805 25 ppm family, for matching | As above |
| <a id="r19"></a>R19 | Isolation, ADC1 | **51 Ω 1%** 0603 (C23197, Basic) | Datasheet: OPA2197 §7.3.5 and Table 3. **Decision, 2026-10-06.** Blueprint §3.5, §3.7 | U3A drives 10 nF at the ADC pin. Table 3: 20 Ω gives 45° phase margin, 51 Ω gives 60°. Daniel chose 60°: "a DC-accuracy path with no bench time budgeted for debugging a marginal buffer." DC cost: ≤ 2 µA BAT54S leakage × 51 Ω = **0.10 mV**, about 0.13 LSB | — |
| <a id="c3"></a>C3 | ADC1 cap | **10 nF** | Blueprint §3.5 | "10 nF cap at each ADC pin" | — |
| <a id="d4"></a>D4 | ADC1 clamp | BAT54S | Blueprint §3.5, §3.6 | Clamped to GND and +3V3 | — |

## Voltage sense — blueprint §3.4

| Ref | Part | Value | Source | Evidence | Bench |
|---|---|---|---|---|---|
| <a id="r20"></a>R20 | Divider top | **30 kΩ 0.1%** | Blueprint §3.4 | ÷4: 10 V → 2.5 V at ADC2 | **Phase 3**: Kelvin V_DS tracks a DMM within 0.5% |
| <a id="r21"></a>R21 | Divider bottom | **10 kΩ 0.1%** | Blueprint §3.4 | Returned to **KELVIN_LO**, not GND, because the README's routing table runs KELVIN_HI/LO as a pair into the divider. ADC2 is ground-referenced, so it reads `V_LO + V_DS/4`. The source-lead drop therefore enters at ¾ weight rather than full weight. That is a §3.4 limitation, not a capture error | As R20 |
| U3 (B) | Kelvin buffer | — | Blueprint §3.4 | Unity gain | — |
| <a id="r22"></a>R22 | Isolation, ADC2 | **51 Ω 1%** 0603 (C23197, Basic) | As R19 | U3B is a **unity-gain** buffer, the configuration the datasheet rates to only 1 nF of direct drive | — |
| <a id="c4"></a>C4 | ADC2 cap | **10 nF** | Blueprint §3.5 | — | — |
| <a id="d5"></a>D5 | ADC2 clamp | BAT54S | Blueprint §3.5, §3.6 | — | — |

## Power, ground, MCU

| Ref | Part | Value | Source | Evidence | Bench |
|---|---|---|---|---|---|
| <a id="j1"></a>J1 | Barrel jack | DC-005, 2.0 mm pin | Blueprint §8 (15 V / 1 A adapter + barrel jack) | Check the adapter's plug before ordering: a 2.0 mm pin takes 5.5×2.1 plugs, not 5.5×2.5 | — |
| <a id="j2"></a>J2 | Supply header | 1×2 | Blueprint §14.4 ("headers, not soldered connections, for the supply") | In parallel with J1. No reverse-polarity protection — §3 specifies none | — |
| <a id="c5"></a>C5 | Bulk | **10 µF**, 50 V aluminium electrolytic | Blueprint §8 (≥25 V), §14.5(3) | 50 V is what is stocked in 5×5.4 mm, above the ≥25 V floor | — |
| <a id="c6"></a>C6, <a id="c7"></a>C7, <a id="c8"></a>C8 | Op-amp decoupling | **100 nF** X7R 50 V | Blueprint §8, §14.5(3) | One per OPA2197 V+, within ~5 mm | — |
| <a id="nt2"></a>NT2 | Star point | — | **Capture C-2** | §14.5(4) | — |
| <a id="j7"></a>J7, <a id="j8"></a>J8 | Nucleo CN7 / CN10 | 2×19 sockets | Blueprint §14.4. `firmware/README.md` pin table | PA0 = CN7-28 (ADC1_IN1), PA4 = CN7-32 (DAC1_OUT1), PC0 = CN7-38 (ADC2_IN6, default solder bridges), PA6 = CN10-13 (DAC2_OUT1). Verified against **UM1724 Rev 14 Table 26**. PA5 unused (LD2, §3.5). Nucleo is USB-powered: +15 V exceeds VIN max | — |
| <a id="tp"></a>TP1–TP27 | Test points | Keystone 5001 loops; TP6 a bare pad | Blueprint §14.4. TP6: Capture C-4 | Every node §14.4 lists, plus every other named net except the op-amp input nodes DA_P, DA_N, GATE_IN- and the per-shunt pads SH1–3_TOP, which SHUNT_HI reaches when selected | — |

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
| S-4 | 2N3904 (sim part) | onsemi MMBT3904LT1G (SOT-23) | SMD for PCBA | Same die. The SST3904 cross-check in sim 10 was already a SOT-23 part |
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

## Open findings (design, not values)

Found while making the 2026-10-06 changes. Not acted on.

**F-1 — The Kelvin divider's current is measured as DUT current.** R20 + R21
(40 kΩ) hang from KELVIN_HI, which is the DUT drain: on the DUT side of the
shunt. So the shunt carries `I_DUT + V_DS / 40 kΩ`, which is **25 µA per
volt**, 250 µA at 10 V. Nothing in `firmware/` or `host/` subtracts it. On
range 1 that is 0.5% of full scale at 10 V, and 2.5% when measuring 10 mA,
which fails Phase 2's "known resistor within 1%". On ranges 2–3 it swamps the
reading. §3.4's stated reason for the buffer, "so the divider doesn't load
the DUT", is not what the buffer does: it stops the ADC loading the divider.
This is the same mechanism as §13's phantom current: a sense network drawing
its current through the shunt.

**F-2 — An op-amp at its rail back-feeds the Nucleo's 3.3 V rail through the
ADC clamp.** The BAT54S high-side diode conducts into +3V3 whenever an ADC
buffer output exceeds ~3.6 V. 51 Ω does not limit that current; the
OPA2197's own ~65 mA output limit does. The Nucleo's 3.3 V LDO cannot sink
current. Two routes there: an over-range on ranges 2–3 (above 1.65 mA on
range 2, the difference amp wants more than 3.3 V), and **unplugged Kelvin
leads on any range**, which leave the U3B input floating.
