"""The fit primitives, checked against closed-form statistics.

The x-intercept standard error is the one that earns a test of its own. It is
tempting to write it as ``sigma_b / m``, which ignores the correlation between
slope and intercept and understates the result. The delta method gives

    var(x0) = [var(b) + x0^2 var(m) + 2 x0 cov(m,b)] / m^2

and the covariance sign is easy to get backwards -- with the wrong sign the
two forms agree near the data's centre and diverge in the tails, which is
exactly where a threshold extrapolation lives. So the implementation is
checked against the standard inverse-prediction formula,

    var(x0) = (s^2/m^2) [1/n + (xbar - x0)^2 / Sxx]

which is derived independently.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from ct_host.extract.common import Estimate, FitError, FitRange, fit_line


def test_recovers_an_exact_line():
    x = np.linspace(0.0, 10.0, 11)
    fit = fit_line(x, 3.0 * x + 2.0)
    assert fit.slope.value == pytest.approx(3.0)
    assert fit.intercept.value == pytest.approx(2.0)
    assert fit.x_intercept.value == pytest.approx(-2.0 / 3.0)
    assert fit.r2 == pytest.approx(1.0)


def test_x_intercept_error_matches_inverse_prediction():
    rng = np.random.default_rng(20260929)
    x = np.linspace(1.0, 5.0, 40)
    y = 2.5 * x - 4.0 + rng.normal(0.0, 0.05, x.size)

    fit = fit_line(x, y)

    n = x.size
    x_mean = x.mean()
    sxx = np.sum((x - x_mean) ** 2)
    residuals = y - (fit.slope.value * x + fit.intercept.value)
    s2 = np.sum(residuals ** 2) / (n - 2)
    x0 = fit.x_intercept.value

    expected = math.sqrt(
        s2 / fit.slope.value ** 2 * (1.0 / n + (x_mean - x0) ** 2 / sxx)
    )
    assert fit.x_intercept.stderr == pytest.approx(expected, rel=1e-10)


def test_naive_error_would_be_wrong():
    """The covariance term is not negligible, so the test above has teeth."""
    rng = np.random.default_rng(7)
    x = np.linspace(2.5, 3.6, 6)          # a realistic gate-step spread
    y = 0.17 * x - 0.37 + rng.normal(0.0, 1e-4, x.size)

    fit = fit_line(x, y)
    naive = abs(fit.intercept.stderr / fit.slope.value)
    assert fit.x_intercept.stderr < 0.5 * naive


def test_two_points_report_no_error_rather_than_zero():
    """A line through two points has no residual to estimate variance from."""
    fit = fit_line([0.0, 1.0], [0.0, 2.0])
    assert fit.slope.value == pytest.approx(2.0)
    assert fit.slope.stderr is None
    assert fit.intercept.stderr is None
    assert fit.x_intercept.stderr is None


def test_degenerate_inputs_raise():
    with pytest.raises(FitError, match="at least 2 points"):
        fit_line([1.0], [1.0])
    with pytest.raises(FitError, match="identical"):
        fit_line([2.0, 2.0, 2.0], [1.0, 2.0, 3.0])
    with pytest.raises(FitError, match="differ in length"):
        fit_line([1.0, 2.0], [1.0])


# --------------------------------------------------------------------------
# Estimate
# --------------------------------------------------------------------------

def test_estimate_formats_with_its_error_and_unit():
    assert str(Estimate(2.1498, 0.00032, "V")) == "2.1498 ± 0.00032 V"


def test_estimate_without_error_says_so_by_omission():
    assert str(Estimate(23.0, None, "ohm")) == "23 ohm"
    assert str(Estimate(2.5e-9, None, "A")) == "2.5000e-09 A"


def test_scaling_carries_the_error_through():
    doubled = Estimate(0.0275, 0.0001, "A/V^2").scaled(2.0)
    assert doubled.value == pytest.approx(0.055)
    assert doubled.stderr == pytest.approx(0.0002)


def test_scaling_preserves_the_spread():
    scaled = Estimate(1.0, 0.1, "V", spread=0.4).scaled(3.0)
    assert scaled.spread == pytest.approx(1.2)


# --------------------------------------------------------------------------
# FitRange
# --------------------------------------------------------------------------

def test_fit_range_reports_what_it_dropped():
    rng = FitRange(rule="a stated rule", origin="explicit", lo=1.0, hi=2.0,
                   n_used=4, n_available=6, quantity="V",
                   excluded=("one point: too low", "another: too high"))
    text = rng.describe()
    assert "4 of 6 points" in text
    assert "[explicit]" in text
    assert "a stated rule" in text
    assert "too low" in text
    assert rng.n_dropped == 2


def test_default_range_is_labelled_default():
    fit = fit_line([0.0, 1.0, 2.0, 3.0], [0.0, 1.0, 2.0, 3.0])
    assert fit.range.origin == "default"
    assert fit.range.n_used == 4
