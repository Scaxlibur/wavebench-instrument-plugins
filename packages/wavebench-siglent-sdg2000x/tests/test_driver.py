from __future__ import annotations

import pytest

from wavebench.errors import DataError
from wavebench.instruments.api import DriverContext
from wavebench.instruments.capabilities import validate_declared_capabilities
from wavebench.instruments.models import SourceStatus
from wavebench.logging import CommandLogger

from wavebench_siglent_sdg2000x import descriptor
from wavebench_siglent_sdg2000x.driver import SDG2000XSource, parse_idn_model


class FakeTransport:
    def __init__(
        self,
        response: str = "Siglent Technologies,SDG2042X,<serial>,<firmware>",
        *,
        responses: dict[str, str] | None = None,
    ) -> None:
        self.response = response
        self.responses = responses
        self.queries: list[str] = []
        self.writes: list[str] = []
        self.closed = False

    def query(self, command: str) -> str:
        self.queries.append(command)
        if self.responses is not None:
            try:
                return self.responses[command]
            except KeyError as exc:
                raise AssertionError(f"unexpected SDG2000X query: {command}") from exc
        return self.response

    def write(self, command: str) -> None:
        self.writes.append(command)
        raise AssertionError("query-only SDG2000X driver must not write")

    def close(self) -> None:
        self.closed = True


def _status_responses(
    *,
    channel: int,
    output: str,
    basic: str,
    sweep: str,
) -> dict[str, str]:
    return {
        "*IDN?": "Siglent Technologies,SDG2042X,<serial>,<firmware>",
        f"C{channel}:OUTP?": output,
        f"C{channel}:BSWV?": basic,
        f"C{channel}:SWWV?": sweep,
    }


def test_descriptor_declares_query_only_external_source() -> None:
    item = descriptor()

    assert item.driver_id == "siglent.sdg2000x"
    assert item.distribution == "wavebench-siglent-sdg2000x"
    assert item.kind == "source"
    assert item.models == ("SDG2042X", "SDG2082X", "SDG2122X")
    assert item.aliases == ()
    assert item.capabilities == ("source.idn", "source.status")
    assert item.backends == ("pyvisa",)
    assert item.wavebench_min_version == "0.8.0"
    assert item.wavebench_max_version == "0.9.0"
    assert item.version == "0.2.0"


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
        "Siglent Technologies,SDG2042X,<serial>,<firmware>,<extra>",
        "*IDN,SDG,SDG2042X,<serial>,<firmware>",
        "*IDN,SDG,SDG2042X,<serial>,<firmware>,",
    ],
)
def test_parse_idn_model_rejects_empty_wrong_family_or_wrong_model(response: str) -> None:
    with pytest.raises(DataError):
        parse_idn_model(response)


def test_idn_queries_identity_without_writes() -> None:
    transport = FakeTransport("Siglent Technologies,SDG2082X,<serial>,<firmware>\n")

    response = SDG2000XSource(transport).idn()

    assert response == "Siglent Technologies,SDG2082X,<serial>,<firmware>"
    assert transport.queries == ["*IDN?"]
    assert transport.writes == []


def test_get_status_parses_ch1_sine_without_writes() -> None:
    basic = (
        "C1:BSWV WVTP,SINE,FRQ,100HZ,PERI,0.01S,AMP,2V,"
        "AMPVRMS,1.41421Vrms,OFST,0V,HLEV,1V,LLEV,-1V,PHSE,0"
    )
    transport = FakeTransport(
        responses=_status_responses(
            channel=1,
            output="C1:OUTP ON,LOAD,HZ,PLRT,NOR\n",
            basic=basic,
            sweep="C1:SWWV STATE,OFF",
        )
    )

    status = SDG2000XSource(transport).get_status(1)

    assert isinstance(status, SourceStatus)
    assert status == SourceStatus(
        channel=1,
        output="ON",
        function="SIN",
        frequency_hz=100.0,
        amplitude=2.0,
        amplitude_unit="VPP",
        offset_v=0.0,
        phase_deg=0.0,
        frequency_mode="FIX",
        sweep_enabled="OFF",
        apply_raw=basic,
        square_duty_cycle_percent=None,
    )
    assert transport.queries == ["*IDN?", "C1:OUTP?", "C1:BSWV?", "C1:SWWV?"]
    assert transport.writes == []


