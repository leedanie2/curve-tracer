"""Tables and figures from an evaluation's ``results.csv.gz``.

Every number in ``report.md`` is computed here from the results file, so the
report cannot drift from the data. A narrative that quotes it should copy
from ``report.md``, not retype from memory -- and if the study is re-run, the
narrative is re-checked against the new report.

Figures use the reference categorical palette's first three slots (validated
all-pairs on the light surface: worst CVD dE 9.2, normal-vision 24.0). Aqua is
below 3:1 against the surface, so every figure has a table twin here, and
series are labelled, never colour-only.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

__all__ = ["write_report", "gate", "mismatch_table"]

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SLOT = ["#2a78d6", "#eb6834", "#1baf7a"]      # blue, orange, aqua

MOSFET_DEV = ["sim-sq", "sim-theta", "sim-rsd", "sim-heat", "sim-tail", "sim-real"]
DIODE_DEV = ["sim-diode", "sim-diode2", "sim-diode-heat"]
ADAPTIVE = ["us", "eig-theta", "eig-phi", "wa-phi"]
GATED = {"mosfet": ["vth", "kp_wl", "lambda"], "diode": ["n", "i_s", "rs"]}


def _kind(dev: str) -> str:
    return "diode" if "diode" in dev else "mosfet"


def _fmt(x, nd=2):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "--"
    if isinstance(x, (bool, np.bool_)):
        return "yes" if x else "no"
    if isinstance(x, (int, np.integer)):
        return str(int(x))
    ax = abs(x)
    if ax != 0 and (ax < 1e-3 or ax >= 1e5):
        return f"{x:.2e}"
    return f"{x:.{nd}f}"


def _md(df: pd.DataFrame, nd: int = 2) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(str(c) for c in cols) + " |",
           "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        out.append("| " + " | ".join(_fmt(r[c], nd) if not isinstance(r[c], str) else r[c]
                                     for c in cols) + " |")
    return "\n".join(out)


# --------------------------------------------------------------------------
# Derived per-run quantities
# --------------------------------------------------------------------------

def _ramp_to_dense(df: pd.DataFrame, suffix: str) -> pd.DataFrame:
    """Per (device, noise, seed): the smallest ramp whose result is within the
    dense uncertainty, and its wall time. A ramp has no rounds, so 'time to the
    dense values' is the cheapest ramp that gets there."""
    r = df[df.design.str.startswith("ramp-") & df.design.str.endswith(suffix)].copy()
    if r.empty:
        return pd.DataFrame()
    r["n_per_gate"] = r.design.str.extract(r"ramp-(\d+)").astype(int)
    rows = []
    for key, g in r.groupby(["device", "noise_lsb", "seed"]):
        ok = g[g.est_all_within_dense.astype(bool)].sort_values("n_per_gate")
        if ok.empty:
            rows.append((*key, math.nan, math.nan))
        else:
            best = ok.iloc[0]
            rows.append((*key, best.n_points, best.wall_s))
    return pd.DataFrame(rows, columns=["device", "noise_lsb", "seed",
                                       "points_to_dense", "wall_to_dense_s"])


def _coverage(g: pd.DataFrame, kind: str, which: str) -> float:
    zs = []
    for k in GATED[kind]:
        col = f"est_{k}_z_{which}"
        if col in g:
            zs.extend(g[col].dropna().tolist())
    return float(np.mean(np.abs(zs) <= 2.0)) if zs else math.nan


def _main(df: pd.DataFrame) -> pd.DataFrame:
    return df[(df.tag == "main") & df.error.isna()] if "error" in df else df[df.tag == "main"]


