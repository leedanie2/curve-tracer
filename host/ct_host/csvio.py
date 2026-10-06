"""Parsing and writing the instrument's CSV transcript.

The format is specified in ``firmware/README.md``. This module implements that
specification and nothing else: it does not guess at missing fields, repair
malformed ones, or normalise anything. A transcript that violates the contract
raises, because the alternative is an extraction quietly performed on repaired
data.

Framing, from the specification:

    '#'  metadata or informational
    '!'  error response
    else a CSV row

Parsing is written as a generator over lines so the same code serves a file
read and a live serial capture. ``parse()`` collects the events into a
``Sweep``; ``parse_stream()`` hands them over as they arrive.
"""

from __future__ import annotations

import datetime as _dt
import io
import os
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Iterable, Iterator

__all__ = [
    "Metadata", "Row", "Sweep", "MetaLine", "Columns", "Error", "End",
    "ContractError", "TruncatedTranscript",
    "parse", "parse_stream", "save",
]

#: Column order, as ``CT_CSV_COLUMNS`` in ``firmware/core/ct_csv.h``.
EXPECTED_COLUMNS = (
    "point", "vgs_set_v", "vds_set_v", "vds_meas_v",
    "i_meas_ma", "i_acc", "v_acc", "range", "flags",
)


class ContractError(ValueError):
    """The transcript violates the format in ``firmware/README.md``."""


class TruncatedTranscript(ContractError):
    """No ``# end:`` marker.

    firmware/README.md: "A transcript without an ``# end:`` line is truncated
    -- treat it as a failed capture, not a short sweep."
    """


# --------------------------------------------------------------------------
# Metadata
# --------------------------------------------------------------------------

class Metadata:
    """The ``#`` header, as parsed keys plus the verbatim lines.

    Both representations are kept. The parsed keys drive computation; the
    verbatim lines are what gets written back out, so a saved capture is
    byte-identical to what the instrument sent rather than a re-serialisation
    of this class's idea of it.
    """

    def __init__(self, items: Iterable[tuple[str, str]] = (),
                 lines: Iterable[str] = ()) -> None:
        self._d: dict[str, str] = dict(items)
        self._lines: list[str] = list(lines)

    # -- mapping-ish surface ------------------------------------------------

    def __getitem__(self, key: str) -> str:
        return self._d[key]

    def __contains__(self, key: str) -> bool:
        return key in self._d

    def __iter__(self) -> Iterator[str]:
        return iter(self._d)

    def __len__(self) -> int:
        return len(self._d)

    def __repr__(self) -> str:
        return f"Metadata({self._d!r})"

    def get(self, key: str, default: str | None = None) -> str | None:
        return self._d.get(key, default)

    def keys(self):
        return self._d.keys()

    def items(self):
        return self._d.items()

    def as_dict(self) -> dict[str, str]:
        return dict(self._d)

    @property
    def lines(self) -> tuple[str, ...]:
        """The header lines exactly as received, ``#`` included."""
        return tuple(self._lines)

    def _add_line(self, line: str) -> None:
        self._lines.append(line)

    # -- typed access -------------------------------------------------------

    def require(self, key: str) -> str:
        try:
            return self._d[key]
        except KeyError:
            raise ContractError(
                f"metadata field {key!r} is missing; "
                f"the firmware emits it unconditionally (firmware/README.md)"
            ) from None

    def float(self, key: str) -> float:
        raw = self.require(key)
        try:
            return _float(raw)
        except ValueError:
            raise ContractError(f"metadata {key}={raw!r} is not a number") from None

    def float_or_none(self, key: str) -> float | None:
        """A numeric field that may be absent or explicitly ``unset``.

        Older schemas lack some ``cal_*`` keys, and a constant that has not
        been measured yet is emitted as ``unset`` rather than as a number that
        looks real. Both come back as ``None``; anything else must parse.
        """
        raw = self._d.get(key)
        if raw is None or raw == "unset":
            return None
        try:
            return _float(raw)
        except ValueError:
            raise ContractError(f"metadata {key}={raw!r} is not a number") from None

    def int(self, key: str) -> int:
        raw = self.require(key)
        try:
            return _int(raw)
        except ValueError:
            raise ContractError(f"metadata {key}={raw!r} is not an integer") from None

    # -- the fields analysis actually needs ---------------------------------

    @property
    def oversample_n(self) -> int:
        return self.int("oversample_n")

    @property
    def n(self) -> int:
        return self.int("n")

    @property
    def device(self) -> str:
        return self.get("device", "unknown") or "unknown"

    @property
    def end(self) -> str | None:
        return self.get("end")

    @property
    def vgs_list(self) -> tuple[float, ...]:
        raw = self.require("vgs_list")
        return tuple(_float(v) for v in raw.split(",") if v != "")

    @property
    def is_simulated(self) -> bool:
        """True when the transcript came from ``ct_sim`` rather than hardware.

        Two independent signals, because either alone can be defeated. The
        simulator names the part ``sim-mosfet`` / ``sim-diode`` /
        ``sim-resistor`` so an archived CSV is self-identifying -- but a
        capture run with ``--device 2N7000`` overwrites that name and the
        transcript then looks exactly like a bench measurement. So the host
        also records the transport it captured through, as ``host_source``,
        which no device name can mask.
        """
        if self.device.startswith("sim-"):
            return True
        source = self.get("host_source", "")
        return bool(source) and source.startswith("ct_sim")

    def cal(self, name: str) -> float:
        """A ``cal_*`` constant, by its short name (``shunt_ohm``, ...)."""
        return self.float(name if name.startswith("cal_") else f"cal_{name}")