def test_get_status_parses_ch2_square_units_and_enabled_sweep_without_writes() -> None:
    basic = (
        "C2:BSWV WVTP,SQUARE,FRQ,2.5KHZ,PERI,0.0004S,AMP,500MVPP,"
        "OFST,-25MV,HLEV,225MV,LLEV,-275MV,PHSE,90DEG,DUTY,40%"
    )
    transport = FakeTransport(
        responses=_status_responses(
            channel=2,
            output="C2:OUTP OFF,PLRT,INVT,LOAD,50OHM",
            basic=basic,
            sweep=(
                "C2:SWWVSTATE,ON,TIME,1S,STOP,1500HZ,START,500HZ,CENTER,1000HZ,"
                "SPAN,1000HZ,TRSR,INT,TRMD,OFF,SWMD,LINE,DIR,UP,SYM,0,"
                "MARK_STATE,OFF,MARK_FREQ,1000HZ,CARR,WVTP,SINE,FRQ,1000HZ,"
                "AMP,4V,AMPVRMS,1.41421Vrms,OFST,0V,PHSE,0"
            ),
        )
    )

    status = SDG2000XSource(transport).get_status(2)

    assert status.channel == 2
    assert status.output == "OFF"
    assert status.function == "SQU"
    assert status.frequency_hz == 2_500.0
    assert status.amplitude == 0.5
    assert status.amplitude_unit == "VPP"
    assert status.offset_v == -0.025
    assert status.phase_deg == 90.0
    assert status.frequency_mode == "SWE"
    assert status.sweep_enabled == "ON"
    assert status.square_duty_cycle_percent == 40.0
    assert transport.queries == ["*IDN?", "C2:OUTP?", "C2:BSWV?", "C2:SWWV?"]
    assert transport.writes == []


@pytest.mark.parametrize(
    ("wave", "expected_function", "expected_offset"),
    [
        ("WVTP,DC,OFST,1V", "DC", 1.0),
        (
            "WVTP,NOISE,STDEV,1V,MEAN,0V,BANDSTATE,ON,BANDWIDTH,10MHZ",
            "NOIS",
            None,
        ),
    ],
)
def test_get_status_preserves_inapplicable_source_status_fields_as_none(
    wave: str,
    expected_function: str,
    expected_offset: float | None,
) -> None:
    transport = FakeTransport(
        responses=_status_responses(
            channel=1,
            output="C1:OUTP OFF,LOAD,HZ,PLRT,NOR",
            basic=f"C1:BSWV {wave}",
            sweep="C1:SWWV STATE,OFF",
        )
    )

    status = SDG2000XSource(transport).get_status(1)

    assert status.function == expected_function
    assert status.frequency_hz is None
    assert status.amplitude is None
    assert status.amplitude_unit is None
    assert status.offset_v == expected_offset
    assert status.phase_deg is None
    assert status.square_duty_cycle_percent is None
    assert transport.writes == []


@pytest.mark.parametrize("channel", [0, 3, -1, True, "1"])
def test_get_status_rejects_invalid_channels_before_io(channel: object) -> None:
    transport = FakeTransport()

    with pytest.raises(DataError, match="channel must be 1 or 2"):
        SDG2000XSource(transport).get_status(channel)  # type: ignore[arg-type]

    assert transport.queries == []
    assert transport.writes == []


