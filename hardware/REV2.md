# Rev 2 scope

**Status: scoped, not designed, not ordered.** This file says what a second
board revision changes and what it would cost. It has no CAD changes and no
fab files. Whether to order is Daniel's decision. The rev 1 record is
`DECISIONS.md` (R2-1 to R2-3 are the items rev 1 already carried forward)
and `ORDER.md`.

Each item says what a lab user hit, or would hit, on rev 1, and what
changes.

## 1. C1 populated by JLCPCB: 3.3 pF C0G ±0.1 pF

**What rev 1 does.** The footprint is empty (R2-2). Board 2 oscillates at
open load at 0.79–1.15 MHz (measured, 2026-11-03). Until it's fixed, every
low-current device needs a resistor across D–S, and the host has to
subtract that current (MVP card §D).

**Rev 2.** C1 = **3.3 pF, C0G, ±0.1 pF, 0603**, FH 0603CG3R3B500NT, LCSC
**C2836771**. That is the part rev 1's LCSC order used. JLCPCB lists it as
an extended SMD part, in stock (3,013 on 2026-11-03), minimum buy 20.
Murata GRM1885C1H3R3BA01D (C162224, 802 in stock) is the same value and
tolerance from a second maker.

**Where 3.3 pF comes from (simulation).** Sim 14 uses TI's OPA2197 model.
It predicts C_f = 3.4–3.9 pF from the model's own input capacitance plus
≤ 1 pF of board. CONTINGENCY §3 rounds down to the stocked value, because
over-compensating is the worse failure (Phase 0's C_comp mechanism). At 6 V
open load, 3.3 pF cuts the ring from 0.83× to 0.40× per half-cycle.

**The risk is the model, not the part's tolerance.** ±0.1 pF is 3% of the
value. What sim 14 rests on is wider than that:

- **Tolerance: not a risk (simulation, sims 14c and 14d).** At 6 V open
  load, the half-cycle ratio goes 0.80, 0.50, 0.40 for C1 = 0, 2.2 and
  3.3 pF. At 4.7 pF there is no ring at all: one 0.17 V dip, settled in
  0.5 µs. The slew-limited edge is the same in every case. So the model
  shows no *too much C_f* failure anywhere up to 4.7 pF, and ±0.1 pF sits
  well inside a bracket that is damped at both ends. At 0.1 and 0.3 V,
  3.3 pF is quiet within 40 µs. With C1 empty, 0.1 V rings and decays
  (8.7 mV p-p at 40–60 µs, 0.23 mV by 60–80 µs).
- **3.3 or 4.7 pF.** CONTINGENCY §3 rounds down, because the analysis
  (blueprint §3.1) puts too much C_f at the Phase 0 failure. The model
  doesn't show that failure at 4.7 pF and damps it better. 3.3 pF follows
  the documented rule, so it stays the choice here. 4.7 pF (C1 would be
  FH 0603CG4R7…, not yet looked up) is the alternative if the model is
  trusted over the analysis. This is a judgement call for Daniel, and
  nothing on rev 1 can measure it.

- **What the input capacitance is.** TI's datasheet doesn't say whether
  its 6.4 pF common-mode figure is per input. The model treats it as per
  input. If it's for both inputs, C_in is ~5 pF and the ideal C_f is
  ~2.2 pF (CONTINGENCY §2A). 3.3 pF is then ~1.1 pF over.
- **One model.** The only evidence is TI's model, and on board 2 it was
  somewhat optimistic: its ring decayed where the bench sustained.

**How rev 2 checks it.** Run MVP card §D step 13, but with no R_p. Then run
Block 1 steps 8–9 (L1, open). If it still oscillates, the R_p workaround
and its host subtraction stay available unchanged.

## 2. Reverse-polarity protection on J2

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
- `check_topology.py` asserts the power entry, so its J2 check changes with
  the net.

## 3. G/D/S on the silkscreen at J6

**What rev 1 does.** J6 has no pin labels. On the bench the pins were
found with ▲ and a continuity beep to TP19 (MVP card step 3). G is at ▲, D
is in the middle, S is the other end.

**Rev 2.** Put "G", "D" and "S" on F.Silkscreen beside each J6 position,
readable with the wire openings facing you. **No cost.**

## 4. J6 turned to face the board edge

**What rev 1 does.** J6's wire openings face into the board, toward
D3/TP19, so the device sits over the board and its leads cross the
terminal block.

**Rev 2.** Rotate J6 180° so the openings face the nearest board edge.
- DUT_G, DUT_D and the S return (GNDPWR) re-route to the new pad order.
- **DUT_D is hand-routed and carries the Kelvin HI tap**, so the re-route
  is a hand job, followed by DRC, ERC and `check_topology.py`.
- The DUT_D trace length into D3 changes by a few mm. That doesn't matter
  at 1 MHz.

**No cost.**

## 5. Other bring-up issues a lab user hit on rev 1

| Issue on rev 1 | Rev 2 change | Cost |
|---|---|---|
| **J2 is a 2.54 mm header.** An alligator clip on it can bridge +15 V to ground. The card has you push female jumper wires on first (MVP step 6) | J2 becomes a 2-way **5.0 mm screw terminal**, KF301-5.0-2P, LCSC **C474881**: the same family as J6, JLCPCB-assembled THT, 49,221 in stock. Wired to VIN (item 2) | +$0.61 for 5 boards, −$0.09 off the J2/J5 header line. A THT line carries no loading fee |
| **No safe scope ground near TP3** (R2-1). The nearest ground pad is 1.6 mm from +15 V, so the scope uses a clip lead to TP9 or TP27, 50 mm away | A bare GNDPWR pad within a few mm of TP3, nothing at another potential within reach of a spring-ground tip | none (copper) |
| **The sweep DAC needs a jumper on the Nucleo** (J7/J8, R2-3). PA5 to PA6 is shunted on the Nucleo and checked with three continuity tests (MVP steps 1a–1c) | Route DAC_SWEEP to **CN10-11 (PA5)** on the board and leave CN10-13 (PA6) unconnected, so the Nucleo needs no shunt. The firmware already drives PA5. **The LED load stays**: LD2 still loads PA5 above ~6.6 V at the node, unless SB21 comes off the Nucleo or the MCU board changes (R2-3, a decision of its own) | none (copper) |
| **Q1's tab sits at +15 V with no heatsink** (the MVP card's top rule) | "TAB +15 V" on the silkscreen by Q1 | none |
| **Nucleo orientation.** The card explains which end of CN7/CN10 is pin 1 (MVP step 2) | "USB ▲" on the silkscreen at the J7/J8 end where the Nucleo's USB connector sits | none |

