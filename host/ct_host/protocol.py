"""Driving a sweep: commands out, a transcript back.

The command set is in ``firmware/README.md``. Two properties of it shape this
module:

* Command responses and CSV rows share one link, distinguished only by the
  first character. So a reader cannot assume that what follows ``SWEEP`` is
  all data -- an ``!`` line may arrive mid-sweep and must surface, not vanish.
* Setters reject rather than clamp. ``SET i_limit_ma 500`` is an error and
  leaves the previous ceiling in place. This module therefore checks every
  ``SET`` acknowledgement instead of firing them off and hoping, because a
  silently-ignored current limit is a burnt device.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Sequence

from .csvio import (EXPECTED_COLUMNS, Columns, End, Error, MetaLine, Metadata,
                    Row, Sweep, parse_stream)
from .transport import Transport

__all__ = ["SweepRequest", "CommandError", "SweepAborted",
           "run_sweep", "identify", "get_params", "send_and_check"]


class CommandError(RuntimeError):
    """The instrument rejected a command."""


class SweepAborted(RuntimeError):
    """The sweep ended for a reason other than ``ok``."""

    def __init__(self, reason: str, sweep: Sweep) -> None:
        super().__init__(f"sweep ended with '{reason}'")
        self.reason = reason
        self.sweep = sweep


@dataclass
class SweepRequest:
    """Parameters for one sweep, as ``SET`` commands.

    Fields left ``None`` are not sent at all, so the firmware's own defaults
    stand. That keeps this class from quietly becoming a second, divergent
    copy of the default table in ``firmware/core/ct_config.h``.
    """

    device: str | None = None
    date: str | None = None
    vgs_list: Sequence[float] | None = None
    vds_max: float | None = None
    n: int | None = None
    oversample_n: int | None = None
    settle_us: int | None = None
    i_limit_ma: float | None = None
    extra: list[str] = field(default_factory=list)

    def commands(self) -> list[str]:
        out: list[str] = []
        if self.device is not None:
            out.append(f"SET device {self.device}")
        if self.date is not None:
            out.append(f"SET date {self.date}")
        if self.vgs_list is not None:
            joined = ",".join(_fmt(v) for v in self.vgs_list)
            out.append(f"SET vgs_list {joined}")
        if self.vds_max is not None:
            out.append(f"SET vds_max {_fmt(self.vds_max)}")
        if self.n is not None:
            out.append(f"SET n {int(self.n)}")
        if self.oversample_n is not None:
            out.append(f"SET oversample_n {int(self.oversample_n)}")
        if self.settle_us is not None:
            out.append(f"SET settle_us {int(self.settle_us)}")
        if self.i_limit_ma is not None:
            out.append(f"SET i_limit_ma {_fmt(self.i_limit_ma)}")
        out.extend(self.extra)
        return out


def _fmt(value: float) -> str:
    """Plain decimal, no exponent -- the firmware's parser rejects ``1e-3``."""
    text = f"{float(value):.6f}".rstrip("0").rstrip(".")
    return text or "0"


def send_and_check(transport: Transport, command: str, *,
                   timeout: float | None = 10.0) -> str:
    """Send one command and consume its single-line acknowledgement.

    Raises on an ``!`` reply rather than continuing, because the firmware
    leaves the old value in place on rejection -- carrying on would run the
    sweep at settings the caller never asked for.
    """
    transport.send(command)
    for line in transport.lines(timeout=timeout):
        if line.startswith("!"):
            raise CommandError(f"{command!r} rejected: {line[1:].strip()}")
        if line.startswith("#"):
            return line
        if line.strip() == "":
            continue
        raise CommandError(f"{command!r}: unexpected reply {line!r}")
    raise CommandError(f"{command!r}: no reply")


def run_sweep(
    transport: Transport,
    request: SweepRequest | None = None,
    *,
    on_row: Callable[[Row], None] | None = None,
    on_meta: Callable[[str, str], None] | None = None,
    timeout: float | None = 300.0,
    strict: bool = True,
    raise_on_abort: bool = False,
) -> Sweep:
    """Configure, run, and collect one sweep.

    ``on_row`` is called as each row arrives, which is what makes the live
    plot live. The returned :class:`Sweep` carries the transcript verbatim in
    ``raw_text`` so it can be archived exactly as received.

    A sweep that ends ``ilimit`` or ``stopped`` is returned, not discarded --
    the flagged row records where a device ran away, which is the information
    needed to choose a lower ceiling. Pass ``raise_on_abort`` to treat it as
    an error instead.
    """
    if request is not None:
        for command in request.commands():
            send_and_check(transport, command, timeout=timeout)

    transport.send("SWEEP")

    raw_lines: list[str] = []
    meta_items: list[tuple[str, str]] = []
    meta_lines: list[str] = []
    rows: list[Row] = []
    errors: list[str] = []
    columns = None
    end_reason: str | None = None

    def tapped() -> Iterable[str]:
        for line in transport.lines(timeout=timeout):
            raw_lines.append(line)
            yield line

    for event in parse_stream(tapped(), strict=strict):
        if isinstance(event, MetaLine):
            meta_items.append((event.key, event.value))
            meta_lines.append(event.raw)
            if on_meta is not None:
                on_meta(event.key, event.value)
        elif isinstance(event, Columns):
            columns = event.names
        elif isinstance(event, Row):
            rows.append(event)
            if on_row is not None:
                on_row(event)
        elif isinstance(event, Error):
            errors.append(event.text)
        elif isinstance(event, End):
            end_reason = event.reason
            break

    sweep = Sweep(
        meta=Metadata(meta_items, meta_lines),
        rows=rows,
        columns=columns if columns is not None else EXPECTED_COLUMNS,
        errors=tuple(errors),
        end_reason=end_reason,
        raw_text="".join(line + "\r\n" for line in raw_lines),
    )

    if end_reason is None:
        sweep.require_complete()
    if raise_on_abort and end_reason != "ok":
        raise SweepAborted(end_reason, sweep)
    return sweep


def identify(transport: Transport, *, timeout: float | None = 10.0) -> dict[str, str]:
    """``ID`` -- firmware version, board, schema."""
    return _collect_hashes(transport, "ID", timeout=timeout)


def get_params(transport: Transport, *,
               timeout: float | None = 10.0) -> dict[str, str]:
    """``GET`` -- every parameter, one per line."""
    return _collect_hashes(transport, "GET", timeout=timeout)


def _collect_hashes(transport: Transport, command: str, *,
                    timeout: float | None) -> dict[str, str]:
    """Read ``#`` lines until the stream goes quiet.

    Neither ID nor GET has a terminator in the protocol, so the end of the
    block is found by sending a follow-up command whose acknowledgement is
    unmistakable and reading up to it. That avoids guessing a line count that
    would break the moment a parameter is added.
    """
    transport.send(command)
    transport.send("SET range 1")      # always rejected: a known sentinel

    out: dict[str, str] = {}
    for line in transport.lines(timeout=timeout):
        if line.startswith("!"):
            break                      # the sentinel's rejection
        if line.startswith("#"):
            body = line[1:].strip()
            if ":" in body:
                key, _, value = body.partition(":")
                out[key.strip()] = value.strip()
    return out
