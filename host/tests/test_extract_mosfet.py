"""Closed-loop MOSFET extraction.

The simulator is handed a device with a chosen V_th, k and lambda; a sweep is
run through the real firmware logic; the host extracts parameters from the
resulting CSV; and the recovered values are compared against what went in.
That closes physics -> measurement -> model in software, before it closes on
the bench.

The tolerances below are deliberately tight. They are not "does it roughly
work" thresholds -- they are the level at which a regression in the fit, the
slice interpolation or the de-embedding would show up.
"""

from __future__ import annotations

import pytest

from conftest import KNOWN_MOSFET
from ct_host.dataset import family_of
from ct_host.extract import FitError, extract_mosfet, vth_sensitivity
from ct_host.recompute import Calibration, recompute


# --------------------------------------------------------------------------
# The closed loop
# --------------------------------------------------------------------------

def test_vth_is_recovered(mosfet):
    p = extract_mosfet(mosfet)
    assert p.vth.value == pytest.approx(KNOWN_MOSFET["vth"], abs=0.005)


def test_vth_carries_a_standard_error(mosfet):
    p = extract_mosfet(mosfet)
    assert p.vth.stderr is not None
    assert 0.0 < p.vth.stderr < 0.01
    # And the true value is inside a few standard errors of the estimate.
    assert abs(p.vth.value - KNOWN_MOSFET["vth"]) < 20 * p.vth.stderr


def test_kp_is_recovered_in_the_spice_convention(mosfet):
    """kp_wl must equal the simulator's --k, which uses I = (k/2)Vov^2."""
    p = extract_mosfet(mosfet)
    assert p.kp_wl.value == pytest.approx(KNOWN_MOSFET["k"], rel=0.02)


def test_beta_is_half_of_kp(mosfet):
    """The factor of two between conventions, asserted rather than assumed."""
    p = extract_mosfet(mosfet)
    assert p.kp_wl.value == pytest.approx(2.0 * p.beta.value, rel=1e-12)


def test_lambda_is_recovered(mosfet):
    p = extract_mosfet(mosfet)
    assert p.lambda_ is not None
    assert p.lambda_.value == pytest.approx(KNOWN_MOSFET["lam"], rel=0.05)
    assert p.va.value == pytest.approx(1.0 / KNOWN_MOSFET["lam"], rel=0.05)


def test_extraction_survives_adc_noise(noisy_mosfet_sweep):
    p = extract_mosfet(recompute(noisy_mosfet_sweep))
    assert p.vth.value == pytest.approx(KNOWN_MOSFET["vth"], abs=0.02)
    assert p.kp_wl.value == pytest.approx(KNOWN_MOSFET["k"], rel=0.05)


# --------------------------------------------------------------------------
# De-embedding
# --------------------------------------------------------------------------

def test_beta_is_de_embedded_and_the_raw_value_is_kept(mosfet):
    """beta_raw carries (1 + lambda*V_slice); beta does not.

    Without de-embedding the extracted transconductance is inflated by the
    channel-length modulation factor at the slice voltage. At the ~8.5 V slice
    these sweeps produce, that is around 10%.
    """
    p = extract_mosfet(mosfet)
    expected_factor = 1.0 + p.lambda_.value * p.vds_slice

    assert p.beta_raw.value > p.beta.value
    assert p.deembed_factor == pytest.approx(expected_factor, rel=1e-9)
    assert expected_factor > 1.05, "the slice should be high enough to matter"

    # The raw value is the one that would have been wrong.
    assert p.beta_raw.value == pytest.approx(
        KNOWN_MOSFET["k"] / 2.0 * expected_factor, rel=0.02)
    assert p.beta.value == pytest.approx(KNOWN_MOSFET["k"] / 2.0, rel=0.02)


def test_disabling_de_embedding_reproduces_the_inflated_value(mosfet):
    p = extract_mosfet(mosfet, deembed_lambda=False)
    assert p.beta.value == pytest.approx(p.beta_raw.value, rel=1e-12)
    assert p.beta.value > KNOWN_MOSFET["k"] / 2.0 * 1.05


# --------------------------------------------------------------------------
# Fit ranges are visible
# --------------------------------------------------------------------------

def test_fit_range_states_its_rule_and_origin(mosfet):
    p = extract_mosfet(mosfet)
    assert p.vth_fit.range.rule
    assert p.vth_fit.range.origin == "default"
    assert p.vth_fit.range.n_used >= 3
    assert "two-pass" in p.vth_fit.range.rule


def test_explicit_range_is_marked_explicit(mosfet):
    p = extract_mosfet(mosfet, vgs_range=(2.8, 3.6))
    assert p.vth_fit.range.origin == "explicit"
    assert "caller-supplied" in p.vth_fit.range.rule
    assert p.vth_fit.range.lo >= 2.8
    assert p.vth_fit.range.hi <= 3.6


