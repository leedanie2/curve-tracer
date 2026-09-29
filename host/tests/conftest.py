"""Shared fixtures. Everything runs against the compiled simulator.

No test in this suite touches a serial port or needs an instrument. The
simulator is the real firmware -- ``firmware/core/`` built for the host with a
modelled DUT behind ``ct_device_t`` -- so these tests exercise the same sweep
engine and CSV writer that runs on the board.

Sweeps are session-scoped and cached: the simulator is fast, but a few dozen
tests each running a 300-point family is still worth doing once.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ct_host.protocol import SweepRequest, run_sweep          # noqa: E402
from ct_host.recompute import recompute                        # noqa: E402
from ct_host.transport import SimTransport, default_sim_path   # noqa: E402

#: The device the closed-loop tests feed the simulator and then try to recover.
KNOWN_MOSFET = {"vth": 2.15, "k": 0.055, "lam": 0.012}
KNOWN_DIODE = {"is_": 2.5e-9, "n_diode": 1.75, "rs": 0.6}


def pytest_configure(config):
    import matplotlib
    matplotlib.use("Agg")          # no display in CI or over ssh


@pytest.fixture(scope="session", autouse=True)
def _require_simulator():
    path = default_sim_path()
    if not path.exists():
        pytest.skip(f"{path} not built; run `make -C firmware` first",
                    allow_module_level=True)


def run(request: SweepRequest, **sim_kwargs):
    """Run one sweep against a fresh simulator process."""
    with SimTransport(**sim_kwargs) as transport:
        return run_sweep(transport, request)


@pytest.fixture(scope="session")
def mosfet_sweep():
    """A six-step family from a device with known parameters."""
    return run(
        SweepRequest(device="sim-mosfet", n=60, vds_max=10, i_limit_ma=165,
                     vgs_list=[2.6, 2.8, 3.0, 3.2, 3.4, 3.6]),
        dut="mosfet", **KNOWN_MOSFET,
    )


@pytest.fixture(scope="session")
def mosfet(mosfet_sweep):
    return recompute(mosfet_sweep)


@pytest.fixture(scope="session")
def noisy_mosfet_sweep():
    return run(
        SweepRequest(device="sim-mosfet", n=60, vds_max=10, i_limit_ma=165,
                     vgs_list=[2.6, 2.8, 3.0, 3.2, 3.4, 3.6]),
        dut="mosfet", noise=8, **KNOWN_MOSFET,
    )


@pytest.fixture(scope="session")
def subthreshold_sweep():
    """A family whose lower gate steps sit below V_th."""
    return run(
        SweepRequest(device="sim-mosfet", n=40, vds_max=10, i_limit_ma=165,
                     vgs_list=[1.0, 1.5, 1.8, 2.6, 2.9, 3.2, 3.5]),
        dut="mosfet", **KNOWN_MOSFET,
    )


@pytest.fixture(scope="session")
def diode_sweep():
    return run(
        SweepRequest(device="sim-diode", n=300, vds_max=3.0, i_limit_ma=165,
                     vgs_list=[0]),
        dut="diode", **KNOWN_DIODE,
    )


@pytest.fixture(scope="session")
def diode(diode_sweep):
    return recompute(diode_sweep)


@pytest.fixture(scope="session")
def ilimit_sweep():
    """A sweep that trips the firmware current limit, producing a flag."""
    return run(
        SweepRequest(device="sim-resistor", n=60, vds_max=10, i_limit_ma=25,
                     vgs_list=[0]),
        dut="resistor", rload=120.0,
    )
