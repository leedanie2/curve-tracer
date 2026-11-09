"""A resistor across D-S with the device: R_p, and taking its current out.

Board 2 oscillates at open load with C1 empty (Block 1, 2026-11-03), so the
diode and MOSFET runs clamp R_p across D-S. These tests use sim 13's 470 ohm;
on the bench that oscillated, and the R_p in use is L1, 200 ohm || 100 nF
(2026-11-08). The firmware reports R_p's current as device current. These tests
feed the simulator a known device with a known R_p beside it, calibrate R_p
from a capture of it alone, as MVP card step 14 does, and require the device
back. They also check that leaving the correction out is detectably wrong.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from conftest import KNOWN_DIODE, KNOWN_MOSFET, run
from ct_host.cli import main
from ct_host.csvio import ContractError, parse, save
from ct_host.dataset import vds_delta_report
from ct_host.extract import FitError, extract_diode, extract_mosfet
from ct_host.parallel import (auto_fit, fit_sweep_resistor, from_fit, from_meta,
                              resolve, subtract)
from ct_host.protocol import SweepRequest
from ct_host.recompute import recompute

R_P = 470.0
R_PTC = 8.4

DIODE_REQUEST = SweepRequest(device="sim-diode", n=100, vds_max=1.5,
                             i_limit_ma=40, vgs_list=[0])


@pytest.fixture(scope="module")
def rp_alone():
    return recompute(run(
        SweepRequest(device="sim-rp", n=100, vds_max=1.5, i_limit_ma=40,
                     vgs_list=[0]),
        dut="resistor", rload=R_P, rptc=R_PTC, noise=2))


@pytest.fixture(scope="module")
def cal_csv(rp_alone, tmp_path_factory):
    return save(rp_alone, tmp_path_factory.mktemp("rp") / "rp.csv")


@pytest.fixture(scope="module")
def diode_rp():
    return recompute(run(DIODE_REQUEST, dut="diode", rpar=R_P, rptc=R_PTC,
                         noise=2, **KNOWN_DIODE))


def test_calibration_capture_fits_r_p(rp_alone):
    fit = fit_sweep_resistor(rp_alone)
    assert fit.r.value == pytest.approx(R_P, rel=0.005)
    assert abs(fit.offset_ma.value) < 0.01


def test_diode_is_recovered_with_r_p_subtracted(diode_rp, cal_csv):
    params = extract_diode(subtract(diode_rp, resolve(str(cal_csv))))
    assert params.n.value == pytest.approx(KNOWN_DIODE["n_diode"], rel=0.01)
    assert params.i_s.value == pytest.approx(KNOWN_DIODE["is_"], rel=0.15)
    assert params.rs.value == pytest.approx(KNOWN_DIODE["rs"], rel=0.10)


def test_diode_without_the_subtraction_is_detectably_wrong(diode_rp):
    """470 ohm carries more than the diode below ~0.6 V; n comes out absurd."""
    params = extract_diode(diode_rp)
    assert params.n.value > 3.0


def test_auto_fit_cross_checks_the_calibration(diode_rp):
    fit, reason = auto_fit(diode_rp)
    assert reason == ""
    assert fit.r.value == pytest.approx(R_P, rel=0.03)


def test_auto_fit_is_unavailable_above_a_dac_floor():
    """A buffered DAC floor of 0.66 V at the node leaves no rows below 0.25 V."""
    sweep = recompute(run(DIODE_REQUEST, dut="diode", rpar=R_P, rptc=R_PTC,
                          dac_floor=0.66, **KNOWN_DIODE))
    fit, reason = auto_fit(sweep)
    assert fit is None and "floor" in reason
    with pytest.raises(FitError, match="unavailable"):
        resolve("auto", sweep)


def test_a_given_value_carries_no_standard_error():
    rp = resolve("468.2")
    assert (rp.ohm, rp.stderr, rp.method) == (468.2, None, "given")
    assert rp.offset_ma is None


#: Board 2's current zero on 2026-11-08: -0.087 mA in the R_p calibration,
#: -0.095 to -0.099 mA in the diode and MOSFET captures' off regions.
ZERO_MA = -0.09


def _with_zero(sweep):
    """The same capture read by an instrument whose current zero is ZERO_MA."""
    return replace(sweep, rows=[replace(r, i_recomp_ma=r.i_recomp_ma + ZERO_MA)
                                for r in sweep.rows])


def test_the_calibration_zero_is_subtracted_with_r_p(rp_alone, diode_rp):
    fit = fit_sweep_resistor(_with_zero(rp_alone))
    assert fit.offset_ma.value == pytest.approx(ZERO_MA, abs=0.01)
    rp = from_fit(fit, "calibration", "test")
    params = extract_diode(subtract(_with_zero(diode_rp), rp))
    assert params.n.value == pytest.approx(KNOWN_DIODE["n_diode"], rel=0.01)
    assert params.i_s.value == pytest.approx(KNOWN_DIODE["is_"], rel=0.15)


def test_leaving_the_zero_in_biases_the_diode(rp_alone, diode_rp):
    """Board 2: n read 1.651 with the zero left in, 1.789 with it out."""
    fit = fit_sweep_resistor(_with_zero(rp_alone))
    rp = replace(from_fit(fit, "calibration", "test"), offset_ma=None)
    params = extract_diode(subtract(_with_zero(diode_rp), rp))
    assert params.n.value < 0.97 * KNOWN_DIODE["n_diode"]


def test_a_calibration_file_must_be_r_p_alone(tmp_path, cal_csv):
    out = tmp_path / "d.csv"
    main(["capture", "--sim", "diode", "--sim-rpar", "470", "--vgs", "0",
          "--vds-max", "1.5", "--n", "30", "--i-limit", "40",
          "--r-parallel", str(cal_csv), "-o", str(out)])
    with pytest.raises(ContractError, match="not a capture of R_p alone"):
        resolve(str(out))


def test_series_drop_diagnostic_uses_total_current(diode_rp, cal_csv):
    """R_p's current drops across R_iso too; leaving it out reads as a fault."""
    report = vds_delta_report(subtract(diode_rp, resolve(str(cal_csv))),
                              r_ptc_ohm=R_PTC)
    assert report.verdict == "as designed"


