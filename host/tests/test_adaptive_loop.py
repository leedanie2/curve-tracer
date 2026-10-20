"""The adaptive loop: seeds, stop reasons, safety filter, ordering, and the
evaluation harness on both its back ends."""

from __future__ import annotations

import numpy as np
import pytest

from ct_host.adaptive import acquire as A
from ct_host.adaptive.devices import mosfet_devices
from ct_host.adaptive.evaluate import Study, run_task
from ct_host.adaptive.loop import (STOP_REASONS, DesignConfig, run_adaptive,
                                   seed_plan)
from ct_host.adaptive.noise import NoiseModel
from ct_host.adaptive.oracle import SyntheticOracle
from ct_host.csvio import save

VGS = [2.3, 2.5, 2.7, 2.9, 3.1, 3.3]
NM = NoiseModel(0.5, 0.5)


def _oracle(name="sim-sq", **kw):
    return SyntheticOracle(mosfet_devices()[name], vgs_list=VGS, vds_max=10,
                           noise_lsb=0.5, seed=4, **kw)


def test_seeds_come_first_and_cover_every_gate_to_vds_max():
    o = _oracle()
    cfg = DesignConfig("mosfet", criterion="eig-phi", budget=60, compute_s=0.01)
    res = run_adaptive(o, cfg, NM, np.random.default_rng(0))
    seeds = sorted(seed_plan(o, "mosfet", 5))
    assert [(p.gate_index, p.code) for p in res.points[:len(seeds)]] == seeds
    top = o.fe.volts_to_code(10.0)
    assert {g for g, c in seeds if c == top} == set(range(len(VGS)))
    assert all(p.batch == 0 for p in res.points[:len(seeds)])


def test_control_device_stops_on_target():
    res = run_adaptive(_oracle(), DesignConfig("mosfet", budget=120, compute_s=0.01),
                       NM, np.random.default_rng(0))
    assert res.stop_reason == "target_met"
    assert res.assessment.stop
    assert res.stop_reason in STOP_REASONS


def test_spread_limited_device_runs_to_budget_and_says_why():
    res = run_adaptive(_oracle("sim-theta"),
                       DesignConfig("mosfet", k=12, budget=66, compute_s=0.01),
                       NM, np.random.default_rng(0))
    assert res.stop_reason == "budget"
    assert res.n_points == 66
    assert "vth" in res.rounds[-1].spread_limited


@pytest.mark.parametrize("criterion", A.CRITERIA)
def test_every_criterion_proposes_feasible_new_points(criterion):
    o = _oracle("sim-theta")
    res = run_adaptive(o, DesignConfig("mosfet", criterion=criterion, k=6, budget=42,
                                       alpha=0.5, compute_s=0.01),
                       NM, np.random.default_rng(0))
    assert res.n_points == 42
    proposed = [p for p in res.points if p.batch > 0]
    assert proposed
    # alpha = 0.5: nothing proposed may be predicted near 30 mA. Measured
    # currents can exceed the bound slightly; they must not approach 60.
    assert max(p.row.i_meas_ma for p in proposed) < 0.5 * 60.0 * 1.1
    assert not any(p.row.flags for p in res.points)


def test_a_trip_ends_the_session_with_the_drain_at_zero():
    o = _oracle(i_limit_ma=20.0)       # the seeds at 10 V on the top step trip it
    res = run_adaptive(o, DesignConfig("mosfet", budget=60, compute_s=0.01),
                       NM, np.random.default_rng(0))
    assert res.stop_reason == "ilimit"
    assert res.points[-1].row.flags == "ilimit"
    assert o.power_w == 0.0


def test_compute_time_is_charged_with_the_drain_at_zero():
    o = _oracle("sim-real")             # spread-limited: runs to its budget
    res = run_adaptive(o, DesignConfig("mosfet", budget=46, k=8, compute_s=0.5),
                       NM, np.random.default_rng(0))
    assert res.stop_reason == "budget"
    charged = o.breakdown.as_dict()["compute"]
    assert charged == pytest.approx(res.compute_s)
    assert charged == pytest.approx(0.5 * (len(res.rounds) + 1))   # + final assessment
    # Cooling happened: the junction ends far closer to ambient than its peak.
    assert o.tj_k < max(p.tj_k for p in o.history)


def test_orderings():
    cand = A.Candidates(np.array([2, 0, 2, 1]), np.array([900, 100, 300, 500]),
                        np.zeros((4, 2)), np.ones(4, bool), 0)
    picks = [0, 1, 2, 3]
    assert A.order_batch(cand, picks, "sorted") == [(0, 100), (1, 500), (2, 300), (2, 900)]
    assert A.order_batch(cand, picks, "acquisition") == [(2, 900), (0, 100), (2, 300), (1, 500)]
    inter = A.order_batch(cand, picks, "interleave")
    assert inter[0] == (2, 900) and inter[1] == (0, 100)
    with pytest.raises(ValueError):
        A.order_batch(cand, picks, "random")


def test_harness_runs_a_task_with_provenance():
    rows, traces = run_task(Study("sim-sq", 0.5, 0,
                                  designs=("dense", "ramp-8", "eig-phi"), budget=40))
    assert not any("error" in r for r in rows)
    designs = {r["design"] for r in rows}
    assert designs == {"dense", "ramp-8+gp", "ramp-8+raw", "eig-phi"}
    assert all(r["source"].startswith("synthetic sim-sq") for r in rows)
    eig = next(r for r in rows if r["design"] == "eig-phi")
    assert eig["stop_reason"] in STOP_REASONS
    assert eig["wall_s"] == pytest.approx(eig["instrument_s"] + eig["compute_s"])
    assert traces and {"value_vth", "dense_vth", "lin_sd_vth"} <= set(traces[0])


def test_harness_subsamples_a_dense_file(tmp_path, mosfet_sweep):
    """The bench path: a dense capture as a pool, by file name."""
    path = save(mosfet_sweep, tmp_path / "dense.csv", source="ct_sim test")
    rows, _ = run_task(Study("dense", 0.5, 0, designs=("dense", "ramp-8", "eig-phi"),
                             pool_csv=str(path), kind="mosfet", budget=60, tag="pool"))
    assert not any("error" in r for r in rows), [r.get("traceback") for r in rows]
    assert {r["design"] for r in rows} == {"dense", "ramp-8+gp", "ramp-8+raw", "eig-phi"}
    # No generative device behind a file: no truth-based metrics.
    eig = next(r for r in rows if r["design"] == "eig-phi")
    assert "recon_rmse_lsb" not in eig and "energy_mj" not in eig


def test_report_is_generated_from_results_alone(tmp_path):
    """Every number in report.md comes from results.csv; nothing is retyped."""
    import json

    import pandas as pd

    from ct_host.adaptive.report import write_report

    rows = []
    for seed in (0, 1):
        r, _ = run_task(Study("sim-sq", 0.5, seed, designs=("dense", "ramp-8", "eig-phi"),
                              budget=40))
        rows += r
    pd.DataFrame(rows).to_csv(tmp_path / "results.csv.gz", index=False)
    (tmp_path / "run.json").write_text(json.dumps({"tasks": 2}))
    text = write_report(tmp_path).read_text()
    assert "M1-M3 at noise 0.5 LSB" in text
    assert "Every result here is simulated" in text
    assert "PROVISIONAL" in text
    assert (tmp_path / "figures" / "time_to_dense.png").stat().st_size > 1000
    assert (tmp_path / "figures" / "lambda.png").stat().st_size > 1000
