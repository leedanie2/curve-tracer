# Rev 2

**Status: approved and laid out, not ordered** (2026-11-03). Daniel
approved E1, E2, E4, O1 and O4, and deferred E3, O2 and O3 to a later
revision. The CAD is done on the `rev2` branch, and the JLCPCB fab files
are in `fab/`. **Daniel places the order himself.** The rev 1 record is
`DECISIONS.md` (R2-1 to R2-4 are the items rev 1 carried forward) and
`ORDER.md`.

| # | Item | Status | Parts cost, 5 boards | Risk |
|---|---|---|---|---|
| E1 | C1 = 4.7 pF, fitted by JLCPCB | **Done** | +$3.30 | **Medium**: the value rests on one vendor model |
| E2 | G/D/S on the silkscreen at J6 | **Done** | $0 | Low |
| E3 | J6 turned to face the board edge | Deferred | $0 | **Medium**: hand-routed analog net |
| E4 | J2 through Q3 (reverse-polarity protection) | **Done** | $0 | Low |
| O1 | J2 becomes a 5 mm screw terminal | **Done** | +$0.52 | Low |
| O2 | A ground pad by TP3 | Deferred | $0 | Low |
| O3 | DAC_SWEEP routed to PA5, no Nucleo jumper | Deferred | $0 | Low to medium |
| O4 | **Q1's tab sits at +15 V with no heatsink** (the MVP card's top rule). **Nucleo orientation:** the card explains which end of CN7/CN10 is pin 1 (MVP step 2) | "▲ NUCLEO USB END ▲" between J7 and J8, at the end where the Nucleo's USB connector sits. **"TAB = +15 V" needs nothing**: rev 1 already has it, in the heatsink keep-out ("FIT Q1 HEATSINK / BEFORE SHORT TEST / TAB = +15 V"). This file listed it by mistake | none | **None** |

## Deferred, and why

Daniel deferred these three (2026-11-03). What they have in common: each
changes copper on or beside a hand-routed analog net, for a convenience a
lab user can live without. Leaving them out keeps rev 2's analog routing
identical to rev 1's. The one change inside the loop is C1, so rev 2's
bench results compare directly with rev 1's.
- **E3, J6 turned to the edge.** This re-routes DUT_D, which carries the
  Kelvin HI tap (routing policy net 6), by hand. DRC and
  `check_topology.py` prove connectivity, not where the tap sits. E2's
  labels fix the part of the problem that cost bench time: finding the pins.
- **O2, ground pad by TP3.** It puts new copper next to the loop's output
  and near the IN− no-pour area. The scope's clip lead to TP9 works, and
  was used for both sessions. With C1 fitted there should be no oscillation
  left to probe at TP3.
- **O3, DAC_SWEEP to PA5.** This re-routes DAC_SWEEP (routing policy net
  9), which drives IN+ of the loop amplifier. It removes one jumper on the
  Nucleo, but the LED load stays (SB21 stays fitted), so it doesn't meet
  R2-3. It would also make rev 1 and rev 2 need different Nucleo setups
  (shunt or no shunt), a new way to get a dead sweep.

## Essential (E1, E2, E4 done; E3 deferred)

### E1. C1 populated by JLCPCB: 4.7 pF C0G ±0.1 pF

**What rev 1 does.** The footprint is empty (R2-2). Board 2 oscillates at
open load at 0.79–1.15 MHz (measured, 2026-11-03). Until it's fixed, every
low-current device needs a resistor across D–S, and the host has to
subtract that current (MVP card §D).

**Rev 2.** C1 = **4.7 pF, C0G, ±0.1 pF, 0603**, FH 0603CG4R7B500NT, LCSC
**C313086**: an extended SMD part, in stock (2,523 on 2026-11-03), minimum
buy 20, $0.0094 each. The ±0.1 pF comes from FH's tolerance code B. JLCPCB's
listing doesn't give the tolerance as a field. Murata GRM1885C1H4R7BA01D
(C162234) is the same value and tolerance from a second maker, but it had
0 in stock on 2026-11-03.

