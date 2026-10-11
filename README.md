# Curve Tracer

Programmable semiconductor curve tracer. Sweeps bias across a device,
measures I-V characteristics across ~5 decades of current, extracts
SPICE model parameters.

Status: in progress.

## Cost

**About $30 per instrument in parts.** This is a result of the design, not a
target. It counts the assembled board and the parts to run it, from the
5-board JLCPCB order of 2026-10-11:

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
of dollars.

**Low per-unit cost is not a project goal.** Do not use it to argue against
the accuracy parts. The 0.1% resistors and the three OPA2197s add only a few
dollars per board, and they are what make the closed-loop result credible.
That result is the deliverable: measured curves checked against the SPICE
model extracted from them.
