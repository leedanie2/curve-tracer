"""The instrument's signal chain, in Python, for the synthetic oracle.

This mirrors ``firmware/sim/ct_sim_device.c`` and the firmware's own unit
conversions: the commanded DAC code becomes a feedback-node voltage, the DUT
draws current through ``R_iso``, the PTC and the shunt, the Kelvin divider
draws ``V/400k`` beside it, and both ADC channels quantise what is left, 64
times per point. ``tests/test_adaptive_oracle.py`` holds it to ``ct_sim``
count for count, so it cannot drift into a second, different model of the
instrument.

Two departures from ct_sim, both deliberate. The operating point is solved
for the DUT current rather than the DUT voltage, because the same single
root then covers resistance inside the device (sim-rsd) without a nested
solve. And noise is Gaussian, not ct_sim's uniform, because a bench noise
floor is closer to Gaussian; it is off for the bit-exact comparison.

Rows and headers are rendered with the firmware's formats so that byte
counts, and therefore serial time, are the instrument's.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..csvio import EXPECTED_COLUMNS
from .devices import Device

__all__ = ["FrontEnd", "render_row", "render_header", "fmt_f",
           "POINTS_EXTRA_COLUMNS"]

#: Columns the proposed points mode appends (plan Q4, option S1). Used only to
#: count bytes in phase 1; nothing parses them yet.
POINTS_EXTRA_COLUMNS = ("batch", "t_us")


@dataclass(frozen=True)
class FrontEnd:
    """Range-1 constants, as ``firmware/core/ct_config.h`` has them."""

    r_iso: float = 22.0
    shunt: float = 1.0
    r_ptc: float = 0.0          # ct_sim has none; the board's is 1.6-15 ohm
    r_div: float = 400000.0
    gain_sweep: float = 3.32
    gain_gate: float = 3.32
    vref: float = 3.3
    dac_fs: int = 4095
    adc_fs: int = 4095
    diffamp_gain: float = 20.0
    vdiv: float = 4.0
    oversample_n: int = 64
    settle_us: int = 50

    @property
    def r_series(self) -> float:
        return self.r_iso + self.r_ptc + self.shunt

    @property
    def i_lsb_ma(self) -> float:
        return self.vref / self.adc_fs / (self.diffamp_gain * self.shunt) * 1000.0

    @property
    def v_lsb_v(self) -> float:
        return self.vref / self.adc_fs * self.vdiv

    # -- DAC, in float32 as the firmware computes it ------------------------

    def volts_to_code(self, volts: float, gain: float | None = None) -> int:
        """``volts_to_code`` in ct_params.c: round to nearest, clamp."""
        g = np.float32(self.gain_sweep if gain is None else gain)
        v = np.float32(volts)
        if not v > np.float32(0.0):
            return 0
        code = (v / g / np.float32(self.vref)) * np.float32(self.dac_fs)
        if code >= np.float32(self.dac_fs):
            return self.dac_fs
        return int(code + np.float32(0.5))

    def gate_code(self, volts: float) -> int:
        return self.volts_to_code(volts, self.gain_gate)

    def code_to_volts(self, code, gain: float | None = None):
        g = np.float32(self.gain_sweep if gain is None else gain)
        c = np.asarray(code, dtype=np.float32)
        return ((c / np.float32(self.dac_fs)) * np.float32(self.vref) * g).astype(float)

    def gate_volts(self, code):
        return self.code_to_volts(code, self.gain_gate)

    def ramp_codes(self, n: int, vds_max: float) -> list[int]:
        """The SWEEP ramp: n points spanning 0..vds_max inclusive (ct_sweep.c)."""
        span = np.float32(n - 1 if n > 1 else 1)
        vmax = np.float32(vds_max)
        return [self.volts_to_code(float(vmax * (np.float32(i) / span)))
                for i in range(n)]

    # -- operating point ----------------------------------------------------

    def solve(self, dev: Device, vgs, v_node, t_k=300.0, iterations: int = 64):
        """DUT voltage and current for a node voltage, vectorised.

        Solves for the DUT current ``j`` with

            v_dut(j) = (v_node - j * R_ser) / (1 + R_ser / R_div)

        (the divider's current also flows through the series path), and
        ``j = I_dev(v_dut(j), j)``. The right side falls monotonically as ``j``
        rises, so bisection on ``[0, v_node / R_ser]`` cannot miss the root.
        """
        vgs = np.atleast_1d(np.asarray(vgs, dtype=float))
        v_node = np.atleast_1d(np.asarray(v_node, dtype=float))
        t_k = np.broadcast_to(np.asarray(t_k, dtype=float), v_node.shape)
        r = self.r_series
        shunt_div = 1.0 + r / self.r_div

        lo = np.zeros_like(v_node)
        hi = np.maximum(v_node, 0.0) / r
        for _ in range(iterations):
            mid = 0.5 * (lo + hi)
            v = (v_node - mid * r) / shunt_div
            excess = dev.current_a(vgs, v, mid, t_k) - mid
            lo = np.where(excess > 0.0, mid, lo)
            hi = np.where(excess > 0.0, hi, mid)
        j = 0.5 * (lo + hi)
        v = np.where(v_node > 0.0, (v_node - j * r) / shunt_div, 0.0)
        j = np.where(v_node > 0.0, j, 0.0)
        return v, j

    def terminal_current(self, dev: Device, vgs, v_dut, t_k=300.0,
                         iterations: int = 64):
        """DUT current at a fixed terminal voltage, with no external series R.

        Needed for "truth" curves: a device with internal resistance still
        needs a self-consistent solve at its own terminals.
        """
        vgs = np.atleast_1d(np.asarray(vgs, dtype=float))
        v_dut = np.atleast_1d(np.asarray(v_dut, dtype=float))
        t_k = np.broadcast_to(np.asarray(t_k, dtype=float), v_dut.shape)
        if dev.internal_r == 0.0:
            return np.asarray(dev.current_a(vgs, v_dut, 0.0, t_k), dtype=float)
        lo = np.zeros_like(v_dut)
        hi = np.maximum(np.asarray(dev.current_a(vgs, v_dut, 0.0, t_k)), 0.0) + 1e-12
        for _ in range(iterations):
            mid = 0.5 * (lo + hi)
            excess = dev.current_a(vgs, v_dut, mid, t_k) - mid
            lo = np.where(excess > 0.0, mid, lo)
            hi = np.where(excess > 0.0, hi, mid)
        return 0.5 * (lo + hi)

    # -- ADC ------------------------------------------------------------------

    def counts(self, v_dut, j_a):
        """Ideal (unquantised) ADC counts for both channels."""
        v_dut = np.asarray(v_dut, dtype=float)
        i_shunt = np.asarray(j_a, dtype=float) + v_dut / self.r_div
        i_counts = i_shunt * self.shunt * self.diffamp_gain / self.vref * self.adc_fs
        v_counts = v_dut / self.vdiv / self.vref * self.adc_fs
        return i_counts, v_counts

    def accumulate(self, counts, sigma_counts: float,
                   rng: np.random.Generator | None) -> np.ndarray:
        """Sum of ``oversample_n`` quantised conversions, per point.

        As ct_sim: add the noise, clamp to the ADC's range, round half up.
        """
        counts = np.atleast_1d(np.asarray(counts, dtype=float))
        n = self.oversample_n
        if sigma_counts > 0.0:
            if rng is None:
                raise ValueError("noise needs a random generator")
            samples = counts[:, None] + rng.normal(0.0, sigma_counts,
                                                   size=(counts.size, n))
        else:
            samples = np.repeat(counts[:, None], n, axis=1)
        codes = np.floor(np.clip(samples, 0.0, float(self.adc_fs)) + 0.5)
        return codes.sum(axis=1).astype(np.int64)

    def firmware_values(self, i_acc, v_acc):
        """``vds_meas_v`` and ``i_meas_ma`` as the firmware reports them."""
        n = self.oversample_n
        v = np.asarray(v_acc, dtype=float) / n / self.adc_fs * self.vref * self.vdiv
        i_shunt = (np.asarray(i_acc, dtype=float) / n / self.adc_fs * self.vref
                   / (self.diffamp_gain * self.shunt) * 1000.0)
        return v, i_shunt - v / self.r_div * 1000.0


def fmt_f(value: float, decimals: int) -> str:
    """``ct_fmt_f``: fixed decimals, and no sign on a value that rounds to 0."""
    text = f"{value:.{decimals}f}"
    if text.startswith("-") and float(text) == 0.0:
        text = text[1:]
    return text


def render_row(point: int, vgs_set: float, vds_set: float, vds_meas: float,
               i_ma: float, i_acc: int, v_acc: int, flags: str = "",
               extra: tuple = ()) -> str:
    """One CSV row, as ``ct_csv_format_row`` writes it (no CRLF)."""
    fields = [str(point), fmt_f(vgs_set, 3), fmt_f(vds_set, 3),
              fmt_f(vds_meas, 3), fmt_f(i_ma, 4), str(int(i_acc)),
              str(int(v_acc)), "1", flags]
    fields.extend(str(x) for x in extra)
    return ",".join(fields)


def render_header(fe: FrontEnd, *, device: str, mode: str, n: int,
                  i_limit_ma: float, vds_max: float, vgs_list: list[float],
                  columns: tuple[str, ...] = EXPECTED_COLUMNS,
                  schema: int = 2) -> list[str]:
    """The metadata block, as ``ct_csv_write_header_mode`` writes it."""
    cal_ptc = "unset"   # what the board reports until its PTC is measured
    lines = [
        "# curve-tracer csv",
        f"# schema: {schema}",
        "# fw: 0.1.0",
        "# board: nucleo-f303re",
        f"# device: {device}",
        "# date: unset",
        "# date_src: none",
        "# range: 1",
        f"# mode: {mode}",
        "# temp_c: 25.4",
        "# temp_src: mcu_die",
        f"# settle_us: {fe.settle_us}",
        f"# n: {n}",
        f"# oversample_n: {fe.oversample_n}",
        f"# i_limit_ma: {fmt_f(i_limit_ma, 2)}",
        f"# vds_max: {fmt_f(vds_max, 3)}",
        "# vgs_list: " + ",".join(fmt_f(v, 3) for v in vgs_list),
        f"# cal_gain_sweep: {fmt_f(fe.gain_sweep, 3)}",
        f"# cal_gain_gate: {fmt_f(fe.gain_gate, 3)}",
        f"# cal_shunt_ohm: {fmt_f(fe.shunt, 3)}",
        f"# cal_diffamp_gain: {fmt_f(fe.diffamp_gain, 2)}",
        f"# cal_vdiv: {fmt_f(fe.vdiv, 3)}",
        f"# cal_rdiv_ohm: {fmt_f(fe.r_div, 0)}",
        f"# cal_r_iso_ohm: {fmt_f(fe.r_iso, 3)}",
        f"# cal_r_ptc_ohm: {cal_ptc}",
        f"# cal_vref: {fmt_f(fe.vref, 3)}",
        f"# cal_adc_full_scale: {fe.adc_fs}",
        f"# cal_dac_full_scale: {fe.dac_fs}",
        "# columns: " + ",".join(columns),
        ",".join(columns),
    ]
    return lines
