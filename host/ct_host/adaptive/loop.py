"""The adaptive capture loop, and the fixed designs it is compared against.

An adaptive run is: open a points session; measure the seeds; then repeat
{fit the GP, estimate, decide whether to stop, choose a batch, measure it}
until a stop reason. Host computation is timed with the wall clock and
charged to the instrument clock as idle time with the drain at zero -- that is
what the device sees while the host thinks, and it counts in every speed
figure.

Stop reasons, written to the result and, in phase 2, to ``# host_stop_reason``:

``target_met``          every gated parameter's stderr and half-spread are
                        under target, the raw-point cross-check agrees, and
                        the extractor ran on at least 90% of posterior samples
``budget``              the point budget is spent
``ilimit``              the firmware's current limit tripped; the session ended
``no_feasible_points``  the safety filter refused every candidate
``max_rounds``          a backstop that should never fire

The rule is the brief's: targets on both numbers, or the budget. A parameter
whose *spread* is above target while its stderr is not cannot be helped by
more points; that is recorded per round as ``spread_limited`` and reported,
but it does not stop the run.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import numpy as np

from . import acquire as A
from . import estimate as E
from .gp import PhysGP
from .noise import NoiseModel
from .oracle import OracleBase, Point

__all__ = ["DesignConfig", "RoundRecord", "RunResult", "seed_plan",
           "run_adaptive", "run_ramp", "STOP_REASONS"]

STOP_REASONS = ("target_met", "budget", "ilimit", "no_feasible_points",
                "max_rounds")


@dataclass
class DesignConfig:
    kind: str                         # "mosfet" | "diode"
    criterion: str = "eig-phi"
    k: int = 8
    seeds_per_gate: int = 5
    budget: int = 300
    targets: dict = field(default_factory=lambda: dict(E.MOSFET_TARGETS))
    alpha: float = 0.9
    n_samples: int = 64
    n_dense: int = 200
    ordering: str = "sorted"
    stride: int = 8
    max_rounds: int = 120
    #: None: charge the measured host compute. A number: charge that many
    #: seconds per round instead (deterministic thermal histories in tests).
    compute_s: float | None = None

    @property
    def gated(self) -> tuple[str, ...]:
        return tuple(self.targets)


@dataclass
class RoundRecord:
    round: int
    n_points: int
    clock_s: float
    compute_s: float
    values: dict[str, float]
    lin_sd: dict[str, float]
    full: bool
    blocking: list[str]
    spread_limited: list[str]


@dataclass
class RunResult:
    design: str
    points: list[Point]
    rounds: list[RoundRecord]
    stop_reason: str
    assessment: E.Assessment | None
    gp: PhysGP | None
    clock_s: float
    breakdown: dict[str, float]
    compute_s: float
    n_refused: int = 0
    grid: E.DenseGrid | None = None
    r_ser: float = math.nan

    @property
    def n_points(self) -> int:
        return len(self.points)


def seed_plan(oracle: OracleBase, kind: str, per_gate: int) -> list[tuple[int, int]]:
    """Endpoints plus a coarse grid, always measured first, as per-gate ramps.

    So the method cannot settle on a wrong model from a few lucky points.
    MOSFET: 3 or 5 commanded fractions of vds_max on every gate step, always
    including vds_max itself (the slice end). Diode: geometric in commanded
    voltage from 0.15 * vds_max, which puts several seeds on the exponential
    before series resistance takes over.
    """
    fe = oracle.fe
    if kind == "mosfet":
        fr = (0.1, 0.25, 0.5, 0.75, 1.0) if per_gate >= 5 else (0.25, 0.6, 1.0)
        plan = [(g, oracle.nearest_code(g, fe.volts_to_code(f * oracle.vds_max)))
                for g in range(len(oracle.vgs_list)) for f in fr]
        return sorted(set(plan))
    count = max(per_gate, 6) + 2
    volts = oracle.vds_max * np.geomspace(0.15, 1.0, count)
    return sorted({(0, oracle.nearest_code(0, fe.volts_to_code(float(v)))) for v in volts})


def _lin_sd(gp: PhysGP, grid: E.DenseGrid, G: np.ndarray | None,
            names: tuple[str, ...]) -> dict[str, float]:
    if G is None:
        return {}
    cov = gp.projected_cov(G, grid.factors if grid.factors is not None else grid.X)
    return {k: float(math.sqrt(max(cov[j, j], 0.0))) for j, k in enumerate(names)}


def _abs_target(cfg: DesignConfig, name: str, value: float) -> float:
    kind, t = cfg.targets[name]
    return t * abs(value) if kind == "rel" else t


def run_adaptive(oracle: OracleBase, cfg: DesignConfig, noise: NoiseModel,
                 rng: np.random.Generator) -> RunResult:
    names = cfg.gated
    oracle.configure()
    oracle.open_points()
    cap = oracle.points(sorted(seed_plan(oracle, cfg.kind, cfg.seeds_per_gate)),
                        batch=0)
    points: list[Point] = list(cap.points)
    rounds: list[RoundRecord] = []
    gp: PhysGP | None = None
    assessment = None
    grid = None
    r_ser = math.nan
    n_refused = 0
    total_compute = 0.0
    reason = "max_rounds"
    if cap.end_reason == "ilimit":
        reason = "ilimit"

    for rnd in range(cfg.max_rounds):
        if reason == "ilimit":
            break
        t0 = time.perf_counter()
        gp = E.fit_gp(oracle, points, cfg.kind, noise, previous=gp)
        r_ser = E.series_resistance(oracle, points)
        cheap, grid, mean_sweep = E.assess(gp, oracle, points, cfg.kind, cfg.targets,
                                           n_dense=cfg.n_dense, r_ser=r_ser, rng=rng,
                                           stage="spread")
        G = E.linearise(mean_sweep, grid, cfg.kind, names) if cheap.params else None
        lin = _lin_sd(gp, grid, G, names)
        values = {k: p.value for k, p in cheap.params.items()}

        def under(k, x):
            return k in values and x is not None and x <= _abs_target(cfg, k, values[k])

        lin_ok = G is not None and all(under(k, lin.get(k)) for k in names)
        spread_ok = all(under(k, None if cheap.params.get(k) is None
                              or cheap.params[k].spread is None
                              else cheap.params[k].spread / 2.0) for k in names)
        # Measurement can still reduce stderr; it cannot reduce a spread.
        spread_limited = [k for k in names if under(k, lin.get(k))
                          and not under(k, None if cheap.params.get(k) is None
                                        or cheap.params[k].spread is None
                                        else cheap.params[k].spread / 2.0)]
        assessment = cheap
        if lin_ok and spread_ok:
            assessment, grid, mean_sweep = E.assess(
                gp, oracle, points, cfg.kind, cfg.targets, n_dense=cfg.n_dense,
                r_ser=r_ser, rng=rng, n_samples=cfg.n_samples, stage="full")

        stop = assessment.stop
        picks: list[int] = []
        cand = None
        if not stop and len(points) < cfg.budget:
            i_hi = max((p.row.i_meas_ma for p in points if p.row.valid), default=1.0)
            cand = A.candidates(gp, oracle, cfg.kind, r_ser, stride=cfg.stride,
                                alpha=cfg.alpha, i_hi_ma=max(oracle.i_limit_ma, i_hi))
            n_refused = cand.n_refused
            weights = None
            if cfg.criterion == "wa-phi":
                weights = np.array([1.0 / max(_abs_target(cfg, k, values.get(k, 1.0)), 1e-30) ** 2
                                    for k in names])
            picks = A.select(gp, cand, min(cfg.k, cfg.budget - len(points)),
                             cfg.criterion, grid=grid, G=G, weights=weights)
        dt = time.perf_counter() - t0
        charged = dt if cfg.compute_s is None else cfg.compute_s
        total_compute += charged
        oracle.idle(charged, "compute")
        rounds.append(RoundRecord(rnd, len(points), oracle.clock, charged, values,
                                  lin, assessment.full, list(assessment.blocking),
                                  spread_limited))
        if stop:
            reason = "target_met"
            break
        if len(points) >= cfg.budget:
            reason = "budget"
            break
        if not picks:
            reason = "no_feasible_points"
            break
        cap = oracle.points(A.order_batch(cand, picks, cfg.ordering, rng), batch=rnd + 1)
        points.extend(cap.points)
        if cap.end_reason == "ilimit":
            reason = "ilimit"
            break

    if reason in ("ilimit", "budget", "max_rounds", "no_feasible_points") and points:
        # A final full assessment on everything measured, for the report.
        t0 = time.perf_counter()
        gp = E.fit_gp(oracle, points, cfg.kind, noise, previous=gp)
        r_ser = E.series_resistance(oracle, points)
        assessment, grid, _ = E.assess(gp, oracle, points, cfg.kind, cfg.targets,
                                       n_dense=cfg.n_dense, r_ser=r_ser, rng=rng,
                                       n_samples=cfg.n_samples, stage="full")
        charged = time.perf_counter() - t0 if cfg.compute_s is None else cfg.compute_s
        total_compute += charged
        oracle.idle(charged, "compute")
    oracle.close_points()
    return RunResult(cfg.criterion, points, rounds, reason, assessment, gp,
                     oracle.clock, oracle.breakdown.as_dict(), total_compute,
                     n_refused, grid, r_ser)


def run_ramp(oracle: OracleBase, n: int, cfg: DesignConfig, noise: NoiseModel,
             rng: np.random.Generator, *, with_gp: bool = True) -> RunResult:
    """Today's SWEEP at ``n`` points per gate step; optionally + the GP estimator.

    No firmware change is involved: this is the baseline adaptive selection
    has to beat. The GP's compute happens after the capture and is counted.
    """
    oracle.configure()
    cap = oracle.sweep(n)
    points = list(cap.points)
    gp = assessment = grid = None
    r_ser = math.nan
    compute = 0.0
    if with_gp and points:
        t0 = time.perf_counter()
        gp = E.fit_gp(oracle, [p for p in points if p.row.valid], cfg.kind, noise)
        r_ser = E.series_resistance(oracle, points)
        assessment, grid, _ = E.assess(gp, oracle, points, cfg.kind, cfg.targets,
                                       n_dense=cfg.n_dense, r_ser=r_ser, rng=rng,
                                       n_samples=cfg.n_samples, stage="full")
        compute = time.perf_counter() - t0 if cfg.compute_s is None else cfg.compute_s
    reason = "ilimit" if cap.end_reason == "ilimit" else "single_shot"
    return RunResult(f"ramp-{n}" + ("+gp" if with_gp else ""), points, [], reason,
                     assessment, gp, oracle.clock + compute,
                     {**oracle.breakdown.as_dict(), "compute": compute}, compute,
                     0, grid, r_ser)
