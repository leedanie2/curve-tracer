# Order

Everything to buy for the board and its bring-up, by vendor. Stock and
prices were read on **2026-10-11**. Prices are USD. Items marked **⚠** are
not settled by this file; they are listed under *Verify yourself* at the end.

| Vendor | What | Subtotal | Shipping | Total |
|---|---|---|---|---|
| JLCPCB | 5 boards, all 5 assembled, every part fitted by JLCPCB, test loops included | $137.98 | $37.16 DHL Express (DDP), less a $10.00 coupon | **$165.14** |
| LCSC | Contingency parts and jumper shunts | $11.66 | not quoted ⚠ | $11.66 + shipping |
| DigiKey | TO-126 heatsink | $3.52 | not quoted ⚠ | $3.52 + shipping |

All 5 boards are assembled (Daniel, 2026-10-11): spares against a soldering
accident, a reversed supply or a blown op-amp, with no second spin.

**JLCPCB status, 2026-10-11:** quoted and in the cart, from commit
`6af53c7`; payment is Daniel's. The cart gives an **estimated ship date of
Wed 14 Oct**; DHL Express (DDP) takes 2–4 business days, so the boards
arrive **Fri 16 – Tue 20 Oct**. Both dates assume payment on 11 Oct.
**Confirm Parts Placement is on**: JLCPCB's engineer checks the placement
and Daniel has **72 hours** to approve it, after which the order goes into
production automatically. Approving promptly keeps the ship date.

---

## JLCPCB: fab and PCBA (one order)

**Upload** from `hardware/fab/jlc/` (regenerate with
`hardware/tools/export_fab.py`, with KiCad's Python, after any change):

| Step | File |
|---|---|
| PCB quote | `curve-tracer_gerbers.zip` |
| PCBA BOM | `curve-tracer_bom_jlc.csv`: 33 lines, one per part, all matched |
| PCBA CPL | `curve-tracer_cpl_jlc.csv`: 74 rows |

**PCB:** 2 layers, FR-4, 1.6 mm, 135 × 92 mm, qty 5, green, HASL (with
lead), 24 h build (free with PCBA). **Express shipping** (blueprint §14.3a).
**PCBA:** Economic, top side, **5 assembled**, Confirm Parts Placement on.

**Cost, 5 assembled: JLCPCB's quote, 2026-10-11.** This is the order, not
an estimate:

| Item | Cost |
|---|---|
| PCB: board $6.00 + engineering fee $4.00 | $10.00 |
| PCBA setup (Economic) | $8.24 |
| Stencil | $1.55 |
| Components (33 lines) | $45.59 |
| **Extended-part fees: 18 SMD lines × $3.09** | **$55.62** |
| SMT joints | $1.37 |
| Confirm Parts Placement | $0.45 |
| Hand-soldering labour (per order) | $3.61 |
| Manual (through-hole) joints | $10.64 |
| Nitrogen reflow (JLCPCB's Economic default) | $0.91 |
| **Merchandise** | **$137.98** |
| Shipping: DHL Express (DDP), 1.38 kg | $37.16 |
| Coupon (applied by JLCPCB) | −$10.00 |
| **Total** | **$165.14** |

**Why the estimate was high ($188.56).** It charged the $3.07 loading fee
on all 25 extended lines. JLCPCB charges it **only on the 18 SMD extended
lines; the 7 through-hole lines (J1, J2/J5, J3/J4, J6, J7/J8, Q1, the
RH-5001 loops) carry no loading fee**, only the labour and per-joint
charges. That is $21.13 less in fees. The rest of the gap: the estimate
used the Oct 6 bare-board shipping ($31.23 at 0.34 kg) and no coupon, and
it priced JLCPCB's parts quantities slightly differently.

**Shipping options offered** (to the US, 1.38 kg; arrival counted from the
14 Oct ship date):

| Method | Cost | Transit | Arrives |
|---|---|---|---|
| **DHL Express (DDP)**, chosen | $37.16 | 2–4 business days | 16–20 Oct |
| DHL Express (duties billed on arrival) | $37.16 | 2–4 business days | 16–20 Oct |
| UPS Express Saver (DDP) | $38.32 | 2–4 business days | 16–20 Oct |
| FedEx Express (DDP) | $49.17 | 2–5 business days | 16–21 Oct |
| Global Standard Direct Line | $26.03 | 8–13 business days | ~26 Oct – 2 Nov |
| Own DHL / UPS / FedEx account | $2.00 + carrier | — | — |

**Customs description:** Sensor\Controller\Precision Instrument /
Multimeter, **HS 903090** (parts of instruments for measuring electrical
quantities), declared by JLCPCB at the order value (DDP).

**Order settings:** PCB build 24 h (free with PCBA), assembly 2–3 days,
HASL with lead (ENIG was +$18), 5 of 5 assembled, Economic, top side.

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

This table is the pre-quote estimate of the parts line. JLCPCB's own
quantities for some basic parts are smaller, and its components line is
$45.59. The through-hole lines (J1–J8, Q1, the RH-5001 loops) are all
assembly process THT, mode `manualWeld`, in JLCPCB's part records.

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

Settled at the quote, 2026-10-11:
- **Economic PCBA takes the through-hole parts.** All nine were selectable
  and assembled on Economic. Only C5's original part was "Standard Only",
  and it was replaced (`DECISIONS.md` C5).
- **Board price, shipping and fees** are now the quote's, above.
- **Orientation:** every polarised part was checked in JLCPCB's preview
  (`DECISIONS.md` P-10, revised), and Q1's tab faces the heatsink side.

Still open:
1. **Approve the placement confirmation within 72 hours**, or it
   auto-confirms.
2. **RH-5001 in a 1.0 mm hole.** Its drawing gives no hole size. If
   JLCPCB's DFM flags it, that is where.
3. **Heatsink fit.** Which way the 19.81 mm runs comes from DigiKey's
   dimension names, not a drawing. Check the datasheet against the keep-out
   before ordering. Also the quantity, 2 or 5.
4. **Shipping for LCSC and DigiKey** was not quoted.
5. **The on-hand items** above.
