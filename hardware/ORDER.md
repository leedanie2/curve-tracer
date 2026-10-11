# Order

Everything to buy for the board and its bring-up, by vendor. Stock and
prices were read on **2026-10-11**. Prices are USD. Items marked **⚠** are
not settled by this file; they are listed under *Verify yourself* at the end.

| Vendor | What | Subtotal | Shipping | Total |
|---|---|---|---|---|
| JLCPCB | 5 boards, all 5 assembled, every part fitted by JLCPCB, test loops included | $137.98 | $31.59 DHL Express (DDP), plus $55.82 duties and $9.66 sales tax | **$235.05 paid** |
| LCSC | H4 parts, contingency parts and jumper shunts. **Not yet ordered** | $13.72 | not quoted ⚠ | $13.72 + shipping |
| DigiKey | TO-126 heatsink and insulator. **Not yet ordered** | $5.37 | not quoted ⚠ | $5.37 + shipping |

All 5 boards are assembled (Daniel, 2026-10-11): spares against a soldering
accident, a reversed supply or a blown op-amp, with no second spin.

**JLCPCB status, 2026-10-11:** **paid**, order **W2026101205158610**
(PCB Y2-13791044A, PCBA SMT026101162484-13791044A), built from commit
`6af53c7`. The uploaded files are `curve-tracer_bom_jlc_6af53c7.csv` and
`curve-tracer_cpl_jlc_6af53c7.csv`, byte-identical copies of the committed
`fab/jlc/` files under new names (JLCPCB ignored a re-upload with the same
name). The cart gives an **estimated ship date of
Wed 14 Oct**; DHL Express (DDP) takes 2–4 business days, so the boards
arrive **Fri 16 – Tue 20 Oct**. Paid on 11 Oct, so both dates stand.
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
| Shipping: DHL Express (DDP), 1.38 kg, as charged | $31.59 |
| Customs duty (35% of merchandise) + duty and tax disbursement fee | $48.30 + $7.52 = $55.82 |
| Sales tax (~7% of merchandise) | $9.66 |
| **Order total, paid 2026-10-11** | **$235.05** |

**Paid against quoted.** The cart showed $165.14: $137.98 + $37.16
shipping − a $10.00 coupon. It did not show the duty, the disbursement fee
or the sales tax, which together add $65.48. Shipping as charged, $31.59, is
$4.43 more than the cart's $37.16 − $10.00 = $27.16; the invoice should
show whether the coupon was smaller or applied differently. The $55.82 of
duty and fee is the cost of DDP: the same duty is owed on any carrier, but
paying it at checkout keeps the parcel from waiting in customs.

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

## LCSC: H4 parts, contingency parts and shunts (one order)

**Not yet ordered.** Stock and prices checked 2026-10-11, after the JLCPCB
order; LCSC's own stock. Order now: the boards ship Oct 14 and arrive
Oct 16–20, and the blocking rows are needed on arrival day. **Blocking**
means H4 as written cannot proceed past that step without it; **contingency
only** means it is needed only if CONTINGENCY.md sends you there.

