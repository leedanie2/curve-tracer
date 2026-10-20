"""How long things take on the instrument, including the serial link.

Speed claims for adaptive sampling are only honest if they count the link, so
this models it explicitly rather than charging a constant per point:

* a measurement is ``settle_us`` plus 128 conversions at 614 ADC cycles
  (601.5 sampling + 12.5 conversion) at 72 MHz -- firmware/README.md;
* every byte costs 10 bit times at 115200 baud;
* the firmware writes into a 4096-byte TX ring (``ct_hal_device.c``) that
  drains continuously and **blocks the sweep when full**. That is why a
  dense sweep's dwell per point changes partway through: the ring absorbs the
  header and the first ~100 rows, then the sweep runs at the link's pace;
* host -> MCU commands cost their own bytes plus a USB/VCP latency each way.
  The latency is an ASSUMPTION (1 ms) until it is measured at bring-up;
* host computation is real: the adaptive loop measures its own wall clock.

Times are seconds. ``Breakdown`` keeps the totals per category so a report
can say where the time went.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

__all__ = ["LinkModel", "Breakdown", "TxRing"]


@dataclass(frozen=True)
class LinkModel:
    baud: int = 115200
    bits_per_byte: int = 10
    ring_bytes: int = 4096
    #: one direction, ASSUMED until measured on the bench (plan B2)
    usb_latency_s: float = 1e-3
    adc_cycles: float = 614.0
    adc_clock_hz: float = 72e6
    conversions_per_point: int = 128

    @property
    def byte_s(self) -> float:
        return self.bits_per_byte / self.baud

    def measure_s(self, settle_us: int) -> float:
        return (settle_us * 1e-6
                + self.conversions_per_point * self.adc_cycles / self.adc_clock_hz)


@dataclass
class Breakdown:
    seconds: dict[str, float] = field(default_factory=lambda: defaultdict(float))

    def add(self, bucket: str, dt: float) -> None:
        self.seconds[bucket] += dt

    @property
    def total(self) -> float:
        return float(sum(self.seconds.values()))

    def as_dict(self) -> dict[str, float]:
        return dict(self.seconds)


class TxRing:
    """The firmware's transmit ring: fill level against a draining link."""

    def __init__(self, link: LinkModel) -> None:
        self.link = link
        self.fill = 0.0
        self.t = 0.0

    def drain_to(self, t: float) -> None:
        if t > self.t:
            self.fill = max(0.0, self.fill - (t - self.t) / self.link.byte_s)
            self.t = t

    def wait_for_room(self, t: float, nbytes: int) -> float:
        """Seconds the writer blocks at time ``t`` before ``nbytes`` fit."""
        self.drain_to(t)
        excess = self.fill + nbytes - self.link.ring_bytes
        return max(0.0, excess) * self.link.byte_s

    def push(self, t: float, nbytes: int) -> None:
        self.drain_to(t)
        self.fill += nbytes

    def empty_after(self, t: float) -> float:
        """Seconds from ``t`` until the last queued byte has left the MCU."""
        self.drain_to(t)
        return self.fill * self.link.byte_s
