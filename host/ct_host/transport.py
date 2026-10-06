"""Where lines come from: a serial port, or the compiled simulator.

Both implementations present the same line-oriented interface, so every layer
above this one -- capture, live plot, extraction -- is identical whether an
instrument is attached or not. That is the point: the bench has been blocked
since the trainer fault of 2026-09-24 (``docs/characterization.md``), and the
host must be finishable regardless.

``SimTransport`` runs ``firmware/build/ct_sim``, which speaks the real
protocol because it *is* the real firmware -- ``firmware/core/`` compiled for
the host with a modelled DUT behind ``ct_device_t``. It streams line by line,
so a live plot driven by it behaves as it will on the wire.
"""

from __future__ import annotations

import os
import queue
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Iterator, Protocol, runtime_checkable

__all__ = ["Transport", "SerialTransport", "SimTransport", "TransportError",
           "default_sim_path"]


class TransportError(RuntimeError):
    pass


@runtime_checkable
class Transport(Protocol):
    """A line-oriented link to the instrument."""

    def send(self, line: str) -> None:
        """Write one command line, terminating it."""

    def lines(self, timeout: float | None = None) -> Iterator[str]:
        """Yield received lines as they arrive, without their terminator."""

    def close(self) -> None:
        ...

    @property
    def description(self) -> str:
        """Human-readable source, recorded in capture provenance."""


def default_sim_path() -> Path:
    """``firmware/build/ct_sim``, located relative to this file."""
    return Path(__file__).resolve().parents[2] / "firmware" / "build" / "ct_sim"


class SimTransport:
    """The compiled simulator, driven over a pipe.

    Model parameters are passed through to ``ct_sim``'s own flags, so a test
    can hand the simulator a known device and check that extraction recovers
    it. That closed loop is what the extraction tests are built on.
    """

    def __init__(
        self,
        *,
        path: str | os.PathLike[str] | None = None,
        dut: str = "mosfet",
        noise: float | None = None,
        vth: float | None = None,
        k: float | None = None,
        lam: float | None = None,
        is_: float | None = None,
        n_diode: float | None = None,
        rs: float | None = None,
        rload: float | None = None,
        rptc: float | None = None,
        rdiv: float | None = None,
    ) -> None:
        self._path = Path(path) if path is not None else default_sim_path()
        if not self._path.exists():
            raise TransportError(
                f"simulator not built at {self._path}\n"
                f"  run: make -C {self._path.parents[1]}"
            )

        argv: list[str] = [str(self._path), "--dut", dut]
        for flag, value in (
            ("--noise", noise), ("--vth", vth), ("--k", k), ("--lambda", lam),
            ("--is", is_), ("--n-diode", n_diode), ("--rs", rs),
            ("--rload", rload), ("--rptc", rptc), ("--rdiv", rdiv),
        ):
            if value is not None:
                argv += [flag, repr(float(value))]

        self._argv = argv
        self._proc = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._closed = False

    @property
    def description(self) -> str:
        return "ct_sim " + " ".join(self._argv[1:])

    @property
    def argv(self) -> tuple[str, ...]:
        return tuple(self._argv)

    def send(self, line: str) -> None:
        if self._closed or self._proc.stdin is None:
            raise TransportError("transport is closed")
        self._proc.stdin.write(line.rstrip("\r\n") + "\n")
        self._proc.stdin.flush()

    def lines(self, timeout: float | None = None) -> Iterator[str]:
        """Yield stdout lines.

        ``timeout`` is not enforced per-line here: the simulator is a local
        process with no link to stall on, and imposing one would only invent
        failures that cannot happen. The serial implementation, where a stall
        is real, does enforce it.
        """
        assert self._proc.stdout is not None
        for line in self._proc.stdout:
            yield line.rstrip("\r\n")

    def end_input(self) -> None:
        """Close stdin so the simulator finishes and exits."""
        if self._proc.stdin is not None and not self._proc.stdin.closed:
            self._proc.stdin.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.end_input()
        try:
            self._proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait(timeout=5)
        for stream in (self._proc.stdout, self._proc.stderr):
            if stream is not None and not stream.closed:
                stream.close()

    def __enter__(self) -> SimTransport:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class SerialTransport:
    """A real instrument on a serial port, via pyserial.

    The Nucleo's port is the ST-LINK VCP wired to USART2 at 115200 8N1; there
    is no USB device stack on the board (firmware/README.md). Reading runs on
    a background thread into a queue so a live plot's redraw cannot stall the
    link and drop bytes.
    """

    def __init__(self, port: str, *, baudrate: int = 115200,
                 timeout: float = 1.0) -> None:
        try:
            import serial  # noqa: PLC0415  (optional dependency)
        except ImportError as exc:
            raise TransportError(
                "pyserial is not installed; it is only needed for a real "
                "instrument. pip install pyserial"
            ) from exc

        self._port_name = port
        self._baudrate = baudrate
        self._serial = serial.Serial(port, baudrate=baudrate, timeout=timeout)
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._stop = threading.Event()
        self._reader = threading.Thread(
            target=self._read_loop, name="ct-serial-reader", daemon=True
        )
        self._reader.start()

    @property
    def description(self) -> str:
        return f"serial {self._port_name} @ {self._baudrate}"

    def _read_loop(self) -> None:
        try:
            while not self._stop.is_set():
                raw = self._serial.readline()
                if raw:
                    self._queue.put(raw.decode("ascii", errors="replace")
                                    .rstrip("\r\n"))
        except Exception as exc:                # pragma: no cover - hardware
            self._queue.put(None)
            self._error = exc
        finally:
            self._queue.put(None)

    def send(self, line: str) -> None:
        self._serial.write((line.rstrip("\r\n") + "\r\n").encode("ascii"))
        self._serial.flush()

    def lines(self, timeout: float | None = 30.0) -> Iterator[str]:
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            remaining = None if deadline is None else deadline - time.monotonic()
            if remaining is not None and remaining <= 0:
                raise TransportError(
                    f"no line from {self._port_name} within {timeout} s"
                )
            try:
                item = self._queue.get(timeout=remaining)
            except queue.Empty:
                raise TransportError(
                    f"no line from {self._port_name} within {timeout} s"
                ) from None
            if item is None:
                return
            if deadline is not None:
                deadline = time.monotonic() + timeout
            yield item

    def close(self) -> None:
        self._stop.set()
        try:
            self._serial.close()
        finally:
            self._reader.join(timeout=2.0)

    def __enter__(self) -> SerialTransport:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def list_serial_ports() -> list[tuple[str, str]]:
    """``(device, description)`` for each port, or [] without pyserial."""
    try:
        from serial.tools import list_ports  # noqa: PLC0415
    except ImportError:
        return []
    return [(p.device, p.description) for p in list_ports.comports()]


def which_sim() -> Path | None:
    """The simulator binary, if it has been built."""
    path = default_sim_path()
    if path.exists():
        return path
    found = shutil.which("ct_sim")
    return Path(found) if found else None
