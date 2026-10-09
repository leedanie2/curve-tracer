"""Command line: capture, hold, plot, extract, model.

    python -m ct_host capture --sim mosfet -o data/run.csv
    python -m ct_host hold    --sim resistor --vds 5 --seconds 10 -o data/hold.csv
    python -m ct_host extract data/run.csv --type mosfet
    python -m ct_host model   data/run.csv --type mosfet --name 2N7000_EXT
    python -m ct_host plot    data/run.csv --save iv.png

Every command accepts either a saved CSV or a live source, and ``--sim``
stands in for an instrument everywhere ``--port`` would go. That is what makes
the whole tool exercisable with nothing attached.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import sys
from pathlib import Path

from .csvio import Sweep, parse, save
from .dataset import vds_delta_report
from .extract import FitError, extract_diode, extract_mosfet
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

    out = save(sweep, args.output, source=source_description)
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
    if args.diagnostics:
        print()
        print(vds_delta_report(sweep, r_ptc_ohm=args.r_ptc).describe())
    if kind == "mosfet" and args.sensitivity and params.sensitivity is not None:
        print()
        print("V_th across fit-range choices")
        print(params.sensitivity.table.to_string(index=False))
    return 0


def cmd_model(args: argparse.Namespace) -> int:
    sweep = _checked(_load(args.csv), strict=not args.allow_mismatch)
    kind = args.type or _guess_kind(sweep)
    try:
        if kind == "mosfet":
            card = mosfet_model_card(extract_mosfet(sweep), name=args.name,
                                     source=args.csv)
        else:
            card = diode_model_card(extract_diode(sweep), name=args.name,
                                    source=args.csv)
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

    sweep = _checked(_load(args.csv), strict=False)
    if args.diagnostic:
        plot_vds_delta(sweep, r_ptc_ohm=args.r_ptc)
    else:
        plot_family(sweep)

    if args.save:
        plt.savefig(args.save, dpi=150, bbox_inches="tight")
        print(f"wrote {args.save}", file=sys.stderr)
    if args.show:
        plt.show()
    return 0


def cmd_ports(_: argparse.Namespace) -> int:
    ports = list_serial_ports()
    if not ports:
        print("no serial ports found (or pyserial is not installed)")
        return 0
    for device, description in ports:
        print(f"{device}\t{description}")
    return 0


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
    p.add_argument("--type", choices=["mosfet", "diode"])
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
    p.add_argument("--allow-mismatch", action="store_true",
                   help="warn instead of failing on calibration disagreement")
    p.set_defaults(func=cmd_extract)

    p = sub.add_parser("model", help="generate a SPICE .model card")
    p.add_argument("csv")
    p.add_argument("--type", choices=["mosfet", "diode"])
    p.add_argument("--name", default="EXTRACTED")
    p.add_argument("-o", "--output")
    p.add_argument("--allow-mismatch", action="store_true")
    p.set_defaults(func=cmd_model)

    p = sub.add_parser("plot", help="plot a saved CSV")
    p.add_argument("csv")
    p.add_argument("--save", metavar="PNG")
    p.add_argument("--show", action="store_true")
    p.add_argument("--diagnostic", action="store_true",
                   help="plot the vds_set - vds_meas series-drop check")
    p.add_argument("--r-ptc", type=float, default=None, metavar="OHM",
                   help="measured PTC resistance for --diagnostic; "
                        "overrides cal_r_ptc_ohm (re-measure after a trip)")
    p.set_defaults(func=cmd_plot)

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
