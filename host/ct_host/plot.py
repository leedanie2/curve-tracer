"""Plotting the I-V family, live as it arrives and as a finished figure.

**The x-axis is ``vds_meas_v``, never ``vds_set_v``.** The whole reason the
instrument carries a four-wire sense is that the commanded voltage is wrong by
over a volt at full current (blueprint §3.1, §3.4). Plotting the commanded
value would draw a curve the device never saw. ``vds_set_v`` appears here only
in the diagnostic overlay, where the *difference* between the two is the
quantity of interest.

Live plotting is driven by the ``on_row`` callback of
:func:`ct_host.protocol.run_sweep`, so points appear at the rate the
instrument produces them. It works against the simulator too, which streams
line by line for exactly this reason.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .csvio import Row, Sweep
from .dataset import family_of, vds_delta_report

__all__ = ["LivePlot", "plot_family", "plot_vds_delta"]


@dataclass
class LivePlot:
    """Accumulates rows and redraws the family as they arrive.

    Redraws are rate-limited: a 1600-point sweep completes in about a second
    and a half on the wire, and redrawing per row would make the plot, not the
    instrument, the bottleneck.
    """

    title: str = "I-V family"
    redraw_interval_s: float = 0.2
    i_limit_ma: float | None = None
    show: bool = True

    _series: "OrderedDict[float, tuple[list[float], list[float]]]" = field(
        default_factory=OrderedDict, init=False, repr=False)
    _flagged: tuple[list[float], list[float]] = field(
        default_factory=lambda: ([], []), init=False, repr=False)
    _lines: dict[float, Any] = field(default_factory=dict, init=False,
                                     repr=False)
    _last_draw: float = field(default=0.0, init=False, repr=False)
    _fig: Any = field(default=None, init=False, repr=False)
    _ax: Any = field(default=None, init=False, repr=False)
    _flag_artist: Any = field(default=None, init=False, repr=False)
    n_rows: int = field(default=0, init=False)

    # -- lifecycle ---------------------------------------------------------

    def open(self) -> LivePlot:
        import matplotlib.pyplot as plt

        if self.show:
            plt.ion()
        self._fig, self._ax = plt.subplots(figsize=(7.5, 5.0))
        self._ax.set_xlabel("V_DS measured at the DUT  (V)")
        self._ax.set_ylabel("I_D  (mA)")
        self._ax.set_title(self.title)
        self._ax.grid(True, alpha=0.3)
        if self.i_limit_ma is not None:
            self._ax.axhline(self.i_limit_ma, linestyle="--", linewidth=1.0,
                             color="0.5")
            self._ax.text(0.01, self.i_limit_ma, " firmware i_limit",
                          va="bottom", ha="left", fontsize=8, color="0.4",
                          transform=self._ax.get_yaxis_transform())
        if self.show:
            self._fig.canvas.draw_idle()
            plt.show(block=False)
        return self

    def __enter__(self) -> LivePlot:
        return self.open()

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._fig is not None and self.show:
            import matplotlib.pyplot as plt
            plt.ioff()

    # -- callbacks ---------------------------------------------------------

    def on_meta(self, key: str, value: str) -> None:
        if key == "device" and self._ax is not None:
            self._ax.set_title(f"{self.title} — {value}")
        elif key == "i_limit_ma" and self.i_limit_ma is None:
            try:
                self.i_limit_ma = float(value)
            except ValueError:
                pass

    def on_row(self, row: Row) -> None:
        """Feed one row. Safe to pass straight to ``run_sweep(on_row=...)``."""
        self.n_rows += 1
        if self._ax is None:
            self.open()

        if not row.valid:
            self._flagged[0].append(row.v_dut)
            self._flagged[1].append(row.i_ma)
        else:
            xs, ys = self._series.setdefault(row.vgs_set_v, ([], []))
            xs.append(row.v_dut)
            ys.append(row.i_ma)

        now = time.monotonic()
        if now - self._last_draw >= self.redraw_interval_s:
            self._last_draw = now
            self.refresh()

    def refresh(self) -> None:
        if self._ax is None:
            return
        for vgs, (xs, ys) in self._series.items():
            line = self._lines.get(vgs)
            if line is None:
                (line,) = self._ax.plot(xs, ys, marker="", linewidth=1.4,
                                        label=f"V_GS = {vgs:.3f} V")
                self._lines[vgs] = line
                self._ax.legend(fontsize=8, loc="upper left")
            else:
                line.set_data(xs, ys)

        if self._flagged[0]:
            if self._flag_artist is None:
                (self._flag_artist,) = self._ax.plot(
                    *self._flagged, linestyle="none", marker="x",
                    markersize=9, color="crimson", label="flagged (excluded)")
                self._ax.legend(fontsize=8, loc="upper left")
            else:
                self._flag_artist.set_data(*self._flagged)

        self._ax.relim()
        self._ax.autoscale_view()
        if self.show:
            self._fig.canvas.draw_idle()
            self._fig.canvas.flush_events()

    def finish(self, sweep: Sweep | None = None) -> None:
        self.refresh()
        if sweep is not None and self._ax is not None:
            if sweep.end_reason and sweep.end_reason != "ok":
                self._ax.set_title(
                    f"{self._ax.get_title()}   [ended: {sweep.end_reason}]")

    def save(self, path: str | Path, dpi: int = 150) -> Path:
        self.refresh()
        path = Path(path)
        self._fig.savefig(path, dpi=dpi, bbox_inches="tight")
        return path

    # -- introspection, for tests ------------------------------------------

    @property
    def figure(self) -> Any:
        return self._fig

    @property
    def axes(self) -> Any:
        return self._ax

    @property
    def series(self) -> "OrderedDict[float, tuple[list[float], list[float]]]":
        return self._series

    @property
    def flagged(self) -> tuple[list[float], list[float]]:
        return self._flagged


def plot_family(sweep: Sweep, *, ax: Any = None, show_flagged: bool = True,
                title: str | None = None) -> Any:
    """Draw a finished sweep. Returns the axes."""
    import matplotlib.pyplot as plt

    if ax is None:
        _, ax = plt.subplots(figsize=(7.5, 5.0))

    family = family_of(sweep)
    for curve in family:
        ax.plot(curve.v, curve.i_ma, linewidth=1.4,
                label=f"V_GS = {curve.vgs:.3f} V")

    if show_flagged and sweep.flagged_rows:
        ax.plot([r.v_dut for r in sweep.flagged_rows],
                [r.i_ma for r in sweep.flagged_rows],
                linestyle="none", marker="x", markersize=9, color="crimson",
                label="flagged (excluded from fits)")

    label = title or sweep.meta.device
    if sweep.meta.is_simulated:
        label += "   [SIMULATED]"
    ax.set_xlabel("V_DS measured at the DUT  (V)")
    ax.set_ylabel("I_D  (mA)")
    ax.set_title(label)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8, loc="upper left")
    return ax


def plot_vds_delta(sweep: Sweep, *, ax: Any = None,
                   r_iso_ohm: float = 22.0) -> Any:
    """The commanded-minus-measured diagnostic against the expected line.

    This is the one plot where ``vds_set_v`` appears, and only as part of the
    difference. A healthy instrument puts every point on the I x 23 ohm line.
    """
    import matplotlib.pyplot as plt
    import numpy as np

    if ax is None:
        _, ax = plt.subplots(figsize=(7.0, 4.5))

    rows = [r for r in sweep.valid_rows if r.i_ma > 0.5]
    i_ma = np.array([r.i_ma for r in rows])
    delta = np.array([r.vds_set_v - r.v_dut for r in rows])

    report = vds_delta_report(sweep, r_iso_ohm=r_iso_ohm)
    ax.plot(i_ma, delta, linestyle="none", marker=".", markersize=4,
            label="measured delta")
    if i_ma.size:
        grid = np.linspace(0.0, float(i_ma.max()), 50)
        ax.plot(grid, grid / 1000.0 * report.expected_r_ohm, linewidth=1.2,
                color="0.4", linestyle="--",
                label=f"expected: I x {report.expected_r_ohm:.0f} Ω")

    ax.set_xlabel("I_D  (mA)")
    ax.set_ylabel("vds_set_v − vds_meas_v  (V)")
    ax.set_title(f"Series-drop diagnostic — {report.verdict}")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8, loc="upper left")
    return ax
