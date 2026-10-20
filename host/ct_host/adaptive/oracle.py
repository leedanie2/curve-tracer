"""Where measurements come from during the evaluation.

One interface, so every design (dense ramp, sparse ramp, adaptive) and every
estimator runs unchanged against each back end:

``SyntheticOracle``
    A device from :mod:`.devices` behind the :mod:`.frontend` signal chain,
    with a thermal state driven by the timed power sequence, and the
    :mod:`.timing` link model. Everything the offline study needs.

``PoolOracle``
    A dense capture loaded from a CSV, used as a pool: a proposed point must be
    a commanded code present in the file, and its row is what comes back. This
    is how dense **bench** sweeps get evaluated later -- a file argument, not a
    rewrite. It inherits that capture's thermal history, so it cannot say
    anything about point order; only a live session on hardware can.

Two commands are modelled. ``sweep()`` is today's ``SWEEP``. ``points()`` is
the **proposed** points session of plan §5.2 (``POINTS`` / ``PT`` / ``END``),
which does not exist in the firmware yet; phase 1 models its timing and its
current-limit ordering so the evaluation can ask whether it is worth building.
Its rows are rendered with the two extra columns of plan option S1
(``batch,t_us``) for byte counting only.

Both commands keep the firmware's §4 ordering: measure, compare against
``i_limit_ma``, zero the drain **before** the offending row is emitted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import numpy as np

from ..csvio import Metadata, Row, Sweep, parse_stream, MetaLine, parse
from ..recompute import recompute
from .devices import Device, T_REF_K
from .frontend import (POINTS_EXTRA_COLUMNS, FrontEnd, render_header,
                       render_row)
from .timing import Breakdown, LinkModel, TxRing
from ..csvio import EXPECTED_COLUMNS

__all__ = ["Point", "OracleBase", "SyntheticOracle", "PoolOracle",
           "ProtocolError", "PT_LINE_MAX"]

#: ``CT_CMD_LINE_MAX`` is 160 including the terminator; leave headroom.
PT_LINE_MAX = 150


class ProtocolError(RuntimeError):
    """A request the (modelled) firmware would reject."""


@dataclass
class Point:
    """One measured point and everything known about how it was taken."""

    row: Row
    gate_index: int
    code: int
    batch: int
    t_set_s: float               # instrument clock when the drain DAC was written
    dwell_s: float = 0.0         # until the drain DAC next changed
    tj_k: float = T_REF_K        # junction temperature at the measurement
    power_w: float = 0.0
    #: unquantised truth at the moment of measurement (synthetic only)
    true_v: float | None = None
    true_i_ma: float | None = None


@dataclass
class Capture:
    """What one command returned."""

    points: list[Point] = field(default_factory=list)
    end_reason: str | None = None

    @property
    def rows(self) -> list[Row]:
        return [p.row for p in self.points]


class OracleBase:
    """The instrument clock, TX ring and command framing shared by both."""

    def __init__(self, fe: FrontEnd, *, vgs_list: Sequence[float],
                 vds_max: float, i_limit_ma: float, device_name: str,
                 link: LinkModel | None = None, source: str = "") -> None:
        self.fe = fe
        self.link = link or LinkModel()
        self.vgs_list = [float(v) for v in vgs_list]
        self.vds_max = float(vds_max)
        self.i_limit_ma = float(i_limit_ma)
        self.device_name = device_name
        self.source = source
        self.clock = 0.0
        self.breakdown = Breakdown()
        self.ring = TxRing(self.link)
        self.power_w = 0.0
        self.session_open = False
        self.session_ended: str | None = None
        self.session_points = 0
        self.session_t0 = 0.0
        self.history: list[Point] = []
        self._last: Point | None = None
        self.gate_codes = [fe.gate_code(v) for v in self.vgs_list]
        self.gate_volts = [float(fe.gate_volts(c)) for c in self.gate_codes]
        self.max_code = fe.volts_to_code(self.vds_max)

    # -- clock --------------------------------------------------------------

    def _advance(self, dt: float, bucket: str) -> None:
        if dt <= 0.0:
            return
        self._thermal_step(dt)
        self.clock += dt
        self.breakdown.add(bucket, dt)

    def _thermal_step(self, dt: float) -> None:      # overridden
        del dt

    def _set_bias_power(self, power_w: float) -> None:
        """A DAC write: close the previous point's dwell, change the power."""
        if self._last is not None and self._last.dwell_s == 0.0:
            self._last.dwell_s = self.clock - self._last.t_set_s
        self.power_w = power_w

    def idle(self, dt: float, bucket: str = "compute") -> None:
        """Host-side time with the drain at zero (between commands)."""
        self._set_bias_power(0.0)
        self._advance(dt, bucket)

    def _upload(self, nbytes: int) -> None:
        self._advance(nbytes * self.link.byte_s, "command")
        self._advance(self.link.usb_latency_s, "latency")

    def _emit(self, nbytes: int) -> None:
        wait = self.ring.wait_for_room(self.clock, nbytes)
        self._advance(wait, "tx")
        self.ring.push(self.clock, nbytes)

    def _host_waits_for_output(self) -> None:
        self._advance(self.ring.empty_after(self.clock), "tx")
        self._advance(self.link.usb_latency_s, "latency")

    def configure(self, n_set: int = 4) -> None:
        """The SET commands any capture starts with; each is a round trip."""
        for _ in range(n_set):
            self._upload(len("SET vgs_list 2.6,2.76,2.92") + 2)
            self._emit(len("# ok: vgs_count=6") + 2)
            self._host_waits_for_output()

    def header_lines(self, mode: str, n: int) -> list[str]:
        columns = (EXPECTED_COLUMNS if mode != "points"
                   else EXPECTED_COLUMNS + POINTS_EXTRA_COLUMNS)
        return render_header(self.fe, device=self.device_name, mode=mode, n=n,
                             i_limit_ma=self.i_limit_ma, vds_max=self.vds_max,
                             vgs_list=self.vgs_list, columns=columns,
                             schema=2 if mode != "points" else 3)

    def metadata(self, n: int = 200) -> Metadata:
        """The dc-mode header as parsed metadata, for building Sweeps."""
        cache = self.__dict__.setdefault("_meta_cache", {})
        if n in cache:
            return cache[n]
        items, lines = [], []
        for ev in parse_stream(self.header_lines("dc", n)):
            if isinstance(ev, MetaLine):
                items.append((ev.key, ev.value))
                lines.append(ev.raw)
        if self.source:
            items.append(("host_source", self.source))
            lines.append(f"# host_source: {self.source}")
        cache[n] = Metadata(items, lines)
        return cache[n]

    # -- backend hooks --------------------------------------------------------

    def available_codes(self, gate_index: int) -> np.ndarray:
        return np.arange(0, self.max_code + 1)

    def nearest_code(self, gate_index: int, code: int) -> int:
        """The closest code this oracle can serve (every code, here)."""
        return int(min(max(code, 0), self.max_code))

    def _acquire(self, gate_index: int, codes: np.ndarray) -> list[dict]:
        raise NotImplementedError

    @property
    def sequential(self) -> bool:
        """True when each point depends on the last (a thermal state)."""
        return False

    # -- one point ------------------------------------------------------------

    def _measure(self, gate_index: int, code: int, point_index: int,
                 batch: int, points_mode: bool, acquired: dict | None) -> Point:
        t_set = self.clock
        if acquired is None:
            acquired = self._acquire(gate_index, np.array([code]))[0]
        self._set_bias_power(acquired["power_w"])
        self._advance(self.link.measure_s(self.fe.settle_us), "measure")

        v_meas, i_ma = acquired["v_meas"], acquired["i_ma"]
        flags = ""
        tripped_at = None
        if i_ma > self.i_limit_ma:
            # Section 4: zero the drain before the row is emitted.
            self.power_w = 0.0
            tripped_at = self.clock
            flags = "ilimit"
        vds_set = float(self.fe.code_to_volts(code))
        extra_cols: tuple = ()
        if points_mode:
            extra_cols = (batch, int(round((t_set - self.session_t0) * 1e6)))
        raw = render_row(point_index, self.gate_volts[gate_index], vds_set,
                         v_meas, i_ma, acquired["i_acc"], acquired["v_acc"],
                         flags, extra_cols)
        row = Row(point=point_index, vgs_set_v=round(self.gate_volts[gate_index], 3),
                  vds_set_v=round(vds_set, 3), vds_meas_v=round(v_meas, 3),
                  i_meas_ma=round(i_ma, 4), i_acc=int(acquired["i_acc"]),
                  v_acc=int(acquired["v_acc"]), range=1, flags=flags, raw=raw)
        self._emit(len(raw) + 2)
        p = Point(row=row, gate_index=gate_index, code=int(code), batch=batch,
                  t_set_s=t_set, tj_k=acquired.get("tj_k", T_REF_K),
                  power_w=acquired["power_w"], true_v=acquired.get("true_v"),
                  true_i_ma=acquired.get("true_i_ma"))
        if tripped_at is not None:
            p.dwell_s = tripped_at - t_set
        self.history.append(p)
        self._last = p
        return p

    def _run_points(self, plan: list[tuple[int, int]], batch: int,
                    first_index: int, points_mode: bool) -> Capture:
        cap = Capture()
        pre: list[dict | None] = [None] * len(plan)
        if not self.sequential and plan:
            # No state couples the points: solve them together.
            by_gate: dict[int, list[int]] = {}
            for k, (g, _) in enumerate(plan):
                by_gate.setdefault(g, []).append(k)
            for g, ks in by_gate.items():
                got = self._acquire(g, np.array([plan[k][1] for k in ks]))
                for k, a in zip(ks, got):
                    pre[k] = a
        for k, (g, code) in enumerate(plan):
            p = self._measure(g, code, first_index + k, batch, points_mode,
                              pre[k])
            cap.points.append(p)
            if p.row.flags:
                cap.end_reason = "ilimit"
                break
        return cap

    # -- SWEEP ------------------------------------------------------------------

    def sweep(self, n: int) -> Capture:
        """Today's SWEEP: header, ``n`` ramp points per gate step, end line."""
        if self.session_open:
            raise ProtocolError("SWEEP while a points session is open")
        self._upload(len("SWEEP") + 2)
        for line in self.header_lines("dc", n):
            self._emit(len(line) + 2)
        codes = self.fe.ramp_codes(n, self.vds_max)
        out = Capture()
        index = 0
        for g in range(len(self.vgs_list)):
            plan = [(g, c) for c in codes]
            cap = self._run_points(plan, 0, index, False)
            out.points.extend(cap.points)
            index += len(cap.points)
            self._set_bias_power(0.0)        # drain to zero between gate steps
            if cap.end_reason == "ilimit":
                out.end_reason = "ilimit"
                break
        out.end_reason = out.end_reason or "ok"
        self._emit(len(f"# end: {out.end_reason}") + 2)
        self._host_waits_for_output()
        return out

    # -- the proposed points session -------------------------------------------

    def open_points(self) -> None:
        self._upload(len("POINTS") + 2)
        for line in self.header_lines("points", 0):
            self._emit(len(line) + 2)
        self._host_waits_for_output()
        self.session_open = True
        self.session_ended = None
        self.session_points = 0
        self.session_t0 = self.clock

    @staticmethod
    def pt_lines(plan: list[tuple[int, int]]) -> list[list[tuple[int, int]]]:
        """Split a batch into ``PT`` lines that fit the command buffer."""
        lines: list[list[tuple[int, int]]] = []
        current: list[tuple[int, int]] = []
        length = len("PT")
        for g, c in plan:
            token = f" {g}:{c}"
            if current and length + len(token) > PT_LINE_MAX:
                lines.append(current)
                current, length = [], len("PT")
            current.append((g, c))
            length += len(token)
        if current:
            lines.append(current)
        return lines

    def validate(self, plan: list[tuple[int, int]]) -> None:
        """Whole-line validation before any DAC write (plan §5.2)."""
        for g, c in plan:
            if not 0 <= g < len(self.vgs_list):
                raise ProtocolError(f"gate index {g} outside vgs_list")
            if not 0 <= c <= self.max_code:
                raise ProtocolError(f"code {c} outside 0..{self.max_code}")

    def points(self, plan: list[tuple[int, int]], batch: int) -> Capture:
        if not self.session_open:
            raise ProtocolError(f"no points session (ended: {self.session_ended})")
        self.validate(plan)
        lines = self.pt_lines(plan)
        upload = sum(len("PT") + sum(len(f" {g}:{c}") for g, c in ln) + 2
                     for ln in lines)
        # Lines are pipelined: one latency, then the bytes.
        self._advance(upload * self.link.byte_s, "command")
        self._advance(self.link.usb_latency_s, "latency")
        out = Capture()
        for ln in lines:
            cap = self._run_points(ln, batch, self.session_points, True)
            out.points.extend(cap.points)
            self.session_points += len(cap.points)
            self._set_bias_power(0.0)         # drain and gate to zero per line
            if cap.end_reason == "ilimit":
                out.end_reason = "ilimit"
                self._emit(len("# end: ilimit") + 2)
                self.session_open = False
                self.session_ended = "ilimit"
                break
            self._emit(len(f"# ok: pt={len(ln)}") + 2)
        self._host_waits_for_output()
        return out

    def close_points(self) -> None:
        if not self.session_open:
            return
        self._upload(len("END") + 2)
        self._emit(len("# end: ok") + 2)
        self._host_waits_for_output()
        self.session_open = False
        self.session_ended = "ok"

    # -- helpers ----------------------------------------------------------------

    def inputs(self, points: Sequence[Point]) -> np.ndarray:
        """GP inputs: the exact DAC gate voltage and the measured drain voltage.

        Not ``vgs_set_v``: the CSV rounds it to 1 mV, which moves V_ov by up
        to 0.5 mV -- 1-2 LSB of current at the top gate step, and a per-gate
        offset the residual GP then reports as model mismatch. The gate code
        is known exactly, so its voltage is used instead.
        """
        sw = self.as_sweep(points)
        return np.array([[self.gate_volts[p.gate_index], r.v_dut]
                         for p, r in zip(points, sw.rows)])

    def as_sweep(self, points: Sequence[Point], n: int = 200) -> Sweep:
        """Measured points as a recomputed Sweep the extractors accept."""
        key = (n, len(points), id(points[0]) if points else 0,
               id(points[-1]) if points else 0)
        cached = self.__dict__.get("_sweep_cache")
        if cached is not None and cached[0] == key:
            return cached[1]
        sweep = recompute(Sweep(meta=self.metadata(n), rows=[p.row for p in points],
                                end_reason="ok"))
        self._sweep_cache = (key, sweep)
        return sweep


