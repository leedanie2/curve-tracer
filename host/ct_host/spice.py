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
                      level: int = 1, notes: list[str] | tuple = ()) -> str:
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
        steps = sorted(params.lambda_fits)
        detail.append(f"* lambda     : {params.lambda_}   "
                      f"(V_A = {params.va}); from {len(steps)} gate steps, "
                      f"V_GS {steps[0]:.3f}..{steps[-1]:.3f} V")
    if params.rds_on is not None:
        detail.append(f"* R_DS(on)   : {params.rds_on}  (not a model "
                      f"parameter; for reference){_rds_on_window(params)}")
    detail.append(f"* V_DS slice : {params.vds_slice:.4f} V (measured, "
                  f"Kelvin-sensed)")
    detail += [
        "* V_GS       : commanded (vgs_set_v), not read back. The gate DAC's",
        "*              accuracy is unmeasured, so VTO's absolute value",
        "*              carries that error, in neither its stderr nor the",
        "*              spread below",
    ]
    detail.append(f"* fit range  : {params.vth_fit.range.rule}")
    detail += _valid_for(params)
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
    detail += [f"* {note}" for note in notes]

    body = [f".model {name} NMOS (",
            f"+   LEVEL = {level}",
            f"+   VTO   = {params.vth.value:.6g}",
            f"+   KP    = {params.kp_wl.value:.6g}"]
    if params.lambda_ is not None:
        body.append(f"+   LAMBDA = {params.lambda_.value:.6g}")
    body.append("+ )")

    return "\n".join(_header("NMOS", params, source, detail) + body) + "\n"


def _valid_for(params: MosfetParams) -> list[str]:
    """The window the V_th fit covered, read from the points it used.

    Taken from the fit rather than from ``--vgs-range``: a requested range
    is a bound, and the I_D floor or the slice can leave fewer steps inside
    it than asked for. A Level-1 square law fitted over a few top steps says
    nothing about the part outside them (2026-11-08, section (e)).
    """
    fit = params.vth_fit
    vgs = fit.x
    i_ma = fit.y ** 2 * 1000.0              # the fit is sqrt(I_D in A)
    lines = [
        f"* valid for  : V_GS {vgs.min():.3f}..{vgs.max():.3f} V, "
        f"I_D {i_ma.min():.3g}..{i_ma.max():.3g} mA "
        f"({vgs.size} points fitted, at V_DS = {params.vds_slice:.3f} V)"
    ]
    dof = vgs.size - 2
    if dof <= 1:
        lines += [
            f"* WARNING: the V_th fit has {dof} degree"
            f"{'' if dof == 1 else 's'} of freedom ({vgs.size} points, "
            f"2 parameters):",
            "*          too few to test the square law over this window.",
        ]
    return lines


def _rds_on_window(params: MosfetParams) -> str:
    """Where R_DS(on)'s gate step sits against the V_th fit's window."""
    if params.rds_on_vgs is None:
        return ""
    vgs = params.vth_fit.x
    where = ("" if vgs.min() <= params.rds_on_vgs <= vgs.max()
             else ", outside the fit window (valid for, below)")
    return f"\n*              from V_GS = {params.rds_on_vgs:.3f} V{where}"


def diode_model_card(params: DiodeParams, *, name: str = "EXTRACTED",
                     source: str | None = None,
                     notes: list[str] | tuple = ()) -> str:
    """A diode ``.model`` card."""
    detail = [
        f"* n          : {params.n}",
        f"* I_S        : {params.i_s}",
    ]
    if params.rs is not None:
        detail.append(f"* R_s        : {params.rs}")
    detail.append(f"* fit range  : {params.fit.range.rule}")
    detail += [f"* {note}" for note in notes]

    body = [f".model {name} D (",
            f"+   IS = {params.i_s.value:.6g}",
            f"+   N  = {params.n.value:.6g}"]
    if params.rs is not None:
        body.append(f"+   RS = {params.rs.value:.6g}")
    body.append("+ )")

    return "\n".join(_header("Diode", params, source, detail) + body) + "\n"