def test_mosfet_is_recovered_with_r_p_subtracted(cal_csv):
    sweep = recompute(run(
        SweepRequest(device="sim-mosfet", n=60, vds_max=10, i_limit_ma=165,
                     vgs_list=[1.8, 2.6, 2.8, 3.0, 3.2, 3.4, 3.6]),
        dut="mosfet", rpar=R_P, **KNOWN_MOSFET))
    fit, _ = auto_fit(sweep)
    assert fit.r.value == pytest.approx(R_P, rel=0.01), "lowest step is off"
    params = extract_mosfet(subtract(sweep, resolve(str(cal_csv))))
    assert params.vth.value == pytest.approx(KNOWN_MOSFET["vth"], abs=0.01)
    # The simulator's saturation law is k/2 * V_ov^2, so KP*W/L = k.
    assert params.kp_wl.value == pytest.approx(KNOWN_MOSFET["k"], rel=0.02)


# --------------------------------------------------------------------------
# The record in the CSV, and the command line
# --------------------------------------------------------------------------

@pytest.fixture
def diode_csv(tmp_path, cal_csv):
    out = tmp_path / "diode_rp.csv"
    assert main(["capture", "--sim", "diode", "--sim-rpar", "470",
                 "--sim-rptc", "8.4", "--sim-noise", "2", "--vgs", "0",
                 "--vds-max", "1.5", "--n", "100", "--i-limit", "40",
                 "--device", "1N4148", "--r-parallel", str(cal_csv),
                 "-o", str(out)]) == 0
    return out