class SyntheticOracle(OracleBase):
    """A synthetic device behind the modelled instrument."""

    def __init__(self, device: Device, *, fe: FrontEnd | None = None,
                 vgs_list: Sequence[float], vds_max: float,
                 i_limit_ma: float = 60.0, noise_lsb: float = 0.0,
                 seed: int = 0, link: LinkModel | None = None,
                 thermal_scale: float = 1.0) -> None:
        fe = fe or FrontEnd()
        super().__init__(fe, vgs_list=vgs_list, vds_max=vds_max,
                         i_limit_ma=i_limit_ma, device_name=device.name,
                         link=link,
                         source=f"synthetic {device.name} noise_lsb={noise_lsb:g} "
                                f"seed={seed} ({device.description})")
        self.device = device
        self.noise_lsb = float(noise_lsb)
        self.rng = np.random.default_rng(seed)
        self.thermal = (device.thermal.scaled(thermal_scale)
                        if device.thermal is not None else None)
        self.tstate = (np.zeros(len(self.thermal.r_k_per_w))
                       if self.thermal is not None else None)

    @property
    def sequential(self) -> bool:
        return self.thermal is not None

    @property
    def tj_k(self) -> float:
        return T_REF_K + (float(self.tstate.sum()) if self.tstate is not None else 0.0)

    def _thermal_step(self, dt: float) -> None:
        if self.thermal is not None:
            self.tstate = self.thermal.step(self.tstate, self.power_w, dt)

    def _acquire(self, gate_index: int, codes: np.ndarray) -> list[dict]:
        fe = self.fe
        codes = np.asarray(codes, dtype=int)
        v_node = fe.code_to_volts(codes)
        vgs = np.full(codes.shape, self.gate_volts[gate_index])
        tj = self.tj_k
        v, j = fe.solve(self.device, vgs, v_node, tj)
        ic, vc = fe.counts(v, j)
        sigma = self.noise_lsb
        i_acc = fe.accumulate(ic, sigma, self.rng)
        v_acc = fe.accumulate(vc, sigma, self.rng)
        v_meas, i_ma = fe.firmware_values(i_acc, v_acc)
        out = []
        for k in range(codes.size):
            out.append({
                "v_meas": float(v_meas[k]), "i_ma": float(i_ma[k]),
                "i_acc": int(i_acc[k]), "v_acc": int(v_acc[k]),
                "power_w": float(max(v[k] * j[k], 0.0)), "tj_k": tj,
                "true_v": float(v[k]), "true_i_ma": float(j[k] * 1000.0),
            })
        return out


