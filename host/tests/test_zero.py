"""The instrument's current zero, subtracted on its own: ``--zero``.

Board 2 read about -0.09 mA with nothing conducting (2026-11-08). With a
stabiliser that draws no DC (MVP card section E) there is no R_p line to
carry that zero, so it needs a source of its own. These tests check each
source, that a given zero replaces an R_p calibration's offset rather than
adding to it, and that the 11-08 diode reproduces the published headline
when given the same R_p and zero.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from conftest import KNOWN_DIODE, KNOWN_MOSFET, run
from ct_host.cli import main
from ct_host.csvio import ContractError, parse
from ct_host.extract import FitError, extract_diode
from ct_host.parallel import ParallelR, subtract
from ct_host.protocol import SweepRequest
from ct_host.recompute import recompute
from ct_host.zero import apply_zero, resolve_zero

#: One range-1 current count, mA: 3.3 V / 4095 / gain 20 / 1 ohm.
LSB_MA = 3.3 / 4095 / 20 * 1000

H4 = Path(__file__).resolve().parents[1] / "h4"
DIODE_11_08 = H4 / "mvp_17_diode_rp.csv"
ZERO_11_08 = -0.0873765        # the step 14 calibration's offset, mA
R_P_11_08 = "201.311"          # the step 14 calibration's R, ohm

#: A planted zero, near board 2's.
ZERO_MA = -0.09


def _shifted(sweep, ma):
    """The same capture read by an instrument whose current zero is ``ma``."""
    sweep = recompute(sweep)
    return replace(sweep, rows=[replace(r, i_recomp_ma=r.i_recomp_ma + ma)
                                for r in sweep.rows])


def _hold(tmp_path, name, vds, rload, *, counts=0):
    """A ct_sim hold; ``counts`` lifts the current channel by that many ADC
    counts, as an instrument with a positive zero would read."""
    out = tmp_path / name
    assert main(["hold", "--sim", "resistor", "--sim-rload", str(rload),
                 "--vds", str(vds), "--seconds", "0.5", "-o", str(out)]) == 0
    if counts:
        lines = []
        for ln in out.read_text().splitlines(keepends=True):
            f = ln.rstrip("\r\n").split(",")
            if ln.startswith("#") or f[0] == "point":
                lines.append(ln)
                continue
            f[4] = f"{float(f[4]) + counts * LSB_MA:.4f}"
            f[5] = str(int(f[5]) + counts * 64)
            lines.append(",".join(f) + ln[len(ln.rstrip("\r\n")):])
        out.write_text("".join(lines), newline="")
    return out


# --------------------------------------------------------------------------
# Sources
# --------------------------------------------------------------------------

def test_a_given_zero_is_taken_as_written():
    z = resolve_zero("-0.05")
    assert (z.ma, z.stderr, z.method) == (-0.05, None, "given")


def test_holds_give_their_mean_and_name_each_file(tmp_path):
    """16 counts (0.64 mA) is clear of board 2's floor at 0.2 and 1 V."""
    a = _hold(tmp_path, "z1.csv", 0.2, 1e9, counts=16)
    b = _hold(tmp_path, "z2.csv", 1, 1e9, counts=16)
    z = resolve_zero(f"{a},{b}")
    expected = [r.i_total_ma for f in (a, b)
                for r in recompute(parse(f.read_text())).valid_rows]
    assert z.method == "holds"
    assert z.ma == pytest.approx(sum(expected) / len(expected), abs=1e-9)
    assert z.ma == pytest.approx(16 * LSB_MA, abs=0.02)
    assert "z1.csv" in z.source and "z2.csv" in z.source


def test_a_hold_on_the_channel_s_floor_is_not_a_zero(tmp_path):
    """Nothing drawing current and a negative zero: the floor, not the zero."""
    floor = _hold(tmp_path, "f.csv", 1, 1e9)
    with pytest.raises(ContractError, match="on its floor"):
        resolve_zero(str(floor))


def test_the_floor_rises_with_the_node_voltage(tmp_path):
    """8 counts is clear of the floor at 0.2 V (5.4 counts) but not at 6 V
    (20.4): board 2's 11-13 cap-only holds read 0.824 mA there."""
    assert resolve_zero(str(_hold(tmp_path, "lo.csv", 0.2, 1e9, counts=8))).ma > 0
    with pytest.raises(ContractError, match="on its floor"):
        resolve_zero(str(_hold(tmp_path, "hi.csv", 6, 1e9, counts=8)))


S3_24 = H4 / "s3_24_diode.csv"


def test_auto_refuses_the_11_13_cap_only_diode():
    """Its off rows read the floor, 5.4-5.9 counts; the old 5-count guard took
    them for the zero (+0.217 mA) and read n as 1.495."""
    sweep = recompute(parse(S3_24.read_text()))
    with pytest.raises(FitError, match="sit on the floor"):
        resolve_zero("auto", sweep)


def test_a_hold_with_a_load_is_not_a_zero(tmp_path):
    loaded = _hold(tmp_path, "l1.csv", 2, 200)
    with pytest.raises(ContractError, match="drawing current"):
        resolve_zero(str(loaded))


DIODE = SweepRequest(device="sim-diode", n=100, vds_max=1.5, i_limit_ma=40,
                     vgs_list=[0])


def test_auto_reads_a_diode_s_own_off_rows():
    """With R_p lifting the channel, as L1 did on 2026-11-08."""
    raw = run(DIODE, dut="diode", rpar=470, noise=2, **KNOWN_DIODE)
    sweep = subtract(_shifted(raw, ZERO_MA), ParallelR(470.0, None, "given", "test"))
    z = resolve_zero("auto", sweep)
    assert z.ma == pytest.approx(ZERO_MA, abs=0.005)
    params = extract_diode(apply_zero(sweep, z))
    assert params.n.value == pytest.approx(KNOWN_DIODE["n_diode"], rel=0.01)


