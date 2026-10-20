"""Synthetic devices for the offline evaluation.

``ct_sim`` is the square-law model the extractors assume, so a sparse fit
against it recovers the parameters almost exactly and proves nothing about a
real part. The devices here depart from that model in ways it cannot express:
mobility degradation, series resistance inside the Kelvin sense, self-heating,
and a smooth inversion characteristic in place of the square law's corner.
Two are controls: ``sim-sq`` and ``sim-diode`` reproduce ``ct_sim``'s models,
and ``tests/test_adaptive_oracle.py`` holds them to it count for count.

**Every number below is an assumption, not a measurement.** The 2N7000-like
defaults are the host suite's ``KNOWN_MOSFET``; the thermal networks split a
datasheet-derived junction-to-ambient resistance across four poles whose time
constants are guesses. They are swept in the evaluation for exactly that
reason, and the bench (blueprint §7) is what replaces them.

All names start ``sim-`` so nothing produced from them can be mistaken for a
bench measurement (``Metadata.is_simulated``).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np

__all__ = ["Thermal", "Mosfet", "Diode", "Device", "TO92_2N7000", "DO35_1N4148",
           "mosfet_devices", "diode_devices", "device_by_name", "VT_300K"]

#: kT/q at 300 K, the constant ct_sim uses.
VT_300K = 0.02585

#: Ambient and parameter reference temperature, K.
T_REF_K = 300.0


@dataclass(frozen=True)
class Thermal:
    """A Foster network: junction rise = sum of first-order poles.

    Driven by the DUT's own dissipation, ``I * V_DS``, held piecewise
    constant between DAC writes. ``r_k_per_w`` sums to the junction-to-ambient
    resistance.
    """

    r_k_per_w: tuple[float, ...]
    tau_s: tuple[float, ...]

    def scaled(self, factor: float) -> Thermal:
        return Thermal(tuple(r * factor for r in self.r_k_per_w), self.tau_s)

    @property
    def r_total(self) -> float:
        return float(sum(self.r_k_per_w))

    def step(self, state: np.ndarray, power_w: float, dt_s: float) -> np.ndarray:
        """Exact update of every pole over ``dt_s`` at constant power."""
        r = np.asarray(self.r_k_per_w)
        tau = np.asarray(self.tau_s)
        target = r * power_w
        return target + (state - target) * np.exp(-dt_s / tau)


#: 2N7000 in TO-92. 312.5 K/W is (150 - 25) C / 400 mW, the datasheet's
#: dissipation rating -- to be confirmed against the datasheet itself. The
#: split across poles is ASSUMED.
TO92_2N7000 = Thermal(r_k_per_w=(15.0, 45.0, 95.0, 157.5),
                      tau_s=(1e-3, 30e-3, 1.0, 30.0))

#: 1N4148 in DO-35, ~350 K/W junction to ambient. ASSUMED, split and all.
DO35_1N4148 = Thermal(r_k_per_w=(17.5, 52.5, 105.0, 175.0),
                      tau_s=(0.5e-3, 20e-3, 0.5, 20.0))


def _softplus(x):
    return np.logaddexp(0.0, x)


@dataclass(frozen=True)
class Mosfet:
    """An N-MOSFET. With every departure at its default this is ct_sim's model.

    ``k`` follows ct_sim's ``--k``: the SPICE ``KP*W/L``, so the extractor's
    ``beta`` is ``k/2``.
    """

    name: str = "sim-sq"
    vth: float = 2.15
    k: float = 0.055
    lam: float = 0.012
    n_sub: float = 1.5          # ct_sim's subthreshold ideality
    #: mobility degradation, beta / (1 + theta * V_ov)
    theta: float = 0.0
    #: source and drain resistance INSIDE the Kelvin sense, so the instrument
    #: measures across them; distinct from R_iso, which it does not
    r_s: float = 0.0
    r_d: float = 0.0
    #: slope factor of a smooth inversion characteristic: the square law with
    #: V_ov replaced by 2 n V_T ln(1 + exp(V_ov / (2 n V_T))). That equals V_ov
    #: in strong inversion and decays exponentially (slope n) below threshold,
    #: so the departure is confined to ~0.2 V either side of V_th -- a
    #: subthreshold tail, not a different triode region. None keeps ct_sim's
    #: piecewise square law with its own subthreshold branch.
    inversion_n: float | None = None
    thermal: Thermal | None = None
    vth_tc_v_per_k: float = 3e-3
    mobility_exp: float = -1.5
    description: str = "square law + lambda (ct_sim's model)"
    kind: str = field(default="mosfet", init=False)

    @property
    def internal_r(self) -> float:
        return self.r_s + self.r_d

    def truth(self) -> dict[str, float]:
        """The generative parameters, in the extractor's names."""
        return {"vth": self.vth, "beta": self.k / 2.0, "kp_wl": self.k,
                "lambda": self.lam}

    def channel_current_a(self, vgs, vds, t_k=T_REF_K):
        """Current at INTERNAL terminal voltages and junction temperature."""
        vgs = np.asarray(vgs, dtype=float)
        vds = np.asarray(vds, dtype=float)
        t_k = np.asarray(t_k, dtype=float)

        vth = self.vth - self.vth_tc_v_per_k * (t_k - T_REF_K)
        k = self.k * (t_k / T_REF_K) ** self.mobility_exp
        vov = vgs - vth
        k = k / (1.0 + self.theta * np.maximum(vov, 0.0))
        vds_pos = np.maximum(vds, 0.0)

        if self.inversion_n is not None:
            two_nvt = 2.0 * self.inversion_n * VT_300K * t_k / T_REF_K
            veff = two_nvt * _softplus(vov / two_nvt)
            tri = k * (veff * vds_pos - 0.5 * vds_pos * vds_pos)
            sat = 0.5 * k * veff * veff
            i = np.where(vds_pos < veff, tri, sat) * (1.0 + self.lam * vds_pos)
            return np.where(vds > 0.0, i, 0.0)

        # ct_sim's model, branch for branch (firmware/sim/ct_sim_device.c).
        sub = (self.k * VT_300K * VT_300K
               * np.exp(np.minimum(vov, 0.0) / (self.n_sub * VT_300K))
               * (1.0 - np.exp(-vds_pos / VT_300K)))
        tri = k * (vov * vds_pos - 0.5 * vds_pos * vds_pos) * (1.0 + self.lam * vds_pos)
        sat = 0.5 * k * vov * vov * (1.0 + self.lam * vds_pos)
        i = np.where(vov <= 0.0, sub, np.where(vds_pos < vov, tri, sat))
        return np.where(vds > 0.0, i, 0.0)

    def current_a(self, vgs, v_term, j, t_k=T_REF_K):
        """Current given the terminal voltage and a trial current ``j``.

        ``j`` sets the drops across the internal resistances; the solver finds
        the ``j`` that reproduces itself.
        """
        if self.internal_r == 0.0:
            return self.channel_current_a(vgs, v_term, t_k)
        return self.channel_current_a(np.asarray(vgs) - j * self.r_s,
                                      np.asarray(v_term) - j * self.internal_r,
                                      t_k)


