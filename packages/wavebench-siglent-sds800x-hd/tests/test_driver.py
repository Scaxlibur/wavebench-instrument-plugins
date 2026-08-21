from __future__ import annotations

from types import SimpleNamespace

import pytest

from wavebench.errors import DataError
from wavebench.instruments.api import DriverContext
from wavebench.instruments.capabilities import validate_declared_capabilities
from wavebench.logging import CommandLogger
from wavebench.services.scope_service import ScopeService

from wavebench_siglent_sds800x_hd import descriptor
from wavebench_siglent_sds800x_hd.driver import SDS800XHDScope
from wavebench_siglent_sds800x_hd.profiles import (
    SDS800X_HD_ACQUISITION_CONTROL_PROFILE,
    SDS800X_HD_SCREENSHOT_PROFILE,
)


DEFAULT_IDN = "SIGLENT TECHNOLOGIES,SDS824X HD,SDS8FAKE000001,1.1.3.1"


class FakeTransport:
    def __init__(self, responses: dict[str, str] | None = None):
        self.responses = {"*IDN?": DEFAULT_IDN}
        if responses is not None:
            self.responses.update(responses)
        self.queries: list[str] = []
        self.close_count = 0

    def query(self, command: str) -> str:
        self.queries.append(command)
        return self.responses[command]

    def close(self) -> None:
        self.close_count += 1


def test_descriptor_is_executable_metadata_without_import_io() -> None:
    item = descriptor()

    assert item.driver_id == "siglent.sds800x-hd"
    assert item.api_version == "wavebench.instrument.v2"
    assert item.kind == "scope"
    assert item.models == (
        "SDS802X HD",
        "SDS804X HD",
        "SDS812X HD",
        "SDS814X HD",
        "SDS822X HD",
        "SDS824X HD",
    )
    assert item.aliases == ()
    assert item.backends == ("pyvisa",)
    assert item.resource_schemes == ("tcpip", "usb")
    assert item.capabilities == (
        "scope.idn",
        "scope.channel_coupling",
        "scope.fetch_waveform",
        "scope.capture_waveform",
        "scope.capture_waveforms",
        "scope.measurement_statistics",
        "scope.screenshot_profile",
        "scope.screenshot_v2",
        "scope.acquisition_run_state",
        "scope.acquisition_control",
    )
    assert item.scope_coupling_policy == "fixed-high-impedance"
    assert item.distribution == "wavebench-siglent-sds800x-hd"
    assert item.version == "0.6.0"
    assert item.wavebench_min_version == "0.8.23"
    assert item.scope_extensions is not None
    assert item.scope_extensions.screenshot_profile is SDS800X_HD_SCREENSHOT_PROFILE
    assert (
        item.scope_extensions.acquisition_control_profile
        is SDS800X_HD_ACQUISITION_CONTROL_PROFILE
    )
    assert item.scope_extensions.trace_profile is None
    assert item.config_fields == (
        "connection.resource",
        "scope.driver",
        "waveform.*",
    )


def test_factory_opens_exactly_one_core_transport_without_querying() -> None:
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
        resource="TCPIP0::<configured>::INSTR",
        backend="pyvisa",
        timeout_ms=2000,
        opc_timeout_ms=2000,
        logger=CommandLogger(),
        _transport_factory=open_transport,
    )

    driver = item.factory(context)
    validate_declared_capabilities(item, driver)

    assert isinstance(driver, SDS800XHDScope)
    assert driver.transport is transport
    assert driver.capture_timeout_s == 2.0
    assert opened == 1
    assert transport.queries == []


def test_idn_is_freshly_validated_and_close_is_idempotent() -> None:
    transport = FakeTransport()
    driver = SDS800XHDScope(transport)

    assert driver.idn() == DEFAULT_IDN
    assert driver.idn() == DEFAULT_IDN
    assert transport.queries == ["*IDN?", "*IDN?"]

    driver.close()
    driver.close()
    assert transport.close_count == 1


def test_idn_rejects_an_empty_response() -> None:
    driver = SDS800XHDScope(FakeTransport({"*IDN?": "  \r\n"}))

    with pytest.raises(DataError, match=r"empty response for \*IDN\?"):
        driver.idn()