def _float(s: str) -> float:
    return float(s)


def _int(s: str) -> int:
    return int(s)


# --------------------------------------------------------------------------
# Rows
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Row:
    """One measurement point.

    ``i_recomp_ma`` and ``v_recomp_v`` are filled by :mod:`ct_host.recompute`
    from the raw accumulators. They are ``None`` on a freshly parsed row, and
    they -- not the firmware's converted columns -- are what analysis uses.
    """

    point: int
    vgs_set_v: float
    vds_set_v: float
    vds_meas_v: float
    i_meas_ma: float
    i_acc: int
    v_acc: int
    range: int
    flags: str
    raw: str = ""
    i_recomp_ma: float | None = None
    v_recomp_v: float | None = None

    @property
    def valid(self) -> bool:
        """False for any flagged row.

        firmware/README.md: "Any row with a non-empty ``flags`` field is not a
        valid measurement point." Flagged rows stay in the saved CSV -- they
        record where a device ran away -- but never enter a fit.
        """
        return self.flags == ""

    @property
    def i_ma(self) -> float:
        """Current for analysis: recomputed if available, else as reported."""
        return self.i_meas_ma if self.i_recomp_ma is None else self.i_recomp_ma

    @property
    def v_dut(self) -> float:
        """Measured DUT voltage for analysis. Never ``vds_set_v``."""
        return self.vds_meas_v if self.v_recomp_v is None else self.v_recomp_v

    @property
    def vds_delta(self) -> float:
        """``vds_set_v - vds_meas_v``; should be I x (23 ohm + R_PTC). See §3.1."""
        return self.vds_set_v - self.vds_meas_v


# --------------------------------------------------------------------------
# Stream events
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class MetaLine:
    key: str
    value: str
    raw: str


@dataclass(frozen=True)
class Columns:
    names: tuple[str, ...]
    raw: str


@dataclass(frozen=True)
class Error:
    """An ``!`` line. Shares the link with data; never silently dropped."""
    text: str


@dataclass(frozen=True)
class End:
    reason: str


Event = MetaLine | Columns | Row | Error | End


def parse_stream(lines: Iterable[str], *, strict: bool = True) -> Iterator[Event]:
    """Yield events as lines arrive.

    Drives both the live plot and :func:`parse`. Rows are yielded the moment
    they are read, so a consumer sees them at the rate the instrument
    produces them.
    """
    columns: tuple[str, ...] | None = None

    for raw_line in lines:
        line = raw_line.rstrip("\r\n")
        if line == "":
            continue

        if line.startswith("#"):
            body = line[1:].strip()
            if ":" in body:
                key, _, value = body.partition(":")
                key, value = key.strip(), value.strip()
                if key == "end":
                    yield End(value)
                else:
                    yield MetaLine(key, value, line)
            continue

        if line.startswith("!"):
            yield Error(line[1:].strip())
            continue

        fields = line.split(",")

        if columns is None:
            columns = tuple(fields)
            if strict and columns != EXPECTED_COLUMNS:
                raise ContractError(
                    f"column header does not match the contract\n"
                    f"  expected: {','.join(EXPECTED_COLUMNS)}\n"
                    f"  received: {','.join(columns)}"
                )
            yield Columns(columns, line)
            continue

        if len(fields) != len(columns):
            raise ContractError(
                f"ragged row: {len(fields)} fields, expected {len(columns)}\n"
                f"  {line!r}\n"
                f"  a row cut mid-field means a truncated capture"
            )

        yield _row_from(fields, columns, line)


def _row_from(fields: list[str], columns: tuple[str, ...], raw: str) -> Row:
    d = dict(zip(columns, fields))
    try:
        return Row(
            point=int(d["point"]),
            vgs_set_v=float(d["vgs_set_v"]),
            vds_set_v=float(d["vds_set_v"]),
            vds_meas_v=float(d["vds_meas_v"]),
            i_meas_ma=float(d["i_meas_ma"]),
            i_acc=int(d["i_acc"]),
            v_acc=int(d["v_acc"]),
            range=int(d["range"]),
            flags=d["flags"],
            raw=raw,
        )
    except (KeyError, ValueError) as exc:
        raise ContractError(f"unparseable row {raw!r}: {exc}") from None


# --------------------------------------------------------------------------
# Sweep
# --------------------------------------------------------------------------

