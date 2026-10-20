"""Parametric means for the GP, with their Jacobians.

These are the models the extractors assume, written as functions so a GP
can use them as its mean and a design criterion can differentiate them:

* MOSFET: square law with channel-length modulation, in the extractor's
  convention ``I = beta * V_ov^2 * (1 + lambda V)`` (saturation) and
  ``beta * (2 V_ov V - V^2) * (1 + lambda V)`` (triode), V the **measured**
  drain voltage. Output in mA. theta = (V_th, beta [A/V^2], lambda).
* Diode: the extractor's inverse form, ``V = a ln I + b + c I`` with
  ``a = n V_T``, ``I_S = exp(-b/a)``, ``R_s = c``. Input ``u = ln(I / 1 A)``,
  output V. Exactly linear in theta = (a, b, c).

Each also says how to weight its points (via :mod:`.noise`) and what its
discrepancy prior looks like; see :mod:`.gp`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .noise import NoiseModel

__all__ = ["MosfetMean", "DiodeMean", "HyperPrior"]


@dataclass(frozen=True)
class HyperPrior:
    """Log-normal priors on the GP hyperparameters, as (median, sd of log).

    The priors exist because maximising the marginal likelihood with 20-40
    points collapses length scales. They are weak (sd of log >= 0.75) and
    stated here rather than buried in the optimiser.
    """

    sigma_rel: tuple[float, float]
    sigma_abs: tuple[float, float]
    lengths: tuple[tuple[float, float], ...]
    noise_scale: tuple[float, float] = (1.0, 0.5)


class MosfetMean:
    names = ("vth", "beta", "lam")
    input_dim = 2
    relative = True
    output_unit = "mA"
    prior = HyperPrior(sigma_rel=(0.02, 1.5), sigma_abs=(0.02, 1.5),
                       lengths=((0.5, 0.75), (2.0, 0.75)))

    @staticmethod
    def _parts(theta, X):
        vth, beta, lam = (float(t) for t in theta)
        vgs, v = X[:, 0], np.maximum(X[:, 1], 0.0)
        vov = vgs - vth
        on = vov > 0.0
        sat = on & (v >= vov)
        tri = on & ~sat
        return vth, beta, lam, v, vov, sat, tri

    def mean(self, theta, X) -> np.ndarray:
        _, beta, lam, v, vov, sat, tri = self._parts(theta, X)
        f = 1.0 + lam * v
        out = np.zeros(X.shape[0])
        out[sat] = beta * vov[sat] ** 2 * f[sat]
        out[tri] = beta * (2.0 * vov[tri] * v[tri] - v[tri] ** 2) * f[tri]
        return out * 1000.0

    def jac(self, theta, X) -> np.ndarray:
        _, beta, lam, v, vov, sat, tri = self._parts(theta, X)
        f = 1.0 + lam * v
        J = np.zeros((X.shape[0], 3))
        J[sat, 0] = -2.0 * beta * vov[sat] * f[sat]
        J[sat, 1] = vov[sat] ** 2 * f[sat]
        J[sat, 2] = beta * vov[sat] ** 2 * v[sat]
        q = 2.0 * vov[tri] * v[tri] - v[tri] ** 2
        J[tri, 0] = -2.0 * beta * v[tri] * f[tri]
        J[tri, 1] = q * f[tri]
        J[tri, 2] = beta * q * v[tri]
        return J * 1000.0

    def slope(self, theta, X) -> np.ndarray:
        """dI/dV in mA/V, for the voltage channel's share of the noise."""
        _, beta, lam, v, vov, sat, tri = self._parts(theta, X)
        out = np.zeros(X.shape[0])
        out[sat] = beta * vov[sat] ** 2 * lam
        q = 2.0 * vov[tri] * v[tri] - v[tri] ** 2
        out[tri] = beta * ((2.0 * vov[tri] - 2.0 * v[tri]) * (1.0 + lam * v[tri])
                           + q * lam)
        return out * 1000.0

    def scale(self, theta, X) -> np.ndarray:
        """Amplitude for the current-proportional part of the discrepancy."""
        return np.abs(self.mean(theta, X))

    def noise_var(self, theta, X, y, noise: NoiseModel) -> np.ndarray:
        return noise.current_var(self.slope(theta, X))

    def init(self, X, y, i_floor_ma: float) -> np.ndarray:
        """A starting theta from the data alone.

        The highest-V point of each gate step is taken as saturated, and a
        straight line through sqrt(I) against V_GS gives V_th and beta, as the
        extractor's own first pass does. Then a weighted nonlinear least
        squares refines all three against every point.
        """
        from scipy.optimize import least_squares

        pts = []
        for g in np.unique(X[:, 0]):
            m = X[:, 0] == g
            k = np.argmax(X[m, 1])
            if y[m][k] > i_floor_ma:
                pts.append((g, math.sqrt(y[m][k] / 1000.0)))
        if len(pts) >= 2:
            g, r = np.array(pts).T
            slope, icpt = np.polyfit(g, r, 1)
            vth0 = -icpt / slope if slope > 0 else float(X[:, 0].min()) - 0.5
            beta0 = max(slope ** 2, 1e-4)
        else:
            vth0, beta0 = float(X[:, 0].min()) - 0.5, 0.02
        theta0 = np.array([vth0, beta0, 0.01])

        w = 1.0 / np.sqrt(np.maximum(y, 0.0) * 1e-3 + 0.04 ** 2)
        res = least_squares(lambda t: (self.mean(t, X) - y) * w, theta0,
                            jac=lambda t: self.jac(t, X) * w[:, None],
                            x_scale=np.array([0.1, 0.01, 0.01]), max_nfev=200)
        return res.x


class DiodeMean:
    names = ("a", "b", "c")
    input_dim = 1
    relative = False
    output_unit = "V"
    prior = HyperPrior(sigma_rel=(1e-3, 1.0), sigma_abs=(0.005, 1.5),
                       lengths=((1.0, 0.75),))

    def mean(self, theta, U) -> np.ndarray:
        a, b, c = theta
        u = U[:, 0]
        return a * u + b + c * np.exp(u)

    def jac(self, theta, U) -> np.ndarray:
        u = U[:, 0]
        return np.column_stack([u, np.ones_like(u), np.exp(u)])

    def scale(self, theta, U) -> np.ndarray:
        return np.zeros(U.shape[0])

    def noise_var(self, theta, U, y, noise: NoiseModel) -> np.ndarray:
        a, _, c = theta
        u = U[:, 0]
        return noise.voltage_var_given_log_current(np.exp(u) * 1000.0,
                                                   a + c * np.exp(u))

    def init(self, U, y, i_floor_ma: float) -> np.ndarray:
        del i_floor_ma
        theta, *_ = np.linalg.lstsq(self.jac(None, U), y, rcond=None)
        return theta