def test_capture_records_r_p_and_its_source(diode_csv, cal_csv):
    sweep = parse(diode_csv.read_text(), require_end=True)
    rp = from_meta(sweep)
    assert rp.method == "calibration"
    assert rp.ohm == pytest.approx(R_P, rel=0.005)
    assert str(cal_csv) in rp.source
    assert rp.offset_ma == pytest.approx(fit_sweep_resistor(
        parse(cal_csv.read_text(), require_end=True)).offset_ma.value, abs=1e-6)
    assert sweep.meta.is_simulated


def test_a_record_without_a_zero_reads_as_none(tmp_path, cal_csv):
    """Captures annotated before 2026-11-08 carry R_p but no zero."""
    text = (tmp_path / "old.csv")
    out = tmp_path / "d.csv"
    main(["capture", "--sim", "diode", "--sim-rpar", "470", "--vgs", "0",
          "--vds-max", "1.5", "--n", "30", "--i-limit", "40",
          "--r-parallel", str(cal_csv), "-o", str(out)])
    lines = [ln for ln in out.read_text().splitlines()
             if not ln.startswith("# host_r_parallel_offset")]
    text.write_text("\n".join(lines) + "\n")
    rp = from_meta(parse(text.read_text(), require_end=True))
    assert rp.offset_ma is None and rp.current_ma(0.5) == pytest.approx(0.5 / rp.ohm * 1000)


def test_extract_applies_the_recorded_r_p_by_default(diode_csv, capsys):
    capsys.readouterr()
    assert main(["extract", str(diode_csv), "--type", "diode"]) == 0
    captured = capsys.readouterr()
    assert "R_p = 470" in captured.err
    assert "cross-check, auto-fit" in captured.err
    n = float(captured.out.split("n      = ")[1].split()[0])
    assert n == pytest.approx(KNOWN_DIODE["n_diode"], rel=0.01)


def test_r_parallel_none_turns_the_record_off(diode_csv, capsys):
    capsys.readouterr()
    main(["extract", str(diode_csv), "--type", "diode", "--r-parallel", "none"])
    captured = capsys.readouterr()
    assert "R_p" not in captured.err
    assert "n      = 1.75" not in captured.out


def test_model_card_names_r_p(diode_csv, capsys):
    capsys.readouterr()
    main(["model", str(diode_csv), "--type", "diode", "--name", "D1"])
    card = capsys.readouterr().out
    assert "* R_p        : R_p = 470" in card and "calibration" in card


def test_plot_labels_r_p(diode_csv, tmp_path):
    import matplotlib.pyplot as plt

    png = tmp_path / "d.png"
    assert main(["plot", str(diode_csv), "--save", str(png)]) == 0
    ax = plt.gcf().axes[0]
    assert "subtracted" in ax.get_ylabel()
    assert any("R_p = 470" in t.get_text() for t in ax.texts)


def test_extract_resistor_reports_fit_and_floor(cal_csv, capsys):
    capsys.readouterr()
    assert main(["extract", str(cal_csv), "--type", "resistor"]) == 0
    out = capsys.readouterr().out
    assert "R       = 470" in out and "offset" in out and "lowest V" in out


def test_annotate_adds_the_record_once(tmp_path, cal_csv, capsys):
    out = tmp_path / "late.csv"
    main(["capture", "--sim", "diode", "--sim-rpar", "470", "--vgs", "0",
          "--vds-max", "1.5", "--n", "60", "--i-limit", "40", "-o", str(out)])
    rows_before = [ln for ln in out.read_text().splitlines()
                   if not ln.startswith("#")]

    assert main(["annotate", str(out), "--r-parallel", str(cal_csv)]) == 0
    assert main(["annotate", str(out), "--r-parallel", "471"]) == 2
    assert main(["annotate", str(out), "--r-parallel", "471", "--force"]) == 0
    raw = out.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "line endings stay CRLF"

    text = out.read_text()
    assert text.count("# host_r_parallel_ohm:") == 1
    assert from_meta(parse(text)).ohm == 471.0
    assert [ln for ln in text.splitlines() if not ln.startswith("#")] == rows_before