| For | MPN | Maker | LCSC | Qty | Unit | Cost | Stock | Missing when the boards arrive? |
|---|---|---|---|---|---|---|---|---|
| J3/J4 jumper shunts, 2.54 mm closed top | 2.54 short-circuit cap | BOOMELE | C100114 | 50 | $0.0094 | $0.47 | 500,950 | **Blocking.** Prep P2 puts both on RNG1; without a shunt there is no sweep current path past the rail checks. Skip only if 2.54 mm shunts are already in the cabinet |
| C_f 3.3 pF, C0G 0603 ±0.1 pF; P3 fits it as C1 | 0603CG3R3B500NT | FH | C2836771 | 50 | $0.0127 | $0.64 | 3,250 | **Blocking.** P3 fits it before first power-up; the board ships with C1 empty |
| C_f 1.5 pF | 0603CG1R5B500NT | FH | C507055 | 100 | $0.0066 | $0.66 | 1,800 | **Blocks H4 Block 2** (the C_f sweep, always run) |
| C_f 2.2 pF | 0603CG2R2B500NT | FH | C313085 | 50 | $0.0118 | $0.59 | 12,150 | **Blocks H4 Block 2** |
| C_f 2.7 pF | 0603CG2R7B500NT | FH | C2836769 | 50 | $0.0129 | $0.65 | 2,300 | **Blocks H4 Block 2** |
| C_f 3.9 pF | GRM1885C1H3R9BA01D | Murata | C162229 | 10 | $0.1428 | $1.43 | 925 | **Blocks H4 Block 2** |
| C_f 4.7 pF | 0603CG4R7B500NT | FH | C313086 | 100 | $0.0095 | $0.95 | 2,800 | **Blocks H4 Block 2** |
| L1 test load resistor: 200 Ω, **1 W**, 1%, metal film, axial | MFR1WSFTE52-200R | YAGEO | C172930 | 20 | $0.0303 | $0.61 | 3,080 | **Blocking** (L1, Blocks 1–2). Cabinet checklist below |
| L1 test load capacitor: 100 nF **X7R** 50 V, leaded | C317C104K5R5TA7301 | KEMET | C1882781 | 5 | $0.5240 | $2.62 | 1,314 | **Blocking** (L1). Cabinet checklist below |
| R_iso raise, 47 Ω 1 W axial (R8) | RN1WS47ΩFT/BA1 | TyoHM | C385394 | 20 | $0.0269 | $0.54 | 740 | Contingency only (CONTINGENCY A6) |
| R_B lower, 330 Ω **1 W** axial (R4) | MFR1WSFTE52-330R | YAGEO | C172941 | 20 | $0.0319 | $0.64 | 16,960 | Contingency only (CONTINGENCY A5). Cabinet checklist below |
| U1 fallback op-amp, cut tape | OPA2196IDR | TI | C2057972 | 2 | $1.5405 | $3.08 | 215 | Contingency only (CONTINGENCY A7, off-bench) |
| D3 spares (JLCPCB fits D3) | SMAJ12A | MDD | C113957 | 20 | $0.0432 | $0.86 | 77,700 | Contingency only (removal for ranges 2–3, or a damaged D3) |
| **Subtotal** | | | | | | **$13.72** | | |

**OPA2196: IDR, not ID.** The tube part (OPA2196ID, C2878263) was down to
21. The cut-tape OPA2196IDR is the same die and package: 215 in stock and
$1.54 against $2.44.

The 3.3 pF line covers both P3 and the 3.3 pF row of Block 2. The C_f sweep
does not have to finish before Blocks 3–4 electrically; the card runs it
first.

---

## DigiKey: heatsink and its insulator

**Not yet ordered.** Checked 2026-10-11.

| For | MPN | Maker | DigiKey | Qty | Unit | Cost | Stock | Missing when the boards arrive? |
|---|---|---|---|---|---|---|---|---|
| Q1 heatsink, TO-126 slide-on, 26 °C/W | 577500B00000G | Boyd | HS216-ND | 2 ⚠ | $1.76 | $3.52 | 5,546 | **Blocks H4 Block 4 only** (steps 14–15); the card's rule is no held short without it. Blocks 1–3 run without it |
| Insulator between Q1's tab and the heatsink: Sil-Pad K-10, Kapton-based, 0.152 mm, cut for TO-220 | SPK10-0.006-00-54 | Bergquist | BER114-ND | 5 | $0.37 | $1.85 | 55,835 | **Blocks H4 Block 4** with the heatsink. Cabinet checklist below |
| **Subtotal** | | | | | | **$5.37** | | |

Heatsink quantity: two covers the board in use and one spare; order 5 to
fit every board. 13.20 × 19.81 mm with 8.13 mm fins, against the 17.5 ×
14.5 mm keep-out (`DECISIONS.md` P-8).

---

## Lab cabinet checklist: assumed on hand

Take this to the cabinet before the boards arrive. **Order** means the
part is on the LCSC or DigiKey list above, because a substitute from the
cabinet is likely to be the wrong spec. **Cabinet** means a common item; use
it if it meets the spec exactly.

- [ ] **Nucleo-F303RE** (STMicroelectronics), with its USB Mini-B cable.
  - **Without it, nothing runs:** it is the MCU, both DACs, both ADCs and
    the host link.
  - **Cabinet:** it is the board the firmware was written for. If it is not
    there: DigiKey **497-15105-ND**, $20.13, 1,111 in stock (2026-10-11).
