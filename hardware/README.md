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
├── DECISIONS.md    ← where every value on the board came from: blueprint, sim or bench
├── curve-tracer.kicad_pro
├── curve-tracer.kicad_sch   ← H1, captured Oct 5, 2026
├── curve-tracer.kicad_pcb   ← H2, routed Oct 6, 2026: 135 × 92 mm, two layers
├── fp-lib-table    ← registers lib/ as footprint library `curve-tracer`
├── lib/curve-tracer.pretty/  ← two project footprints: J3/J4 range select, J7/J8 Nucleo socket
├── tools/check_topology.py   ← asserts the §3 / §14.5 topology; run after every edit
├── tools/export_fab.py       ← writes everything in fab/; run before every order
├── fab/            ← engineering BOM, Gerbers + drill, and the JLCPCB upload set in fab/jlc/
├── review/         ← layout renders and metrics, pass1/ and pass2/: the evidence for the write-up
├── analysis/       ← gitignored; kicad-happy analyzer runs
└── datasheets/     ← gitignored; re-sync with the lcsc skill's sync_datasheets_lcsc.py
```

Symbols are stock KiCad 10. So are the footprints, except two. J3/J4 is a
stock 2×3 header with silkscreen added (RNG1–RNG3 per row, and "J3=J4
POS"). J7/J8 is the stock 2×19 socket with its pad numbering mirrored for a
board the Nucleo plugs into (`DECISIONS.md` L-2). Each symbol carries `MPN`, `Manufacturer`, `LCSC` and
`Provenance` fields. `Provenance` links to the symbol's row in `DECISIONS.md`.

### Checking the schematic after an edit

The schematic is the source of truth and is edited by hand from here on. ERC
proves it is legal; it does not prove it is the circuit §3 describes. Run
both:

```
kicad-cli sch erc --severity-all hardware/curve-tracer.kicad_sch
python3 hardware/tools/check_topology.py --self-test
```

`check_topology.py` exports the netlist through kicad-cli and asserts every
connection §3 depends on: each op-amp pin, the three gains and the ÷4, the
§14.5(5) tap position, limiter and clamp polarity, the Nucleo pin map, star
ground, and test-point coverage. `--self-test` also plants eleven faults that
ERC passes, and fails if any goes uncaught. Change a value on purpose →
change the matching assertion in the same commit.

**For H2:** KiCad ships a `STM32_Nucleo-64_Morpho` project template
(`KiCad.app/Contents/SharedSupport/template/`). Its board places the two
2×19 morpho sockets at the correct spacing, with the mounting holes. Take
the CN7/CN10 geometry from it rather than measuring a Nucleo.

---

## Toolchain

| | |
|---|---|
| **EDA** | **KiCad 10.0.6** (schematic capture, layout, gerber/BOM/CPL export) |
| **Review** | **`kicad-happy` v2.3.0** agent skills — ERC/DRC review, netlist and footprint checks, BOM and CPL sanity before the order goes out |
| **Assembly** | **PCBA** — assembled by the fab, **express shipping** (§14.3, §14.3a) |
| **Routing** | Analog-critical nets **by hand**. Everything else autorouted with **Freerouting v2.5.0** (`DECISIONS.md` P-6) |

### Installed state

All five are installed on this machine: the first four as of **Oct 5, 2026**,
Freerouting on Oct 6. `kicad-happy` must be present before **H1** (§9), and
it is.

| | |
|---|---|
| KiCad | **10.0.6**, `/Applications/KiCad/KiCad.app`, CLI at `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli`. Installed from the official universal `.dmg`, **not** Homebrew — the cask writes to a root-owned path and wants a sudo password. Upgrades are therefore manual: fetch a new `.dmg` from kicad.org |
| `kicad-happy` | **v2.3.0** (`aklofas/kicad-happy`), cloned to `~/.claude/kicad-happy`, with all **11** skills symlinked into `~/.claude/skills/` — `kicad`, `spice`, `emc`, `datasheets`, `bom`, `digikey`, `mouser`, `lcsc`, `element14`, `jlcpcb`, `pcbway`. Global, so available in every project. **Upgrade with `git pull` in that clone** — upstream documents `/plugin update` as unreliable, which is why this is a symlink install rather than a marketplace plugin |
| KiCad library tables | Default global `sym-lib-table` / `fp-lib-table` copied from the bundled template into `~/Library/Preferences/kicad/10.0/` on Oct 5, 2026. KiCad's first-run dialog normally does this; it had never been run here, so `kicad-cli sch erc` reported every symbol as an unknown library |
| Freerouting | **v2.5.0**, `~/.local/share/freerouting/freerouting-2.5.0.jar`, from the GitHub release (`freerouting/freerouting`). Installed Oct 6, 2026; SHA-256 `f6f51bb0…ffeb5de3c7` matches the release's published digest. Runs on Homebrew `openjdk` 25.0.2, which was already installed. **Headless only**: `java -Djava.awt.headless=true -jar <jar> --gui.enabled=false -de board.dsn -dr board.rules -do board.ses`. Even `--version` hangs once the GUI starts. Not a KiCad plugin: the board goes out as a SPECCTRA `.dsn` and comes back as a `.ses` (P-6 has the method). Upgrade by downloading the new release JAR and checking its digest |
| `ngspice` | **47**, Homebrew (`/opt/homebrew/bin/ngspice`), installed Oct 5, 2026 for the `spice` skill's subcircuit checks. LTspice stays the tool for `sim/`; the skill cannot drive the CrossOver bottle. Upgrade with `brew upgrade ngspice` |

`kicad-happy` needs Python 3.10+ and has no required dependencies (stdlib
only); this machine has 3.12.7. It does **not** need KiCad at runtime — it
parses saved `.kicad_sch` / `.kicad_pcb` files directly, and supports KiCad
5 through 10.

Optional, not set up: `DIGIKEY_CLIENT_ID` / `DIGIKEY_CLIENT_SECRET`,
`MOUSER_SEARCH_API_KEY`, `ELEMENT14_API_KEY`. Without them the sourcing skills
fall back to web search. LCSC needs no key, which is the one that matters if
the board goes to JLCPCB.

### What the review skills do and do not settle

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
| 6 | `KELVIN_HI` / `KELVIN_LO` → ÷4 divider → buffer | The four-wire measurement is what makes `R_iso`'s uncorrected 1.1 V drop harmless (§3.1, §3.4). If this pair is compromised the stability fix is too | Matched pair from the DUT socket terminals. Sensed **at the socket**, not at the nearest convenient copper. Past the divider, `VDIV` is a 75 kΩ node (300k ‖ 100k): keep it short and away from `BD139_C` |
| 7 | `BD139_C` and every op-amp `V+` | Decoupling placement, §14.5(3) | 100 nF within **~5 mm of the pin, measured along the trace**, cap body to pin. Bulk 10 µF on the rail. The collector net is also the 0.89 W node — and the TO-126 **tab is the collector, live at +15 V** (§8): clearance to every adjacent net, no contact with a grounded enclosure |
| 8 | `GND_STAR` and all sense returns | §14.5(4) | One reference point. A shared milliohm at 107 mA is millivolts into a sense path whose range-3 full scale is 100 mV |
| 9 | `DAC_SWEEP` (PA6), `DAC_GATE` (PA4), `ADC1_I`, `ADC2_V` | Low-level analog into 12-bit converters; §3.5 wants the 10 nF at each ADC pin and BAT54S clamps to rails | Keep clear of `BD139_C` and `BD139_E`. 10 nF and clamps at the pin. **PA5 is not usable as a DAC output — it drives LD2** (§3.5) |

Nets 1, 2 and 5 are the three that cannot be fixed by rework if they are
wrong. Route those first, while there is still freedom in the floorplan.

### Everything else

Digital, USB, the Nucleo header fan-out, LEDs, jumper selects: autoroute is
fine, then check it does not cut across nets 1–6 or break the star ground.
Done that way on Oct 6, 2026, with nets 1–9 locked first (`DECISIONS.md`
P-6, P-7). `review/pass2/p2_split_crossings.png` shows every net that
crosses the ground split, and its distance to the star tie.

---

## Fab outputs

`python3 hardware/tools/export_fab.py` regenerates everything in `fab/`
from the saved schematic and board. Re-run it after any change, after DRC.
It refuses to write the JLCPCB files if the BOM and CPL disagree.

| File | What it is for |
|---|---|
| `fab/jlc/curve-tracer_gerbers.zip` | The quote page upload: Gerbers (Protel names) and Excellon PTH/NPTH, in JLCPCB's documented KiCad settings |
| `fab/jlc/curve-tracer_bom_jlc.csv` | PCBA BOM upload. 25 PCBA lines with LCSC numbers. Seven more are marked **HAND-SOLDER** and have no LCSC number, so they cannot be matched |
| `fab/jlc/curve-tracer_cpl_jlc.csv` | PCBA placement upload: 38 rows, PCBA parts only, rotations corrected per `DECISIONS.md` P-10 |
| `fab/curve-tracer_bom.csv` | Engineering BOM: every line including DNP. The LCSC hand-solder order is its `hand` lines |
| `fab/gerbers/` | The same Gerbers unzipped, for review |

---

## Before the order goes out

**The order is event-driven: it goes out as soon as this list is clear and
Phase 1 has passed — target Oct 13, no later than Oct 20** (§9). Nothing on
the board improves by waiting, so do not hold a DRC-clean layout for a
calendar date. The Oct 26 abandon-the-PCB checkpoint is in §9.

**Order with express shipping** (§14.3a). The slack is all in front of the
order; there is none between arrival and the Nov 16 freeze.

- [ ] Every node named in §3 has a test point (§14.4 enumerates them)
- [ ] Alternate-value footprints placed: `R_iso`, `R_B`, `R_sense` (§14.4)
- [ ] `C_f` footprint placed beside `R_f`, **unstuffed** — value is fitted
      after measuring on the real board (§14.4)
- [ ] All six §14.5 constraints checked by measuring the layout
- [ ] Headers, not solder, for supply / DUT socket / shunt select / Kelvin
      leads; **Nucleo on headers**
- [ ] TO-126 footprint (not TO-220), heatsink keep-out drawn, tab clearance
      for a net at +15 V
- [ ] BD139 footprint checked against the **physical** E-C-B lead order, not
      ST's pin numbers, which run the other way (`DECISIONS.md` L-1)
- [ ] Two 2.54 mm jumper shunts for J3/J4 on the parts order; they are not
      on the PCBA BOM
- [ ] Hand-solder parts ordered from LCSC alongside the PCBA: every BOM line
      with `Assembly` = `hand` (J1–J8, Q1) plus 26 Keystone 5001 test loops,
      which LCSC does not stock (TP6 is a bare pad; `DECISIONS.md`, Assembly)
- [ ] In JLCPCB's BOM step, only the 25 `PCBA` lines match parts. The seven
      HAND-SOLDER lines show as unmatched / not placed: no LCSC number, no
      CPL row
- [ ] `tools/check_topology.py --self-test` passes on the frozen schematic
- [ ] BAT54S ADC clamps and gate Zener placed; output-clamp footprint at the
      DUT socket for §3.6's +48% short-recovery overshoot, unstuffed is fine
- [ ] All three shunts populated — **1 Ω, 100 Ω, 10 kΩ** — plus §3.3's 3-pin
      selection header. Only range 1 is validated by Nov 16, but ranges 2–3
      must not need a board revision (§14.2)
- [ ] ERC and DRC clean; `kicad-happy` review pass on schematic and layout
- [ ] BOM and CPL checked against §8 — including that `R_f` is **23.2 kΩ**
      (E96; 23.3 kΩ does not exist and has never been orderable)
- [ ] Phase 1 breadboard stability result is in `docs/characterization.md`,
      and it is a **GO** — taken on a ≥8 MHz DIP-8 part, with the substitute
      and its rails recorded (§14.3)
- [ ] **Express shipping selected** on the fab order
- [ ] Footprint orientation, below

### Footprint orientation: what ERC and DRC cannot see

ERC checks pins against symbols, and DRC checks copper against copper.
Neither knows which way round the real part sits on its footprint. L-2, the
mirrored Nucleo sockets, passed both. For each part, check the one thing
listed on `review/pass2/p2_top.png` (crops: `p2_orientation.png`).
Re-render first if the board has changed. x runs right and y runs down,
from the top-left corner.

- [ ] **J7/J8 Nucleo sockets** (L-2). Each socket body covers both pad
      columns; the first render had it one column off. Pin 1 (square pad)
      is the top-left pad of each socket, with pin 2 to its right. That is
      CN7's outer column and CN10's inner column, per UM1724
- [ ] **Q1 BD139** (L-1). The body outline sits on the −y side of its pad
      row, toward the shaded heatsink keep-out. That face is the metal tab,
      at +15 V. Pads left to right are E (square), C, B. Seen from the marked
      face, i.e. from the board's bottom edge, the real leads read E-C-B
      left to right, so the part goes in printing toward the bottom edge
- [ ] **Q2 MMBT3904 (SOT-23).** Pin 3 (collector, BD139_B) is the lone pad on
      +x. Pin 1 (base, BD139_E) is top-left and pin 2 (emitter, FB_SENSE)
      bottom-left
- [ ] **D4/D5 BAT54S (SOT-23).** Pin 3, the common node on the ADC line, is
      the lone pad on +x. Pin 1 (GND) is top-left and pin 2 (+3V3)
      bottom-left. Turned 180°, the ADC pin is wired to a rail
- [ ] **D2 BZT52C12 Zener (SOD-123).** The cathode band is at −x, toward J6
      on DUT_G, and the anode goes to GNDPWR. Reversed, it clamps every gate
      drive at ~0.7 V
- [ ] **D1 1N4148W (SOD-123).** The band is at +x, on Q1's base (BD139_B),
      and the anode is on BD139_E
- [ ] **Q3 HL2303 (SOT-23), above J1.** Pin 3 (drain, VIN) is the lone pad
      on −x, toward TP28 and J1's centre pin. Pin 1 (gate) is bottom-right
      and pin 2 (source, +15V) top-right. With drain and source swapped
      the board still powers up and is not protected, so power-on cannot
      show this one
- [ ] **D6 BZT52C12 (SOD-123), beside Q3.** The band is at −y, on the
      +15V source trace; the anode goes to Q3's gate
- [ ] **C5 10 µF electrolytic.** "+" (pad 1, +15 V) is at −x; the can's dark
      stripe is at +x (GNDPWR)
- [ ] **U1–U3 OPA2197 (SOIC-8).** The pin-1 dot is top-left on all three
- [ ] **J1, J6.** The barrel-jack opening and the terminal block's wire
      entries face the left board edge

**Then again in JLCPCB's placement preview**, for the PCBA parts in that
list: C5, D1, D2, D4, D5, D6, Q2, Q3, U1–U3. The CPL rotations are community data
(`DECISIONS.md` P-10), not JLCPCB's. A rotation that is wrong there is the
PCBA version of L-2: every file checks out and the board does not. Fix any
rotation in the preview, then copy the fix into `CORRECTIONS` in
`tools/export_fab.py`.

---

## H4 bring-up measurements

What the board has to be measured for before its numbers are trusted. The
H4 *gate* is blueprint §9; this is the list of measurements behind it, each
traced to the `DECISIONS.md` row that asked for it. Log results in
`docs/characterization.md`.

**Do not run a short test without the TO-126 heatsink fitted on Q1.** That
covers every held short below: limiter trip, op-amp current in a held short,
short recovery. In a held short Q1 dissipates 0.89 W. Bare, that is 129 °C
at 40 °C ambient against a 150 °C limit: 21 °C of hand-calculated margin, on
the part those tests stress on purpose (`DECISIONS.md` P-8). The silkscreen
where the heatsink goes says the same.

- [ ] **J2 polarity by meter before first power-up.** With the bench supply
      set and its output off, meter its leads at J2: + on the pad marked
      "+15V", − on "GND". J2 has no reverse-polarity protection
      (`DECISIONS.md` P-14)
- [ ] **First power-up through J2, not J1**, bench supply at 15 V with the
      current limit at **100 mA**. Expect ~8 mA idle. Raise the limit above
      ~120 mA before any held-short test below: a held short draws ~107 mA
      plus idle, and a 100 mA limit would mask it
- [ ] Rails and star ground: +15 V at TP7, +3V3 at TP8, 0 V between TP9
      (GND_STAR) and TP27 (GNDPWR) with no load
- [ ] **ADC zero offsets**, both channels: ADC1 at zero DUT current and ADC2
      at V_DS = 0. The 1 kΩ isolation resistors turn BAT54S leakage into up
      to 2 mV (8 mV at the DUT on ADC2, §3.5). Record them as calibration,
      then re-check at full scale, since the leakage moves with signal level
      and temperature
- [ ] **+3V3 with a clamp conducting**: unplug the Kelvin leads so U3B rails,
      and read TP8. Up to ~11 mA flows in through the BAT54S; the rail must
      stay in spec (`DECISIONS.md` F-2)
- [ ] **R_PTC**: the TP5 → TP17 drop at a known current. Set `CT_R_PTC_OHM`
      in `firmware/core/ct_config.h`; re-measure after any trip
- [ ] Zener knee: TP16 against TP18 at full-scale gate code; any difference is
      D2 current × 1 kΩ (`DECISIONS.md` D2)
- [ ] **Q3 drop**: TP28 (VIN) to TP7 (+15V) at a known supply current.
      Datasheet bound ≤ 28.5 mV at 150 mA (`DECISIONS.md` P-11)
- [ ] **Reverse polarity at J1**: bench supply reversed onto J1, current
      limit ~20 mA. TP7 must stay at 0 V and the supply should draw ~0 mA.
      J2 is not protected; never reverse it
- [ ] **Q1 heatsink fitted and verified, before any short test.** This is a
      check on the board, not a BOM line:
      - The heatsink sits flat on the TO-126 tab, with an insulating pad if
        it can touch anything grounded. The tab is +15 V.
      - Meter: heatsink to GNDPWR reads open.
      - In the first held short, log Q1's case temperature after a minute.
        Expect about 45 °C at 25 °C ambient: 0.89 W into ~21 °C/W, P-8.
      - Above 70 °C the heatsink is not doing its job: stop. That threshold
        is a judgement, between the ~45 °C expected and the ~105 °C case
        temperature of a bare part.
- [ ] Limiter trip at ~75.2 mA, cold and again warm (§3.1)
- [ ] §3.1 stability gate: ≤ 25% overshoot into 100 nF and 1% within 5 µs,
      with `C_f` fitted *and swept* both ways
- [ ] Op-amp current in a held short, from the drop across R_B: out of its
      own limit (§3.1)
- [ ] Short-recovery overshoot at the DUT socket against sim 10's +48% (§3.6)
