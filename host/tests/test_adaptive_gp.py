"""Noise model, GP algebra, and the mismatch statistic.

The noise model is checked against a Monte-Carlo quantiser, the GP against
closed forms it must reduce to, and the batch-selection shortcut (rank-one
updates) against refitting with the point actually added.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from scipy.optimize import least_squares

from ct_host.adaptive import estimate as E
from ct_host.adaptive.devices import mosfet_devices
from ct_host.adaptive.gp import PhysGP
from ct_host.adaptive.models import DiodeMean, MosfetMean
from ct_host.adaptive.noise import NoiseModel, mean_error_var_lsb2, rho
from ct_host.adaptive.oracle import SyntheticOracle

VGS = [2.3, 2.5, 2.7, 2.9, 3.1, 3.3]


# --------------------------------------------------------------------------
# Noise
# --------------------------------------------------------------------------

def test_no_dither_means_no_benefit_from_oversampling():
    assert rho(0.0) == 1.0
    assert mean_error_var_lsb2(0.0, 64) == pytest.approx(1.0 / 12.0)
    assert mean_error_var_lsb2(0.0, 1) == pytest.approx(1.0 / 12.0)


def test_plenty_of_dither_gives_the_textbook_result():
    s = 2.0
    assert mean_error_var_lsb2(s, 64) == pytest.approx((s * s + 1 / 12) / 64, rel=1e-6)


@pytest.mark.parametrize("sigma", [0.0, 0.1, 0.3, 1.0])
def test_noise_model_matches_a_monte_carlo_quantiser(sigma):
    rng = np.random.default_rng(7)
    x = rng.uniform(0.0, 500.0, 20000)
    n = 64
    samples = x[:, None] + (rng.normal(0.0, sigma, (x.size, n)) if sigma else 0.0)
    err = np.floor(samples + 0.5).mean(1) - x
    assert err.var() == pytest.approx(mean_error_var_lsb2(sigma, n), rel=0.05)


def test_voltage_error_dominates_in_triode():
    """Plan F8: 1/(k V_ov) = 12.5 ohm makes the voltage channel ~6x worse."""
    nm = NoiseModel(0.0, 0.0)
    slope = 1000.0 / 12.54                       # mA/V
    ratio = math.sqrt(nm.current_var(slope) / nm.current_var(0.0))
    assert ratio == pytest.approx(6.5, abs=0.1)


# --------------------------------------------------------------------------
# GP
# --------------------------------------------------------------------------

def _ramp(name, n=12, noise=0.5, seed=1):
    o = SyntheticOracle(mosfet_devices()[name], vgs_list=VGS, vds_max=10,
                        noise_lsb=noise, seed=seed)
    pts = o.sweep(n).points
    X = o.inputs(pts)
    y = np.array([r.i_ma for r in o.as_sweep(pts).rows])
    return o, pts, X, y


def test_with_the_residual_off_gls_is_weighted_least_squares():
    _, _, X, y = _ramp("sim-sq")
    nm = NoiseModel(0.5, 0.5)
    h = np.log(np.array([1e-6, 1e-6, 0.5, 2.0, 1.0]))
    gp = PhysGP(MosfetMean(), X, y, nm, hyper=h).fit(optimise_hyper=False)
    m = MosfetMean()
    w = lambda t: 1.0 / np.sqrt(m.noise_var(t, X, y, nm))       # noqa: E731
    ls = least_squares(lambda t: (m.mean(t, X) - y) * w(gp.theta), gp.theta,
                       xtol=1e-14, ftol=1e-14)
    assert gp.theta == pytest.approx(ls.x, rel=1e-5)


def test_diode_model_is_exactly_linear():
    rng = np.random.default_rng(3)
    u = np.linspace(math.log(1e-4), math.log(5e-2), 30)[:, None]
    theta = np.array([0.045, 0.88, 0.6])
    y = DiodeMean().mean(theta, u) + rng.normal(0, 1e-4, 30)
    gp = PhysGP(DiodeMean(), u, y, NoiseModel(1.0, 1.0)).fit()
    ols, *_ = np.linalg.lstsq(DiodeMean().jac(None, u), y, rcond=None)
    assert gp.theta == pytest.approx(ols, rel=0.02, abs=2e-3)


def test_theta_recovered_on_the_control_device():
    _, _, X, y = _ramp("sim-sq", n=20)
    gp = PhysGP(MosfetMean(), X, y, NoiseModel(0.5, 0.5)).fit()
    vth, beta, lam = gp.theta
    sd = np.sqrt(np.diag(gp.sigma_theta))
    assert abs(vth - 2.15) < 4 * sd[0] + 1e-4
    assert abs(beta - 0.0275) < 4 * sd[1] + 1e-6
    assert abs(lam - 0.012) < 4 * sd[2] + 1e-5


def test_marginal_residual_sd_is_at_least_the_conditional():
    o, _, X, y = _ramp("sim-theta")
    gp = PhysGP(MosfetMean(), X, y, NoiseModel(0.5, 0.5)).fit()
    _, sd_m = gp.residual(X)
    _, sd_c = gp.residual(X, given_theta=True)
    assert np.all(sd_m >= sd_c - 1e-12)


def test_rank_one_update_equals_refitting_with_the_point():
    """y-independence: the variance after observing x does not depend on what
    was observed, so the greedy batch can update without measuring."""
    o, _, X, y = _ramp("sim-sq", n=10)
    nm = NoiseModel(0.5, 0.5)
    gp = PhysGP(MosfetMean(), X, y, nm).fit()
    Xc = np.array([[2.7, 3.0], [2.7, 3.2], [3.1, 6.0], [2.5, 8.0]])
    _, v = gp.predict(Xc)
    s = v[0] + gp.noise_var_at(Xc[:1])[0]
    col = gp.cross_cov(Xc, Xc[:1])[:, 0]
    v_upd = v - col * col / s

    mu0, _ = gp.predict(Xc[:1])
    X2 = np.vstack([X, Xc[:1]])
    y2 = np.append(y, mu0)
    # same hyperparameters; noise scale folded into the per-point variance
    gp2 = PhysGP(MosfetMean(), X2, y2, nm, hyper=gp.h, theta=gp.st.theta)
    gp2.fit(optimise_hyper=False)
    _, v2 = gp2.predict(Xc)
    assert v2 == pytest.approx(v_upd, rel=0.02, abs=1e-9)


def test_mismatch_statistic_separates_control_from_mismatch():
    lam = {}
    for name in ("sim-sq", "sim-theta"):
        _, _, X, y = _ramp(name, n=16)
        lam[name] = PhysGP(MosfetMean(), X, y, NoiseModel(0.5, 0.5)).fit().mismatch_statistic()
    assert lam["sim-sq"] < 10.0
    assert lam["sim-theta"] > 100.0


def test_exact_gate_voltage_not_the_csv_rounding():
    """Rounding V_GS to 1 mV made the control device look mismatched (it moves
    V_ov by up to 0.5 mV, 1-2 LSB at the top step). The inputs use the DAC's
    exact voltage, and the control's statistic stays null."""
    o, pts, X, y = _ramp("sim-sq", n=30)
    assert not np.allclose(X[:, 0], np.round(X[:, 0], 3), atol=1e-6)
    gp = PhysGP(MosfetMean(), X, y, NoiseModel(0.5, 0.5)).fit()
    assert gp.mismatch_statistic() < 10.0