def summary_table(df: pd.DataFrame, noise: float) -> pd.DataFrame:
    """M1-M3 per device and design at one noise level, medians over seeds."""
    m = _main(df)
    m = m[m.noise_lsb == noise]
    out = []
    for dev in MOSFET_DEV + DIODE_DEV:
        d = m[m.device == dev]
        if d.empty:
            continue
        kind = _kind(dev)
        dense = d[d.design == "dense"]
        out.append({"device": dev, "design": "dense (n=200)",
                    "points": dense.n_points.median(), "wall_s": dense.wall_s.median(),
                    "to_dense_pts": math.nan, "to_dense_s": math.nan,
                    "reached": math.nan, "stop": "--",
                    "cov_dense": math.nan, "cov_truth": _coverage(dense, kind, "truth")})
        for suffix, label in (("+raw", "best ramp, raw"), ("+gp", "best ramp + GP")):
            rt = _ramp_to_dense(d, suffix)
            rr = d[d.design.str.endswith(suffix)]
            out.append({"device": dev, "design": label,
                        "points": math.nan, "wall_s": math.nan,
                        "to_dense_pts": rt.points_to_dense.median() if not rt.empty else math.nan,
                        "to_dense_s": rt.wall_to_dense_s.median() if not rt.empty else math.nan,
                        "reached": float(rt.points_to_dense.notna().mean()) if not rt.empty else math.nan,
                        "stop": "--",
                        "cov_dense": _coverage(rr, kind, "dense"),
                        "cov_truth": _coverage(rr, kind, "truth")})
        for crit in ADAPTIVE:
            a = d[d.design == crit]
            if a.empty:
                continue
            stops = a.stop_reason.value_counts()
            out.append({"device": dev, "design": crit,
                        "points": a.n_points.median(), "wall_s": a.wall_s.median(),
                        "to_dense_pts": a.points_to_dense.median(),
                        "to_dense_s": a.wall_to_dense_s.median(),
                        "reached": float(a.points_to_dense.notna().mean()),
                        "stop": ", ".join(f"{k} {v}" for k, v in stops.items()),
                        "cov_dense": _coverage(a, kind, "dense"),
                        "cov_truth": _coverage(a, kind, "truth")})
    return pd.DataFrame(out)


def gate(df: pd.DataFrame, noise: float, mismatch: pd.DataFrame) -> pd.DataFrame:
    """The plan's §4.6 criteria, per mismatched device, at one noise level."""
    m = _main(df)
    m = m[m.noise_lsb == noise]
    rows = []
    for dev in MOSFET_DEV + DIODE_DEV:
        if dev in ("sim-sq", "sim-diode"):
            continue
        d = m[m.device == dev]
        if d.empty:
            continue
        kind = _kind(dev)
        dense_wall = d[d.design == "dense"].wall_s.median()
        best_crit, best_t = None, math.inf
        for crit in ADAPTIVE:
            t = d[d.design == crit].wall_to_dense_s.median()
            if math.isfinite(t) and t < best_t:
                best_crit, best_t = crit, t
        # The comparator is the best option that needs no firmware change:
        # the cheaper of a raw sparse ramp and a sparse ramp + GP.
        ramp_t, ramp_lbl = math.inf, "--"
        for suffix in ("+raw", "+gp"):
            rt = _ramp_to_dense(d, suffix)
            t = rt.wall_to_dense_s.median() if not rt.empty else math.nan
            if math.isfinite(t) and t < ramp_t:
                ramp_t, ramp_lbl = t, "ramp" + suffix
        ramp_t = ramp_t if math.isfinite(ramp_t) else math.nan
        cov = (_coverage(d[d.design == best_crit], kind, "dense")
               if best_crit else math.nan)
        mm = mismatch[mismatch.device == dev]
        tpr = float(mm.tpr.iloc[0]) if not mm.empty else math.nan
        rows.append({
            "device": dev, "best adaptive": best_crit or "--",
            "to dense, s": best_t if best_crit else math.nan,
            "dense wall, s": dense_wall,
            "1: <= 50% dense": bool(best_crit) and best_t <= 0.5 * dense_wall,
            "no-firmware best": ramp_lbl,
            "its time to dense, s": ramp_t,
            "2: >= 30% under it": (bool(best_crit) and (not math.isfinite(ramp_t)
                                                        or best_t <= 0.7 * ramp_t)),
            "3: coverage": cov,
            "3: >= 90%": bool(math.isfinite(cov) and cov >= 0.9),
            "4: flag TPR": tpr,
        })
    return pd.DataFrame(rows)


