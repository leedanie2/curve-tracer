"""The offline evaluation: does adaptive sampling earn a firmware change?

    python -m ct_host.adaptive.evaluate --out ../docs/adaptive            # the study
    python -m ct_host.adaptive.evaluate --quick --out /tmp/adaptive       # smoke run
    python -m ct_host.adaptive.evaluate --from-csv dense_bench.csv \\
        --kind mosfet --out ../docs/adaptive-bench                         # bench, later

Every task runs one (device, noise, seed) combination through every design
and records, per design, the metrics of plan §4.5:

M1  points and wall time to reach the dense values within their stated
    uncertainty; M2 the stop outcome and where the time went; M3 coverage of
    the reported uncertainty; M4 curve reconstruction error; M5 whether the
    residual GP flags the mismatch or absorbs it; M6 thermal history; M7
    safety (refused proposals, trips).

``--from-csv`` replaces the synthetic oracle with a :class:`PoolOracle` on a
dense capture -- the bench path. Without a generative device there is no
truth, so M4 and the truth half of M3 and M5 are skipped; and a pool inherits
the dense capture's thermal history, so M6 is meaningless there and skipped.

All results are simulated unless ``--from-csv`` names a bench file, and every
row says which (``device``, ``source``). Figures quoted anywhere must come
from the results file this writes, not be retyped.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import traceback
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np

__all__ = ["Study", "run_task", "main"]

MOSFET_VGS = (2.3, 2.5, 2.7, 2.9, 3.1, 3.3)
RAMP_NS = (5, 6, 8, 12, 16, 24, 32, 48)
CRITERIA = ("us", "eig-theta", "eig-phi", "wa-phi")


@dataclass
class Study:
    """One task: a device at a noise level and seed, through a set of designs."""

    device: str
    noise_lsb: float
    seed: int
    designs: tuple[str, ...] = ("dense",) + tuple(f"ramp-{n}" for n in RAMP_NS) + CRITERIA
    k: int = 8
    seeds_per_gate: int = 5
    ordering: str = "sorted"
    thermal_scale: float = 1.0
    severity: dict = field(default_factory=dict)
    budget: int | None = None
    tag: str = "main"
    pool_csv: str | None = None
    kind: str | None = None
    #: targets nothing can meet, so a run spends its whole budget: for studies
    #: of what happens *after* the seeds (ordering, the safety filter)
    force_budget: bool = False
    i_limit_ma: float = 60.0
    #: if set, the designs' limit is this multiple of the part's own peak
    #: current (from its dense sweep): the only window in which the safety
    #: filter can bind without the seeds -- which include every curve's peak
    #: -- tripping the limit first
    i_limit_rel: float | None = None
    #: draw this seed's own device and PTC (see _device); off only for tests
    #: that need the nominal part
    jitter: bool = True


# --------------------------------------------------------------------------
# Setup
# --------------------------------------------------------------------------

#: Spread of the per-seed device draw: a different part on each seed, so
#: replicates are replicates even with no noise (at sigma_n = 0 the oracle is
#: otherwise deterministic). ASSUMED widths, of the order of a datasheet's.
JITTER = {"vth": 0.03, "k": 0.05, "lam": 0.15, "theta": 0.10, "r_s": 0.10,
          "r_d": 0.10, "i_s": 0.30, "n": 0.03, "i_s2": 0.30}
#: The board's PTC, unmeasured: the nSMD010's datasheet band (blueprint §3.6).
PTC_BAND_OHM = (1.6, 15.0)


def _device(st: Study):
    """The seed's own part: the named device, at its severity, jittered."""
    from .devices import device_by_name
    dev = device_by_name(st.device)
    if st.severity:
        dev = replace(dev, **st.severity)
    if not st.jitter:
        return dev
    rng = np.random.default_rng(10_007 * st.seed + 17)
    upd = {}
    for name, sd in JITTER.items():
        if not hasattr(dev, name):
            continue
        v = getattr(dev, name)
        if name in ("vth", "n"):
            upd[name] = v + rng.normal(0.0, sd)
        elif v:
            upd[name] = v * math.exp(rng.normal(0.0, sd))
    return replace(dev, **upd)


