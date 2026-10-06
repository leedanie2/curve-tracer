"""The Kelvin divider's current, and the series-drop diagnostic's R_PTC.

Blueprint §3.4: the ÷4 divider (300k/100k) sits across the DUT, on the DUT
side of the shunt, so the shunt carries ``I_DUT + V_DS / 400k``. Firmware
schema 2 subtracts the second term; these tests check that it does, that the
host's recomputation does the same, and that leaving it out is detectably
wrong -- a correction nobody can tell is missing is the failure mode
blueprint §11 records twice.

The load is a 40 kohm resistor so the divider's share is 10% of the shunt
current: 25 uA against 250 uA at 10 V. On range 1 that is 0.6 of an LSB, so
the simulator dithers and the sweep oversamples, which is also how the real
board resolves it.
"""

from __future__ import annotations

import numpy as np
import pytest

from conftest import run
from ct_host.dataset import vds_delta_report
from ct_host.protocol import SweepRequest
from ct_host.recompute import Calibration, recompute

R_LOAD = 40_000.0


@pytest.fixture(scope="module")
def resistor_sweep():
    return recompute(run(
        SweepRequest(device="sim-40k", n=40, vds_max=10, oversample_n=1024,
                     i_limit_ma=165, vgs_list=[0.0]),
        dut="resistor", rload=R_LOAD, noise=1.0,
    ))


def _fit_resistance(v, i_ma):
    """Least-squares R through the origin, from V and I in mA."""
    i_a = np.asarray(i_ma) / 1000.0
    v = np.asarray(v)
    return float(np.dot(v, v) / np.dot(v, i_a))


def test_header_carries_the_divider_resistance(resistor_sweep):
    cal = Calibration.from_sweep(resistor_sweep)
    assert resistor_sweep.meta.require("schema") == "2"
    assert cal.rdiv_ohm == pytest.approx(400_000.0)


def test_correction_fires(resistor_sweep):
    """Firmware's i_meas_ma is the shunt current less exactly V_DS / rdiv."""
    cal = Calibration.from_sweep(resistor_sweep)
    rows = [r for r in resistor_sweep.valid_rows if r.vds_meas_v > 1.0]
    assert len(rows) > 20
    for r in rows:
        shunt = cal.shunt_current_ma(r.i_acc)
        divider = cal.voltage_v(r.v_acc) / cal.rdiv_ohm * 1000.0
        assert divider > 0.0025                      # >= 2.5 uA at > 1 V
        assert r.i_meas_ma == pytest.approx(shunt - divider, abs=2e-4)
        assert r.i_recomp_ma == pytest.approx(shunt - divider, abs=1e-9)


def test_corrected_sweep_recovers_the_load(resistor_sweep):
    rows = [r for r in resistor_sweep.valid_rows if r.vds_meas_v > 1.0]
    fitted = _fit_resistance([r.v_dut for r in rows], [r.i_ma for r in rows])
    assert fitted == pytest.approx(R_LOAD, rel=0.02)


def test_uncorrected_sweep_is_detectably_wrong(resistor_sweep):
    """Without the subtraction, 40k reads as 40k || 400k = 36.4k: 9% low."""
    cal = Calibration.from_sweep(resistor_sweep)
    rows = [r for r in resistor_sweep.valid_rows if r.vds_meas_v > 1.0]
    uncorrected = [cal.shunt_current_ma(r.i_acc) for r in rows]
    fitted = _fit_resistance([r.v_dut for r in rows], uncorrected)
    parallel = 1.0 / (1.0 / R_LOAD + 1.0 / cal.rdiv_ohm)
    assert fitted == pytest.approx(parallel, rel=0.02)
    assert (R_LOAD - fitted) / R_LOAD > 0.05


# --------------------------------------------------------------------------
# vds_delta_report and R_PTC
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ptc_sweep():
    """A MOSFET family with a 5 ohm PTC in the drain path."""
    return recompute(run(
        SweepRequest(device="sim-ptc", n=40, vds_max=10, i_limit_ma=165,
                     vgs_list=[3.0, 3.4, 3.8]),
        dut="mosfet", rptc=5.0,
    ))


def test_firmware_reports_r_ptc_as_unset_until_measured(ptc_sweep):
    assert ptc_sweep.meta.require("cal_r_ptc_ohm") == "unset"
    assert Calibration.from_sweep(ptc_sweep).r_ptc_ohm is None


def test_unset_r_ptc_says_to_measure_it(ptc_sweep):
    report = vds_delta_report(ptc_sweep)
    assert "measure R_PTC at bring-up" in report.verdict
    assert report.implied_r_ptc_ohm == pytest.approx(5.0, abs=0.5)
    assert "inside" in report.verdict


def test_measured_r_ptc_makes_the_check_tight(ptc_sweep):
    report = vds_delta_report(ptc_sweep, r_ptc_ohm=5.0)
    assert report.expected_r_ohm == pytest.approx(28.0)
    assert report.fitted_r_ohm == pytest.approx(28.0, rel=0.02)
    assert report.verdict == "as designed"


def test_stale_r_ptc_is_flagged(ptc_sweep):
    """A PTC that has moved since it was measured shows as a mismatch."""
    report = vds_delta_report(ptc_sweep, r_ptc_ohm=15.0)
    assert report.verdict != "as designed"