@dataclass
class Sweep:
    """A complete transcript: header, rows, and the text they came from."""

    meta: Metadata
    rows: list[Row]
    columns: tuple[str, ...] = EXPECTED_COLUMNS
    errors: tuple[str, ...] = ()
    end_reason: str | None = None
    raw_text: str = ""
    #: True once recompute() has run and agreement has been checked.
    recomputed: bool = False
    _sources: dict[str, str] = field(default_factory=dict, repr=False)

    @property
    def complete(self) -> bool:
        return self.end_reason is not None

    @property
    def valid_rows(self) -> list[Row]:
        """Unflagged rows only -- the ones a fit may use."""
        return [r for r in self.rows if r.valid]

    @property
    def flagged_rows(self) -> list[Row]:
        return [r for r in self.rows if not r.valid]

    def require_complete(self) -> Sweep:
        if not self.complete:
            raise TruncatedTranscript(
                "transcript has no '# end:' marker -- it is a failed capture, "
                "not a short sweep (firmware/README.md)"
            )
        return self

    def with_rows(self, rows: list[Row]) -> Sweep:
        return replace(self, rows=rows)

    def describe(self) -> str:
        lines = [
            f"device      : {self.meta.device}"
            + ("   [SIMULATED]" if self.meta.is_simulated else ""),
            f"date        : {self.meta.get('date')} "
            f"(src {self.meta.get('date_src')})",
            f"range       : {self.meta.get('range')}    "
            f"mode: {self.meta.get('mode')}",
            f"rows        : {len(self.rows)}  "
            f"({len(self.valid_rows)} valid, {len(self.flagged_rows)} flagged)",
            f"gate steps  : {len(self.meta.vgs_list)}  {list(self.meta.vgs_list)}",
            f"end         : {self.end_reason}",
        ]
        if self.errors:
            lines.append(f"errors      : {len(self.errors)}")
        return "\n".join(lines)


def parse(text: str | Iterable[str], *, strict: bool = True,
          require_end: bool = False) -> Sweep:
    """Parse a whole transcript.

    ``require_end`` raises :class:`TruncatedTranscript` when the ``# end:``
    marker is absent. It is off here and on in the capture path, so reading a
    partial file for inspection stays possible while a capture that lost its
    tail is never silently analysed.
    """
    if isinstance(text, str):
        raw_text = text
        lines: Iterable[str] = text.splitlines()
    else:
        lines = list(text)
        raw_text = "".join(
            ln if ln.endswith("\n") else ln + "\n" for ln in lines
        )

    meta_items: list[tuple[str, str]] = []
    meta_lines: list[str] = []
    rows: list[Row] = []
    errors: list[str] = []
    columns = EXPECTED_COLUMNS
    end_reason: str | None = None

    for event in parse_stream(lines, strict=strict):
        if isinstance(event, MetaLine):
            meta_items.append((event.key, event.value))
            meta_lines.append(event.raw)
        elif isinstance(event, Columns):
            columns = event.names
        elif isinstance(event, Row):
            rows.append(event)
        elif isinstance(event, Error):
            errors.append(event.text)
        elif isinstance(event, End):
            end_reason = event.reason

    sweep = Sweep(
        meta=Metadata(meta_items, meta_lines),
        rows=rows,
        columns=columns,
        errors=tuple(errors),
        end_reason=end_reason,
        raw_text=raw_text,
    )
    if require_end:
        sweep.require_complete()
    return sweep


# --------------------------------------------------------------------------
# Saving
# --------------------------------------------------------------------------

def save(sweep: Sweep, path: str | os.PathLike[str], *,
         stamp_date: bool = True, source: str | None = None) -> Path:
    """Write the transcript out, header preserved verbatim.

    The bytes the instrument sent are written back unchanged -- header,
    flagged rows and all. Nothing is reformatted, reordered or recomputed,
    because the raw accumulators exist precisely so an archived capture can be
    re-derived later, and that only works if the archive is what arrived.

    ``stamp_date`` adds host-supplied provenance when the firmware reported
    ``date: unset`` (a Nucleo has no RTC time source). ``source`` records what
    the capture came through. Both are prefixed ``host_`` and inserted after
    the instrument's own header, so no firmware field is ever shadowed or
    rewritten.

    Recording the source matters for more than tidiness: a simulator capture
    taken with ``--device 2N7000`` carries a part name that looks like a bench
    measurement, and ``host_source`` is then the only thing separating a
    modelled curve from a real one.
    """
    path = Path(path)
    text = sweep.raw_text
    added: list[str] = []

    if stamp_date and sweep.meta.get("date") in (None, "unset"):
        now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        added.append(f"# host_date: {now}")
        added.append("# host_date_src: host-save-time")

    if source is not None and "host_source" not in sweep.meta:
        added.append(f"# host_source: {source}")

    if added:
        text = _insert_after_header(
            text, "".join(line + "\r\n" for line in added))

    path.write_text(text, newline="")
    return path


def _insert_after_header(text: str, block: str) -> str:
    """Insert after the last leading ``#`` line, before the column header."""
    out = io.StringIO()
    inserted = False
    for line in text.splitlines(keepends=True):
        if not inserted and not line.lstrip().startswith("#") and line.strip():
            out.write(block)
            inserted = True
        out.write(line)
    if not inserted:
        out.write(block)
    return out.getvalue()