@pytest.mark.parametrize(
    "output",
    [
        "C2:OUTP ON,LOAD,HZ,PLRT,NOR",
        "C1:OUTP MAYBE,LOAD,HZ,PLRT,NOR",
        "C1:OUTP ON,LOAD,HZ",
        "C1:OUTP ON,LOAD,HZ,LOAD,50,PLRT,NOR",
        "C1:OUTP ON,LOAD,10,PLRT,NOR",
        "C1:OUTP ON,LOAD,HZ,PLRT,UNKNOWN",
        "C1:OUTP ON,LOAD,HZ,PLRT,NOR,EXTRA,1",
    ],
)
def test_get_status_rejects_malformed_output_responses(output: str) -> None:
    transport = FakeTransport(
        responses=_status_responses(
            channel=1,
            output=output,
            basic="C1:BSWV WVTP,SINE,FRQ,1KHZ,AMP,1V,OFST,0V,PHSE,0",
            sweep="C1:SWWV STATE,OFF",
        )
    )

    with pytest.raises(DataError):
        SDG2000XSource(transport).get_status(1)

    assert transport.writes == []


@pytest.mark.parametrize(
    "basic",
    [
        "C2:BSWV WVTP,SINE,FRQ,1KHZ,AMP,1V,OFST,0V,PHSE,0",
        "C1:BSWV FRQ,1KHZ,AMP,1V,OFST,0V,PHSE,0",
        "C1:BSWV WVTP,SINE,EXTRA,1,FRQ,1KHZ,AMP,1V,OFST,0V,PHSE,0",
        "C1:BSWV WVTP,SINE,WVTP,SQUARE,FRQ,1KHZ,AMP,1V,OFST,0V,PHSE,0",
        "C1:BSWV WVTP,SINE,FRQ,NANHZ,AMP,1V,OFST,0V,PHSE,0",
        "C1:BSWV WVTP,SINE,FRQ,1S,AMP,1V,OFST,0V,PHSE,0",
        "C1:BSWV WVTP,SQUARE,FRQ,1KHZ,AMP,1V,OFST,0V,PHSE,0",
        "C1:BSWV WVTP,SINE,FRQ,1KHZ,AMP,1V,OFST,0V,PHSE,361",
        "C1:BSWV WVTP,SINE,FRQ,1KHZ,AMP,0V,OFST,0V,PHSE,0",
        "C1:BSWV WVTP,SINE,FRQ,1KHZ,AMP,1V,OFST,0V,PHSE,0\nC1:OUTP OFF",
    ],
)
def test_get_status_rejects_malformed_basic_wave_responses(basic: str) -> None:
    transport = FakeTransport(
        responses=_status_responses(
            channel=1,
            output="C1:OUTP OFF,LOAD,HZ,PLRT,NOR",
            basic=basic,
            sweep="C1:SWWV STATE,OFF",
        )
    )

    with pytest.raises(DataError):
        SDG2000XSource(transport).get_status(1)

    assert transport.writes == []


@pytest.mark.parametrize(
    "sweep",
    [
        "C2:SWWV STATE,OFF",
        "C1:SWWV MODE,OFF",
        "C1:SWWV STATE,MAYBE",
        "C1:SWWV STATE,OFF,TIME,1S",
        "C1:SWWV STATE,ON",
        "C1:SWWV STATE,ON,TIME",
    ],
)
def test_get_status_rejects_malformed_sweep_responses(sweep: str) -> None:
    transport = FakeTransport(
        responses=_status_responses(
            channel=1,
            output="C1:OUTP OFF,LOAD,HZ,PLRT,NOR",
            basic="C1:BSWV WVTP,SINE,FRQ,1KHZ,AMP,1V,OFST,0V,PHSE,0",
            sweep=sweep,
        )
    )

    with pytest.raises(DataError):
        SDG2000XSource(transport).get_status(1)

    assert transport.writes == []


def test_get_status_caches_verified_identity_within_one_session() -> None:
    responses = _status_responses(
        channel=1,
        output="C1:OUTP OFF,LOAD,HZ,PLRT,NOR",
        basic="C1:BSWV WVTP,SINE,FRQ,1KHZ,AMP,1V,OFST,0V,PHSE,0",
        sweep="C1:SWWV STATE,OFF",
    )
    transport = FakeTransport(responses=responses)
    driver = SDG2000XSource(transport)

    driver.get_status(1)
    driver.get_status(1)

    assert transport.queries.count("*IDN?") == 1
    assert transport.queries.count("C1:OUTP?") == 2
    assert transport.queries.count("C1:BSWV?") == 2
    assert transport.queries.count("C1:SWWV?") == 2
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
