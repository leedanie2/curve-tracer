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

**The channel's floor.** The current channel is single-supply, and board 2's
zero is negative (-0.09 to -0.14 mA). With nothing drawing current it reads
neither its zero nor 0 counts, but the difference stage's lowest output:
``0.198 + 0.104 * V`` mA, measured 2026-11-13 (:mod:`ct_host.channel`). So
no source here takes a row within a margin of that floor: ``auto`` skips
them, and a hold sitting there is refused. Until 2026-11-13 the guard was a
fixed 5 counts; the floor is 5.7 counts at 0.24 V, so ``auto`` took a
cap-only diode's floor rows for its zero (+0.217 mA) and read n as 1.495.

A fourth source, a **channel model** file from ``ct_host channel``, carries
the zero with the common-mode term, the current gain and the voltage
offset, and flags rows on the floor so no fit uses them. Beside an R_p
calibration line it applies only the gain and the voltage offset: the line
already holds the zero and the common-mode term, measured in place.

When a zero is given, it replaces any offset an R_p calibration carries;
the two are never both subtracted.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from .channel import BOARD2_FLOOR, Floor, is_model_file, read_model
from .csvio import ContractError, Sweep, parse
from .extract.common import FitError
from .recompute import recompute

__all__ = ["Zero", "resolve_zero", "apply_zero", "AUTO_V_MAX", "HOLD_MAX_MA"]

#: Highest Kelvin voltage ``auto`` averages. The 11-08 1N4148 (n 1.79,
#: I_S 2.7 nA) carries 0.6 uA here, 1.5% of one current LSB.
AUTO_V_MAX = 0.30

#: Fewest rows ``auto`` accepts.
MIN_ROWS = 5

#: A zero hold drawing more than this has a load on it. The difference
#: amp's worst-case CMRR corner (sim 04, 74 dB) gives ~1.1 mA at 6 V.
HOLD_MAX_MA = 1.5


@dataclass(frozen=True)
class Zero:
    """The current zero subtracted from every row, and where it came from."""

    ma: float
    stderr: float | None
    method: str          # "given" | "holds" | "auto" | "channel"
    source: str
    #: A channel model's other terms; identity for a plain zero.
    ma_per_v: float = 0.0
    gain: float = 1.0
    v_offset_v: float = 0.0
    floor: Floor | None = None
    #: Beside an R_p calibration line, which already holds the zero and the
    #: common-mode term: only the gain and the voltage offset apply.
    in_line: bool = False

    @property
    def label(self) -> str:
        if self.method == "channel":
            terms = ("gain" + (" and voltage offset" if self.v_offset_v else "")
                     if self.in_line else
                     f"zero {self.ma:+.4f} {self.ma_per_v:+.4f}·V mA, gain")
            return (f"channel model: {terms} (g {self.gain:.4f}, delta "
                    f"{self.v_offset_v * 1000:+.1f} mV) applied; floor rows "
                    f"excluded (channel: {self.source})")
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
    if "," not in spec and is_model_file(Path(spec)):
        m = read_model(spec)
        return Zero(m.zero_ma, m.stderr.get("zero_ma"), "channel", spec,
                    ma_per_v=m.cm_ma_per_v, gain=m.gain, v_offset_v=m.v_offset_v,
                    floor=m.floor)
    return _holds([Path(p) for p in spec.split(",") if p])


def apply_zero(sweep: Sweep, zero: Zero) -> Sweep:
    """Return a copy with the zero taken out of every row's current.

    A channel model also divides out the gain, takes the voltage offset off
    and flags rows on the floor ``floor``. Its zero and common-mode term are
    evaluated at the voltage as read, and the floor on the total reading.
    """
    if not sweep.recomputed:
        sweep = recompute(sweep)
    rows = []
    for r in sweep.rows:
        z = 0.0 if zero.in_line else zero.ma + zero.ma_per_v * r.v_meas
        flags = r.flags
        if zero.floor is not None and not flags and zero.floor.holds(r.i_total_ma, r.v_meas):
            flags = "floor"
        rows.append(replace(r, i_zero_ma=z, flags=flags,
                            i_gain=None if zero.gain == 1.0 else zero.gain,
                            v_zero_v=zero.v_offset_v or None))
    return replace(sweep, rows=rows, zero=zero)


def _auto(sweep: Sweep) -> Zero:
    if not sweep.recomputed:
        sweep = recompute(sweep)
    steps = {r.vgs_set_v for r in sweep.valid_rows}
    if len(steps) != 1:
        raise FitError(f"--zero auto is for a diode-like capture (one gate step); "
                       f"this one has {len(steps)}")
    off = [r for r in sweep.valid_rows if r.v_dut <= AUTO_V_MAX]
    rows = [r for r in off if not BOARD2_FLOOR.holds(r.i_total_ma, r.v_meas)]
    if len(rows) < MIN_ROWS:
        lowest = min((r.v_dut for r in sweep.valid_rows), default=float("nan"))
        raise FitError(
            f"--zero auto: {len(rows)} rows at or below {AUTO_V_MAX:g} V clear of "
            f"the channel's floor ({BOARD2_FLOOR.label}, board 2); need "
            f"{MIN_ROWS}. {len(off) - len(rows)} of {len(off)} sit on the floor, "
            f"which a stabiliser with no resistor causes; use a channel model "
            f"(`ct_host channel`) or give the zero (lowest measured V {lowest:.3f} V)")
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
        mean = float(np.mean(i))
        v_read = float(np.mean([r.v_meas for r in hold.valid_rows]))
        if BOARD2_FLOOR.holds(mean, v_read):
            raise ContractError(
                f"{path} averages {mean:+.4f} mA at {v_read:.3f} V: the current "
                f"channel is on its floor ({BOARD2_FLOOR.at(v_read):+.4f} mA there), "
                f"so this reads the floor, not the zero. A negative zero can't be "
                f"read with nothing drawing current; fit a channel model from "
                f"known resistors (`ct_host channel`), or give it")
        if abs(mean) > HOLD_MAX_MA:
            raise ContractError(f"{path} averages {mean:+.3f} mA: something is "
                                f"drawing current, so it is not a zero hold")
        v = float(np.mean([r.v_dut for r in hold.valid_rows]))
        currents += i
        parts.append(f"{path.name} {mean:+.4f} mA at {v:.2f} V")
    arr = np.array(currents)
    return Zero(float(arr.mean()), float(arr.std(ddof=1) / math.sqrt(arr.size)),
                "holds", "; ".join(parts))
