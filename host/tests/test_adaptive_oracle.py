"""The synthetic instrument: held to ct_sim, and to the firmware's ordering.

The offline evaluation runs on a Python model of the signal chain. If that
model drifted from ct_sim -- which *is* firmware/core/ -- every conclusion
drawn from it would be about a different instrument. So the controls are
compared count for count, and the current-limit ordering of the proposed
points session is asserted the way test_sweep.c asserts the sweep's.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from conftest import KNOWN_DIODE, KNOWN_MOSFET, run
from ct_host.adaptive.devices import (Diode, Mosfet, diode_devices,
                                      mosfet_devices)
from ct_host.adaptive.frontend import FrontEnd
from ct_host.adaptive.oracle import PT_LINE_MAX, PoolOracle, ProtocolError, SyntheticOracle
from ct_host.csvio import save
from ct_host.protocol import SweepRequest

VGS = [2.6, 2.8, 3.0, 3.2, 3.4, 3.6]


@pytest.fixture(scope="module")
def ct_sim_mosfet():
    return run(SweepRequest(device="sim-mosfet", n=200, vds_max=10, i_limit_ma=165,
                            vgs_list=VGS), dut="mosfet", **KNOWN_MOSFET)


def _twin_counts(dev, req):
    o = SyntheticOracle(dev, vgs_list=req.vgs_list, vds_max=req.vds_max,
                        i_limit_ma=req.i_limit_ma)
    return o, o.sweep(req.n)


def test_mosfet_twin_matches_ct_sim_count_for_count(ct_sim_mosfet):
    _, cap = _twin_counts(Mosfet(), SweepRequest(n=200, vds_max=10, i_limit_ma=165,
                                                 vgs_list=VGS))
    c = np.array([(r.i_acc, r.v_acc) for r in ct_sim_mosfet.rows])
    p = np.array([(r.i_acc, r.v_acc) for r in cap.rows])
    assert c.shape == p.shape
    assert np.array_equal(c[:, 0], p[:, 0])
    # float32 (C) against float64 (here) can land on opposite sides of a
    # rounding tie; then every one of the 64 samples moves by one code.
    diff = np.abs(c[:, 1] - p[:, 1])
    assert set(np.unique(diff)) <= {0, 64}
    assert np.count_nonzero(diff) <= 2


def test_diode_twin_matches_ct_sim_count_for_count():
    sw = run(SweepRequest(device="sim-diode", n=300, vds_max=3.0, i_limit_ma=165,
                          vgs_list=[0]), dut="diode", **KNOWN_DIODE)
    _, cap = _twin_counts(Diode(), SweepRequest(n=300, vds_max=3.0, i_limit_ma=165,
                                                vgs_list=[0]))
    assert [(r.i_acc, r.v_acc) for r in sw.rows] == [(r.i_acc, r.v_acc) for r in cap.rows]


def test_rendered_header_is_ct_sims(ct_sim_mosfet):
    o = SyntheticOracle(Mosfet(), vgs_list=VGS, vds_max=10, i_limit_ma=165)
    ours = o.header_lines("dc", 200)
    theirs = [ln for ln in ct_sim_mosfet.raw_text.splitlines()
              if ln.startswith("#") and not ln.startswith(("# end", "# host"))]
    theirs.append(ct_sim_mosfet.raw_text.splitlines()[len(theirs)])  # column line
    assert [ln.replace("sim-sq", "sim-mosfet") for ln in ours] == theirs
    # The figure the plan quotes (F2, corrected): 30 lines, 741 bytes.
    assert len(ours) == 30
    assert sum(len(ln) + 2 for ln in ours) == 741


def test_every_departure_moves_the_curve():
    """Blueprint §11: a parameter that changes nothing is not wired up."""
    fe = FrontEnd()
    # One gate step well above threshold and one just above it: the
    # subthreshold-tail device departs only within ~0.2 V of V_th, by design.
    vgs = np.repeat([2.25, 3.1], 50)
    v = np.tile(np.linspace(0.5, 9.0, 50), 2)
    base = fe.terminal_current(Mosfet(), vgs, v)
    for name, dev in mosfet_devices().items():
        if name in ("sim-sq", "sim-heat"):
            continue
        assert np.max(np.abs(fe.terminal_current(dev, vgs, v) - base)) > 1e-5, name
    d0 = fe.terminal_current(Diode(), 0.0, np.linspace(0.5, 0.9, 20))
    d2 = fe.terminal_current(diode_devices()["sim-diode2"], 0.0, np.linspace(0.5, 0.9, 20))
    assert np.max(np.abs(d2 - d0)) > 1e-6


def test_a_departure_at_zero_is_the_control():
    fe = FrontEnd()
    vgs, v = np.full(30, 3.0), np.linspace(0.1, 9.0, 30)
    zero = replace(Mosfet(), theta=0.0, r_s=0.0, r_d=0.0)
    assert np.array_equal(fe.terminal_current(zero, vgs, v),
                          fe.terminal_current(Mosfet(), vgs, v))


def test_heating_device_heats_and_a_zero_network_does_not():
    heat = mosfet_devices()["sim-heat"]
    o = SyntheticOracle(heat, vgs_list=VGS, vds_max=10, i_limit_ma=165)
    cap = o.sweep(100)
    assert max(p.tj_k for p in cap.points) > 310.0
    cold = SyntheticOracle(heat, vgs_list=VGS, vds_max=10, i_limit_ma=165,
                           thermal_scale=0.0)
    ref = SyntheticOracle(Mosfet(), vgs_list=VGS, vds_max=10, i_limit_ma=165)
    assert ([r.i_acc for r in cold.sweep(100).rows]
            == [r.i_acc for r in ref.sweep(100).rows])


def test_dense_sweep_dwell_changes_when_the_tx_ring_fills():
    """Plan F4: ~1.14 ms per point until the 4 KB ring fills, then ~4 ms."""
    o = SyntheticOracle(Mosfet(), vgs_list=VGS, vds_max=10, i_limit_ma=165)
    pts = o.sweep(200).points
    dwell = np.array([p.dwell_s for p in pts[:199]]) * 1000.0
    assert dwell[5] == pytest.approx(1.142, abs=0.01)
    first_slow = int(np.argmax(dwell > 2.0))
    assert 80 <= first_slow <= 120
    assert np.median(dwell[150:199]) == pytest.approx(4.0, abs=0.4)


def test_points_session_zeroes_the_drain_before_the_flagged_row():
    o = SyntheticOracle(Mosfet(), vgs_list=VGS, vds_max=10, i_limit_ma=20.0)
    o.open_points()
    code = o.fe.volts_to_code(9.0)
    cap = o.points([(0, o.fe.volts_to_code(1.0)), (5, code), (5, code)], batch=1)
    assert cap.end_reason == "ilimit"
    assert [p.row.flags for p in cap.points] == ["", "ilimit"]
    tripped = cap.points[-1]
    # Power went to zero at the end of the measurement, before the row's
    # bytes were queued: the dwell at the over-limit bias is the measurement.
    assert tripped.dwell_s == pytest.approx(o.link.measure_s(o.fe.settle_us), rel=1e-9)
    assert o.power_w == 0.0
    assert not o.session_open and o.session_ended == "ilimit"
    with pytest.raises(ProtocolError):
        o.points([(0, 10)], batch=2)


def test_a_bad_line_is_rejected_before_any_measurement():
    o = SyntheticOracle(Mosfet(), vgs_list=VGS, vds_max=5, i_limit_ma=60)
    o.open_points()
    before = len(o.history)
    for plan in ([(0, 10), (6, 10)], [(0, 10), (0, o.max_code + 1)], [(-1, 5)]):
        with pytest.raises(ProtocolError):
            o.points(plan, batch=1)
        assert len(o.history) == before
    assert o.session_open


def test_pt_lines_fit_the_command_buffer():
    plan = [(g, c) for g in range(6) for c in range(3000, 3080, 2)]
    lines = SyntheticOracle.pt_lines(plan)
    assert [pc for ln in lines for pc in ln] == plan
    for ln in lines:
        assert len("PT" + "".join(f" {g}:{c}" for g, c in ln)) <= PT_LINE_MAX


def test_points_rows_carry_batch_and_time():
    o = SyntheticOracle(Mosfet(), vgs_list=VGS, vds_max=10, i_limit_ma=60)
    o.open_points()
    cap = o.points([(1, 500), (1, 1500)], batch=3)
    fields = [p.row.raw.split(",") for p in cap.points]
    assert all(len(f) == 11 for f in fields)
    assert [f[9] for f in fields] == ["3", "3"]
    assert int(fields[1][10]) > int(fields[0][10]) >= 0


def test_pool_oracle_serves_only_what_the_file_holds(tmp_path, mosfet_sweep):
    path = save(mosfet_sweep, tmp_path / "dense.csv", source="ct_sim test")
    o = PoolOracle(path)
    assert o.device_name == "sim-mosfet"
    codes = o.available_codes(0)
    assert codes.size == 60
    o.open_points()
    cap = o.points([(0, int(codes[10])), (2, int(codes[40]))], batch=1)
    assert cap.rows[0].i_acc == o.pool[(0, int(codes[10]))].i_acc
    with pytest.raises(ProtocolError):
        o.points([(0, int(codes[10]) + 1)], batch=2)
    o.close_points()
    ramp = o.sweep(20)
    assert len(ramp.points) == 6 * 20
