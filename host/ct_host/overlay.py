"""Closing the loop on the desk: simulate the extracted model, overlay it.

Blueprint §5 item 5, and the last step of ``device -> measurement -> model ->
simulation``. Three commands, one per step:

    python -m ct_host model    h4/d.csv --type diode --name D1N4148_CT -o h4/d.lib
    python -m ct_host simulate h4/d.lib --like h4/d.csv -o h4/d_sim.csv
    python -m ct_host overlay  h4/d.csv h4/d_sim.csv --save media/d_overlay.png

**What is simulated.** A voltage source sits directly across the device, swept
over the Kelvin-measured voltage range of the capture, with the gate held at
each measured step's commanded V_GS. The instrument's R_iso, PTC and shunt are
outside the Kelvin sense, so they are not in the comparison, and nothing
needs them. The device's own series resistance is in the card as ``RS``, the
same R_s the extraction fitted. Any R_p across D-S has already been taken
out of the measured current (:mod:`ct_host.parallel`), so the simulated
circuit is the device alone.

**The residual is the honest part of the figure.** For a diode it is
``V_meas - V_model(I_meas)`` in mV, because the extraction regresses voltage
on ln I and a voltage residual stays readable across decades of current. For
a MOSFET it is ``I_meas - I_model(V_meas)`` in mA, per gate step. Points the
extraction did not use (below its current floor) are drawn hollow, so a
reader can see which part of the curve the model was fitted to.

ngspice runs in batch mode. Blueprint §6's validation names LTspice; the card
is plain SPICE and runs unchanged in either, so ngspice is used because it
runs headless on any machine the host runs on.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .csvio import Sweep
from .dataset import family_of
from .plot import is_two_terminal
from .extract.diode import I_FLOOR_LSB as DIODE_FLOOR_LSB
from .extract.mosfet import I_FLOOR_LSB as MOSFET_FLOOR_LSB
from .recompute import Calibration

__all__ = ["ModelCard", "read_card", "simulate", "SimCurves", "read_sim",
           "write_sim", "plot_overlay"]

#: Palette slots (dataviz reference palette, light surface).
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4",
          "#008300", "#6250d6", "#e34948"]


@dataclass(frozen=True)
class ModelCard:
    path: Path
    name: str
    kind: str                 # "diode" | "mosfet"
    params: dict[str, float]
    text: str

    def summary(self) -> str:
        keys = ("IS", "N", "RS") if self.kind == "diode" else ("VTO", "KP", "LAMBDA")
        return ", ".join(f"{k} = {self.params[k]:.4g}" for k in keys
                         if k in self.params)


def read_card(path: str | Path) -> ModelCard:
    path = Path(path)
    text = path.read_text()
    m = re.search(r"^\.model\s+(\S+)\s+(\w+)", text, re.M | re.I)
    if m is None:
        raise ValueError(f"{path} has no .model line")
    name, mtype = m.group(1), m.group(2).upper()
    kind = {"D": "diode", "NMOS": "mosfet"}.get(mtype)
    if kind is None:
        raise ValueError(f"{path}: model type {mtype} is not D or NMOS")
    params = {k.upper(): float(v) for k, v in
              re.findall(r"^\+\s*(\w+)\s*=\s*([-+0-9.eE]+)", text, re.M)}
    return ModelCard(path, name, kind, params, text)


@dataclass(frozen=True)
class SimCurves:
    """Simulated I-V: one ``(vgs, v, i_ma)`` curve per gate step."""

    kind: str
    curves: tuple[tuple[float, np.ndarray, np.ndarray], ...]
    meta: dict[str, str]


def _ngspice() -> str:
    exe = shutil.which("ngspice")
    if exe is None:
        raise FileNotFoundError("ngspice is not on PATH (brew install ngspice)")
    return exe


def _version(exe: str) -> str:
    out = subprocess.run([exe, "--version"], capture_output=True, text=True).stdout
    m = re.search(r"ngspice-\S+", out)
    return m.group(0) if m else "ngspice"


def _run_dc(exe: str, card: ModelCard, vmax: float, step: float,
            vgs: float | None, workdir: Path) -> tuple[np.ndarray, np.ndarray]:
    out = workdir / "dc.dat"
    if card.kind == "diode":
        circuit = f"VD a 0 0\nD1 a 0 {card.name}\n"
    else:
        circuit = (f"VD d 0 0\nVG g 0 {vgs!r}\n"
                   f"M1 d g 0 0 {card.name} W=100u L=100u\n")
    netlist = (f"* ct_host simulate: {card.path.name}\n"
               f".include {card.path.resolve()}\n{circuit}"
               f".control\nset wr_singlescale\n"
               f"dc VD 0 {vmax!r} {step!r}\n"
               f"wrdata {out} -i(VD)\n.endc\n.end\n")
    deck = workdir / "deck.cir"
    deck.write_text(netlist)
    proc = subprocess.run([exe, "-b", str(deck)], capture_output=True,
                          text=True, cwd=workdir)
    if not out.exists():
        raise RuntimeError(f"ngspice failed on {card.path}:\n{proc.stdout[-2000:]}"
                           f"{proc.stderr[-2000:]}")
    data = np.loadtxt(out)
    out.unlink()
    return data[:, 0], data[:, 1] * 1000.0


def simulate(card: ModelCard, like: Sweep, *, step: float = 0.002) -> SimCurves:
    """Sweep the card over the capture's measured range, per gate step."""
    exe = _ngspice()
    fam = family_of(like)
    vmax = max(float(c.v.max()) for c in fam) * 1.02
    steps: list[float | None] = ([None] if card.kind == "diode"
                                 else [c.vgs for c in fam])
    curves = []
    with tempfile.TemporaryDirectory() as tmp:
        for vgs in steps:
            v, i = _run_dc(exe, card, vmax, step, vgs, Path(tmp))
            curves.append((0.0 if vgs is None else vgs, v, i))
    meta = {
        "simulator": _version(exe),
        "model_card": str(card.path),
        "model": f"{card.name} ({card.summary()})",
        "kind": card.kind,
        "circuit": ("voltage source across the device at the Kelvin-measured "
                    "voltage; gate at each step's commanded V_GS"
                    if card.kind == "mosfet" else
                    "voltage source across the device at the Kelvin-measured "
                    "voltage"),
    }
    return SimCurves(card.kind, tuple(curves), meta)


