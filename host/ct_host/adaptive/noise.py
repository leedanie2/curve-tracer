"""Per-point measurement noise, for weighting points in the GP.

**Oversampling reduces quantisation error only when there is dither.** With
no noise ahead of the ADC, all 64 conversions of a point round to the same
code, the mean is off by up to half an LSB, and averaging does nothing:
the error stays at LSB/sqrt(12). ct_sim's default ``--noise 0`` is exactly
that case. Assuming LSB/sqrt(12 * 64) there would claim eight times the
precision that exists.

For Gaussian noise of rms ``s`` LSB ahead of the quantiser, the part of the
quantisation error that does *not* average out is its signal-dependent mean,
whose variance is a fraction ``rho(s)`` of LSB^2/12 (Widrow & Kollar,
*Quantization Noise*, 2008):

    rho(s) = sum_k 6/(pi^2 k^2) * exp(-4 pi^2 k^2 s^2)        rho(0) = 1

so the oversampled mean of N conversions has error variance

    var = s^2/N + (1/12) * (rho + (1 - rho)/N)          [LSB^2]

which runs from 1/12 (no dither, no benefit from N) to (s^2 + 1/12)/N
(plenty of dither). The non-averaging part is a deterministic sawtooth in the
true value; across points at different currents it behaves as independent
noise, and it is modelled that way.

The voltage channel's error reaches the current through the curve's slope --
in triode at the top gate step a 0.93 mV voltage error is worth ~74 uA, far
more than the current channel's own ~12 uA -- so the effective variance on a
point is ``var_I + (dI/dV)^2 var_V`` (first-order noisy-input GP, McHutchon &
Rasmussen 2011).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

__all__ = ["rho", "mean_error_var_lsb2", "NoiseModel"]


def rho(s: float) -> float:
    """Fraction of quantisation variance that oversampling cannot remove."""
    s = abs(float(s))
    if s == 0.0:
        return 1.0
    k_max = max(50, int(3.0 / s) + 1)
    k = np.arange(1, k_max + 1, dtype=float)
    return float(np.sum(6.0 / (math.pi ** 2 * k ** 2)
                        * np.exp(-4.0 * math.pi ** 2 * k ** 2 * s * s)))


def mean_error_var_lsb2(sigma_lsb: float, n: int) -> float:
    """Variance of an oversampled mean's error, in LSB^2."""
    r = rho(sigma_lsb)
    return sigma_lsb ** 2 / n + (r + (1.0 - r) / n) / 12.0


@dataclass(frozen=True)
class NoiseModel:
    """Noise per channel, as rms LSB ahead of the quantiser.

    Before the bench this is the simulator's setting. On the bench it is the
    blueprint §7 noise-floor test (1000 samples at a fixed bias), which this
    model makes load-bearing.
    """

    sigma_i_lsb: float = 0.0
    sigma_v_lsb: float = 0.0
    oversample_n: int = 64
    i_lsb_ma: float = 3.3 / 4095 / 20.0 * 1000.0
    v_lsb_v: float = 3.3 / 4095 * 4.0

    @property
    def var_i_ma2(self) -> float:
        return mean_error_var_lsb2(self.sigma_i_lsb, self.oversample_n) * self.i_lsb_ma ** 2

    @property
    def var_v_v2(self) -> float:
        return mean_error_var_lsb2(self.sigma_v_lsb, self.oversample_n) * self.v_lsb_v ** 2

    def current_var(self, slope_ma_per_v=0.0) -> np.ndarray:
        """Effective variance of a current reading, mA^2, given dI/dV."""
        slope = np.asarray(slope_ma_per_v, dtype=float)
        return self.var_i_ma2 + slope ** 2 * self.var_v_v2

    def voltage_var_given_log_current(self, i_ma, dv_dlni=0.0) -> np.ndarray:
        """Effective variance of V regressed on ln(I) (the diode's form), V^2.

        The current error enters through ln I: sigma_u = sigma_I / I.
        """
        i = np.maximum(np.asarray(i_ma, dtype=float), 1e-12)
        sigma_u2 = self.var_i_ma2 / i ** 2
        return self.var_v_v2 + np.asarray(dv_dlni) ** 2 * sigma_u2
