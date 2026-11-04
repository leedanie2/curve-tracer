"""The desk pipeline: .model card -> ngspice -> overlay, on simulator data.

Each step is one command. The tests run them in order on a ct_sim capture
with R_p beside the device, as MVP card section D takes it, and check that
the simulated curve reproduces the measured one and that nothing in the
output can pass for a bench measurement. They need ngspice on PATH.
"""

from __future__ import annotations

import math
import shutil

import numpy as np
import pytest

from conftest import KNOWN_DIODE
from ct_host.cli import main
from ct_host.overlay import read_card, read_sim

pytestmark = pytest.mark.skipif(shutil.which("ngspice") is None,
                                reason="ngspice not installed")


@pytest.fixture(scope="module")
def diode_files(tmp_path_factory):
    d = tmp_path_factory.mktemp("pipe")
    rp, cap = d / "rp.csv", d / "d.csv"
    lib, sim, png = d / "d.lib", d / "d_sim.csv", d / "d.png"
    assert main(["capture", "--sim", "resistor", "--sim-rload", "470",
                 "--sim-rptc", "8.4", "--vgs", "0", "--vds-max", "1.5",
                 "--n", "100", "--i-limit", "40", "-o", str(rp)]) == 0
    assert main(["capture", "--sim", "diode", "--sim-rpar", "470",
                 "--sim-rptc", "8.4", "--sim-noise", "2", "--vgs", "0",
                 "--vds-max", "1.5", "--n", "100", "--i-limit", "40",
                 "--device", "1N4148", "--r-parallel", str(rp), "-o", str(cap)]) == 0
    assert main(["model", str(cap), "--type", "diode", "--name", "DX",
                 "-o", str(lib)]) == 0
    assert main(["simulate", str(lib), "--like", str(cap), "-o", str(sim)]) == 0
    assert main(["overlay", str(cap), str(sim), "--save", str(png)]) == 0
    return {"cap": cap, "lib": lib, "sim": sim, "png": png}


def test_card_is_read_back(diode_files):
    card = read_card(diode_files["lib"])
    assert (card.name, card.kind) == ("DX", "diode")
    assert card.params["N"] == pytest.approx(KNOWN_DIODE["n_diode"], rel=0.01)
    assert "SIMULATED" in card.text


def test_ngspice_runs_the_card_as_written(diode_files):
    """The simulated current is the diode law with the card's own values."""
    card = read_card(diode_files["lib"])
    (_, v, i_ma), = read_sim(diode_files["sim"]).curves
    k = np.searchsorted(v, 0.5)
    is_, n = card.params["IS"], card.params["N"]
    expected = is_ * (math.exp(v[k] / (n * 0.025865)) - 1) * 1000
    assert i_ma[k] == pytest.approx(expected, rel=0.02)   # RS is negligible here


def test_simulated_output_says_it_is_a_simulation(diode_files):
    text = diode_files["sim"].read_text()
    assert text.startswith("# ct_host simulated I-V -- SIMULATION")
    assert "simulator: ngspice" in text and "like:" in text


def test_overlay_is_written_and_marked_simulated(diode_files):
    import matplotlib.pyplot as plt

    assert diode_files["png"].stat().st_size > 20_000
    assert "[SIMULATED]" in plt.gcf()._suptitle.get_text()


def test_simulated_curve_reproduces_the_capture(diode_files):
    """Measured (R_p subtracted) against simulated, at the fitted points."""
    from ct_host.csvio import parse
    from ct_host.parallel import from_meta, subtract
    from ct_host.recompute import recompute

    sweep = recompute(parse(diode_files["cap"].read_text()))
    sweep = subtract(sweep, from_meta(sweep))
    (_, v_sim, i_sim), = read_sim(diode_files["sim"]).curves
    rows = [r for r in sweep.valid_rows if r.i_ma > 0.2]
    v_model = np.interp(np.log([r.i_ma for r in rows]), np.log(np.clip(i_sim, 1e-12, None)),
                        v_sim)
    dv = np.array([r.v_dut for r in rows]) - v_model
    assert np.sqrt(np.mean(dv ** 2)) < 0.002          # under 2 mV rms


def test_mosfet_path_simulates_every_gate_step(tmp_path):
    cap, lib, sim, png = (tmp_path / n for n in ("m.csv", "m.lib", "m_sim.csv", "m.png"))
    assert main(["capture", "--sim", "mosfet", "--sim-rpar", "470",
                 "--vgs", "1.8,2.4,2.7,3.0", "--vds-max", "3", "--n", "40",
                 "--i-limit", "40", "--r-parallel", "470", "-o", str(cap)]) == 0
    assert main(["model", str(cap), "--type", "mosfet", "--name", "MX",
                 "-o", str(lib)]) == 0
    assert main(["simulate", str(lib), "--like", str(cap), "-o", str(sim)]) == 0
    curves = read_sim(sim).curves
    assert [round(g, 2) for g, _, _ in curves] == [1.8, 2.4, 2.7, 3.0]
    assert main(["overlay", str(cap), str(sim), "--save", str(png)]) == 0
