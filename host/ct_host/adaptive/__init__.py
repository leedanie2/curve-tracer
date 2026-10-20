"""Adaptive sampling: a physics-informed GP, Bayesian design, and the
offline evaluation that decides whether any of it earns a firmware change.

**Closed after phase 1 (2026-10-20).** In simulation, adaptive point
selection did not beat a sparse uniform ``SWEEP``, so the firmware points
session was not built. The code is kept so the work can be resumed. When
that would be worth it, and how to start, is in
``docs/adaptive_sampling_plan.md`` under "Resuming this work"; the results
are in ``docs/adaptive_sampling.md``.

Nothing in this package talks to the firmware. The points session it models
(``oracle.points``) does not exist on the instrument.
"""
