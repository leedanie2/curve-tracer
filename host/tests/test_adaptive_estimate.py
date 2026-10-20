"""Reported parameters: pushforward, spreads, cross-check, linearisation.

The linearisation is derived by hand from what the extractor does and is
used only to choose points; it is held to finite differences of the *real*
extractor here, so the two cannot drift apart unnoticed.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from ct_host.adaptive import estimate as E
from ct_host.adaptive.devices import diode_devices, mosfet_devices
from ct_host.adaptive.noise import NoiseModel
from ct_host.adaptive.oracle import SyntheticOracle

VGS = [2.3, 2.5, 2.7, 2.9, 3.1, 3.3]


def _setup(name, n=20, noise=0.5, seed=2):
    dev = {**mosfet_devices(), **diode_devices()}[name]
    if dev.kind == "mosfet":
        o = SyntheticOracle(dev, vgs_list=VGS, vds_max=10, noise_lsb=noise, seed=seed)
    else:
        o = SyntheticOracle(dev, vgs_list=[0], vds_max=2.0, noise_lsb=noise, seed=seed)
    pts = o.sweep(n).points
    gp = E.fit_gp(o, pts, dev.kind, NoiseModel(noise, noise))
    return o, pts, gp, dev.kind


@pytest.mark.parametrize("name", ["sim-sq", "sim-theta", "sim-diode", "sim-diode2"])
def test_linearisation_matches_finite_differences_of_the_extractor(name):
    o, pts, gp, kind = _setup(name, n=20 if "diode" not in name else 30)
    targets = E.MOSFET_TARGETS if kind == "mosfet" else E.DIODE_TARGETS
    names = tuple(targets)
    a, grid, ms = E.assess(gp, o, pts, kind, targets, n_dense=200,
                           r_ser=E.series_resistance(o, pts),
                           rng=np.random.default_rng(0), stage="mean")
    G = E.linearise(ms, grid, kind, names)
    base_vals = (np.array([r.i_ma for r in ms.rows]) if kind == "mosfet"
                 else np.array([r.v_dut for r in ms.rows]))
    active = np.where(np.abs(G).sum(0) > 0)[0]
    rng = np.random.default_rng(1)
    for j in rng.choice(active, size=min(15, active.size), replace=False):
        h = 1e-5 * max(abs(base_vals[j]), 1e-3)
        up, dn = base_vals.copy(), base_vals.copy()
        up[j] += h; dn[j] -= h
        ru = E.extract_values(E.grid_sweep(o, grid, up, kind), kind)
        rd = E.extract_values(E.grid_sweep(o, grid, dn, kind), kind)
        fd = np.array([(ru[k] - rd[k]) / (2 * h) for k in names])
        scale = np.abs(G).max(1)
        assert np.all(np.abs(fd - G[:, j]) <= 1e-2 * scale), (name, j)


def test_pushforward_reaches_the_dense_values_on_the_control():
    o, pts, gp, kind = _setup("sim-sq", n=24)
    a, _, _ = E.assess(gp, o, pts, kind, E.MOSFET_TARGETS, n_dense=200,
                       r_ser=E.series_resistance(o, pts),
                       rng=np.random.default_rng(0), stage="full", n_samples=32)
    od = SyntheticOracle(mosfet_devices()["sim-sq"], vgs_list=VGS, vds_max=10,
                         noise_lsb=0.5, seed=2)
    ref = E.reference(od.as_sweep(od.sweep(200).points), "mosfet", od.fe.i_lsb_ma)
    for k in E.MOSFET_TARGETS:
        p = a.params[k]
        assert abs(p.value - ref[k].value) <= 2.0 * math.hypot(p.u, ref[k].u), k


def test_every_gated_parameter_reports_both_numbers():
    o, pts, gp, kind = _setup("sim-sq", n=16)
    a, _, _ = E.assess(gp, o, pts, kind, E.MOSFET_TARGETS, n_dense=200,
                       r_ser=E.series_resistance(o, pts),
                       rng=np.random.default_rng(0), stage="full", n_samples=16)
    for k in E.MOSFET_TARGETS:
        assert a.params[k].stderr is not None and a.params[k].stderr > 0
        assert a.params[k].spread is not None
        assert a.params[k].raw_value is not None


def test_spread_limited_device_is_blocked_on_its_spread():
    """With theta = 0.2, V_th depends on the fit range by ~+-20 mV: no design
    can meet a 2 mV target, and the rule must say why rather than stop."""
    o, pts, gp, kind = _setup("sim-theta", n=24)
    a, _, _ = E.assess(gp, o, pts, kind, E.MOSFET_TARGETS, n_dense=200,
                       r_ser=E.series_resistance(o, pts),
                       rng=np.random.default_rng(0), stage="full", n_samples=16)
    assert not a.stop
    assert any(b.startswith("vth:") and "half-spread" in b for b in a.blocking)
    assert a.params["vth"].spread / 2 > 10e-3


def test_series_resistance_absorbs_an_unmeasured_ptc():
    dev = mosfet_devices()["sim-sq"]
    from ct_host.adaptive.frontend import FrontEnd
    o = SyntheticOracle(dev, fe=FrontEnd(r_ptc=6.0), vgs_list=VGS, vds_max=10)
    pts = o.sweep(20).points
    assert E.series_resistance(o, pts) == pytest.approx(22 + 1 + 6, abs=0.1)


def test_param_result_rules():
    p = E.ParamResult("vth", 2.15, 0.001, 0.003, raw_value=2.1505, raw_stderr=0.001,
                      target=0.002)
    assert p.u == pytest.approx(math.hypot(0.001, 0.0015))
    assert p.meets_target
    assert p.crosscheck_ok
    assert not E.ParamResult("vth", 2.15, 0.001, 0.005, target=0.002).meets_target
    far = E.ParamResult("vth", 2.15, 0.001, 0.0, raw_value=2.2, raw_stderr=0.001)
    assert far.crosscheck_ok is False
    assert E.ParamResult("vth", 2.15, 0.001, 0.0).crosscheck_ok is None
