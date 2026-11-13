"""The current channel's model: gain, zero, common-mode term, offset, floor.

Board 2's cap-only holds of 2026-11-13 read neither the zero nor 0 counts
but the difference stage's floor, which rises with node voltage. These tests
plant a known channel on the simulator and recover the device through it,
check that 2026-11-13's holds give the recorded model, and that a MOSFET
family whose lowest step conducts isn't taken for R_p alone.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from conftest import KNOWN_DIODE, run
from ct_host.channel import (BOARD2_FLOOR, ChannelModel, Floor, fit_channel,
                             read_model)
from ct_host.cli import main
from ct_host.csvio import parse
from ct_host.extract import extract_diode
from ct_host.parallel import ParallelR, auto_fit, subtract
from ct_host.protocol import SweepRequest
from ct_host.recompute import recompute
from ct_host.zero import apply_zero, resolve_zero

H4 = Path(__file__).resolve().parents[1] / "h4"
RESISTORS = [(H4 / "s3_23a_hold_100r_2v.csv", 100.0),
             (H4 / "s3_23b_hold_1k_2v.csv", 1000.0),
             (H4 / "s3_23c_hold_1k_6v.csv", 1000.0)]
FLOOR = [H4 / f for f in ("s3_22b_hold_0v2.csv", "s3_22c_hold_1v.csv",
                          "s3_22d_hold_6v.csv", "s3_22d3_hold_6v_clean.csv")]
CAL = H4 / "s3_22f_rp.csv"

#: A planted channel, near board 2's.
PLANTED = ChannelModel(gain=1.006, zero_ma=-0.13, cm_ma_per_v=-0.02,
                       v_offset_v=-0.010, floor=BOARD2_FLOOR, source="test",
                       stderr={})

DIODE = SweepRequest(device="sim-diode", n=100, vds_max=1.5, i_limit_ma=40,
                     vgs_list=[0])


def _read_through(sweep, model):
    """The same capture as read by a channel described by ``model``."""
    sweep = recompute(sweep)
    rows = [replace(r, i_recomp_ma=model.reading_ma(r.i_recomp_ma, r.v_recomp_v),
                    v_recomp_v=r.v_recomp_v + model.v_offset_v)
            for r in sweep.rows]
    return replace(sweep, rows=rows)


def _as_zero(model, path):
    return resolve_zero(str(model.write(path)))


# --------------------------------------------------------------------------
# Closed loop on the simulator
# --------------------------------------------------------------------------

def test_a_diode_read_through_the_channel_comes_back(tmp_path):
    raw = run(DIODE, dut="diode", noise=2, **KNOWN_DIODE)
    seen = _read_through(raw, PLANTED)
    params = extract_diode(apply_zero(seen, _as_zero(PLANTED, tmp_path / "m.txt")))
    assert params.n.value == pytest.approx(KNOWN_DIODE["n_diode"], rel=0.01)
    assert params.i_s.value == pytest.approx(KNOWN_DIODE["is_"], rel=0.15)


def test_rows_on_the_floor_are_flagged_and_left_out(tmp_path):
    raw = run(DIODE, dut="diode", noise=2, **KNOWN_DIODE)
    out = apply_zero(_read_through(raw, PLANTED), _as_zero(PLANTED, tmp_path / "m.txt"))
    floor = [r for r in out.rows if r.flags == "floor"]
    assert floor and all(r.v_dut < 0.62 for r in floor)
    assert all(r.flags != "floor" for r in out.valid_rows)


def test_without_the_model_the_floor_reads_as_current():
    """The 2026-11-13 failure: the floor taken as the zero bends the fit."""
    raw = run(DIODE, dut="diode", noise=2, **KNOWN_DIODE)
    seen = _read_through(raw, PLANTED)
    params = extract_diode(apply_zero(seen, resolve_zero("0.2168")))
    assert abs(params.n.value - KNOWN_DIODE["n_diode"]) > 0.1


def test_beside_a_calibration_line_only_gain_and_offset_apply(tmp_path):
    """The line already holds the zero and the common-mode term."""
    raw = run(DIODE, dut="diode", rpar=200, noise=2, **KNOWN_DIODE)
    seen = _read_through(raw, PLANTED)
    # What a calibration capture of the 200 ohm alone would fit, through the
    # same channel: slope g G + c, offset b - delta (g G + c - c).
    g_p = PLANTED.gain / 200.0 * 1000.0
    slope = g_p + PLANTED.cm_ma_per_v
    line = ParallelR(1000.0 / slope, None, "calibration", "test",
                     PLANTED.zero_ma - PLANTED.v_offset_v * g_p)
    z = replace(_as_zero(PLANTED, tmp_path / "m.txt"), in_line=True)
    params = extract_diode(apply_zero(subtract(seen, line), z))
    assert params.n.value == pytest.approx(KNOWN_DIODE["n_diode"], rel=0.01)


def test_the_model_file_round_trips(tmp_path):
    back = read_model(PLANTED.write(tmp_path / "m.txt"))
    fields = ("gain", "zero_ma", "cm_ma_per_v", "v_offset_v")
    assert [getattr(back, f) for f in fields] == [getattr(PLANTED, f) for f in fields]
    assert (back.floor.ma, back.floor.ma_per_v, back.floor.margin_ma) == pytest.approx(
        (PLANTED.floor.ma, PLANTED.floor.ma_per_v, PLANTED.floor.margin_ma), abs=1e-5)


# --------------------------------------------------------------------------
# 2026-11-13, board 2
# --------------------------------------------------------------------------

def test_the_11_13_holds_give_the_recorded_model():
    fit = fit_channel(RESISTORS, FLOOR, calibration=CAL)
    flat = fit.no_offset
    assert (flat.gain, flat.zero_ma, flat.cm_ma_per_v) == pytest.approx(
        (1.0080, -0.1310, -0.0225), abs=2e-4)
    m = fit.model
    assert m.v_offset_v == pytest.approx(-0.0101, abs=2e-4)
    assert m.gain == pytest.approx(1.0014, abs=2e-4)
    assert (m.floor.ma, m.floor.ma_per_v) == pytest.approx(
        (BOARD2_FLOOR.ma, BOARD2_FLOOR.ma_per_v), abs=2e-4)


def test_the_floor_matches_11_03_s_open_load_holds():
    """0.830 and 0.832 mA at 6.006 V: the floor, read again ten days later."""
    for name in ("mvp_09_hold_open.csv", "mvp_09c_hold_open.csv"):
        hold = recompute(parse((H4 / name).read_text()))
        rows = hold.valid_rows
        i = sum(r.i_total_ma for r in rows) / len(rows)
        v = sum(r.v_meas for r in rows) / len(rows)
        assert i == pytest.approx(BOARD2_FLOOR.at(v), abs=0.010)


def test_the_cap_only_diode_through_the_model(tmp_path, capsys):
    out = tmp_path / "m.txt"
    assert main(["channel", *[a for p, ohm in RESISTORS
                              for a in ("--resistor", f"{p}={ohm:g}")],
                 "--floor", ",".join(map(str, FLOOR)), "--calibration", str(CAL),
                 "-o", str(out)]) == 0
    capsys.readouterr()
    assert main(["extract", str(H4 / "s3_24_diode.csv"), "--type", "diode",
                 "--zero", str(out)]) == 0
    got = capsys.readouterr()
    assert "39 rows on the channel's floor" in got.err
    n = float(got.out.split("n      = ")[1].split()[0])
    assert n == pytest.approx(1.949, abs=0.002)


def test_a_floor_is_a_line_in_node_voltage():
    f = Floor(0.2, 0.1)
    assert f.holds(0.25, 0.2) and not f.holds(0.40, 0.2)
    assert f.holds(0.75, 6.0)


# --------------------------------------------------------------------------
# R_p's cross-check on a MOSFET family
# --------------------------------------------------------------------------

def test_a_conducting_lowest_step_is_not_taken_for_r_p():
    """2026-11-13: 2.45 V conducts; its line read R 12% low, offset +4 mA."""
    fit, reason = auto_fit(recompute(parse((H4 / "s3_25_mosfet.csv").read_text())))
    assert fit is None and "conducts" in reason


def test_an_off_lowest_step_still_cross_checks():
    """2026-11-08: 1.5 V is off; its line is L1 to -0.15%."""
    fit, _ = auto_fit(recompute(parse((H4 / "mvp_18_mosfet_rp.csv").read_text())))
    assert fit is not None
    assert fit.r.value == pytest.approx(201.01, abs=0.05)