- [ ] **L1 resistor: 200 Ω, genuinely rated 1 W**, 1%, metal film, axial
  (D3.3 × L9 mm class).
  - **Why 1 W:** it dissipates 0.18 W at the card's 6 V and **0.60 W at the
    10.96 V full scale**, so a quarter-watt part is overloaded. An
    underrated 200 Ω already smoked on this project (Daniel, 2026-10-11).
    Check the marking or datasheet, not the body size alone.
  - **Without it:** no resistive load for H4 Blocks 1–2 (oscillation and
    step tests), and no full-scale ADC check against `11_q3.csv`.
  - **Order:** YAGEO MFR1WSFTE52-200R, LCSC **C172930**.
- [ ] **L1 capacitor: 100 nF, X7R or C0G, ≥ 25 V, leaded ceramic.**
  - **Not Y5V or Z5U.** Those are rated −20%/+80% and lose much of their
    capacitance under bias, so the "100 nF" stability load would not be
    100 nF. It is the top of the range R_iso was simulated clean for
    (100 pF–100 nF, sim 03).
  - **Without it:** no capacitive load, so H4 Blocks 1–2 cannot test
    stability.
  - **Order:** KEMET C317C104K5R5TA7301, LCSC **C1882781**. Cabinet only if
    you can confirm the dielectric.
- [ ] **Q1 heatsink insulator: TO-126 insulating pad**, polyimide-backed
  silicone, about 0.15–0.25 mm.
  - **Why:** the TO-126 tab is Q1's collector, tied to **+15 V**. Without
    the pad the heatsink is live at +15 V, and anything grounded touching
    it shorts the +15 V rail straight to ground, bypassing the limiter.
    Only the bench supply's current limit is left to protect the board.
  - **Without it:** H4 Block 4 (held short and short recovery) cannot run
    safely.
  - **Order:** Bergquist Sil-Pad K-10 SPK10-0.006-00-54, DigiKey
    **BER114-ND**. It is cut for TO-220, so trim it to the tab with
    scissors. The TO-126 shape (Bergquist 1009AC-60) is no longer stocked
    at DigiKey.
  - ⚠ **Check that the slide-on heatsink still grips with the pad in
    place.** H4 step P4 now checks both: heatsink to **TP7 (+15 V)** must
    read **OL** (the pad insulates), as well as heatsink to TP27 (ground),
    which a live heatsink also passes when nothing grounded touches it.
- [ ] **10 kΩ resistor**, any tolerance, ≥ 1/8 W.
  - Dissipates at most ~20 mW (+15 V across it with D3 reversed).
  - **Without it:** H4 step 13a cannot run, so D3's presence and
    orientation go unverified before the overshoot test.
  - **Cabinet:** the §8 0.1% assortment includes 10 kΩ.
- [ ] **330 Ω axial, 1 W**, for R4 (CONTINGENCY A5 only).
  - **Why 1 W:** it sits in parallel with R_B, itself a 1 W part. At the R_B
    voltage limit the card allows (14.85 V, step 14b) a 330 Ω carries
    **0.67 W**, so a quarter-watt part is overloaded.
  - **Order:** YAGEO MFR1WSFTE52-330R, LCSC **C172941**. Cabinet only if
    yours is genuinely 1 W; §8's on-hand 330 Ω does not state a rating.
- [ ] **10 Ω axial**, ≥ 1/4 W, for R6 (contingency only).
  - In parallel with R_sense it carries at most ~0.03 W.
  - **Cabinet:** §8 lists 10 Ω × 5.
- [ ] **Bench and assembly items** for the card (`H4_CARD.md` S1–S3, P5–P8):
  - bench supply, 15.00 V with a settable current limit;
  - scope with a 10× probe; DMM; thermometer for step 14d;
  - a 5.5 × 2.1 mm barrel plug for the reversed J1 lead (P7);
  - wire for the J6 D–S jumper and the Kelvin pair (P5, P6);
  - IPA, brush, a fine iron (C_f swaps), mini-grabbers.
  - **Cabinet.**

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
