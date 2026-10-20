"""Choosing the next batch of points.

Four criteria, all scored over the same candidates (the gate steps of
``vgs_list`` x sweep DAC codes, each placed at the measured drain voltage the
posterior mean predicts for it through the fitted series resistance):

``us``        uncertainty sampling: the largest posterior variance of the
              curve (MacKay 1992).
``eig-theta`` Bayesian D-optimal design on the model's parameters theta: the
              expected information gain about theta, with the residual GP
              counted -- a point the residual could explain says less about
              theta (Lindley 1956; Chaloner & Verdinelli 1995).
``eig-phi``   the same, about the *reported* parameters phi (V_th, KP,
              lambda; n, I_S, R_s), through the extractor's linearisation.
``wa-phi``    weighted A-optimal on phi, sum Var(phi_j) / t_j^2, which is
              aligned with a per-parameter stopping rule.

Every posterior covariance here is independent of the not-yet-measured
values, so **greedy batch selection is exact sequential selection** given
the current fit: pick, rank-one update, repeat. The only cost of a batch is
that theta, the hyperparameters and the linearisation go stale for k points.
log det is submodular, so the greedy EIG batch is within (1 - 1/e) of the
best batch (Krause, Singh & Guestrin 2008).

The safety filter is advisory: it refuses candidates whose upper confidence
bound on current reaches ``alpha * i_limit_ma``. Every accepted point is still
measured and limit-checked by the firmware; a prediction never stands in for
that check.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .gp import PhysGP
from .oracle import OracleBase
from . import estimate as E

__all__ = ["Candidates", "candidates", "select", "order_batch", "CRITERIA"]

CRITERIA = ("us", "eig-theta", "eig-phi", "wa-phi")


@dataclass
class Candidates:
    gate_index: np.ndarray
    code: np.ndarray
    X: np.ndarray
    feasible: np.ndarray
    n_refused: int


def candidates(gp: PhysGP, oracle: OracleBase, kind: str, r_ser: float, *,
               stride: int = 8, alpha: float = 0.9, i_hi_ma: float = 60.0,
               min_volts: float = 0.05) -> Candidates:
    gi_all, code_all, X_all = [], [], []
    lsb = oracle.fe.i_lsb_ma
    for g in range(len(oracle.vgs_list)):
        codes = oracle.available_codes(g)
        codes = codes[oracle.fe.code_to_volts(codes) >= min_volts]
        # Every DAC code on a synthetic device is ~3700 per gate step; thin to
        # ~21 mV. A pool (a dense capture's ~200 codes) is used as it is.
        if stride > 1 and codes.size > 400:
            codes = codes[::stride]
        if kind == "mosfet":
            v = E._invert_mosfet(gp, oracle, g, codes, r_ser)
            X = np.column_stack([np.full(codes.size, oracle.gate_volts[g]), v])
            gi_all.append(np.full(codes.size, g)); code_all.append(codes); X_all.append(X)
        else:
            u, inside = E._invert_diode(gp, oracle, codes, r_ser, i_hi_ma)
            keep = inside & (np.exp(u) * 1000.0 > 3.0 * lsb)
            gi_all.append(np.zeros(int(keep.sum()), int)); code_all.append(codes[keep])
            X_all.append(u[keep][:, None])
    gi = np.concatenate(gi_all); code = np.concatenate(code_all); X = np.vstack(X_all)
    if X.shape[0] == 0:
        return Candidates(gi, code, X, np.zeros(0, bool), 0)

    limit = alpha * oracle.i_limit_ma
    if kind == "mosfet":
        mu, var = gp.predict(X)
        ucb = mu + 3.0 * np.sqrt(var)
    else:
        mu, var = gp.predict(X)
        # Current follows from the node equation; a voltage error of sd moves
        # it by sd / R_ser.
        ucb = np.exp(X[:, 0]) * 1000.0 + 3.0 * np.sqrt(var) / r_ser * 1000.0
    feasible = ucb < limit
    return Candidates(gi, code, X, feasible, int((~feasible).sum()))


def _targets(gp: PhysGP, cand: Candidates, criterion: str, *,
             grid: E.DenseGrid | None, G: np.ndarray | None):
    """Target covariance T and cross-covariance B with the candidates."""
    if criterion == "eig-theta":
        return gp.sigma_theta.copy(), gp.theta_cross_cov(cand.X)
    if G is None or grid is None:
        raise ValueError(f"{criterion} needs the extractor's linearisation")
    gf = grid.factors if grid.factors is not None else gp.factors(grid.X)
    return gp.projected_cov(G, gf), gp.projected_cross_cov(G, gf, cand.X)


def select(gp: PhysGP, cand: Candidates, k: int, criterion: str, *,
           grid: E.DenseGrid | None = None, G: np.ndarray | None = None,
           weights: np.ndarray | None = None) -> list[int]:
    """Indices into ``cand`` of a greedy batch of ``k`` points."""
    if criterion not in CRITERIA:
        raise ValueError(f"unknown criterion {criterion!r}")
    idx_ok = np.where(cand.feasible)[0]
    if idx_ok.size == 0:
        return []
    Xc = gp.factors(cand.X[idx_ok])
    _, v = gp.predict(Xc)
    noise = gp.noise_var_at(Xc)
    if criterion != "us":
        T, B = _targets(gp, Candidates(cand.gate_index[idx_ok], cand.code[idx_ok],
                                       Xc, cand.feasible[idx_ok], 0),
                        criterion, grid=grid, G=G)
        T = T + 1e-30 * np.eye(T.shape[0])
    chosen: list[int] = []
    U: list[np.ndarray] = []        # low-rank corrections to the candidate covariance
    for _ in range(min(k, idx_ok.size)):
        s = v + noise
        if criterion == "us":
            gain = v.copy()
        elif criterion == "wa-phi":
            w = np.ones(B.shape[0]) if weights is None else weights
            gain = (w[:, None] * B * B).sum(0) / s
        else:
            try:
                TiB = np.linalg.solve(T, B)
            except np.linalg.LinAlgError:
                TiB = np.linalg.lstsq(T, B, rcond=None)[0]
            q = np.clip(np.sum(B * TiB, 0) / s, 0.0, 1.0 - 1e-12)
            gain = -0.5 * np.log1p(-q)
        gain[chosen] = -np.inf
        c = int(np.argmax(gain))
        if not np.isfinite(gain[c]):
            break
        chosen.append(c)
        col = gp.cross_cov(Xc, Xc.X[c:c + 1])[:, 0]
        for u in U:
            col = col - u * u[c]
        sc = s[c]
        u_new = col / math.sqrt(sc)
        U.append(u_new)
        v = np.maximum(v - u_new * u_new, 0.0)
        if criterion != "us":
            b = B[:, c].copy()
            T = T - np.outer(b, b) / sc
            B = B - np.outer(b, col) / sc
    return [int(idx_ok[c]) for c in chosen]


def order_batch(cand: Candidates, picks: list[int], policy: str = "sorted",
                rng: np.random.Generator | None = None) -> list[tuple[int, int]]:
    """The order the firmware will measure a batch in.

    ``sorted``      by gate step, then ascending drain code: closest to the
                    ramp's thermal history, and every jump within a gate step
                    is upward from the last point (the default)
    ``acquisition`` the order the criterion picked them
    ``interleave``  alternate high and low power, the worst case for heating
    """
    plan = [(int(cand.gate_index[p]), int(cand.code[p])) for p in picks]
    if policy == "sorted":
        return sorted(plan)
    if policy == "acquisition":
        return plan
    if policy == "interleave":
        s = sorted(plan, key=lambda gc: (gc[0] + 1) * gc[1])
        out = []
        while s:
            out.append(s.pop())
            if s:
                out.append(s.pop(0))
        return out
    raise ValueError(f"unknown ordering {policy!r}")
