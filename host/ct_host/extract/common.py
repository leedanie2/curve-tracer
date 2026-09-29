"""Fit primitives: values with uncertainties, and ranges you can see.

Two ideas carry through the extraction modules.

**An extracted number without an uncertainty is not a measurement.** Every
fitted quantity here is an :class:`Estimate` carrying a standard error, and
derived quantities propagate it rather than dropping it.

**The fit range is part of the result, not an implementation detail.** Which
points enter a threshold fit moves V_th by more than measurement noise does.
So every fit returns the :class:`FitRange` it used, stating the literal rule
applied and whether the caller chose it or a default did, and
:meth:`LinearFit.describe` prints it. There are no hidden heuristics: if a
point was dropped, the report says which and why.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

__all__ = ["Estimate", "FitRange", "LinearFit", "fit_line", "FitError"]


class FitError(ValueError):
    """Not enough usable points, or a degenerate fit."""


@dataclass(frozen=True)
class Estimate:
    """A value with a standard error, where one is meaningful.

    ``stderr`` is ``None`` for a quantity that was computed rather than
    fitted. That is deliberately distinct from zero: zero would claim perfect
    knowledge, ``None`` says the question does not apply.
    """

    value: float
    stderr: float | None = None
    unit: str = ""
    #: Set when a systematic spread dominates the fit's own standard error --
    #: see MosfetParams.vth. Reported alongside, never folded in silently.
    spread: float | None = None

    def __str__(self) -> str:
        text = _sig(self.value)
        if self.stderr is not None:
            text += f" ± {_sig(self.stderr)}"
        if self.unit:
            text += f" {self.unit}"
        return text

    @property
    def relative(self) -> float | None:
        if self.stderr is None or self.value == 0.0:
            return None
        return abs(self.stderr / self.value)

    def scaled(self, factor: float, unit: str | None = None) -> Estimate:
        """Multiply by an exact constant, carrying the error through."""
        return Estimate(
            value=self.value * factor,
            stderr=None if self.stderr is None else abs(self.stderr * factor),
            unit=self.unit if unit is None else unit,
            spread=None if self.spread is None else abs(self.spread * factor),
        )


def _sig(x: float, digits: int = 5) -> str:
    if x == 0.0 or not math.isfinite(x):
        return f"{x:g}"
    magnitude = math.floor(math.log10(abs(x)))
    if -4 <= magnitude < digits:
        text = f"{x:.{max(0, digits - 1 - magnitude)}f}"
        # Trailing zeros past the significant digits are noise, and on an
        # error term they read as precision that is not there.
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text
    return f"{x:.{digits - 1}e}"


@dataclass(frozen=True)
class FitRange:
    """Which points a fit used, and by what rule.

    ``rule`` is the literal criterion, written out. ``origin`` says whether
    the caller supplied it or a default did -- a reader should never have to
    guess whether a range was chosen deliberately.
    """

    rule: str
    origin: str = "default"           # "explicit" | "default"
    lo: float | None = None
    hi: float | None = None
    n_used: int = 0
    n_available: int = 0
    excluded: tuple[str, ...] = ()
    quantity: str = ""                # what lo/hi are measured in

    @property
    def n_dropped(self) -> int:
        return self.n_available - self.n_used

    def describe(self, indent: str = "  ") -> str:
        bounds = ""
        if self.lo is not None and self.hi is not None:
            bounds = f" over {self.lo:.4g} .. {self.hi:.4g}"
            if self.quantity:
                bounds += f" {self.quantity}"
        lines = [
            f"{indent}range   : {self.n_used} of {self.n_available} points"
            f"{bounds}  [{self.origin}]",
            f"{indent}rule    : {self.rule}",
        ]
        for note in self.excluded:
            lines.append(f"{indent}          dropped: {note}")
        return "\n".join(lines)


@dataclass(frozen=True)
class LinearFit:
    """Ordinary least squares, with the errors done properly."""

    slope: Estimate
    intercept: Estimate
    x_intercept: Estimate
    r2: float
    residual_rms: float
    range: FitRange
    x: np.ndarray = field(repr=False, default_factory=lambda: np.array([]))
    y: np.ndarray = field(repr=False, default_factory=lambda: np.array([]))

    def predict(self, x: np.ndarray | float) -> np.ndarray | float:
        return self.slope.value * np.asarray(x) + self.intercept.value

    def describe(self, indent: str = "  ") -> str:
        return "\n".join([
            f"{indent}slope       : {self.slope}",
            f"{indent}intercept   : {self.intercept}",
            f"{indent}x-intercept : {self.x_intercept}",
            f"{indent}R^2 = {self.r2:.6f}   residual RMS = "
            f"{_sig(self.residual_rms)}",
            self.range.describe(indent),
        ])


def fit_line(x, y, *, fit_range: FitRange | None = None,
             x_unit: str = "", y_unit: str = "") -> LinearFit:
    """Least-squares straight line with standard errors on everything.

    The x-intercept error is the one worth being careful about. It is not the
    intercept's error divided by the slope: the slope and intercept estimates
    are correlated, and ignoring that covariance understates the result. The
    delta method on ``x0 = -b/m`` gives

        var(x0) = [var(b) + x0^2 var(m) + 2 x0 cov(m,b)] / m^2

    which reduces to the standard inverse-prediction form

        var(x0) = (s^2/m^2) [1/n + (xbar - x0)^2 / Sxx]

    That reduction is asserted in the tests, since it is easy to get the
    covariance sign wrong and the two forms disagree only in the tails.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = x.size

    if n != y.size:
        raise FitError(f"x and y differ in length: {n} vs {y.size}")
    if n < 2:
        raise FitError(f"a line needs at least 2 points, got {n}")

    x_mean = float(x.mean())
    sxx = float(np.sum((x - x_mean) ** 2))
    if sxx <= 0.0:
        raise FitError("all x values are identical; the slope is undefined")

    y_mean = float(y.mean())
    slope = float(np.sum((x - x_mean) * (y - y_mean)) / sxx)
    intercept = y_mean - slope * x_mean

    residuals = y - (slope * x + intercept)
    sse = float(np.sum(residuals ** 2))
    dof = n - 2

    if dof > 0:
        s2 = sse / dof
        var_slope = s2 / sxx
        var_intercept = s2 * (1.0 / n + x_mean ** 2 / sxx)
        cov_mb = -s2 * x_mean / sxx
        se_slope: float | None = math.sqrt(max(var_slope, 0.0))
        se_intercept: float | None = math.sqrt(max(var_intercept, 0.0))
    else:
        # Two points determine a line exactly; there is no residual to
        # estimate a variance from. Say so instead of reporting zero error.
        s2 = var_slope = var_intercept = cov_mb = 0.0
        se_slope = se_intercept = None

    sst = float(np.sum((y - y_mean) ** 2))
    r2 = 1.0 - sse / sst if sst > 0.0 else 1.0

    if slope == 0.0:
        x0, se_x0 = math.nan, None
    else:
        x0 = -intercept / slope
        if dof > 0:
            var_x0 = (var_intercept + x0 ** 2 * var_slope
                      + 2.0 * x0 * cov_mb) / (slope ** 2)
            se_x0 = math.sqrt(max(var_x0, 0.0))
        else:
            se_x0 = None

    if fit_range is None:
        fit_range = FitRange(
            rule="all supplied points",
            origin="default",
            lo=float(x.min()), hi=float(x.max()),
            n_used=n, n_available=n, quantity=x_unit,
        )

    return LinearFit(
        slope=Estimate(slope, se_slope,
                       f"{y_unit}/{x_unit}" if x_unit and y_unit else ""),
        intercept=Estimate(intercept, se_intercept, y_unit),
        x_intercept=Estimate(x0, se_x0, x_unit),
        r2=r2,
        residual_rms=math.sqrt(sse / n),
        range=fit_range,
        x=x, y=y,
    )