@dataclass(frozen=True)
class Diode:
    """A junction diode. With ``i_s2 = 0`` and no thermal network, ct_sim's."""

    name: str = "sim-diode"
    i_s: float = 2.5e-9
    n: float = 1.75
    r_s: float = 0.6
    #: second, recombination-like component sharing the junction voltage
    i_s2: float = 0.0
    n2: float = 2.0
    thermal: Thermal | None = None
    xti: float = 3.0
    eg_ev: float = 1.11
    description: str = "Shockley + R_s (ct_sim's model)"
    kind: str = field(default="diode", init=False)

    def truth(self) -> dict[str, float]:
        return {"n": self.n, "i_s": self.i_s, "rs": self.r_s}

    def _is_at(self, i_s, n, t_k):
        vt = VT_300K * t_k / T_REF_K
        ratio = t_k / T_REF_K
        return i_s * ratio ** (self.xti / n) * np.exp((ratio - 1.0) * self.eg_ev / (n * vt))

    def current_a(self, vgs, v_term, j, t_k=T_REF_K):
        del vgs
        v_term = np.asarray(v_term, dtype=float)
        t_k = np.asarray(t_k, dtype=float)
        # ct_sim clamps the terminal voltage at 2 V before expf can overflow.
        v = np.minimum(v_term, 2.0)
        vj = v - j * self.r_s
        if self.thermal is None:
            vt = VT_300K
            i_s, i_s2 = self.i_s, self.i_s2
        else:
            vt = VT_300K * t_k / T_REF_K
            i_s = self._is_at(self.i_s, self.n, t_k)
            i_s2 = self._is_at(self.i_s2, self.n2, t_k) if self.i_s2 else 0.0
        i = i_s * (np.exp(vj / (self.n * vt)) - 1.0)
        if self.i_s2:
            i = i + i_s2 * (np.exp(vj / (self.n2 * vt)) - 1.0)
        return np.where(v_term > 0.0, i, 0.0)

    @property
    def internal_r(self) -> float:
        return self.r_s


Device = Mosfet | Diode


def mosfet_devices() -> dict[str, Mosfet]:
    """The MOSFET set of blueprint-plan §4.2, at default severity."""
    sq = Mosfet()
    return {
        "sim-sq": sq,
        "sim-theta": replace(sq, name="sim-theta", theta=0.2,
                             description="mobility degradation, theta = 0.2 /V"),
        "sim-rsd": replace(sq, name="sim-rsd", r_s=1.0, r_d=1.0,
                           description="internal R_S = R_D = 1 ohm"),
        "sim-heat": replace(sq, name="sim-heat", thermal=TO92_2N7000,
                            description="self-heating, TO-92 312.5 K/W (assumed split)"),
        "sim-tail": replace(sq, name="sim-tail", inversion_n=1.5,
                            description="smooth inversion (subthreshold tail), n = 1.5"),
        "sim-real": replace(sq, name="sim-real", theta=0.2, r_s=1.0, r_d=1.0,
                            thermal=TO92_2N7000, inversion_n=1.5,
                            description="theta + R_SD + heating + smooth inversion"),
    }


def diode_devices() -> dict[str, Diode]:
    d = Diode()
    return {
        "sim-diode": d,
        "sim-diode2": replace(d, name="sim-diode2", i_s2=2e-8,
                              description="added n = 2 recombination component"),
        "sim-diode-heat": replace(d, name="sim-diode-heat", thermal=DO35_1N4148,
                                  description="self-heating, DO-35 350 K/W (assumed)"),
    }


def device_by_name(name: str) -> Device:
    table: dict[str, Device] = {**mosfet_devices(), **diode_devices()}
    try:
        return table[name]
    except KeyError:
        raise KeyError(f"unknown synthetic device {name!r}; "
                       f"known: {', '.join(table)}") from None