def test_excluded_points_say_why(mosfet):
    p = extract_mosfet(mosfet, vgs_range=(2.9, 3.6))
    assert p.vth_fit.range.n_dropped > 0
    assert any("outside the requested range" in note
               for note in p.vth_fit.range.excluded)


def test_slice_is_a_measured_voltage_not_a_commanded_one(mosfet):
    """The slice must lie in the measured span, which is below the commanded.

    vds_max is 10 V, but no curve *measures* 10 V because R_iso eats the
    difference. A slice defaulting to a commanded value would sit outside
    every curve.
    """
    p = extract_mosfet(mosfet)
    assert p.vds_slice < 10.0
    for curve in family_of(mosfet):
        assert curve.i_at(p.vds_slice) is not None


def test_describe_mentions_the_fit_range(mosfet):
    text = extract_mosfet(mosfet).describe()
    assert "rule" in text
    assert "V_th" in text


# --------------------------------------------------------------------------
# Sensitivity, surfaced not buried
# --------------------------------------------------------------------------

def test_sensitivity_table_covers_several_choices(mosfet_sweep):
    table = vth_sensitivity(mosfet_sweep)
    assert len(table) >= 5
    assert {"vds_slice", "vgs_lo", "vgs_hi", "vth", "stderr"} <= set(table.columns)
    # Every choice recovers roughly the right threshold...
    assert table["vth"].between(2.13, 2.17).all()
    # ...but not identically. That spread is the point.
    assert table["vth"].std() > 0


def test_describe_reports_the_spread_alongside_the_stderr(mosfet):
    """A reader must see both numbers without knowing to ask for either."""
    p = extract_mosfet(mosfet)
    text = p.describe()

    assert "fit standard error" in text
    assert "fit-range spread" in text
    assert p.sensitivity is not None
    assert p.vth.spread is not None
    assert p.vth.spread == pytest.approx(p.sensitivity.spread)


def test_range_choice_dominates_the_fit_error(mosfet):
    """On noiseless data the spread is several times the fit's own stderr.

    This is the substantive claim behind surfacing both: quoting the fit
    standard error alone would understate the uncertainty by this factor, and
    on bench data the gap is expected to be wider still.
    """
    p = extract_mosfet(mosfet)
    assert p.sensitivity.spread > 3.0 * p.vth.stderr


def test_sensitivity_can_be_switched_off(mosfet):
    p = extract_mosfet(mosfet, sensitivity=False)
    assert p.sensitivity is None
    assert p.vth.spread is None


# --------------------------------------------------------------------------
# Subthreshold: unavailable on range 1, and that is the result
# --------------------------------------------------------------------------

def test_subthreshold_is_unavailable_on_range_1(subthreshold_sweep):
    """Blueprint §5's claim, turned into a checked result.

    "Subthreshold slope needs the low current range -- this is the measurement
    that justifies building three ranges instead of one." Range 1's current
    LSB is ~40 uA; subthreshold currents are nanoamps. They quantise to zero,
    so the slope is not measurable, and the extractor must say so rather than
    fit a line to quantisation noise.
    """
    p = extract_mosfet(recompute(subthreshold_sweep))

    assert p.subthreshold.available is False
    assert p.subthreshold.mv_per_decade is None
    assert "range 3" in p.subthreshold.reason
    assert "LSB" in p.subthreshold.reason or "uA" in p.subthreshold.reason


def test_subthreshold_reason_quotes_the_actual_lsb(subthreshold_sweep):
    sweep = recompute(subthreshold_sweep)
    lsb_ua = Calibration.from_sweep(sweep).i_lsb_ma * 1000.0
    p = extract_mosfet(sweep)
    assert f"{lsb_ua:.1f}" in p.subthreshold.reason


def test_sub_threshold_gate_steps_really_do_read_zero(subthreshold_sweep):
    """The premise of the test above, checked directly."""
    family = family_of(recompute(subthreshold_sweep))
    below = [c for c in family if c.vgs < KNOWN_MOSFET["vth"]]
    assert below, "the fixture must include gate steps below V_th"
    for curve in below:
        assert max(r.i_acc for r in curve.rows) == 0


# --------------------------------------------------------------------------
# Failure modes
# --------------------------------------------------------------------------

def test_too_few_gate_steps_is_an_error(diode):
    with pytest.raises(FitError, match="at least 3 gate steps"):
        extract_mosfet(diode)


def test_flagged_rows_never_enter_a_fit(ilimit_sweep):
    sweep = recompute(ilimit_sweep)
    assert sweep.flagged_rows, "the fixture must trip the limit"

    points = [r for curve in family_of(sweep) for r in curve.rows]
    assert all(r.valid for r in points)
    assert len(points) == len(sweep.rows) - len(sweep.flagged_rows)
