"""A Gaussian process with a physical mean and a residual that shows mismatch.

    y_i = m(x_i; theta) + delta(x_i) + eps_i,      eps_i ~ N(0, c * sigma_i^2)
    delta ~ GP(0, k),  k(x,x') = [s_rel^2 s(x) s(x') + s_abs^2] * Matern52(x, x'; l)

``m`` is the device model the extractors assume (:mod:`.models`), ``s(x)`` the
model's own current where the discrepancy is expected to scale with it, and
``sigma_i`` the per-point noise from :mod:`.noise`. ``c`` lets the data
rescale that noise moderately (prior median 1), so a slightly wrong noise
floor is not mistaken for structure.

m is linearised about the current estimate, which makes this a GP with
explicit basis functions (Rasmussen & Williams 2006, §2.7). theta then has
a closed-form posterior given the hyperparameters:

    Sigma_theta = (J' C^-1 J)^-1,   theta_bar = theta_hat + Sigma_theta J' C^-1 (y - m)

computed **with** the correlated residual. Where the residual could explain a
shape that theta also explains, the parameter uncertainty grows instead of
the mismatch being silently absorbed into theta (Kennedy & O'Hagan 2001;
Brynjarsdottir & O'Hagan 2014). Gauss-Newton iterates the linearisation.

Hyperparameters are a MAP estimate under the restricted marginal likelihood
(theta integrated out) with the log-normal priors each model states. scipy
is used for the optimiser and the triangular solves, and for nothing else.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.linalg import cho_factor, cho_solve, solve_triangular
from scipy.optimize import minimize

from .noise import NoiseModel

__all__ = ["PhysGP", "Factors", "matern52"]

SQRT5 = math.sqrt(5.0)
_LOG_FLOOR = -30.0          # log(sigma) meaning "off"


def _sqdist_scaled(XA, XB, ell):
    A = XA / ell
    B = XB / ell
    d2 = (np.sum(A * A, 1)[:, None] + np.sum(B * B, 1)[None, :] - 2.0 * A @ B.T)
    return np.maximum(d2, 0.0)


def matern52(XA, XB, ell):
    r = np.sqrt(_sqdist_scaled(XA, XB, ell))
    return (1.0 + SQRT5 * r + 5.0 / 3.0 * r * r) * np.exp(-SQRT5 * r)


@dataclass
class Factors:
    X: np.ndarray
    m: np.ndarray
    J: np.ndarray
    s: np.ndarray
    K: np.ndarray
    W: np.ndarray
    R: np.ndarray


@dataclass
class _State:
    theta: np.ndarray
    m: np.ndarray
    J: np.ndarray
    s: np.ndarray
    nv: np.ndarray
    L: np.ndarray
    V: np.ndarray            # L^-1 J
    sigma_theta: np.ndarray
    dtheta: np.ndarray
    beta_res: np.ndarray     # C^-1 (r - J dtheta)


class PhysGP:
    """Fit once with :meth:`fit`; then predict, sample and compare."""

    def __init__(self, model, X, y, noise: NoiseModel, *, i_floor_ma: float = 0.2,
                 hyper: np.ndarray | None = None, theta: np.ndarray | None = None):
        self.model = model
        self.X = np.atleast_2d(np.asarray(X, dtype=float))
        self.y = np.asarray(y, dtype=float)
        self.noise = noise
        self.i_floor_ma = i_floor_ma
        p = model.prior
        self.prior_mu = np.log(np.array([p.sigma_rel[0], p.sigma_abs[0],
                                         *[l[0] for l in p.lengths],
                                         p.noise_scale[0]]))
        self.prior_sd = np.array([p.sigma_rel[1], p.sigma_abs[1],
                                  *[l[1] for l in p.lengths], p.noise_scale[1]])
        if not model.relative:
            self.prior_mu[0] = _LOG_FLOOR
        self.h = self.prior_mu.copy() if hyper is None else np.asarray(hyper, float).copy()
        self.theta0 = theta
        self.st: _State | None = None
        self.n_lik_evals = 0

    # -- kernel ----------------------------------------------------------------

    def _ell(self, h):
        return np.exp(h[2:2 + self.model.input_dim])

    def _amp(self, h, sA, sB):
        return (math.exp(2 * h[0]) * np.outer(sA, sB) + math.exp(2 * h[1]))

    def prior_cov(self, XA, XB, sA, sB, h=None):
        h = self.h if h is None else h
        return self._amp(h, sA, sB) * matern52(XA, XB, self._ell(h))

    def prior_var(self, XA, sA, h=None):
        h = self.h if h is None else h
        return math.exp(2 * h[0]) * sA * sA + math.exp(2 * h[1])

    # -- restricted marginal likelihood ------------------------------------------

    def _restricted(self, h, theta, want_grad: bool):
        X, model = self.X, self.model
        m = model.mean(theta, X)
        J = model.jac(theta, X)
        s = model.scale(theta, X)
        nv = model.noise_var(theta, X, self.y, self.noise)
        r = self.y - m
        n, p = J.shape
        colnorm = np.linalg.norm(J, axis=0)
        colnorm[colnorm == 0.0] = 1.0
        Js = J / colnorm

        M = matern52(X, X, self._ell(h))
        amp = self._amp(h, s, s)
        Kd = amp * M
        c = math.exp(h[-1])
        C = Kd + np.diag(c * nv + 1e-12 * (1.0 + np.mean(nv)))
        try:
            cf = cho_factor(C, lower=True)
        except np.linalg.LinAlgError:
            return -1e12, np.zeros_like(h)
        a0 = cho_solve(cf, r)
        CiJ = cho_solve(cf, Js)
        A = Js.T @ CiJ
        try:
            Af = cho_factor(A, lower=True)
        except np.linalg.LinAlgError:
            return -1e12, np.zeros_like(h)
        Jta = Js.T @ a0
        rPr = float(r @ a0 - Jta @ cho_solve(Af, Jta))
        logdetC = 2.0 * float(np.sum(np.log(np.diag(cf[0]))))
        logdetA = 2.0 * float(np.sum(np.log(np.diag(Af[0]))))
        lik = -0.5 * rPr - 0.5 * logdetC - 0.5 * logdetA - 0.5 * (n - p) * math.log(2 * math.pi)
        self.n_lik_evals += 1
        if not want_grad:
            return lik, None

        Pr = a0 - CiJ @ cho_solve(Af, Jta)
        Ci = cho_solve(cf, np.eye(n))
        P = Ci - CiJ @ cho_solve(Af, CiJ.T)
        grads = []
        # log sigma_rel, log sigma_abs
        D0 = 2.0 * math.exp(2 * h[0]) * np.outer(s, s) * M
        D1 = 2.0 * math.exp(2 * h[1]) * M
        derivs = [D0, D1]
        ell = self._ell(h)
        r2 = _sqdist_scaled(X, X, ell)
        rr = np.sqrt(r2)
        base = 5.0 / 3.0 * (1.0 + SQRT5 * rr) * np.exp(-SQRT5 * rr)
        for d in range(model.input_dim):
            diff = (X[:, d][:, None] - X[:, d][None, :]) / ell[d]
            derivs.append(amp * base * diff * diff)
        for D in derivs:
            grads.append(0.5 * float(Pr @ D @ Pr) - 0.5 * float(np.sum(P * D)))
        # log c (noise scale)
        dn = c * nv
        grads.append(0.5 * float(np.sum(Pr * Pr * dn)) - 0.5 * float(np.sum(np.diag(P) * dn)))
        return lik, np.array(grads)

    def _objective(self, h, theta):
        lik, g = self._restricted(h, theta, True)
        z = (h - self.prior_mu) / self.prior_sd
        logp = -0.5 * float(z @ z)
        gp = -z / self.prior_sd
        if not self.model.relative:
            g = g.copy(); g[0] = 0.0; gp[0] = 0.0
        return -(lik + logp), -(g + gp)

    def _bounds(self):
        d = self.model.input_dim
        b = [(-14.0, 2.0), (-14.0, 2.0)] + [(math.log(0.02), math.log(100.0))] * d
        b.append((math.log(0.2), math.log(10.0)))
        if not self.model.relative:
            b[0] = (_LOG_FLOOR, _LOG_FLOOR)
        return b

    def _optimise_h(self, theta, restarts: int):
        starts = [self.h.copy()]
        rng = np.random.default_rng(len(self.y))
        for _ in range(restarts):
            starts.append(self.prior_mu + rng.normal(0.0, 1.0, self.h.size) * self.prior_sd * 0.5)
        best = None
        for h0 in starts:
            h0 = np.clip(h0, [b[0] for b in self._bounds()], [b[1] for b in self._bounds()])
            res = minimize(self._objective, h0, args=(theta,), jac=True,
                           method="L-BFGS-B", bounds=self._bounds(),
                           options={"maxiter": 60})
            if best is None or res.fun < best.fun:
                best = res
        self.h = best.x

    # -- theta: Gauss-Newton GLS -------------------------------------------------------

    def _gls(self, theta, h):
        X, model = self.X, self.model
        m = model.mean(theta, X)
        J = model.jac(theta, X)
        s = model.scale(theta, X)
        nv = model.noise_var(theta, X, self.y, self.noise)
        C = self.prior_cov(X, X, s, s, h) + np.diag(math.exp(h[-1]) * nv
                                                    + 1e-12 * (1.0 + np.mean(nv)))
        L = np.linalg.cholesky(C)
        V = solve_triangular(L, J, lower=True)
        z = solve_triangular(L, self.y - m, lower=True)
        A = V.T @ V
        # Columns with no data (e.g. a parameter nothing depends on) are held.
        reg = 1e-12 * np.maximum(np.diag(A), 1e-30)
        sigma_theta = np.linalg.pinv(A + np.diag(reg))
        dtheta = sigma_theta @ (V.T @ z)
        return dict(m=m, J=J, s=s, nv=nv, L=L, V=V, z=z, sigma_theta=sigma_theta,
                    dtheta=dtheta, obj=float(z @ z - (V.T @ z) @ dtheta))

    def _gauss_newton(self, theta, h, iters: int = 12):
        theta = np.asarray(theta, dtype=float)
        for _ in range(iters):
            g = self._gls(theta, h)
            step = g["dtheta"]
            base = float(g["z"] @ g["z"])
            accepted = False
            for _half in range(8):
                trial = theta + step
                gt = self._gls(trial, h)
                if float(gt["z"] @ gt["z"]) <= base + 1e-12:
                    theta, accepted = trial, True
                    break
                step = step * 0.5
            if not accepted:
                break
            if np.all(np.abs(step) <= 1e-9 * (1.0 + np.abs(theta))):
                break
        return theta

    # -- public ------------------------------------------------------------------------------

    def fit(self, *, restarts: int = 1, alternations: int = 2,
            optimise_hyper: bool = True) -> PhysGP:
        theta = (self.model.init(self.X, self.y, self.i_floor_ma)
                 if self.theta0 is None else np.asarray(self.theta0, float))
        for _ in range(alternations):
            theta = self._gauss_newton(theta, self.h)
            if optimise_hyper:
                self._optimise_h(theta, restarts)
        theta = self._gauss_newton(theta, self.h)
        g = self._gls(theta, self.h)
        r_res = solve_triangular(g["L"].T, g["z"] - g["V"] @ g["dtheta"], lower=False)
        self.st = _State(theta=theta, m=g["m"], J=g["J"], s=g["s"], nv=g["nv"],
                         L=g["L"], V=g["V"], sigma_theta=g["sigma_theta"],
                         dtheta=g["dtheta"], beta_res=r_res)
        return self

    @property
    def theta(self) -> np.ndarray:
        return self.st.theta + self.st.dtheta

    @property
    def sigma_theta(self) -> np.ndarray:
        return self.st.sigma_theta

    def factors(self, Xs) -> Factors:
        """Everything the posterior needs at Xs, computed once.

        Pass the result instead of Xs to predict / cross_cov / residual to
        reuse it; a round of design evaluates the same grid and candidates
        several times.
        """
        if isinstance(Xs, Factors):
            return Xs
        st = self.st
        Xs = np.atleast_2d(np.asarray(Xs, dtype=float))
        ms = self.model.mean(st.theta, Xs)
        Js = self.model.jac(st.theta, Xs)
        ss = self.model.scale(st.theta, Xs)
        Ks = self.prior_cov(self.X, Xs, st.s, ss)
        W = solve_triangular(st.L, Ks, lower=True)
        R = Js - W.T @ st.V
        return Factors(Xs, ms, Js, ss, Ks, W, R)

    def _parts(self, Xs):
        f = self.factors(Xs)
        return f.X, f.m, f.J, f.s, f.K, f.W, f.R

    def projected_cov(self, G: np.ndarray, Xs) -> np.ndarray:
        """G Cov(f(Xs)) G', without forming the full covariance."""
        f = self.factors(Xs)
        GK = (self.prior_cov(f.X, f.X, f.s, f.s) @ G.T).T
        GW = G @ f.W.T
        GR = G @ f.R
        out = GK @ G.T - GW @ GW.T + GR @ self.st.sigma_theta @ GR.T
        return 0.5 * (out + out.T)

    def projected_cross_cov(self, G: np.ndarray, XA, XB) -> np.ndarray:
        """G Cov(f(XA), f(XB)), (rows of G) x len(XB)."""
        fa, fb = self.factors(XA), self.factors(XB)
        GK = G @ self.prior_cov(fa.X, fb.X, fa.s, fb.s)
        return GK - (G @ fa.W.T) @ fb.W + (G @ fa.R) @ self.st.sigma_theta @ fb.R.T

    def predict(self, Xs, full_cov: bool = False):
        """Posterior mean and variance (or covariance) of the noise-free curve."""
        st = self.st
        Xs, ms, Js, ss, Ks, W, R = self._parts(Xs)
        mu = ms + Js @ st.dtheta + Ks.T @ st.beta_res
        if full_cov:
            cov = (self.prior_cov(Xs, Xs, ss, ss) - W.T @ W
                   + R @ st.sigma_theta @ R.T)
            return mu, 0.5 * (cov + cov.T)
        var = (self.prior_var(Xs, ss) - np.sum(W * W, 0)
               + np.einsum("ij,jk,ik->i", R, st.sigma_theta, R))
        return mu, np.maximum(var, 0.0)

    def cross_cov(self, XA, XB):
        """Posterior covariance between the curve at XA and at XB."""
        st = self.st
        XA, _, _, sA, KA, WA, RA = self._parts(XA)
        XB, _, _, sB, KB, WB, RB = self._parts(XB)
        return (self.prior_cov(XA, XB, sA, sB) - WA.T @ WB
                + RA @ st.sigma_theta @ RB.T)

    def theta_cross_cov(self, Xs):
        """Posterior covariance between theta and the curve at Xs, (p, n*)."""
        _, _, _, _, _, _, R = self._parts(Xs)
        return self.st.sigma_theta @ R.T

    def sample(self, Xs, n_samples: int, rng: np.random.Generator):
        mu, cov = self.predict(Xs, full_cov=True)
        jitter = 1e-10 * max(float(np.mean(np.diag(cov))), 1e-12)
        for _ in range(6):
            try:
                Lc = np.linalg.cholesky(cov + jitter * np.eye(cov.shape[0]))
                break
            except np.linalg.LinAlgError:
                jitter *= 100.0
        else:
            w, Q = np.linalg.eigh(cov)
            Lc = Q * np.sqrt(np.maximum(w, 0.0))
        return mu[None, :] + rng.standard_normal((n_samples, mu.size)) @ Lc.T

    def noise_var_at(self, Xs) -> np.ndarray:
        """Measurement variance a new point at Xs would carry (scaled by c)."""
        Xs = Xs.X if isinstance(Xs, Factors) else np.atleast_2d(np.asarray(Xs, dtype=float))
        return math.exp(self.h[-1]) * self.model.noise_var(
            self.st.theta, Xs, None, self.noise)

    # -- mismatch ----------------------------------------------------------------------------

    def residual(self, Xs, *, given_theta: bool = False):
        """Posterior of the discrepancy delta alone: mean and sd.

        Marginally (the default) the sd includes theta's uncertainty, because
        delta = f - J theta. On a mismatched device theta is uncertain exactly
        where the residual could mimic it, so the marginal sd is large wherever
        the mean is, and a pointwise |mean/sd| test finds nothing even when the
        global statistic is enormous -- the identifiability problem in one line.
        ``given_theta`` returns the sd with theta held at its estimate instead,
        which answers "where did the residual have to add structure beyond the
        fitted model", the question a mismatch map is for.
        """
        st = self.st
        Xs, ms, Js, ss, Ks, W, R = self._parts(Xs)
        mean = Ks.T @ st.beta_res
        var = self.prior_var(Xs, ss) - np.sum(W * W, 0)
        if not given_theta:
            Q = W.T @ st.V                     # K*' C^-1 J
            var = var + np.einsum("ij,jk,ik->i", Q, st.sigma_theta, Q)
        return mean, np.sqrt(np.maximum(var, 0.0))

    def mismatch_statistic(self) -> float:
        """Lambda = 2 [log p(y | model + residual GP) - log p(y | model + noise)].

        Both are restricted likelihoods at their own best theta. The noise-only
        model also gets a free noise scale, fitted in closed form, so only
        *structured* residual can raise Lambda -- a slightly wrong noise floor
        cannot. The threshold is calibrated by the evaluation on control
        devices; this returns the raw statistic.
        """
        theta1 = self.st.theta
        l1, _ = self._restricted(self.h, theta1, False)

        h0 = self.h.copy()
        h0[0] = h0[1] = _LOG_FLOOR
        h0[-1] = 0.0
        theta0 = self._gauss_newton(theta1, h0)
        g = self._gls(theta0, h0)
        n, p = g["J"].shape
        c_hat = max(g["obj"] / max(n - p, 1), 1e-12)
        h0[-1] = math.log(c_hat)
        l0, _ = self._restricted(h0, theta0, False)
        return 2.0 * (l1 - l0)
