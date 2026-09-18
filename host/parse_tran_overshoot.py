#!/usr/bin/env python3
"""Per-step rise/fall metrics from a stepped LTspice .tran .raw of sims 08/09.

Usage: python3 host/parse_tran_overshoot.py sim/08_sweep_source_rb_sweep.raw
       python3 host/parse_tran_overshoot.py sim/09_sweep_source_clamped.raw

Reads the binary .raw directly rather than trusting stepped .meas output in
the .log. From the .log it takes only the ".step" parameter values, any
".meas" results (08/09 log cl, rl and taupred per step; 09 adds taudiode),
and convergence notes.

Timing mirrors V2 = PULSE(v0 v1 1u 100n 100n 100u ...):

Rising edge (starts at 1 us):
  vbase = V(emitter) at 0.9 us, vhigh = V(emitter) at 90 us
  OS %  = 100 * (max V(emitter) over 1..90 us - vhigh) / (vhigh - vbase)
  slew  = max dV/dt on the rise; sust = median dV/dt over the 10-90 % rise
  flat  = fraction of the 10-90 % rise whose slope is within 10 % of sust.
          A slew-limited ramp is ~100 %; an exponential or second-order
          settle is well under half. Measured against the median, not the
          max, so a one-sample spike at the edge cannot hide a ramp.
  ts    = first t after which |V - vhigh| stays under 1 % of the step, to 90 us

Falling edge (starts at 101.1 us):
  vlow  = V(emitter) at the last sample
  tau   = fit of V = Vinf + A*exp(-t/tau) over the 80 %..20 % part of the
          fall, Vinf free. With the follower cut off and no clamp, the load
          discharges through RL and Ri+Rf+RG to ground, so Vinf should come
          out near 0 V; through a B-E clamp diode it sits near V_f.
  slew  = median -dV/dt in that window; flat is as for the rise. A fall the
          op-amp drives (slew-limited) is flat; a passive RC decay is not,
          and tau is only printed for falls that are not flat.
  off   = whether Vbe dropped under 0.4 V at any point in the fall
  Vbe   = min V(base) - V(emitter) over the fall (reverse bias if negative)
  I_snk = peak current the op-amp sinks through Rbase during the fall
  ts    = first t after which |V - vlow| stays under 1 % of the step, to end

I_op is the peak current the op-amp sources into Rbase on the rise. I(Rbase)
is positive from base to op-amp output, so sourcing shows up negative and
sinking positive.
"""

import os
import re
import sys

import numpy as np

SIGNAL = "V(emitter)"
BASE = "V(n004)"  # BD139 base in 08; that net has no FLAG
IBASE = "I(Rbase)"
T_EDGE = 1e-6
T_BASE = 0.9e-6
T_FIN = 90e-6
T_FALL = 101.1e-6
SETTLE_FRAC = 0.01
SLEW_FLAT_FRAC = 0.6  # "flat" above this counts as slew-limited
VBE_OFF = 0.4


