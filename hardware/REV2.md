# Rev 2 scope

**Status: scoped, not designed, not ordered.** This file says what a second
board revision changes and what it would cost. It has no CAD changes and no
fab files. **Daniel approves the item list before any CAD starts**, and
decides separately whether to order. The rev 1 record is `DECISIONS.md`
(R2-1 to R2-4 are the items rev 1 already carried forward) and `ORDER.md`.

The items are split in two:
- **Essential (E1–E4).** These fix what a lab user hits on rev 1: the
  oscillation, finding the pins, the device's position, and a reversed lead.
- **Optional (O1–O4).** Each one stands alone, and any of them can be dropped
  without touching the rest.

Every item gives its risk, meaning what could go wrong with the change
itself, and how rev 2's bring-up would show it.

| # | Item | Parts cost, 5 boards | CAD | Risk |
|---|---|---|---|---|
| E1 | C1 = 4.7 pF, fitted by JLCPCB | +$3.30 | BOM field | **Medium**: the value rests on one vendor model |
| E2 | G/D/S on the silkscreen at J6 | $0 | silkscreen | Low |
| E3 | J6 turned to face the board edge | $0 | hand re-route of DUT_D (Kelvin HI) | **Medium**: hand-routed analog net |
| E4 | J2 through Q3 (reverse-polarity protection) | $0 | one net change | Low |
| O1 | J2 becomes a 5 mm screw terminal | +$0.52 | footprint swap | Low |
| O2 | A ground pad by TP3 | $0 | copper | Low |
| O3 | DAC_SWEEP routed to PA5, no Nucleo jumper | $0 | re-route | Low to medium |
| O4 | "TAB +15 V" and "USB ▲" on the silkscreen | $0 | silkscreen | None |

## Essential

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

**Risk: low.** The risk is a label on the wrong pin, made at the same
time as E3's rotation. Check it against the pad numbers in the footprint
(pin 1 G, 2 D, 3 GNDPWR) and in JLCPCB's 3D view, which is the view that
caught Q1's reversed tab on rev 1. Silkscreen too close to pads draws a
DFM warning; it's moved, not ignored.

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

## Optional

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

## BOM delta

| Ref | Rev 1 | Rev 2 | LCSC | JLCPCB tier | Effect on 5 boards |
|---|---|---|---|---|---|
| C1 (E1) | DNP | 4.7 pF C0G ±0.1 pF 0603, FH 0603CG4R7B500NT | C313086 | extended SMD | +$3.09 loading fee, +$0.19 parts (20, JLCPCB's minimum), +$0.02 joints |
| J2 (O1) | PZ254V-11-02P header (line shared with J5), on +15V | KF301-5.0-2P screw terminal, on VIN | C474881 | extended THT | +$0.61 parts; J2/J5 line −$0.09 |
| — | — | ground pad by TP3 (O2); silkscreen G/D/S (E2), TAB +15 V, USB ▲ (O4) | — | — | $0 |

Net changes, no parts: J2 to VIN (E4), J6 rotated (E3), DAC_SWEEP to
CN10-11 (O3).

## Cost, 5 assembled boards

Rev 1's JLCPCB quote (`ORDER.md`, 2026-10-11) plus the delta above. Duty
and tax are scaled at rev 1's rates (35.0% and 7.0% of merchandise), and
shipping is taken as rev 1's DHL charge. **This is not a new quote.** Fees,
part prices and the tariff may have moved since 2026-10-11.

| | Rev 1, paid | Rev 2, essential only | Rev 2, all items |
|---|---|---|---|
| Merchandise | $137.98 | $141.28 | $141.80 |
| Shipping, DHL Express DDP | $31.59 | $31.59 | $31.59 |
| Duty + disbursement fee | $48.30 + $7.52 | $49.45 + $7.52 | $49.64 + $7.52 |
| Sales tax | $9.66 | $9.89 | $9.93 |
| **Total** | **$235.05** | **~$239.73** ($47.95 per board) | **~$240.47** ($48.09 per board) |

## Lead time, from rev 1's dates

| Rev 1 step | Date | Days |
|---|---|---|
| Ordered and paid | Sun 2026-10-11 | 0 |
| Parts placement confirmed (JLCPCB allows 72 h) | 2026-10-13 | 2 |
| Packed for DHL | by 2026-10-17 | 6 |
| DHL's delivery estimate | Wed 2026-10-21 | 10 |

So it is **about 10 days from order to door**, plus the CAD work before an
order can go in: roughly one to two working days for every item. E3 is
most of it: the J6 re-route by hand. The rest is the J2 net change
(and O3's), the silkscreen, then DRC/ERC, `check_topology.py`, the fab
export and the placement preview. With only E1, E2 and E4, CAD is about
half a day. The repo doesn't record the day rev 1's boards actually
arrived.

**Against the plan.** Bench work stops on 2026-11-15. With the CAD done by
2026-11-05 and the order placed that day, the boards would arrive around
**2026-11-15**, the last bench day. Any later and they arrive after it.
So rev 2 can't be measured inside the current plan. It is worth ordering
only if bench time after November 15 is available, or as a design that is
specified here and left unordered.
