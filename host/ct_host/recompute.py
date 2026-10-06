"""Re-deriving current and voltage from the raw accumulators.

``i_acc`` and ``v_acc`` are the *sum* of ``oversample_n`` raw ADC conversions.
They are in the CSV so an archived sweep survives a calibration change: if the
3.32 gain turns out to be 3.31 on the bench, or the shunt measures 0.998 ohm,
every capture ever taken can be re-derived rather than re-measured.

This module does that re-derivation, and then checks it against the firmware's
own converted columns. **The check is the point.** The two paths use the same
constants from two places -- ``firmware/core/ct_config.h`` and the ``cal_*``
header fields -- and if they ever disagree, one of them has drifted. A drift
of a few percent in a gain constant does not look wrong in a plot; it looks
like a slightly different transistor. Silently extracting parameters from it
would put a wrong number in a SPICE model and there would be nothing to
notice. So a mismatch raises.

Analysis runs on the recomputed values, not the reported ones.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .csvio import ContractError, Row, Sweep

__all__ = ["recompute", "assert_agreement", "AgreementReport",
           "CalibrationMismatch", "Calibration", "I_TOL_MA", "V_TOL_V"]


#: Agreement tolerances.
#:
#: The firmware prints current to 4 decimal places and voltage to 3, so
#: half-ULP rounding alone is 5e-5 mA and 5e-4 V. It also computes in float32
#: where this computes in float64, which on a 262080-count accumulator costs
#: another few 1e-5. These are set an order of magnitude above that floor:
#: loose enough that formatting and float width never trip them, tight enough
#: that the smallest plausible constant drift does. The tightest constant in
#: the chain is the shunt at 1.000 ohm; a 0.1% error in it shows as 0.05 mA at
#: 50 mA, fifty times this threshold.
I_TOL_MA = 0.002
V_TOL_V = 0.002


class CalibrationMismatch(ContractError):
    """Recomputed values disagree with the firmware's own conversion."""


@dataclass(frozen=True)
class Calibration:
    """The ``cal_*`` header block."""

    vref: float
    adc_full_scale: float
    diffamp_gain: float
    shunt_ohm: float
    vdiv: float
    oversample_n: int
    gain_sweep: float
    gain_gate: float
    #: Kelvin divider resistance, KELVIN_HI to KELVIN_LO (blueprint §3.4).
    #: ``None`` for schema-1 captures, whose firmware did not correct for it,
    #: so recomputing them must not either.
    rdiv_ohm: float | None = None
    #: Series resistance outside the loop, for the delta diagnostic only.
    #: ``r_ptc_ohm`` is ``None`` until it has been measured on the board.
    r_iso_ohm: float | None = None
    r_ptc_ohm: float | None = None

    @classmethod
    def from_sweep(cls, sweep: Sweep) -> Calibration:
        m = sweep.meta
        return cls(
            rdiv_ohm=m.float_or_none("cal_rdiv_ohm"),
            r_iso_ohm=m.float_or_none("cal_r_iso_ohm"),
            r_ptc_ohm=m.float_or_none("cal_r_ptc_ohm"),
            vref=m.cal("vref"),
            adc_full_scale=m.cal("adc_full_scale"),
            diffamp_gain=m.cal("diffamp_gain"),
            shunt_ohm=m.cal("shunt_ohm"),
            vdiv=m.cal("vdiv"),
            oversample_n=m.oversample_n,
            gain_sweep=m.cal("gain_sweep"),
            gain_gate=m.cal("gain_gate"),
        )

    @property
    def i_lsb_ma(self) -> float:
        """Current per ADC count, before oversampling. ~40.3 uA on range 1."""
        return (self.vref / self.adc_full_scale
                / (self.diffamp_gain * self.shunt_ohm) * 1000.0)

    @property
    def v_lsb_v(self) -> float:
        return self.vref / self.adc_full_scale * self.vdiv

    @property
    def i_full_scale_ma(self) -> float:
        return self.vref / (self.diffamp_gain * self.shunt_ohm) * 1000.0

    def shunt_current_ma(self, i_acc: int) -> float:
        """Everything through the shunt: the DUT *and* the Kelvin divider."""
        mean = i_acc / self.oversample_n
        volts = mean / self.adc_full_scale * self.vref
        return volts / (self.diffamp_gain * self.shunt_ohm) * 1000.0

    def divider_current_ma(self, v_dut: float) -> float:
        """The Kelvin divider's share of the shunt current at ``v_dut``."""
        return 0.0 if self.rdiv_ohm is None else v_dut / self.rdiv_ohm * 1000.0

    def current_ma(self, i_acc: int, v_acc: int) -> float:
        """DUT current: the shunt current less the divider's (§3.4).

        Needs ``v_acc`` because the divider draws ``V_DS / rdiv``. Mirrors
        ``ct_dut_current_ma`` in the firmware, so the agreement check below
        compares like with like.
        """
        return self.shunt_current_ma(i_acc) - self.divider_current_ma(self.voltage_v(v_acc))

    def voltage_v(self, v_acc: int) -> float:
        mean = v_acc / self.oversample_n
        return mean / self.adc_full_scale * self.vref * self.vdiv