**Why 4.7 pF and not 3.3 pF** (DECISIONS R2-4, Daniel, 2026-11-03). The
bench is less damped than TI's model: board 2 sustained an oscillation where
sim 14 decays. And 4.7 pF shows no over-compensation in that model. The
results below are simulated, with TI's OPAx197 model:

| Case | 0 | 2.2 pF | 3.3 pF | 4.7 pF |
|---|---|---|---|---|
| 6 V open load, half-cycle ratio (sims 14, 14c) | 0.80 | 0.50 | 0.40 | no ring |
| 6 V open load, peak over final | +1.47 V | +0.76 V | +0.40 V | +0.4 mV, one 0.17 V dip |
| 6 V open load, 1% settling after the edge | 7.1 µs | 2.7 µs | 2.1 µs | 0.5 µs |
| 6 V into L1, p-p left after the settling (sims 14b, 14e) | 0.24 mV | — | 0.24 mV | 0.24 mV |
| 0.1 / 0.3 V open load, p-p at 60–80 µs (sims 14d, 14f) | 0.23 / 0.03 mV | — | 0.00 / 0.00 mV | 0.00 / 0.00 mV |

This supersedes CONTINGENCY §3's round-down rule for this case. That rule
existed because blueprint §3.1's analysis puts too much C_f at the Phase 0
C_comp failure.

**Risk: medium. The evidence is one vendor model, and it was optimistic
about rev 1.**
- **Over-compensation, per the analysis.** The ideal is C_f = 0.431 · C_in.
  With the model's 8 pF plus ≤ 1 pF of board, that is 3.4–3.9 pF, so
  4.7 pF is 0.8–1.3 pF over. If TI's 6.4 pF is for both inputs rather than
  per input (the datasheet doesn't say), the ideal is ~2.2 pF and 4.7 pF is
  ~2.5 pF over. That is near §3.1's 2.66 pF case, which the analysis puts
  at 25.4% overshoot.
- **Not enough, per the bench.** If the real loop has more excess phase
  than the model, 4.7 pF could still leave a ring at open load. It is
  still more damping than 3.3 pF would give.
- **Tolerance is not the risk.** ±0.1 pF is 2% of the value, and the
  whole 2.2–4.7 pF bracket is damped in the model.
- **What it costs if wrong.** Taking an 0603 off is a solder job (R2-2). It
  returns the board to rev 1's loop, where the R_p workaround and its host
  subtraction still apply unchanged.

**How rev 2's bring-up checks it.** MVP card §D step 13 with nothing in J6
(open load at 0.1 and 0.3 V). Block 1 steps 8–9 (L1, then open). Then H4's
step test into L1 (step 5), whose overshoot compares with sim 08's 10.3%.

### E2. G/D/S on the silkscreen at J6

**What rev 1 does.** J6 has no pin labels. On the bench the pins were found
with ▲ and a continuity beep to TP19 (MVP card step 3). G is at ▲, D is in
the middle, S is the other end.

**Rev 2.** Put "G", "D" and "S" on F.Silkscreen beside each J6 position,
readable with the wire openings facing you. **No cost.**

**Risk: low.** The risk is a label on the wrong pin. **Done:** the
labels sit at x 53.2, between J6 and D3, at each pad's y: G at 124.0
(pin 1, the square pad), D at 119.0 (pin 2, DUT_D), S at 114.0 (pin 3,
GNDPWR). That matches the footprint and `check_topology.py`'s J6
assertion. DRC has no silkscreen warnings. With E3 deferred, J6 keeps
rev 1's orientation, so the openings, and the labels beside them, face
into the board toward D3.

### E3. J6 turned to face the board edge

**What rev 1 does.** J6's wire openings face into the board, toward
D3/TP19, so the device sits over the board and its leads cross the
terminal block.

**Rev 2.** Rotate J6 180° so the openings face the nearest board edge.
- DUT_G, DUT_D and the S return (GNDPWR) re-route to the new pad order.
- DUT_D is hand-routed and carries the Kelvin HI tap, so the re-route
  is a hand job, followed by DRC, ERC and `check_topology.py`.
- The DUT_D trace length into D3 changes by a few mm. That doesn't matter
  at 1 MHz.

**No cost.**

**Risk: medium.**
- **The Kelvin tap.** DRC and `check_topology.py` prove connectivity, not
  where on DUT_D the Kelvin HI tap sits. A tap moved upstream of the
  terminal would put trace drop into the voltage reading. Review it by eye
  against rev 1's routing.
- **Mechanical.** The terminal sits near two edges (J6 at x 47, y 124; the
  board runs x 40–175, y 40–132). The rotated body has to keep JLCPCB's
  edge clearance. The wire entry may overhang the edge, which is the point.
- **The check after the fact.** MVP card step 15's accuracy rows, compared
  with rev 1's, show any new voltage error.

### E4. Reverse-polarity protection on J2

**What rev 1 does.** J1, the barrel jack, feeds +15V through Q3, a
high-side P-FET (P-11). J2, the header the bench supply actually clips to,
connects straight to +15V. A reversed bench lead reaches the whole board,
with only the supply's current limit in the way (the MVP card warns of
this).