**Waiting on a measurement, not in scope yet.** The sweep DAC's floor is
guaranteed only to 0.66 V at the node (blueprint §3.5). If session 2 (MVP
§D steps 13–14) shows a real floor, R23, the DNP pull-down footprint
already on DAC_SWEEP, is the first thing to try. Its value would come from
that measurement.

**Considered, not proposed.**
- **A lower-capacitance TVS for D3.** D3's ~1 nF is half the open-load
  pole, but C1 is the fix asked for, and D3's job (blueprint §3.6) doesn't
  change.
- **Kelvin sense routed to J6 on the board.** That would drop the J5 wires,
  but the board would then sense at the terminal, not at the device.

## BOM delta

| Ref | Rev 1 | Rev 2 | LCSC | JLCPCB tier | Effect on 5 boards |
|---|---|---|---|---|---|
| C1 | DNP | 3.3 pF C0G ±0.1 pF 0603, FH 0603CG3R3B500NT | C2836771 | extended SMD | +$3.09 loading fee, +$0.26 parts (20, JLCPCB's minimum), +$0.02 joints |
| J2 | PZ254V-11-02P header (line shared with J5), on +15V | KF301-5.0-2P screw terminal, on VIN | C474881 | extended THT | +$0.61 parts; J2/J5 line −$0.09 |
| — | — | ground pad by TP3; silkscreen G/D/S, TAB +15 V, USB ▲ | — | — | $0 |

Net changes, no parts: J2 to VIN, J6 rotated, DAC_SWEEP to CN10-11.

## Cost, 5 assembled boards

Rev 1's JLCPCB quote (`ORDER.md`, 2026-10-11) plus the delta above. Duty
and tax are scaled at rev 1's rates (35.0% and 7.0% of merchandise), and
shipping is taken as rev 1's DHL charge. **This is not a new quote.** Fees,
part prices and the tariff may have moved since 2026-10-11.

| | Rev 1, paid | Rev 2, estimate |
|---|---|---|
| Merchandise | $137.98 | $141.86 |
| Shipping, DHL Express DDP | $31.59 | $31.59 |
| Duty + disbursement fee | $48.30 + $7.52 | $49.66 + $7.52 |
| Sales tax | $9.66 | $9.93 |
| **Total** | **$235.05** | **~$240.56** ($48.11 per board) |

## Lead time, from rev 1's dates

| Rev 1 step | Date | Days |
|---|---|---|
| Ordered and paid | Sun 2026-10-11 | 0 |
| Parts placement confirmed (JLCPCB allows 72 h) | 2026-10-13 | 2 |
| Packed for DHL | by 2026-10-17 | 6 |
| DHL's delivery estimate | Wed 2026-10-21 | 10 |

So it is **about 10 days from order to door**, plus the CAD work before an
order can go in. That work is the J6 re-route by hand, the J2 and DAC_SWEEP
net changes, the pad, the silkscreen, then DRC/ERC, `check_topology.py`,
the fab export and the placement preview: roughly one to two working days.
The repo doesn't record the day rev 1's boards actually arrived.

**Against the plan.** Bench work stops on 2026-11-15. With the CAD done by
2026-11-05 and the order placed that day, the boards would arrive around
**2026-11-15**, the last bench day. Any later and they arrive after it.
So rev 2 can't be measured inside the current plan. It is worth ordering
only if bench time after November 15 is available, or as a design that is
specified here and left unordered.
