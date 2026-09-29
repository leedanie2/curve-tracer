"""Diode parameter extraction, per blueprint §5.

Fit ``I = I_S (exp(V / n V_T) - 1)`` on a semilog plot: the slope gives the
ideality factor ``n``, the intercept gives ``I_S``, and series resistance
shows as a high-current roll-off away from that ideal line.

**Series resistance is not a nuisance to be fitted around.** The obvious
approach -- pick a window below the roll-off and fit the straight part --
fails quietly, because there is no clean boundary. ``R_s`` starts bending the
curve as soon as ``I R_s`` is an appreciable fraction of ``n V_T``, which for
a 0.6 ohm bulk resistance is already a few milliamps, well inside any window
wide enough to fit. Fitting there returns a flattened slope, and so an
inflated ``n`` and an inflated ``I_S``, with an excellent R^2. Measured
against the simulator with known values, a windowed fit of a 1.75-ideality
diode returned n = 1.85 and I_S nearly 2x high. Alternating a windowed fit
with an ``R_s`` correction improves that but does not fix it: it converges
slowly and to a biased point, since each half uses the other's error.

``R_s`` is therefore fitted **jointly** with ``n`` and ``I_S``, and no
iteration is needed because the model is exactly linear in the right basis.
Inverting the diode law for the terminal voltage,

    V = n V_T ln(I/I_S + 1) + I R_s

and, wherever ``I >> I_S`` -- true by six decades for anything range 1 can
resolve -- that is

    V = a ln(I) + b + c I,    a = n V_T,  b = -n V_T ln(I_S),  c = R_s

an ordinary three-parameter least squares in ``ln(I)``, ``1`` and ``I``, with
``n = a / V_T``, ``I_S = exp(-b/a)`` and ``R_s = c``. One solve, no window to
choose, every resolvable point used, and a full covariance matrix to
propagate. The regression is of measured voltage on functions of measured
current, which is also the right way round: ``V`` is the Kelvin-sensed
quantity.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..csvio import Sweep
from ..dataset import family_of
from ..recompute import Calibration, recompute
from .common import Estimate, FitError, FitRange, LinearFit, fit_line

__all__ = ["DiodeParams", "extract_diode"]

#: Thermal voltage at 300 K, matching the firmware model's constant.
VT_300K = 0.02585

#: Points below this many current LSBs are treated as unresolved.
I_FLOOR_LSB = 5.0

#: R_s is reported only when it exceeds this many standard errors. Below
#: that it is indistinguishable from fit scatter, and quoting it would be
#: inventing a number.
RS_SIGNIFICANCE = 3.0


@dataclass(frozen=True)
class DiodeParams:
    n: Estimate
    i_s: Estimate
    rs: Estimate | None
    fit: LinearFit
    vt_used: float
    device: str = "unknown"
    simulated: bool = False
    rs_points: int = 0
    iterations: int = 0
    converged: bool = True
    notes: tuple[str, ...] = field(default_factory=tuple)

    def describe(self) -> str:
        out = [
            "Diode parameters",
            f"  device : {self.device}"
            + ("   [SIMULATED -- not a bench measurement]"
               if self.simulated else ""),
            "",
            f"  n      = {self.n}",
            f"  I_S    = {self.i_s}",
        ]
        if self.rs is not None:
            out.append(f"  R_s    = {self.rs}"
                       f"    de-embedded over {self.rs_points} points, "
                       f"{self.iterations} iterations")
        else:
            out.append("  R_s    : not resolved -- no departure from the "
                       "ideal line above fit scatter")
        out += [
            "",
            f"  semilog fit (V_T = {self.vt_used:.5f} V at 300 K)",
            self.fit.describe("    "),
        ]
        if not self.converged:
            out.append("    WARNING: the R_s iteration did not converge")
        if self.notes:
            out.append("")
            out.append("  notes")
            out += [f"    - {note}" for note in self.notes]
        return "\n".join(out)


def extract_diode(
    sweep: Sweep,
    *,
    i_window_ma: tuple[float, float] | None = None,
    vt: float = VT_300K,
    refine_rs: bool = True,
    max_iter: int = 40,
    tol_ohm: float = 1e-6,
) -> DiodeParams:
    """Extract ``n``, ``I_S`` and ``R_s``.

    By default every point carrying resolvable current is used, with ``R_s``
    de-embedded iteratively (see the module docstring). ``i_window_ma``
    restricts the fit to a current window instead, and ``refine_rs=False``
    performs a plain semilog fit with no de-embedding -- both are available
    for comparison, and both are recorded in the returned fit range so a
    report says which was used.
    """
    if not sweep.recomputed:
        sweep = recompute(sweep)

    cal = Calibration.from_sweep(sweep)
    fam = family_of(sweep)
    notes: list[str] = []

    rows = [r for curve in fam for r in curve.rows]
    if not rows:
        raise FitError("no valid rows in the sweep")

    i_floor_ma = I_FLOOR_LSB * cal.i_lsb_ma
    v_all = np.array([r.v_dut for r in rows], dtype=float)
    i_ma_all = np.array([r.i_ma for r in rows], dtype=float)

    usable = (i_ma_all > i_floor_ma) & (v_all > 0.0)
    if int(usable.sum()) < 4:
        raise FitError(
            f"only {int(usable.sum())} points carry resolvable current "
            f"(floor {i_floor_ma:.4f} mA); raise vds_max so the diode conducts"
        )

    v, i_ma = v_all[usable], i_ma_all[usable]
    order = np.argsort(v)
    v, i_ma = v[order], i_ma[order]
    n_available = int(v.size)
    i_a = i_ma / 1000.0
    log_i = np.log10(i_a)

    excluded: list[str] = []
    if i_window_ma is not None:
        lo_ma, hi_ma = i_window_ma
        mask = (i_ma >= lo_ma) & (i_ma <= hi_ma)
        rule = f"caller-supplied current window {lo_ma:.4g} .. {hi_ma:.4g} mA"
        origin = "explicit"
        dropped = int((~mask).sum())
        if dropped:
            excluded.append(f"{dropped} points outside the window")
    else:
        mask = np.ones_like(v, dtype=bool)
        below = int(np.sum(~usable & (i_ma_all <= i_floor_ma)))
        rule = (f"every point carrying resolvable current "
                f"(I >= {I_FLOOR_LSB:.0f} current LSB = {i_floor_ma:.4f} mA)")
        origin = "default"
        if below:
            excluded.append(f"{below} points below {i_floor_ma:.4f} mA "
                            f"(unresolved on range 1)")

    if int(mask.sum()) < 4:
        raise FitError(
            f"{int(mask.sum())} points left after range selection; need at "
            f"least 4. Increase n, or widen i_window_ma"
        )

    vw, iw_a, logw = v[mask], i_a[mask], log_i[mask]

    # -- the joint solve ---------------------------------------------------
    a, b, c, cov = _solve_diode(vw, iw_a, include_rs=refine_rs)

    if a <= 0.0:
        raise FitError(
            "the fitted n*V_T is not positive; these points are not on a "
            "diode exponential"
        )

    rule_full = rule + (
        "; n, I_S and R_s solved jointly as V = a*ln(I) + b + c*I"
        if refine_rs else
        "; n and I_S only, R_s held at zero (refine_rs=False)"
    )
    fit_range = FitRange(
        rule=rule_full, origin=origin,
        lo=float(vw.min()), hi=float(vw.max()),
        n_used=int(mask.sum()), n_available=n_available,
        excluded=tuple(excluded), quantity="V (V_AK)",
    )

    # A semilog LinearFit is still reported, on R_s-corrected junction
    # voltage, because that is the plot a reader checks the fit against.
    lf = fit_line(vw - iw_a * c, logw, fit_range=fit_range,
                  x_unit="V", y_unit="log10(A)")

    var_a, var_b, var_c, cov_ab = cov

    n_value = a / vt
    n_err = math.sqrt(var_a) / vt if var_a >= 0.0 else None

    # I_S = exp(-b/a); both parameters are correlated, so carry the covariance.
    is_value = math.exp(-b / a)
    d_da = is_value * b / (a * a)
    d_db = -is_value / a
    var_is = (d_da ** 2 * var_a + d_db ** 2 * var_b + 2.0 * d_da * d_db * cov_ab)
    is_err = math.sqrt(var_is) if var_is > 0.0 else None

    rs_estimate: Estimate | None = None
    rs_points = int(vw.size)
    rs_err = math.sqrt(var_c) if var_c > 0.0 else None
    if refine_rs and c > 0.0:
        if rs_err is None or c > RS_SIGNIFICANCE * rs_err:
            rs_estimate = Estimate(c, rs_err, "ohm")
        else:
            notes.append(
                f"an R_s of {c:.4g} ohm was fitted but its standard error is "
                f"{rs_err:.2g} ohm, under {RS_SIGNIFICANCE:g} sigma; reported "
                f"as unresolved rather than quoted"
            )
    elif refine_rs:
        notes.append(
            "the fitted R_s is not positive, so it is unresolved at these "
            "currents; sweep higher if it is wanted"
        )

    return DiodeParams(
        n=Estimate(n_value, n_err, ""),
        i_s=Estimate(is_value, is_err, "A"),
        rs=rs_estimate, rs_points=rs_points,
        fit=lf, vt_used=vt,
        iterations=1, converged=True,
        device=sweep.meta.device, simulated=sweep.meta.is_simulated,
        notes=tuple(notes),
    )


def _solve_diode(v: np.ndarray, i_a: np.ndarray, *, include_rs: bool
                 ) -> tuple[float, float, float, tuple[float, float, float,
                                                       float]]:
    """Least squares for ``V = a ln(I) + b + c I``.

    Returns ``(a, b, c)`` and ``(var_a, var_b, var_c, cov_ab)``. The a-b
    covariance is kept because ``I_S = exp(-b/a)`` depends on both and they
    are strongly correlated; ignoring it understates the error on ``I_S`` by
    a large factor.
    """
    columns = [np.log(i_a), np.ones_like(i_a)]
    if include_rs:
        columns.append(i_a)
    design = np.column_stack(columns)

    dof = design.shape[0] - design.shape[1]
    if dof <= 0:
        raise FitError(
            f"{design.shape[0]} points cannot determine "
            f"{design.shape[1]} parameters"
        )

    solution, *_ = np.linalg.lstsq(design, v, rcond=None)
    residual = v - design @ solution
    s2 = float(residual @ residual) / dof

    try:
        xtx_inv = np.linalg.inv(design.T @ design)
    except np.linalg.LinAlgError as exc:
        raise FitError(f"the diode design matrix is singular: {exc}") from None
    covariance = s2 * xtx_inv

    a, b = float(solution[0]), float(solution[1])
    c = float(solution[2]) if include_rs else 0.0
    var_c = float(covariance[2, 2]) if include_rs else 0.0

    return a, b, c, (float(covariance[0, 0]), float(covariance[1, 1]),
                     var_c, float(covariance[0, 1]))