**Rev 2.** Move J2 pin 1 from net +15V to net VIN, so both inputs go
through Q3. **No new parts.**
- Q3, the HL2303, is rated −30 V V_DS and ±20 V V_GS, with ≤ 190 mΩ on.
  At the board's worst-case ~110 mA (limiter into a short, sim 11) it
  drops ≤ 21 mV.
- `check_topology.py` asserts the power entry: VIN = {J1, Q3, TP28}. That
  check changes to include J2.

**Risk: low.**
- **Q3 now carries the bench current too.** At ≤ 110 mA and ≤ 190 mΩ, that
  is ≤ 2.3 mW.
- **Hot-plugging a clip lead** rings harder than plugging in a barrel jack.
  D6, the 12 V Zener from gate to source, holds Q3's V_GS inside its 20 V
  rating, as it already does for J1.
- **The header stays.** A clip can still bridge J2's pins, which is why O1
  exists.
- **The check.** A reversed lead at the supply's current limit: the board
  draws nothing and +15V reads 0 V.

## Optional (O1 and O4 done; O2 and O3 deferred)

| # | Issue on rev 1 | Rev 2 change | Cost | Risk |
|---|---|---|---|---|
| O1 | **J2 is a 2.54 mm header.** An alligator clip on it can bridge +15 V to ground. The card has you push female jumper wires on first (MVP step 6) | J2 becomes a 2-way **5.0 mm screw terminal**, KF301-5.0-2P, LCSC **C474881**: the same family as J6, JLCPCB-assembled THT, 49,221 in stock. Wired to VIN (E4) | +$0.61 for 5 boards, −$0.09 off the J2/J5 header line (+$0.52). A THT line carries no loading fee | **Low.** It's a bigger footprint, so the space around J2 has to fit it. The polarity has to be marked: "+" by pin 1 on the silkscreen |
| O2 | **No safe scope ground near TP3** (R2-1). The nearest ground pad is 1.6 mm from +15 V, so the scope uses a clip lead to TP9 or TP27, 50 mm away | A bare GNDPWR pad within a few mm of TP3, nothing at another potential within reach of a spring-ground tip | none (copper) | **Low.** The pad has to stay out of the IN− no-pour area (§14.5(2)), where copper adds stray C_in, which is the quantity C1 is sized against |
| O3 | **The sweep DAC needs a jumper on the Nucleo** (J7/J8, R2-3). PA5 to PA6 is shunted on the Nucleo and checked with three continuity tests (MVP steps 1a–1c) | Route DAC_SWEEP to **CN10-11 (PA5)** on the board and leave CN10-13 (PA6) unconnected, so the Nucleo needs no shunt. The firmware already drives PA5 | none (copper) | **Low to medium.** DAC_SWEEP drives IN+ of the loop amplifier, so the new route must keep away from noisy nets. A Nucleo still shunted from rev 1 is harmless: PA6 is held analog. **It does not meet R2-3's rev 2 requirement.** SB21 stays fitted (Daniel, 2026-11-03), so the LED still loads PA5 above ~6.6 V at the node |
| O4 | **Q1's tab sits at +15 V with no heatsink** (the MVP card's top rule). **Nucleo orientation:** the card explains which end of CN7/CN10 is pin 1 (MVP step 2) | "TAB +15 V" on the silkscreen by Q1. "USB ▲" at the J7/J8 end where the Nucleo's USB connector sits | none | **None** beyond silkscreen clearance |

