"""Closed-loop diode extraction.

Same principle as the MOSFET tests: hand the simulator a diode with a chosen
I_S, n and R_s, sweep it, extract, and require the values back.

The R_s case is the interesting one. A windowed semilog fit -- the obvious
implementation, and what blueprint §5 describes -- cannot recover these,
because series resistance starts bending the curve well inside any window wide
enough to fit. ``test_windowed_fit_is_biased_by_series_resistance`` pins that
failure down explicitly, so the joint solve is never "simplified" back to it.
"""

from __future__ import annotations

import pytest

from conftest import KNOWN_DIODE, run
from ct_host.extract import FitError, extract_diode
from ct_host.protocol import SweepRequest
from ct_host.recompute import recompute


def test_ideality_is_recovered(diode):
    d = extract_diode(diode)
    assert d.n.value == pytest.approx(KNOWN_DIODE["n_diode"], rel=0.02)


def test_saturation_current_is_recovered(diode):
    d = extract_diode(diode)
    assert d.i_s.value == pytest.approx(KNOWN_DIODE["is_"], rel=0.15)


def test_series_resistance_is_recovered(diode):
    d = extract_diode(diode)
    assert d.rs is not None
    assert d.rs.value == pytest.approx(KNOWN_DIODE["rs"], rel=0.05)


def test_every_parameter_carries_a_standard_error(diode):
    d = extract_diode(diode)
    assert d.n.stderr is not None and d.n.stderr > 0
    assert d.i_s.stderr is not None and d.i_s.stderr > 0
    assert d.rs.stderr is not None and d.rs.stderr > 0


@pytest.mark.parametrize("is_,n_diode,rs", [
    (2.5e-9, 1.75, 2.0),
    (1.0e-9, 1.90, 0.0),
    (5.0e-9, 1.50, 1.0),
    (1.0e-14, 1.00, 0.5),
])
def test_recovery_across_devices(is_, n_diode, rs):
    sweep = run(SweepRequest(device="sim-diode", n=300, vds_max=3.0,
                             i_limit_ma=165, vgs_list=[0]),
                dut="diode", is_=is_, n_diode=n_diode, rs=rs)
    d = extract_diode(recompute(sweep))

    assert d.n.value == pytest.approx(n_diode, rel=0.02)
    assert d.i_s.value == pytest.approx(is_, rel=0.15)
    if rs > 0:
        assert d.rs is not None
        assert d.rs.value == pytest.approx(rs, rel=0.05)
    else:
        assert d.rs is None, "a zero R_s must be reported as unresolved"


def test_windowed_fit_is_biased_by_series_resistance(diode):
    """Why the joint solve exists, demonstrated rather than asserted.

    Fitting a straight semilog window with R_s left in returns an inflated
    ideality factor and an inflated I_S, with a convincing R^2. On this
    fixture it gives n = 1.97 against a true 1.75 -- a 13% error -- at
    R^2 = 0.9965, which no one would look at twice.
    """
    joint = extract_diode(diode)
    # Two decades of current below the roll-off, fitted straight: the window
    # blueprint §5 describes, and the one a naive implementation picks.
    windowed = extract_diode(diode, refine_rs=False, i_window_ma=(0.4, 40.0))

    assert windowed.fit.r2 > 0.995, "the biased fit looks excellent"
    assert windowed.n.value > 1.10 * KNOWN_DIODE["n_diode"]
    assert windowed.n.value > joint.n.value
    assert windowed.i_s.value > joint.i_s.value

    true_n = KNOWN_DIODE["n_diode"]
    assert abs(windowed.n.value - true_n) > 3 * abs(joint.n.value - true_n)


def test_fitting_the_whole_range_without_deembedding_is_visibly_curved(diode):
    """The other failure mode: keep every point, ignore R_s, and the semilog
    line stops being a line. Less dangerous than the windowed fit, because
    R^2 drops far enough to notice, but still badly biased."""
    unrefined = extract_diode(diode, refine_rs=False)
    assert unrefined.fit.r2 < 0.99
    assert unrefined.n.value > 1.25 * KNOWN_DIODE["n_diode"]


def test_fit_range_records_which_method_ran(diode):
    assert "solved jointly" in extract_diode(diode).fit.range.rule
    assert "R_s held at zero" in extract_diode(diode, refine_rs=False).fit.range.rule


def test_explicit_window_is_marked_explicit(diode):
    d = extract_diode(diode, i_window_ma=(1.0, 20.0))
    assert d.fit.range.origin == "explicit"
    assert "caller-supplied" in d.fit.range.rule


def test_unresolvable_points_are_excluded_with_a_reason(diode):
    d = extract_diode(diode)
    assert d.fit.range.n_used > 50
    assert d.fit.range.n_used <= d.fit.range.n_available


def test_describe_is_honest_about_simulated_data(diode):
    assert "SIMULATED" in extract_diode(diode).describe()


def test_a_sweep_that_never_conducts_is_an_error():
    sweep = run(SweepRequest(device="sim-diode", n=40, vds_max=0.3,
                             vgs_list=[0]),
                dut="diode", **KNOWN_DIODE)
    with pytest.raises(FitError, match="resolvable current"):
        extract_diode(recompute(sweep))
