"""Transport, live plotting and the command line -- all against the simulator.

Nothing here opens a serial port. The point of the transport abstraction is
that everything above it is identical either way, so exercising the simulator
path exercises the code that will run against hardware.
"""

from __future__ import annotations

import time

import pytest

from ct_host.cli import main
from ct_host.csvio import parse
from ct_host.plot import LivePlot, plot_family, plot_vds_delta
from ct_host.protocol import (
    CommandError,
    SweepRequest,
    get_params,
    identify,
    run_sweep,
)
from ct_host.transport import SimTransport, Transport, TransportError


# --------------------------------------------------------------------------
# Transport
# --------------------------------------------------------------------------

def test_sim_transport_satisfies_the_protocol():
    with SimTransport() as transport:
        assert isinstance(transport, Transport)


def test_identify_reports_firmware_and_board():
    with SimTransport() as transport:
        info = identify(transport)
    assert info["board"] == "nucleo-f303re"
    assert "fw" in info and "schema" in info


def test_get_params_returns_the_parameter_table():
    with SimTransport() as transport:
        params = get_params(transport)
    for key in ("settle_us", "n", "oversample_n", "i_limit_ma", "vds_max"):
        assert key in params


def test_rejected_set_raises_rather_than_continuing():
    """Setters reject; a host that ignored that would sweep at wrong settings."""
    with SimTransport() as transport:
        with pytest.raises(CommandError, match="rejected"):
            run_sweep(transport, SweepRequest(i_limit_ma=500.0))


def test_rejected_set_leaves_the_old_ceiling_in_place():
    with SimTransport() as transport:
        with pytest.raises(CommandError):
            run_sweep(transport, SweepRequest(i_limit_ma=500.0))
        assert float(get_params(transport)["i_limit_ma"]) == pytest.approx(60.0)


def test_missing_simulator_binary_is_a_clear_error(tmp_path):
    with pytest.raises(TransportError, match="not built"):
        SimTransport(path=tmp_path / "nope")


def test_rows_arrive_before_the_sweep_finishes():
    """The property the live plot depends on.

    The simulator streams line by line, so the first row must reach the host
    measurably before the last one does -- exactly as over the serial link.
    """
    timestamps: list[float] = []

    with SimTransport() as transport:
        run_sweep(
            transport,
            SweepRequest(n=400, vgs_list=[2.5, 3.0, 3.5, 4.0], i_limit_ma=165),
            on_row=lambda _row: timestamps.append(time.perf_counter()),
        )

    assert len(timestamps) == 1600
    assert timestamps[-1] > timestamps[0]


def test_a_large_family_is_not_truncated():
    """The 64 KB staging buffer regression, from the host's side."""
    with SimTransport() as transport:
        sweep = run_sweep(transport, SweepRequest(
            n=200, vgs_list=[2.5, 3, 3.5, 4, 4.5, 5, 5.5, 6],
            vds_max=10, i_limit_ma=165))
    assert sweep.complete
    assert sweep.end_reason == "ok"
    assert len(sweep.rows) == 1600
    assert [r.point for r in sweep.rows] == list(range(1600))


# --------------------------------------------------------------------------
# Live plot
# --------------------------------------------------------------------------

def test_live_plot_accumulates_one_series_per_gate_step(mosfet_sweep):
    plot = LivePlot(show=False).open()
    for row in mosfet_sweep.rows:
        plot.on_row(row)
    assert len(plot.series) == 6
    assert plot.n_rows == len(mosfet_sweep.rows)


def test_live_plot_uses_measured_voltage_on_the_x_axis(mosfet_sweep):
    """Never vds_set_v -- the commanded value is wrong by over a volt."""
    plot = LivePlot(show=False).open()
    for row in mosfet_sweep.rows:
        plot.on_row(row)

    first_vgs = next(iter(plot.series))
    xs, _ = plot.series[first_vgs]
    expected = [r.v_dut for r in mosfet_sweep.rows
                if r.vgs_set_v == first_vgs]
    assert xs == expected
    assert "measured" in plot.axes.get_xlabel()


def test_live_plot_separates_flagged_points(ilimit_sweep):
    plot = LivePlot(show=False).open()
    for row in ilimit_sweep.rows:
        plot.on_row(row)
    assert len(plot.flagged[0]) == len(ilimit_sweep.flagged_rows) == 1
    total = sum(len(xs) for xs, _ in plot.series.values())
    assert total == len(ilimit_sweep.valid_rows)


def test_live_plot_drives_from_run_sweep_directly():
    plot = LivePlot(show=False).open()
    with SimTransport() as transport:
        sweep = run_sweep(transport, SweepRequest(n=30, vgs_list=[2.5, 3.0]),
                          on_row=plot.on_row, on_meta=plot.on_meta)
    plot.finish(sweep)
    assert plot.n_rows == 60


