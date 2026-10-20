"""Reported parameters, their uncertainty, and when to stop.

**The parameters come from the existing extractors, not from the GP's theta.**
When the device departs from the square law, ``extract_mosfet``'s answer
depends on where the points are: the sqrt-fit at the slice, the per-curve
lambda line and the diode least squares all weight the data by point density.
A sparse design and the dense design then converge to *different* values,
however many points are taken. So the estimand is "what the extractor returns
on the dense sweep", and it is estimated by pushing the GP posterior through
the unchanged extractor on the dense sweep's own grid:

1. place the dense design's commanded points at the measured drain voltages
   the posterior-mean curve predicts for them (through the series resistance
   fitted from the data, so an unmeasured PTC is handled);
2. draw posterior samples of the curve there, wrap each as a ``Sweep``;
3. run the extractor on each.

Reported per parameter, in the same two numbers ``describe()`` prints for a
dense capture:

* **stderr**: the spread of the extractor over posterior samples -- the
  measurement-limited part;
* **spread**: the extractor over a grid of fit-range choices on the posterior
  mean -- the procedure-limited part. Only V_th has such a grid in the
  extractor today (plan F1), so the grid for beta, KP, lambda and the diode is
  computed here, by re-running the extractor with different slices, margins
  and current windows. ``extract/*.py`` is unchanged (plan Q2 is open).

The same extractor is also run directly on the raw adaptive points, as a
model-free cross-check; a disagreement blocks stopping, so the GP is never
the only path from data to a number.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

import numpy as np
import pandas  # noqa: F401  -- vth_sensitivity imports it; load it once, not mid-capture

from ..csvio import Row, Sweep
from ..extract import FitError, extract_diode, extract_mosfet
from .gp import PhysGP
from .models import DiodeMean, MosfetMean
from .noise import NoiseModel
from .oracle import OracleBase, Point
from .devices import VT_300K

__all__ = ["Targets", "MOSFET_TARGETS", "DIODE_TARGETS", "ParamResult",
           "Assessment", "DenseGrid", "series_resistance", "fit_gp",
           "dense_grid", "grid_sweep", "extract_values", "spread_grid",
           "linearise", "assess", "reference"]

#: Gate parameters, as (kind, target). PROVISIONAL: plan Q1 is open. "rel"
#: targets multiply |value|. R_DS(on) is reported, not gated.
MOSFET_TARGETS = {"vth": ("abs", 2e-3), "kp_wl": ("rel", 0.02),
                  "lambda": ("rel", 0.20)}
DIODE_TARGETS = {"n": ("rel", 0.01), "i_s": ("rel", 0.10), "rs": ("rel", 0.10)}
Targets = dict

I_FLOOR_LSB = 5.0           # the extractors' own floor
GP_FLOOR_LSB = 2.0          # diode: points below this carry no ln(I)


@dataclass
class ParamResult:
    name: str
    value: float
    stderr: float | None
    spread: float | None
    raw_value: float | None = None
    raw_stderr: float | None = None
    target: float | None = None

    @property
    def u(self) -> float:
        """Combined: sqrt(stderr^2 + (spread/2)^2)."""
        se = self.stderr or 0.0
        sp = (self.spread or 0.0) / 2.0
        return math.hypot(se, sp)

    @property
    def crosscheck_ok(self) -> bool | None:
        if self.raw_value is None:
            return None
        sig = math.hypot(self.u, self.raw_stderr or 0.0)
        return abs(self.value - self.raw_value) <= 3.0 * max(sig, 1e-15)

    @property
    def meets_target(self) -> bool:
        if self.target is None:
            return True
        return ((self.stderr or 0.0) <= self.target
                and (self.spread or 0.0) / 2.0 <= self.target)


@dataclass
class Assessment:
    params: dict[str, ParamResult]
    sample_failures: int = 0
    n_samples: int = 0
    full: bool = True
    blocking: list[str] = field(default_factory=list)

    @property
    def stop(self) -> bool:
        return self.full and not self.blocking


# --------------------------------------------------------------------------
# Building blocks
# --------------------------------------------------------------------------

def series_resistance(oracle: OracleBase, points: list[Point]) -> float:
    """Through-origin fit of commanded-minus-measured voltage against current.

    The same fit ``vds_delta_report`` does, on exact DAC volts. It absorbs a
    PTC nobody has measured yet.
    """
    rows = oracle.as_sweep(points).rows
    i_a, delta = [], []
    for p, r in zip(points, rows):
        if r.valid and r.i_ma > 1.0:
            i_a.append(r.i_ma / 1000.0 + r.v_dut / oracle.fe.r_div)
            delta.append(float(oracle.fe.code_to_volts(p.code)) - r.v_dut)
    if len(i_a) < 2:
        return oracle.fe.r_iso + oracle.fe.shunt
    i_a, delta = np.array(i_a), np.array(delta)
    return float(i_a @ delta / (i_a @ i_a))


def gp_data(oracle: OracleBase, points: list[Point], kind: str):
    """(X, y) for the GP from measured points; valid rows only."""
    rows = oracle.as_sweep(points).rows
    keep = [k for k, r in enumerate(rows) if r.valid]
    if kind == "mosfet":
        X = oracle.inputs([points[k] for k in keep])
        y = np.array([rows[k].i_ma for k in keep])
        return X, y
    lsb = oracle.fe.i_lsb_ma
    sel = [k for k in keep if rows[k].i_ma > GP_FLOOR_LSB * lsb]
    X = np.array([[math.log(rows[k].i_ma / 1000.0)] for k in sel]).reshape(-1, 1)
    y = np.array([rows[k].v_dut for k in sel])
    return X, y


def fit_gp(oracle: OracleBase, points: list[Point], kind: str, noise: NoiseModel,
           *, previous: PhysGP | None = None, restarts: int = 1) -> PhysGP:
    X, y = gp_data(oracle, points, kind)
    model = MosfetMean() if kind == "mosfet" else DiodeMean()
    gp = PhysGP(model, X, y, noise, i_floor_ma=I_FLOOR_LSB * oracle.fe.i_lsb_ma,
                hyper=None if previous is None else previous.h,
                theta=None if previous is None else previous.st.theta)
    return gp.fit(restarts=restarts if previous is None else 0,
                  alternations=2 if previous is None else 1)


@dataclass
class DenseGrid:
    """The dense design's points, placed where the posterior mean puts them."""

    gate_index: np.ndarray
    code: np.ndarray
    X: np.ndarray            # GP inputs
    v: np.ndarray            # measured drain voltage
    i_ma: np.ndarray | None  # diode: fixed current at each point
    n_dense: int
    #: per point, as a dense capture's CSV would carry them (3-dp rounding)
    vgs_r: list[float] = field(default_factory=list)
    vset_r: list[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.factors = None      # filled by the caller that owns the GP


def _invert_mosfet(gp: PhysGP, oracle: OracleBase, gate_index: int,
                   codes: np.ndarray, r_ser: float) -> np.ndarray:
    v_node = oracle.fe.code_to_volts(codes)
    vmax = float(np.max(v_node)) if v_node.size else 0.0
    vf = np.linspace(0.0, max(vmax, 1e-3), 600)
    Xf = np.column_stack([np.full_like(vf, oracle.gate_volts[gate_index]), vf])
    mu, _ = gp.predict(Xf)
    g = vf + (np.maximum(mu, 0.0) / 1000.0 + vf / oracle.fe.r_div) * r_ser
    g = np.maximum.accumulate(g)
    return np.interp(v_node, g, vf)


def _invert_diode(gp: PhysGP, oracle: OracleBase, codes: np.ndarray,
                  r_ser: float, i_hi_ma: float):
    lsb = oracle.fe.i_lsb_ma
    uf = np.linspace(math.log(GP_FLOOR_LSB * lsb / 1000.0),
                     math.log(max(i_hi_ma, 3 * lsb) / 1000.0), 800)
    mu, _ = gp.predict(uf[:, None])
    g = np.maximum.accumulate(mu + (np.exp(uf) + mu / oracle.fe.r_div) * r_ser)
    v_node = oracle.fe.code_to_volts(codes)
    inside = (v_node >= g[0]) & (v_node <= g[-1])
    u = np.interp(v_node, g, uf)
    return u, inside


def dense_grid(gp: PhysGP, oracle: OracleBase, kind: str, n_dense: int,
               r_ser: float, i_hi_ma: float | None = None) -> DenseGrid:
    codes = np.array(oracle.fe.ramp_codes(n_dense, oracle.vds_max))
    if kind == "mosfet":
        gi, cc, vv = [], [], []
        for g in range(len(oracle.vgs_list)):
            v = _invert_mosfet(gp, oracle, g, codes, r_ser)
            gi.append(np.full(codes.size, g)); cc.append(codes); vv.append(v)
        gi, cc, vv = np.concatenate(gi), np.concatenate(cc), np.concatenate(vv)
        X = np.column_stack([np.array(oracle.gate_volts)[gi], vv])
        return DenseGrid(gi, cc, X, vv, None, n_dense, *_rounded(oracle, gi, cc))
    u, inside = _invert_diode(gp, oracle, codes, r_ser, i_hi_ma or 60.0)
    mu, _ = gp.predict(u[inside][:, None])
    gi = np.zeros(int(inside.sum()), int)
    return DenseGrid(gi, codes[inside], u[inside][:, None], mu,
                     np.exp(u[inside]) * 1000.0, n_dense,
                     *_rounded(oracle, gi, codes[inside]))


def _rounded(oracle: OracleBase, gi: np.ndarray, codes: np.ndarray):
    vgs = np.round(np.array(oracle.gate_volts)[gi], 3).tolist()
    vset = np.round(oracle.fe.code_to_volts(codes), 3).tolist()
    return vgs, vset


def grid_sweep(oracle: OracleBase, grid: DenseGrid, values: np.ndarray,
               kind: str) -> Sweep:
    """A Sweep of the dense grid with the given curve values, ready to extract.

    MOSFET values are currents (mA) at fixed measured voltages; diode values
    are voltages at fixed currents. Gate voltages carry the CSV's 3-dp
    rounding, as a dense capture's would.
    """
    if kind == "mosfet":
        vs, ii = grid.v.tolist(), np.asarray(values, float).tolist()
    else:
        vs, ii = np.asarray(values, float).tolist(), grid.i_ma.tolist()
    rows = [Row(point=k, vgs_set_v=g, vds_set_v=vset, vds_meas_v=v, i_meas_ma=i,
                i_acc=0, v_acc=0, range=1, flags="", i_recomp_ma=i, v_recomp_v=v)
            for k, (g, vset, v, i) in enumerate(zip(grid.vgs_r, grid.vset_r, vs, ii))]
    return Sweep(meta=oracle.metadata(grid.n_dense), rows=rows, end_reason="ok",
                 recomputed=True)


# --------------------------------------------------------------------------
# Extraction and its fit-range grid
# --------------------------------------------------------------------------

MOSFET_REPORTED = ("vth", "beta", "kp_wl", "lambda", "rds_on")
DIODE_REPORTED = ("n", "i_s", "rs")


def extract_values(sweep: Sweep, kind: str, **kw) -> dict[str, float] | None:
    """The extractor's values (and stderrs) as plain floats, or None on failure."""
    try:
        if kind == "mosfet":
            p = extract_mosfet(sweep, sensitivity=kw.pop("sensitivity", False), **kw)
            out = {"vth": p.vth.value, "beta": p.beta.value, "kp_wl": p.kp_wl.value,
                   "lambda": p.lambda_.value if p.lambda_ else math.nan,
                   "rds_on": p.rds_on.value if p.rds_on else math.nan}
            se = {"vth": p.vth.stderr, "beta": p.beta.stderr, "kp_wl": p.kp_wl.stderr,
                  "lambda": p.lambda_.stderr if p.lambda_ else None,
                  "rds_on": p.rds_on.stderr if p.rds_on else None}
            out["_se"] = se
            out["_vth_spread"] = (p.sensitivity.spread if p.sensitivity is not None
                                  else None)
            out["_params"] = p
            return out
        kw.pop("sensitivity", None)
        p = extract_diode(sweep, **kw)
        out = {"n": p.n.value, "i_s": p.i_s.value,
               "rs": p.rs.value if p.rs is not None else math.nan}
        out["_se"] = {"n": p.n.stderr, "i_s": p.i_s.stderr,
                      "rs": p.rs.stderr if p.rs is not None else None}
        out["_params"] = p
        return out
    except (FitError, ValueError, ZeroDivisionError, FloatingPointError):
        return None


def spread_grid(sweep: Sweep, kind: str, lsb_ma: float) -> dict[str, float]:
    """Max - min of each parameter over plausible fit-range choices.

    MOSFET: 5 slice voltages across the upper half of the common measured
    span (vth_sensitivity's choice) x saturation margins 0.3/0.5/0.8 V.
    Diode: lower current cut 5/10/20 LSB x upper cut 100/80/60% of the
    largest current. Choices the extractor rejects are skipped.
    """
    vals: dict[str, list[float]] = {}
    if kind == "mosfet":
        from ..dataset import family_of
        fam = family_of(sweep)
        lo, hi = fam.common_v_span()
        if not hi > lo:
            return {}
        for v_slice in np.linspace(lo + 0.5 * (hi - lo), hi, 5):
            for margin in (0.3, 0.5, 0.8):
                r = extract_values(sweep, kind, vds_slice=float(v_slice),
                                   saturation_margin_v=margin)
                if r is None:
                    continue
                for k in MOSFET_REPORTED:
                    if math.isfinite(r[k]):
                        vals.setdefault(k, []).append(r[k])
    else:
        i_max = max((r.i_ma for r in sweep.rows if r.valid), default=0.0)
        for lo_lsb in (5.0, 10.0, 20.0):
            for frac in (1.0, 0.8, 0.6):
                r = extract_values(sweep, kind,
                                   i_window_ma=(lo_lsb * lsb_ma, frac * i_max + 1e-9))
                if r is None:
                    continue
                for k in DIODE_REPORTED:
                    if math.isfinite(r[k]):
                        vals.setdefault(k, []).append(r[k])
    return {k: (max(v) - min(v)) for k, v in vals.items() if len(v) >= 2}


def reference(sweep: Sweep, kind: str, lsb_ma: float) -> dict[str, ParamResult] | None:
    """The extractor on a measured sweep, with its spread: the dense reference,
    and the raw cross-check."""
    base = extract_values(sweep, kind, sensitivity=(kind == "mosfet"))
    if base is None:
        return None
    spreads = spread_grid(sweep, kind, lsb_ma)
    out = {}
    names = MOSFET_REPORTED if kind == "mosfet" else DIODE_REPORTED
    for k in names:
        if not math.isfinite(base[k]):
            continue
        sp = spreads.get(k)
        if k == "vth" and base.get("_vth_spread") is not None:
            sp = max(sp or 0.0, base["_vth_spread"])
        out[k] = ParamResult(k, base[k], base["_se"].get(k), sp)
    return out


# --------------------------------------------------------------------------
# Linearisation of the extractor, for design
# --------------------------------------------------------------------------

def linearise(sweep: Sweep, grid: DenseGrid, kind: str,
              names: tuple[str, ...]) -> np.ndarray | None:
    """d(parameter)/d(curve value at each grid point), rows in ``names``.

    Derived by hand from what the extractor does on this sweep -- which
    points entered the slice fit and each lambda fit, read back from the fits
    it returns -- and checked against finite differences of the real
    extractor in ``tests/test_adaptive_estimate.py``, so the two cannot
    quietly diverge. Used only to choose points, never to report them.
    """
    r = extract_values(sweep, kind)
    if r is None:
        return None
    n = grid.code.size
    if kind == "diode":
        p = r["_params"]
        v = np.array([row.v_dut for row in sweep.rows])
        i_a = np.array([row.i_ma for row in sweep.rows]) / 1000.0
        floor = I_FLOOR_LSB * 3.3 / 4095 / 20.0
        used = (i_a > floor) & (v > 0.0)
        D = np.column_stack([np.log(i_a[used]), np.ones(int(used.sum())), i_a[used]])
        Gabc = np.zeros((3, n))
        Gabc[:, used] = np.linalg.pinv(D)
        a, b = p.n.value * p.vt_used, -p.n.value * p.vt_used * math.log(p.i_s.value)
        i_s = p.i_s.value
        rows = {"n": np.array([1.0 / p.vt_used, 0.0, 0.0]),
                "i_s": np.array([i_s * b / (a * a), -i_s / a, 0.0]),
                "rs": np.array([0.0, 0.0, 1.0])}
        return np.vstack([rows[k] @ Gabc for k in names])

    p = r["_params"]
    v_slice = p.vds_slice
    vgs_rows = np.array([row.vgs_set_v for row in sweep.rows])
    v_rows = np.array([row.v_dut for row in sweep.rows])
    i_rows = np.array([row.i_ma for row in sweep.rows])

    # V_th and beta_raw: sqrt(I) at the slice against V_GS, OLS.
    x = np.asarray(p.vth_fit.x, float)
    dy = np.zeros((x.size, n))
    yv = np.zeros(x.size)
    for j, g in enumerate(x):
        idx = np.where(np.isclose(vgs_rows, g))[0]
        idx = idx[np.argsort(v_rows[idx])]
        vv = v_rows[idx]
        k = int(np.clip(np.searchsorted(vv, v_slice), 1, vv.size - 1))
        lo, hi = idx[k - 1], idx[k]
        w = (v_slice - v_rows[lo]) / (v_rows[hi] - v_rows[lo]) if v_rows[hi] != v_rows[lo] else 0.0
        i_a = max(((1 - w) * i_rows[lo] + w * i_rows[hi]) / 1000.0, 1e-15)
        yv[j] = math.sqrt(i_a)
        d = 1.0 / (2.0 * math.sqrt(i_a)) / 1000.0
        dy[j, lo] += (1 - w) * d
        dy[j, hi] += w * d
    xm = x.mean()
    sxx = float(np.sum((x - xm) ** 2))
    m = float(np.sum((x - xm) * yv) / sxx)
    b = yv.mean() - m * xm
    dm = ((x - xm) / sxx) @ dy
    db = (1.0 / x.size - xm * (x - xm) / sxx) @ dy
    dvth = -db / m + b * dm / (m * m)
    dbeta_raw = 2.0 * m * dm

    # lambda: per-curve I = s V + b0, lambda_c = s / b0, combined by the
    # extractor's inverse-variance weights. The weights move with the data
    # (through each fit's residual variance), and when the curves disagree --
    # exactly the mismatched case -- that term dominates, so it is included:
    #   var_c = sigma2 * F(s, b0),  F = [1/Sxx + s^2 c1 / b0^2] / b0^2,
    #   c1 = 1/n + Vbar^2/Sxx,  d(sigma2)/dI_i = 2 e_i / (n - 2).
    lam_c, w_c, dlam_c, dw_c = [], [], [], []
    for g, lf in p.lambda_fits.items():
        idx = np.where(np.isclose(vgs_rows, g))[0]
        sel = idx[np.isin(v_rows[idx], lf.x)]
        vv, ii = v_rows[sel], i_rows[sel]
        nc = vv.size
        vm = vv.mean(); svv = float(np.sum((vv - vm) ** 2))
        s_ = float(np.sum((vv - vm) * ii) / svv); b0 = ii.mean() - s_ * vm
        ds = np.zeros(n); dbb = np.zeros(n)
        ds[sel] = (vv - vm) / svv
        dbb[sel] = 1.0 / nc - vm * (vv - vm) / svv
        lam_c.append(s_ / b0)
        dlam_c.append((ds * b0 - s_ * dbb) / (b0 * b0))
        e = ii - (b0 + s_ * vv)
        sigma2 = float(e @ e) / max(nc - 2, 1)
        dsig = np.zeros(n); dsig[sel] = 2.0 * e / max(nc - 2, 1)
        c1 = 1.0 / nc + vm * vm / svv
        F = (1.0 / svv + s_ * s_ * c1 / (b0 * b0)) / (b0 * b0)
        dF_ds = 2.0 * s_ * c1 / b0 ** 4
        dF_db = -2.0 / (b0 ** 3 * svv) - 4.0 * s_ * s_ * c1 / b0 ** 5
        var = sigma2 * F
        dvar = dsig * F + sigma2 * (dF_ds * ds + dF_db * dbb)
        if var > 0.0 and math.isfinite(var):
            w_c.append(1.0 / var); dw_c.append(-dvar / (var * var))
        else:
            w_c.append(math.nan); dw_c.append(np.zeros(n))
    if lam_c:
        lam_c_a = np.array(lam_c)
        w = np.array(w_c)
        if np.all(np.isfinite(w)) and np.all(w > 0):
            lam = float(np.sum(w * lam_c_a) / w.sum())
            dlam = sum(w[k] * dlam_c[k] + (lam_c_a[k] - lam) * dw_c[k]
                       for k in range(w.size)) / w.sum()
        else:
            lam = float(lam_c_a.mean())
            dlam = sum(dlam_c) / len(dlam_c)
    else:
        dlam = np.zeros(n); lam = 0.0
    f = 1.0 + lam * v_slice
    beta_raw = p.beta_raw.value
    dbeta = dbeta_raw / f - beta_raw * v_slice * dlam / (f * f)
    rows = {"vth": dvth, "beta": dbeta, "kp_wl": 2.0 * dbeta, "lambda": dlam}
    return np.vstack([rows[k] for k in names])


# --------------------------------------------------------------------------
# The stopping assessment
# --------------------------------------------------------------------------

def _target_abs(kind_t, value):
    kind, t = kind_t
    return t * abs(value) if kind == "rel" else t


STAGES = ("mean", "spread", "full")


def assess(gp: PhysGP, oracle: OracleBase, points: list[Point], kind: str,
           targets: dict, *, n_dense: int, r_ser: float, rng: np.random.Generator,
           n_samples: int = 64, stage: str = "full",
           lin_sd: dict[str, float] | None = None
           ) -> tuple[Assessment, DenseGrid, Sweep]:
    """The pushforward estimate, in stages of increasing cost.

    ``mean``    values only: the extractor on the posterior-mean sweep
    ``spread``  + the fit-range spread (a property of the curve, ~15 extractor
                calls) and, for the MOSFET, the extractor's own V_th grid
    ``full``    + the stderr over posterior samples and the raw cross-check

    The adaptive loop runs ``spread`` every round and ``full`` only when the
    spreads and the linearised stderr (``lin_sd``) already meet target, so the
    expensive check runs only when it might say stop. The stopping rule is
    decided on ``full`` alone; the cheaper stages only decide whether to ask.
    """
    if stage not in STAGES:
        raise ValueError(f"unknown stage {stage!r}")
    lsb = oracle.fe.i_lsb_ma
    i_hi = max((p.row.i_meas_ma for p in points if p.row.valid), default=1.0)
    grid = dense_grid(gp, oracle, kind, n_dense, r_ser, i_hi * 1.02)
    grid.factors = gp.factors(grid.X)
    mean_vals = (gp.predict(grid.factors)[0] if kind == "mosfet" else grid.v)
    mean_sweep = grid_sweep(oracle, grid, mean_vals, kind)
    want_sens = kind == "mosfet" and stage != "mean"
    base = extract_values(mean_sweep, kind, sensitivity=want_sens)
    full = stage == "full"
    names = tuple(targets)
    if base is None:
        return (Assessment({}, full=full,
                           blocking=["extractor failed on the posterior mean"]),
                grid, mean_sweep)

    params = {k: ParamResult(k, base[k], None, None,
                             target=_target_abs(targets[k], base[k]) if k in targets else None)
              for k in (MOSFET_REPORTED if kind == "mosfet" else DIODE_REPORTED)
              if math.isfinite(base[k])}
    a = Assessment(params, full=full)
    if stage == "mean":
        return a, grid, mean_sweep

    # spread: the fit-range grid on the posterior mean
    spreads = spread_grid(mean_sweep, kind, lsb)
    for k, pr in params.items():
        pr.spread = spreads.get(k)
        if k == "vth" and base.get("_vth_spread") is not None:
            pr.spread = max(pr.spread or 0.0, base["_vth_spread"])
    if stage == "spread":
        if lin_sd:
            for k, pr in params.items():
                if k in lin_sd:
                    pr.stderr = lin_sd[k]       # provisional, linearised
        return a, grid, mean_sweep

    # stderr: the extractor over posterior samples
    samples = gp.sample(grid.factors, n_samples, rng)
    got: dict[str, list[float]] = {}
    for smp in samples:
        r = extract_values(grid_sweep(oracle, grid, smp, kind), kind)
        if r is None:
            a.sample_failures += 1
            continue
        for k in params:
            if math.isfinite(r[k]):
                got.setdefault(k, []).append(r[k])
    a.n_samples = n_samples
    for k, pr in params.items():
        if len(got.get(k, [])) >= 2:
            pr.stderr = float(np.std(got[k], ddof=1))

    # raw cross-check: the extractor on the measured points themselves
    raw = extract_values(oracle.as_sweep(points), kind)
    if raw is not None:
        for k, pr in params.items():
            if math.isfinite(raw.get(k, math.nan)):
                pr.raw_value = raw[k]
                pr.raw_stderr = raw["_se"].get(k)

    # the rule
    if a.sample_failures > 0.1 * n_samples:
        a.blocking.append(f"extractor failed on {a.sample_failures}/{n_samples} samples")
    for k in names:
        pr = params.get(k)
        if pr is None:
            a.blocking.append(f"{k}: not extracted")
            continue
        if pr.stderr is None or pr.spread is None:
            a.blocking.append(f"{k}: no stderr or spread yet")
        elif not pr.meets_target:
            a.blocking.append(f"{k}: stderr {pr.stderr:.3g} / half-spread "
                              f"{pr.spread / 2:.3g} above target {pr.target:.3g}")
        ok = pr.crosscheck_ok
        if ok is None:
            a.blocking.append(f"{k}: raw-point cross-check unavailable")
        elif not ok:
            a.blocking.append(f"{k}: GP {pr.value:.5g} vs raw {pr.raw_value:.5g} "
                              f"disagree by more than 3 sigma")
    return a, grid, mean_sweep