def recompute(sweep: Sweep, *, check: bool = True,
              i_tol_ma: float = I_TOL_MA,
              v_tol_v: float = V_TOL_V) -> Sweep:
    """Return a copy of ``sweep`` with the recomputed columns filled in.

    With ``check`` (the default) the agreement assertion runs and raises on a
    mismatch. Turning it off is for diagnosing a known mismatch, not for
    working around one.
    """
    cal = Calibration.from_sweep(sweep)
    rows = [
        replace(row,
                i_recomp_ma=cal.current_ma(row.i_acc, row.v_acc),
                v_recomp_v=cal.voltage_v(row.v_acc))
        for row in sweep.rows
    ]
    out = replace(sweep, rows=rows, recomputed=True)
    if check:
        assert_agreement(out, i_tol_ma=i_tol_ma, v_tol_v=v_tol_v).raise_if_bad()
    return out


@dataclass(frozen=True)
class AgreementReport:
    """How closely the two conversion paths agree."""

    n_rows: int
    worst_i_row: Row | None
    worst_i_delta_ma: float
    worst_v_row: Row | None
    worst_v_delta_v: float
    i_tol_ma: float
    v_tol_v: float
    #: Ratio reported/recomputed over the rows with usable signal. A constant
    #: offset from 1.0 here is the signature of a drifted gain constant.
    i_ratio: float | None
    v_ratio: float | None

    @property
    def ok(self) -> bool:
        return (self.worst_i_delta_ma <= self.i_tol_ma
                and self.worst_v_delta_v <= self.v_tol_v)

    def raise_if_bad(self) -> AgreementReport:
        if not self.ok:
            raise CalibrationMismatch(self.describe())
        return self

    def explain(self) -> str:
        """Name the constant whose drift would produce the observed ratio."""
        notes: list[str] = []
        for label, ratio, constants in (
            ("current", self.i_ratio, "cal_diffamp_gain or cal_shunt_ohm"),
            ("voltage", self.v_ratio, "cal_vdiv"),
        ):
            if ratio is None or abs(ratio - 1.0) < 1e-6:
                continue
            notes.append(
                f"  {label}: firmware/recomputed = {ratio:.6f}\n"
                f"    consistent with {constants} differing by "
                f"{(ratio - 1.0) * 100:+.3f}% between ct_config.h and the "
                f"cal_* header"
            )
        if not notes:
            notes.append("  ratios are 1.000000; the disagreement is not a "
                         "constant scale factor -- suspect a per-row problem")
        return "\n".join(notes)

    def describe(self) -> str:
        head = (
            f"recomputed values disagree with the firmware's own conversion\n"
            f"  rows checked   : {self.n_rows}\n"
            f"  worst current  : {self.worst_i_delta_ma:.6f} mA "
            f"(tolerance {self.i_tol_ma})\n"
            f"  worst voltage  : {self.worst_v_delta_v:.6f} V "
            f"(tolerance {self.v_tol_v})\n"
        )
        if self.worst_i_row is not None:
            r = self.worst_i_row
            head += (
                f"  worst row      : point {r.point}, i_acc {r.i_acc}, "
                f"reported {r.i_meas_ma:.4f} mA, "
                f"recomputed {r.i_recomp_ma:.4f} mA\n"
            )
        return head + self.explain() + (
            "\n  a cal_* constant has drifted between firmware and host; "
            "fix it rather than loosening the tolerance"
        )


def assert_agreement(sweep: Sweep, *, i_tol_ma: float = I_TOL_MA,
                     v_tol_v: float = V_TOL_V) -> AgreementReport:
    """Compare the recomputed columns against the firmware's."""
    rows = [r for r in sweep.rows if r.i_recomp_ma is not None]
    if not rows:
        raise ValueError("sweep has not been recomputed")

    worst_i_row = worst_v_row = None
    worst_i = worst_v = 0.0
    for row in rows:
        di = abs(row.i_meas_ma - row.i_recomp_ma)
        if di >= worst_i:
            worst_i, worst_i_row = di, row
        dv = abs(row.vds_meas_v - row.v_recomp_v)
        if dv >= worst_v:
            worst_v, worst_v_row = dv, row

    return AgreementReport(
        n_rows=len(rows),
        worst_i_row=worst_i_row, worst_i_delta_ma=worst_i,
        worst_v_row=worst_v_row, worst_v_delta_v=worst_v,
        i_tol_ma=i_tol_ma, v_tol_v=v_tol_v,
        i_ratio=_ratio([(r.i_meas_ma, r.i_recomp_ma) for r in rows]),
        v_ratio=_ratio([(r.vds_meas_v, r.v_recomp_v) for r in rows]),
    )


def _ratio(pairs: list[tuple[float, float]]) -> float | None:
    """Mean reported/recomputed over rows with enough signal to be meaningful.

    Near zero the ratio is dominated by quantisation, so rows below 1% of the
    observed span are skipped rather than allowed to swamp the average.
    """
    span = max((abs(b) for _, b in pairs), default=0.0)
    if span <= 0.0:
        return None
    usable = [(a, b) for a, b in pairs if abs(b) > 0.01 * span]
    if not usable:
        return None
    return sum(a / b for a, b in usable) / len(usable)
