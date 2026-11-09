"""``model`` takes the MOSFET fit window that ``extract`` takes.

Board 2's 2N7000 (2026-11-08, section (e)) is in moderate inversion below
about 2.5 V, so a Level-1 square law fits only the top gate steps and a card
fitted over every step is unsound. These tests check that ``model`` honours
``--vds-slice``, ``--vgs-range`` and ``--saturation-margin`` exactly as
``extract`` does, that the card states the window it was fitted over, read
from the fit, and that it warns when that window is too thin to test the
square law.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from conftest import KNOWN_MOSFET
from ct_host.cli import main

H4 = Path(__file__).resolve().parents[1] / "h4"
MOSFET_11_08 = H4 / "mvp_18_mosfet_rp.csv"
WINDOW_11_08 = ["--vds-slice", "1.5", "--vgs-range", "2.45", "2.75"]


def _value(card: str, key: str) -> float:
    for line in card.splitlines():
        stripped = line.lstrip("+ ").strip()
        if stripped.startswith(f"{key} ") or stripped.startswith(f"{key}="):
            return float(stripped.split("=", 1)[1])
    raise AssertionError(f"{key} not found in card:\n{card}")


def _valid_for(card: str) -> str:
    lines = [line for line in card.splitlines() if line.startswith("* valid for")]
    assert len(lines) == 1, card
    return lines[0]


@pytest.fixture(scope="module")
def sim_csv(tmp_path_factory):
    """A six-step simulated family from the known device."""
    out = tmp_path_factory.mktemp("window") / "cap.csv"
    assert main(["capture", "--sim", "mosfet",
                 "--sim-vth", str(KNOWN_MOSFET["vth"]),
                 "--sim-k", str(KNOWN_MOSFET["k"]),
                 "--sim-lambda", str(KNOWN_MOSFET["lam"]),
                 "--vgs", "2.6,2.8,3.0,3.2,3.4,3.6", "--n", "60",
                 "--vds-max", "10", "--i-limit", "165", "-o", str(out)]) == 0
    return out


def _model(capsys, csv, *extra) -> str:
    capsys.readouterr()
    assert main(["model", str(csv), "--type", "mosfet", *extra]) == 0
    return capsys.readouterr().out


# --------------------------------------------------------------------------
# Simulated family
# --------------------------------------------------------------------------

def test_model_with_a_window_recovers_the_known_device(sim_csv, capsys):
    card = _model(capsys, sim_csv, "--vgs-range", "2.7", "3.5")
    assert _value(card, "VTO") == pytest.approx(KNOWN_MOSFET["vth"], abs=0.005)
    assert _value(card, "KP") == pytest.approx(KNOWN_MOSFET["k"], rel=0.02)
    assert _value(card, "LAMBDA") == pytest.approx(KNOWN_MOSFET["lam"], rel=0.05)


def test_card_carries_the_window_and_what_it_fitted(sim_csv, capsys):
    card = _model(capsys, sim_csv, "--vgs-range", "2.7", "3.5")
    assert "caller-supplied V_GS range 2.700..3.500 V" in card

    # From the points fitted, not the arguments: 2.8..3.4 V, not 2.7..3.5.
    line = _valid_for(card)
    m = re.search(r"V_GS ([\d.]+)\.\.([\d.]+) V, I_D ([\d.]+)\.\.([\d.]+) mA "
                  r"\((\d+) points fitted", line)
    assert m, line
    assert float(m[1]) == pytest.approx(2.8, abs=0.01)
    assert float(m[2]) == pytest.approx(3.4, abs=0.01)
    assert m[5] == "4"

    # I_D at the slice, from the known device: K/2 (V_GS-V_th)^2 (1+lambda V_DS).
    vds = float(re.search(r"at V_DS = ([\d.]+) V", line)[1])
    k, vth, lam = KNOWN_MOSFET["k"], KNOWN_MOSFET["vth"], KNOWN_MOSFET["lam"]
    for vgs, i_ma in ((float(m[1]), float(m[3])), (float(m[2]), float(m[4]))):
        expected = k / 2 * (vgs - vth) ** 2 * (1 + lam * vds) * 1000
        assert i_ma == pytest.approx(expected, rel=0.03)

    assert "degree" not in card          # 4 points: 2 degrees of freedom


def test_window_options_change_the_card(sim_csv, capsys):
    """Each option reaches the fit: none is accepted and then ignored."""
    default = _model(capsys, sim_csv)
    assert "two-pass" in default
    assert "6 points fitted" in _valid_for(default)

    sliced = _model(capsys, sim_csv, "--vds-slice", "6")
    assert "at V_DS = 6.0" in _valid_for(sliced)

    margin = _model(capsys, sim_csv, "--saturation-margin", "0.9")
    assert "V_GS - V_th + 0.90 V" in margin


def test_a_three_step_window_warns_of_its_one_degree_of_freedom(sim_csv, capsys):
    card = _model(capsys, sim_csv, "--vgs-range", "2.9", "3.5")
    assert "3 points fitted" in _valid_for(card)
    assert "WARNING: the V_th fit has 1 degree of freedom" in card
    # A comment, not a parameter.
    assert "WARNING" not in card.split(".model", 1)[1]


# --------------------------------------------------------------------------
# Board 2's 2N7000, 2026-11-08
# --------------------------------------------------------------------------

def test_model_reproduces_extract_on_the_11_08_capture(capsys):
    """Same window, same numbers: model must not refit differently.

    The pinned values are the 11-08 extract with the header's R_p record
    (201.31 ohm, zero -0.0874 mA) subtracted.
    """
    capsys.readouterr()
    assert main(["extract", str(MOSFET_11_08), "--type", "mosfet",
                 *WINDOW_11_08]) == 0
    printed = capsys.readouterr().out
    vth = float(re.search(r"V_th   = ([\d.]+)", printed)[1])
    kp = float(re.search(r"KP\*W/L = ([\d.]+)", printed)[1])
    assert vth == pytest.approx(2.1496, abs=5e-5)
    assert kp == pytest.approx(0.17521, abs=5e-6)
    assert "R^2 = 0.999362" in printed
    assert "3 of 13 points over 2.499 .. 2.7 V" in printed

    card = _model(capsys, MOSFET_11_08, *WINDOW_11_08)
    assert _value(card, "VTO") == pytest.approx(vth, abs=5e-5)
    assert _value(card, "KP") == pytest.approx(kp, abs=5e-6)
    assert "V_GS 2.499..2.700 V" in _valid_for(card)
    assert "3 points fitted, at V_DS = 1.500 V" in _valid_for(card)
    assert "WARNING: the V_th fit has 1 degree of freedom" in card
    assert "* R_p        : R_p = 201.31" in card
