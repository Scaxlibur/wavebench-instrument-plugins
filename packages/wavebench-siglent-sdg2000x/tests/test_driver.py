from __future__ import annotations

import pytest

from wavebench.errors import DataError
from wavebench.instruments.api import DriverContext
from wavebench.instruments.capabilities import validate_declared_capabilities
from wavebench.logging import CommandLogger

from wavebench_siglent_sdg2000x import descriptor
from wavebench_siglent_sdg2000x.driver import SDG2000XSource, parse_idn_model


class FakeTransport:
    def __init__(
        self,
        response: str = "Siglent Technologies,SDG2042X,<serial>,<firmware>",
    ) -> None:
        self.response = response
        self.queries: list[str] = []
        self.writes: list[str] = []
        self.closed = False

    def query(self, command: str) -> str:
        self.queries.append(command)
        return self.response

    def write(self, command: str) -> None:
        self.writes.append(command)
        raise AssertionError("identity-only SDG2000X baseline must not write")

    def close(self) -> None:
        self.closed = True


def test_descriptor_declares_identity_only_external_source() -> None:
    item = descriptor()

    assert item.driver_id == "siglent.sdg2000x"
    assert item.distribution == "wavebench-siglent-sdg2000x"
    assert item.kind == "source"
    assert item.models == ("SDG2042X", "SDG2082X", "SDG2122X")
    assert item.aliases == ()
    assert item.capabilities == ("source.idn",)
    assert item.backends == ("pyvisa",)
    assert item.wavebench_min_version == "0.8.0"
    assert item.wavebench_max_version == "0.9.0"


def test_factory_opens_one_core_transport_and_satisfies_capabilities() -> None:
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
        resource="TCPIP::192.0.2.40::INSTR",
        backend="pyvisa",
        timeout_ms=1_000,
        opc_timeout_ms=1_000,
        logger=CommandLogger(),
        _transport_factory=open_transport,
    )

    driver = item.factory(context)
    validate_declared_capabilities(item, driver)

    assert isinstance(driver, SDG2000XSource)
    assert driver.transport is transport
    assert opened == 1
    assert transport.queries == []


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        ("Siglent Technologies,SDG2042X,<serial>,<firmware>", "SDG2042X"),
        ("SIGLENT TECHNOLOGIES,sdg2082x,<serial>,<firmware>", "SDG2082X"),
        ("*IDN,SDG,SDG2122X,<serial>,<firmware>,<hardware>", "SDG2122X"),
    ],
)
def test_parse_idn_model_accepts_documented_formats(response: str, expected: str) -> None:
    assert parse_idn_model(response) == expected


@pytest.mark.parametrize(
    "response",
    [
        "",
        "RIGOL TECHNOLOGIES,DG4202,<serial>,<firmware>",
        "Siglent Technologies,SDG1032X,<serial>,<firmware>",
        "*IDN,OTHER,SDG2042X,<serial>,<firmware>",
    ],
)
def test_parse_idn_model_rejects_empty_wrong_family_or_wrong_model(response: str) -> None:
    with pytest.raises(DataError):
        parse_idn_model(response)


def test_idn_is_the_only_instrument_operation() -> None:
    transport = FakeTransport("Siglent Technologies,SDG2082X,<serial>,<firmware>\n")

    response = SDG2000XSource(transport).idn()

    assert response == "Siglent Technologies,SDG2082X,<serial>,<firmware>"
    assert transport.queries == ["*IDN?"]
    assert transport.writes == []


def test_idn_rejects_a_different_instrument() -> None:
    transport = FakeTransport("Siglent Technologies,SDG1032X,<serial>,<firmware>")

    with pytest.raises(DataError, match="unsupported SDG2000X model"):
        SDG2000XSource(transport).idn()

    assert transport.queries == ["*IDN?"]
    assert transport.writes == []


def test_close_is_forwarded() -> None:
    transport = FakeTransport()

    SDG2000XSource(transport).close()

    assert transport.closed is True
