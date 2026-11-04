# Curve Tracer

A low-cost semiconductor curve tracer for small-signal MOSFETs and diodes. It
sweeps the voltage across a device, measures the current through it with
four-wire (Kelvin) sensing, and streams the result over USB. A Python host then
fits the device's parameters (threshold voltage, transconductance, channel-length
modulation; diode ideality, saturation current and series resistance) and writes
them out as a SPICE `.model` card. The aim is to close the loop
`device → measurement → model → simulation` on hardware I designed.

It is built as an assembled PCB carrying an STM32 Nucleo-F303RE, with firmware
in C and a Python host.

## Status, 2026-11-03

Every claim below is one of four things. **Measured** means on the bench,
from the board. **Simulated only** means LTspice, ngspice or the firmware
simulator, with no bench result yet. **Done** covers work that needs no
measurement. **Not done** is what's left. Nothing in this README goes past
its row.

| Claim | Status | Evidence |
|---|---|---|
| Analog design: stability into capacitive loads, current limiter, sense-amp CMRR | Simulated only | LTspice sims 02–11, [below](#simulation-results) |
| Schematic and 2-layer PCB, DRC/ERC clean, topology checker | Done | `hardware/review/pass2/` |
| Five boards fabricated and fully assembled by JLCPCB | Done | `hardware/ORDER.md` |
| Firmware runs on the Nucleo; host link works | Measured | 2026-10-30, 2026-11-03 holds (`host/h4/`) |
| Board powers up; loop quiet into 200 Ω ‖ 100 nF at 6 V | Measured | 2026-11-03, [Block 1](#block-1-measurements-first-power-up-board-2) |
| Loop stable with nothing connected (C1 empty) | **Measured: fails.** Oscillates at 0.8–1.15 MHz | [The open-load oscillation](#a-measured-finding-the-open-load-oscillation) |
| Root cause of the oscillation | Analysis and simulation | Sims 12–14 |
| C1 in the 2.2–4.7 pF range damps it | Simulated only (TI's op-amp model, open load and 200 Ω ‖ 100 nF) | Sims 14–14f; not fitted, since 0603 can't be hand-fitted here. Rev 2 specifies 4.7 pF |
| 470 Ω across the device keeps the loop quiet | Simulated only | Sim 13; bench test is next session's step 13 |
| Voltage and current accuracy against a DMM | Not done | Next session, step 15 |
| R_p subtraction, extraction, `.model` card, ngspice overlay | Done, tested on simulated data only | `host/`, 159 tests; [demo figures](host/README.md#from-a-capture-to-the-overlay) |
| Diode parameters from a real diode | **TBD**, next session | `hardware/MVP_CARD.md` §D |
| Measured vs simulated overlay, real diode | **TBD**, next session | `python -m ct_host overlay` |
| MOSFET parameters from a real part | **TBD**, stretch goal of the next session | |
| Blueprint §6 closed loop: build a circuit with the extracted model, compare | Not done | |
| Short-circuit and thermal test (H4 Block 4) | Not done | No heatsink insulator at the bench |
| Current ranges 2 and 3 (fitted on the board) | Not done | Out of scope |

**The headline figure goes here**: one real diode, measured against the
ngspice simulation of its extracted model, with residuals. The pipeline that
draws it is built and tested. On simulated data it looks like
[this](media/demo_overlay_diode_SIMULATED.png), and that figure is labelled
SIMULATED because it is. The bench data comes from the next session.

![3D render of the assembled board](hardware/review/pass2/p2_3d.png)

*KiCad render of the routed board (Pass 2, 2026-10-06), not a photograph. The
Nucleo plugs into the two sockets on the right. Board size 135 × 92 mm, two
layers.*

## What it can measure

The design envelope. Nothing in it is measured yet unless the row says so.

| | |
|---|---|
| **Devices** | Two-terminal devices (diodes, LEDs, resistors) and **N-channel enhancement MOSFETs**. **No BJTs**: the step source is a voltage through 1 kΩ, not a base current. **No P-channel or depletion parts**: the gate source is 0 to +10 V |
| **Polarity** | **One quadrant.** Drain/anode at 0 to +10 V and current into the device only. No reverse bias |
| **Voltage** | 0–10 V by design; 9.06–9.73 V is the ceiling at 50 mA (analysis: the PTC fuse's drop). On this board the sweep DAC is guaranteed only from 0.66 V at the node, and above ~6.6 V the Nucleo's LED loads it. Both are estimates, to be measured next session |
| **Current** | 0–50 mA on range 1, 40.3 µA per ADC count, averaged 64× per point. Hardware limiter ~75 mA (simulated); firmware limit set per device |
| **Mode** | **DC only.** No pulsed mode, so the device heats at its own dissipation |
| **Accuracy** | Not yet measured. Block 1's voltage/current ratio agreed with the load resistance to 0.13%, but that ratio cancels a shared reference error, so it is not an accuracy figure |
| **Until rev 2** | Low-current devices need a resistor (≤ 470 Ω) across them to keep the loop quiet (simulated). The host subtracts its current. That costs resolution at the low end: ~6 µA at 0.6 V for a 0.5% error in R_p |

**What it's for.** It replaces the undergraduate I-V lab done by hand with
a bench supply and two meters, one point at a time, for small diodes, LEDs
and small N-MOSFETs. It records the curve with four-wire sensing and fits a
SPICE model from it. **What it isn't:** a general-purpose commercial curve
tracer or source-measure unit. Those cover high voltage and current, both
polarities, pulsed measurement, BJTs and picoamp leakage. This covers none of
them.

## A measured finding: the open-load oscillation

**Measured, 2026-11-03, board 2, C1 empty.** Holding 6 V into
200 Ω ‖ 100 nF, the loop was quiet. With nothing connected it oscillated
intermittently at **0.79–1.15 MHz**, from over 0.2 V to over 2 V
peak-to-peak (the scope clipped). The DC
readings were off by up to 3 mA while it did. Full data is in
[Block 1](#block-1-measurements-first-power-up-board-2) below and in
[`docs/characterization.md`](docs/characterization.md).

**Root cause (analysis, checked in LTspice sims 12–14).** With no load, the
pass transistor (Q1) carries only ~0.2 mA. Its emitter resistance is then
~130 Ω, and it drives the ~1 nF of the protection diode D3 through ~41 Ω.
That puts a pole near 0.8 MHz inside the loop. Under the 200 Ω load, Q1 runs
at 26 mA and the pole moves far out. So the problem depends on the load,
which is why it shows up well below the ~3 MHz the design had estimated for
the op-amp's input-capacitance pole. The generic op-amp model reproduces
the oscillation only with 20–30 pF of input capacitance added. TI's own
OPA2197 model needs none: at open load it rings at 0.91 MHz, each
half-cycle 0.83× the last, close to sustained.

**The fix (simulation, sims 14–14f, TI's model).** The board has an empty
footprint for C1, a capacitor across the feedback resistor. The predicted
value is **3.4–3.9 pF**. At 6 V open load, 3.3 pF cuts the ring to 0.40×
per half-cycle, and 4.7 pF removes it, with no sign of over-compensation.
The generic model's figure, 8.6–12.9 pF, would over-compensate. Because the
bench was less damped than TI's model, rev 2 specifies **4.7 pF**
(`hardware/DECISIONS.md` R2-4). That rests on one vendor model. C1 is a
0603 part, which I can't fit reliably by hand, so it isn't fitted on rev 1.
Rev 2 has the assembler fit it.

**Working around it until then (simulation, sim 13).** A resistor of 470 Ω or
less clamped across the device keeps the bare loop quiet from 0.1 V up. The
host subtracts its current using the measured voltage. The next bench session
tests that first, at 0.1 V and 0.3 V.

## Design decisions

Each of these is backed by a simulation, a calculation or a datasheet figure.
The full record, part by part, is [`hardware/DECISIONS.md`](hardware/DECISIONS.md);
the reasoning is in [`curve_tracer_blueprint.md`](curve_tracer_blueprint.md).

1. **Isolate the capacitive load; don't compensate it.** The obvious fix, a
   capacitor across the feedback resistor, made the loop *worse* at every value
   from 1 to 100 pF. Instead, a 22 Ω `R_iso` sits outside the loop, and Kelvin
   sensing makes its 1.1 V drop at 50 mA harmless (sims 02, 03).
2. **Model fidelity decided the answer.** With a generic 2N2222 model the
   loop looked unconditionally stable. ST's published BD139 model (f_T ≈ 54 MHz,
   C_jc 36 pF) oscillated immediately. A third-party BD139 model found online
   had placeholder junction capacitances (`CJE = CJC = 1e-11`) and would have
   hidden the problem. A separate false result, 9% overshoot, turned out to be
   a solver timestep artefact. Capping the timestep removed it
   (blueprint §12).
3. **Base resistor 330 Ω, not 680 Ω.** Both are stable in simulation, but
   680 Ω leaves ~44° of implied phase margin, against ~59° for 330 Ω. The
   op-amp's own input capacitance adds a pole the simulation does not contain
   (estimated 5–9 pF), and from 44° that loss is not recoverable (sim 08).
4. **A base-emitter clamp diode.** On a falling edge the op-amp slams to its
   rail while the load holds the emitter up, and V_BE reaches −9 V against the
   BD139's 5 V rating. A 1N4148 holds it to −0.74 V (sims 08, 09).
5. **A hardware current limiter**, Q2 across a 10 Ω `R_sense`, independent of
   the firmware limit. 15 Ω was rejected because its trip point (~49–50 mA)
   falls inside the sweep range (sims 10, 11).
6. **Buffer the difference amplifier's inputs.** Unbuffered, the resistor
   bridge alone draws 475.6 µA through the shunt with nothing connected. That
   is 0.95% of full scale on range 1 and makes range 3 unusable. The design
   went from two to three dual op-amps (sims 06, 07).
7. **0.1% resistors in the difference amp**, because common-mode rejection
   comes from resistor matching alone and cannot be trimmed afterwards (sims 04,
   05).
8. **One board revision, designed for it.** There is a test point on every
   node, footprints for alternate values, headers instead of soldered
   connections, and a footprint for the compensation capacitor, left empty.
   JLCPCB assembled every part on all five boards.
9. **The host slices on *measured* voltage, never the commanded voltage.** At
   one commanded voltage, curves at different currents reach different real
   voltages because of `R_iso`'s drop. Grouping by the command gives a
   convincing but wrong threshold voltage. The diode fit solves n, I_S and R_s
   jointly; a windowed semilog fit was 13% wrong on n at R² = 0.9965
   ([`host/README.md`](host/README.md)).

Two decisions changed when they met reality. They are recorded as rev-2 items,
not hidden:

- **The F303RE has no DAC2.** The board routed the sweep to a pin with no DAC.
  This was found at the first real firmware build. The fix is a jumper on the
  Nucleo from PA5 (DAC1_OUT2) to PA6. PA5 also drives the Nucleo's LED, which
  loads the DAC and may cut sweeps above about 6.6 V (estimated, not yet
  measured; `DECISIONS.md` R2-3).
- **The empty compensation-capacitor footprint assumed hand-fitting**, a
  0603 part, which I could not do reliably. Rev 2 has JLCPCB fit it, at
  4.7 pF (`DECISIONS.md` R2-2, R2-4).

## Simulation results

**All of these are simulated.** LTspice files are in [`sim/`](sim/), with
per-file detail in [`sim/README.md`](sim/README.md). The sweep-source sims
ran at R_f = 23.3 kΩ; the board has 23.2 kΩ, a 0.4% difference below the
precision of every figure here.

| Question | Result (simulated) | Simulation |
|---|---|---|
| Capacitive load the sweep source tolerates | Without `R_iso`: stable to ~1 nF, oscillating by 2.2 nF. With 22 Ω: clean from 100 pF to 100 nF | LTspice, `sim/03_sweep_source_load_sweep.asc` |
| Small-signal step, 100 nF ‖ 200 Ω, R_B = 330 Ω | 10.34% overshoot, 0.50 µs to 1%, ζ ≈ 0.59 (~59° implied phase margin) | LTspice, `sim/08_sweep_source_rb_sweep.asc` |
| Reverse V_BE on a falling edge, 100 nF load | −7.72 V → −0.73 V (200 Ω load); −8.98 V → −0.74 V (open), with the clamp | LTspice, `sim/08…`, `sim/09_sweep_source_clamped.asc` |
| Current-limiter trip; hard short | 75.2 mA through R_sense; 107.0 mA load; BD139 at 891 mW | LTspice, `sim/11_limit_sizing.asc` |
| Overshoot on recovery from a short, 100 pF load | 14.8 V peak (+48%); back within 1% in 1.9 µs | LTspice, `sim/10_current_limit.asc` |
| Difference-amp CMRR, worst-case 0.1% corner | 74.42 dB | LTspice, `sim/04_diffamp_cmrr.cir` |
| CMRR, 500-run Monte Carlo at 0.1% | median 88.26 dB, p5 79.43 dB, min 76.20 dB | LTspice, `sim/05_diffamp_mc.cir` |
| Phantom current, unbuffered diff amp, no DUT | 475.6 µA at 1 Ω shunt | LTspice, `sim/06_diffamp_loading.cir` |

![CMRR Monte Carlo histogram](media/cmrr_mc.png)

*Simulated: CMRR over 500 Monte Carlo runs with 0.1% resistors
(`sim/05_diffamp_mc.cir`). LTspice draws uniform, independent tolerances, so
this spread is conservative.*

Sims 02–11 didn't model D3's ~1 nF, the PTC or the Kelvin divider; sim 12
added them. That is the gap the board fell into at open load: see
[the finding](#a-measured-finding-the-open-load-oscillation).

### Host software, closed loop on a simulated device

`ct_sim` is the real firmware core (sweep engine, CSV writer, command parser,
current limit), compiled for the desktop with a modelled device behind it. The
host's tests feed it known parameters, run a sweep, extract the parameters, and
require the same values back. **Simulated, `ct_sim`:**

| Fed in | Recovered |
|---|---|
| V_th = 2.15 V | 2.1502 V (0.2 mV) |
| k = 0.055 A/V² | 0.05506 (0.1%) |
| λ = 0.012 /V | 0.01192 (0.7%) |
| diode n = 1.75 | 1.7605 (0.6%) |
| diode I_S = 2.5 nA | 2.73 nA (9%; quantisation, explained in [`host/README.md`](host/README.md)) |
| diode R_s = 0.6 Ω | 0.5914 Ω (1.4%) |

With a 470 Ω resistor beside the device, its current subtracted, and the
extracted card run back through ngspice, the simulated diode comes back as
n = 1.751, I_S = 2.52 nA and R_s = 0.601 Ω, with a 0.63 mV rms residual
([`host/README.md`](host/README.md#from-a-capture-to-the-overlay)). 159
host tests and the firmware unit suites pass. That validates the software
path only. It says nothing about the analog hardware.

## Block diagram

```
   Nucleo-F303RE                     Board
  ┌──────────────┐
  │ DAC1_OUT2 PA5├─shunt─► PA6 ─► [×3.32] ─► [OPA2197 + BD139 follower] ─► R_sense ─┬─► R_iso 22Ω ─► PTC ─► shunt ─► DUT drain
  │              │                                ▲      │                         │                        │            │
  │              │                                │   [Q2 current limiter]        │                   [buffered     [Kelvin pair
  │              │                                └─────────── feedback ──────────┘                   diff amp ×20]  ÷4 + buffer]
  │ ADC1  PA0   ◄├──────────────────────────────────────────────────────────────────────────────────────────┘            │
  │ ADC2  PC0   ◄├───────────────────────────────────────────────────────────────────────────────────────────────────────┘
  │ DAC1_OUT1 PA4├─────► [×3.32] ─► [buffer] ─► 1 kΩ ─► DUT gate  (12 V Zener clamp)
  │ USART2 ◄─────┼─► ST-LINK VCP ─► USB ─► Python host
  └──────────────┘                                                     DUT source ─► GND        (SMAJ12A TVS on the drain)
```

Per point: set the gate DAC, set the drain DAC, wait to settle, oversample both
ADCs 64×, send a CSV row. The host recomputes current and voltage from the raw
accumulators and checks them against the firmware's own numbers.

## PCB

![Top view of the routed board](hardware/review/pass2/p2_top.png)

*KiCad render, top view (`hardware/review/pass2/`). The analog section is on the
left, with the Nucleo sockets J7/J8 on the right. Q1's heatsink keep-out is
marked at the top left.*

- The analog-critical nets were routed by hand: the feedback node, the
  inverting input, the base drive, the shunt and Kelvin pairs. The rest was
  autorouted (Freerouting) with those nets locked
  ([`hardware/README.md`](hardware/README.md), *Routing policy*).
- DRC and ERC are clean with schematic parity
  (`hardware/review/pass2/metrics.txt`). `check_topology.py` asserts the
  circuit's topology from the netlist (59 checks) and catches all 14 faults
  its self-test plants, which ERC passes.
- Every net that crosses the ground split, and its distance to the star
  tie: [`p2_split_crossings.png`](hardware/review/pass2/p2_split_crossings.png).

## A bench finding: the ST-LINK serial link on macOS

The first time the host talked to the Nucleo (2026-10-30), every command timed
out. A single host write of **16 bytes or more** stopped the ST-LINK/V2-1's
virtual COM port passing data from host to target until the USB cable was
replugged. This was on firmware V2J33M25, under macOS. Writes of 8 bytes,
5 ms apart, got through. The first write after the ST-LINK enumerates was also
lost.

To rule out the firmware, I read the MCU state over SWD while the link was
wedged. The main loop was idle, USART2 was configured, and no bytes were
reaching the RX pin (PA3). The fault is upstream of the MCU, in the ST-LINK's
USB-to-UART bridge. The fix is host-side: the transport writes in 8-byte
chunks 5 ms apart and opens with a blank line, which the firmware's parser
ignores. A regression test checks that no single write reaches 16 bytes. After
the fix, two hold runs back to back worked after a replug (commit `2debc57`).
An ST-LINK firmware upgrade might also fix it. That is untested.

## Bench record

### Block 1 measurements: first power-up, board 2

**Measured, 2026-11-03**, from [`hardware/MVP_CARD.md`](hardware/MVP_CARD.md)
(raw data in `host/h4/mvp_*.csv`; full log in
[`docs/characterization.md`](docs/characterization.md)). A pass here shows
no sustained oscillation under a DC hold. It does not measure phase margin
or ringing (H4 step 5, not run). C1, the compensation capacitor, is empty.

| Measurement | Pass band | Result |
|---|---|---|
| Supply current at power-up | 3–25 mA | 3 mA, supply in CV (rails not checked) |
| Scope baseline at TP3, idle (B) | < 10 mV p-p | 12.0 mV, board powered |
| Hold 6 V into 95.2 nF ‖ 202 Ω (measured): p-p at TP3 | ≤ B + 5 mV | 12–30 mV; 26.8 mV, and 26.0 mV with the probe ground moved. Broadband, no periodic component |
| … measured V, I | 4.8–5.5 V, 23–29 mA | 5.193 V, 25.74 mA (5.193 V / 202 Ω = 25.71 mA) |
| Hold 6 V, open load: p-p at TP3 | ≤ B + 5 mV | **Oscillates**: > 0.2 V to > 2 V p-p (clipped), varying run to run |
| … measured V, I | 5.7–6.2 V, ≤ 0.5 mA | 6.006–6.192 V, 0.83–3.0 mA; the largest oscillation gave the largest errors |
| Oscillation frequency | — | ~0.79 MHz (read while clipped) and 1.149 MHz |
| **Block 1 verdict** | | **Fail**: no sustained oscillation with a 200 Ω ‖ 100 nF load; intermittent ~0.8–1.15 MHz oscillation at open load, C1 empty |

The 26 mV under load is over the card's limit, but it is broadband noise,
not oscillation. The limit allowed less than 2 DAC steps at TP3.

### Next session

`hardware/MVP_CARD.md` §D: about 45 minutes, no soldering. In order:
1. 470 Ω across D–S, held at 0.1 V and 0.3 V with the scope watching. If
   it oscillates, the 200 Ω ‖ 100 nF load that was quiet in Block 1 takes
   its place.
2. A calibration sweep of that resistor.
3. Six accuracy points against a DMM.
4. One diode with the resistor beside it, unless the DAC's floor reads
   above 0.2 V; then the session stops here.
5. A small N-MOSFET, if there's time.

Then, at the desk, the model card, the ngspice run and the overlay above.

## Repository

`hardware/`: KiCad project, decisions record, bring-up cards, order files ·
`firmware/`: STM32 firmware, host-side simulator `ct_sim`, unit tests ·
`host/`: Python capture, extraction, model cards and the ngspice overlay · `sim/`: LTspice and
Monte Carlo · `docs/`: characterization plans · `curve_tracer_blueprint.md`:
the design document.

## Cost

From `hardware/ORDER.md`, at the 2026-10-11 prices:

| | Total | Per board (÷ 5) |
|---|---|---|
| JLCPCB: PCB, assembly and parts | $137.98 | $27.60 |
| Shipping, duty and sales tax on that order | $97.07 | $19.41 |
| **Assembled board, all-in** | **$235.05** | **$47.01** |
| Nucleo-F303RE (DigiKey 497-15105-ND, $20.13 on 2026-10-11) | | $20.13 |
| **One instrument** | | **$67.14** |

**Not in that figure:**
- the +15 V bench supply, the scope and the DMM;
- the USB cable;
- $48.05 of bring-up and contingency parts (test loads, the C_f kit,
  heatsinks).

The first build came to **$283.10**: the JLCPCB order plus those parts,
with the Nucleo from the lab cabinet. Fixed costs dominate a five-board run.
The extended-part loading fees alone are $55.62, more than the $45.59 of
components.

Low unit cost isn't the goal. The 0.1% resistors and the three OPA2197s
add a few dollars per board. They are what would make the closed-loop result
credible.
