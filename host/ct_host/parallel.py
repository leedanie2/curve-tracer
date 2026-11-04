"""A resistor across D-S with the device, and taking its current back out.

Board 2's sweep loop oscillates at open load with C1 empty (Block 1,
2026-11-03), and a diode or MOSFET is an open load at the bottom of its
sweep. Sim 13 keeps the loop quiet with 470 ohm or less clamped across D-S
in J6. The firmware cannot tell that resistor, R_p, from the device, so
every reading carries an extra ``V / R_p``. This module subtracts it using
the Kelvin-sensed voltage, the same way the firmware subtracts the Kelvin
divider's ``V / 400k``.

Where R_p comes from matters more than its tolerance. Three sources:

- **calibration**, the primary: a capture of R_p alone on the same
  instrument (MVP card step 14), fitted as ``I = V / R + offset``. The fit
  uses the instrument's own readings, so gain errors in the current and the
  voltage reading cancel: what is subtracted is what the instrument reads
  through R_p, not what a DMM says R_p is. The instrument's current zero
  is not subtracted; it is in every capture, R_p or not.
- **given**: a number on the command line, such as a DMM reading. A gain
  error in the instrument does not cancel against it.
- **auto**: fitted from the capture itself, over points where the device
  carries no current: below 0.25 V on a diode, the lowest gate step of a
  MOSFET family. It is the cross-check on the other two, and primary only
  when nothing else exists. It needs points down there, which a sweep DAC
  with a floor above 0.25 V does not give (blueprint §3.5).

What it costs: the subtraction's error is ``V * sigma_R / R^2``, a fixed
current at a given voltage, so it is largest relative to the smallest device
currents. At 0.5% of 470 ohm and 0.6 V it is 6 uA, 3% of the diode fit's
0.2 mA floor (5 LSB).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from .csvio import ContractError, Row, Sweep, parse
from .extract.common import Estimate, FitError
from .recompute import recompute

__all__ = ["ResistorFit", "ParallelR", "fit_resistor", "auto_fit", "resolve",
           "from_meta", "subtract", "AUTO_V_MAX"]

#: Highest Kelvin voltage the diode auto-fit uses. A 1N4148 carries under
#: 1 uA there, against 0.5 mA through 470 ohm.
AUTO_V_MAX = 0.25

#: Fewest points a resistor fit accepts.
MIN_POINTS = 5


@dataclass(frozen=True)
class ResistorFit:
    """``I = V / R + offset`` over a set of rows, total current."""

    r: Estimate
    offset_ma: Estimate
    n: int
    v_lo: float
    v_hi: float
    max_residual_ma: float
    r_squared: float
    rule: str

    def describe(self, indent: str = "  ") -> str:
        return "\n".join([
            f"{indent}R       = {self.r}",
            f"{indent}offset  = {self.offset_ma}   (current at V = 0: the "
            f"instrument's zero)",
            f"{indent}fit     : {self.n} points over {self.v_lo:.4g} .. "
            f"{self.v_hi:.4g} V; max residual {self.max_residual_ma:.4f} mA; "
            f"R^2 {self.r_squared:.6f}",
            f"{indent}rule    : {self.rule}",
        ])


def fit_resistor(rows: list[Row], *, rule: str) -> ResistorFit:
    """Least squares ``I = g V + b`` on total current; ``R = 1/g``."""
    v = np.array([r.v_dut for r in rows], dtype=float)
    i = np.array([r.i_total_ma for r in rows], dtype=float)
    if v.size < MIN_POINTS or float(np.ptp(v)) <= 0.0:
        raise FitError(f"{v.size} points over {float(np.ptp(v)) if v.size else 0:.3g} V "
                       f"cannot fit a resistance; need {MIN_POINTS} spread in V")
    design = np.column_stack([v, np.ones_like(v)])
    (g, b), *_ = np.linalg.lstsq(design, i, rcond=None)
    residual = i - design @ np.array([g, b])
    dof = v.size - 2
    s2 = float(residual @ residual) / dof if dof > 0 else 0.0
    cov = s2 * np.linalg.inv(design.T @ design)
    if g <= 0.0:
        raise FitError("the fitted conductance is not positive; this is not a "
                       "resistor")
    r_ohm = 1000.0 / g
    r_err = math.sqrt(cov[0, 0]) * 1000.0 / (g * g)
    ss_tot = float(((i - i.mean()) ** 2).sum())
    return ResistorFit(
        r=Estimate(r_ohm, r_err, "ohm"),
        offset_ma=Estimate(float(b), math.sqrt(cov[1, 1]), "mA"),
        n=int(v.size), v_lo=float(v.min()), v_hi=float(v.max()),
        max_residual_ma=float(np.abs(residual).max()),
        r_squared=1.0 - float(residual @ residual) / ss_tot if ss_tot else 1.0,
        rule=rule,
    )


def fit_sweep_resistor(sweep: Sweep) -> ResistorFit:
    """A calibration capture: every valid row of R_p alone."""
    if not sweep.recomputed:
        sweep = recompute(sweep)
    return fit_resistor(sweep.valid_rows,
                        rule="every valid row, I = V/R + offset, total current")


def auto_fit(sweep: Sweep, *, v_max: float = AUTO_V_MAX
             ) -> tuple[ResistorFit | None, str]:
    """R_p from the capture itself, or ``None`` and the reason it is not.

    One gate step (a diode): the rows at or below ``v_max``. Several steps (a
    MOSFET family): every row of the lowest step, which is assumed to be off.
    That assumption is stated in the rule, and a curve that does conduct
    shows as a poor fit.
    """
    if not sweep.recomputed:
        sweep = recompute(sweep)
    rows = sweep.valid_rows
    steps = sorted({r.vgs_set_v for r in rows})
    if len(steps) > 1:
        rows = [r for r in rows if r.vgs_set_v == steps[0]]
        rule = (f"lowest gate step, V_GS = {steps[0]:.3f} V, assumed off; "
                f"I = V/R + offset")
    else:
        rows = [r for r in rows if r.v_dut <= v_max]
        rule = (f"rows at V <= {v_max:g} V, where the device carries "
                f"negligible current; I = V/R + offset")
    above_zero = [r for r in rows if r.v_dut > 0.02]
    if len(above_zero) < MIN_POINTS:
        lowest = min((r.v_dut for r in sweep.valid_rows), default=float("nan"))
        return None, (f"unavailable: {len(above_zero)} rows between 0.02 V and "
                      f"{v_max:g} V (lowest measured V {lowest:.3f} V; a DAC "
                      f"floor above {v_max:g} V leaves none)")
    try:
        return fit_resistor(rows, rule=rule), ""
    except FitError as exc:
        return None, f"unavailable: {exc}"


@dataclass(frozen=True)
class ParallelR:
    """The R_p a capture's current is corrected for, and where it came from."""

    ohm: float
    stderr: float | None
    method: str          # "calibration" | "given" | "auto"
    source: str

    def current_error_ma(self, v: float) -> float | None:
        """The subtraction's standard error at Kelvin voltage ``v``."""
        if self.stderr is None:
            return None
        return v * self.stderr / (self.ohm * self.ohm) * 1000.0

    def meta_items(self) -> list[tuple[str, str]]:
        return [
            ("host_r_parallel_ohm", f"{self.ohm:.6g}"),
            ("host_r_parallel_stderr_ohm",
             "unset" if self.stderr is None else f"{self.stderr:.3g}"),
            ("host_r_parallel_method", self.method),
            ("host_r_parallel_src", self.source),
        ]

    @property
    def label(self) -> str:
        err = "" if self.stderr is None else f" ± {self.stderr:.2g}"
        return f"R_p = {self.ohm:.5g}{err} Ω subtracted ({self.method}: {self.source})"

    def describe(self) -> str:
        return f"  {self.label}"