class PoolOracle(OracleBase):
    """A dense capture as a candidate pool (bench sweeps, later)."""

    def __init__(self, path_or_sweep: str | Path | Sweep, *,
                 fe: FrontEnd | None = None, link: LinkModel | None = None,
                 i_limit_ma: float | None = None) -> None:
        sweep = (path_or_sweep if isinstance(path_or_sweep, Sweep)
                 else parse(Path(path_or_sweep).read_text(), require_end=True))
        meta = sweep.meta
        fe = fe or FrontEnd(oversample_n=meta.oversample_n,
                            settle_us=meta.int("settle_us"))
        super().__init__(fe, vgs_list=list(meta.vgs_list),
                         vds_max=meta.float("vds_max"),
                         i_limit_ma=(i_limit_ma if i_limit_ma is not None
                                     else meta.float("i_limit_ma")),
                         device_name=meta.device, link=link,
                         source=meta.get("host_source", "") or
                         f"pool {getattr(path_or_sweep, 'name', 'sweep')}")
        self.pool_sweep = sweep
        self.pool: dict[tuple[int, int], Row] = {}
        for row in sweep.rows:
            g = int(np.argmin([abs(row.vgs_set_v - gv) for gv in self.gate_volts]))
            code = fe.volts_to_code(row.vds_set_v)
            self.pool[(g, code)] = row
        self._codes = {g: np.array(sorted(c for (gg, c) in self.pool if gg == g))
                       for g in range(len(self.vgs_list))}

    def available_codes(self, gate_index: int) -> np.ndarray:
        return self._codes[gate_index]

    def nearest_code(self, gate_index: int, code: int) -> int:
        codes = self._codes[gate_index]
        return int(codes[np.argmin(np.abs(codes - code))])

    def sweep(self, n: int) -> Capture:
        # A ramp the pool did not take is snapped to its nearest pool codes;
        # the timing is still that of an n-point SWEEP.
        return super().sweep(n)

    def _run_points(self, plan, batch, first_index, points_mode):
        if not points_mode:
            plan = [(g, c if (g, c) in self.pool else self.nearest_code(g, c))
                    for g, c in plan]
        return super()._run_points(plan, batch, first_index, points_mode)

    def points(self, plan, batch):
        missing = [(g, c) for g, c in plan if (g, c) not in self.pool]
        if missing:
            raise ProtocolError(f"{len(missing)} proposed points are not in the "
                                f"pool, e.g. {missing[0]}")
        return super().points(plan, batch)

    def _acquire(self, gate_index: int, codes: np.ndarray) -> list[dict]:
        out = []
        for c in np.atleast_1d(codes):
            row = self.pool[(gate_index, int(c))]
            out.append({"v_meas": row.vds_meas_v, "i_ma": row.i_meas_ma,
                        "i_acc": row.i_acc, "v_acc": row.v_acc,
                        "power_w": 0.0})
        return out
