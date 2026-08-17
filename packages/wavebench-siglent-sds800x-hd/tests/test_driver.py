from __future__ import annotations

import pytest

from wavebench.errors import DataError
from wavebench.instruments.api import DriverContext
from wavebench.instruments.capabilities import validate_declared_capabilities
from wavebench.logging import CommandLogger

from wavebench_siglent_sds800x_hd import descriptor
from wavebench_siglent_sds800x_hd.driver import SDS800XHDScope


class FakeTransport:
    def __init__(self, response: str = "SIGLENT TECHNOLOGIES,SDS824X HD,SERIAL,FIRMWARE"):
        self.response = response
        self.queries: list[str] = []
        self.closed = False

    def query(self, command: str) -> str:
        self.queries.append(command)
        return self.response

    def close(self) -> None:
        self.closed = True


def test_descriptor_is_query_only_executable_metadata_without_io() -> None:
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
    assert item.capabilities == ("scope.idn",)
    assert item.scope_coupling_policy == "fixed-high-impedance"
    assert item.distribution == "wavebench-siglent-sds800x-hd"


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
    assert opened == 1
    assert transport.queries == []


def test_idn_is_the_only_instrument_query_and_close_releases_transport() -> None:
    transport = FakeTransport()
    driver = SDS800XHDScope(transport)

    assert driver.idn() == "SIGLENT TECHNOLOGIES,SDS824X HD,SERIAL,FIRMWARE"
    assert transport.queries == ["*IDN?"]

    driver.close()
    assert transport.closed is True


def test_idn_rejects_an_empty_response() -> None:
    driver = SDS800XHDScope(FakeTransport("  \r\n"))

    with pytest.raises(DataError, match=r"empty response for \*IDN\?"):
        driver.idn()
