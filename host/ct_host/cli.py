"""Command line: capture, hold, plot, extract, model.

    python -m ct_host capture --sim mosfet -o data/run.csv
    python -m ct_host hold    --sim resistor --vds 5 --seconds 10 -o data/hold.csv
    python -m ct_host extract data/run.csv --type mosfet
    python -m ct_host model   data/run.csv --type mosfet --name 2N7000_EXT
    python -m ct_host plot    data/run.csv --save iv.png
    python -m ct_host extract data/rp.csv --type resistor
    python -m ct_host annotate data/run.csv --r-parallel data/rp.csv
    python -m ct_host simulate data/d.lib --like data/d.csv -o data/d_sim.csv
    python -m ct_host overlay  data/d.csv data/d_sim.csv --save overlay.png

Every command accepts either a saved CSV or a live source, and ``--sim``
stands in for an instrument everywhere ``--port`` would go. That is what makes
the whole tool exercisable with nothing attached.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import sys
from dataclasses import replace
from pathlib import Path

from .csvio import ContractError, Sweep, add_host_meta, parse, save
from .dataset import VDS_SET_MAX_V, vds_delta_report
from .extract import FitError, extract_diode, extract_mosfet
from .parallel import ParallelR, auto_fit, fit_sweep_resistor, from_meta, resolve, subtract
from .protocol import SweepRequest, run_hold, run_sweep
from .recompute import CalibrationMismatch, recompute
from .spice import diode_model_card, mosfet_model_card
from .transport import SimTransport, TransportError, list_serial_ports


def _source_args(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--port", help="serial device, e.g. /dev/tty.usbmodem1103")
    group.add_argument("--sim", nargs="?", const="mosfet",
                       choices=["mosfet", "diode", "resistor"],
                       help="drive the compiled simulator instead of hardware")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--sim-vth", type=float)
    parser.add_argument("--sim-k", type=float)
    parser.add_argument("--sim-lambda", type=float)
    parser.add_argument("--sim-is", type=float)
    parser.add_argument("--sim-n", type=float)
    parser.add_argument("--sim-rs", type=float)
    parser.add_argument("--sim-rload", type=float)
    parser.add_argument("--sim-rptc", type=float)
    parser.add_argument("--sim-rpar", type=float, metavar="OHM",
                        help="simulate a resistor across D-S with the DUT")
    parser.add_argument("--sim-dac-floor", type=float, metavar="V",
                        help="lowest node voltage the simulated DAC reaches")
    parser.add_argument("--sim-noise", type=float)


def _sweep_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--device", help="part name recorded in the header")
    parser.add_argument("--vgs", help="comma-separated gate steps, e.g. 2.5,3,3.5")
    parser.add_argument("--vds-max", type=float)
    parser.add_argument("--n", type=int, help="points per gate step")
    parser.add_argument("--oversample", type=int)
    parser.add_argument("--settle-us", type=int)
    parser.add_argument("--i-limit", type=float, metavar="MA",
                        help="DUT protection ceiling in mA")


def _open_transport(args: argparse.Namespace):
    if args.sim:
        return SimTransport(
            dut=args.sim, noise=args.sim_noise, vth=args.sim_vth,
            k=args.sim_k, lam=args.sim_lambda, is_=args.sim_is,
            n_diode=args.sim_n, rs=args.sim_rs, rload=args.sim_rload,
            rptc=args.sim_rptc, rpar=args.sim_rpar,
            dac_floor=args.sim_dac_floor,
        )
    from .transport import SerialTransport
    return SerialTransport(args.port, baudrate=args.baud)


def _request(args: argparse.Namespace) -> SweepRequest:
    vgs = None
    if args.vgs:
        vgs = [float(v) for v in args.vgs.split(",") if v.strip()]
    return SweepRequest(
        device=args.device,
        date=_dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        vgs_list=vgs, vds_max=args.vds_max, n=args.n,
        oversample_n=args.oversample, settle_us=args.settle_us,
        i_limit_ma=args.i_limit,
    )


def _load(path: str) -> Sweep:
    return parse(Path(path).read_text(), require_end=True)


def _checked(sweep: Sweep, *, strict: bool) -> Sweep:
    try:
        return recompute(sweep)
    except CalibrationMismatch as exc:
        if strict:
            print(f"error: {exc}", file=sys.stderr)
            raise SystemExit(2) from None
        print(f"warning: {exc}\n", file=sys.stderr)
        return recompute(sweep, check=False)


def _resolve_rp(spec: str, sweep: Sweep | None = None) -> ParallelR:
    try:
        return resolve(spec, sweep)
    except (ValueError, FitError) as exc:
        print(f"error: --r-parallel: {exc}", file=sys.stderr)
        raise SystemExit(2) from None


def _with_rp(sweep: Sweep, spec: str | None, *, report: bool = True) -> Sweep:
    """Subtract R_p: from ``--r-parallel`` if given, else the CSV's record.

    ``--r-parallel none`` turns a recorded R_p off. Whenever one is applied,
    the auto-fit is reported beside it as a cross-check.
    """
    if spec == "none":
        return sweep
    rp = _resolve_rp(spec, sweep) if spec else from_meta(sweep)
    if rp is None:
        return sweep
    if report:
        print(rp_report(sweep, rp), file=sys.stderr)
    return subtract(sweep, rp)


def rp_report(sweep: Sweep, rp: ParallelR) -> str:
    how = ("V / R_p" if rp.offset_ma is None
           else "V / R_p + offset (the calibration line, zero included)")
    lines = [f"R_p across D-S, subtracted from every row as {how}",
             rp.describe()]
    v = [r.v_dut for r in sweep.valid_rows]
    if v and rp.stderr is not None:
        hi = max(v)
        lines.append(f"  its standard error adds ±{rp.current_error_ma(hi) * 1000:.2g} uA "
                     f"at {hi:.3g} V, this capture's highest voltage, and "
                     f"less below it")
    if rp.method != "auto":
        fit, reason = auto_fit(sweep)
        if fit is None:
            lines.append(f"  cross-check, auto-fit: {reason}")
        else:
            lines.append(f"  cross-check, auto-fit: R = {fit.r} over {fit.n} rows, "
                         f"{(fit.r.value / rp.ohm - 1) * 100:+.2f}% from the value used; "
                         f"offset {fit.offset_ma.value:+.4f} mA")
    return "\n".join(lines) + "\n"


def zero_bracket(sweep: Sweep, lo_ma: float, hi_ma: float) -> list[str]:
    """Refit a diode with the instrument's zero at each end of a range.

    The zero is subtracted with R_p (``parallel``). Its value differs from
    one estimate to the next (board 2, 2026-11-08: -0.087 mA from the R_p
    calibration, -0.099 mA from the diode's own off rows), and n, I_S and
    R_s follow it. This is that systematic, quoted beside the statistical
    errors. The headline values stay those of the zero actually applied.
    """
    rp = sweep.r_parallel
    if rp is None:
        raise ValueError("--zero-bracket needs an R_p (and its zero) to vary")
    fits = [(z, extract_diode(subtract(sweep, replace(rp, offset_ma=z))))
            for z in (lo_ma, hi_ma)]
    (z0, a), (z1, b) = fits

    def row(label, va, vb, fmt, unit=""):
        return (f"  {label:<4}: {va:{fmt}}{unit} at {z0:+.3f} mA, "
                f"{vb:{fmt}}{unit} at {z1:+.3f} mA; spread {abs(vb - va):{fmt}}{unit}")

    lines = [f"zero range : n, I_S and R_s refitted with the instrument's zero "
             f"at {z0:+.4f} and {z1:+.4f} mA",
             row("n", a.n.value, b.n.value, ".4f"),
             row("I_S", a.i_s.value, b.i_s.value, ".4g", " A")]
    if a.rs is not None and b.rs is not None:
        lines.append(row("R_s", a.rs.value, b.rs.value, ".4f", " ohm"))
    lines.append(f"  fit residual rms {a.fit.residual_rms:.3g} / "
                 f"{b.fit.residual_rms:.3g}; points {a.rs_points} / {b.rs_points}")
    return lines


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

def cmd_capture(args: argparse.Namespace) -> int:
    live = None
    if args.live:
        from .plot import LivePlot
        live = LivePlot(i_limit_ma=args.i_limit).open()

    with _open_transport(args) as transport:
        source_description = transport.description
        print(f"source: {source_description}", file=sys.stderr)
        sweep = run_sweep(
            transport, _request(args),
            on_row=(live.on_row if live else None),
            on_meta=(live.on_meta if live else None),
        )

    if live is not None:
        live.finish(sweep)

    print(sweep.describe(), file=sys.stderr)
    if sweep.end_reason != "ok":
        print(f"\nNOTE: sweep ended '{sweep.end_reason}'. The flagged row is "
              f"kept in the file; it records where the device ran away.",
              file=sys.stderr)

    extra: list[tuple[str, str]] = []
    if args.r_parallel:
        rp = _resolve_rp(args.r_parallel, recompute(sweep, check=False))
        print("\n" + rp_report(recompute(sweep, check=False), rp).rstrip(),
              file=sys.stderr)
        extra = rp.meta_items()
    out = save(sweep, args.output, source=source_description, extra=extra)
    print(f"\nwrote {out}  ({len(sweep.rows)} rows)", file=sys.stderr)

    if live is not None and args.save_plot:
        live.save(args.save_plot)
        print(f"wrote {args.save_plot}", file=sys.stderr)
    return 0


def cmd_hold(args: argparse.Namespace) -> int:
    request = SweepRequest(
        device=args.device,
        date=_dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        vgs_list=[args.vgs], oversample_n=args.oversample,
        settle_us=args.settle_us, i_limit_ma=args.i_limit,
    )
    with _open_transport(args) as transport:
        source_description = transport.description
        print(f"source: {source_description}", file=sys.stderr)
        print(f"holding {args.vds} V at vgs {args.vgs} V for {args.seconds} s",
              file=sys.stderr)

        def show(row) -> None:
            print(f"  t={row.point:>4d} s  vds_meas {row.vds_meas_v:7.3f} V  "
                  f"i_meas {row.i_meas_ma:8.3f} mA  {row.flags}", file=sys.stderr)

        hold = run_hold(transport, args.vds, request, seconds=args.seconds,
                        on_row=show)

    if hold.end_reason == "ilimit":
        print(f"\nNOTE: hold ended 'ilimit' -- the current passed {args.i_limit or 60} mA "
              f"and the drain was zeroed.", file=sys.stderr)
    out = save(hold, args.output, source=source_description)
    print(f"\nwrote {out}  ({len(hold.rows)} rows, end {hold.end_reason})",
          file=sys.stderr)
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    sweep = _checked(_load(args.csv), strict=not args.allow_mismatch)
    kind = args.type or _guess_kind(sweep)

    if kind == "resistor":
        try:
            fit = fit_sweep_resistor(sweep)
        except FitError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"Resistor fit\n  device : {sweep.meta.device}"
              + ("   [SIMULATED -- not a bench measurement]"
                 if sweep.meta.is_simulated else "") + "\n")
        print(fit.describe())
        print(f"  lowest V reached: {fit.v_lo:.4f} V (the sweep's floor)")
        return 0

    sweep = _with_rp(sweep, args.r_parallel)
    try:
        if kind == "mosfet":
            params = extract_mosfet(
                sweep,
                vds_slice=args.vds_slice,
                vgs_range=(tuple(args.vgs_range) if args.vgs_range else None),
                saturation_margin_v=args.saturation_margin,
            )
        else:
            params = extract_diode(sweep)
    except FitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(params.describe())
    if args.zero_bracket:
        if kind != "diode":
            print("error: --zero-bracket is for diodes", file=sys.stderr)
            return 2
        try:
            print("\n  " + "\n  ".join(zero_bracket(sweep, *args.zero_bracket)))
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    if args.diagnostics:
        print()
        print(vds_delta_report(sweep, r_ptc_ohm=args.r_ptc,
                               vds_set_max_v=args.vds_set_max).describe())
    if kind == "mosfet" and args.sensitivity and params.sensitivity is not None:
        print()
        print("V_th across fit-range choices")
        print(params.sensitivity.table.to_string(index=False))
    return 0


def cmd_model(args: argparse.Namespace) -> int:
    sweep = _checked(_load(args.csv), strict=not args.allow_mismatch)
    kind = args.type or _guess_kind(sweep)
    sweep = _with_rp(sweep, args.r_parallel)
    notes = ([f"R_p        : {sweep.r_parallel.label}"]
             if sweep.r_parallel is not None else [])
    try:
        if args.zero_bracket:
            if kind != "diode":
                raise ValueError("--zero-bracket is for diodes")
            notes += zero_bracket(sweep, *args.zero_bracket)
    except (ValueError, FitError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    try:
        if kind == "mosfet":
            card = mosfet_model_card(extract_mosfet(sweep), name=args.name,
                                     source=args.csv, notes=notes)
        else:
            card = diode_model_card(extract_diode(sweep), name=args.name,
                                    source=args.csv, notes=notes)
    except FitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.output:
        Path(args.output).write_text(card)
        print(f"wrote {args.output}", file=sys.stderr)
    else:
        print(card, end="")
    return 0


def cmd_plot(args: argparse.Namespace) -> int:
    import matplotlib
    if args.save and not args.show:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from .plot import plot_family, plot_vds_delta

    sweep = _with_rp(_checked(_load(args.csv), strict=False), args.r_parallel)
    if args.diagnostic:
        plot_vds_delta(sweep, r_ptc_ohm=args.r_ptc,
                       vds_set_max_v=args.vds_set_max)
    else:
        plot_family(sweep)

    if args.save:
        plt.savefig(args.save, dpi=150, bbox_inches="tight")
        print(f"wrote {args.save}", file=sys.stderr)
    if args.show:
        plt.show()
    return 0


def cmd_simulate(args: argparse.Namespace) -> int:
    from .overlay import read_card, simulate, write_sim

    like = _with_rp(_checked(_load(args.like), strict=False), args.r_parallel,
                    report=False)
    try:
        card = read_card(args.card)
        sim = simulate(card, like, step=args.step)
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    out = write_sim(sim, args.output, like=args.like)
    print(f"{sim.meta['simulator']}: {sim.meta['model']}, "
          f"{len(sim.curves)} curve(s)\nwrote {out}", file=sys.stderr)
    return 0


def cmd_overlay(args: argparse.Namespace) -> int:
    import matplotlib
    matplotlib.use("Agg")

    from .overlay import plot_overlay, read_sim

    sweep = _with_rp(_checked(_load(args.csv), strict=False), args.r_parallel)
    fig = plot_overlay(sweep, read_sim(args.sim), title=args.title)
    fig.savefig(args.save, dpi=150, facecolor=fig.get_facecolor(),
                bbox_inches="tight")
    print(f"wrote {args.save}", file=sys.stderr)
    return 0


def cmd_annotate(args: argparse.Namespace) -> int:
    sweep = _checked(_load(args.csv), strict=False)
    rp = _resolve_rp(args.r_parallel, sweep)
    try:
        add_host_meta(args.csv, rp.meta_items(), replace_existing=args.force)
    except ContractError as exc:
        print(f"error: {exc}; pass --force to replace it", file=sys.stderr)
        return 2
    print(rp_report(sweep, rp).rstrip(), file=sys.stderr)
    print(f"wrote the R_p record into {args.csv}", file=sys.stderr)
    return 0


def cmd_ports(_: argparse.Namespace) -> int:
    ports = list_serial_ports()
    if not ports:
        print("no serial ports found (or pyserial is not installed)")
        return 0
    for device, description in ports:
        print(f"{device}\t{description}")
    return 0


def _vds_set_max(text: str) -> float | None:
    """``--vds-set-max``: a voltage, or ``none`` to fit every row."""
    return None if text.lower() == "none" else float(text)


def _rp_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--r-parallel", metavar="OHM|auto|CSV|none",
        help="subtract V/R_p, and a fitted R_p's zero, for a resistor across D-S: a calibration "
             "capture of R_p alone (primary), a value in ohms, auto (fit "
             "this capture's low end), or none. Default: the R_p recorded "
             "in the CSV header, if any")


def _zero_bracket_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--zero-bracket", type=float, nargs=2, metavar=("MA", "MA"),
        help="diode: refit with the instrument's zero at each of two values "
             "and report the spread in n, I_S and R_s (on `model`, in the "
             "card's header)")


def _guess_kind(sweep: Sweep) -> str:
    device = sweep.meta.device.lower()
    if "diode" in device or "led" in device or "1n" in device:
        return "diode"
    if len(sweep.meta.vgs_list) <= 1:
        return "diode"
    return "mosfet"


# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ct_host",
        description="Curve tracer host: capture, plot, extract, model.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("capture", help="run a sweep and save the CSV")
    _source_args(p)
    _sweep_args(p)
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--live", action="store_true", help="plot as it arrives")
    p.add_argument("--r-parallel", metavar="OHM|auto|CSV",
                   help="a resistor clamped across D-S with the device: record "
                        "it in the header (a calibration capture of it alone, "
                        "a value in ohms, or auto to fit this capture)")
    p.add_argument("--save-plot", metavar="PNG")
    p.set_defaults(func=cmd_capture)

    p = sub.add_parser("hold", help="hold one drain level, one row per second")
    _source_args(p)
    p.add_argument("--vds", type=float, required=True, help="drain level to hold, V")
    p.add_argument("--vgs", type=float, default=0.0, help="gate level, V (default 0)")
    p.add_argument("--seconds", type=float, default=30.0,
                   help="how long to hold before STOP (default 30)")
    p.add_argument("--device", help="part name recorded in the header")
    p.add_argument("--oversample", type=int)
    p.add_argument("--settle-us", type=int)
    p.add_argument("--i-limit", type=float, metavar="MA",
                   help="DUT protection ceiling in mA")
    p.add_argument("-o", "--output", required=True)
    p.set_defaults(func=cmd_hold)

    p = sub.add_parser("extract", help="extract parameters from a CSV")
    p.add_argument("csv")
    p.add_argument("--type", choices=["mosfet", "diode", "resistor"],
                   help="resistor: fit I = V/R + offset, e.g. R_p alone")
    _rp_arg(p)
    p.add_argument("--vds-slice", type=float,
                   help="measured drain voltage for the threshold fit")
    p.add_argument("--vgs-range", type=float, nargs=2, metavar=("LO", "HI"))
    p.add_argument("--saturation-margin", type=float, default=0.5)
    p.add_argument("--sensitivity", action="store_true",
                   help="print the full V_th fit-range table")
    p.add_argument("--diagnostics", action="store_true")
    p.add_argument("--r-ptc", type=float, default=None, metavar="OHM",
                   help="measured PTC resistance for the delta diagnostic; "
                        "overrides cal_r_ptc_ohm (re-measure after a trip)")
    p.add_argument("--vds-set-max", type=_vds_set_max, default=VDS_SET_MAX_V,
                   metavar="V",
                   help="highest vds_set_v the delta diagnostic fits "
                        f"(default {VDS_SET_MAX_V:g} V: above it the sweep DAC "
                        "is outside its rated load while SB21 is fitted); "
                        "'none' fits every row")
    p.add_argument("--allow-mismatch", action="store_true",
                   help="warn instead of failing on calibration disagreement")
    _zero_bracket_arg(p)
    p.set_defaults(func=cmd_extract)

    p = sub.add_parser("model", help="generate a SPICE .model card")
    p.add_argument("csv")
    p.add_argument("--type", choices=["mosfet", "diode"])
    p.add_argument("--name", default="EXTRACTED")
    p.add_argument("-o", "--output")
    _rp_arg(p)
    p.add_argument("--allow-mismatch", action="store_true")
    _zero_bracket_arg(p)
    p.set_defaults(func=cmd_model)

    p = sub.add_parser("plot", help="plot a saved CSV")
    p.add_argument("csv")
    _rp_arg(p)
    p.add_argument("--save", metavar="PNG")
    p.add_argument("--show", action="store_true")
    p.add_argument("--diagnostic", action="store_true",
                   help="plot the vds_set - vds_meas series-drop check")
    p.add_argument("--r-ptc", type=float, default=None, metavar="OHM",
                   help="measured PTC resistance for --diagnostic; "
                        "overrides cal_r_ptc_ohm (re-measure after a trip)")
    p.add_argument("--vds-set-max", type=_vds_set_max, default=VDS_SET_MAX_V,
                   metavar="V",
                   help="highest vds_set_v the delta diagnostic fits "
                        f"(default {VDS_SET_MAX_V:g} V: above it the sweep DAC "
                        "is outside its rated load while SB21 is fitted); "
                        "'none' fits every row")
    p.set_defaults(func=cmd_plot)

    p = sub.add_parser("simulate",
                       help="sweep a .model card in ngspice over a capture's range")
    p.add_argument("card", help="the .model card from `model`")
    p.add_argument("--like", required=True, metavar="CSV",
                   help="the capture whose voltage range and gate steps to use")
    p.add_argument("--step", type=float, default=0.002, metavar="V")
    p.add_argument("-o", "--output", required=True)
    _rp_arg(p)
    p.set_defaults(func=cmd_simulate)

    p = sub.add_parser("overlay",
                       help="measured vs simulated I-V, with residuals")
    p.add_argument("csv", help="the capture")
    p.add_argument("sim", help="the output of `simulate`")
    p.add_argument("--save", required=True, metavar="PNG")
    p.add_argument("--title", help="device name for the title")
    _rp_arg(p)
    p.set_defaults(func=cmd_overlay)

    p = sub.add_parser("annotate",
                       help="record the R_p a saved capture was taken with")
    p.add_argument("csv")
    p.add_argument("--r-parallel", required=True, metavar="OHM|auto|CSV")
    p.add_argument("--force", action="store_true",
                   help="replace an R_p record already in the file")
    p.set_defaults(func=cmd_annotate)

    p = sub.add_parser("ports", help="list serial ports")
    p.set_defaults(func=cmd_ports)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except TransportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
