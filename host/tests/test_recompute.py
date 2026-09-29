"""Recomputation from raw accumulators, and the agreement assertion.

The assertion is the safety net for a whole class of silent error: a
calibration constant that drifts between ``firmware/core/ct_config.h`` and the
``cal_*`` header. A few percent of gain error does not look wrong in a plot --
it looks like a slightly different transistor -- and it would propagate
straight into a SPICE model with nothing to notice. These tests inject exactly
that drift and require it to be caught.
"""

from __future__ import annotations

import pytest

from ct_host.csvio import parse
from ct_host.recompute import (
    Calibration,
    CalibrationMismatch,
    assert_agreement,
    recompute,
)


def test_recompute_matches_the_firmware(mosfet_sweep):
    report = assert_agreement(recompute(mosfet_sweep, check=False))
    assert report.ok
    assert report.n_rows == len(mosfet_sweep.rows)


def test_agreement_is_far_tighter_than_the_tolerance(mosfet_sweep):
    """Headroom, so the tolerance is not quietly doing the work."""
    report = assert_agreement(recompute(mosfet_sweep, check=False))
    assert report.worst_i_delta_ma < report.i_tol_ma / 10.0
    assert report.worst_v_delta_v < report.v_tol_v / 2.0


def test_recompute_fills_both_columns(mosfet):
    assert mosfet.recomputed
    for row in mosfet.rows:
        assert row.i_recomp_ma is not None
        assert row.v_recomp_v is not None


def test_analysis_uses_the_recomputed_values(mosfet):
    """Row.i_ma must follow the recomputed column once it exists."""
    row = next(r for r in mosfet.rows if r.i_acc > 0)
    assert row.i_ma == row.i_recomp_ma
    assert row.v_dut == row.v_recomp_v


def test_lsb_matches_the_documented_front_end(mosfet):
    cal = Calibration.from_sweep(mosfet)
    # 3.3 V / 4095 / (gain 20 * 1 ohm) = 40.3 uA, per firmware/README.md.
    assert cal.i_lsb_ma * 1000.0 == pytest.approx(40.3, abs=0.1)
    assert cal.i_full_scale_ma == pytest.approx(165.0, abs=0.5)


# --------------------------------------------------------------------------
# Injected drift must be caught
# --------------------------------------------------------------------------

def _with_cal(sweep, key: str, value: str):
    """Rewrite one cal_* header field, as a firmware/host divergence would."""
    lines = []
    for line in sweep.raw_text.splitlines():
        if line.startswith(f"# {key}:"):
            line = f"# {key}: {value}"
        lines.append(line)
    return parse("\r\n".join(lines) + "\r\n")


def test_drifted_shunt_is_caught(mosfet_sweep):
    drifted = _with_cal(mosfet_sweep, "cal_shunt_ohm", "0.998")
    with pytest.raises(CalibrationMismatch):
        recompute(drifted)


def test_drifted_diffamp_gain_is_caught(mosfet_sweep):
    drifted = _with_cal(mosfet_sweep, "cal_diffamp_gain", "20.40")
    with pytest.raises(CalibrationMismatch):
        recompute(drifted)


def test_drifted_divider_is_caught(mosfet_sweep):
    drifted = _with_cal(mosfet_sweep, "cal_vdiv", "4.02")
    with pytest.raises(CalibrationMismatch):
        recompute(drifted)


def test_a_tenth_percent_shunt_error_is_caught(mosfet_sweep):
    """The smallest drift worth worrying about, at the tightest constant."""
    drifted = _with_cal(mosfet_sweep, "cal_shunt_ohm", "1.001")
    with pytest.raises(CalibrationMismatch):
        recompute(drifted)


def test_the_error_names_the_likely_constant(mosfet_sweep):
    drifted = _with_cal(mosfet_sweep, "cal_diffamp_gain", "20.40")
    with pytest.raises(CalibrationMismatch) as excinfo:
        recompute(drifted)
    message = str(excinfo.value)
    assert "cal_diffamp_gain" in message
    assert "worst row" in message
    assert "point" in message
    # And it must not suggest loosening the tolerance as the fix.
    assert "rather than loosening" in message


def test_mismatch_can_be_inspected_without_raising(mosfet_sweep):
    drifted = _with_cal(mosfet_sweep, "cal_shunt_ohm", "0.990")
    sweep = recompute(drifted, check=False)
    report = assert_agreement(sweep)
    assert not report.ok
    assert report.i_ratio == pytest.approx(0.990, rel=0.01)


def test_voltage_drift_is_attributed_to_the_divider(mosfet_sweep):
    drifted = _with_cal(mosfet_sweep, "cal_vdiv", "4.10")
    report = assert_agreement(recompute(drifted, check=False))
    assert "cal_vdiv" in report.explain()
