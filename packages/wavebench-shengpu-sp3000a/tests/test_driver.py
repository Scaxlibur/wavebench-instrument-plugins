from __future__ import annotations

import pytest

from wavebench.errors import DataError, InstrumentError
from wavebench.instruments.api import DriverContext
from wavebench.instruments.capabilities import validate_declared_capabilities
from wavebench.logging import CommandLogger

from wavebench_shengpu_sp3000a import descriptor
from wavebench_shengpu_sp3000a.driver import (
    SP30120ProtocolError,
    SP30120SweepAnalyzer,
)


class FakeTransport:
    def __init__(self, responses: dict[str, str] | None = None) -> None:
        self.responses = {
            "*IDN?": "SHENGPU SP3000 Series Digital Sweeper",
            "RFSTAT?": "ON",
            "OUTOHMSEL?": "50",
            "CENS?": "6.050000e+07,1.190000e+08",
            "STAS?": "1.000000e+06,1.200000e+08",
            "CWFREQ?": "1.000000e+07",
            "FREQOFFSET?": "0.000000e+00",
            "SWET?": "2.000000e-01",
            "SWET:MODE?": "LIN",
            "TRIM?": "CONT",
            "EXTT?": "OFF",
            "INPZ?": "50",
            **(responses or {}),
        }
        self.queries: list[str] = []
        self.writes: list[str] = []
        self.closed = False

    def query(self, command: str) -> str:
        self.queries.append(command)
        return self.responses[command]

    def write(self, command: str) -> None:
        self.writes.append(command)

    def close(self) -> None:
        self.closed = True


def test_descriptor_is_query_only_executable_metadata_without_io() -> None:
    item = descriptor()

    assert item.driver_id == "shengpu.sp30120"
    assert item.api_version == "wavebench.instrument.v2"
    assert item.kind == "sweep_analyzer"
    assert item.models == ("SP30120",)
    assert item.aliases == ()
    assert item.backends == ("serial",)
    assert item.capabilities == ("sweep_analyzer.idn",)
    assert item.distribution == "wavebench-shengpu-sp3000a"


def test_factory_opens_exactly_one_core_transport() -> None:
    item = descriptor()
    transport = FakeTransport()
    opened = 0

    def open_transport() -> FakeTransport:
        nonlocal opened
        opened += 1
        return transport

    context = DriverContext(
        driver_id=item.driver_id,
        kind=item.kind,
        resource="serial-by-id:<configured>",
        backend="serial",
        timeout_ms=2000,
        opc_timeout_ms=2000,
        logger=CommandLogger(),
        _transport_factory=open_transport,
    )

    driver = item.factory(context)
    validate_declared_capabilities(item, driver)

    assert isinstance(driver, SP30120SweepAnalyzer)
    assert driver.transport is transport
    assert opened == 1
    assert transport.queries == []


def test_verified_scalar_status_is_query_only_and_typed() -> None:
    transport = FakeTransport()
    driver = SP30120SweepAnalyzer(transport)

    assert driver.idn() == "SHENGPU SP3000 Series Digital Sweeper"
    status = driver.read_scalar_status()

    assert status.rf_output_enabled is True
    assert status.source_impedance_ohm == 50
    assert status.center_frequency_hz == 60_500_000.0
    assert status.span_frequency_hz == 119_000_000.0
    assert status.start_frequency_hz == 1_000_000.0
    assert status.stop_frequency_hz == 120_000_000.0
    assert status.cw_frequency_hz == 10_000_000.0
    assert status.frequency_offset_hz == 0.0
    assert status.sweep_time_s == 0.2
    assert status.sweep_axis == "linear"
    assert status.acquisition == "continuous"
    assert status.external_trigger_enabled is False
    assert status.input_impedance == 50
    assert transport.writes == []
    assert all(command.endswith("?") for command in transport.queries)


@pytest.mark.parametrize(
    ("response", "code", "message"),
    [
        ("ERRORNo00", "ERRORNo00", "command format error"),
        ("ERRORNo01", "ERRORNo01", "current state"),
        ("ERRORNo02", "ERRORNo02", "out of range"),
        ("ERRORNo03", "ERRORNo03", "zero value"),
        ("ERRORNo04", "ERRORNo04", "negative value"),
        ("ERRORNo05", "ERRORNo05", "floating-point format"),
        ("ERRORNo06", "ERRORNo06", "leading zero"),
        ("ERRORNo07", "ERRORNo07", "no valid input data"),
        ("errorno08", "ERRORNo08", "too many digits"),
        ("Error", "undocumented_error", "undocumented Error"),
    ],
)
def test_private_errors_are_structured_deterministic_and_never_retried(
    response: str, code: str, message: str
) -> None:
    command = "RFSTAT?"
    transport = FakeTransport({command: response})

    with pytest.raises(SP30120ProtocolError, match=message) as caught:
        SP30120SweepAnalyzer(transport).read_scalar_status()

    assert isinstance(caught.value, InstrumentError)
    assert caught.value.code == code
    assert caught.value.command == command
    assert caught.value.retryable is False
    assert transport.queries.count(command) == 1
    assert transport.writes == []


@pytest.mark.parametrize(
    ("responses", "message"),
    [
        ({"RFSTAT?": "MAYBE"}, "RFSTAT"),
        ({"CENS?": "1,2,3"}, "pair response"),
        ({"STAS?": "2.0e6,1.0e6"}, "start frequency"),
        ({"SWET?": "nan"}, "finite and > 0"),
        ({"INPZ?": "100"}, "unsupported.*impedance"),
    ],
)
def test_invalid_or_unverified_status_shapes_fail_closed(
    responses: dict[str, str], message: str
) -> None:
    with pytest.raises((DataError, ValueError), match=message):
        SP30120SweepAnalyzer(FakeTransport(responses)).read_scalar_status()


def test_family_identity_does_not_claim_model_from_incompatible_response() -> None:
    private_token = "SERIAL-DO-NOT-LOG"
    driver = SP30120SweepAnalyzer(
        FakeTransport({"*IDN?": f"SHENGPU,SP30120A,{private_token},FW"})
    )

    with pytest.raises(DataError, match="identity mismatch") as caught:
        driver.idn()

    assert private_token not in str(caught.value)
    assert "SP30120A" not in str(caught.value)


def test_family_identity_tolerates_only_formatting_variations() -> None:
    driver = SP30120SweepAnalyzer(
        FakeTransport({"*IDN?": "  shengpu   sp3000 series digital sweeper.  "})
    )

    assert driver.idn() == "shengpu   sp3000 series digital sweeper."


def test_documented_high_impedance_status_is_preserved_without_guessing_ohms() -> None:
    status = SP30120SweepAnalyzer(FakeTransport({"INPZ?": "HIGHZ"})).read_scalar_status()

    assert status.input_impedance == "highz"


def test_unverified_and_write_paths_are_not_exposed() -> None:
    driver = SP30120SweepAnalyzer(FakeTransport())

    assert not hasattr(driver, "get_snapshot")
    assert not hasattr(driver, "fetch_frequency_response")
    assert not hasattr(driver, "apply_sweep_plan")
    assert not hasattr(driver, "trigger_single")
    assert not hasattr(driver, "set_source_output")
    assert not hasattr(driver, "read_markers")
    assert not hasattr(driver, "read_measurements")


def test_close_is_forwarded() -> None:
    transport = FakeTransport()
    SP30120SweepAnalyzer(transport).close()
    assert transport.closed
