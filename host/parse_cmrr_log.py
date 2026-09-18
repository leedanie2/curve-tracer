#!/usr/bin/env python3
"""Parse CMRR values out of an LTspice .log and summarise the Monte Carlo spread.

Usage: python3 host/parse_cmrr_log.py sim/05_diffamp_mc.log

Reads the "Measurement: cmrr" block, prints n/min/p5/median/p95/max in dB, and
writes a histogram to media/cmrr_mc.png marking the worst-case corner from 04.
"""

import os
import re
import sys

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

WORST_CASE_DB = 74.42
OUT_PNG = os.path.join("media", "cmrr_mc.png")


def read_log(path):
    """LTspice writes utf-8 on some builds and utf-16 on others."""
    with open(path, "rb") as fh:
        raw = fh.read()
    for encoding in ("utf-8", "utf-16"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def parse_cmrr(text):
    """Collect the numbers under the 'Measurement: cmrr' heading.

    The block runs from that heading to the next 'Measurement:' or blank-line
    separated section. Rows look like:  1    7.620000e+01    1
    """
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(r"\s*Measurement:\s*cmrr\s*$", line, re.IGNORECASE):
            start = i + 1
            break
    if start is None:
        return np.array([])

    # A data row is "<step index> <value> [...]". Anchoring on the integer step
    # index skips the column header, whose formula text ("20*log10(20/abs(acm))")
    # would otherwise scan as numbers.
    row = re.compile(r"^\s*\d+\s+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\b")

    values = []
    for line in lines[start:]:
        if re.match(r"\s*Measurement:", line, re.IGNORECASE):
            break
        match = row.match(line)
        if match:
            values.append(float(match.group(1)))
        elif values:
            break

    return np.array(values, dtype=float)


def summarise(values):
    stats = {
        "n": len(values),
        "min": float(np.min(values)),
        "p5": float(np.percentile(values, 5)),
        "median": float(np.median(values)),
        "p95": float(np.percentile(values, 95)),
        "max": float(np.max(values)),
    }
    print(f"n      = {stats['n']}")
    for key in ("min", "p5", "median", "p95", "max"):
        print(f"{key:<6} = {stats[key]:.2f} dB")
    return stats


def plot(values):
    os.makedirs(os.path.dirname(OUT_PNG), exist_ok=True)

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    ax.hist(values, bins=40, color="#4878a8", edgecolor="white", linewidth=0.5)
    ax.axvline(
        WORST_CASE_DB,
        color="red",
        linestyle="--",
        linewidth=1.5,
        label="worst case",
    )
    ax.set_xlabel("CMRR (dB)")
    ax.set_ylabel("runs")
    ax.set_title(f"Difference amp CMRR, {len(values)}-run Monte Carlo (0.1% resistors)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=150)
    plt.close(fig)
    print(f"wrote {OUT_PNG}")


def main():
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <ltspice .log>", file=sys.stderr)
        return 2

    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"no such file: {path}", file=sys.stderr)
        return 1

    values = parse_cmrr(read_log(path))
    if values.size == 0:
        print(f"no 'Measurement: cmrr' values found in {path}", file=sys.stderr)
        return 1

    summarise(values)
    plot(values)
    return 0


if __name__ == "__main__":
    sys.exit(main())