def mismatch_table(df: pd.DataFrame, noise: float) -> tuple[pd.DataFrame, dict]:
    """Lambda per device.

    The threshold is the 95th percentile of Lambda on the control device of the
    same kind (every GP-bearing design, this noise level) -- a parametric
    bootstrap -- taken from **even** seeds only. Flag rates are measured on
    **odd** seeds, so the false-positive rate is not 5% by construction.
    """
    m = _main(df)
    m = m[(m.noise_lsb == noise) & m.mismatch_lambda.notna()]
    thr = {}
    for kind, ctl in (("mosfet", "sim-sq"), ("diode", "sim-diode")):
        lam = m[(m.device == ctl) & (m.seed % 2 == 0)].mismatch_lambda
        thr[kind] = float(np.quantile(lam, 0.95)) if len(lam) else math.nan
    rows = []
    for dev in MOSFET_DEV + DIODE_DEV:
        d = m[m.device == dev]
        if d.empty:
            continue
        t = thr[_kind(dev)]
        lam = d[d.seed % 2 == 1].mismatch_lambda
        if lam.empty:
            lam = d.mismatch_lambda
        rows.append({"device": dev, "runs": len(d), "held-out runs": len(lam),
                     "lambda median": d.mismatch_lambda.median(),
                     "lambda p5": d.mismatch_lambda.quantile(0.05),
                     "threshold": t, "tpr": float(np.mean(lam > t)) if dev not in ("sim-sq", "sim-diode") else math.nan,
                     "fpr": float(np.mean(lam > t)) if dev in ("sim-sq", "sim-diode") else math.nan,
                     "map flagged": d.zmap_flagged_frac.median() if "zmap_flagged_frac" in d else math.nan,
                     "map precision": d.zmap_precision.median() if "zmap_precision" in d else math.nan,
                     "map recall": d.zmap_recall.median() if "zmap_recall" in d else math.nan,
                     "true mismatch frac (1 LSB)": d.true_mismatch_frac.median() if "true_mismatch_frac" in d else math.nan,
                     "(3 LSB)": d.true_mismatch_frac_3lsb.median() if "true_mismatch_frac_3lsb" in d else math.nan,
                     "residual max, LSB": d.residual_max_lsb.median() if "residual_max_lsb" in d else math.nan})
    return pd.DataFrame(rows), thr


def calibration_table(df: pd.DataFrame) -> pd.DataFrame:
    """M3 against the generative truth, on the control devices only (where
    the truth is what the extractor estimates): every GP-bearing design, all
    gated parameters pooled. Nominal: 68.3% within 1 sigma, 95.4% within 2."""
    m = _main(df)
    rows = []
    for nz in sorted(m.noise_lsb.dropna().unique()):
        for dev in ("sim-sq", "sim-diode"):
            g = m[(m.device == dev) & (m.noise_lsb == nz)
                  & m.design.isin(ADAPTIVE + [f"ramp-{n}+gp" for n in (5, 6, 8, 12, 16, 24, 32, 48)])]
            parts = [g[f"est_{k}_z_truth"].dropna().values
                     for k in GATED[_kind(dev)] if f"est_{k}_z_truth" in g]
            zs = np.concatenate(parts) if parts else np.array([])
            if zs.size == 0:
                continue
            rows.append({"noise_lsb": nz, "device": dev, "estimates": int(zs.size),
                         "within 1 sigma": float(np.mean(np.abs(zs) <= 1.0)),
                         "within 2 sigma": float(np.mean(np.abs(zs) <= 2.0)),
                         "median |z|": float(np.median(np.abs(zs)))})
    return pd.DataFrame(rows)


def recon_table(df: pd.DataFrame, noise: float) -> pd.DataFrame:
    m = _main(df)
    m = m[(m.noise_lsb == noise) & m.recon_rmse_lsb.notna()] if "recon_rmse_lsb" in m else m.iloc[0:0]
    if m.empty:
        return m
    keep = m[m.design.isin(ADAPTIVE + ["ramp-16+gp", "ramp-48+gp"])]
    g = keep.groupby(["device", "design"]).agg(
        points=("n_points", "median"), rmse_lsb=("recon_rmse_lsb", "median"),
        max_lsb=("recon_max_lsb", "median"), band95=("recon_cov95", "median"),
        iso_rmse_lsb=("recon_iso_rmse_lsb", "median")).reset_index()
    return g


def thermal_table(df: pd.DataFrame) -> pd.DataFrame:
    """The purely thermal devices against their isothermal generative values.

    Only sim-heat and sim-diode-heat: on a device that also departs from the
    model, the generative values are not what any design estimates.
    """
    sel = _main(df)
    sel = sel[sel.device.isin(["sim-heat", "sim-diode-heat"]) & (sel.noise_lsb == 0.5)]
    rows = []
    for (dev, design), g in sel.groupby(["device", "design"]):
        if design not in ("dense", "ramp-8+raw", "ramp-24+raw", "ramp-24+gp", "eig-phi", "us"):
            continue
        kind = _kind(dev)
        r = {"device": dev, "design": design, "runs": len(g),
             "energy_mJ": g.energy_mj.median(), "peak_Tj_K": g.peak_tj_k.median(),
             "dwell_ms": g.mean_dwell_ms.median()}
        for k in GATED[kind]:
            r[k] = g[f"est_{k}"].median()
            r[f"{k} z"] = g[f"est_{k}_z_truth"].median()
        rows.append(r)
    return pd.DataFrame(rows)


