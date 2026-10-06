"""Grouping a sweep into curves, and slicing across them.

The slice is the part with a trap in it. Blueprint §3.4: because ``R_iso``'s
drop scales with current, one commanded ``vds_set_v`` lands at a different
measured ``vds_meas_v`` on every curve. Grouping by the commanded value
compares points taken at different bias. These tests demonstrate that the trap
is real on this instrument's own data, and that the slice avoids it.
"""

from __future__ import annotations

import pytest

from ct_host.dataset import family_of, vds_delta_report


def test_family_groups_by_gate_step(mosfet):
    family = family_of(mosfet)
    assert len(family) == 6
    assert family.vgs_values == tuple(sorted(family.vgs_values))
    assert sum(len(c) for c in family) == len(mosfet.valid_rows)


def test_curves_are_drain_ascending(mosfet):
    for curve in family_of(mosfet):
        v = curve.v
        assert list(v) == sorted(v)


def test_commanded_voltage_lands_at_different_measured_voltages(mosfet):
    """The trap itself, measured on real instrument output.

    One commanded value; the spread in what the curves actually saw is over a
    volt. Any analysis grouping on vds_set_v inherits that error silently.
    """
    family = family_of(mosfet)
    target_set = family[0].v_set[len(family[0]) // 5]

    measured = []
    for curve in family:
        idx = min(range(len(curve)),
                  key=lambda i: abs(curve.v_set[i] - target_set))
        measured.append(curve.v[idx])

    spread = max(measured) - min(measured)
    assert spread > 0.5, (
        f"at one commanded {target_set:.3f} V the curves measured "
        f"{[f'{m:.3f}' for m in measured]}"
    )
    # And it is ordered: more gate drive, more current, more drop.
    assert measured == sorted(measured, reverse=True)


def test_slice_returns_one_point_per_curve_at_equal_measured_voltage(mosfet):
    family = family_of(mosfet)
    lo, hi = family.common_v_span()
    target = 0.5 * (lo + hi)

    points = family.slice_at(target)
    assert len(points) == len(family)
    assert [vgs for vgs, _ in points] == sorted(vgs for vgs, _ in points)
    # Current rises with gate voltage at fixed drain voltage.
    currents = [i for _, i in points]
    assert currents == sorted(currents)


def test_slice_interpolates_rather_than_snapping_to_a_row(mosfet):
    """A slice voltage between samples must not be rounded to a neighbour."""
    curve = family_of(mosfet)[-1]
    v, i = curve.v, curve.i_ma
    # Adjacent points often share an ADC count; find a pair that does not, so
    # the assertion is about interpolation and not about quantisation.
    idx = next(k for k in range(5, len(curve) - 1) if i[k + 1] > i[k])

    mid = 0.5 * (v[idx] + v[idx + 1])
    got = curve.i_at(mid)
    assert got is not None
    assert i[idx] < got < i[idx + 1]
    assert got == pytest.approx(0.5 * (i[idx] + i[idx + 1]))


def test_out_of_range_slice_returns_none_rather_than_extrapolating(mosfet):
    curve = family_of(mosfet)[0]
    assert curve.i_at(curve.v.max() + 1.0) is None
    assert curve.i_at(-1.0) is None


def test_common_span_is_bounded_by_the_highest_gate_curve(mosfet):
    """The curve drawing most current reaches the lowest measured voltage."""
    family = family_of(mosfet)
    _, hi = family.common_v_span()
    assert hi == pytest.approx(family[-1].v_span[1])
    assert hi < family[0].v_span[1]


def test_flagged_rows_are_excluded_from_the_family(ilimit_sweep):
    from ct_host.recompute import recompute
    sweep = recompute(ilimit_sweep)
    assert sweep.flagged_rows
    rows = [r for curve in family_of(sweep) for r in curve.rows]
    assert all(r.valid for r in rows)


# --------------------------------------------------------------------------
# The series-drop diagnostic
# --------------------------------------------------------------------------

def test_vds_delta_recovers_23_ohms(mosfet):
    # The default simulator models no PTC, so R_PTC is genuinely zero here.
    report = vds_delta_report(mosfet, r_ptc_ohm=0.0)
    assert report.fitted_r_ohm == pytest.approx(23.0, rel=0.02)
    assert report.verdict == "as designed"
    assert report.monotonic


def test_vds_delta_describes_itself(mosfet):
    text = vds_delta_report(mosfet, r_ptc_ohm=0.0).describe()
    assert "implied series R" in text
    assert "23.00 ohm" in text


def test_shorted_kelvin_leads_would_be_caught(mosfet):
    """Simulate the failure firmware/README.md warns about.

    If the sense leads were on the force node, vds_meas would equal vds_set
    and the delta would collapse to zero. The diagnostic must call that out
    rather than report a healthy instrument.
    """
    from dataclasses import replace
    faked = replace(mosfet, rows=[
        replace(r, vds_meas_v=r.vds_set_v, v_recomp_v=r.vds_set_v)
        for r in mosfet.rows
    ])
    report = vds_delta_report(faked)
    assert report.fitted_r_ohm is None or report.fitted_r_ohm < 1.0
    assert "Kelvin" in report.verdict
