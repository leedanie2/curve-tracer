#!/usr/bin/env python3
"""Current-limiter metrics per step from sim 10/11's .raw.

Usage: python3 host/parse_current_limit.py sim/10_current_limit.raw
       python3 host/parse_current_limit.py sim/11_limit_sizing.raw

Sim 10 holds the output at its setpoint, ramps the load from open to a short,
holds the short, then removes it. Node names follow the netlist: e_bjt is the
BD139 emitter (before R_sense), fb is after R_sense (the feedback tap), out is
the load node after R_iso, oa is the op-amp output.

Per step:
  I_load at trip = load current (through R_iso) when V(fb) first droops 1 %
                   below its open-load setpoint during the ramp
  held short     = values at T_HOLD: load current, R_sense current (the part
                   Q2 regulates), op-amp current into R_B, Q2 collector current,
                   Q2 / BD139 / op-amp dissipation
  op-amp limited = op-amp current within 2 % of the stepped Ilimit
  recovery       = after the short is removed at T_OPEN: peak V(fb) and V(out),
                   overshoot above the setpoint, and time until V(out) stays
                   within 1 % of the setpoint

Dissipations are V*I from the saved node voltages: BD139 is (V1 - V(e_bjt))
times its collector current, Q2 is (V(base) - V(fb)) * Ic(Q2), and the op-amp
is (V1 - V(oa)) * I_op. The op-amp model has Rail=0, so its output swings to
the rail and its dissipation here is a lower bound.
"""

import os
import sys

import numpy as np

from parse_tran_overshoot import read_log, read_raw, settle_time, split_steps

V1 = 15.0
R_ISO = 22.0
T_SET = 0.19e-3   # open load, before the ramp starts at 0.2 ms
T_RAMP = (0.2e-3, 2.2e-3)
T_HOLD = 3.1e-3   # short held from 2.2 ms to 3.2 ms
T_OPEN = 3.2e-3


def at(t, x, when):
    return float(np.interp(when, t, x))


def measure(t, sig):
    vfb, vout, vbase, ve, voa = (sig[k] for k in ("V(fb)", "V(out)", "V(base)", "V(e_bjt)", "V(oa)"))
    i_sense = sig["I(Rsense)"]
    i_op = -sig["I(Rbase)"]  # I(Rbase) runs base -> oa; sourcing is negative
    ic2, ib2 = sig["Ic(Q2)"], sig["Ib(Q2)"]
    i_load = (vfb - vout) / R_ISO

    r = {"vset": at(t, vfb, T_SET)}

    ramp = (t >= T_RAMP[0]) & (t <= T_RAMP[1])
    droop = np.flatnonzero(vfb[ramp] < 0.99 * r["vset"])
    if droop.size:
        k = np.flatnonzero(ramp)[droop[0]]
        r["i_trip"], r["isense_trip"] = i_load[k], i_sense[k]
    else:
        r["i_trip"] = r["isense_trip"] = float("nan")

    h = {k: at(t, x, T_HOLD) for k, x in
         (("i_load", i_load), ("i_sense", i_sense), ("i_op", i_op), ("ic2", ic2), ("ib2", ib2),
          ("vfb", vfb), ("vbase", vbase), ("ve", ve), ("voa", voa))}
    ib_bd = h["i_op"] - h["ic2"]
    ic_bd = h["i_sense"] + h["ib2"] - ib_bd
    r.update(h)
    r["p_q2"] = h["ic2"] * (h["vbase"] - h["vfb"]) + h["ib2"] * (h["ve"] - h["vfb"])
    r["p_bd"] = ic_bd * (V1 - h["ve"]) + ib_bd * (h["vbase"] - h["ve"])
    r["p_op"] = h["i_op"] * (V1 - h["voa"])

    rec = t >= T_OPEN
    tr, fr, orr = t[rec], vfb[rec], vout[rec]
    r["pk_fb"], r["pk_out"] = fr.max(), orr.max()
    r["os_out"] = 100.0 * (r["pk_out"] - r["vset"]) / r["vset"]
    r["t_above"] = float(np.sum(np.diff(tr)[orr[:-1] > 1.01 * r["vset"]]))
    r["ts_rec"] = settle_time(tr, orr, r["vset"], 0.01 * r["vset"], T_OPEN)
    return r


def main():
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <sim 10 .raw>", file=sys.stderr)
        return 2
    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"no such file: {path}", file=sys.stderr)
        return 1

    names, time, data = read_raw(path)
    params, meas, notes = read_log(os.path.splitext(path)[0] + ".log")
    wanted = ("V(fb)", "V(out)", "V(base)", "V(e_bjt)", "V(oa)",
              "I(Rbase)", "I(Rsense)", "Ic(Q2)", "Ib(Q2)")
    cols = {k: names.index(k) - 1 for k in wanted}

    rows = []
    for i, idx in enumerate(split_steps(time)):
        sig = {k: data[idx, c].astype(np.float64) for k, c in cols.items()}
        r = measure(time[idx], sig)
        p = params[i] if i < len(params) else {}
        # ilim is a step in sim 10; sim 11 fixes it and logs it as .meas ilimit
        fixed = meas.get("ilimit", [])
        ilim = float(p["ilim"]) if "ilim" in p else (fixed[i] if i < len(fixed) else float("nan"))
        r["limited"] = r["i_op"] >= 0.98 * ilim
        r["label"] = f"{i + 1}  " + "  ".join(f"{k}={v}" for k, v in p.items())
        r["conv"] = notes[i] if i < len(notes) else "?"
        rows.append(r)
    w = max(len(r["label"]) for r in rows)

    print("TRIP AND HELD SHORT (currents mA, power mW, voltages V)")
    print(f"{'':{w}}  {'Vset':>6}  {'I_trip':>6}  {'I_load':>6}  {'I_Rsns':>6}  {'I_op':>6}  "
          f"{'op lim':>6}  {'I_Q2':>6}  {'P_Q2':>5}  {'P_BD':>5}  {'P_op':>5}  "
          f"{'V(oa)':>6}  {'V(base)':>7}  conv")
    for r in rows:
        print(f"{r['label']:{w}}  {r['vset']:6.3f}  {r['i_trip'] * 1e3:6.1f}  "
              f"{r['i_load'] * 1e3:6.1f}  {r['i_sense'] * 1e3:6.1f}  {r['i_op'] * 1e3:6.1f}  "
              f"{'yes' if r['limited'] else 'no':>6}  {r['ic2'] * 1e3:6.1f}  "
              f"{r['p_q2'] * 1e3:5.0f}  {r['p_bd'] * 1e3:5.0f}  {r['p_op'] * 1e3:5.0f}  "
              f"{r['voa']:6.2f}  {r['vbase']:7.3f}  {r['conv']}")

    print()
    print("RECOVERY AFTER THE SHORT IS REMOVED (3.2 ms)")
    print(f"{'':{w}}  {'Vset':>6}  {'pk V(fb)':>8}  {'pk V(out)':>9}  {'OS %':>6}  "
          f"{'>1% for':>9}  {'ts1%':>9}")
    for r in rows:
        print(f"{r['label']:{w}}  {r['vset']:6.3f}  {r['pk_fb']:8.3f}  {r['pk_out']:9.3f}  "
              f"{r['os_out']:6.1f}  {r['t_above'] * 1e6:7.2f}us  {r['ts_rec'] * 1e6:7.2f}us")
    return 0


if __name__ == "__main__":
    sys.exit(main())