def ordering_table(df: pd.DataFrame) -> pd.DataFrame:
    """Point order, paired: the same part (seed) under each ordering, every run
    forced to its budget so every ordered batch is measured. Differences are
    against 'sorted' on the same seed, in units of that run's stated u."""
    o = df[df.tag == "ordering"]
    if "error" in o:
        o = o[o.error.isna()]
    rows = []
    for dev, g in o.groupby("device"):
        kind = _kind(dev)
        base = g[g.ordering == "sorted"].set_index("seed")
        for order, h in g.groupby("ordering"):
            h = h.set_index("seed")
            r = {"device": dev, "ordering": order, "runs": len(h),
                 "points": h.n_points.median(), "energy_mJ": h.energy_mj.median(),
                 "peak_Tj_K": h.peak_tj_k.median()}
            common = h.index.intersection(base.index)
            for k in GATED[kind]:
                d = ((h.loc[common, f"est_{k}"] - base.loc[common, f"est_{k}"])
                     / base.loc[common, f"est_{k}_u"].replace(0, np.nan))
                r[f"{k}: (x - sorted)/u, median"] = d.median()
                r[f"{k}: max |.|"] = d.abs().max()
                if f"est_{k}_z_truth" in h and dev != "sim-real":
                    r[f"{k} z vs truth"] = h[f"est_{k}_z_truth"].median()
            rows.append(r)
    return pd.DataFrame(rows)


def safety_table(df: pd.DataFrame) -> pd.DataFrame:
    s = df[df.tag == "safety"]
    if "error" in s:
        s = s[s.error.isna()]
    if s.empty:
        return s
    return s.groupby(["device", "design"]).agg(
        runs=("seed", "count"), i_limit_ma=("i_limit_ma", "first"),
        points=("n_points", "median"), stop=("stop_reason", lambda x: ", ".join(
            f"{k} {v}" for k, v in x.value_counts().items())),
        refused_last_round=("n_refused_last", "median"),
        ilimit_rows=("ilimit_rows", "sum"),
        max_i_over_limit=("max_i_over_limit", "max")).reset_index()


def k_table(df: pd.DataFrame) -> pd.DataFrame:
    k = df[df.tag.isin(["k-sweep", "main"]) & (df.design == "eig-phi") & (df.noise_lsb == 0.5)
           & df.device.isin(["sim-sq", "sim-theta", "sim-real", "sim-diode", "sim-diode2"])]
    if "error" in k:
        k = k[k.error.isna()]
    k = k[k.seed < 3]
    return k.groupby(["device", "k"]).agg(
        runs=("seed", "count"), rounds=("rounds", "median"), points=("n_points", "median"),
        wall_s=("wall_s", "median"), compute_s=("compute_s", "median"),
        to_dense_pts=("points_to_dense", "median"), to_dense_s=("wall_to_dense_s", "median"),
    ).reset_index()


def stderr_met_table(df: pd.DataFrame, noise: float) -> pd.DataFrame:
    m = _main(df)
    m = m[(m.noise_lsb == noise) & m.design.isin(ADAPTIVE)]
    g = m.groupby(["device", "design"]).agg(
        stop_points=("n_points", "median"), stop_s=("wall_s", "median"),
        stderr_met_points=("points_stderr_met", "median"),
        stderr_met_s=("wall_stderr_met_s", "median"),
        spread_limited=("spread_limited", lambda s: ", ".join(sorted({x for v in s.dropna() for x in str(v).split(",") if x})))
    ).reset_index()
    return g


def timing_table(df: pd.DataFrame, noise: float) -> pd.DataFrame:
    m = _main(df)
    m = m[(m.noise_lsb == noise) & m.design.isin(ADAPTIVE + ["dense", "ramp-16+gp"])]
    cols = [c for c in m.columns if c.startswith("t_") and c.endswith("_s")]
    g = m.groupby("design")[cols + ["wall_s", "rounds"]].median().reset_index()
    g["compute per round, s"] = [
        (m[m.design == d].t_compute_s / m[m.design == d].rounds.clip(lower=1)).median()
        if d in ADAPTIVE else math.nan for d in g.design]
    return g.rename(columns={c: c[2:-2] for c in cols})


