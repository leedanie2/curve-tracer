"""Turning a flat row list into an I-V family, and slicing it.

A sweep arrives as one stream of rows covering every gate step. Analysis wants
it as a family of curves, and -- for threshold extraction -- as a slice across
those curves at one drain voltage.

**That slice is the subtle part, and it is why this module exists.** The
obvious implementation groups rows by ``vds_set_v``: every curve was commanded
through the same ramp, so the same commanded value appears once per curve.
That is wrong here. The feedback node is tapped ahead of ``R_iso`` (blueprint
§3.1), so the drop across ``R_iso`` plus the shunt burden is downstream of the
loop and scales with current. At one commanded voltage, the curve drawing the
most current sees the least drain voltage:

    commanded 2.052 V  ->  1.921 V at V_GS = 2.6 V     (5.7 mA)
                       ->  0.899 V at V_GS = 3.6 V    (50.1 mA)

Over a volt apart, and in that example the second device has been pushed out
of saturation entirely while the first is still in it. Fitting sqrt(I_D)
across that slice compares a saturated device against one in triode and
returns a threshold voltage that is simply wrong -- plausibly wrong, with a
good-looking R^2.

So a slice is taken at a **measured** drain voltage, with each curve
interpolated onto it. Recorded in blueprint §3.4.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass

import numpy as np

from .csvio import Row, Sweep

__all__ = ["Curve", "Family", "family_of", "DeltaReport", "vds_delta_report"]


@dataclass(frozen=True)
class Curve:
    """One gate step: the rows sharing a ``vgs_set_v``, drain-ascending."""

    vgs: float
    rows: tuple[Row, ...]

    @property
    def v(self) -> np.ndarray:
        """Measured drain voltage. Never the commanded value."""
        return np.array([r.v_dut for r in self.rows], dtype=float)

    @property
    def i_ma(self) -> np.ndarray:
        return np.array([r.i_ma for r in self.rows], dtype=float)

    @property
    def v_set(self) -> np.ndarray:
        return np.array([r.vds_set_v for r in self.rows], dtype=float)

    @property
    def v_span(self) -> tuple[float, float]:
        v = self.v
        return (float(v.min()), float(v.max())) if v.size else (0.0, 0.0)

    def __len__(self) -> int:
        return len(self.rows)

    def i_at(self, v_dut: float) -> float | None:
        """Current at a measured drain voltage, linearly interpolated.

        ``None`` when the requested voltage falls outside what this curve
        reached -- which is a real and common case, since a high-gate curve
        tops out at a lower measured voltage than a low-gate one. Returning
        ``None`` rather than extrapolating keeps a fit from silently including
        an invented point.
        """
        v, i = self.v, self.i_ma
        if v.size < 2:
            return None
        order = np.argsort(v)
        v, i = v[order], i[order]
        if v_dut < v[0] or v_dut > v[-1]:
            return None
        return float(np.interp(v_dut, v, i))

    def saturation_mask(self, vth: float, margin_v: float) -> np.ndarray:
        """Points with ``V_DS >= V_GS - V_th + margin``.

        The square-law saturation condition with a margin, so points sitting
        just past the knee -- where the model is least accurate -- stay out of
        a lambda fit.
        """
        vov = self.vgs - vth
        return self.v >= (vov + margin_v)


@dataclass(frozen=True)
class Family:
    """The curves of one sweep, ordered by gate voltage."""

    curves: tuple[Curve, ...]
    sweep: Sweep

    def __len__(self) -> int:
        return len(self.curves)

    def __iter__(self):
        return iter(self.curves)

    def __getitem__(self, idx: int) -> Curve:
        return self.curves[idx]

    @property
    def vgs_values(self) -> tuple[float, ...]:
        return tuple(c.vgs for c in self.curves)

    def common_v_span(self) -> tuple[float, float]:
        """The measured-voltage window every curve reaches.

        Empty when the curves do not overlap, which is itself informative:
        it means the series drop has spread them apart further than the ramp
        covered.
        """
        if not self.curves:
            return (0.0, 0.0)
        lows, highs = zip(*(c.v_span for c in self.curves))
        return (float(max(lows)), float(min(highs)))

    def slice_at(self, v_dut: float) -> list[tuple[float, float]]:
        """``(V_GS, I_D)`` across the family at one *measured* drain voltage.

        Curves that never reached ``v_dut`` are omitted rather than
        extrapolated.
        """
        out: list[tuple[float, float]] = []
        for curve in self.curves:
            i = curve.i_at(v_dut)
            if i is not None:
                out.append((curve.vgs, i))
        return out


def family_of(sweep: Sweep) -> Family:
    """Group a sweep's valid rows into curves.

    Flagged rows are excluded here, once, so nothing downstream has to
    remember to. They remain in ``sweep.rows`` and in any saved file.
    """
    groups: OrderedDict[float, list[Row]] = OrderedDict()
    for row in sweep.valid_rows:
        groups.setdefault(row.vgs_set_v, []).append(row)

    curves = tuple(
        Curve(vgs=vgs, rows=tuple(sorted(rows, key=lambda r: r.v_dut)))
        for vgs, rows in sorted(groups.items())
    )
    return Family(curves=curves, sweep=sweep)


# --------------------------------------------------------------------------
# The vds delta diagnostic
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class DeltaReport:
    """``vds_set_v - vds_meas_v`` against the expected I x (R_iso + shunt + R_PTC).

    firmware/README.md tabulates what departures mean: a delta near zero at
    high current points at Kelvin leads shorted to the force leads, a
    scattered delta at a bad sense connection, an oversized one at extra
    series resistance.
    """

    n: int
    mean_delta_v: float
    expected_mean_v: float
    fitted_r_ohm: float | None
    expected_r_ohm: float
    max_residual_v: float
    monotonic: bool
    #: ``None`` when the board's PTC has not been measured. ``expected_r_ohm``
    #: is then R_iso + shunt only, a lower bound rather than a prediction.
    r_ptc_ohm: float | None = None

    #: nSMD010 datasheet: 1.6 ohm minimum, 15 ohm maximum one hour after
    #: reflow or a trip (hardware/DECISIONS.md, S-1).
    R_PTC_BAND_OHM = (1.6, 15.0)

    @property
    def implied_r_ptc_ohm(self) -> float | None:
        """What the fit says the PTC is, if R_PTC was not supplied."""
        if self.fitted_r_ohm is None or self.r_ptc_ohm is not None:
            return None
        return self.fitted_r_ohm - self.expected_r_ohm

    @property
    def verdict(self) -> str:
        if self.n == 0:
            return "no rows above the noise floor; nothing to check"
        if self.fitted_r_ohm is None:
            return "too few points to fit a series resistance"
        # Gross faults first: they do not depend on knowing the PTC.
        if self.fitted_r_ohm < 0.5 * self.expected_r_ohm:
            return ("delta far too small -- Kelvin leads may be shorted to the "
                    "force leads, or sensing the wrong node")
        if self.r_ptc_ohm is None:
            lo, hi = self.R_PTC_BAND_OHM
            if self.fitted_r_ohm > 1.5 * (self.expected_r_ohm + hi):
                return ("delta far too large -- extra series resistance in a lead, "
                        "socket or contact, beyond even a worst-case PTC")
            implied = self.implied_r_ptc_ohm
            where = ("inside" if lo <= implied <= hi else "OUTSIDE")
            return (f"R_PTC unset -- measure R_PTC at bring-up (TP5 -> TP17 drop "
                    f"at a known current) and set cal_r_ptc_ohm; the fit implies "
                    f"{implied:.1f} ohm, {where} the {lo:g}-{hi:g} ohm datasheet band")
        err = (self.fitted_r_ohm - self.expected_r_ohm) / self.expected_r_ohm
        if abs(err) < 0.10 and self.max_residual_v < 0.05:
            return "as designed"
        if self.fitted_r_ohm < 0.5 * self.expected_r_ohm:
            return ("delta far too small -- Kelvin leads may be shorted to the "
                    "force leads, or sensing the wrong node")
        if self.fitted_r_ohm > 1.5 * self.expected_r_ohm:
            return ("delta far too large -- extra series resistance in a lead, "
                    "socket or contact")
        if not self.monotonic or self.max_residual_v >= 0.05:
            return ("delta does not track current smoothly -- noise on ADC2, "
                    "or a bad Kelvin connection")
        return f"series resistance {err * 100:+.1f}% from nominal"

    def describe(self) -> str:
        fitted = ("--" if self.fitted_r_ohm is None
                  else f"{self.fitted_r_ohm:.2f} ohm")
        return (
            f"vds_set_v - vds_meas_v diagnostic ({self.n} rows)\n"
            f"  mean delta        : {self.mean_delta_v:.4f} V "
            f"(expected {self.expected_mean_v:.4f} V at these currents)\n"
            f"  implied series R  : {fitted} "
            f"(expected {self.expected_r_ohm:.2f} ohm = R_iso + shunt"
            f"{'' if self.r_ptc_ohm is None else f' + R_PTC {self.r_ptc_ohm:.2f}'}"
            f"{'; R_PTC unset' if self.r_ptc_ohm is None else ''})\n"
            f"  max residual      : {self.max_residual_v:.4f} V\n"
            f"  verdict           : {self.verdict}"
        )


def vds_delta_report(sweep: Sweep, *, r_iso_ohm: float | None = None,
                     r_ptc_ohm: float | None = None,
                     i_floor_ma: float = 1.0) -> DeltaReport:
    """Check the commanded-minus-measured delta against I x (R_iso + shunt + R_PTC).

    The expected resistance comes from the sweep's ``cal_*`` header, not a
    literal: ``cal_r_iso_ohm``, ``cal_shunt_ohm`` and the board's measured
    ``cal_r_ptc_ohm``. Either can be overridden here -- ``r_ptc_ohm`` in
    particular, because the PTC moves after every trip and re-measuring it
    should not need a reflash. With no R_PTC from either place the verdict
    says to measure it, and reports what the fit implies.

    Rows below ``i_floor_ma`` are excluded: at low current the delta is a
    fraction of an ADC count and the ratio is meaningless.
    """
    from .recompute import Calibration

    cal = Calibration.from_sweep(sweep) if "cal_shunt_ohm" in sweep.meta else None
    shunt = cal.shunt_ohm if cal else 1.0
    if r_iso_ohm is None:
        r_iso_ohm = cal.r_iso_ohm if cal and cal.r_iso_ohm is not None else 22.0
    if r_ptc_ohm is None and cal is not None:
        r_ptc_ohm = cal.r_ptc_ohm
    expected_r = r_iso_ohm + shunt + (r_ptc_ohm or 0.0)

    rows = [r for r in sweep.valid_rows if r.i_ma > i_floor_ma]
    if not rows:
        return DeltaReport(0, 0.0, 0.0, None, expected_r, 0.0, True, r_ptc_ohm)

    i_a = np.array([r.i_ma for r in rows]) / 1000.0
    delta = np.array([r.vds_set_v - r.v_dut for r in rows])

    fitted = None
    residual = 0.0
    if i_a.size >= 2 and float(i_a.max() - i_a.min()) > 1e-6:
        # Through the origin: at zero current there is no drop to explain.
        fitted = float(np.dot(i_a, delta) / np.dot(i_a, i_a))
        residual = float(np.max(np.abs(delta - fitted * i_a)))

    order = np.argsort(i_a)
    sorted_delta = delta[order]
    monotonic = bool(np.all(np.diff(sorted_delta) >= -0.02))

    return DeltaReport(
        n=len(rows),
        mean_delta_v=float(delta.mean()),
        expected_mean_v=float((i_a * expected_r).mean()),
        fitted_r_ohm=fitted,
        expected_r_ohm=expected_r,
        max_residual_v=residual,
        monotonic=monotonic,
        r_ptc_ohm=r_ptc_ohm,
    )
