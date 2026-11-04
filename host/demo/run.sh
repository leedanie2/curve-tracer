#!/bin/sh
# The desk pipeline, end to end on ct_sim data: R_p calibration, diode || R_p,
# 2N7000-ish || R_p, each extracted, simulated in ngspice and overlaid.
# Every capture here is SIMULATED and marked so in its header and its figure.
# On the bench data, only the capture lines change (MVP_CARD section D);
# each later step is the one command shown. Run from host/: sh demo/run.sh
set -e
S="--sim-rptc 8.4 --sim-noise 2"

python -m ct_host capture --sim resistor --sim-rload 470 $S --vgs 0 --vds-max 1.5 \
    --n 100 --i-limit 40 --device R_p -o demo/rp.csv
python -m ct_host extract demo/rp.csv --type resistor

# Diode: capture, then model card -> ngspice -> overlay.
python -m ct_host capture --sim diode --sim-rpar 470 $S --vgs 0 --vds-max 1.5 \
    --n 100 --i-limit 40 --device 1N4148 --r-parallel demo/rp.csv -o demo/diode_rp.csv
python -m ct_host model    demo/diode_rp.csv --type diode --name D1N4148_SIM -o demo/diode.lib
python -m ct_host simulate demo/diode.lib --like demo/diode_rp.csv -o demo/diode_sim.csv
python -m ct_host overlay  demo/diode_rp.csv demo/diode_sim.csv --save ../media/demo_overlay_diode_SIMULATED.png

# MOSFET: the same three steps.
python -m ct_host capture --sim mosfet --sim-rpar 470 $S \
    --vgs 1.5,1.6,1.7,1.8,1.9,2.0,2.1,2.2,2.3,2.4,2.5,2.6,2.7,2.8,2.9,3.0 \
    --vds-max 3 --n 40 --i-limit 40 --device 2N7000 --r-parallel demo/rp.csv -o demo/mosfet_rp.csv
python -m ct_host model    demo/mosfet_rp.csv --type mosfet --name M2N7000_SIM -o demo/mosfet.lib
python -m ct_host simulate demo/mosfet.lib --like demo/mosfet_rp.csv -o demo/mosfet_sim.csv
python -m ct_host overlay  demo/mosfet_rp.csv demo/mosfet_sim.csv --save ../media/demo_overlay_mosfet_SIMULATED.png
