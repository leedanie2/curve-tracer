"""Parsing and saving, against the contract in firmware/README.md."""

from __future__ import annotations

import pytest

from ct_host.csvio import (
    EXPECTED_COLUMNS,
    ContractError,
    TruncatedTranscript,
    parse,
    parse_stream,
    save,
)
from ct_host.csvio import Row as CsvRow


def test_columns_match_the_contract(mosfet_sweep):
    assert mosfet_sweep.columns == EXPECTED_COLUMNS
    assert mosfet_sweep.meta["columns"].split(",") == list(EXPECTED_COLUMNS)


def test_metadata_is_complete(mosfet_sweep):
    for key in ("schema", "fw", "board", "device", "date", "date_src", "range",
                "mode", "temp_c", "temp_src", "settle_us", "n", "oversample_n",
                "i_limit_ma", "vds_max", "vgs_list", "cal_shunt_ohm",
                "cal_diffamp_gain", "cal_vdiv", "cal_vref"):
        assert key in mosfet_sweep.meta, f"missing {key}"
    assert mosfet_sweep.end_reason == "ok"
    assert mosfet_sweep.complete


def test_header_lines_are_kept_verbatim(mosfet_sweep):
    lines = mosfet_sweep.meta.lines
    assert lines[0].startswith("#")
    assert any(line.startswith("# cal_shunt_ohm:") for line in lines)


def test_missing_metadata_raises_rather_than_defaulting(mosfet_sweep):
    text = "\r\n".join(
        line for line in mosfet_sweep.raw_text.splitlines()
        if not line.startswith("# cal_vdiv:")
    ) + "\r\n"
    with pytest.raises(ContractError, match="cal_vdiv"):
        parse(text).meta.cal("vdiv")


def test_truncated_transcript_is_rejected(mosfet_sweep):
    text = "\r\n".join(
        line for line in mosfet_sweep.raw_text.splitlines()
        if not line.startswith("# end:")
    ) + "\r\n"
    sweep = parse(text)
    assert not sweep.complete
    with pytest.raises(TruncatedTranscript):
        sweep.require_complete()
    with pytest.raises(TruncatedTranscript):
        parse(text, require_end=True)


def test_ragged_row_is_rejected(mosfet_sweep):
    lines = mosfet_sweep.raw_text.splitlines()
    for idx, line in enumerate(lines):
        if line and not line.startswith(("#", "!")) and line[0].isdigit():
            lines[idx] = line.rsplit(",", 2)[0]     # a row cut mid-field
            break
    with pytest.raises(ContractError, match="ragged row"):
        parse("\r\n".join(lines) + "\r\n")


def test_wrong_column_header_is_rejected(mosfet_sweep):
    # Reorder the data column header, leaving the "# columns:" declaration
    # alone -- a host must not trust one because the other looked right.
    lines = mosfet_sweep.raw_text.splitlines()
    idx = next(k for k, line in enumerate(lines)
               if line.startswith("point,"))
    lines[idx] = lines[idx].replace("i_meas_ma,i_acc", "i_acc,i_meas_ma")
    with pytest.raises(ContractError, match="column header"):
        parse("\r\n".join(lines) + "\r\n")


def test_flagged_rows_are_parsed_and_marked(ilimit_sweep):
    assert ilimit_sweep.end_reason == "ilimit"
    flagged = ilimit_sweep.flagged_rows
    assert len(flagged) == 1
    assert flagged[0].flags == "ilimit"
    assert flagged[0] is ilimit_sweep.rows[-1]
    assert not flagged[0].valid
    assert all(r.valid for r in ilimit_sweep.rows[:-1])


def test_valid_rows_excludes_only_the_flagged_one(ilimit_sweep):
    assert (len(ilimit_sweep.valid_rows)
            == len(ilimit_sweep.rows) - len(ilimit_sweep.flagged_rows))


def test_error_lines_surface_rather_than_vanish():
    text = "! err: something went wrong\r\n"
    events = list(parse_stream(text.splitlines()))
    assert len(events) == 1
    assert events[0].text == "err: something went wrong"


def test_stream_yields_rows_before_the_end_marker(mosfet_sweep):
    seen_row_before_end = False
    for event in parse_stream(mosfet_sweep.raw_text.splitlines()):
        if isinstance(event, CsvRow):
            seen_row_before_end = True
            break
    assert seen_row_before_end


# --------------------------------------------------------------------------
# Saving
# --------------------------------------------------------------------------

def test_save_preserves_the_transcript_byte_for_byte(mosfet_sweep, tmp_path):
    out = save(mosfet_sweep, tmp_path / "a.csv", stamp_date=False)
    # Read raw: read_text() would translate CRLF to LF and hide a real
    # difference. The contract says CRLF, so check the bytes.
    written = out.read_bytes().decode("ascii")
    assert written == mosfet_sweep.raw_text
    assert written.endswith("# end: ok\r\n")


def test_saved_file_reparses_identically(mosfet_sweep, tmp_path):
    out = save(mosfet_sweep, tmp_path / "b.csv", stamp_date=False)
    again = parse(out.read_bytes().decode("ascii"), require_end=True)
    assert len(again.rows) == len(mosfet_sweep.rows)
    assert again.meta.as_dict() == mosfet_sweep.meta.as_dict()


def test_flagged_rows_stay_in_the_saved_file(ilimit_sweep, tmp_path):
    """Excluded from fits, kept in the archive -- they say where it ran away."""
    out = save(ilimit_sweep, tmp_path / "c.csv", stamp_date=False)
    again = parse(out.read_text())
    assert len(again.flagged_rows) == 1
    assert again.flagged_rows[0].flags == "ilimit"


def test_unset_date_is_stamped_without_touching_firmware_fields(
        mosfet_sweep, tmp_path):
    assert mosfet_sweep.meta["date"] == "unset"
    out = save(mosfet_sweep, tmp_path / "d.csv")
    again = parse(out.read_text())

    assert again.meta["date"] == "unset"            # untouched
    assert again.meta["date_src"] == "none"         # untouched
    assert again.meta["host_date_src"] == "host-save-time"
    assert again.meta["host_date"].endswith("Z")


def test_source_is_recorded_so_simulated_data_stays_identifiable(
        mosfet_sweep, tmp_path):
    """A device name can be overridden; the source cannot.

    Capturing from the simulator with --device 2N7000 would otherwise produce
    a file indistinguishable from a bench measurement.
    """
    out = save(mosfet_sweep, tmp_path / "e.csv", source="ct_sim --dut mosfet")
    again = parse(out.read_text())
    assert again.meta["host_source"].startswith("ct_sim")
    assert again.meta.is_simulated


def test_a_renamed_simulator_capture_is_still_flagged_as_simulated(tmp_path):
    from conftest import run
    from ct_host.protocol import SweepRequest

    sweep = run(SweepRequest(device="2N7000", n=10, vgs_list=[3.0]),
                dut="mosfet")
    assert sweep.meta.device == "2N7000"
    assert not sweep.meta.is_simulated              # nothing to go on yet

    out = save(sweep, tmp_path / "f.csv", source="ct_sim --dut mosfet")
    assert parse(out.read_text()).meta.is_simulated
