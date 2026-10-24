# Curve Tracer

Curve tracer for MOSFETs and diodes, designed to be accessible in cost and usability. Sweeps drain voltage up to 10 V and
50 mA with four-wire sensing and a KiCad PCB. STM32 firmware receives the data, sending it over serial to a desktop Python script that extracts
device-specific parameters, such as threshold voltage, into a SPICE .model card for accurate simulation. Using simulated data, this design has calculated the threshold voltage to within 0.1% error of known values.

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
