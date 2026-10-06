"""The CSV contract, exercised the way the Python host will consume it.

The C tests check the firmware produces what it intends to. This one checks
that a naive Python reader — the host that has not been written yet — can
parse the result without special cases. If this file needs a workaround, the
format is wrong, not the parser.

    make -C firmware            # builds build/ct_sim
    pytest firmware/tests/test_csv_contract.py
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

SIM = Path(__file__).resolve().parent.parent / "build" / "ct_sim"

EXPECTED_COLUMNS = [
    "point", "vgs_set_v", "vds_set_v", "vds_meas_v",
    "i_meas_ma", "i_acc", "v_acc", "range", "flags",
]


def run(commands: str, *args: str) -> str:
    if not SIM.exists():
        pytest.skip(f"{SIM} not built; run `make -C firmware` first")
    out = subprocess.run(
        [str(SIM), *args],
        input=commands,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert out.returncode == 0, out.stderr
    return out.stdout


def parse(text: str):
    """Split a transcript into (metadata, rows) exactly as a host would."""
    meta: dict[str, str] = {}
    rows: list[dict[str, str]] = []
    columns: list[str] | None = None

    for raw in text.splitlines():
        line = raw.rstrip("\r")
        if not line:
            continue
        if line.startswith("#"):
            body = line[1:].strip()
            if ":" in body:
                key, _, value = body.partition(":")
                meta[key.strip()] = value.strip()
            continue
        if line.startswith("!"):
            continue
        fields = line.split(",")
        if columns is None:
            columns = fields
            continue
        assert len(fields) == len(columns), f"ragged row: {line!r}"
        rows.append(dict(zip(columns, fields)))

    return meta, columns, rows


def test_columns_match_declaration():
    meta, columns, _ = parse(run("SET n 5\nSWEEP\n"))
    assert columns == EXPECTED_COLUMNS
    # The header also declares them, so a host can validate before parsing.
    assert meta["columns"].split(",") == EXPECTED_COLUMNS


def test_metadata_fields_present():
    text = run("SET device 2N7000\nSET date 2026-09-28T14:03:11Z\n"
               "SET n 5\nSWEEP\n")
    meta, _, _ = parse(text)

    for key in ("schema", "fw", "board", "device", "date", "date_src",
                "range", "mode", "temp_c", "temp_src", "settle_us", "n",
                "oversample_n", "i_limit_ma", "vds_max", "vgs_list", "end",
                "cal_rdiv_ohm", "cal_r_iso_ohm", "cal_r_ptc_ohm"):
        assert key in meta, f"missing metadata: {key}"

    # Schema 2: i_meas_ma is DUT current, the Kelvin divider's share removed.
    assert meta["schema"] == "2"
    # Never measured on any board yet, so it must not look like a number.
    assert meta["cal_r_ptc_ohm"] == "unset"

    assert meta["device"] == "2N7000"
    assert meta["date"] == "2026-09-28T14:03:11Z"
    assert meta["date_src"] == "host"
    assert meta["mode"] == "dc"
    assert meta["range"] == "1"
    assert meta["end"] == "ok"


def test_temperature_is_labelled_as_die_not_dut():
    meta, _, _ = parse(run("SET n 3\nSWEEP\n"))
    # A host must be able to tell this is not a DUT measurement.
    assert meta["temp_src"] == "mcu_die"


def test_unset_date_is_not_fabricated():
    meta, _, _ = parse(run("SET n 3\nSWEEP\n"))
    assert meta["date"] == "unset"
    assert meta["date_src"] == "none"


def test_every_numeric_field_parses():
    _, _, rows = parse(run("SET n 20\nSET vgs_list 2.5,3.0\nSWEEP\n"))
    assert len(rows) == 40

    for row in rows:
        int(row["point"])
        int(row["i_acc"])
        int(row["v_acc"])
        int(row["range"])
        for key in ("vgs_set_v", "vds_set_v", "vds_meas_v", "i_meas_ma"):
            # float() is locale-independent in Python, but a ',' decimal
            # separator would already have broken the field split above.
            float(row[key])


def test_row_count_matches_declared_parameters():
    text = run("SET n 7\nSET vgs_list 1,2,3\nSWEEP\n")
    meta, _, rows = parse(text)
    assert len(rows) == int(meta["n"]) * len(meta["vgs_list"].split(","))


def test_ramp_spans_zero_to_vds_max():
    meta, _, rows = parse(run("SET n 11\nSET vds_max 10\n"
                              "SET vgs_list 0\nSWEEP\n"))
    vds = [float(r["vds_set_v"]) for r in rows]
    assert vds[0] == 0.0
    # Last point lands on vds_max to within one DAC step (2.7 mV).
    assert abs(vds[-1] - float(meta["vds_max"])) < 0.005
    assert vds == sorted(vds), "drain ramp must be monotonic"


def test_current_limit_row_is_flagged_and_last():
    text = run("SET n 40\nSET vgs_list 4.0\nSET vds_max 10\n"
               "SET i_limit_ma 25\nSWEEP\n")
    meta, _, rows = parse(text)

    assert meta["end"] == "ilimit"

    flagged = [r for r in rows if r["flags"]]
    assert len(flagged) == 1, "exactly one row should carry a flag"
    assert flagged[0] is rows[-1], "the flagged row must be the last one"
    assert flagged[0]["flags"] == "ilimit"

    # The limit actually fired, i.e. the flagged reading is over the ceiling.
    assert float(flagged[0]["i_meas_ma"]) > float(meta["i_limit_ma"])

    # And every preceding row is a valid point, under the ceiling.
    for row in rows[:-1]:
        assert row["flags"] == ""
        assert float(row["i_meas_ma"]) <= float(meta["i_limit_ma"])


def test_flagged_rows_are_excludable_by_the_documented_rule():
    """A host filtering on `flags == ""` keeps only valid measurements."""
    text = run("SET n 40\nSET vgs_list 4.0\nSET vds_max 10\n"
               "SET i_limit_ma 25\nSWEEP\n")
    meta, _, rows = parse(text)
    valid = [r for r in rows if not r["flags"]]
    assert len(valid) == len(rows) - 1
    assert all(float(r["i_meas_ma"]) <= float(meta["i_limit_ma"]) for r in valid)


def test_vds_delta_is_the_series_drop_not_noise():
    """vds_set_v - vds_meas_v must be a monotonic function of current.

    This is the property README.md documents: the delta is R_iso plus shunt
    burden, so it grows with current rather than scattering about zero.
    """
    _, _, rows = parse(run("SET n 25\nSET vgs_list 4.0\nSET vds_max 8\n"
                           "SET i_limit_ma 165\nSWEEP\n"))
    pairs = [
        (float(r["i_meas_ma"]), float(r["vds_set_v"]) - float(r["vds_meas_v"]))
        for r in rows
    ]
    pairs = [(i, d) for i, d in pairs if i > 1.0]
    assert len(pairs) > 5

    # Delta is always positive: the DUT can never see more than commanded.
    assert all(d > 0 for _, d in pairs), pairs

    # And it tracks current at ~23 ohm (R_iso 22 + shunt 1).
    for current_ma, delta_v in pairs:
        expected = (current_ma / 1000.0) * 23.0
        assert abs(delta_v - expected) < 0.05, (current_ma, delta_v, expected)


def test_diode_model_is_monotonic():
    """Monotonic to within one LSB.

    Below an LSB the shunt reading quantises to zero, and the firmware still
    subtracts the Kelvin divider's exact V_DS / 400k (schema 2, blueprint
    §3.4), so a diode that has not turned on reads a few uA *negative* in a
    noise-free simulation. On the board ADC noise dithers that away on
    average. It is never more than one LSB (~40 uA on range 1).
    """
    meta, _, rows = parse(run("SET n 30\nSET vds_max 1.0\nSWEEP\n", "--dut", "diode"))
    lsb_ma = (float(meta["cal_vref"]) / float(meta["cal_adc_full_scale"])
              / (float(meta["cal_diffamp_gain"]) * float(meta["cal_shunt_ohm"])) * 1000.0)
    currents = [float(r["i_meas_ma"]) for r in rows]
    assert all(b >= a - lsb_ma for a, b in zip(currents, currents[1:]))
    assert min(currents) > -lsb_ma
    assert currents[-1] > currents[0]


def test_command_errors_use_the_bang_prefix():
    text = run("SET n 0\nSET nosuch 1\nBOGUS\n")
    errors = [l for l in text.splitlines() if l.startswith("!")]
    assert len(errors) == 3
    # An error must never look like a data row.
    for line in errors:
        assert "," not in line.split(":")[0]


def test_blank_lines_produce_no_output():
    assert run("\n\n\n").strip() == ""


def test_large_sweep_is_not_truncated():
    """A full-size family must survive intact.

    The simulator used to stage output in a fixed 64 KB buffer flushed once
    per input line, so a sweep this size overran it: the transcript lost its
    `# end:` marker and the final row was cut mid-field. It streams now, so
    there is no buffer to overflow.
    """
    text = run("SET n 200\nSET vgs_list 2.5,3,3.5,4,4.5,5,5.5,6\n"
               "SET vds_max 10\nSET i_limit_ma 165\nSWEEP\n")
    meta, columns, rows = parse(text)

    assert meta.get("end") == "ok", "no end marker: transcript was truncated"
    assert len(rows) == 200 * 8
    assert columns == EXPECTED_COLUMNS
    # A cut row would show up as a short field count or an unparseable number.
    assert [int(r["point"]) for r in rows] == list(range(200 * 8))
    for row in rows:
        float(row["i_meas_ma"])
        int(row["i_acc"])


def test_output_streams_rather_than_arriving_as_one_block():
    """Rows must reach the host as they are produced, not all at the end.

    This is what lets the live plot be developed against the simulator with
    no board attached; buffering a whole sweep would leave that path
    untestable. Asserted by reading the first row before the sweep finishes.
    """
    if not SIM.exists():
        pytest.skip(f"{SIM} not built; run `make -C firmware` first")

    proc = subprocess.Popen(
        [str(SIM)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1,
    )
    try:
        proc.stdin.write("SET n 400\nSET vgs_list 2.5,3,3.5,4\n"
                         "SET i_limit_ma 165\nSWEEP\n")
        proc.stdin.flush()

        seen = 0
        first_row_seen_before_end = False
        for line in proc.stdout:
            if line.startswith("# end"):
                break
            if not line.startswith(("#", "!")) and "," in line:
                seen += 1
                if seen == 2:           # 1 is the column header
                    first_row_seen_before_end = True
        assert first_row_seen_before_end, "no row arrived before the end marker"
        assert seen == 400 * 4 + 1
    finally:
        proc.stdin.close()
        proc.wait(timeout=60)


def test_noise_does_not_break_the_format():
    """With ADC noise on, the format must still parse exactly."""
    _, columns, rows = parse(
        run("SET n 20\nSET vgs_list 3.0\nSWEEP\n", "--noise", "12")
    )
    assert columns == EXPECTED_COLUMNS
    assert len(rows) == 20
    for row in rows:
        float(row["i_meas_ma"])
        int(row["i_acc"])
