# hardware/ — PCB revision

KiCad project for the curve tracer PCB. Scope, dates and the non-negotiable
layout constraints live in `curve_tracer_blueprint.md` **§14**; the build
phases and date gates are **§9**. This file is the toolchain and the routing
policy.

MVP scope, unchanged from `firmware/README.md`: **range 1 only, DC sweep, no
pulsed mode, no auto-ranging.** **One revision only** — §14.4 lists what that
buys (test points everywhere, alternate-value footprints, headers over solder).

```
hardware/
├── README.md       ← this file
├── curve-tracer.kicad_pro
├── curve-tracer.kicad_sch
├── curve-tracer.kicad_pcb
├── fab/            ← gerbers, BOM, CPL for the PCBA order
└── lib/            ← project-local symbols and footprints
```

---

## Toolchain

| | |
|---|---|
| **EDA** | **KiCad** (schematic capture, layout, gerber/BOM/CPL export) |
| **Review** | **`kicad-happy` agent skills** — ERC/DRC review, netlist and footprint checks, BOM and CPL sanity before the order goes out |
| **Assembly** | **PCBA** — assembled by the fab. Rationale in §14.3: the OPA2197 is SOIC-only and there are four of them |
| **Routing** | Analog-critical nets **by hand**. Everything else may be autorouted |

The `kicad-happy` skills are a review pass, not an authority. Every §14.5
constraint is a geometric claim about the finished board — trace length,
copper at a node, cap-to-pin distance, return-path separation — and a passing
DRC says nothing about any of them. **Check them against the layout by
measuring, then have the skills review it.** Neither substitutes for the other.

---

## Routing policy

**The analog-critical nets below are routed by hand and are not handed to an
autorouter.** The reason is not aesthetic. This circuit's stability is set by a
parasitic — §3.1 puts stray capacitance at the op-amp inverting node at a pole
of **2–3 MHz, against a ~3 MHz crossover**, worth roughly **45° of phase
margin** — and an autorouter optimises for completion and length, with no model
of node capacitance, return-current paths, or differential symmetry. It will
produce a board that passes DRC and oscillates.

An autorouter is also the wrong tool for a one-revision board for a second
reason: its output is not reviewable. §14.5's constraints have to be *checked*,
and that requires routing someone chose.

### Hand-routed nets

Ordered by how much damage a bad route does.

| # | Net | Why it is hand-routed | Rule |
|---|---|---|---|
| 1 | `FB_SENSE` — `R_sense` tap → op-amp inverting input | The loop's only error signal, on a 7 kΩ node (`R_f ‖ R_g`). §14.5(1) | Shortest practical path. **Never adjacent or parallel to `BD139_C`** — the largest `dV/dt` and the full load current. Cross at 90° if a crossing is unavoidable |
| 2 | `OPA_SWEEP_IN-` — the inverting node itself, with `R_f`, `R_g`, `C_f` | *This is the 2–3 MHz pole.* §14.5(2) | Minimum copper: pads and the shortest links between them. **No ground pour under this node, under `R_f`/`R_g`, or under the `C_f` pads.** `C_f` pads sit immediately beside `R_f` — a footprint reached by a long trace adds stray capacitance to the node it exists to correct (§14.4) |
| 3 | `BD139_B` — op-amp output → `R_B` → BD139 base | `R_B · C_jc` is a ~13 MHz pole inside the loop (§3.1), and this net also carries the clamp-diode discharge, **21.9 mA peak** (sim 09) | Short. Keep `R_B` and the 1N4148 B-E clamp physically at the transistor, not at the op-amp |
| 4 | `BD139_E` → `R_sense` → `R_iso` → `LOAD` | High-current path: **75.2 mA** at the limiter, **107 mA** into a hard short (§3.1) | Wide. Its return goes to the star point on **dedicated copper** — never shared with a sense return (§14.5(4)). `R_sense` and `R_iso` in series, in that order, with the §14.5(5) tap between them |
| 5 | `SHUNT_HI` / `SHUNT_LO` → difference-amp inputs | Worst-case CMRR is **74.4 dB** from resistor tolerance alone (§13); asymmetric routing degrades it and **cannot be trimmed back** | Matched differential pair: equal length, equal width, routed together, same layer. Kelvin-connect at the shunt pads themselves |
| 6 | `KELVIN_HI` / `KELVIN_LO` → ÷4 divider → buffer | The four-wire measurement is what makes `R_iso`'s uncorrected 1.1 V drop harmless (§3.1, §3.4). If this pair is compromised the stability fix is too | Matched pair from the DUT socket terminals. Sensed **at the socket**, not at the nearest convenient copper |
| 7 | `BD139_C` and every op-amp `V+` | Decoupling placement, §14.5(3) | 100 nF within **~5 mm of the pin, measured along the trace**, cap body to pin. Bulk 10 µF on the rail. The collector net is also the 0.89 W node — and the TO-126 **tab is the collector, live at +15 V** (§8): clearance to every adjacent net, no contact with a grounded enclosure |
| 8 | `GND_STAR` and all sense returns | §14.5(4) | One reference point. A shared milliohm at 107 mA is millivolts into a sense path whose range-3 full scale is 100 mV |
| 9 | `DAC_SWEEP` (PA6), `DAC_GATE` (PA4), `ADC1_I`, `ADC2_V` | Low-level analog into 12-bit converters; §3.5 wants the 10 nF at each ADC pin and BAT54S clamps to rails | Keep clear of `BD139_C` and `BD139_E`. 10 nF and clamps at the pin. **PA5 is not usable as a DAC output — it drives LD2** (§3.5) |

Nets 1, 2 and 5 are the three that cannot be fixed by rework if they are
wrong. Route those first, while there is still freedom in the floorplan.

### Everything else

Digital, USB, the Nucleo header fan-out, LEDs, jumper selects: autoroute is
fine, then check it does not cut across nets 1–6 or break the star ground.

---

## Before the order goes out

The Oct 19 design freeze means this list is finished, not started, on Oct 19.
Dates and the Oct 26 abandon-the-PCB checkpoint are in §9.

- [ ] Every node named in §3 has a test point (§14.4 enumerates them)
- [ ] Alternate-value footprints placed: `R_iso`, `R_B`, `R_sense` (§14.4)
- [ ] `C_f` footprint placed beside `R_f`, **unstuffed** — value is fitted
      after measuring on the real board (§14.4)
- [ ] All six §14.5 constraints checked by measuring the layout
- [ ] Headers, not solder, for supply / DUT socket / shunt select / Kelvin
      leads; **Nucleo on headers**
- [ ] TO-126 footprint (not TO-220), heatsink keep-out drawn, tab clearance
      for a net at +15 V
- [ ] BAT54S ADC clamps and gate Zener placed; output-clamp footprint at the
      DUT socket for §3.6's +48% short-recovery overshoot, unstuffed is fine
- [ ] ERC and DRC clean; `kicad-happy` review pass on schematic and layout
- [ ] BOM and CPL checked against §8 — including that `R_f` is **23.2 kΩ**
      (E96; 23.3 kΩ does not exist and has never been orderable)
- [ ] Phase 1 breadboard stability result is in `docs/characterization.md`,
      and it is a **GO**
