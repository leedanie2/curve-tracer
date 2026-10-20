# Curve Tracer

Programmable semiconductor curve tracer. Sweeps bias across a device,
measures I-V characteristics across ~5 decades of current, extracts
SPICE model parameters.

Status: in progress.

## Cost

**The first build cost about $283, not $30.** That is the four orders in
`hardware/ORDER.md`, shipping, duty and tax included: JLCPCB $235.05 (five
assembled boards), LCSC ~$25.97, DigiKey $11.48 and ~$10.60. It excludes the
Nucleo-F303RE and any earlier prototype parts. Most of it is one-time or
shared across five boards: setup, stencil and extended-part fees, and
shipping and duty.

**Marginal cost is about $31 per additional instrument.** This is a result of
the design, not a target. It counts the assembled board and the parts to run
it, from the 5-board JLCPCB order of 2026-10-11, and is only a fair number if
you already have the one-time costs behind you:

| Item | Per instrument |
|---|---|
| Components on the board (JLCPCB unit prices) | ~$7.90 |
| Bare PCB | ~$1.20 |
| Assembly joints (SMT and through-hole) | ~$2.25 |
| Nucleo-F303RE | ~$18 |
| TO-126 heatsink | ~$1.80 |
| **Total** | **~$31** |

It excludes the one-time costs of a first order: setup, stencil and
extended-part loading fees, shipping and import duty
(`hardware/ORDER.md`). Commercial curve tracers cost hundreds to thousands
of dollars, so even the $283 first build is below that.

**Low per-unit cost is not a project goal.** Do not use it to argue against
the accuracy parts. The 0.1% resistors and the three OPA2197s add only a few
dollars per board, and they are what make the closed-loop result credible.
That result is the deliverable: measured curves checked against the SPICE
model extracted from them.
