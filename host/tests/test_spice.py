"""SPICE .model card generation.

The card is the handoff to LTspice for the closed-loop validation in blueprint
§6, so two things matter beyond the numbers being right: the convention must
be SPICE's, and the card must carry enough provenance that it cannot be
mistaken for a bench-measured model six months later.
"""

from __future__ import annotations

import pytest

from conftest import KNOWN_DIODE, KNOWN_MOSFET
from ct_host.extract import extract_diode, extract_mosfet
from ct_host.spice import diode_model_card, mosfet_model_card


def _value(card: str, key: str) -> float:
    for line in card.splitlines():
        stripped = line.lstrip("+ ").strip()
        if stripped.startswith(f"{key} ") or stripped.startswith(f"{key}="):
            return float(stripped.split("=", 1)[1])
    raise AssertionError(f"{key} not found in card:\n{card}")


def test_card_uses_the_spice_convention_not_beta(mosfet):
    """KP must be 2*beta. Emitting beta would halve every simulated current."""
    params = extract_mosfet(mosfet)
    card = mosfet_model_card(params)

    assert _value(card, "KP") == pytest.approx(params.kp_wl.value, rel=1e-6)
    assert _value(card, "KP") == pytest.approx(2.0 * params.beta.value, rel=1e-6)
    assert _value(card, "KP") == pytest.approx(KNOWN_MOSFET["k"], rel=0.02)


def test_card_carries_the_extracted_values(mosfet):
    params = extract_mosfet(mosfet)
    card = mosfet_model_card(params, name="TESTFET")

    assert ".model TESTFET NMOS (" in card
    assert _value(card, "VTO") == pytest.approx(KNOWN_MOSFET["vth"], abs=0.005)
    assert _value(card, "LAMBDA") == pytest.approx(KNOWN_MOSFET["lam"], rel=0.05)
    assert _value(card, "LEVEL") == 1


def test_card_records_the_de_embedding(mosfet):
    card = mosfet_model_card(extract_mosfet(mosfet))
    assert "de-embedded" in card
    assert "lambda*" in card


def test_card_reports_both_uncertainties(mosfet):
    card = mosfet_model_card(extract_mosfet(mosfet))
    assert "V_th spread over" in card
    assert "fit stderr" in card
    assert "honest uncertainty" in card


def test_card_states_the_fit_range(mosfet):
    card = mosfet_model_card(extract_mosfet(mosfet))
    assert "fit range" in card
    assert "two-pass" in card


def test_simulated_data_is_marked_unmistakably(mosfet):
    card = mosfet_model_card(extract_mosfet(mosfet))
    assert "WARNING" in card
    assert "SIMULATED" in card
    assert "not from a bench measurement" in card


def test_source_is_recorded_when_given(mosfet):
    card = mosfet_model_card(extract_mosfet(mosfet), source="data/run.csv")
    assert "capture    : data/run.csv" in card


def test_unmeasured_subthreshold_is_stated_not_invented(mosfet):
    """Nothing is filled in from a datasheet. An absent measurement says so."""
    card = mosfet_model_card(extract_mosfet(mosfet))
    assert "subthresh. : not measured" in card
    # And no subthreshold parameter leaked into the model body.
    body = card.split(".model", 1)[1]
    assert "NFS" not in body


def test_diode_card(diode):
    params = extract_diode(diode)
    card = diode_model_card(params, name="TESTDIODE")

    assert ".model TESTDIODE D (" in card
    assert _value(card, "IS") == pytest.approx(KNOWN_DIODE["is_"], rel=0.15)
    assert _value(card, "N") == pytest.approx(KNOWN_DIODE["n_diode"], rel=0.02)
    assert _value(card, "RS") == pytest.approx(KNOWN_DIODE["rs"], rel=0.05)


def test_diode_card_omits_rs_when_unresolved():
    from conftest import run
    from ct_host.protocol import SweepRequest
    from ct_host.recompute import recompute

    sweep = run(SweepRequest(device="sim-diode", n=300, vds_max=3.0,
                             i_limit_ma=165, vgs_list=[0]),
                dut="diode", is_=1e-9, n_diode=1.9, rs=0.0)
    card = diode_model_card(extract_diode(recompute(sweep)))
    assert "RS" not in card.split(".model", 1)[1]


def test_card_is_valid_spice_syntax(mosfet, diode):
    for card in (mosfet_model_card(extract_mosfet(mosfet)),
                 diode_model_card(extract_diode(diode))):
        lines = [line for line in card.splitlines() if line.strip()]
        for line in lines:
            assert line.startswith(("*", ".model", "+")), line
        assert lines[-1].strip() == "+ )"
