# Order

Everything to buy for the board and its bring-up, by vendor. Stock and
prices were read on **2026-10-11**. Prices are USD. Items marked **⚠** are
not settled by this file; they are listed under *Verify yourself* at the end.

| Vendor | What | Subtotal | Shipping | Total |
|---|---|---|---|---|
| JLCPCB | 5 boards, all 5 assembled, every part fitted by JLCPCB, test loops included | $157.33 | $31.23 ⚠ | **$188.56** |
| LCSC | Contingency parts and jumper shunts | $11.66 | not quoted ⚠ | $11.66 + shipping |
| DigiKey | TO-126 heatsink | $3.52 | not quoted ⚠ | $3.52 + shipping |

All 5 boards are assembled (Daniel, 2026-10-11): spares against a soldering
accident, a reversed supply or a blown op-amp, with no second spin.

---

## JLCPCB: fab and PCBA (one order)

**Upload** from `hardware/fab/jlc/` (regenerate with
`hardware/tools/export_fab.py`, with KiCad's Python, after any change):

| Step | File |
|---|---|
| PCB quote | `curve-tracer_gerbers.zip` |
| PCBA BOM | `curve-tracer_bom_jlc.csv`: 33 lines, one per part, all matched |
| PCBA CPL | `curve-tracer_cpl_jlc.csv`: 74 rows |

**PCB:** 2 layers, FR-4, 1.6 mm, 135 × 92 mm, qty 5, green, HASL, 2-day
build. **Express shipping** (blueprint §14.3a). **PCBA:** Economic ⚠, top
side, **5 assembled**.

**Cost, 5 assembled.** From JLCPCB's price page (2026-10-11) and live part
prices:

| Item | Basis | Cost |
|---|---|---|
| Board | 2026-10-06 quote, qty 5 (`DECISIONS.md` P-5) ⚠ | $10.00 |
| PCBA setup | Economic | $8.18 |
| Stencil | Economic | $1.53 |
| Extended-part loading fees | 25 extended × $3.07 (6 Basic and 2 Preferred have none) | $76.75 |
| SMT joints | 100 per board × 5 × $0.0016 | $0.80 |
| Through-hole labour | per order | $3.58 |
| Through-hole joints | 127 per board × 5 × $0.0164 | $10.41 |
| Parts | table below, with JLCPCB's minimums and attrition | $46.08 |
| **Subtotal** | | **$157.33** |
| Shipping | DHL, 2026-10-06 bare-board quote ⚠ | $31.23 |
| **Total** | | **$188.56** |

The through-hole parts account for $21.49 of the fees (7 parts), $3.58 +
$10.41 of the labour and $17.03 of the parts. The test loops alone are
$14.36 of that (`DECISIONS.md`, Assembly).

**Parts JLCPCB buys.** "Buy" is the quantity JLCPCB charges for: 5 boards
plus its attrition, or its minimum if that is larger. Stock is JLCPCB's.

| Refs | MPN | Maker | LCSC | Per board | Buy | Unit | Cost | Tier | Stock |
|---|---|---|---|---|---|---|---|---|---|
| C2, C6, C7, C8 | CC0603KRX7R9BB104 | YAGEO | C14663 | 4 | 30 | $0.0140 | $0.42 | basic | 56,357,634 |
| C3, C4 | 0603B103K500NT | FH | C57112 | 2 | 20 | $0.0108 | $0.22 | basic | 6,126,055 |
| C5 | RVT50V10M5X5 | jieerrui | C47023118 | 1 | 6 | $0.0360 | $0.22 | extended | 31,607 |
| D1 | 1N4148W | ST | C81598 | 1 | 15 | $0.0123 | $0.18 | basic | 4,877,572 |
| D2, D6 | BZT52C12 | MDD | C173429 | 2 | 20 | $0.0162 | $0.32 | extended | 346,157 |
| D3 | SMAJ12A | MDD | C113957 | 1 | 9 | $0.0429 | $0.39 | extended | 78,060 |
| D4, D5 | BAT54S | hongjiacheng | C7420333 | 2 | 15 | $0.0137 | $0.21 | preferred | 970,498 |
| F1 | nSMD010 | TECHFUSE | C70065 | 1 | 20 | $0.0305 | $0.61 | extended | 539,907 |
| J1 | DC-005 2.0 | BOOMELE | C16214 | 1 | 6 | $0.0562 | $0.34 | extended | 80,803 |
| J2, J5 | PZ254V-11-02P | XFCN | C492401 | 2 | 10 | $0.0186 | $0.19 | extended | 1,199,043 |
| J3, J4 | PZ254V-12-6P | XFCN | C492420 | 2 | 10 | $0.0422 | $0.42 | extended | 101,973 |
| J6 | KF301-5.0-3P | Cixi Kefa | C474882 | 1 | 6 | $0.1390 | $0.83 | extended | 8,099 |
| J7, J8 | PM254-2-19-Z-8.5 | HCTL | C2897420 | 2 | 10 | $0.4854 | $4.85 | extended | 1,948 |
| Q1 | BD139 | STMicroelectronics | C27866 | 1 | 5 | $0.2481 | $1.24 | extended | 81 |
| Q2 | MMBT3904(RANGE:100-300) | JSCJ | C20526 | 1 | 10 | $0.0116 | $0.12 | basic | 328,704 |
| Q3 | HL2303 | hongjiacheng | C7420345 | 1 | 10 | $0.0344 | $0.34 | preferred | 407,818 |
| R1, R9 | RT0603BRE0723K2L | YAGEO | C861768 | 2 | 18 | $0.0294 | $0.53 | extended | 857 |
| R2, R10 | RT0603BRD0710KL | YAGEO | C95204 | 2 | 20 | $0.0328 | $0.66 | extended | 2,341,305 |
| R3 | FRC2512F3300TS | FOJAN | C2934068 | 1 | 13 | $0.0346 | $0.45 | extended | 56,639 |
| R5 | CRCW120610R0FKEAHP | Vishay | C511457 | 1 | 9 | $0.0592 | $0.53 | extended | 7,936 |
| R7 | RC2512FK-0722RL | YAGEO | C276336 | 1 | 9 | $0.0825 | $0.74 | extended | 7,505 |
| R11 | FRC2512F1001TS | FOJAN | C2960683 | 1 | 13 | $0.0373 | $0.48 | extended | 91,384 |
| R12 | RC2512FK-071RL | YAGEO | C181756 | 1 | 7 | $0.1470 | $1.03 | extended | 9,894 |
| R13 | RT0805BRD07100RL | YAGEO | C110773 | 1 | 20 | $0.0395 | $0.79 | extended | 227,127 |
| R14 | RT0805BRD0710KL | YAGEO | C110775 | 1 | 13 | $0.0396 | $0.51 | extended | 973,430 |
| R15, R17 | RT0805BRD071KL | YAGEO | C110774 | 2 | 18 | $0.0429 | $0.77 | extended | 294,985 |
| R16, R18 | RT0805BRD0720KL | YAGEO | C469660 | 2 | 14 | $0.0926 | $1.30 | extended | 27,687 |
| R19, R22 | 0603WAF1001T5E | UNI-ROYAL | C21190 | 2 | 20 | $0.0026 | $0.05 | basic | 26,928,020 |
| R20 | RT0603BRD07300KL | YAGEO | C705762 | 1 | 20 | $0.0390 | $0.78 | extended | 120,049 |
| R21 | RT0603BRD07100KL | YAGEO | C122538 | 1 | 20 | $0.0321 | $0.64 | extended | 1,378,984 |
| R25 | 0603WAF1002T5E | UNI-ROYAL | C25804 | 1 | 20 | $0.0022 | $0.04 | basic | 33,702,315 |
| TP1–TP27 except TP6 | RH-5001 | ronghe | C5199801 | 26 | 134 | $0.0683 | $9.15 | extended | 167,868 |
| U1, U2, U3 | OPA2197IDR | Texas Instruments | C139363 | 3 | 15 | $1.1141 | $16.71 | extended | 19,993 |

The through-hole lines (J1–J8, Q1, the RH-5001 loops) are all assembly
process THT, mode `manualWeld`, in JLCPCB's part records.

**C5 substituted at the BOM step (Daniel, 2026-10-11).** C72487 (ROQANG
RVT1H100M0505) is tagged "Standard Only" on JLCPCB's BOM page and would not
be placed on an Economic order. C47023118 (jieerrui RVT50V10M5X5) replaces
it: 10 µF 50 V aluminium electrolytic, SMD 5×5.4 mm, the same RVT series
name, 2000 h at 105 °C, 17 mA at 120 Hz. It shows no "Standard Only" tag.
**JLCPCB lists no ESR for it, nor for C72487**, so the match is on series,
ripple and family, not a measured ESR. C5 damps the supply lead, and
damping comes from ESR, so ESR is the parameter that matters and it is
inferred. The quantities JLCPCB set at the BOM step differ a little from
this table's for some basic parts; the quote is the figure to trust.

**Thin stock:** Q1 BD139 has **81** at JLCPCB (128 on 2026-10-06), and R1/R9
23.2 kΩ 0.1% has 857. Both cover this order. Recheck if the order slips.

---

## LCSC: contingency parts and jumper shunts (one order)

The C_f kit, the R_iso and U1 fallbacks, D3 spares (`README.md`, Contingency
parts; `CONTINGENCY.md`), and the J3/J4 jumper shunts. Stock is LCSC's own.

| For | MPN | Maker | LCSC | Qty | Unit | Cost | Stock |
|---|---|---|---|---|---|---|---|
| C_f 1.5 pF, C0G 0603 ±0.1 pF | 0603CG1R5B500NT | FH | C507055 | 100 (min 100) | $0.0066 | $0.66 | 1,800 |
| C_f 2.2 pF | 0603CG2R2B500NT | FH | C313085 | 50 (min 50) | $0.0118 | $0.59 | 12,150 |
| C_f 2.7 pF | 0603CG2R7B500NT | FH | C2836769 | 50 (min 50) | $0.0129 | $0.65 | 2,300 |
| C_f 3.3 pF; H4 P3 fits it as C1 | 0603CG3R3B500NT | FH | C2836771 | 50 (min 50) | $0.0127 | $0.64 | 3,250 |
| C_f 3.9 pF | GRM1885C1H3R9BA01D | Murata | C162229 | 10 (min 5) | $0.1428 | $1.43 | 925 |
| C_f 4.7 pF | 0603CG4R7B500NT | FH | C313086 | 100 (min 100) | $0.0095 | $0.95 | 2,800 |
| R_iso raise, 47 Ω 1 W axial (R8) | RN1WS47ΩFT/BA1 | TyoHM | C385394 | 20 (min 20) | $0.0269 | $0.54 | 740 |
| U1 fallback | OPA2196ID | TI | C2878263 | 2 | $2.4414 | $4.88 | **21** |
| D3 spares | SMAJ12A | MDD | C113957 | 20 (min 20) | $0.0432 | $0.86 | 78,060 |
| J3/J4 jumper shunts, 2.54 mm closed top | 2.54 short-circuit cap | BOOMELE | C100114 | 50 (min 50) | $0.0094 | $0.47 | 500,950 |
| **Subtotal** | | | | | | **$11.66** | |

**The shunts are here, not at DigiKey.** LCSC stocks them, so they ship with
the contingency parts. The board needs 2 per assembled board.

**OPA2196ID has 21 left.** OPA2196IDR (C2057972, cut tape) is the same part
if the tube stock goes.

---

## DigiKey: heatsink

| For | MPN | Maker | DigiKey | Qty | Unit | Cost | Stock |
|---|---|---|---|---|---|---|---|
| Q1 heatsink, TO-126 slide-on, 26 °C/W | 577500B00000G | Boyd | HS216-ND | 2 ⚠ | $1.76 | $3.52 | 5,546 |

13.20 × 19.81 mm with 8.13 mm fins, against the 17.5 × 14.5 mm keep-out
(`DECISIONS.md` P-8). Required before any short test (H4 Block 4). Two
covers the board in use and one spare board; order 5 to fit every board.

---

## Not on this order (on hand, blueprint §8) ⚠

330 Ω and 10 Ω axial (R4, R6 contingency), the 10 kΩ for H4 step 13a, L1's
100 nF and 200 Ω 1 W, the Nucleo-F303RE, insulating pad for the heatsink.

---

## Verify yourself

1. **Economic PCBA with through-hole parts.** JLCPCB's FAQ says through-hole
   parts marked for wave or manual soldering are assembled, and its price
   page lists the hand-soldering fees under both tiers. The quote was not
   run here, because it needs the files uploaded. If the quote forces
   Standard PCBA, the totals barely move: setup $25.56, stencil $8.21 and
   $1.53 per part on all 33 parts come to $84.26, against Economic's $86.46.
2. **Board price and shipping** are the 2026-10-06 bare-board quote. PCBA
   adds weight, and shipping is set at checkout.
3. **The fees** ($3.07 per extended part, $3.58 labour, $0.0164 per joint)
   are from the price page, not a quote. Confirm them on the quote.
4. **Through-hole orientation in JLCPCB's preview:** Q1 (reversed, it swaps
   emitter and base) and J6 (wire entries to the board edge). See
   `README.md`, *Footprint orientation*. The CPL gives through-hole parts
   at their pin-1 origin, so the preview may draw them offset.
5. **RH-5001 in a 1.0 mm hole.** Its drawing shows the Keystone 5001 form
   (two 0.25 mm legs sprung to 1.4 mm) but gives no hole size. Keystone's
   is ~1.02 mm, and the footprint is drilled 1.0 mm. If JLCPCB's DFM flags
   it, that is where.
6. **Heatsink fit.** Which way the 19.81 mm runs comes from DigiKey's
   dimension names, not a drawing. Check the datasheet against the keep-out
   before ordering. Also the quantity, 2 or 5.
7. **Shipping for LCSC and DigiKey** was not quoted.
8. **The on-hand items** above.
