"""``model`` takes the MOSFET fit window that ``extract`` takes.

Board 2's 2N7000 (2026-11-08, section (e)) is in moderate inversion below
about 2.5 V, so a Level-1 square law fits only the top gate steps and a card
fitted over every step is unsound. These tests check that ``model`` honours
``--vds-slice``, ``--vgs-range`` and ``--saturation-margin`` exactly as
``extract`` does, that the card states the window it was fitted over, read
from the fit, and that it warns when that window is too thin to test the
square law. Lambda follows the same window, so LAMBDA and the de-embedded
KP describe the steps VTO does, and so does the V_th spread over fit-range
choices.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from conftest import KNOWN_MOSFET
from ct_host.cli import main
from ct_host.extract import extract_mosfet

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


def test_lambda_follows_the_window(mosfet):
    windowed = extract_mosfet(mosfet, vgs_range=(2.7, 3.5))
    assert windowed.lambda_fits
    assert all(2.7 <= vgs <= 3.5 for vgs in windowed.lambda_fits)
    assert windowed.lambda_.value == pytest.approx(KNOWN_MOSFET["lam"], rel=0.05)
    # The de-embedding uses the window's lambda.
    assert windowed.deembed_factor == pytest.approx(
        1 + windowed.lambda_.value * windowed.vds_slice, rel=1e-9)

    # Without a range, every step with enough saturation points, as before.
    default = extract_mosfet(mosfet)
    assert len(default.lambda_fits) > len(windowed.lambda_fits)
    assert max(default.lambda_fits) > 3.5


def test_card_states_lambda_steps_and_r_ds_on_against_the_window(sim_csv, capsys):
    card = _model(capsys, sim_csv, "--vgs-range", "2.7", "3.5")
    assert re.search(r"lambda .*from 4 gate steps, V_GS 2\.\d+\.\.3\.\d+ V", card)
    # R_DS(on) comes from the top step, 3.6 V, which the window excludes.
    assert re.search(r"from V_GS = 3\.\d+ V, outside the fit window", card)
    assert "R_DS" not in card.split(".model", 1)[1]

    default = _model(capsys, sim_csv)
    assert "from 6 gate steps" in default
    assert "outside the fit window" not in default


def test_sensitivity_follows_the_window(mosfet):
    windowed = extract_mosfet(mosfet, vgs_range=(2.7, 3.5)).sensitivity
    table = windowed.table
    assert windowed.vgs_range == (2.7, 3.5)
    assert (table["vgs_lo"] >= 2.7).all() and (table["vgs_hi"] <= 3.5).all()
    # Four steps: keep all, drop the lowest, or drop the highest.
    assert set(table["n_points"]) == {3, 4}

    default = extract_mosfet(mosfet).sensitivity
    assert default.vgs_range is None
    assert default.table["vgs_hi"].max() > 3.5
    assert default.n_choices > windowed.n_choices


def test_card_says_where_the_spread_came_from(sim_csv, capsys):
    card = _model(capsys, sim_csv, "--vgs-range", "2.7", "3.5")
    assert ("choices drawn only from the gate steps in the V_GS range "
            "2.700..3.500 V") in card
    assert "choices drawn only" not in _model(capsys, sim_csv)


def test_capture_names_the_row_that_tripped(tmp_path, capsys):
    out = tmp_path / "trip.csv"
    capsys.readouterr()
    assert main(["capture", "--sim", "mosfet", "--vgs", "2.6,3.0,3.6",
                 "--n", "40", "--i-limit", "40", "-o", str(out)]) == 0
    err = capsys.readouterr().err
    assert "sweep ended 'ilimit'" in err
    m = re.search(r"flagged: V_GS ([\d.]+) V, V_DS ([\d.]+) V, ([\d.]+) mA", err)
    assert m, err
    assert float(m[3]) > 40.0


def test_card_says_v_gs_is_commanded(sim_csv, capsys):
    card = _model(capsys, sim_csv)
    assert "V_GS       : commanded (vgs_set_v), not read back" in card
    assert "gate DAC's" in card and "accuracy is unmeasured" in card


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
    (201.31 ohm, zero -0.0874 mA) subtracted. KP was 0.17521 while lambda
    came from every step (0.0301 /V); with lambda from the window it is
    0.17557. V_th and R^2 don't depend on lambda.
    """
    capsys.readouterr()
    assert main(["extract", str(MOSFET_11_08), "--type", "mosfet",
                 *WINDOW_11_08]) == 0
    printed = capsys.readouterr().out
    vth = float(re.search(r"V_th   = ([\d.]+)", printed)[1])
    kp = float(re.search(r"KP\*W/L = ([\d.]+)", printed)[1])
    assert vth == pytest.approx(2.1496, abs=5e-5)
    assert kp == pytest.approx(0.17557, abs=5e-6)
    assert "R^2 = 0.999362" in printed
    assert "3 of 13 points over 2.499 .. 2.7 V" in printed

    card = _model(capsys, MOSFET_11_08, *WINDOW_11_08)
    assert _value(card, "VTO") == pytest.approx(vth, abs=5e-5)
    assert _value(card, "KP") == pytest.approx(kp, abs=5e-6)
    assert "V_GS 2.499..2.700 V" in _valid_for(card)
    assert "3 points fitted, at V_DS = 1.500 V" in _valid_for(card)
    assert _value(card, "LAMBDA") == pytest.approx(0.02867, abs=5e-6)
    assert "from 3 gate steps, V_GS 2.499..2.700 V" in card
    assert "from V_GS = 2.801 V, outside the fit window" in card
    # Three steps leave no step to drop, so only the slice varies: 5 choices.
    assert "V_th spread over 5 fit-range choices: 1.04 mV" in card
    assert "choices drawn only from the gate steps" in card
    assert "WARNING: the V_th fit has 1 degree of freedom" in card
    assert "* R_p        : R_p = 201.31" in card