def write_sim(sim: SimCurves, path: str | Path, *, like: str | None = None) -> Path:
    path = Path(path)
    lines = ["# ct_host simulated I-V -- SIMULATION, not a measurement"]
    lines += [f"# {k}: {v}" for k, v in sim.meta.items()]
    if like:
        lines.append(f"# like: {like}")
    lines.append("vgs_v,v_v,i_ma")
    for vgs, v, i in sim.curves:
        lines += [f"{vgs:.4f},{a:.6g},{b:.6g}" for a, b in zip(v, i)]
    path.write_text("\n".join(lines) + "\n")
    return path


def read_sim(path: str | Path) -> SimCurves:
    meta: dict[str, str] = {}
    rows: list[tuple[float, float, float]] = []
    for line in Path(path).read_text().splitlines():
        if line.startswith("#"):
            key, sep, value = line[1:].partition(":")
            if sep:
                meta[key.strip()] = value.strip()
        elif line and not line.startswith("vgs_v"):
            a, b, c = (float(x) for x in line.split(","))
            rows.append((a, b, c))
    arr = np.array(rows)
    curves = tuple((g, arr[arr[:, 0] == g, 1], arr[arr[:, 0] == g, 2])
                   for g in sorted(set(arr[:, 0])))
    return SimCurves(meta.get("kind", "diode"), curves, meta)


# --------------------------------------------------------------------------
# The figure
# --------------------------------------------------------------------------