def test_auto_skips_the_channel_s_floor():
    """No R_p: the off rows sit at 0 counts, and auto says so."""
    sweep = _shifted(run(DIODE, dut="diode", noise=2, **KNOWN_DIODE), ZERO_MA)
    with pytest.raises(FitError, match="floor"):
        resolve_zero("auto", sweep)


def test_auto_refuses_a_mosfet_family():
    sweep = run(SweepRequest(device="sim-mosfet", n=30, vds_max=5, i_limit_ma=165,
                             vgs_list=[2.6, 3.0]), dut="mosfet", **KNOWN_MOSFET)
    with pytest.raises(FitError, match="one gate step"):
        resolve_zero("auto", sweep)


# --------------------------------------------------------------------------
# The 11-08 diode
# --------------------------------------------------------------------------

def _extract(capsys, *extra):
    capsys.readouterr()
    assert main(["extract", str(DIODE_11_08), "--type", "diode", *extra]) == 0
    out = capsys.readouterr()
    value = lambda key: float(out.out.split(f"{key} = ")[1].split()[0])  # noqa: E731
    return value("n     "), value("I_S   "), value("R_s   "), out.err


def test_the_11_08_diode_reproduces_the_published_headline(capsys):
    """README and mvp_17_diode.lib: n 1.7885, I_S 2.6795 nA, R_s 1.1353 ohm."""
    n, i_s, r_s, err = _extract(capsys, "--r-parallel", R_P_11_08,
                                "--zero", str(ZERO_11_08))
    assert n == pytest.approx(1.7885, abs=1e-4)
    assert i_s == pytest.approx(2.6795e-9, rel=1e-3)
    assert r_s == pytest.approx(1.1353, abs=1e-3)
    assert "zero -0.0874 mA subtracted (given" in err


def test_a_given_zero_replaces_the_calibration_offset(capsys):
    """Calibration R_p plus --zero: the zero once, not twice."""
    n, i_s, _, err = _extract(capsys, "--r-parallel", str(H4 / "mvp_14_rp.csv"),
                              "--zero", str(ZERO_11_08))
    assert n == pytest.approx(1.7885, abs=1e-4)
    assert i_s == pytest.approx(2.6795e-9, rel=1e-3)
    assert "is not subtracted; the zero below replaces it" in err


def test_the_zero_bracket_varies_the_given_zero(capsys):
    capsys.readouterr()
    assert main(["extract", str(DIODE_11_08), "--type", "diode",
                 "--r-parallel", R_P_11_08, "--zero", str(ZERO_11_08),
                 "--zero-bracket", "-0.087", "-0.099"]) == 0
    out = capsys.readouterr().out
    assert "1.7877 at -0.087 mA, 1.8309 at -0.099 mA" in out


# --------------------------------------------------------------------------
# Output headers
# --------------------------------------------------------------------------

def test_model_card_and_plot_record_the_zero_and_its_source(tmp_path, capsys):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    capsys.readouterr()
    assert main(["model", str(DIODE_11_08), "--type", "diode", "--zero", "auto"]) == 0
    card = capsys.readouterr().out
    assert "* zero       : zero -0.09" in card and "(auto: this capture" in card

    assert main(["plot", str(DIODE_11_08), "--zero", "auto",
                 "--save", str(tmp_path / "p.png")]) == 0
    ax = plt.gcf().axes[0]
    assert "zero subtracted" in ax.get_ylabel()
    assert any("auto: this capture" in t.get_text() for t in ax.texts)


# --------------------------------------------------------------------------
# overlay and simulate
# --------------------------------------------------------------------------

def _overlay(tmp_path, *extra):
    """Draw the 11-08 overlay; return its plotted data and its texts."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    plt.close("all")
    assert main(["overlay", str(DIODE_11_08), str(H4 / "mvp_17_diode_sim.csv"),
                 "--save", str(tmp_path / "o.png"), *extra]) == 0
    fig = plt.gcf()
    data = []
    for ax in fig.axes:
        data += [np.asarray(ln.get_xydata()) for ln in ax.lines]
        data += [np.asarray(c.get_offsets()) for c in ax.collections]
    texts = [t.get_text() for t in fig.findobj(lambda a: hasattr(a, "get_text"))]
    return data, texts


def test_the_11_08_overlay_reproduces_the_published_figure(tmp_path):
    """media/overlay_diode_1n4148.png was drawn with the calibration's own
    zero; a given zero of -0.0873765 mA draws the same points and residuals."""
    import numpy as np

    published, _ = _overlay(tmp_path)
    data, texts = _overlay(tmp_path, "--zero", str(ZERO_11_08))
    assert len(data) == len(published)
    for a, b in zip(data, published):
        np.testing.assert_allclose(a, b, atol=1e-9)
    assert any("rms 0.51 mV over the 60 fitted points" in t for t in texts)
    assert any("zero -0.0874 mA subtracted (given: command line)" in t for t in texts)


@pytest.mark.skipif(__import__("shutil").which("ngspice") is None,
                    reason="ngspice not installed")
def test_simulate_records_the_capture_s_corrections(tmp_path):
    out = tmp_path / "sim.csv"
    assert main(["simulate", str(H4 / "mvp_17_diode.lib"), "--like", str(DIODE_11_08),
                 "--zero", str(ZERO_11_08), "-o", str(out)]) == 0
    head = out.read_text()
    assert "# like_zero: zero -0.0874 mA subtracted (given: command line)" in head
    assert "# like_r_parallel: R_p = 201.31" in head
