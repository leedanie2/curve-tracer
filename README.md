# Curve Tracer

Programmable semiconductor curve tracer. Sweeps bias across a device,
measures I-V characteristics across ~5 decades of current, extracts
SPICE model parameters.

Status: in progress.

## Layout

`hardware/` KiCad PCB and order files · `firmware/` STM32 firmware and tests ·
`host/` Python host tools · `sim/` SPICE and Monte Carlo analysis · `docs/`
characterization plans.

## Cost

The first build cost about **$283** (four orders in `hardware/ORDER.md`, shipping,
duty and tax included; excludes the Nucleo-F303RE). Most of that is one-time setup,
stencil and shipping across five boards. **Each additional instrument is about
$31**, including the Nucleo (~$18).

Low unit cost is not the goal. The 0.1% resistors and three OPA2197s add only a few
dollars per board and are what make the closed-loop result credible: measured
curves checked against the SPICE model extracted from them.