def _style(ax) -> None:
    ax.set_facecolor(SURFACE)
    ax.grid(True, color="#e4e3df", linewidth=0.6)
    ax.tick_params(colors=INK_2, labelsize=8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#bdbcb7")
    ax.xaxis.label.set_color(INK)
    ax.yaxis.label.set_color(INK)


def _measured_label(sweep: Sweep) -> str:
    return ("ct_sim capture (SIMULATED, not a bench measurement)"
            if sweep.meta.is_simulated else "measured, curve tracer")


def plot_overlay(sweep: Sweep, sim: SimCurves, *, title: str | None = None):
    """Measured against simulated, with residuals. Returns the figure."""
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(10.0, 6.6), facecolor=SURFACE)
    cal = Calibration.from_sweep(sweep)
    device = title or sweep.meta.device
    if is_two_terminal(r.vgs_set_v for r in sweep.rows):
        # A diode-like capture is titled with the device alone; the
        # [SIMULATED] marker stays, so a ct_sim figure can't pass for a
        # bench one.
        head = f"{device} [SIMULATED]" if sweep.meta.is_simulated else device
    else:
        head = f"{device}: {_measured_label(sweep).split(',')[0]} vs. simulated with the extracted model"
        if sweep.meta.is_simulated:
            head = f"{device} [SIMULATED]: pipeline check on ct_sim data"
    fig.suptitle(head, x=0.01, ha="left", fontsize=12, color=INK, y=0.995)
    sub = [f"Model {sim.meta.get('model', '')}, simulated in "
           f"{sim.meta.get('simulator', 'ngspice')}: {sim.meta.get('circuit', '')}."]
    if sweep.r_parallel is not None:
        sub.append(sweep.r_parallel.label + ".")
    fig.text(0.01, 0.945, "\n".join(_wrap(s, 150) for s in sub), fontsize=7.5,
             color=INK_2, va="top")

    if sim.kind == "diode":
        _diode_panels(fig, sweep, sim, cal)
    else:
        _mosfet_panels(fig, sweep, sim, cal)
    fig.subplots_adjust(left=0.07, right=0.98 if sim.kind == "diode" else 0.76,
                        top=0.86, bottom=0.08, hspace=0.38, wspace=0.22)
    return fig


def _wrap(text: str, width: int) -> str:
    import textwrap
    return "\n".join(textwrap.wrap(text, width))


def _diode_panels(fig, sweep: Sweep, sim: SimCurves, cal: Calibration) -> None:
    gs = fig.add_gridspec(2, 2, height_ratios=[3, 1.6])
    ax_lin, ax_log = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1])
    ax_res = fig.add_subplot(gs[1, :])
    curve = family_of(sweep).curves[0]
    v, i = curve.v, curve.i_ma
    floor = DIODE_FLOOR_LSB * cal.i_lsb_ma
    used = i > floor
    _, v_sim, i_sim = sim.curves[0]
    meas = _measured_label(sweep)

    for ax, log in ((ax_lin, False), (ax_log, True)):
        _style(ax)
        ax.plot(v_sim, i_sim, color=SERIES[1], linewidth=2.0, label="simulated, extracted model",
                zorder=2)
        ax.plot(v[used], i[used], "o", markersize=4.5, color=SERIES[0],
                markeredgecolor=SURFACE, markeredgewidth=0.8, label=meas, zorder=3)
        ax.plot(v[~used], i[~used], "o", markersize=4.5, markerfacecolor="none",
                markeredgecolor=SERIES[0], label=f"not fitted (< {floor:.2f} mA)",
                zorder=3)
        ax.set_xlabel("V across the diode, Kelvin-sensed (V)", fontsize=9)
        ax.set_ylabel("I (mA)", fontsize=9)
        if log:
            ax.set_yscale("log")
            ax.set_ylim(cal.i_lsb_ma / 4, max(i.max(), i_sim.max()) * 1.5)
            ax.set_title("semilog", fontsize=9, color=INK_2, loc="left")
        else:
            ax.set_title("linear", fontsize=9, color=INK_2, loc="left")
    ax_lin.legend(fontsize=7.5, loc="upper left", frameon=False)

    _style(ax_res)
    order = np.argsort(i_sim)
    ok = i >= cal.i_lsb_ma
    v_model = np.interp(np.log(i[ok]), np.log(np.clip(i_sim[order], 1e-12, None)),
                        v_sim[order])
    dv = (v[ok] - v_model) * 1000.0
    used_ok = used[ok]
    ax_res.axhline(0.0, color=INK_2, linewidth=0.8)
    ax_res.plot(i[ok][used_ok], dv[used_ok], "o", markersize=4.5, color=SERIES[0],
                markeredgecolor=SURFACE, markeredgewidth=0.8)
    ax_res.plot(i[ok][~used_ok], dv[~used_ok], "o", markersize=4.5,
                markerfacecolor="none", markeredgecolor=SERIES[0])
    ax_res.set_xscale("log")
    ax_res.set_xlabel("I (mA)", fontsize=9)
    ax_res.set_ylabel("V meas − V model (mV)", fontsize=9)
    rms = float(np.sqrt(np.mean(dv[used_ok] ** 2))) if used_ok.any() else float("nan")
    ax_res.set_title(f"residual at the measured current, from 1 LSB "
                     f"({cal.i_lsb_ma:.3f} mA) up: rms {rms:.2f} mV over the "
                     f"{int(used_ok.sum())} fitted points", fontsize=9,
                     color=INK_2, loc="left")