@pytest.mark.parametrize(
    ("response", "message"),
    [
        ("SIGLENT TECHNOLOGIES,SDS824X HD,SDS8FAKE000001", "four non-empty"),
        ("OTHER,SDS824X HD,SDS8FAKE000001,1.1.3.1", "unsupported manufacturer"),
        (
            "SIGLENT TECHNOLOGIES,SDS999X HD,SDS8FAKE000001,1.1.3.1",
            "unsupported model",
        ),
        ("SIGLENT TECHNOLOGIES,SDS824X HD,SHORT,1.1.3.1", "14 ASCII"),
        ("SIGLENT TECHNOLOGIES,SDS824X HD,SDS8FAKE000001,", "four non-empty"),
    ],
)
def test_idn_rejects_malformed_or_unsupported_identity(response: str, message: str) -> None:
    driver = SDS800XHDScope(FakeTransport({"*IDN?": response}))

    with pytest.raises(DataError, match=message):
        driver.idn()


def test_channel_coupling_uses_identity_channel_count_and_normalizes_response() -> None:
    transport = FakeTransport({":CHANnel4:COUPling?": " ac\r\n"})
    driver = SDS800XHDScope(transport)

    assert driver.channel_coupling(4) == "AC"
    assert transport.queries == ["*IDN?", ":CHANnel4:COUPling?"]


def test_channel_coupling_reuses_identity_cache() -> None:
    transport = FakeTransport(
        {
            ":CHANnel1:COUPling?": "DC",
            ":CHANnel2:COUPling?": "GND",
        }
    )
    driver = SDS800XHDScope(transport)

    assert driver.channel_coupling(1) == "DC"
    assert driver.channel_coupling(2) == "GND"
    assert transport.queries == [
        "*IDN?",
        ":CHANnel1:COUPling?",
        ":CHANnel2:COUPling?",
    ]


def test_core_status_summary_uses_identity_and_coupling_in_one_session() -> None:
    transport = FakeTransport({":CHANnel2:COUPling?": "DC"})
    driver = SDS800XHDScope(transport)
    item = descriptor()
    service = ScopeService(
        config=SimpleNamespace(scope=SimpleNamespace(driver=item.driver_id)),
        logger=SimpleNamespace(),
        session=driver,
        descriptor=item,
    )

    result = service.status_summary(channel=2)

    assert result.status == "partial"
    assert result.idn == DEFAULT_IDN
    assert result.coupling == "DC"
    assert result.missing_capabilities == ("scope.snapshot",)
    assert transport.queries == ["*IDN?", ":CHANnel2:COUPling?"]


@pytest.mark.parametrize("channel", [True, 1.0, "1", None])
def test_channel_coupling_rejects_non_integer_channel_without_io(channel: object) -> None:
    transport = FakeTransport()
    driver = SDS800XHDScope(transport)

    with pytest.raises(DataError, match="must be an integer"):
        driver.channel_coupling(channel)  # type: ignore[arg-type]

    assert transport.queries == []


def test_channel_coupling_rejects_non_positive_channel_without_io() -> None:
    transport = FakeTransport()
    driver = SDS800XHDScope(transport)

    with pytest.raises(DataError, match="must be >= 1"):
        driver.channel_coupling(0)

    assert transport.queries == []


def test_channel_coupling_rejects_channel_missing_from_two_channel_model() -> None:
    transport = FakeTransport(
        {"*IDN?": "SIGLENT TECHNOLOGIES,SDS802X HD,SDS8FAKE000001,1.1.3.1"}
    )
    driver = SDS800XHDScope(transport)

    with pytest.raises(DataError, match="SDS802X HD channel must be between 1 and 2"):
        driver.channel_coupling(3)

    assert transport.queries == ["*IDN?"]


def test_channel_coupling_rejects_unknown_response() -> None:
    transport = FakeTransport({":CHANnel1:COUPling?": "DCL"})
    driver = SDS800XHDScope(transport)

    with pytest.raises(DataError, match="must be one of AC, DC, or GND"):
        driver.channel_coupling(1)
