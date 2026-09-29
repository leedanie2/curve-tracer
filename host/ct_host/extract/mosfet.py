"""MOSFET parameter extraction, per blueprint §5.

Conventions, stated because they are the commonest source of a silent factor
of two in a SPICE card:

    I_D = beta * (V_GS - V_th)^2                    <- beta, what the fit gives
    I_D = (KP/2) * (W/L) * (V_GS - V_th)^2          <- SPICE Level 1

so ``kp_wl = 2 * beta``. Both are reported. ``spice.py`` emits ``KP`` from
``kp_wl``.

The second correction is channel-length modulation. Saturation current carries
a ``(1 + lambda*V_DS)`` factor, so a sqrt-fit performed at a slice voltage
returns ``beta_fit = beta_true * (1 + lambda * V_slice)``. At a 7 V slice with
lambda = 0.012 that is 8.4% -- an order of magnitude above the fit's own
standard error, and one-signed, so it reads as a good measurement of the wrong
quantity. ``beta`` below is de-embedded using the fitted lambda; the raw value
is kept as ``beta_raw``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..csvio import Sweep
from ..dataset import Curve, Family, family_of
from ..recompute import Calibration, recompute
from .common import Estimate, FitError, FitRange, LinearFit, fit_line

__all__ = ["MosfetParams", "Subthreshold", "extract_mosfet", "vth_sensitivity"]


#: Points below this many current LSBs are treated as unresolved.
I_FLOOR_LSB = 5.0

#: Default margin past the saturation knee, in volts.
SATURATION_MARGIN_V = 0.5


@dataclass(frozen=True)
class Subthreshold:
    """Weak-inversion slope, or a statement of why it is not available.

    Blueprint §5: "Subthreshold slope needs the low current range -- this is
    the measurement that justifies building three ranges instead of one." On
    range 1 this is expected to be unavailable, and that is a result rather
    than a gap: the current LSB is ~40 uA where subthreshold currents are
    nanoamps, so they quantise to exactly zero.
    """

    available: bool
    reason: str = ""
    mv_per_decade: Estimate | None = None
    n_factor: Estimate | None = None
    fit: LinearFit | None = None

    def describe(self, indent: str = "  ") -> str:
        if not self.available:
            return f"{indent}unavailable: {self.reason}"
        lines = [f"{indent}slope   : {self.mv_per_decade}"]
        if self.n_factor is not None:
            lines.append(f"{indent}n       : {self.n_factor}")
        lines.append(f"{indent}(theoretical floor is 59.6 mV/dec at 300 K)")
        return "\n".join(lines)


@dataclass(frozen=True)
class MosfetParams:
    """Extracted parameters, each with the range that produced it."""

    vth: Estimate
    beta: Estimate                 # de-embedded, I_D = beta (Vgs-Vth)^2
    beta_raw: Estimate             # as fitted, still carrying (1+lambda*Vds)
    kp_wl: Estimate                # = 2*beta, SPICE KP*(W/L)
    lambda_: Estimate | None
    va: Estimate | None
    rds_on: Estimate | None
    subthreshold: Subthreshold
    vds_slice: float
    vth_fit: LinearFit
    lambda_fits: dict[float, LinearFit] = field(default_factory=dict)
    rds_on_fit: LinearFit | None = None
    sensitivity: "SensitivityResult | None" = None
    device: str = "unknown"
    simulated: bool = False
    notes: tuple[str, ...] = ()

    @property
    def deembed_factor(self) -> float:
        return self.beta_raw.value / self.beta.value if self.beta.value else 1.0

    def describe(self) -> str:
        out: list[str] = []
        out.append("MOSFET parameters")
        out.append(f"  device : {self.device}"
                   + ("   [SIMULATED -- not a bench measurement]"
                      if self.simulated else ""))
        out.append("")

        out.append(f"  V_th   = {self.vth}")
        if self.sensitivity is not None and self.sensitivity.spread is not None:
            s = self.sensitivity
            ratio = (s.spread / self.vth.stderr
                     if self.vth.stderr not in (None, 0.0) else None)
            out.append(
                f"           fit standard error   ± {_g(self.vth.stderr)} V"
            )
            out.append(
                f"           fit-range spread     ± {_g(s.spread / 2)} V "
                f"(full spread {_g(s.spread)} V over {s.n_choices} choices)"
            )
            if ratio is not None:
                out.append(f"           {_dominance_note(ratio)}")
        out.append("")

        out.append(f"  beta   = {self.beta}          I_D = beta (V_GS-V_th)^2")
        out.append(f"  KP*W/L = {self.kp_wl}          SPICE Level 1, = 2*beta")
        out.append(f"           de-embedded from {_g(self.beta_raw.value)} "
                   f"by /(1 + lambda*{self.vds_slice:.3f}) "
                   f"= /{self.deembed_factor:.4f} "
                   f"({(self.deembed_factor - 1) * 100:+.1f}%)")
        out.append("")

        if self.lambda_ is not None:
            out.append(f"  lambda = {self.lambda_}")
            out.append(f"  V_A    = {self.va}")
        else:
            out.append("  lambda : not extracted (no curve had enough "
                       "saturation points)")
        out.append("")

        if self.rds_on is not None:
            out.append(f"  R_DS(on) = {self.rds_on}")
            if self.rds_on_fit is not None:
                out.append(self.rds_on_fit.range.describe("             "))
        else:
            out.append("  R_DS(on) : not extracted (no triode-region points)")
        out.append("")

        out.append("  subthreshold slope")
        out.append(self.subthreshold.describe("    "))
        out.append("")

        out.append(f"  V_th fit, at a measured V_DS slice of "
                   f"{self.vds_slice:.4f} V")
        out.append(self.vth_fit.describe("    "))

        if self.lambda_fits:
            out.append("")
            out.append("  lambda fits, per gate step")
            for vgs, lf in sorted(self.lambda_fits.items()):
                lam = lf.slope.value / lf.intercept.value
                out.append(f"    V_GS = {vgs:.3f} V : lambda = {lam:.5f} /V, "
                           f"{lf.range.n_used} pts, R^2 = {lf.r2:.5f}")

        if self.notes:
            out.append("")
            out.append("  notes")
            for note in self.notes:
                out.append(f"    - {note}")

        return "\n".join(out)


def _g(x: float | None) -> str:
    return "--" if x is None else f"{x:.5g}"


def _dominance_note(ratio: float) -> str:
    if ratio >= 3.0:
        return (f"fit-range choice dominates: the spread is {ratio:.0f}x the "
                f"fit error, so quote the spread")
    if ratio <= 0.5:
        return ("measurement noise dominates the fit-range choice")
    return (f"comparable: spread is {ratio:.1f}x the fit error; neither alone "
            f"is the uncertainty")


# --------------------------------------------------------------------------
# Sensitivity
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class SensitivityResult:
    """V_th recomputed across plausible fit-range choices.

    On noiseless simulator data this spread is ~10x the fit's own standard
    error. On bench data it is expected to dominate outright. It is surfaced
    in :meth:`MosfetParams.describe` rather than left behind an API call,
    because a reader who does not know to ask is exactly the reader who will
    otherwise quote the fit error as the uncertainty.
    """

    table: "object"                # pandas.DataFrame
    spread: float | None
    n_choices: int
    best: float
    worst: float

    def describe(self) -> str:
        if self.spread is None:
            return "  sensitivity: too few viable fit ranges to compare"
        return (
            f"  V_th over {self.n_choices} fit-range choices: "
            f"{self.best:.5f} .. {self.worst:.5f} V "
            f"(spread {self.spread * 1000:.2f} mV)"
        )


def vth_sensitivity(sweep: Sweep, *, slices: int = 5,
                    saturation_margin_v: float = SATURATION_MARGIN_V):
    """V_th across a grid of slice voltages and gate-point subsets.

    Returns a ``pandas.DataFrame``, one row per choice. The point is to make
    the range-selection uncertainty a number that can be compared against the
    fit's standard error rather than an unstated judgement.
    """
    import pandas as pd

    fam = _family(sweep)
    lo, hi = fam.common_v_span()
    if not math.isfinite(lo) or hi <= lo:
        return pd.DataFrame(columns=["vds_slice", "drop_low", "drop_high",
                                     "n_points", "vgs_lo", "vgs_hi",
                                     "vth", "stderr"])

    candidates = np.linspace(lo + 0.5 * (hi - lo), hi, max(2, slices))
    records: list[dict[str, float]] = []

    for v_slice in candidates:
        points = fam.slice_at(float(v_slice))
        if len(points) < 3:
            continue
        for drop_low in (0, 1, 2):
            for drop_high in (0, 1):
                kept = points[drop_low: len(points) - drop_high or None]
                if len(kept) < 3:
                    continue
                try:
                    fit = _sqrt_fit(kept)
                except FitError:
                    continue
                records.append({
                    "vds_slice": float(v_slice),
                    "drop_low": drop_low,
                    "drop_high": drop_high,
                    "n_points": len(kept),
                    "vgs_lo": kept[0][0],
                    "vgs_hi": kept[-1][0],
                    "vth": fit.x_intercept.value,
                    "stderr": (fit.x_intercept.stderr
                               if fit.x_intercept.stderr is not None
                               else float("nan")),
                })

    return pd.DataFrame.from_records(records)


def _sensitivity_result(sweep: Sweep, **kw) -> SensitivityResult | None:
    table = vth_sensitivity(sweep, **kw)
    if len(table) < 2:
        return None
    values = table["vth"].to_numpy(dtype=float)
    values = values[np.isfinite(values)]
    if values.size < 2:
        return None
    return SensitivityResult(
        table=table,
        spread=float(values.max() - values.min()),
        n_choices=int(values.size),
        best=float(values.min()),
        worst=float(values.max()),
    )


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------

def _family(sweep: Sweep) -> Family:
    if not sweep.recomputed:
        sweep = recompute(sweep)
    return family_of(sweep)


def _sqrt_fit(points: list[tuple[float, float]],
              fit_range: FitRange | None = None) -> LinearFit:
    """Least squares on sqrt(I_D) against V_GS. Current in mA, I in A."""
    vgs = np.array([p[0] for p in points], dtype=float)
    root_i = np.sqrt(np.array([p[1] for p in points], dtype=float) / 1000.0)
    return fit_line(vgs, root_i, fit_range=fit_range,
                    x_unit="V", y_unit="sqrt(A)")


def extract_mosfet(
    sweep: Sweep,
    *,
    vds_slice: float | None = None,
    vgs_range: tuple[float, float] | None = None,
    saturation_margin_v: float = SATURATION_MARGIN_V,
    deembed_lambda: bool = True,
    sensitivity: bool = True,
) -> MosfetParams:
    """Extract V_th, beta, lambda, R_DS(on) and the subthreshold slope.

    ``vds_slice`` is a **measured** drain voltage. Left ``None`` it defaults
    to the highest measured voltage every curve reached, and the rule is
    recorded in the returned fit range.

    ``vgs_range`` restricts the gate steps entering the threshold fit. Left
    ``None``, a two-pass rule applies: fit once to get a provisional V_th,
    then keep only the steps that are actually in saturation at the slice,
    ``V_DS >= V_GS - V_th + margin``, and refit. That iteration is stated in
    the fit range rather than being a hidden heuristic.
    """
    if not sweep.recomputed:
        sweep = recompute(sweep)

    fam = family_of(sweep)
    cal = Calibration.from_sweep(sweep)
    notes: list[str] = []

    if len(fam) < 3:
        raise FitError(
            f"a threshold fit needs at least 3 gate steps, this sweep has "
            f"{len(fam)}; set vgs_list to a list, not a single value"
        )

    # -- the slice ---------------------------------------------------------
    lo, hi = fam.common_v_span()
    if hi <= lo:
        raise FitError(
            "no measured drain voltage is common to every curve: the series "
            "drop has spread the curves apart further than the ramp covered "
            "(see §3.4). Raise vds_max or narrow vgs_list."
        )

    if vds_slice is None:
        v_slice = hi
        slice_rule = (f"highest measured V_DS reached by every curve "
                      f"(common span {lo:.3f}..{hi:.3f} V)")
        slice_origin = "default"
    else:
        v_slice = float(vds_slice)
        slice_rule = "caller-supplied slice voltage"
        slice_origin = "explicit"
        if not (lo <= v_slice <= hi):
            notes.append(
                f"requested slice {v_slice:.3f} V lies outside the span common "
                f"to all curves ({lo:.3f}..{hi:.3f} V); curves that did not "
                f"reach it are excluded rather than extrapolated"
            )

    points_all = fam.slice_at(v_slice)
    if len(points_all) < 3:
        raise FitError(
            f"only {len(points_all)} curves reach {v_slice:.3f} V; "
            f"need at least 3 for a threshold fit"
        )

    # -- which gate steps --------------------------------------------------
    i_floor_ma = I_FLOOR_LSB * cal.i_lsb_ma
    excluded: list[str] = []

    kept = []
    for vgs, i_ma in points_all:
        if i_ma < i_floor_ma:
            excluded.append(
                f"V_GS = {vgs:.3f} V: I_D = {i_ma:.4f} mA is below "
                f"{I_FLOOR_LSB:.0f} current LSB ({i_floor_ma:.4f} mA)"
            )
            continue
        kept.append((vgs, i_ma))

    if vgs_range is not None:
        g_lo, g_hi = vgs_range
        before = list(kept)
        kept = [(v, i) for v, i in kept if g_lo <= v <= g_hi]
        for v, _ in before:
            if not (g_lo <= v <= g_hi):
                excluded.append(f"V_GS = {v:.3f} V: outside the requested "
                                f"range {g_lo:.3f}..{g_hi:.3f} V")
        rule = (f"caller-supplied V_GS range {g_lo:.3f}..{g_hi:.3f} V, "
                f"and I_D >= {I_FLOOR_LSB:.0f} current LSB")
        origin = "explicit"
    else:
        if len(kept) < 3:
            raise FitError(
                f"only {len(kept)} gate steps carry resolvable current at "
                f"{v_slice:.3f} V (floor {i_floor_ma:.4f} mA)"
            )
        provisional = _sqrt_fit(kept)
        vth_guess = provisional.x_intercept.value
        in_saturation = [
            (v, i) for v, i in kept
            if v_slice >= (v - vth_guess) + saturation_margin_v
        ]
        if len(in_saturation) >= 3:
            saturated_vgs = {v for v, _ in in_saturation}
            for v, _ in kept:
                if v not in saturated_vgs:
                    excluded.append(
                        f"V_GS = {v:.3f} V: V_DS {v_slice:.3f} V is below "
                        f"V_ov + {saturation_margin_v:.2f} V "
                        f"= {(v - vth_guess) + saturation_margin_v:.3f} V, "
                        f"so the device is not in saturation at the slice"
                    )
            kept = in_saturation
            rule = (
                f"two-pass: fit all steps with I_D >= {I_FLOOR_LSB:.0f} "
                f"current LSB to get a provisional V_th = {vth_guess:.4f} V, "
                f"then keep steps satisfying "
                f"V_DS >= V_GS - V_th + {saturation_margin_v:.2f} V and refit"
            )
        else:
            rule = (
                f"all steps with I_D >= {I_FLOOR_LSB:.0f} current LSB; the "
                f"saturation filter (margin {saturation_margin_v:.2f} V) was "
                f"not applied because it would have left "
                f"{len(in_saturation)} points"
            )
            notes.append(
                "the saturation filter was skipped for want of points -- "
                "V_th may be biased by triode-region steps; raise vds_max"
            )
        origin = "default"

    if len(kept) < 3:
        raise FitError(f"{len(kept)} points left after range selection; "
                       f"need at least 3")

    fit_range = FitRange(
        rule=f"{slice_rule}; {rule}",
        origin=origin if slice_origin == "default" else "explicit",
        lo=kept[0][0], hi=kept[-1][0],
        n_used=len(kept), n_available=len(points_all),
        excluded=tuple(excluded), quantity="V (V_GS)",
    )
    vth_fit = _sqrt_fit(kept, fit_range)
    vth = vth_fit.x_intercept

    # -- lambda ------------------------------------------------------------
    lambda_est, lambda_fits = _extract_lambda(
        fam, vth.value, saturation_margin_v, i_floor_ma
    )
    if lambda_est is None:
        notes.append(
            "lambda could not be fitted, so beta is NOT de-embedded and "
            "remains inflated by (1 + lambda*V_DS)"
        )

    # -- beta --------------------------------------------------------------
    slope = vth_fit.slope
    beta_raw = Estimate(
        value=slope.value ** 2,
        stderr=(None if slope.stderr is None
                else 2.0 * abs(slope.value) * slope.stderr),
        unit="A/V^2",
    )

    if deembed_lambda and lambda_est is not None:
        factor = 1.0 + lambda_est.value * v_slice
        beta = beta_raw.scaled(1.0 / factor)
    else:
        beta = beta_raw

    kp_wl = beta.scaled(2.0)

    va = None
    if lambda_est is not None and lambda_est.value != 0.0:
        va_value = 1.0 / lambda_est.value
        va_err = (None if lambda_est.stderr is None
                  else abs(va_value ** 2 * lambda_est.stderr))
        va = Estimate(va_value, va_err, "V")

    # -- the rest ----------------------------------------------------------
    rds_on, rds_fit = _extract_rds_on(fam, vth.value, i_floor_ma)
    sub = _extract_subthreshold(fam, vth.value, cal)

    sens = _sensitivity_result(
        sweep, saturation_margin_v=saturation_margin_v
    ) if sensitivity else None

    if sens is not None and sens.spread is not None and vth.stderr:
        vth = Estimate(vth.value, vth.stderr, vth.unit, spread=sens.spread)

    return MosfetParams(
        vth=vth,
        beta=beta, beta_raw=beta_raw, kp_wl=kp_wl,
        lambda_=lambda_est, va=va,
        rds_on=rds_on, subthreshold=sub,
        vds_slice=v_slice,
        vth_fit=vth_fit, lambda_fits=lambda_fits, rds_on_fit=rds_fit,
        sensitivity=sens,
        device=sweep.meta.device, simulated=sweep.meta.is_simulated,
        notes=tuple(notes),
    )


def _extract_lambda(fam: Family, vth: float, margin_v: float,
                    i_floor_ma: float) -> tuple[Estimate | None,
                                                dict[float, LinearFit]]:
    """lambda from the saturation-region slope of I_D against V_DS.

    ``I_D = I_sat (1 + lambda V_DS)``, so a straight-line fit gives
    ``lambda = slope / intercept``. Fitted per gate step and combined by
    inverse-variance weighting; the scatter between steps is reported as the
    uncertainty when it exceeds the individual fit errors, since a real device
    that is not perfectly square-law will disagree between curves by more than
    any single fit admits.
    """
    fits: dict[float, LinearFit] = {}
    values: list[tuple[float, float]] = []      # (lambda, variance)

    for curve in fam:
        mask = curve.saturation_mask(vth, margin_v)
        v, i = curve.v[mask], curve.i_ma[mask]
        keep = i > i_floor_ma
        v, i = v[keep], i[keep]
        if v.size < 4:
            continue
        try:
            lf = fit_line(v, i, fit_range=FitRange(
                rule=f"V_DS >= V_GS - V_th + {margin_v:.2f} V, "
                     f"I_D >= {i_floor_ma:.4f} mA",
                origin="default",
                lo=float(v.min()), hi=float(v.max()),
                n_used=int(v.size), n_available=len(curve),
                quantity="V (V_DS)",
            ), x_unit="V", y_unit="mA")
        except FitError:
            continue
        if lf.intercept.value <= 0.0:
            continue

        lam = lf.slope.value / lf.intercept.value
        if lf.slope.stderr is None or lf.intercept.stderr is None:
            var = float("inf")
        else:
            rel = ((lf.slope.stderr / lf.slope.value) ** 2
                   if lf.slope.value else float("inf"))
            rel += (lf.intercept.stderr / lf.intercept.value) ** 2
            var = (lam ** 2) * rel
        fits[curve.vgs] = lf
        values.append((lam, var))

    if not values:
        return None, fits

    lams = np.array([v for v, _ in values])
    variances = np.array([var for _, var in values])

    if np.all(np.isfinite(variances)) and np.all(variances > 0):
        weights = 1.0 / variances
        mean = float(np.sum(weights * lams) / np.sum(weights))
        fit_err = float(math.sqrt(1.0 / np.sum(weights)))
    else:
        mean = float(lams.mean())
        fit_err = float("nan")

    # Scatter between curves, when there is more than one to compare.
    scatter = (float(lams.std(ddof=1) / math.sqrt(lams.size))
               if lams.size > 1 else 0.0)
    stderr = max(fit_err, scatter) if math.isfinite(fit_err) else scatter

    return Estimate(mean, stderr if stderr > 0 else None, "1/V"), fits


def _extract_rds_on(fam: Family, vth: float,
                    i_floor_ma: float) -> tuple[Estimate | None,
                                                LinearFit | None]:
    """On-resistance from the triode slope of the highest gate step."""
    if not fam.curves:
        return None, None
    curve: Curve = fam.curves[-1]
    vov = curve.vgs - vth
    if vov <= 0.0:
        return None, None

    limit = 0.25 * vov
    mask = (curve.v > 0.0) & (curve.v <= limit) & (curve.i_ma > i_floor_ma)
    v, i = curve.v[mask], curve.i_ma[mask]
    if v.size < 4:
        return None, None

    try:
        lf = fit_line(v, i / 1000.0, fit_range=FitRange(
            rule=f"highest gate step (V_GS = {curve.vgs:.3f} V), "
                 f"0 < V_DS <= 0.25*V_ov = {limit:.3f} V",
            origin="default",
            lo=float(v.min()), hi=float(v.max()),
            n_used=int(v.size), n_available=len(curve),
            quantity="V (V_DS)",
        ), x_unit="V", y_unit="A")
    except FitError:
        return None, None

    if lf.slope.value <= 0.0:
        return None, None
    r = 1.0 / lf.slope.value
    err = (None if lf.slope.stderr is None
           else abs(r ** 2 * lf.slope.stderr))
    return Estimate(r, err, "ohm"), lf


def _extract_subthreshold(fam: Family, vth: float,
                          cal: Calibration) -> Subthreshold:
    """Weak-inversion slope, if the range can resolve it.

    On range 1 it cannot, and saying so precisely is more useful than
    returning a number fitted to quantisation noise.
    """
    points: list[tuple[float, float]] = []
    for curve in fam:
        if curve.vgs >= vth:
            continue
        mask = curve.v > 0.2
        i = curve.i_ma[mask]
        if i.size == 0:
            continue
        median = float(np.median(i))
        if median > 0.0:
            points.append((curve.vgs, median))

    lsb = cal.i_lsb_ma
    if len(points) < 3:
        return Subthreshold(
            available=False,
            reason=(
                f"only {len(points)} gate steps below V_th carry non-zero "
                f"current. Range 1's current LSB is {lsb * 1000:.1f} uA, and "
                f"subthreshold currents are nanoamps, so they quantise to "
                f"exactly zero. This needs range 3 (blueprint §5)"
            ),
        )

    resolved = [p for p in points if p[1] >= lsb]
    if len(resolved) < 3:
        return Subthreshold(
            available=False,
            reason=(
                f"{len(resolved)} of {len(points)} subthreshold points sit at "
                f"or above one current LSB ({lsb * 1000:.1f} uA); a slope "
                f"fitted through the rest would be fitted to quantisation "
                f"noise. This needs range 3 (blueprint §5)"
            ),
        )

    vgs = np.array([p[0] for p in resolved])
    log_i = np.log10(np.array([p[1] for p in resolved]) / 1000.0)
    try:
        lf = fit_line(vgs, log_i, fit_range=FitRange(
            rule=f"gate steps below V_th = {vth:.4f} V with current at or "
                 f"above one LSB ({lsb * 1000:.1f} uA)",
            lo=float(vgs.min()), hi=float(vgs.max()),
            n_used=int(vgs.size), n_available=len(points),
            quantity="V (V_GS)",
        ), x_unit="V", y_unit="log10(A)")
    except FitError as exc:
        return Subthreshold(available=False, reason=str(exc))

    if lf.slope.value <= 0.0:
        return Subthreshold(
            available=False,
            reason="fitted subthreshold slope is not positive; the points are "
                   "not in weak inversion",
        )

    ss = 1000.0 / lf.slope.value            # mV per decade
    ss_err = (None if lf.slope.stderr is None
              else abs(ss / lf.slope.value * lf.slope.stderr))
    n_value = ss / (1000.0 * 0.02585 * math.log(10.0))
    n_err = None if ss_err is None else ss_err / (1000.0 * 0.02585
                                                  * math.log(10.0))
    return Subthreshold(
        available=True,
        mv_per_decade=Estimate(ss, ss_err, "mV/dec"),
        n_factor=Estimate(n_value, n_err, ""),
        fit=lf,
    )
