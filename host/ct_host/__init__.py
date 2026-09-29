"""Python host for the curve tracer.

The instrument's CSV output is the contract between this package and the
firmware; it is specified in ``firmware/README.md`` and implemented in
``firmware/core/ct_csv.c``. Nothing here may assume a field the firmware does
not emit, and nothing here may quietly repair one it emits badly.

Four functions, per blueprint §5:

1. capture   -- serial or simulator -> CSV file, header preserved verbatim
2. plot      -- the I-V family, live as it arrives
3. extract   -- MOSFET and diode parameters, with uncertainties
4. model     -- SPICE .model cards from those parameters

Everything runs against ``firmware/build/ct_sim`` with no instrument
attached; see ``host/README.md``.
"""

from .csvio import Metadata, Row, Sweep, parse, parse_stream, save
from .dataset import Curve, Family, family_of
from .extract import (
    DiodeParams,
    Estimate,
    FitRange,
    LinearFit,
    MosfetParams,
    Subthreshold,
    extract_diode,
    extract_mosfet,
    vth_sensitivity,
)
from .recompute import AgreementReport, CalibrationMismatch, assert_agreement, recompute
from .spice import diode_model_card, mosfet_model_card
from .transport import SerialTransport, SimTransport, Transport

__version__ = "0.1.0"

__all__ = [
    "Metadata", "Row", "Sweep", "parse", "parse_stream", "save",
    "Curve", "Family", "family_of",
    "Estimate", "FitRange", "LinearFit",
    "MosfetParams", "DiodeParams", "Subthreshold",
    "extract_mosfet", "extract_diode", "vth_sensitivity",
    "recompute", "assert_agreement", "AgreementReport", "CalibrationMismatch",
    "mosfet_model_card", "diode_model_card",
    "Transport", "SerialTransport", "SimTransport",
]