def resolve(spec: str, sweep: Sweep | None = None) -> ParallelR:
    """``--r-parallel``: ``OHM``, ``auto``, or the path of a calibration CSV."""
    if spec == "auto":
        if sweep is None:
            raise ValueError("--r-parallel auto needs the capture to fit")
        fit, reason = auto_fit(sweep)
        if fit is None:
            raise FitError(f"R_p auto-fit {reason}")
        return ParallelR(fit.r.value, fit.r.stderr, "auto",
                         f"this capture, {fit.n} rows, {fit.rule}")
    try:
        ohm = float(spec)
    except ValueError:
        pass
    else:
        if ohm <= 0.0:
            raise ValueError(f"R_p must be positive, not {spec}")
        return ParallelR(ohm, None, "given", "command line")
    path = Path(spec)
    if not path.exists():
        raise ValueError(f"--r-parallel {spec!r} is not a number, 'auto', or a "
                         f"file")
    cal = parse(path.read_text(), require_end=True)
    if cal.meta.get("host_r_parallel_ohm") is not None:
        raise ContractError(f"{spec} was itself captured with an R_p "
                            f"correction; it is not a capture of R_p alone")
    fit = fit_sweep_resistor(cal)
    return ParallelR(
        fit.r.value, fit.r.stderr, "calibration",
        f"{spec}, {fit.n} rows over {fit.v_lo:.3g}..{fit.v_hi:.3g} V, "
        f"offset {fit.offset_ma.value:+.4f} mA",
    )


def from_meta(sweep: Sweep) -> ParallelR | None:
    """The R_p record a capture was saved with, if any."""
    ohm = sweep.meta.float_or_none("host_r_parallel_ohm")
    if ohm is None:
        return None
    return ParallelR(ohm, sweep.meta.float_or_none("host_r_parallel_stderr_ohm"),
                     sweep.meta.get("host_r_parallel_method", "given"),
                     sweep.meta.get("host_r_parallel_src", "unrecorded"))


def subtract(sweep: Sweep, rp: ParallelR) -> Sweep:
    """Return a copy with ``V / R_p`` taken out of every row's current."""
    if not sweep.recomputed:
        sweep = recompute(sweep)
    rows = [replace(r, i_parallel_ma=r.v_dut / rp.ohm * 1000.0)
            for r in sweep.rows]
    return replace(sweep, rows=rows, r_parallel=rp)