def read_text(path):
    """LTspice writes utf-8 on some builds and utf-16 on others."""
    with open(path, "rb") as fh:
        raw = fh.read()
    for encoding in ("utf-8", "utf-16"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def read_raw(path):
    """Return (names, time, data) for a binary transient .raw.

    Header is utf-16-le up to "Binary:\\n". Each point is time as f64 followed
    by every other variable as f32, so the stride is 8 + 4*(nvars-1) bytes.
    LTspice may set the sign bit on time as a flag, hence abs(). data stays
    f32; callers widen the per-step slices they use.
    """
    with open(path, "rb") as fh:
        blob = fh.read()
    marker = "Binary:\n".encode("utf-16-le")
    idx = blob.find(marker)
    if idx < 0:
        raise ValueError(f"{path}: not a binary .raw (no 'Binary:' marker)")
    header = blob[:idx].decode("utf-16-le")
    body = memoryview(blob)[idx + len(marker):]

    nvars = int(re.search(r"No\. Variables:\s*(\d+)", header).group(1))
    npts = int(re.search(r"No\. Points:\s*(\d+)", header).group(1))
    if "double" in re.search(r"Flags:(.*)", header).group(1):
        raise ValueError(f"{path}: 'double' flag set; all-f64 layout not handled")

    names = []
    in_vars = False
    for line in header.splitlines():
        if line.startswith("Variables:"):
            in_vars = True
            continue
        if in_vars and line.startswith("\t"):
            names.append(line.split("\t")[2])
    if len(names) != nvars:
        raise ValueError(f"{path}: parsed {len(names)} names, header says {nvars}")

    stride = 8 + 4 * (nvars - 1)
    if len(body) != stride * npts:
        raise ValueError(
            f"{path}: body is {len(body)} bytes, expected {stride}*{npts}={stride * npts}"
        )

    rec = np.dtype([("t", "<f8"), ("v", "<f4", (nvars - 1,))])
    arr = np.frombuffer(body, dtype=rec, count=npts)
    return names, np.abs(arr["t"]), arr["v"]


def split_steps(time):
    """Each step restarts time at 0; split wherever time goes backwards."""
    starts = np.flatnonzero(np.diff(time) < 0) + 1
    return np.split(np.arange(len(time)), starts)


def read_log(log_path):
    """Return (params, meas, notes), one entry per step.

    params: [{'rb': '220', 'lcase': '1'}, ...] from '.step a=1 b=2' lines.
    meas:   {'cl': [1e-07, ...], ...} from 'Measurement: <name>' blocks.
    notes:  ['gmin', ...] summarising convergence messages under each .step.
    """
    if not os.path.exists(log_path):
        return [], {}, []
    params, meas, notes = [], {}, []
    current = None
    for line in read_text(log_path).splitlines():
        if line.startswith(".step "):
            params.append(dict(kv.split("=", 1) for kv in line.split()[1:]))
            notes.append(set())
            continue
        m = re.match(r"Measurement:\s*(\S+)", line)
        if m:
            current = meas.setdefault(m.group(1), [])
            continue
        if current is not None:
            row = re.match(r"^\s*\d+\s+(\S+)", line)
            if row:
                current.append(float(row.group(1)))
            continue
        if notes:
            low = line.lower()
            if "gmin stepping succeeded" in low:
                notes[-1].add("gmin")
            elif "source stepping succeeded" in low:
                notes[-1].add("src-step")
            elif "time step too small" in low or "singular" in low:
                notes[-1].add("FAIL")
            elif "failed" in low and "direct newton" not in low:
                notes[-1].add("FAIL")
    return params, meas, [",".join(sorted(n)) or "ok" for n in notes]


def settle_time(t, v, vfinal, band, t0):
    """First t (relative to t0) after which |v - vfinal| < band through t[-1]."""
    outside = np.flatnonzero(np.abs(v - vfinal) >= band)
    if outside.size == 0:
        return 0.0
    if outside[-1] + 1 >= len(t):
        return float("nan")
    return t[outside[-1] + 1] - t0


def first_cross(v, level, rising):
    hit = np.flatnonzero(v >= level if rising else v <= level)
    return hit[0] if hit.size else None


def flatness(dv):
    """(median slope, fraction of samples within 10 % of it)."""
    med = float(np.median(dv))
    return med, float(np.mean(np.abs(dv - med) <= 0.1 * abs(med)))


def measure(t, v, vbe, ib):
    r = {}

    # Rising edge.
    vbase = np.interp(T_BASE, t, v)
    vhigh = np.interp(T_FIN, t, v)
    step = vhigh - vbase
    rise = (t >= T_EDGE) & (t <= T_FIN)
    tr, vr = t[rise], v[rise]
    r["vbase"], r["vhigh"] = vbase, vhigh
    r["os"] = 100.0 * (vr.max() - vhigh) / step
    dv = np.gradient(vr, tr)
    r["slew"] = dv.max()
    i10 = first_cross(vr, vbase + 0.1 * step, True)
    i90 = first_cross(vr, vbase + 0.9 * step, True)
    if i10 is None or i90 is None or i90 <= i10:
        r["sust"] = r["flat"] = float("nan")
    else:
        r["sust"], r["flat"] = flatness(dv[i10:i90 + 1])
    r["ts_rise"] = settle_time(tr, vr, vhigh, SETTLE_FRAC * abs(step), T_EDGE)

    # Falling edge.
    fall = t >= T_FALL
    tf, vf, bf, ibf = t[fall], v[fall], vbe[fall], ib[fall]
    vlow = vf[-1]
    drop = vhigh - vlow
    r["vlow"] = vlow
    i80 = first_cross(vf, vlow + 0.8 * drop, False)
    i20 = first_cross(vf, vlow + 0.2 * drop, False)
    if i80 is None or i20 is None or i20 - i80 < 3:
        r["tau"] = r["vinf"] = r["r2"] = r["fslew"] = r["fflat"] = float("nan")
    else:
        seg = slice(i80, i20 + 1)
        r["tau"], r["vinf"], r["r2"] = fit_exp(tf[seg], vf[seg])
        r["fslew"], r["fflat"] = flatness(-np.gradient(vf[seg], tf[seg]))
    r["off"] = bool(bf.min() < VBE_OFF)
    r["vbe_min"] = bf.min()
    r["isnk"] = ibf.max()
    r["ts_fall"] = settle_time(tf, vf, vlow, SETTLE_FRAC * abs(drop), T_FALL)

    r["iop"] = -ib[rise].min()
    return r


def fit_exp(t, v, max_pts=20000):
    """Least-squares fit of v = vinf + a*exp(-(t - t[0])/tau); returns (tau, vinf, R^2).

    For fixed tau the model is linear in (vinf, a), so search tau on a log grid
    and refine with golden-section, solving the linear part at each trial.
    """
    step = max(1, len(t) // max_pts)
    x, y = t[::step] - t[0], v[::step]
    span = x[-1]

    def sse(tau):
        basis = np.column_stack([np.ones_like(x), np.exp(-x / tau)])
        coef, *_ = np.linalg.lstsq(basis, y, rcond=None)
        resid = y - basis @ coef
        return float(resid @ resid), coef

    grid = np.logspace(np.log10(span / 100), np.log10(span * 100), 121)
    k = int(np.argmin([sse(g)[0] for g in grid]))
    lo, hi = np.log(grid[max(k - 1, 0)]), np.log(grid[min(k + 1, len(grid) - 1)])
    g = (np.sqrt(5) - 1) / 2
    for _ in range(60):
        a, b = hi - g * (hi - lo), lo + g * (hi - lo)
        if sse(np.exp(a))[0] < sse(np.exp(b))[0]:
            hi = b
        else:
            lo = a
    tau = float(np.exp((lo + hi) / 2))
    err, (vinf, _) = sse(tau)
    r2 = 1.0 - err / float(np.sum((y - y.mean()) ** 2))
    return tau, float(vinf), r2


def eng(x, unit):
    if not np.isfinite(x):
        return "nan"
    for scale, prefix in ((1e9, "G"), (1e6, "M"), (1e3, "k"), (1, ""),
                          (1e-3, "m"), (1e-6, "u"), (1e-9, "n"), (1e-12, "p")):
        if abs(x) >= scale:
            return f"{x / scale:.3g}{prefix}{unit}"
    return f"{x:.3g}{unit}"


def main():
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <ltspice .raw>", file=sys.stderr)
        return 2
    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"no such file: {path}", file=sys.stderr)
        return 1

    names, time, data = read_raw(path)
    col = names.index(SIGNAL) - 1
    bcol = names.index(BASE) - 1
    icol = names.index(IBASE) - 1
    params, meas, notes = read_log(os.path.splitext(path)[0] + ".log")
    steps = split_steps(time)
    if params and len(params) != len(steps):
        print(f"warning: {len(params)} .step lines in log, {len(steps)} steps in raw",
              file=sys.stderr)

    def m(name, i):
        vals = meas.get(name, [])
        return vals[i] if i < len(vals) else float("nan")

    rows = []
    for i, idx in enumerate(steps):
        t = time[idx]
        v = data[idx, col].astype(np.float64)
        vbe = data[idx, bcol].astype(np.float64) - v
        ib = data[idx, icol].astype(np.float64)
        r = measure(t, v, vbe, ib)
        p = params[i] if i < len(params) else {}
        r["label"] = (f"{i + 1:>2}  Rb={p.get('rb', '?'):>4}  "
                      f"C={eng(m('cl', i), 'F'):>5}  RL={eng(m('rl', i), ''):>4}")
        if "tcase" in p:  # 08: 1 = 100 mV small-signal step, 2 = full-scale
            r["label"] += f"  tcase={p['tcase']}"
        r["taupred"] = m("taupred", i)
        r["taudiode"] = m("taudiode", i)
        r["conv"] = notes[i] if i < len(notes) else "?"
        rows.append(r)

    w = max(len(r["label"]) for r in rows)
    print("RISING EDGE (1 us)")
    print(f"{'':{w}}  {'vbase':>6}  {'vhigh':>6}  {'OS %':>5}  {'slew V/us':>9}  "
          f"{'sust V/us':>9}  {'flat':>5}  {'shape':>5}  {'ts1% us':>7}  {'I_op mA':>7}  conv")
    for r in rows:
        shape = "slew" if r["flat"] >= SLEW_FLAT_FRAC else "exp"
        print(f"{r['label']:{w}}  {r['vbase']:6.3f}  {r['vhigh']:6.3f}  {r['os']:5.2f}  "
              f"{r['slew'] * 1e-6:9.2f}  {r['sust'] * 1e-6:9.2f}  "
              f"{r['flat'] * 100:4.0f}%  {shape:>5}  "
              f"{r['ts_rise'] * 1e6:7.3f}  {r['iop'] * 1e3:7.2f}  {r['conv']}")

    print()
    print("FALLING EDGE (101.1 us)")
    print(f"{'':{w}}  {'vlow':>6}  {'tau fit':>8}  {'Vinf':>6}  {'R^2':>7}  "
          f"{'tau pas':>8}  {'tau dio':>8}  {'slew V/us':>9}  {'flat':>5}  {'shape':>5}  "
          f"{'off':>3}  {'Vbe min':>7}  {'I_snk mA':>8}  {'ts1%':>8}")
    for r in rows:
        slew = r["fflat"] >= SLEW_FLAT_FRAC
        shape = "slew" if slew else "exp"
        fit = ("-", "-", "-") if slew else (
            eng(r["tau"], "s"), f"{r['vinf']:.3f}", f"{r['r2']:.4f}")
        print(f"{r['label']:{w}}  {r['vlow']:6.3f}  {fit[0]:>8}  "
              f"{fit[1]:>6}  {fit[2]:>7}  {eng(r['taupred'], 's'):>8}  "
              f"{eng(r['taudiode'], 's'):>8}  {r['fslew'] * 1e-6:9.3f}  "
              f"{r['fflat'] * 100:4.0f}%  {shape:>5}  {'yes' if r['off'] else 'no':>3}  "
              f"{r['vbe_min']:7.2f}  {r['isnk'] * 1e3:8.2f}  {eng(r['ts_fall'], 's'):>8}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
