"""SPICE ``.model`` cards from extracted parameters.

The card is the handoff to LTspice for the closed-loop validation in blueprint
§6: measure a device, extract it, simulate a circuit with *your* model, build
it, compare. So the card carries its own provenance in comments -- which
instrument, which capture, which fit range, and whether the data came from
hardware or the simulator. A model card that turns up in a schematic six
months later should say where it came from.

``KP`` is emitted from ``kp_wl``, the SPICE convention, never from ``beta``.
That factor of two is the whole reason the extractor reports both.
"""

from __future__ import annotations

import datetime as _dt

from .extract.diode import DiodeParams
from .extract.mosfet import MosfetParams

__all__ = ["mosfet_model_card", "diode_model_card"]


def _header(name: str, params, source: str | None, extra: list[str]) -> list[str]:
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    lines = [
        f"* {name} -- extracted from a curve-tracer measurement",
        f"* generated  : {stamp} by ct_host",
        f"* device     : {params.device}",
    ]
    if source:
        lines.append(f"* capture    : {source}")
    if params.simulated:
        lines += [
            "*",
            "* WARNING: this model was extracted from SIMULATED data",
            "*          (firmware/sim), not from a bench measurement.",
            "*          It describes the test fixture's model, not a part.",
        ]
    lines.append("*")
    lines += extra
    lines.append("*")
    return lines


def mosfet_model_card(params: MosfetParams, *, name: str = "EXTRACTED",
                      source: str | None = None,
                      level: int = 1) -> str:
    """An NMOS ``.model`` card.

    Only the parameters that were actually measured are emitted. Nothing is
    filled in from a datasheet or a plausible default: a card that silently
    mixes measured and invented values cannot be used to validate anything,
    which is the one job it has.
    """
    detail = [
        f"* V_th       : {params.vth}",
        f"* KP*(W/L)   : {params.kp_wl}   (= 2*beta; beta = {params.beta})",
        f"* de-embedded: beta_raw {params.beta_raw.value:.6g} A/V^2 divided by "
        f"(1 + lambda*{params.vds_slice:.3f}) = {params.deembed_factor:.4f}",
    ]
    if params.lambda_ is not None:
        detail.append(f"* lambda     : {params.lambda_}   "
                      f"(V_A = {params.va})")
    if params.rds_on is not None:
        detail.append(f"* R_DS(on)   : {params.rds_on}  (not a model "
                      f"parameter; for reference)")
    detail.append(f"* V_DS slice : {params.vds_slice:.4f} V (measured, "
                  f"Kelvin-sensed)")
    detail.append(f"* fit range  : {params.vth_fit.range.rule}")
    if params.sensitivity is not None and params.sensitivity.spread is not None:
        detail.append(
            f"* V_th spread over {params.sensitivity.n_choices} fit-range "
            f"choices: {params.sensitivity.spread * 1000:.2f} mV "
            f"(fit stderr "
            f"{(params.vth.stderr or 0) * 1000:.2f} mV) -- the larger of "
            f"these is the honest uncertainty"
        )
    if params.subthreshold.available:
        detail.append(f"* subthresh. : {params.subthreshold.mv_per_decade}")
    else:
        detail.append(f"* subthresh. : not measured -- "
                      f"{params.subthreshold.reason.splitlines()[0]}")

    body = [f".model {name} NMOS (",
            f"+   LEVEL = {level}",
            f"+   VTO   = {params.vth.value:.6g}",
            f"+   KP    = {params.kp_wl.value:.6g}"]
    if params.lambda_ is not None:
        body.append(f"+   LAMBDA = {params.lambda_.value:.6g}")
    body.append("+ )")

    return "\n".join(_header("NMOS", params, source, detail) + body) + "\n"


def diode_model_card(params: DiodeParams, *, name: str = "EXTRACTED",
                     source: str | None = None) -> str:
    """A diode ``.model`` card."""
    detail = [
        f"* n          : {params.n}",
        f"* I_S        : {params.i_s}",
    ]
    if params.rs is not None:
        detail.append(f"* R_s        : {params.rs}")
    detail.append(f"* fit range  : {params.fit.range.rule}")

    body = [f".model {name} D (",
            f"+   IS = {params.i_s.value:.6g}",
            f"+   N  = {params.n.value:.6g}"]
    if params.rs is not None:
        body.append(f"+   RS = {params.rs.value:.6g}")
    body.append("+ )")

    return "\n".join(_header("Diode", params, source, detail) + body) + "\n"
