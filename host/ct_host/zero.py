"""The instrument's current zero, subtracted on its own.

With a resistor across D-S (``parallel``), the zero comes out as the offset
of R_p's calibration line. With a stabiliser that draws no DC, a capacitor
alone (MVP card section E), there is no line to fit, but the zero is still
there: -0.087 mA on board 2 on 2026-11-08, 43% of the diode fit's 0.2 mA
floor. Left in, it read that diode's n as 1.651 instead of 1.789. This module
gives the zero a source of its own. Three:

- **given** (``MA``): a number, for example from an earlier session.
- **holds** (``CSV[,CSV...]``): the mean current of holds with nothing
  drawing DC, the card's 22b-d. Each file's mean is reported, because the
  zero moves with the node voltage (the difference amp's CMRR) and the
  spread between holds at 0.2, 1 and 6 V shows by how much.
- **auto**: the capture's own rows below ``AUTO_V_MAX``, where a diode
  carries no resolvable current. One gate step only: a MOSFET family has no
  such region it can be trusted to have.

**The channel's floor.** The current channel is single-supply and the ADC
unipolar, so it cannot read below 0 counts, and board 2's zero is negative
(-0.087 mA, -2.2 counts). At true zero current it reads its floor, not its
zero. On 2026-11-08 L1 kept it ~20 counts up. With nothing drawing DC
(a capacitor alone), it would not be. So no source here takes rows under
``FLOOR_COUNTS``: ``auto`` skips them, and a hold sitting there is refused.
A zero for that case comes from two known resistors' intercept, or is given.

When a zero is given, it replaces any offset an R_p calibration carries;
the two are never both subtracted.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from .csvio import ContractError, Sweep, parse
from .extract.common import FitError
from .recompute import recompute

__all__ = ["Zero", "resolve_zero", "apply_zero", "AUTO_V_MAX", "FLOOR_COUNTS",
           "HOLD_MAX_MA"]

#: Highest Kelvin voltage ``auto`` averages. The 11-08 1N4148 (n 1.79,
#: I_S 2.7 nA) carries 0.6 uA here, 1.5% of one current LSB.
AUTO_V_MAX = 0.30

#: Fewest rows ``auto`` accepts.
MIN_ROWS = 5

#: Rows averaging fewer raw ADC counts per sample than this may be on the
#: channel's floor (0 counts, or the op-amp's low swing a few counts up).
#: 5 counts is 0.2 mA on range 1, the diode fit's own floor.
FLOOR_COUNTS = 5.0

#: A zero hold drawing more than this has a load on it. The difference
#: amp's worst-case CMRR corner (sim 04, 74 dB) gives ~1.1 mA at 6 V.
HOLD_MAX_MA = 1.5


@dataclass(frozen=True)
class Zero:
    """The current zero subtracted from every row, and where it came from."""

    ma: float
    stderr: float | None
    method: str          # "given" | "holds" | "auto"
    source: str

    @property
    def label(self) -> str:
        err = "" if self.stderr is None else f" ± {self.stderr:.2g}"
        return f"zero {self.ma:+.4f}{err} mA subtracted ({self.method}: {self.source})"

    def describe(self) -> str:
        return f"  {self.label}"


def resolve_zero(spec: str, sweep: Sweep | None = None) -> Zero:
    """``--zero``: ``MA``, ``auto``, or hold CSVs separated by commas.

    For ``auto``, ``sweep`` is the capture with any R_p already subtracted
    (without R_p's own offset), so its off rows read the zero alone.
    """
    if spec == "auto":
        if sweep is None:
            raise ValueError("--zero auto needs the capture")
        return _auto(sweep)
    try:
        ma = float(spec)
    except ValueError:
        pass
    else:
        return Zero(ma, None, "given", "command line")
    return _holds([Path(p) for p in spec.split(",") if p])


def apply_zero(sweep: Sweep, zero: Zero) -> Sweep:
    """Return a copy with the zero taken out of every row's current."""
    if not sweep.recomputed:
        sweep = recompute(sweep)
    rows = [replace(r, i_zero_ma=zero.ma) for r in sweep.rows]
    return replace(sweep, rows=rows, zero=zero)


def _auto(sweep: Sweep) -> Zero:
    if not sweep.recomputed:
        sweep = recompute(sweep)
    steps = {r.vgs_set_v for r in sweep.valid_rows}
    if len(steps) != 1:
        raise FitError(f"--zero auto is for a diode-like capture (one gate step); "
                       f"this one has {len(steps)}")
    n = sweep.meta.oversample_n
    off = [r for r in sweep.valid_rows if r.v_dut <= AUTO_V_MAX]
    rows = [r for r in off if r.i_acc / n >= FLOOR_COUNTS]
    if len(rows) < MIN_ROWS:
        lowest = min((r.v_dut for r in sweep.valid_rows), default=float("nan"))
        raise FitError(
            f"--zero auto: {len(rows)} rows at or below {AUTO_V_MAX:g} V clear of "
            f"the channel's floor ({FLOOR_COUNTS:g} counts); need {MIN_ROWS}. "
            f"{len(off) - len(rows)} of {len(off)} sit on the floor, which a "
            f"stabiliser with no resistor causes; give the zero instead "
            f"(lowest measured V {lowest:.3f} V)")
    i = np.array([r.i_ma for r in rows])
    v = [r.v_dut for r in rows]
    return Zero(float(i.mean()), float(i.std(ddof=1) / math.sqrt(i.size)), "auto",
                f"this capture, {i.size} rows over {min(v):.3g}..{max(v):.3g} V")


def _holds(paths: list[Path]) -> Zero:
    if not paths:
        raise ValueError("--zero: no hold files given")
    currents: list[float] = []
    parts: list[str] = []
    for path in paths:
        if not path.exists():
            raise ValueError(f"--zero {str(path)!r} is not a number, 'auto', or a file")
        hold = parse(path.read_text(), require_end=True)
        if hold.meta.get("mode") != "hold":
            raise ContractError(f"{path} is not a hold (mode: {hold.meta.get('mode')})")
        if hold.meta.get("host_r_parallel_ohm") is not None:
            raise ContractError(f"{path} was taken with an R_p; a zero hold has "
                                f"nothing drawing DC")
        hold = recompute(hold)
        i = [r.i_total_ma for r in hold.valid_rows]
        if not i:
            raise ContractError(f"{path} has no valid rows")
        counts = float(np.mean([r.i_acc for r in hold.valid_rows])) / hold.meta.oversample_n
        if counts < FLOOR_COUNTS:
            raise ContractError(
                f"{path} averages {counts:.1f} ADC counts: the current channel "
                f"is on its floor, so this reads the floor, not the zero. A "
                f"negative zero can't be read with nothing drawing current; "
                f"take it from two known resistors' intercept, or give it")
        mean = float(np.mean(i))
        if abs(mean) > HOLD_MAX_MA:
            raise ContractError(f"{path} averages {mean:+.3f} mA: something is "
                                f"drawing current, so it is not a zero hold")
        v = float(np.mean([r.v_dut for r in hold.valid_rows]))
        currents += i
        parts.append(f"{path.name} {mean:+.4f} mA at {v:.2f} V")
    arr = np.array(currents)
    return Zero(float(arr.mean()), float(arr.std(ddof=1) / math.sqrt(arr.size)),
                "holds", "; ".join(parts))