def _mosfet_panels(fig, sweep: Sweep, sim: SimCurves, cal: Calibration) -> None:
    gs = fig.add_gridspec(2, 1, height_ratios=[3, 1.6])
    ax, ax_res = fig.add_subplot(gs[0]), fig.add_subplot(gs[1], sharex=None)
    _style(ax)
    _style(ax_res)
    floor = MOSFET_FLOOR_LSB * cal.i_lsb_ma
    sim_by_vgs = {round(g, 4): (vv, ii) for g, vv, ii in sim.curves}
    curves = [c for c in family_of(sweep) if c.i_ma.max() > floor]
    if len(curves) > len(SERIES):
        curves = curves[-len(SERIES):]
    worst = 0.0
    for k, c in enumerate(curves):
        color = SERIES[k]
        vv, ii = sim_by_vgs[round(c.vgs, 4)]
        ax.plot(vv, ii, color=color, linewidth=2.0)
        ax.plot(c.v, c.i_ma, "o", markersize=4, color=color,
                markeredgecolor=SURFACE, markeredgewidth=0.6,
                label=f"V_GS = {c.vgs:.2f} V")
        di = c.i_ma - np.interp(c.v, vv, ii)
        ax_res.plot(c.v, di, "o-", markersize=3.5, linewidth=0.8, color=color)
        worst = max(worst, float(np.abs(di).max()))
    ax.plot([], [], color=INK_2, linewidth=2.0, label="lines: simulated,\nextracted model")
    ax.plot([], [], "o", color=INK_2, markersize=4,
            label=("points: ct_sim capture,\nSIMULATED" if sweep.meta.is_simulated
                   else "points: measured,\ncurve tracer"))
    ax.legend(fontsize=7.5, loc="upper left", bbox_to_anchor=(1.01, 1.0),
              frameon=False)
    ax.set_xlabel("V_DS, Kelvin-sensed (V)", fontsize=9)
    ax.set_ylabel("I_D (mA)", fontsize=9)
    ax_res.axhline(0.0, color=INK_2, linewidth=0.8)
    ax_res.set_xlabel("V_DS (V)", fontsize=9)
    ax_res.set_ylabel("I meas − I model (mA)", fontsize=9)
    ax_res.set_title(f"residual per gate step; largest {worst:.3f} mA "
                     f"(1 LSB = {cal.i_lsb_ma:.4f} mA)", fontsize=9,
                     color=INK_2, loc="left")