## Not in scope

**Waiting on a measurement.** The sweep DAC's floor is guaranteed only to
0.66 V at the node (blueprint §3.5). If session 2 (MVP §D step 13d) shows a
real floor, R23 is the first thing to try. It's the DNP pull-down footprint
already on DAC_SWEEP, and its value would come from that measurement.

**The LED on PA5 (R2-3).** SB21 stays fitted (Daniel, 2026-11-03: no
soldering). Rev 2 keeps the F303RE and PA5, so R2-3's rev 2 requirement (a
sweep DAC pin with no LED on it) is not met. Above ~6.6 V at the node, the
LED load stays.

**Considered, not proposed.**
- **A lower-capacitance TVS for D3.** D3's ~1 nF is half the open-load
  pole, but C1 is the fix asked for, and D3's job (blueprint §3.6) doesn't
  change.
- **Kelvin sense routed to J6 on the board.** That would drop the J5 wires,
  but the board would then sense at the terminal, not at the device.

## BOM delta (as built)

| Ref | Rev 1 | Rev 2 | LCSC | JLCPCB tier | Effect on 5 boards |
|---|---|---|---|---|---|
| C1 (E1) | DNP | 4.7 pF C0G ±0.1 pF 0603, FH 0603CG4R7B500NT | C313086 | extended SMD | +$3.09 loading fee, +$0.19 parts (20, JLCPCB's minimum), +$0.02 joints |
| J2 (O1) | PZ254V-11-02P header (line shared with J5), on +15V | KF301-5.0-2P screw terminal, on VIN | C474881 | extended THT, hand-soldered by JLCPCB | +$0.61 parts (6: 5 plus 1 attrition, $0.1019); J2/J5 line −$0.09 |
| — | — | silkscreen: G/D/S (E2), ▲ NUCLEO USB END ▲ (O4), +15V / GND moved beside J2 | — | — | $0 |

Net change, no parts: J2 pin 1 from +15V to VIN (E4). Two copper changes:
- J2's rev 1 tie to +15V comes out. C5 and TP7 stay joined, as before.
- A 0.6 mm VIN track on F.Cu, 35.2 mm long, runs from J2 pin 1 up the
  left edge, between J1's pads 2 and 3, to J1 pin 1.

## Parts, confirmed 2026-11-03

**C1, C313086, on LCSC's own page**
(`lcsc.com/product-detail/C313086.html`). The page's text, verbatim:
- title: "0603CG4R7B500NT | Ceramic Capacitors | FH | LCSC"
- Key Attributes: "CAP CER 4.7pF 50V C0G 0603"
- specifications: Capacitance "4.7pF"; Temperature Coefficient "C0G";
  Voltage Rating "50V"; Packaging "0603"; Manufacturer "FH"
- summary: "Features 4.7pF and C0G. From $0.0046, 2,500 in stock."

The page states no tolerance. ±0.1 pF comes from the "B" in FH's part
number, per FH's code table (`README.md`, contingency parts). The PDF the
page links to wasn't downloadable without a browser.

JLCPCB's part record (cart.jlcpcb.com, `getComponentDetail`):
- C313086: extended, SMT, 2,523 in stock, minimum 20, attrition 10,
  $0.0094.
- C474881 (KF301-5.0-2P): extended, **THT, manualWeld** (JLCPCB solders it
  by hand), status yes, 49,355 in stock, minimum 2, attrition 1, $0.1019.
  It is now in `tools/export_fab.py`'s `THT_VERIFIED`.

## CAD, done 2026-11-03 on `rev2`

| Check | Result |
|---|---|
| ERC (`kicad-cli sch erc --severity-all`) | 0 violations |
| DRC (`--severity-all --schematic-parity`) | 0 violations, 0 unconnected, 0 parity issues. The same as rev 1. A first pass gave 38 silkscreen warnings from J2's fields, which had come out visible; now hidden |
| `check_topology.py --self-test` | 60/60 checks, 16 of 16 planted faults caught. New: J2 pin 1 on VIN and VIN = {J1, J2, Q3, TP28}; C1 4.7 pF C0G, PCBA, C313086. New faults: J2 back on +15V; C1 back to DNP |
| Semantic diff against rev 1 (footprints, pads, tracks, drawings, zones) | Only the changes above: C1, J2 and its pad 1 net, the two +15V segments out, four VIN segments in, six silkscreen texts |
| `tools/export_fab.py` | JLC BOM 35 lines (33 on rev 1), CPL 75 rows (74), BOM and CPL agree |

**Renders** (`review/rev2/`):
- `rev2_3d_before_after.png`: J2, C1, J6, rev 1 against rev 2, 3D.
- `rev2_j2_before_after.png`, `rev2_j6_before_after.png` and
  `rev2_usb_before_after.png`: copper and silkscreen.
- `rev2_3d_top.png`: the whole top.

**Choices made in the CAD:**
- **J2 at rot 270**, so the wire entry faces the left board edge. J6's rot
  90 faces into the board, so this is the same footprint turned 180°.
  Pin 1 (VIN) is on top, nearer J1.
- **G / D / S sit between J6 and D3, rotated 90°**, upright for someone
  facing J6's wire openings. "D" prints over the 1.2 mm DUT_D track
  (silkscreen on solder mask, which JLCPCB prints).
- **Rev 1's stencil already had C1's paste apertures.** The paste layer
  doesn't change.

**In JLCPCB's order flow, before paying** (README, footprint orientation;
the 3D view caught Q1's reversed tab on rev 1):
- [ ] In the BOM step, all 35 lines match, with C1 = C313086 and
  J2 = C474881.
- [ ] Tilt the 3D placement preview. **J2's wire openings face the left
  board edge**, and its body sits on its two pads, not offset. J2 is the
  only new through-hole part, and the terminal family's rotation was only
  checked at rot 90 (J6) on rev 1.
- [ ] C1 sits on its two pads beside R1.
- [ ] Every rev 1 preview check still holds: Q1's tab, the SOT-23s, J7/J8.

## Cost, 5 assembled boards

Rev 1's JLCPCB quote (`ORDER.md`, 2026-10-11) plus the delta above, with
part prices re-checked on 2026-11-03. Duty and tax are scaled at rev 1's
rates (35.0% and 7.0% of merchandise), and shipping is taken as rev 1's
DHL charge. **This is an estimate, not a quote.** JLCPCB's quote page
gives the real figure once the files are uploaded. The deferred items cost
$0, so the approved set costs the same as all items would have.

| | Rev 1, paid | Rev 2, as approved |
|---|---|---|
| Merchandise | $137.98 | $141.80 |
| Shipping, DHL Express DDP | $31.59 | $31.59 |
| Duty + disbursement fee | $48.30 + $7.52 | $49.64 + $7.52 |
| Sales tax | $9.66 | $9.93 |
| **Total** | **$235.05** | **~$240.47** ($48.09 per board) |

## Lead time, from rev 1's dates

| Rev 1 step | Date | Days |
|---|---|---|
| Ordered and paid | Sun 2026-10-11 | 0 |
| Parts placement confirmed (JLCPCB allows 72 h) | 2026-10-13 | 2 |
| Packed for DHL | by 2026-10-17 | 6 |
| DHL's delivery estimate | Wed 2026-10-21 | 10 |

So it is **about 10 days from order to door**. The CAD is done, so an
order placed on 2026-11-04 arrives around **2026-11-14**, one day before
bench work stops on 2026-11-15. Any later and it arrives after. The repo
doesn't record the day rev 1's boards actually arrived.
