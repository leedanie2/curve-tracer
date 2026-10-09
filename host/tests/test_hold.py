"""HOLD against the simulator: the protocol driver and the ``hold`` command.

The firmware side is tested in ``firmware/tests/test_hold.c``. These tests
check what the host must get right: it ends the hold, it reads the whole
block, and it leaves the link clean, so the next command on the same
transport behaves. The simulator's clock is simulated, so a "second" of hold
costs microseconds here.
"""

from __future__ import annotations

import pytest

from ct_host.cli import main
from ct_host.csvio import parse
from ct_host.protocol import (
    CommandError,
    SweepRequest,
    identify,
    run_hold,
    run_sweep,
)
from ct_host.transport import SimTransport

R_LOAD = 1000.0


def test_hold_holds_the_level_and_stops_on_request():
    with SimTransport(dut="resistor", rload=R_LOAD) as t:
        hold = run_hold(t, 5.0, SweepRequest(vgs_list=[0.0]), rows=3)

    assert hold.end_reason == "stopped"
    assert hold.meta["mode"] == "hold"
    assert hold.meta["hold_vds_set_v"] == "5.000"
    assert len(hold.rows) >= 3
    assert all(r.vds_set_v == pytest.approx(5.0, abs=0.003) for r in hold.rows)
    assert all(r.valid for r in hold.rows)
    # 5 V across the 1 kohm load and the ~23 ohm front end.
    assert hold.rows[0].i_meas_ma == pytest.approx(5.0 / (R_LOAD + 23.0) * 1e3,
                                                   rel=0.02)


def test_the_link_is_clean_after_a_hold():
    """The STOP acknowledgement is consumed, so the next command is not
    confused by a stray ``# stop:`` line."""
    with SimTransport(dut="resistor", rload=R_LOAD) as t:
        run_hold(t, 5.0, SweepRequest(vgs_list=[0.0]), rows=2)
        ident = identify(t)
        sweep = run_sweep(t, SweepRequest(n=5, vds_max=2.0, vgs_list=[0.0]))

    assert "fw" in ident and "stop" not in ident
    assert sweep.end_reason == "ok"
    assert len(sweep.rows) == 5
    assert sweep.meta["mode"] == "dc"


def test_hold_trips_the_limit_by_itself():
    """No STOP is needed: the firmware zeroes the drain, flags the row, ends."""
    with SimTransport(dut="resistor", rload=50.0) as t:
        hold = run_hold(t, 5.0, SweepRequest(vgs_list=[0.0], i_limit_ma=10.0),
                        rows=1000)
        after = identify(t)

    assert hold.end_reason == "ilimit"
    assert hold.rows[-1].flags == "ilimit"
    assert all(r.valid for r in hold.rows[:-1])
    assert "fw" in after


def test_ambiguous_gate_is_rejected():
    with SimTransport(dut="resistor", rload=R_LOAD) as t:
        with pytest.raises(CommandError, match="exactly one entry"):
            run_hold(t, 5.0, SweepRequest(vgs_list=[2.5, 3.0]), rows=1)


def test_out_of_range_level_is_rejected():
    with SimTransport(dut="resistor", rload=R_LOAD) as t:
        with pytest.raises(CommandError, match="out of range"):
            run_hold(t, 11.5, SweepRequest(vgs_list=[0.0]), rows=1)


def test_seconds_bound_ends_the_hold():
    ticks = iter([0.0, 0.5, 1.0, 1.5, 2.0, 2.5] + [9.0] * 1000)
    with SimTransport(dut="resistor", rload=R_LOAD) as t:
        hold = run_hold(t, 3.0, SweepRequest(vgs_list=[0.0]), seconds=2.0,
                        clock=lambda: next(ticks))
    assert hold.end_reason == "stopped"
    assert len(hold.rows) >= 5        # rows at clock 0, 0.5 ... 2.0


def test_hold_needs_an_end_condition():
    with SimTransport(dut="resistor", rload=R_LOAD) as t:
        with pytest.raises(ValueError):
            run_hold(t, 5.0)


def test_hold_command_writes_a_parseable_file(tmp_path):
    out = tmp_path / "hold.csv"
    code = main(["hold", "--sim", "resistor", "--sim-rload", "1000",
                 "--vds", "5", "--vgs", "0", "--seconds", "0",
                 "--device", "HOLDTEST", "-o", str(out)])
    assert code == 0

    saved = parse(out.read_text(), require_end=True)
    assert saved.end_reason == "stopped"
    assert saved.meta["mode"] == "hold"
    assert saved.meta.device == "HOLDTEST"
    assert saved.meta["host_source"].startswith("ct_sim")
    assert len(saved.rows) >= 1
