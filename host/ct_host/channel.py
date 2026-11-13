"""The current channel's transfer: gain, zero, common-mode term, and floor.

Board 2's current reading, measured 2026-11-13 (MVP card section E), is

    reading = max( floor(V),  g * I + b + c * V )        on V - delta

- **The floor.** With nothing drawing current the channel does not read its
  zero (-0.09 to -0.14 mA) and does not sit at 0 counts either. It reads
  ``0.198 + 0.104 * V`` mA: 4.9 counts plus 2.6 counts per volt of node
  voltage. That is the difference stage's output (an OPA197 whose negative
  rail is ground) at the bottom of its swing: 5 mV typical with no load
  (TI's table), plus ~44 ohm times the current the saturated output sinks
  through the 20 kOhm feedback resistor, ``V * 20/21 / 20 kOhm``. A reading
  on the floor says only that the true reading is lower. 2026-11-03's
  open-load 0.830 and 0.832 mA at 6 V were this floor, as were the 1N4148's
  off rows on 2026-11-13, to within 0.3 counts.
- **The linear part**, above the floor: ``g``, the current channel's gain
  against the voltage channel's; ``b``, the zero; ``c``, the difference
  amp's common-mode term. Three holds into 0.1% resistors give all three.
- **delta**, a voltage-channel offset. An R_p calibration line (L1) gives a
  second zero: on 2026-11-13, -0.091 mA against the resistors' -0.131 mA,
  one LSB apart. A voltage offset of -10 mV reconciles them exactly, and
  2026-11-08's DMM comparison read the voltage 6-7 mV low. A curved
  common-mode term would reconcile them as well, and these holds cannot
  tell the two apart. So ``delta`` is fitted only when a calibration is
  given, and both solutions are reported.

``fit_channel`` solves this from hold CSVs and writes a small text file;
``--zero FILE`` applies it (:mod:`ct_host.zero`): the zero and common-mode
term subtracted, the gain divided out, delta taken off the voltage, and rows
on the floor flagged ``floor`` so no fit uses them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .csvio import ContractError, Sweep, parse
from .extract.common import FitError
from .parallel import fit_sweep_resistor
from .recompute import recompute

__all__ = ["Floor", "ChannelModel", "ChannelFit", "fit_channel", "read_model",
           "is_model_file", "BOARD2_FLOOR", "HEADER"]

#: First line of a channel model file.
HEADER = "# curve-tracer channel"

#: One range-1 current count, mA.
LSB_MA = 3.3 / 4095 / 20 * 1000

#: Monte Carlo draws for the uncertainties.
MC_DRAWS = 4000


@dataclass(frozen=True)
class Floor:
    """The lowest reading the channel gives at node voltage ``v``."""

    ma: float
    ma_per_v: float
    #: A reading less than this above the floor counts as on it. Two counts:
    #: the 2026-11-13 diode's rows sat within 0.3 counts of the line until
    #: they left it, and the first row off it was 2.6 counts up.
    margin_ma: float = 2 * LSB_MA

    def at(self, v: float) -> float:
        return self.ma + self.ma_per_v * v

    def holds(self, i_total_ma: float, v: float) -> bool:
        """True if a reading of ``i_total_ma`` at ``v`` may be the floor."""
        return i_total_ma < self.at(v) + self.margin_ma

    @property
    def label(self) -> str:
        return (f"floor {self.ma:.4f} + {self.ma_per_v:.4f}·V mA "
                f"(+{self.margin_ma:.3f} mA margin)")


#: Board 2's floor: holds 22b, 22c, 22d and 22d3 of 2026-11-13, cap only.
BOARD2_FLOOR = Floor(0.1984, 0.1041)


@dataclass(frozen=True)
class ChannelModel:
    """What ``--zero FILE`` applies."""

    gain: float
    zero_ma: float
    cm_ma_per_v: float
    v_offset_v: float
    floor: Floor
    source: str
    stderr: dict[str, float]

    def true_ma(self, i_total_ma: float, v_meas: float) -> float:
        return (i_total_ma - self.zero_ma - self.cm_ma_per_v * v_meas) / self.gain

    def reading_ma(self, i_ma: float, v_true: float) -> float:
        """What the channel reads for ``i_ma`` at true voltage ``v_true``."""
        v = v_true + self.v_offset_v
        return max(self.floor.at(v),
                   self.gain * i_ma + self.zero_ma + self.cm_ma_per_v * v)

    def write(self, path: str | Path) -> Path:
        path = Path(path)
        items = [
            ("gain", f"{self.gain:.6f}"),
            ("zero_ma", f"{self.zero_ma:.5f}"),
            ("cm_ma_per_v", f"{self.cm_ma_per_v:.5f}"),
            ("v_offset_v", f"{self.v_offset_v:.5f}"),
            ("floor_ma", f"{self.floor.ma:.5f}"),
            ("floor_ma_per_v", f"{self.floor.ma_per_v:.5f}"),
            ("floor_margin_ma", f"{self.floor.margin_ma:.5f}"),
        ] + [(f"stderr_{k}", f"{v:.3g}") for k, v in self.stderr.items()]
        lines = [HEADER] + [f"{k}: {v}" for k, v in items] + [f"source: {self.source}"]
        path.write_text("\n".join(lines) + "\n")
        return path

    def describe(self, indent: str = "  ") -> str:
        def e(key: str, fmt: str) -> str:
            se = self.stderr.get(key)
            return "" if se is None else f" ± {se:{fmt}}"
        return "\n".join([
            f"{indent}g (current gain / voltage gain) = {self.gain:.5f}{e('gain', '.2g')}",
            f"{indent}b (zero)                        = {self.zero_ma:+.4f}{e('zero_ma', '.2g')} mA",
            f"{indent}c (common-mode)                 = {self.cm_ma_per_v:+.4f}{e('cm_ma_per_v', '.2g')} mA/V",
            f"{indent}delta (voltage offset)          = {self.v_offset_v * 1000:+.2f}"
            + ("" if "v_offset_v" not in self.stderr
               else f" ± {self.stderr['v_offset_v'] * 1000:.2g}") + " mV",
            f"{indent}{self.floor.label}",
        ])


def is_model_file(path: Path) -> bool:
    try:
        with path.open() as fh:
            return fh.readline().strip() == HEADER
    except (OSError, UnicodeDecodeError):
        return False


def read_model(path: str | Path) -> ChannelModel:
    path = Path(path)
    lines = path.read_text().splitlines()
    if not lines or lines[0].strip() != HEADER:
        raise ContractError(f"{path} is not a channel model (first line {HEADER!r})")
    kv = dict(ln.split(": ", 1) for ln in lines[1:] if ": " in ln)
    try:
        return ChannelModel(
            gain=float(kv["gain"]), zero_ma=float(kv["zero_ma"]),
            cm_ma_per_v=float(kv["cm_ma_per_v"]), v_offset_v=float(kv["v_offset_v"]),
            floor=Floor(float(kv["floor_ma"]), float(kv["floor_ma_per_v"]),
                        float(kv["floor_margin_ma"])),
            source=kv.get("source", str(path)),
            stderr={k[7:]: float(v) for k, v in kv.items() if k.startswith("stderr_")},
        )
    except KeyError as exc:
        raise ContractError(f"{path} lacks {exc.args[0]}") from None


# --------------------------------------------------------------------------
# Fitting
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class _Hold:
    name: str
    v: float
    i: float
    i_se: float
    n: int


def _hold(path: Path) -> _Hold:
    hold = parse(path.read_text(), require_end=True)
    if hold.meta.get("mode") != "hold":
        raise ContractError(f"{path} is not a hold (mode: {hold.meta.get('mode')})")
    rows = recompute(hold).valid_rows
    if len(rows) < 3:
        raise ContractError(f"{path} has {len(rows)} valid rows; need 3")
    v = np.array([r.v_meas for r in rows])
    i = np.array([r.i_total_ma for r in rows])
    # Medians: one hold (23c) carries two spikes in 22 rows, which move its
    # mean by 6 uA, 0.1% of its current.
    sd = 1.4826 * float(np.median(np.abs(i - np.median(i))))
    sd = sd if sd > 0 else float(i.std(ddof=1))
    return _Hold(path.name, float(np.median(v)), float(np.median(i)),
                 1.253 * sd / math.sqrt(i.size), int(i.size))


@dataclass(frozen=True)
class ChannelFit:
    """The fitted model, and what it was fitted from."""

    model: ChannelModel
    #: The same holds solved with delta held at zero (the card's g, b, c).
    no_offset: ChannelModel
    floor_holds: tuple[_Hold, ...]
    resistor_holds: tuple[tuple[_Hold, float], ...]
    calibration: tuple[float, float, float, str] | None   # slope, offset, offset se, name
    residuals_ma: tuple[float, ...]

    def describe(self) -> str:
        out = ["Channel model", "", "  floor, from holds with nothing drawing DC:"]
        for h in self.floor_holds:
            out.append(f"    {h.name}: {h.v:.4f} V, {h.i:+.4f} mA; line "
                       f"{self.model.floor.at(h.v):+.4f} "
                       f"({(h.i - self.model.floor.at(h.v)) * 1000:+.1f} uA)")
        out += ["", "  resistor holds (medians):"]
        for (h, r), res in zip(self.resistor_holds, self.residuals_ma):
            out.append(f"    {h.name}: {r:g} ohm, {h.v:.5f} V, {h.i:.5f} ± "
                       f"{h.i_se:.1g} mA; residual {res * 1000:+.1f} uA")
        out += ["", "  delta held at 0 (zero, gain and common-mode term only):",
                self.no_offset.describe("    ")]
        if self.calibration is not None:
            slope, off, off_se, name = self.calibration
            implied = self.no_offset.zero_ma
            out += ["", f"  R_p calibration {name}: line offset {off:+.4f} ± "
                        f"{off_se:.1g} mA against b = {implied:+.4f} mA from the "
                        f"resistors ({(off - implied) / LSB_MA:+.2f} LSB)",
                    "  delta fitted so the calibration's offset is the same zero:",
                    self.model.describe("    ")]
        out += ["", f"  written: {'delta fitted' if self.calibration else 'delta 0'}"]
        return "\n".join(out)


def _solve(holds: list[tuple[float, float, float]], delta: float
           ) -> np.ndarray:
    """g, b, c by least squares at a fixed delta. ``holds``: (V, I, R_kohm)."""
    a = np.array([[(v - delta) / r, 1.0, v] for v, _, r in holds])
    y = np.array([i for _, i, _ in holds])
    sol, *_ = np.linalg.lstsq(a, y, rcond=None)
    return sol


def _solve_delta(holds, slope: float, offset: float) -> tuple[float, np.ndarray]:
    """delta such that the calibration line's offset is the model's zero.

    For an R_p of conductance G read through the model,
    ``I = g (V - delta) G + b + c V``, so its line has slope ``g G + c`` and
    offset ``b - delta (slope - c)``.
    """
    def resid(d: float) -> float:
        g, b, c = _solve(holds, d)
        return b - d * (slope - c) - offset

    lo, hi = -0.2, 0.2
    rlo, rhi = resid(lo), resid(hi)
    if rlo * rhi > 0:
        raise FitError("no voltage offset within ±0.2 V reconciles the "
                       "calibration's zero with the resistors'")
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        rm = resid(mid)
        if rlo * rm <= 0:
            hi = mid
        else:
            lo, rlo = mid, rm
    d = 0.5 * (lo + hi)
    return d, _solve(holds, d)


def fit_channel(resistors: list[tuple[Path, float]], floor_holds: list[Path], *,
                calibration: Path | None = None, tolerance: float = 0.001,
                seed: int = 1) -> ChannelFit:
    """Solve the channel model from hold CSVs.

    ``resistors``: (hold, ohms) pairs, at least three, with at least two
    resistances; holds with the same value are taken to be the same part.
    ``tolerance`` is the resistors' (uniform, ±). ``floor_holds``: holds with
    nothing drawing DC, at two or more voltages.
    """
    fh = [_hold(p) for p in floor_holds]
    if len({round(h.v, 2) for h in fh}) < 2:
        raise FitError("the floor needs holds at two or more voltages")
    fa = np.array([[1.0, h.v] for h in fh])
    (f0, f1), *_ = np.linalg.lstsq(fa, np.array([h.i for h in fh]), rcond=None)
    floor = Floor(float(f0), float(f1))

    rh = [(_hold(p), ohm) for p, ohm in resistors]
    if len(rh) < 3 or len({ohm for _, ohm in rh}) < 2:
        raise FitError("need three resistor holds, with at least two resistances")
    for h, ohm in rh:
        if floor.holds(h.i, h.v):
            raise FitError(f"{h.name} reads {h.i:.4f} mA, on the channel's floor; "
                           f"it can't fix the linear part")
    base = [(h.v, h.i, ohm / 1000.0) for h, ohm in rh]

    cal = None
    if calibration is not None:
        fit = fit_sweep_resistor(parse(calibration.read_text(), require_end=True))
        slope = 1000.0 / fit.r.value
        cal = (slope, fit.offset_ma.value, fit.offset_ma.stderr or 0.0,
               calibration.name)

    def solve(holds, cal_vals):
        if cal_vals is None:
            return 0.0, _solve(holds, 0.0)
        return _solve_delta(holds, cal_vals[0], cal_vals[1])

    d0, (g0, b0, c0) = solve(base, None)
    d1, (g1, b1, c1) = solve(base, cal) if cal else (d0, (g0, b0, c0))

    # Uncertainty: resistor tolerance (one draw per resistance), each hold's
    # standard error, and the calibration offset's.
    rng = np.random.default_rng(seed)
    values = sorted({ohm for _, ohm in rh})
    draws0, draws1 = [], []
    for _ in range(MC_DRAWS):
        scale = {ohm: 1.0 + rng.uniform(-tolerance, tolerance) for ohm in values}
        holds = [(h.v, h.i + rng.normal(0.0, h.i_se), ohm * scale[ohm] / 1000.0)
                 for h, ohm in rh]
        d, sol = solve(holds, None)
        draws0.append([*sol, d])
        if cal:
            c_vals = (cal[0], cal[1] + rng.normal(0.0, cal[2]))
            d, sol = solve(holds, c_vals)
            draws1.append([*sol, d])

    def model(g, b, c, d, draws, note):
        sd = np.array(draws).std(axis=0)
        stderr = {"gain": float(sd[0]), "zero_ma": float(sd[1]),
                  "cm_ma_per_v": float(sd[2])}
        if note:
            stderr["v_offset_v"] = float(sd[3])
        src = ("; ".join(f"{h.name}={ohm:g}" for h, ohm in rh)
               + f"; floor {', '.join(h.name for h in fh)}"
               + (f"; delta from {cal[3]}" if note else "")
               + f"; resistors ±{tolerance * 100:g}%")
        return ChannelModel(float(g), float(b), float(c), float(d), floor, src, stderr)

    m0 = model(g0, b0, c0, 0.0, draws0, False)
    m1 = model(g1, b1, c1, d1, draws1, True) if cal else m0
    res = tuple(h.i - (g1 * (h.v - d1) / (ohm / 1000.0) + b1 + c1 * h.v)
                for h, ohm in rh)
    return ChannelFit(m1, m0, tuple(fh), tuple(rh), cal, res)


def parse_resistor_arg(text: str) -> tuple[Path, float]:
    """``CSV=OHM``."""
    path, sep, ohm = text.rpartition("=")
    if not sep:
        raise ValueError(f"--resistor {text!r}: expected CSV=OHM")
    return Path(path), float(ohm)


def floor_rows(sweep: Sweep, floor: Floor) -> int:
    """How many valid rows of ``sweep`` read the floor."""
    return sum(floor.holds(r.i_total_ma, r.v_meas) for r in sweep.valid_rows)
