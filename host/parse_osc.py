#!/usr/bin/env python3
"""Per-step sustained-oscillation metrics from a stepped LTspice .tran .raw (sims 12-14).

Usage: python3 host/parse_osc.py sim/12_bare_loop_cin.raw [--node 'V(e)'] [--kick 150e-6]
       python3 host/parse_osc.py sim/14_bare_loop_opa197.raw --ring 3e-6 14e-6
       python3 host/parse_osc.py sim/14b_l1_opa197.raw --residual 10e-6 14e-6

Timing mirrors sims 12-13: the DAC steps at 2 us, a small kick lands at
--kick (150 us), the run ends at T_END. Each step is resampled onto a
uniform 5 ns grid. Sim 14 is too short for a sustained state and has no
kick; --ring T0 T1 measures the start-up ring's frequency and decay instead.
Its L1 runs are still charging 100 nF at 14 us; --residual T0 T1 gives the
p-p left after a cubic fit to that settling, i.e. any ring riding on it.

  pp1   = p-p of the node over the 48 us before the kick (from 2 us if the
          kick is earlier than that), after the start-up step
  pp2   = p-p over the last 50 us, well after the kick
  f     = mean frequency from rising crossings of the mean over the last 50 us
  vdut  = mean V(dut) over the last 50 us (the DC the Kelvin ADC would see)
  idut  = mean I(Rsh) over the last 50 us, mA (the DC the shunt would see)
  osc   = 'SUSTAINED' when pp2 >= 10 mV (the MVP card's ~B + 5 mV scale
          rounded up), else 'quiet'

A loop that rings and decays reads quiet: pp2 starts 10+ us after the kick
kick, far longer than any decay the sims have shown (sim 09: < 2 us).
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse_tran_overshoot import read_log, read_raw, split_steps  # noqa: E402

DT = 5e-9
OSC_PP = 0.010


def resample(t, v, t0, t1):
    grid = np.arange(t0, t1, DT)
    return grid, np.interp(grid, t, v)


def freq(t, v):
    x = v - v.mean()
    up = np.flatnonzero((x[:-1] < 0) & (x[1:] >= 0))
    if len(up) < 3:
        return float("nan")
    return (len(up) - 1) / (t[up[-1]] - t[up[0]])


def ring(t, v, t0, t1):
    """Ring frequency and median ratio of successive half-cycle peaks.

    For runs too short to show a sustained state (sim 14). The final value is
    the mean of the window's last fifth; a ratio near 1 is near-marginal.
    """
    g, y = resample(t, v, t0, t1)
    y = y - y[-len(y) // 5:].mean()
    sc = np.flatnonzero(np.sign(y[:-1]) != np.sign(y[1:]))
    if len(sc) < 4:
        return float("nan"), float("nan"), np.ptp(y)
    pk = [np.abs(y[sc[k]:sc[k + 1]]).max() for k in range(len(sc) - 1)]
    f = (len(sc) - 1) / 2 / (g[sc[-1]] - g[sc[0]])
    return f, float(np.median(np.array(pk[1:]) / np.array(pk[:-1]))), pk[0]


def residual(t, v, t0, t1):
    """p-p of the node after removing a cubic fit (a slow settling curve)."""
    g, y = resample(t, v, t0, t1)
    x = g - g[0]
    return np.ptp(y - np.polyval(np.polyfit(x, y, 3), x))


def main_residual(path, node, t0, t1):
    names, time, data = read_raw(path)
    params, _, notes = read_log(os.path.splitext(path)[0] + ".log")
    col = {n: i - 1 for i, n in enumerate(names) if i}
    keys = list(params[0].keys()) if params else []
    print("\t".join(keys + ["mean V", "residual p-p mV", "solver"]))
    for k, idx in enumerate(split_steps(time)):
        v = data[idx, col[node]].astype(float)
        _, y = resample(time[idx], v, t0, t1)
        p = params[k] if k < len(params) else {}
        print("\t".join([p.get(key, "") for key in keys]
                        + [f"{y.mean():.4f}", f"{1e3 * residual(time[idx], v, t0, t1):.2f}",
                           notes[k] if k < len(notes) else ""]))


def main_ring(path, node, t0, t1):
    names, time, data = read_raw(path)
    params, _, notes = read_log(os.path.splitext(path)[0] + ".log")
    col = {n: i - 1 for i, n in enumerate(names) if i}
    keys = list(params[0].keys()) if params else []
    print("\t".join(keys + ["f MHz", "half-cycle ratio", "first peak mV", "solver"]))
    for k, idx in enumerate(split_steps(time)):
        f, r, p0 = ring(time[idx], data[idx, col[node]].astype(float), t0, t1)
        p = params[k] if k < len(params) else {}
        print("\t".join([p.get(key, "") for key in keys]
                        + ["-" if np.isnan(f) else f"{f / 1e6:.3f}",
                           "-" if np.isnan(r) else f"{r:.3f}",
                           f"{1e3 * p0:.1f}", notes[k] if k < len(notes) else ""]))


def main():
    path = sys.argv[1]
    node = "V(e)"
    if "--node" in sys.argv:
        node = sys.argv[sys.argv.index("--node") + 1]
    if "--ring" in sys.argv:
        i = sys.argv.index("--ring")
        main_ring(path, node, float(sys.argv[i + 1]), float(sys.argv[i + 2]))
        return
    if "--residual" in sys.argv:
        i = sys.argv.index("--residual")
        main_residual(path, node, float(sys.argv[i + 1]), float(sys.argv[i + 2]))
        return
    kick = 150e-6
    if "--kick" in sys.argv:
        kick = float(sys.argv[sys.argv.index("--kick") + 1])
    w1 = (max(kick - 50e-6, 2.5e-6), kick - 2e-6)
    names, time, data = read_raw(path)
    params, _, notes = read_log(os.path.splitext(path)[0] + ".log")
    col = {n: i - 1 for i, n in enumerate(names) if i}
    rows = []
    for k, idx in enumerate(split_steps(time)):
        t = time[idx]
        t_end = t[-1]
        w2 = (t_end - 50e-6, t_end)
        v = data[idx, col[node]].astype(float)
        _, a = resample(t, v, *w1)
        g2, b = resample(t, v, *w2)
        _, vd = resample(t, data[idx, col["V(dut)"]].astype(float), *w2)
        _, isn = resample(t, data[idx, col["I(Rsh)"]].astype(float), *w2)
        pp1, pp2 = np.ptp(a), np.ptp(b)
        f = freq(g2, b) if pp2 >= OSC_PP else float("nan")
        p = params[k] if k < len(params) else {}
        rows.append((p, pp1, pp2, f, vd.mean(), 1e3 * isn.mean(),
                     notes[k] if k < len(notes) else "", pp2 >= OSC_PP))
    keys = list(rows[0][0].keys()) if rows and rows[0][0] else []
    print("\t".join(keys + ["pp1 mV", "pp2 mV", "f MHz", "vdut V", "idut mA", "osc", "solver"]))
    for p, pp1, pp2, f, vd, i, note, osc in rows:
        print("\t".join([p.get(key, "") for key in keys]
                        + [f"{1e3 * pp1:.2f}", f"{1e3 * pp2:.2f}",
                           "-" if np.isnan(f) else f"{f / 1e6:.3f}",
                           f"{vd:.4f}", f"{i:.4f}",
                           "SUSTAINED" if osc else "quiet", note]))


if __name__ == "__main__":
    main()