def severity_table(df: pd.DataFrame, thr: dict) -> pd.DataFrame:
    s = df[(df.tag == "severity") & (df.design == "ramp-24+gp")]
    if "error" in s:
        s = s[s.error.isna()]
    rows = []
    for (dev, sev), g in s.groupby(["device", "severity"]):
        t = thr.get(_kind(dev), math.nan)
        rows.append({"device": dev, "severity": sev, "runs": len(g),
                     "lambda median": g.mismatch_lambda.median(),
                     "flagged": float(np.mean(g.mismatch_lambda > t)),
                     "true mismatch frac": g.true_mismatch_frac.median() if "true_mismatch_frac" in g else math.nan})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Figures
# --------------------------------------------------------------------------

def _style(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
        ax.spines[side].set_linewidth(0.8)
    ax.tick_params(colors=INK2, labelsize=8, length=0)
    ax.grid(True, axis="x", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def fig_time_to_dense(df: pd.DataFrame, noise: float, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    m = _main(df)
    m = m[m.noise_lsb == noise]
    devs = [d for d in MOSFET_DEV + DIODE_DEV if d in set(m.device)]
    fig, axes = plt.subplots(len(devs), 1, figsize=(7.2, 0.95 * len(devs) + 1.0),
                             sharex=True, facecolor=SURFACE)
    axes = np.atleast_1d(axes)
    labels = ["ramp, raw", "ramp + GP", "best adaptive"]
    for ax, dev in zip(axes, devs):
        _style(ax)
        d = m[m.device == dev]
        dense = d[d.design == "dense"].wall_s.median()
        vals = []
        for suffix in ("+raw", "+gp"):
            rt = _ramp_to_dense(d, suffix)
            vals.append(rt.wall_to_dense_s.dropna().values if not rt.empty else np.array([]))
        best, best_med = None, math.inf
        for crit in ADAPTIVE:
            t = d[d.design == crit].wall_to_dense_s
            med = t.median()
            if t.notna().any() and med < best_med:
                best, best_med = t, med
        vals.append(best.dropna().values if best is not None else np.array([]))
        for j, v in enumerate(vals):
            if v.size:
                y = np.full(v.size, j) + np.linspace(-0.15, 0.15, v.size)
                ax.scatter(v, y, s=16, color=SLOT[j], edgecolor=SURFACE, linewidth=1.0,
                           zorder=3)
                ax.plot([np.median(v)] * 2, [j - 0.32, j + 0.32], color=SLOT[j], lw=1.5,
                        zorder=2)
        ax.axvline(dense, color=INK2, lw=1)
        ax.text(dense, 2.55, " dense", color=INK2, fontsize=7, va="center")
        ax.set_yticks([0, 1, 2], labels, fontsize=7, color=INK2)
        ax.set_ylim(-0.6, 2.8)
        ax.set_title(dev, fontsize=8, color=INK, loc="left", pad=2)
    axes[-1].set_xscale("log")
    from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator
    ticks = [0.1, 0.3, 1, 3, 10, 30, 100]
    axes[-1].xaxis.set_major_locator(FixedLocator(ticks))
    axes[-1].xaxis.set_minor_locator(NullLocator())
    axes[-1].xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:g}"))
    axes[-1].set_xlabel("wall time to the dense values, s (log)", fontsize=8, color=INK2)
    fig.suptitle(f"Time to the dense sweep's answer, noise {noise:g} LSB (simulated)",
                 fontsize=9, color=INK, x=0.02, ha="left")
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def fig_lambda(df: pd.DataFrame, noise: float, thr: dict, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    m = _main(df)
    m = m[(m.noise_lsb == noise) & m.mismatch_lambda.notna()]
    devs = [d for d in MOSFET_DEV + DIODE_DEV if d in set(m.device)]
    fig, ax = plt.subplots(figsize=(7.2, 0.32 * len(devs) + 1.2), facecolor=SURFACE)
    _style(ax)
    for j, dev in enumerate(devs):
        v = m[m.device == dev].mismatch_lambda.values
        ctl = dev in ("sim-sq", "sim-diode")
        y = np.full(v.size, j) + np.linspace(-0.25, 0.25, v.size)
        ax.scatter(np.clip(v, 0.1, None), y, s=10, color=MUTED if ctl else SLOT[0],
                   edgecolor=SURFACE, linewidth=0.8, zorder=3)
    for kind, color_ in (("mosfet", INK2), ("diode", INK2)):
        t = thr.get(kind)
        if t is not None and math.isfinite(t):
            js = [j for j, d in enumerate(devs) if _kind(d) == kind]
            ax.plot([max(t, 0.1)] * 2, [min(js) - 0.4, max(js) + 0.4], color=color_, lw=1)
            ax.text(max(t, 0.1), max(js) + 0.45, f" 95% of control ({kind})", fontsize=7,
                    color=INK2)
    ax.set_xscale("log")
    ax.set_yticks(range(len(devs)), devs, fontsize=7, color=INK2)
    ax.invert_yaxis()
    ax.set_xlabel("mismatch statistic Lambda (log; clipped at 0.1). Grey = control device",
                  fontsize=8, color=INK2)
    ax.set_title(f"Does the residual GP flag the mismatch? noise {noise:g} LSB (simulated)",
                 fontsize=9, color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def fig_k(kt: pd.DataFrame, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    if kt.empty:
        return
    devs = [d for d in ("sim-sq", "sim-theta", "sim-real") if d in set(kt.device)]
    fig, ax = plt.subplots(figsize=(6.0, 3.2), facecolor=SURFACE)
    _style(ax)
    ax.grid(True, axis="y", color=GRID, linewidth=0.6)
    for j, dev in enumerate(devs):
        d = kt[kt.device == dev].sort_values("k")
        ax.plot(d.k, d.to_dense_s, color=SLOT[j], lw=2, marker="o", ms=5,
                markeredgecolor=SURFACE, markeredgewidth=1.0, label=dev)
    # Two of the three series sit on top of each other near 1 s, so end labels
    # would collide; the legend carries identity instead.
    ax.set_xscale("log", base=2)
    from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator
    ax.xaxis.set_major_locator(FixedLocator([2, 4, 8, 16, 32]))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:g}"))
    ax.set_xlabel("batch size k (points per round trip)", fontsize=8, color=INK2)
    ax.set_ylabel("median wall time to the dense values, s", fontsize=8, color=INK2)
    ax.legend(fontsize=7, frameon=False, labelcolor=INK2)
    ax.set_title("Batch size against round trips, eig-phi, noise 0.5 LSB (simulated)",
                 fontsize=9, color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def fig_thermal(tt: pd.DataFrame, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    if tt.empty:
        return
    panels = [("sim-heat", "kp_wl z", "sim-heat: KP*W/L"),
              ("sim-heat", "lambda z", "sim-heat: lambda"),
              ("sim-diode-heat", "rs z", "sim-diode-heat: R_s")]
    fig, axes = plt.subplots(1, 3, figsize=(7.8, 2.6), facecolor=SURFACE)
    for ax, (dev, col, label) in zip(axes, panels):
        _style(ax)
        d = tt[tt.device == dev]
        if d.empty or col not in d:
            continue
        y = np.arange(len(d))
        ax.barh(y, d[col].values, color=SLOT[0], height=0.55)
        ax.axvline(0, color=AXIS, lw=0.8)
        ax.set_yticks(y, list(d.design), fontsize=6.5, color=INK2)
        ax.invert_yaxis()
        ax.set_title(label, fontsize=8, color=INK, loc="left")
        ax.set_xlabel("(estimate - isothermal truth) / u", fontsize=7, color=INK2)
    fig.suptitle("Self-heating against the isothermal truth, noise 0.5 LSB (simulated)",
                 fontsize=8.5, color=INK, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


# --------------------------------------------------------------------------

def _find(out: Path, stem: str) -> Path | None:
    for name in (f"{stem}.csv.gz", f"{stem}.csv"):
        if (out / name).exists():
            return out / name
    return None


def write_report(out: Path, *, from_csv: bool = False, noise: float = 0.5) -> Path:
    out = Path(out)
    df = pd.read_csv(_find(out, "results"), low_memory=False)
    if "error" not in df:
        df["error"] = np.nan
    meta = json.loads((out / "run.json").read_text()) if (out / "run.json").exists() else {}
    figs = out / "figures"
    figs.mkdir(exist_ok=True)
    mm, thr = mismatch_table(df, noise)
    lines = [
        "# Adaptive sampling: evaluation results (generated)",
        "",
        "**Generated by `ct_host/adaptive/report.py` from `results.csv`. Do not edit by hand;"
        " re-run the evaluation instead.**",
        "",
        f"- generated: {meta.get('generated', '?')}; tasks {meta.get('tasks', '?')}; "
        f"workers {meta.get('workers', '?')}; BLAS threads {meta.get('blas_threads', '?')}",
        f"- elapsed: {meta.get('elapsed_s', '?')} s; command: `{' '.join(meta.get('argv', []))}`",
        f"- rows: {len(df)}; rows with errors: {int(df.error.notna().sum())}",
        "- **Every result here is simulated** (`sim-*` devices, `source` column = synthetic oracle)"
        + ("" if not from_csv else "; except pool rows, which subsample the named capture") + ".",
        "- Host compute was measured with several workers sharing the machine, single-threaded"
        " BLAS. Treat compute and wall times as conservative.",
        "- Targets are PROVISIONAL (plan Q1): V_th 2 mV, KP 2%, lambda 20%; diode n 1%,"
        " I_S 10%, R_s 10%. Budgets 300 (MOSFET) and 50 (diode) points.",
        "",
    ]
    for nz in sorted(df.noise_lsb.dropna().unique()):
        st = summary_table(df, nz)
        if st.empty:
            continue
        lines += [f"## M1-M3 at noise {nz:g} LSB", "",
                  "Medians over seeds. `to_dense` = first point count (and wall time) from which "
                  "every gated parameter stays within the dense sweep's stated uncertainty "
                  "`sqrt(se^2 + (spread/2)^2)`; for ramps, the cheapest ramp that is within it. "
                  "`reached` = fraction of seeds that got there. `cov_*` = fraction of gated "
                  "parameter estimates within 2 combined sigma of the dense value / of the "
                  "generative truth (truth: control devices only are meaningful).", "",
                  _md(st), ""]
        if nz == noise:
            lines += ["![time to dense](figures/time_to_dense.png)", "",
                      "*Dots are seeds and the tick is their median. A row with no dots never "
                      "reached the dense values. The vertical line is the dense sweep's own "
                      "wall time.*", ""]
    ct = calibration_table(df)
    if not ct.empty:
        lines += ["## M3: calibration against the truth (control devices)", "",
                  "Every GP-bearing design (adaptive, and sparse ramps + GP), gated parameters "
                  "pooled, z = (estimate - generative value) / stated u. Nominal: 0.683 within "
                  "1 sigma, 0.954 within 2. Noise 0 is the undithered case, where oversampling "
                  "does not reduce quantisation error.", "", _md(ct), ""]
    g = gate(df, noise, mm)
    lines += [f"## The phase-2 gate (plan §4.6) at noise {noise:g} LSB", "",
              _md(g), "",
              f"## M5: mismatch statistic at noise {noise:g} LSB", "",
              "Threshold = 95th percentile of Lambda on the control device of the same kind, "
              "over every GP-bearing design at this noise, from even seeds; `tpr`/`fpr` are "
              "measured on odd seeds (held out). "
              "`map` columns: the residual map (|E delta| > 3 sd given theta and > 1 LSB) "
              "against where the noiseless truth departs from its best model fit by > 1 LSB "
              "(the same magnitude floor); the 3-LSB fraction is shown beside it.",
              "", _md(mm), "", "![Lambda](figures/lambda.png)", ""]
    sv = severity_table(df, thr)
    if not sv.empty:
        lines += ["### Flag rate against severity (ramp-24 + GP)", "", _md(sv), ""]
    rc = recon_table(df, noise)
    if not rc.empty:
        lines += [f"## M4: curve reconstruction at noise {noise:g} LSB", "",
                  "RMSE and max error of the posterior mean against the noiseless curve at the "
                  "dense design's points (under the dense ramp's heating), in output LSB; `band95` "
                  "= fraction inside the 95% band; `iso_rmse` = against the isothermal curve.",
                  "", _md(rc), ""]
    ts = timing_table(df, noise)
    if not ts.empty:
        lines += [f"## M2: where the time goes, noise {noise:g} LSB (medians, s)", "", _md(ts, 3), ""]
    tpath = _find(out, "timing")
    if tpath is not None:
        tm = pd.read_csv(tpath)
        if "error" in tm:
            tm = tm[tm.error.isna()]
        tm = tm[tm.design.isin(["eig-phi", "ramp-24+gp"])]
        cont = _main(df)
        cont = cont[(cont.noise_lsb == 0.5) & cont.design.isin(["eig-phi", "ramp-24+gp"])
                    & cont.device.isin(set(tm.device)) & (cont.seed < 3)]
        def per_round(g):
            return (g.compute_s / g.rounds.clip(lower=1)).median()
        trows = []
        for (dev, des), g in tm.groupby(["device", "design"]):
            c = cont[(cont.device == dev) & (cont.design == des)]
            trows.append({"device": dev, "design": des,
                          "uncontended compute, s": g.compute_s.median(),
                          "study compute, s": c.compute_s.median() if not c.empty else math.nan,
                          "uncontended per round, s": per_round(g) if des == "eig-phi" else math.nan,
                          "study per round, s": per_round(c) if des == "eig-phi" and not c.empty else math.nan,
                          "uncontended wall, s": g.wall_s.median(),
                          "uncontended to dense, s": g.wall_to_dense_s.median()})
        lines += ["## Host compute, uncontended (`--timing`)", "",
                  "The same code with the machine to itself (one process, default BLAS "
                  "threads), noise 0.5 LSB, seeds 0-2, beside the study's contended figures.",
                  "", _md(pd.DataFrame(trows), 3), ""]
    se = stderr_met_table(df, noise)
    if not se.empty:
        lines += ["## The rule as briefed against a spread-aware rule", "",
                  "`stderr_met` = first round at which every gated parameter's linearised stderr "
                  "met target, spreads aside. Past that point more points cannot help a "
                  "spread-limited parameter; the briefed rule keeps sampling to the budget.",
                  "", _md(se), ""]
    kt = k_table(df)
    if not kt.empty:
        lines += ["## Batch size (eig-phi, noise 0.5 LSB, seeds 0-2)", "", _md(kt), "",
                  "![k](figures/k.png)", ""]
    tt = thermal_table(df)
    if not tt.empty:
        lines += ["## M6: thermal history (noise 0.5 LSB)", "",
                  "Purely thermal devices only. `z` = (estimate - isothermal generative value) "
                  "/ stated u; energy is the DUT's dissipation integrated over the capture.",
                  "", _md(tt), "", "![thermal](figures/thermal.png)", ""]
    ot = ordering_table(df)
    if not ot.empty:
        lines += ["### Point order (eig-phi, forced to budget, paired by seed)", "",
                  "Each part measured three times, once per ordering. A difference beyond "
                  "~1 u is the thermal history changing the answer.", "", _md(ot), ""]
    sc = df[(df.tag == "thermal-scale")]
    if not sc.empty:
        sct = sc.groupby(["device", "design", "thermal_scale"]).agg(
            runs=("seed", "count"), energy_mJ=("energy_mj", "median"),
            peak_Tj_K=("peak_tj_k", "median")).reset_index()
        lines += ["### Thermal network scaled x0.5 / x2", "", _md(sct), ""]
    sd = df[df.tag == "seeds-3"]
    if not sd.empty:
        base = _main(df)
        base = base[(base.noise_lsb == 0.5) & (base.design == "eig-phi")
                    & base.device.isin(set(sd.device)) & (base.seed < 5)]
        both = pd.concat([base.assign(seeds=5), sd.assign(seeds=3)])
        sdt = both.groupby(["device", "seeds"]).agg(
            runs=("seed", "count"), points=("n_points", "median"), wall_s=("wall_s", "median"),
            to_dense_pts=("points_to_dense", "median"),
            reached=("points_to_dense", lambda s: float(s.notna().mean()))).reset_index()
        lines += ["## Seed density (eig-phi, noise 0.5 LSB)", "", _md(sdt), ""]
    sft = safety_table(df)
    if not sft.empty:
        lines += ["## M7: the safety filter against a tight limit", "",
                  "Each part's limit set to 1.05 x its own peak current; the filter refuses "
                  "candidates whose UCB reaches 0.9 x that. Runs forced to budget.",
                  "", _md(sft), ""]
    saf = _main(df)
    saf = saf[saf.design.isin(ADAPTIVE)]
    if not saf.empty:
        sat = saf.groupby("device").agg(
            runs=("seed", "count"), ilimit_rows=("ilimit_rows", "sum"),
            max_i_over_limit=("max_i_over_limit", "max"),
            refused_last_round=("n_refused_last", "median")).reset_index()
        lines += ["## M7: safety (adaptive designs, all noise levels)", "", _md(sat), ""]
    errs = df[df.error.notna()]
    if not errs.empty:
        lines += ["## Errors", "", _md(errs[["tag", "device", "noise_lsb", "seed", "design",
                                             "error"]].head(30)), ""]

    fig_time_to_dense(df, noise, figs / "time_to_dense.png")
    fig_lambda(df, noise, thr, figs / "lambda.png")
    fig_k(kt, figs / "k.png")
    fig_thermal(tt, figs / "thermal.png")
    path = out / "report.md"
    path.write_text("\n".join(lines) + "\n")
    return path