def _ptc(st: Study) -> float:
    if not st.jitter:
        return 0.0
    return float(np.random.default_rng(7919 * st.seed + 3).uniform(*PTC_BAND_OHM))


def _oracle(st: Study, dev, seed_offset: int, i_limit_ma: float | None = None):
    from .frontend import FrontEnd
    from .oracle import PoolOracle, SyntheticOracle
    if st.pool_csv:
        return PoolOracle(st.pool_csv)
    fe = FrontEnd(r_ptc=_ptc(st))
    if dev.kind == "mosfet":
        return SyntheticOracle(dev, fe=fe, vgs_list=MOSFET_VGS, vds_max=10.0,
                               i_limit_ma=i_limit_ma or st.i_limit_ma,
                               noise_lsb=st.noise_lsb, seed=st.seed * 1000 + seed_offset,
                               thermal_scale=st.thermal_scale)
    return SyntheticOracle(dev, fe=fe, vgs_list=[0.0], vds_max=2.0,
                           i_limit_ma=i_limit_ma or st.i_limit_ma,
                           noise_lsb=st.noise_lsb, seed=st.seed * 1000 + seed_offset,
                           thermal_scale=st.thermal_scale)


def _config(st: Study, kind: str, criterion: str = "eig-phi"):
    from . import estimate as E
    from .loop import DesignConfig
    targets = dict(E.MOSFET_TARGETS if kind == "mosfet" else E.DIODE_TARGETS)
    if st.force_budget:
        targets = {k: ("abs", 0.0) for k in targets}
    if kind == "mosfet":
        return DesignConfig("mosfet", criterion=criterion, k=st.k,
                            seeds_per_gate=st.seeds_per_gate,
                            budget=st.budget or 300, targets=targets,
                            ordering=st.ordering)
    return DesignConfig("diode", criterion=criterion, k=max(1, st.k // 2),
                        seeds_per_gate=st.seeds_per_gate, budget=st.budget or 50,
                        targets=targets, ordering=st.ordering)


# --------------------------------------------------------------------------
# Truth (synthetic only)
# --------------------------------------------------------------------------

def _truth(oracle, dev, dense_points, kind):
    """Noiseless curve at the dense design's points, as the dense ramp heated
    the device, and the same points isothermal at 300 K."""
    pts = [p for p in dense_points if p.true_v is not None and p.row.valid]
    if kind == "mosfet":
        X = np.array([[oracle.gate_volts[p.gate_index], p.true_v] for p in pts])
        y = np.array([p.true_i_ma for p in pts])
        iso = oracle.fe.terminal_current(dev, X[:, 0], X[:, 1], 300.0) * 1000.0
        return X, y, iso, oracle.fe.i_lsb_ma
    lsb = oracle.fe.i_lsb_ma
    pts = [p for p in pts if p.true_i_ma > 2.0 * lsb]
    X = np.array([[math.log(p.true_i_ma / 1000.0)] for p in pts]).reshape(-1, 1)
    y = np.array([p.true_v for p in pts])
    return X, y, None, oracle.fe.v_lsb_v


def _mismatch_mask(X, y, kind, lsb, n_lsb=1.0):
    """Where the device truly departs from its model: residual of the best
    parametric fit to the noiseless dense truth, beyond ``n_lsb`` output LSB
    -- 1 by default, the same magnitude floor the residual map uses."""
    from scipy.optimize import least_squares
    from .models import DiodeMean, MosfetMean
    if kind == "mosfet":
        m = MosfetMean()
        th0 = m.init(X, y, 5 * lsb)
        res = least_squares(lambda t: m.mean(t, X) - y, th0,
                            jac=lambda t: m.jac(t, X), max_nfev=300)
        r = y - m.mean(res.x, X)
    else:
        m = DiodeMean()
        th, *_ = np.linalg.lstsq(m.jac(None, X), y, rcond=None)
        r = y - m.mean(th, X)
    return np.abs(r) > n_lsb * lsb


# --------------------------------------------------------------------------
# Summaries
# --------------------------------------------------------------------------

def _params_row(prefix, params, names):
    out = {}
    for k in names:
        p = params.get(k) if params else None
        out[f"{prefix}{k}"] = p.value if p else math.nan
        out[f"{prefix}{k}_se"] = (p.stderr if p and p.stderr is not None else math.nan)
        out[f"{prefix}{k}_spread"] = (p.spread if p and p.spread is not None else math.nan)
        out[f"{prefix}{k}_u"] = p.u if p else math.nan
    return out


def _compare(row, names, ref, truth_params, prefix="est_"):
    within = []
    for k in names:
        est, u = row.get(f"{prefix}{k}", math.nan), row.get(f"{prefix}{k}_u", math.nan)
        dv = ref[k].value if ref and k in ref else math.nan
        du = ref[k].u if ref and k in ref else math.nan
        ok = abs(est - dv) <= du if all(map(math.isfinite, (est, dv, du))) else False
        row[f"{prefix}{k}_within_dense"] = ok
        z = (est - dv) / math.hypot(u, du) if all(map(math.isfinite, (est, dv, u, du))) and math.hypot(u, du) > 0 else math.nan
        row[f"{prefix}{k}_z_dense"] = z
        tv = truth_params.get(k, math.nan) if truth_params else math.nan
        row[f"{prefix}{k}_z_truth"] = ((est - tv) / u if all(map(math.isfinite, (est, tv, u))) and u > 0
                                       else math.nan)
        within.append(ok)
    row[f"{prefix}all_within_dense"] = bool(within) and all(within)


def _abs_t(name, value, names):
    from . import estimate as E
    table = E.MOSFET_TARGETS if name in E.MOSFET_TARGETS else E.DIODE_TARGETS
    kind, t = table[name]
    return t * abs(value) if kind == "rel" else t


def _thermal(points):
    if not points:
        return {}
    e = sum(p.power_w * p.dwell_s for p in points)
    return {"energy_mj": e * 1000.0,
            "peak_tj_k": max(p.tj_k for p in points),
            "mean_dwell_ms": 1000.0 * float(np.mean([p.dwell_s for p in points]))}


def _to_dense(result, ref, names):
    """First round from which every gated value stays within the dense u."""
    if not result.rounds or not ref:
        return math.nan, math.nan
    ok = [all(k in rr.values and k in ref and
              abs(rr.values[k] - ref[k].value) <= ref[k].u for k in names)
          for rr in result.rounds]
    for r in range(len(ok)):
        if all(ok[r:]):
            return result.rounds[r].n_points, result.rounds[r].clock_s
    return math.nan, math.nan


def _gp_metrics(gp, truth, mask):
    out = {}
    if gp is None or truth is None:
        return out
    X, y, iso, lsb = truth
    if X.size == 0:
        return out
    mu, var = gp.predict(X)
    err = mu - y
    sd = np.sqrt(var + 1e-30)
    out["recon_rmse_lsb"] = float(np.sqrt(np.mean(err ** 2)) / lsb)
    out["recon_max_lsb"] = float(np.max(np.abs(err)) / lsb)
    out["recon_cov95"] = float(np.mean(np.abs(err) <= 1.96 * sd))
    if iso is not None:
        out["recon_iso_rmse_lsb"] = float(np.sqrt(np.mean((mu - iso) ** 2)) / lsb)
    # The map: where the residual departs from zero by more than 3 sd (theta
    # held at its estimate) AND by more than one output LSB.
    dm, ds = gp.residual(X, given_theta=True)
    flag = (np.abs(dm) > 3.0 * np.maximum(ds, 1e-30)) & (np.abs(dm) > lsb)
    dm_marg, ds_marg = gp.residual(X)
    out["zmap_marginal_flagged_frac"] = float(np.mean(np.abs(dm_marg) > 3.0 * ds_marg))
    out["zmap_flagged_frac"] = float(np.mean(flag))
    out["residual_max_lsb"] = float(np.max(np.abs(dm)) / lsb)
    if mask is not None:
        tp = float(np.sum(flag & mask))
        out["zmap_precision"] = tp / float(np.sum(flag)) if flag.any() else math.nan
        out["zmap_recall"] = tp / float(np.sum(mask)) if mask.any() else math.nan
        out["true_mismatch_frac"] = float(np.mean(mask))
    return out


def _summarise(st, design, result, ref, names, truth, mask, truth_params, oracle,
               extra=None, mask3=None):
    row = {"tag": st.tag, "device": st.device, "noise_lsb": st.noise_lsb,
           "seed": st.seed, "design": design, "k": st.k, "seeds_per_gate": st.seeds_per_gate,
           "ordering": st.ordering, "thermal_scale": st.thermal_scale,
           "severity": json.dumps(st.severity) if st.severity else "",
           "source": getattr(oracle, "source", "")}
    row["n_points"] = result.n_points
    row["wall_s"] = result.clock_s
    row["compute_s"] = result.compute_s
    row["instrument_s"] = result.clock_s - result.compute_s
    for kk, v in result.breakdown.items():
        row[f"t_{kk}_s"] = v
    row["stop_reason"] = result.stop_reason
    row["targets_met"] = bool(result.assessment is not None and result.assessment.stop)
    row["rounds"] = len(result.rounds)
    # When stderr alone first met target (linearised), spreads aside: what a
    # spread-aware rule would have stopped at. The brief's rule does not.
    row["points_stderr_met"] = row["wall_stderr_met_s"] = math.nan
    for rr_ in result.rounds:
        if rr_.lin_sd and all(k in rr_.lin_sd and k in rr_.values and
                              rr_.lin_sd[k] <= _abs_t(k, rr_.values[k], names)
                              for k in names):
            row["points_stderr_met"] = rr_.n_points
            row["wall_stderr_met_s"] = rr_.clock_s
            break
    params = result.assessment.params if result.assessment else {}
    reported = names + tuple(k for k in ("beta", "rds_on") if k in params)
    row.update(_params_row("est_", params, reported))
    _compare(row, names, ref, truth_params)
    if params:
        row["raw_all_within_dense"] = all(
            params.get(k) is not None and params[k].raw_value is not None and k in ref
            and abs(params[k].raw_value - ref[k].value) <= ref[k].u for k in names)
    row["blocking"] = "; ".join(result.assessment.blocking) if result.assessment else ""
    row["spread_limited"] = ",".join(result.rounds[-1].spread_limited) if result.rounds else ""
    n2d, w2d = _to_dense(result, ref, names)
    row["points_to_dense"] = n2d
    row["wall_to_dense_s"] = w2d
    row["n_refused_last"] = result.n_refused
    row["ilimit_rows"] = sum(1 for p in result.points if p.row.flags)
    row["max_i_over_limit"] = (max((p.row.i_meas_ma for p in result.points), default=0.0)
                               / oracle.i_limit_ma)
    row["r_ser"] = result.r_ser
    row["r_ptc_true"] = getattr(oracle.fe, "r_ptc", math.nan)
    row["i_limit_ma"] = oracle.i_limit_ma
    if result.gp is not None:
        try:
            row["mismatch_lambda"] = result.gp.mismatch_statistic()
        except Exception:                                   # noqa: BLE001
            row["mismatch_lambda"] = math.nan
        row.update(_gp_metrics(result.gp, truth, mask))
        if mask3 is not None:
            row["true_mismatch_frac_3lsb"] = float(np.mean(mask3))
    if not st.pool_csv:
        row.update(_thermal(result.points))
    if extra:
        row.update(extra)
    return row


# --------------------------------------------------------------------------
# One task
# --------------------------------------------------------------------------

def run_task(st: Study) -> tuple[list[dict], list[dict]]:
    from . import estimate as E
    from .loop import RunResult, run_adaptive, run_ramp
    from .noise import NoiseModel

    rows, traces = [], []
    dev = None if st.pool_csv else _device(st)
    kind = st.kind or (dev.kind if dev else "mosfet")
    names = tuple(E.MOSFET_TARGETS) if kind == "mosfet" else tuple(E.DIODE_TARGETS)
    noise = NoiseModel(st.noise_lsb, st.noise_lsb)
    truth_params = dev.truth() if dev is not None else {}
    if kind == "diode" and dev is not None:
        truth_params = {"n": dev.n, "i_s": dev.i_s, "rs": dev.r_s}

    # -- the dense reference -------------------------------------------------
    o = _oracle(st, dev, 0)
    o.configure()
    t0 = time.perf_counter()
    if st.pool_csv:
        from ..recompute import recompute
        dense_points = None
        dense_sweep = recompute(o.pool_sweep)
        n_dense_pts = len(dense_sweep.valid_rows)
        cap_clock = o.clock
    else:
        cap = o.sweep(200)
        dense_points = cap.points
        dense_sweep = o.as_sweep(dense_points)
        n_dense_pts = len(dense_points)
        cap_clock = o.clock
    ref = E.reference(dense_sweep, kind, o.fe.i_lsb_ma)
    ref_compute = time.perf_counter() - t0
    truth = mask = mask3 = None
    if dense_points is not None:
        truth = _truth(o, dev, dense_points, kind)
        try:
            mask = _mismatch_mask(truth[0], truth[1], kind, truth[3], 1.0)
            mask3 = _mismatch_mask(truth[0], truth[1], kind, truth[3], 3.0)
        except Exception:                                   # noqa: BLE001
            mask = mask3 = None
    if "dense" in st.designs:
        dense_res = RunResult("dense", dense_points or [], [], "single_shot", None, None,
                              cap_clock, o.breakdown.as_dict(), 0.0)
        row = _summarise(st, "dense", dense_res, ref, names, truth, mask, truth_params, o,
                         {"n_points": n_dense_pts}, mask3=mask3)
        row.update(_params_row("est_", ref or {}, names + (("beta", "rds_on") if kind == "mosfet" else ())))
        _compare(row, names, ref, truth_params)
        row["analysis_s"] = ref_compute
        if dense_points:
            row.update(_thermal(dense_points))
        rows.append(row)

    # -- designs ---------------------------------------------------------------
    limit = None
    if st.i_limit_rel is not None:
        limit = st.i_limit_rel * max(r.i_ma for r in dense_sweep.valid_rows)
    for j, design in enumerate(d for d in st.designs if d != "dense"):
        rng = np.random.default_rng(st.seed * 7919 + j)
        o = _oracle(st, dev, j + 1, limit)
        cfg = _config(st, kind, design if design in CRITERIA else "eig-phi")
        try:
            if design.startswith("ramp-"):
                n = int(design.split("-")[1])
                res = run_ramp(o, n, cfg, noise, rng)
                rr = _summarise(st, design + "+gp", res, ref, names, truth, mask, truth_params, o,
                                 mask3=mask3)
                rows.append(rr)
                raw_ref = E.reference(o.as_sweep(res.points), kind, o.fe.i_lsb_ma)
                raw = _summarise(st, design + "+raw",
                                 replace(res, assessment=None, gp=None,
                                         clock_s=res.clock_s - res.compute_s, compute_s=0.0,
                                         stop_reason="single_shot"),
                                 ref, names, None, None, truth_params, o)
                raw.update(_params_row("est_", raw_ref or {}, names))
                _compare(raw, names, ref, truth_params)
                rows.append(raw)
            else:
                res = run_adaptive(o, cfg, noise, rng)
                rows.append(_summarise(st, design, res, ref, names, truth, mask, truth_params, o,
                                       mask3=mask3))
                for rr_ in res.rounds:
                    tr = {"tag": st.tag, "device": st.device, "noise_lsb": st.noise_lsb,
                          "seed": st.seed, "design": design, "k": st.k,
                          "ordering": st.ordering, "round": rr_.round,
                          "n_points": rr_.n_points, "clock_s": rr_.clock_s,
                          "compute_s": rr_.compute_s, "full_check": rr_.full}
                    for k_ in names:
                        tr[f"value_{k_}"] = rr_.values.get(k_, math.nan)
                        tr[f"lin_sd_{k_}"] = rr_.lin_sd.get(k_, math.nan)
                        tr[f"dense_{k_}"] = ref[k_].value if ref and k_ in ref else math.nan
                        tr[f"dense_u_{k_}"] = ref[k_].u if ref and k_ in ref else math.nan
                    traces.append(tr)
        except Exception as exc:                            # noqa: BLE001
            rows.append({"tag": st.tag, "device": st.device, "noise_lsb": st.noise_lsb,
                         "seed": st.seed, "design": design, "error": repr(exc),
                         "traceback": traceback.format_exc()[-1500:]})
    return rows, traces


# --------------------------------------------------------------------------
# The study plan
# --------------------------------------------------------------------------

def plan(quick: bool, reps: int) -> list[Study]:
    from .devices import diode_devices, mosfet_devices
    tasks: list[Study] = []
    noises = (0.0, 0.5, 2.0) if not quick else (0.5,)
    mos = list(mosfet_devices()) if not quick else ["sim-sq", "sim-theta"]
    dio = list(diode_devices()) if not quick else ["sim-diode"]
    designs_q = ("dense", "ramp-16", "eig-phi")
    for d in mos + dio:
        for nz in noises:
            for s in range(reps):
                tasks.append(Study(d, nz, s, designs=designs_q if quick else
                                   Study.__dataclass_fields__["designs"].default))
    if quick:
        return tasks
    # batch size: eig-phi only, fewer reps
    for d in ("sim-sq", "sim-theta", "sim-real", "sim-diode", "sim-diode2"):
        for k in (2, 4, 16, 32):
            for s in range(min(reps, 3)):
                tasks.append(Study(d, 0.5, s, designs=("eig-phi",), k=k, tag="k-sweep"))
    # Point order: forced to its budget, or a device that stops on its seeds
    # never measures an ordered batch at all. Same seeds -- the same part --
    # under every ordering, so they can be compared pairwise.
    for d in ("sim-heat", "sim-real", "sim-diode-heat"):
        for order in ("sorted", "acquisition", "interleave"):
            for s in range(min(reps, 5)):
                tasks.append(Study(d, 0.5, s, designs=("eig-phi",), ordering=order,
                                   force_budget=True,
                                   budget=150 if d != "sim-diode-heat" else 40,
                                   tag="ordering"))
    # The safety filter, with a limit it has to work against: 1.05 x the
    # part's own peak, so the filter (0.9 x limit, on the UCB) refuses the top
    # of the plane while the seeds still clear the limit.
    for d in ("sim-sq", "sim-theta", "sim-real"):
        for crit in ("us", "eig-phi"):
            for s in range(min(reps, 5)):
                tasks.append(Study(d, 0.5, s, designs=(crit,), i_limit_rel=1.05,
                                   force_budget=True, budget=150, tag="safety"))
    for d in ("sim-heat", "sim-real", "sim-diode-heat"):
        for scale in (0.5, 2.0):
            for s in range(min(reps, 5)):
                tasks.append(Study(d, 0.5, s, designs=("dense", "ramp-24", "eig-phi"),
                                   thermal_scale=scale, tag="thermal-scale"))
    # seeds
    for d in ("sim-sq", "sim-theta", "sim-real"):
        for s in range(min(reps, 5)):
            tasks.append(Study(d, 0.5, s, designs=("eig-phi",), seeds_per_gate=3,
                               tag="seeds-3"))
    # severity: does the flag fire as the departure grows?
    sev = {"sim-theta": [{"theta": t} for t in (0.02, 0.05, 0.1, 0.4)],
           "sim-rsd": [{"r_s": r, "r_d": r} for r in (0.25, 0.5, 2.0)],
           "sim-tail": [{"inversion_n": n} for n in (1.2, 1.8)],
           "sim-diode2": [{"i_s2": v} for v in (2e-10, 2e-9, 2e-7)]}
    for d, svs in sev.items():
        for sv in svs:
            for s in range(min(reps, 5)):
                tasks.append(Study(d, 0.5, s, designs=("dense", "ramp-24"), severity=sv,
                                   tag="severity"))
    return tasks


def _worker(st: Study):
    try:
        return run_task(st)
    except Exception as exc:                                # noqa: BLE001
        return ([{"tag": st.tag, "device": st.device, "noise_lsb": st.noise_lsb,
                  "seed": st.seed, "design": "*", "error": repr(exc),
                  "traceback": traceback.format_exc()[-1500:]}], [])


def _timing(out: Path) -> int:
    """Host compute per round with the machine to itself.

    The main study runs many workers at once with single-threaded BLAS, so
    its compute times are inflated; this measures the same code uncontended
    for the report to quote beside them.
    """
    import pandas as pd
    rows = []
    for dev in ("sim-sq", "sim-theta", "sim-real", "sim-diode"):
        for seed in range(3):
            r, _ = run_task(Study(dev, 0.5, seed, designs=("ramp-24", "eig-phi"),
                                  tag="timing"))
            rows += r
            print(f"  timing {dev} {seed}", file=sys.stderr)
    pd.DataFrame(rows).to_csv(out / "timing.csv.gz", index=False)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m ct_host.adaptive.evaluate",
                                 description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", required=True, help="directory for results and figures")
    ap.add_argument("--quick", action="store_true", help="a small smoke run")
    ap.add_argument("--reps", type=int, default=10)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--from-csv", dest="from_csv", metavar="FILE",
                    help="a dense capture (e.g. from the bench) to subsample")
    ap.add_argument("--kind", choices=["mosfet", "diode"],
                    help="device type, with --from-csv")
    ap.add_argument("--noise-lsb", type=float, default=None,
                    help="with --from-csv: the measured noise floor, rms LSB")
    ap.add_argument("--no-report", action="store_true")
    ap.add_argument("--timing", action="store_true",
                    help="uncontended host-compute calibration: a few tasks, one process, "
                         "default BLAS threads; writes timing.csv next to results.csv")
    args = ap.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.timing:
        return _timing(out)
    if args.from_csv:
        if not args.kind:
            ap.error("--from-csv needs --kind")
        tasks = [Study(Path(args.from_csv).stem, args.noise_lsb or 0.0, s,
                       pool_csv=args.from_csv, kind=args.kind, tag="pool")
                 for s in range(args.reps)]
    else:
        tasks = plan(args.quick, args.reps)

    print(f"{len(tasks)} tasks on {args.workers} workers -> {out}", file=sys.stderr)
    t0 = time.time()
    rows: list[dict] = []
    traces: list[dict] = []
    if args.workers <= 1:
        for i, st in enumerate(tasks):
            r, t = _worker(st)
            rows += r; traces += t
            print(f"  {i + 1}/{len(tasks)} {st.tag} {st.device} {st.noise_lsb} {st.seed}",
                  file=sys.stderr)
    else:
        import multiprocessing as mp
        ctx = mp.get_context("spawn")
        with ctx.Pool(args.workers) as pool:
            for i, (r, t) in enumerate(pool.imap_unordered(_worker, tasks)):
                rows += r; traces += t
                if (i + 1) % 10 == 0 or i + 1 == len(tasks):
                    print(f"  {i + 1}/{len(tasks)} done, {time.time() - t0:.0f} s",
                          file=sys.stderr)

    import pandas as pd
    df = pd.DataFrame(rows)
    # gzip: the study writes ~12 MB of text otherwise; pandas reads it as is.
    df.to_csv(out / "results.csv.gz", index=False)
    pd.DataFrame(traces).to_csv(out / "traces.csv.gz", index=False)
    meta = {"generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "tasks": len(tasks),
            "workers": args.workers, "elapsed_s": round(time.time() - t0, 1),
            "argv": sys.argv[1:] if argv is None else argv,
            "blas_threads": os.environ.get("OMP_NUM_THREADS", "default"),
            "note": "host compute was measured with this many workers sharing "
                    "the machine; treat compute times as conservative"}
    (out / "run.json").write_text(json.dumps(meta, indent=2))
    n_err = int(df["error"].notna().sum()) if "error" in df else 0
    print(f"wrote {len(df)} rows ({n_err} errors) in {meta['elapsed_s']} s", file=sys.stderr)
    if not args.no_report:
        from .report import write_report
        write_report(out, from_csv=bool(args.from_csv))
    return 0


if __name__ == "__main__":
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    sys.exit(main())