def test_static_plots_render(mosfet, tmp_path):
    ax = plot_family(mosfet)
    assert "measured" in ax.get_xlabel()
    ax.figure.savefig(tmp_path / "family.png")

    ax2 = plot_vds_delta(mosfet, r_ptc_ohm=0.0)   # the simulator models no PTC
    assert "as designed" in ax2.get_title()
    ax2.figure.savefig(tmp_path / "delta.png")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def test_capture_writes_a_parseable_file(tmp_path):
    out = tmp_path / "cap.csv"
    code = main(["capture", "--sim", "mosfet", "--sim-vth", "2.15",
                 "--sim-k", "0.055", "--device", "SIMTEST",
                 "--vgs", "2.6,2.9,3.2,3.5", "--n", "40", "--vds-max", "10",
                 "--i-limit", "165", "-o", str(out)])
    assert code == 0

    sweep = parse(out.read_text(), require_end=True)
    assert len(sweep.rows) == 160
    assert sweep.meta.device == "SIMTEST"
    assert sweep.meta["host_source"].startswith("ct_sim")
    assert sweep.meta.is_simulated, "a renamed sim capture must stay marked"


def test_extract_prints_both_uncertainties(tmp_path, capsys):
    out = tmp_path / "cap.csv"
    main(["capture", "--sim", "mosfet", "--sim-vth", "2.15", "--sim-k", "0.055",
          "--vgs", "2.6,2.9,3.2,3.5", "--n", "40", "--i-limit", "165",
          "-o", str(out)])
    capsys.readouterr()

    assert main(["extract", str(out), "--type", "mosfet"]) == 0
    printed = capsys.readouterr().out
    assert "V_th" in printed
    assert "fit standard error" in printed
    assert "fit-range spread" in printed
    assert "KP*W/L" in printed


def test_model_emits_a_spice_card(tmp_path, capsys):
    out = tmp_path / "cap.csv"
    main(["capture", "--sim", "mosfet", "--sim-vth", "2.15", "--sim-k", "0.055",
          "--vgs", "2.6,2.9,3.2,3.5", "--n", "40", "--i-limit", "165",
          "-o", str(out)])
    capsys.readouterr()

    assert main(["model", str(out), "--type", "mosfet", "--name", "M1"]) == 0
    card = capsys.readouterr().out
    assert ".model M1 NMOS (" in card
    assert "VTO   = 2.15" in card
    assert "SIMULATED" in card


def test_plot_command_saves_a_png(tmp_path):
    out = tmp_path / "cap.csv"
    main(["capture", "--sim", "mosfet", "--vgs", "2.6,3.0", "--n", "30",
          "--i-limit", "165", "-o", str(out)])
    png = tmp_path / "iv.png"
    assert main(["plot", str(out), "--save", str(png)]) == 0
    assert png.exists() and png.stat().st_size > 1000


def test_calibration_mismatch_fails_the_command(tmp_path, capsys):
    out = tmp_path / "cap.csv"
    main(["capture", "--sim", "mosfet", "--vgs", "2.6,3.0,3.4", "--n", "30",
          "--i-limit", "165", "-o", str(out)])
    out.write_text(out.read_text().replace("# cal_shunt_ohm: 1.000",
                                           "# cal_shunt_ohm: 0.980"))
    capsys.readouterr()

    with pytest.raises(SystemExit) as excinfo:
        main(["extract", str(out), "--type", "mosfet"])
    assert excinfo.value.code == 2
    assert "cal_shunt_ohm" in capsys.readouterr().err


def test_mismatch_can_be_overridden_deliberately(tmp_path, capsys):
    out = tmp_path / "cap.csv"
    main(["capture", "--sim", "mosfet", "--vgs", "2.6,3.0,3.4", "--n", "40",
          "--i-limit", "165", "-o", str(out)])
    out.write_text(out.read_text().replace("# cal_shunt_ohm: 1.000",
                                           "# cal_shunt_ohm: 0.980"))
    capsys.readouterr()

    assert main(["extract", str(out), "--type", "mosfet",
                 "--allow-mismatch"]) == 0
    captured = capsys.readouterr()
    assert "warning" in captured.err
    assert "V_th" in captured.out


def test_truncated_file_is_refused(tmp_path):
    from ct_host.csvio import TruncatedTranscript

    out = tmp_path / "cap.csv"
    main(["capture", "--sim", "mosfet", "--vgs", "2.6,3.0", "--n", "20",
          "--i-limit", "165", "-o", str(out)])
    text = "\r\n".join(line for line in out.read_text().splitlines()
                       if not line.startswith("# end:")) + "\r\n"
    out.write_text(text)

    with pytest.raises(TruncatedTranscript):
        main(["extract", str(out), "--type", "mosfet"])
