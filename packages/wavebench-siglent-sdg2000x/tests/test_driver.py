from __future__ import annotations

import inspect
import re
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from wavebench.errors import ConfigError, DataError, InstrumentError
from wavebench.instruments.api import DriverContext
from wavebench.instruments.capabilities import validate_declared_capabilities
from wavebench.instruments.models import ArbitraryQueryProbeResult, SourceStatus
from wavebench.logging import CommandLogger
from wavebench.services.source_service import SourceService

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
        raise AssertionError("read-only SDG2000X operation must not write")

    def close(self) -> None:
        self.closed = True


class StatefulOutputTransport:
    def __init__(self, *, model: str = "SDG2122X") -> None:
        self.model = model
        self.outputs = {1: "OFF", 2: "OFF"}
        self.loads = {1: "HZ", 2: "HZ"}
        self.basics = {
            channel: (
                f"C{channel}:BSWV WVTP,SINE,FRQ,1KHZ,AMP,4V,OFST,0V,PHSE,0"
            )
            for channel in (1, 2)
        }
        self.sweeps = {1: "OFF", 2: "OFF"}
        self.modulation = {1: "OFF", 2: "OFF"}
        self.burst = {1: "OFF", 2: "OFF"}
        self.harmonic = {1: "OFF", 2: "OFF"}
        self.combine = {1: "OFF", 2: "OFF"}
        self.noise_add = {1: "OFF", 2: "OFF"}
        self.coupling = {
            "TRACE": "OFF",
            "TRDUCH": "OFF",
            "FCOUP": "OFF",
            "PCOUP": "OFF",
            "ACOUP": "OFF",
        }
        self.queries: list[str] = []
        self.writes: list[str] = []
        self.query_overrides: dict[str, str] = {}
        self.fail_query_counts: dict[str, int] = {}
        self.fail_before_write_counts: dict[str, int] = {}
        self.fail_after_write_counts: dict[str, int] = {}
        self.fail_readback_counts: dict[str, int] = {}
        self.ignore_write_counts: dict[str, int] = {}
        self.drift_write_counts: dict[str, int] = {}
        self.advanced_drift_write_counts: dict[str, int] = {}
        self.closed = False

    @staticmethod
    def _consume(values: dict[str, int], command: str) -> bool:
        remaining = values.get(command, 0)
        if remaining <= 0:
            return False
        values[command] = remaining - 1
        return True

    def query(self, command: str) -> str:
        self.queries.append(command)
        if self._consume(self.fail_query_counts, command):
            raise InstrumentError("injected SDG2000X query failure")
        if command in self.query_overrides:
            return self.query_overrides[command]
        if command == "*IDN?":
            return f"Siglent Technologies,{self.model},<serial>,<firmware>"
        if command == "COUP?":
            return "COUP " + ",".join(
                item
                for name, value in self.coupling.items()
                for item in (name, value)
            )
        match = re.fullmatch(
            r"C([12]):(OUTP|BSWV|SWWV|MDWV|BTWV|HARM|CMBN|NOISE_ADD)\?",
            command,
        )
        if match is None:
            raise AssertionError(f"unexpected SDG2000X query: {command}")
        channel = int(match.group(1))
        header = match.group(2)
        if header == "OUTP":
            return (
                f"C{channel}:OUTP {self.outputs[channel]},LOAD,{self.loads[channel]},"
                "POWERON_STATE,OFF,PLRT,NOR"
            )
        if header == "BSWV":
            return self.basics[channel]
        if header == "SWWV" and self.sweeps[channel] == "ON":
            return f"C{channel}:SWWV STATE,ON,TIME,1S"
        if header == "SWWV":
            return f"C{channel}:SWWV STATE,OFF"
        if header == "MDWV":
            return f"C{channel}:MDWV STATE,{self.modulation[channel]}"
        if header == "BTWV":
            return f"C{channel}:BTWV STATE,{self.burst[channel]}"
        if header == "HARM":
            if self.harmonic[channel] == "OFF":
                return f"C{channel}:HARM HARMSTATE,OFF"
            return (
                f"C{channel}:HARM HARMSTATE,ON,HARMTYPE,EVEN,HARMORDER,2,"
                "HARMAMP,0.25V,HARMDBC,-24.0824dBc,HARMPHASE,0"
            )
        if header == "CMBN":
            return f"C{channel}:CMBN {self.combine[channel]}"
        return (
            f"C{channel}:NOISE_ADD STATE,{self.noise_add[channel]},"
            "RATIO,100,RATIO_DB,20dB"
        )

    def write(self, command: str) -> None:
        self.writes.append(command)
        if self._consume(self.fail_before_write_counts, command):
            raise InstrumentError("injected SDG2000X write failure before fake apply")
        output_match = re.fullmatch(r"C([12]):OUTP (ON|OFF)", command)
        sweep_match = re.fullmatch(r"C([12]):SWWV STATE,OFF", command)
        frequency_match = re.fullmatch(
            r"C([12]):BSWV FRQ,([+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)",
            command,
        )
        amplitude_match = re.fullmatch(
            r"C([12]):BSWV AMP,([+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)",
            command,
        )
        function_match = re.fullmatch(
            r"C([12]):BSWV WVTP,(SINE|SQUARE|RAMP|PULSE|NOISE|DC)",
            command,
        )
        duty_match = re.fullmatch(
            r"C([12]):BSWV DUTY,([+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)",
            command,
        )
        match = (
            output_match
            or sweep_match
            or frequency_match
            or amplitude_match
            or function_match
            or duty_match
        )
        if match is None:
            raise AssertionError(f"unexpected SDG2000X write: {command}")
        channel = int(match.group(1))
        if not self._consume(self.ignore_write_counts, command):
            if output_match is not None:
                self.outputs[channel] = output_match.group(2)
            elif sweep_match is not None:
                self.sweeps[channel] = "OFF"
            elif frequency_match is not None:
                value_hz = float(frequency_match.group(2))
                self.basics[channel] = re.sub(
                    r"FRQ,[^,]+",
                    f"FRQ,{value_hz:.12g}HZ",
                    self.basics[channel],
                    count=1,
                )
            elif amplitude_match is not None:
                value_vpp = float(amplitude_match.group(2))
                self.basics[channel] = re.sub(
                    r"AMP,[^,]+",
                    f"AMP,{value_vpp:.12g}V",
                    self.basics[channel],
                    count=1,
                )
            elif function_match is not None:
                wave_type = function_match.group(2)
                current = self.basics[channel]

                def value(name: str, default: str) -> str:
                    found = re.search(rf"(?:^|,){name},([^,]+)", current)
                    return found.group(1) if found is not None else default

                common = (
                    f"FRQ,{value('FRQ', '1KHZ')},AMP,{value('AMP', '1V')},"
                    f"OFST,{value('OFST', '0V')}"
                )
                phase = value("PHSE", "0")
                if wave_type == "SINE":
                    body = f"WVTP,SINE,{common},PHSE,{phase}"
                elif wave_type == "SQUARE":
                    body = (
                        f"WVTP,SQUARE,{common},PHSE,{phase},"
                        f"DUTY,{value('DUTY', '50')}"
                    )
                elif wave_type == "RAMP":
                    body = f"WVTP,RAMP,{common},PHSE,{phase},SYM,50"
                elif wave_type == "PULSE":
                    body = (
                        f"WVTP,PULSE,{common},WIDTH,500US,RISE,8.4NS,"
                        "FALL,8.4NS,DLY,0S,DUTY,50"
                    )
                elif wave_type == "NOISE":
                    body = (
                        "WVTP,NOISE,STDEV,1V,MEAN,0V,BANDSTATE,OFF,"
                        "BANDWIDTH,120MHZ"
                    )
                else:
                    body = f"WVTP,DC,OFST,{value('OFST', '0V')}"
                self.basics[channel] = f"C{channel}:BSWV {body}"
            else:
                assert duty_match is not None
                duty_percent = float(duty_match.group(2))
                self.basics[channel] = re.sub(
                    r"DUTY,[^,]+",
                    f"DUTY,{duty_percent:.12g}",
                    self.basics[channel],
                    count=1,
                )
        if self._consume(self.drift_write_counts, command):
            self.basics[channel] = (
                f"C{channel}:BSWV WVTP,SINE,FRQ,1KHZ,AMP,2V,OFST,0V,PHSE,0"
            )
        if self._consume(self.advanced_drift_write_counts, command):
            self.combine[channel] = "ON"
        if self._consume(self.fail_readback_counts, command):
            if output_match is not None:
                query = f"C{channel}:OUTP?"
            elif sweep_match is not None:
                query = f"C{channel}:SWWV?"
            else:
                query = f"C{channel}:BSWV?"
            self.fail_query_counts[query] = self.fail_query_counts.get(query, 0) + 1
        if self._consume(self.fail_after_write_counts, command):
            raise InstrumentError("injected ambiguous SDG2000X write failure")

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


def _output_safety_queries(channel: int) -> list[str]:
    return [
        f"C{channel}:MDWV?",
        f"C{channel}:BTWV?",
        f"C{channel}:HARM?",
        f"C{channel}:CMBN?",
        f"C{channel}:NOISE_ADD?",
        "COUP?",
    ]


def _configuration_queries(channel: int) -> list[str]:
    return [
        f"C{channel}:OUTP?",
        f"C{channel}:BSWV?",
        f"C{channel}:SWWV?",
        *_output_safety_queries(channel),
    ]


def test_descriptor_declares_output_capable_external_source() -> None:
    item = descriptor()

    assert item.driver_id == "siglent.sdg2000x"
    assert item.distribution == "wavebench-siglent-sdg2000x"
    assert item.kind == "source"
    assert item.models == ("SDG2042X", "SDG2082X", "SDG2122X")
    assert item.aliases == ()
    assert item.capabilities == (
        "source.idn",
        "source.status",
        "source.set_frequency",
        "source.set_function",
        "source.set_amplitude_vpp",
        "source.set_square_duty_cycle",
        "source.output",
        "source.arbitrary_probe",
    )
    assert item.backends == ("pyvisa",)
    assert item.wavebench_min_version == "0.8.0"
    assert item.wavebench_max_version == "0.9.0"
    assert item.version == "0.8.0"
    assert item.config_fields == (
        "source.resource",
        "source.driver",
        "safety_limits.max_source_vpp",
    )


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


def test_arbitrary_probe_uses_only_documented_queries_and_core_results() -> None:
    transport = FakeTransport(
        responses={
            "*IDN?": "Siglent Technologies,SDG2122X,<serial>,<firmware>",
            "C2:ARWV?": "C2:ARWV INDEX,2,NAME,StairUp",
            "C2:SRATE?": "C2:SRATE MODE,DDS",
            "STL? BUILDIN": "STL M2,StairUp,M3,StairDn",
        }
    )

    results = SDG2000XSource(transport).probe_arbitrary_queries(2)

    assert all(isinstance(item, ArbitraryQueryProbeResult) for item in results)
    assert [(item.label, item.command) for item in results] == [
        ("current_selection", "C2:ARWV?"),
        ("sample_rate_mode", "C2:SRATE?"),
        ("builtin_catalog", "STL? BUILDIN"),
    ]
    assert [item.response for item in results] == [
        "C2:ARWV INDEX,2,NAME,StairUp",
        "C2:SRATE MODE,DDS",
        "STL M2,StairUp,M3,StairDn",
    ]
    assert all(item.errors == [] and item.exception is None and item.accepted for item in results)
    assert transport.queries == [
        "*IDN?",
        "C2:ARWV?",
        "C2:SRATE?",
        "STL? BUILDIN",
    ]
    assert transport.writes == []


def test_arbitrary_probe_records_query_failure_and_continues_without_writes() -> None:
    transport = StatefulOutputTransport()
    transport.query_overrides.update(
        {
            "C1:ARWV?": "C1:ARWV INDEX,3,NAME,StairDn",
            "C1:SRATE?": "C1:SRATE MODE,DDS",
            "STL? BUILDIN": "STL M2,StairUp,M3,StairDn",
        }
    )
    transport.fail_query_counts["C1:SRATE?"] = 1

    results = SDG2000XSource(transport).probe_arbitrary_queries(1)

    assert results[0].accepted
    assert not results[1].accepted
    assert results[1].response is None
    assert results[1].exception == "InstrumentError: injected SDG2000X query failure"
    assert results[2].accepted
    assert transport.queries == [
        "*IDN?",
        "C1:ARWV?",
        "C1:SRATE?",
        "STL? BUILDIN",
    ]
    assert transport.writes == []


@pytest.mark.parametrize("channel", [0, 3, True, 1.0, "1"])
def test_arbitrary_probe_rejects_invalid_channel_before_io(channel: object) -> None:
    transport = FakeTransport()

    with pytest.raises(DataError):
        SDG2000XSource(transport).probe_arbitrary_queries(channel)  # type: ignore[arg-type]

    assert transport.queries == []
    assert transport.writes == []


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


def test_get_status_accepts_verified_sdg2122x_power_on_output_state() -> None:
    transport = FakeTransport(
        responses=_status_responses(
            channel=1,
            output="C1:OUTP OFF,LOAD,HZ,POWERON_STATE,OFF,PLRT,NOR",
            basic="C1:BSWV WVTP,SINE,FRQ,1KHZ,AMP,1V,OFST,0V,PHSE,0",
            sweep="C1:SWWV STATE,OFF",
        )
    )

    status = SDG2000XSource(transport).get_status(1)

    assert status.output == "OFF"
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
        "C1:OUTP ON,LOAD,HZ,POWERON_STATE,UNKNOWN,PLRT,NOR",
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


def test_set_output_matches_the_core_source_driver_signature() -> None:
    signature = inspect.signature(SDG2000XSource.set_output)
    parameters = tuple(signature.parameters.values())

    assert tuple(parameter.name for parameter in parameters) == (
        "self",
        "channel",
        "enabled",
        "check_errors",
    )
    assert parameters[-1].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters[-1].default is True


def test_set_frequency_matches_the_core_source_driver_signature() -> None:
    signature = inspect.signature(SDG2000XSource.set_frequency)
    parameters = tuple(signature.parameters.values())

    assert tuple(parameter.name for parameter in parameters) == (
        "self",
        "channel",
        "value_hz",
        "ensure_fix_mode",
        "check_errors",
    )
    assert parameters[-2].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters[-2].default is True
    assert parameters[-1].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters[-1].default is True


@pytest.mark.parametrize("model", ["SDG2042X", "SDG2082X", "SDG2122X"])
@pytest.mark.parametrize("channel", [1, 2])
@pytest.mark.parametrize("output", ["OFF", "ON"])
def test_set_frequency_covers_models_channels_and_live_output(
    model: str,
    channel: int,
    output: str,
) -> None:
    transport = StatefulOutputTransport(model=model)
    transport.outputs[channel] = output

    status = SDG2000XSource(transport).set_frequency(
        channel,
        2_500.0,
        check_errors=False,
    )

    assert status.frequency_hz == 2_500.0
    assert status.output == output
    assert transport.writes == [f"C{channel}:BSWV FRQ,2500"]
    assert transport.queries == [
        "*IDN?",
        *_configuration_queries(channel),
        *_configuration_queries(channel),
    ]


def test_set_frequency_is_idempotent_with_full_safety_snapshot() -> None:
    transport = StatefulOutputTransport()

    status = SDG2000XSource(transport).set_frequency(
        1,
        1_000.0004,
        check_errors=False,
    )

    assert status.frequency_hz == 1_000.0
    assert transport.writes == []
    assert transport.queries == ["*IDN?", *_configuration_queries(1)]


@pytest.mark.parametrize("ensure_fix_mode", [False, True])
def test_set_frequency_handles_sweep_mode_only_with_safe_automatic_selection(
    ensure_fix_mode: bool,
) -> None:
    transport = StatefulOutputTransport()
    transport.sweeps[1] = "ON"
    driver = SDG2000XSource(transport)

    if not ensure_fix_mode:
        with pytest.raises(DataError, match="require FIX mode"):
            driver.set_frequency(
                1,
                2_000.0,
                ensure_fix_mode=False,
                check_errors=False,
            )
        assert transport.writes == []
        return

    status = driver.set_frequency(
        1,
        2_000.0,
        ensure_fix_mode=True,
        check_errors=False,
    )

    assert status.frequency_mode == "FIX"
    assert status.sweep_enabled == "OFF"
    assert status.frequency_hz == 2_000.0
    assert transport.writes == ["C1:SWWV STATE,OFF", "C1:BSWV FRQ,2000"]


def test_set_frequency_rejects_live_automatic_sweep_mode_selection() -> None:
    transport = StatefulOutputTransport()
    transport.outputs[1] = "ON"
    transport.sweeps[1] = "ON"

    with pytest.raises(DataError, match="requires output OFF"):
        SDG2000XSource(transport).set_frequency(1, 2_000.0, check_errors=False)

    assert transport.writes == []


@pytest.mark.parametrize("channel", [0, 3, -1, True, "1"])
def test_set_frequency_rejects_invalid_channels_before_io(channel: object) -> None:
    transport = StatefulOutputTransport()

    with pytest.raises(DataError, match="channel must be 1 or 2"):
        SDG2000XSource(transport).set_frequency(  # type: ignore[arg-type]
            channel,
            1_000.0,
            check_errors=False,
        )

    assert transport.queries == []
    assert transport.writes == []


@pytest.mark.parametrize("value", [True, "1000", None, float("nan"), float("inf")])
def test_set_frequency_rejects_non_finite_numbers_before_io(value: object) -> None:
    transport = StatefulOutputTransport()

    with pytest.raises(DataError, match="finite number"):
        SDG2000XSource(transport).set_frequency(  # type: ignore[arg-type]
            1,
            value,
            check_errors=False,
        )

    assert transport.queries == []
    assert transport.writes == []


@pytest.mark.parametrize("ensure_fix_mode", [0, 1, "true", None])
def test_set_frequency_rejects_invalid_fix_mode_flag_before_io(
    ensure_fix_mode: object,
) -> None:
    transport = StatefulOutputTransport()

    with pytest.raises(DataError, match="ensure_fix_mode"):
        SDG2000XSource(transport).set_frequency(  # type: ignore[arg-type]
            1,
            1_000.0,
            ensure_fix_mode=ensure_fix_mode,
            check_errors=False,
        )

    assert transport.queries == []
    assert transport.writes == []


@pytest.mark.parametrize("check_errors", [True, 1, "false", None])
def test_set_frequency_rejects_unavailable_error_checks_before_io(
    check_errors: object,
) -> None:
    transport = StatefulOutputTransport()

    with pytest.raises(DataError, match="check_errors"):
        SDG2000XSource(transport).set_frequency(  # type: ignore[arg-type]
            1,
            1_000.0,
            check_errors=check_errors,
        )

    assert transport.queries == []
    assert transport.writes == []


@pytest.mark.parametrize(
    ("model", "basic", "value_hz"),
    [
        ("SDG2042X", "WVTP,SINE,FRQ,1KHZ,AMP,1V,OFST,0V,PHSE,0", 40e6 + 1),
        ("SDG2082X", "WVTP,SINE,FRQ,1KHZ,AMP,1V,OFST,0V,PHSE,0", 80e6 + 1),
        ("SDG2122X", "WVTP,SINE,FRQ,1KHZ,AMP,1V,OFST,0V,PHSE,0", 120e6 + 1),
        ("SDG2122X", "WVTP,SQUARE,FRQ,1KHZ,AMP,1V,OFST,0V,PHSE,0,DUTY,50", 25e6 + 1),
        ("SDG2122X", "WVTP,RAMP,FRQ,1KHZ,AMP,1V,OFST,0V,PHSE,0", 1e6 + 1),
        ("SDG2122X", "WVTP,PULSE,FRQ,1KHZ,AMP,1V,OFST,0V", 25e6 + 1),
        ("SDG2122X", "WVTP,ARB,FRQ,1KHZ,AMP,1V,OFST,0V,PHSE,0", 20e6 + 1),
    ],
)
def test_set_frequency_enforces_model_and_function_limits_before_write(
    model: str,
    basic: str,
    value_hz: float,
) -> None:
    transport = StatefulOutputTransport(model=model)
    transport.basics[1] = f"C1:BSWV {basic}"

    with pytest.raises(DataError, match="frequency exceeds"):
        SDG2000XSource(transport).set_frequency(1, value_hz, check_errors=False)

    assert transport.writes == []


@pytest.mark.parametrize("value_hz", [0.0, -1.0, 0.9e-6])
def test_set_frequency_enforces_the_one_microhertz_floor(value_hz: float) -> None:
    transport = StatefulOutputTransport()

    with pytest.raises(DataError, match="at least 1 uHz"):
        SDG2000XSource(transport).set_frequency(1, value_hz, check_errors=False)

    assert transport.writes == []


@pytest.mark.parametrize(
    "basic",
    [
        "C1:BSWV WVTP,NOISE,STDEV,1V,MEAN,0V,BANDSTATE,OFF,BANDWIDTH,120MHZ",
        "C1:BSWV WVTP,DC,OFST,0V",
    ],
)
def test_set_frequency_rejects_inapplicable_functions(basic: str) -> None:
    transport = StatefulOutputTransport()
    transport.basics[1] = basic

    with pytest.raises(DataError, match="not applicable"):
        SDG2000XSource(transport).set_frequency(1, 1_000.0, check_errors=False)

    assert transport.writes == []


def test_set_frequency_rejects_advanced_mode_before_write_without_latching() -> None:
    transport = StatefulOutputTransport()
    transport.harmonic[1] = "ON"
    driver = SDG2000XSource(transport)

    with pytest.raises(DataError, match="advanced signal modes OFF"):
        driver.set_frequency(1, 2_000.0, check_errors=False)

    assert transport.writes == []
    assert driver.configuration_writes_blocked is False


def test_set_frequency_postwrite_mismatch_forces_off_and_latches_all_writes() -> None:
    transport = StatefulOutputTransport()
    transport.ignore_write_counts["C1:BSWV FRQ,2000"] = 1
    driver = SDG2000XSource(transport)

    with pytest.raises(InstrumentError, match="confirmed OFF"):
        driver.set_frequency(1, 2_000.0, check_errors=False)

    assert transport.outputs[1] == "OFF"
    assert transport.writes == ["C1:BSWV FRQ,2000", "C1:OUTP OFF"]
    assert driver.configuration_writes_blocked is True
    assert driver.output_writes_blocked is True

    io_counts = (len(transport.queries), len(transport.writes))
    with pytest.raises(InstrumentError, match="configuration writes are blocked"):
        driver.set_frequency(1, 3_000.0, check_errors=False)
    with pytest.raises(InstrumentError, match="configuration writes are blocked"):
        driver.set_output(1, True, check_errors=False)
    assert (len(transport.queries), len(transport.writes)) == io_counts


@pytest.mark.parametrize("failure", ["ambiguous", "readback", "drift", "advanced"])
def test_set_frequency_all_postwrite_failures_force_off_and_latch(failure: str) -> None:
    transport = StatefulOutputTransport()
    command = "C1:BSWV FRQ,2000"
    if failure == "ambiguous":
        transport.fail_after_write_counts[command] = 1
    elif failure == "readback":
        transport.fail_readback_counts[command] = 1
    elif failure == "drift":
        transport.drift_write_counts[command] = 1
    else:
        transport.advanced_drift_write_counts[command] = 1
    driver = SDG2000XSource(transport)

    with pytest.raises(InstrumentError, match="confirmed OFF"):
        driver.set_frequency(1, 2_000.0, check_errors=False)

    assert transport.outputs[1] == "OFF"
    assert transport.writes == [command, "C1:OUTP OFF"]
    assert driver.configuration_writes_blocked is True


def test_set_frequency_recovery_failure_reports_uncertain_output() -> None:
    transport = StatefulOutputTransport()
    transport.fail_after_write_counts["C1:BSWV FRQ,2000"] = 1
    transport.fail_before_write_counts["C1:OUTP OFF"] = 1
    driver = SDG2000XSource(transport)

    with pytest.raises(InstrumentError, match="state is uncertain"):
        driver.set_frequency(1, 2_000.0, check_errors=False)

    assert driver.configuration_writes_blocked is True


def test_set_amplitude_matches_the_core_source_driver_signature() -> None:
    signature = inspect.signature(SDG2000XSource.set_amplitude_vpp)
    parameters = tuple(signature.parameters.values())

    assert tuple(parameter.name for parameter in parameters) == (
        "self",
        "channel",
        "value_vpp",
        "check_errors",
    )
    assert parameters[-1].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters[-1].default is True


@pytest.mark.parametrize("model", ["SDG2042X", "SDG2082X", "SDG2122X"])
@pytest.mark.parametrize("channel", [1, 2])
@pytest.mark.parametrize("output", ["OFF", "ON"])
def test_set_amplitude_covers_models_channels_and_live_output(
    model: str,
    channel: int,
    output: str,
) -> None:
    transport = StatefulOutputTransport(model=model)
    transport.outputs[channel] = output

    status = SDG2000XSource(transport).set_amplitude_vpp(
        channel,
        2.5,
        check_errors=False,
    )

    assert status.amplitude == 2.5
    assert status.amplitude_unit == "VPP"
    assert status.output == output
    assert transport.writes == [f"C{channel}:BSWV AMP,2.5"]
    assert transport.queries == [
        "*IDN?",
        *_configuration_queries(channel),
        *_configuration_queries(channel),
    ]


def test_set_amplitude_is_idempotent_with_full_safety_snapshot() -> None:
    transport = StatefulOutputTransport()

    status = SDG2000XSource(transport).set_amplitude_vpp(
        1,
        4.0000004,
        check_errors=False,
    )

    assert status.amplitude == 4.0
    assert transport.writes == []
    assert transport.queries == ["*IDN?", *_configuration_queries(1)]


@pytest.mark.parametrize(
    "value",
    [
        True,
        "1",
        None,
        float("nan"),
        float("inf"),
        0.0,
        -1.0,
        0.0019,
        10.0001,
    ],
)
def test_set_amplitude_rejects_invalid_values_before_io(value: object) -> None:
    transport = StatefulOutputTransport()

    with pytest.raises(DataError):
        SDG2000XSource(transport).set_amplitude_vpp(  # type: ignore[arg-type]
            1,
            value,
            check_errors=False,
        )

    assert transport.queries == []
    assert transport.writes == []


@pytest.mark.parametrize("channel", [0, 3, -1, True, "1"])
def test_set_amplitude_rejects_invalid_channels_before_io(channel: object) -> None:
    transport = StatefulOutputTransport()

    with pytest.raises(DataError, match="channel must be 1 or 2"):
        SDG2000XSource(transport).set_amplitude_vpp(  # type: ignore[arg-type]
            channel,
            1.0,
            check_errors=False,
        )

    assert transport.queries == []
    assert transport.writes == []


@pytest.mark.parametrize("check_errors", [True, 1, "false", None])
def test_set_amplitude_rejects_unavailable_error_checks_before_io(
    check_errors: object,
) -> None:
    transport = StatefulOutputTransport()

    with pytest.raises(DataError, match="check_errors"):
        SDG2000XSource(transport).set_amplitude_vpp(  # type: ignore[arg-type]
            1,
            1.0,
            check_errors=check_errors,
        )

    assert transport.queries == []
    assert transport.writes == []


@pytest.mark.parametrize(
    "basic",
    [
        "C1:BSWV WVTP,NOISE,STDEV,1V,MEAN,0V,BANDSTATE,OFF,BANDWIDTH,120MHZ",
        "C1:BSWV WVTP,DC,OFST,0V",
    ],
)
def test_set_amplitude_rejects_inapplicable_functions(basic: str) -> None:
    transport = StatefulOutputTransport()
    transport.basics[1] = basic

    with pytest.raises(DataError, match="not applicable"):
        SDG2000XSource(transport).set_amplitude_vpp(1, 1.0, check_errors=False)

    assert transport.writes == []


def test_set_amplitude_rejects_sweep_and_unsafe_voltage_envelope() -> None:
    sweep_transport = StatefulOutputTransport()
    sweep_transport.sweeps[1] = "ON"
    with pytest.raises(DataError, match="require FIX mode"):
        SDG2000XSource(sweep_transport).set_amplitude_vpp(
            1,
            1.0,
            check_errors=False,
        )
    assert sweep_transport.writes == []

    offset_transport = StatefulOutputTransport()
    offset_transport.basics[1] = (
        "C1:BSWV WVTP,SINE,FRQ,1KHZ,AMP,1V,OFST,9.5V,PHSE,0"
    )
    with pytest.raises(DataError, match="absolute voltage envelope"):
        SDG2000XSource(offset_transport).set_amplitude_vpp(
            1,
            2.0,
            check_errors=False,
        )
    assert offset_transport.writes == []


def test_set_amplitude_prewrite_query_failure_does_not_latch() -> None:
    transport = StatefulOutputTransport()
    transport.fail_query_counts["C1:HARM?"] = 1
    driver = SDG2000XSource(transport)

    with pytest.raises(InstrumentError, match="query failure"):
        driver.set_amplitude_vpp(1, 2.0, check_errors=False)

    assert transport.writes == []
    assert driver.configuration_writes_blocked is False


@pytest.mark.parametrize("failure", ["ignored", "ambiguous", "readback", "drift", "advanced"])
def test_set_amplitude_postwrite_failures_force_off_and_latch(failure: str) -> None:
    transport = StatefulOutputTransport()
    command = "C1:BSWV AMP,3"
    if failure == "ignored":
        transport.ignore_write_counts[command] = 1
    elif failure == "ambiguous":
        transport.fail_after_write_counts[command] = 1
    elif failure == "readback":
        transport.fail_readback_counts[command] = 1
    elif failure == "drift":
        transport.drift_write_counts[command] = 1
    else:
        transport.advanced_drift_write_counts[command] = 1
    driver = SDG2000XSource(transport)

    with pytest.raises(InstrumentError, match="confirmed OFF"):
        driver.set_amplitude_vpp(1, 3.0, check_errors=False)

    assert transport.outputs[1] == "OFF"
    assert transport.writes == [command, "C1:OUTP OFF"]
    assert driver.configuration_writes_blocked is True


def test_set_function_matches_the_core_source_driver_signature() -> None:
    signature = inspect.signature(SDG2000XSource.set_function)
    parameters = tuple(signature.parameters.values())

    assert tuple(parameter.name for parameter in parameters) == (
        "self",
        "channel",
        "function",
        "check_errors",
    )
    assert parameters[-1].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters[-1].default is True


@pytest.mark.parametrize(
    ("requested", "expected", "vendor"),
    [
        ("squ", "SQU", "SQUARE"),
        ("square", "SQU", "SQUARE"),
        ("ramp", "RAMP", "RAMP"),
        ("tri", "RAMP", "RAMP"),
        ("triangle", "RAMP", "RAMP"),
        ("puls", "PULS", "PULSE"),
        ("pulse", "PULS", "PULSE"),
        ("nois", "NOIS", "NOISE"),
        ("noise", "NOIS", "NOISE"),
        ("dc", "DC", "DC"),
    ],
)
def test_set_function_covers_every_public_alias(
    requested: str,
    expected: str,
    vendor: str,
) -> None:
    transport = StatefulOutputTransport()

    status = SDG2000XSource(transport).set_function(
        1,
        requested,
        check_errors=False,
    )

    assert status.function == expected
    assert status.output == "OFF"
    assert transport.writes == [f"C1:BSWV WVTP,{vendor}"]


@pytest.mark.parametrize("model", ["SDG2042X", "SDG2082X", "SDG2122X"])
@pytest.mark.parametrize("channel", [1, 2])
@pytest.mark.parametrize(
    ("requested", "expected", "vendor"),
    [
        ("square", "SQU", "SQUARE"),
        ("ramp", "RAMP", "RAMP"),
        ("pulse", "PULS", "PULSE"),
    ],
)
def test_set_function_preserves_live_output_for_bounded_periodic_waves(
    model: str,
    channel: int,
    requested: str,
    expected: str,
    vendor: str,
) -> None:
    transport = StatefulOutputTransport(model=model)
    transport.outputs[channel] = "ON"

    status = SDG2000XSource(transport).set_function(
        channel,
        requested,
        check_errors=False,
    )

    assert status.function == expected
    assert status.output == "ON"
    assert status.frequency_hz == 1_000.0
    assert status.amplitude == 4.0
    assert status.offset_v == 0.0
    assert transport.writes == [f"C{channel}:BSWV WVTP,{vendor}"]


def test_non_sine_transactions_do_not_send_the_inapplicable_harmonic_query() -> None:
    transport = StatefulOutputTransport()
    transport.basics[1] = (
        "C1:BSWV WVTP,SQUARE,FRQ,1KHZ,AMP,4V,OFST,0V,PHSE,0,DUTY,50"
    )
    transport.fail_query_counts["C1:HARM?"] = 1

    status = SDG2000XSource(transport).set_frequency(1, 2_000.0, check_errors=False)

    assert status.function == "SQU"
    assert status.frequency_hz == 2_000.0
    assert "C1:HARM?" not in transport.queries
    assert transport.fail_query_counts["C1:HARM?"] == 1


def test_switching_back_to_sine_detects_a_reactivated_harmonic_state() -> None:
    transport = StatefulOutputTransport()
    transport.basics[1] = (
        "C1:BSWV WVTP,SQUARE,FRQ,1KHZ,AMP,4V,OFST,0V,PHSE,0,DUTY,50"
    )
    transport.harmonic[1] = "ON"
    driver = SDG2000XSource(transport)

    with pytest.raises(InstrumentError, match="confirmed OFF"):
        driver.set_function(1, "sine", check_errors=False)

    assert transport.queries.count("C1:HARM?") == 1
    assert transport.writes == ["C1:BSWV WVTP,SINE", "C1:OUTP OFF"]
    assert driver.configuration_writes_blocked is True


@pytest.mark.parametrize("requested", ["sin", "sine", " SIN "])
def test_set_function_is_idempotent_for_sine_aliases(requested: str) -> None:
    transport = StatefulOutputTransport()

    status = SDG2000XSource(transport).set_function(
        1,
        requested,
        check_errors=False,
    )

    assert status.function == "SIN"
    assert transport.writes == []
    assert transport.queries == ["*IDN?", *_configuration_queries(1)]


def test_set_function_can_leave_noise_for_a_safe_periodic_wave_while_off() -> None:
    transport = StatefulOutputTransport()
    transport.basics[1] = (
        "C1:BSWV WVTP,NOISE,STDEV,1V,MEAN,0V,BANDSTATE,OFF,BANDWIDTH,120MHZ"
    )

    status = SDG2000XSource(transport).set_function(1, "sine", check_errors=False)

    assert status.function == "SIN"
    assert status.frequency_hz == 1_000.0
    assert status.amplitude == 1.0
    assert status.output == "OFF"


@pytest.mark.parametrize("function", ["", "arb", "user", "harm", "sin;*rst", 1, None])
def test_set_function_rejects_unknown_or_non_string_values_before_io(
    function: object,
) -> None:
    transport = StatefulOutputTransport()

    with pytest.raises(DataError, match="function must be one of"):
        SDG2000XSource(transport).set_function(  # type: ignore[arg-type]
            1,
            function,
            check_errors=False,
        )

    assert transport.queries == []
    assert transport.writes == []


@pytest.mark.parametrize("channel", [0, 3, -1, True, "1"])
def test_set_function_rejects_invalid_channels_before_io(channel: object) -> None:
    transport = StatefulOutputTransport()

    with pytest.raises(DataError, match="channel must be 1 or 2"):
        SDG2000XSource(transport).set_function(  # type: ignore[arg-type]
            channel,
            "sine",
            check_errors=False,
        )

    assert transport.queries == []
    assert transport.writes == []


@pytest.mark.parametrize("check_errors", [True, 1, "false", None])
def test_set_function_rejects_unavailable_error_checks_before_io(
    check_errors: object,
) -> None:
    transport = StatefulOutputTransport()

    with pytest.raises(DataError, match="check_errors"):
        SDG2000XSource(transport).set_function(  # type: ignore[arg-type]
            1,
            "square",
            check_errors=check_errors,
        )

    assert transport.queries == []
    assert transport.writes == []


@pytest.mark.parametrize("target", ["noise", "dc"])
def test_set_function_requires_output_off_for_unbounded_targets(target: str) -> None:
    transport = StatefulOutputTransport()
    transport.outputs[1] = "ON"

    with pytest.raises(DataError, match="require output OFF"):
        SDG2000XSource(transport).set_function(1, target, check_errors=False)

    assert transport.writes == []


def test_set_function_enforces_target_frequency_limit_before_write() -> None:
    transport = StatefulOutputTransport()
    transport.basics[1] = (
        "C1:BSWV WVTP,SINE,FRQ,30MHZ,AMP,1V,OFST,0V,PHSE,0"
    )

    with pytest.raises(DataError, match="frequency exceeds"):
        SDG2000XSource(transport).set_function(1, "square", check_errors=False)

    assert transport.writes == []


def test_set_function_rejects_sweep_and_advanced_modes_before_write() -> None:
    sweep_transport = StatefulOutputTransport()
    sweep_transport.sweeps[1] = "ON"
    with pytest.raises(DataError, match="require FIX mode"):
        SDG2000XSource(sweep_transport).set_function(1, "square", check_errors=False)
    assert sweep_transport.writes == []

    harmonic_transport = StatefulOutputTransport()
    harmonic_transport.harmonic[1] = "ON"
    with pytest.raises(DataError, match="advanced signal modes OFF"):
        SDG2000XSource(harmonic_transport).set_function(
            1,
            "square",
            check_errors=False,
        )
    assert harmonic_transport.writes == []


@pytest.mark.parametrize("failure", ["ignored", "ambiguous", "readback", "drift", "advanced"])
def test_set_function_postwrite_failures_force_off_and_latch(failure: str) -> None:
    transport = StatefulOutputTransport()
    command = "C1:BSWV WVTP,SQUARE"
    if failure == "ignored":
        transport.ignore_write_counts[command] = 1
    elif failure == "ambiguous":
        transport.fail_after_write_counts[command] = 1
    elif failure == "readback":
        transport.fail_readback_counts[command] = 1
    elif failure == "drift":
        transport.drift_write_counts[command] = 1
    else:
        transport.advanced_drift_write_counts[command] = 1
    driver = SDG2000XSource(transport)

    with pytest.raises(InstrumentError, match="confirmed OFF"):
        driver.set_function(1, "square", check_errors=False)

    assert transport.outputs[1] == "OFF"
    assert transport.writes == [command, "C1:OUTP OFF"]
    assert driver.configuration_writes_blocked is True


def test_set_square_duty_matches_the_core_source_driver_signature() -> None:
    signature = inspect.signature(SDG2000XSource.set_square_duty_cycle)
    parameters = tuple(signature.parameters.values())

    assert tuple(parameter.name for parameter in parameters) == (
        "self",
        "channel",
        "duty_percent",
        "check_errors",
    )
    assert parameters[-1].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters[-1].default is True


@pytest.mark.parametrize("model", ["SDG2042X", "SDG2082X", "SDG2122X"])
@pytest.mark.parametrize("channel", [1, 2])
@pytest.mark.parametrize("output", ["OFF", "ON"])
def test_set_square_duty_covers_models_channels_and_live_output(
    model: str,
    channel: int,
    output: str,
) -> None:
    transport = StatefulOutputTransport(model=model)
    transport.outputs[channel] = output
    transport.basics[channel] = (
        f"C{channel}:BSWV WVTP,SQUARE,FRQ,1KHZ,AMP,4V,OFST,0V,"
        "PHSE,0,DUTY,50"
    )

    status = SDG2000XSource(transport).set_square_duty_cycle(
        channel,
        25.0,
        check_errors=False,
    )

    assert status.function == "SQU"
    assert status.square_duty_cycle_percent == 25.0
    assert status.output == output
    assert transport.writes == [f"C{channel}:BSWV DUTY,25"]
    assert f"C{channel}:HARM?" not in transport.queries


@pytest.mark.parametrize("duty_percent", [0.001, 99.999])
def test_set_square_duty_accepts_documented_global_boundaries(
    duty_percent: float,
) -> None:
    transport = StatefulOutputTransport()
    transport.basics[1] = (
        "C1:BSWV WVTP,SQUARE,FRQ,1KHZ,AMP,4V,OFST,0V,PHSE,0,DUTY,50"
    )

    status = SDG2000XSource(transport).set_square_duty_cycle(
        1,
        duty_percent,
        check_errors=False,
    )

    assert status.square_duty_cycle_percent == duty_percent


def test_set_square_duty_is_idempotent_with_full_safety_snapshot() -> None:
    transport = StatefulOutputTransport()
    transport.basics[1] = (
        "C1:BSWV WVTP,SQUARE,FRQ,1KHZ,AMP,4V,OFST,0V,PHSE,0,DUTY,50"
    )

    status = SDG2000XSource(transport).set_square_duty_cycle(
        1,
        50.0000004,
        check_errors=False,
    )

    assert status.square_duty_cycle_percent == 50.0
    assert transport.writes == []


@pytest.mark.parametrize(
    "value",
    [
        True,
        "50",
        None,
        float("nan"),
        float("inf"),
        0.0,
        -1.0,
        0.0009,
        100.0,
        99.9991,
    ],
)
def test_set_square_duty_rejects_invalid_values_before_io(value: object) -> None:
    transport = StatefulOutputTransport()

    with pytest.raises(DataError):
        SDG2000XSource(transport).set_square_duty_cycle(  # type: ignore[arg-type]
            1,
            value,
            check_errors=False,
        )

    assert transport.queries == []
    assert transport.writes == []


@pytest.mark.parametrize("channel", [0, 3, -1, True, "1"])
def test_set_square_duty_rejects_invalid_channels_before_io(channel: object) -> None:
    transport = StatefulOutputTransport()

    with pytest.raises(DataError, match="channel must be 1 or 2"):
        SDG2000XSource(transport).set_square_duty_cycle(  # type: ignore[arg-type]
            channel,
            50.0,
            check_errors=False,
        )

    assert transport.queries == []
    assert transport.writes == []


@pytest.mark.parametrize("check_errors", [True, 1, "false", None])
def test_set_square_duty_rejects_unavailable_error_checks_before_io(
    check_errors: object,
) -> None:
    transport = StatefulOutputTransport()

    with pytest.raises(DataError, match="check_errors"):
        SDG2000XSource(transport).set_square_duty_cycle(  # type: ignore[arg-type]
            1,
            50.0,
            check_errors=check_errors,
        )

    assert transport.queries == []
    assert transport.writes == []


def test_set_square_duty_requires_square_fix_mode_and_advanced_modes_off() -> None:
    sine_transport = StatefulOutputTransport()
    with pytest.raises(DataError, match="require the SQUARE function"):
        SDG2000XSource(sine_transport).set_square_duty_cycle(
            1,
            25.0,
            check_errors=False,
        )
    assert sine_transport.writes == []

    sweep_transport = StatefulOutputTransport()
    sweep_transport.basics[1] = (
        "C1:BSWV WVTP,SQUARE,FRQ,1KHZ,AMP,4V,OFST,0V,PHSE,0,DUTY,50"
    )
    sweep_transport.sweeps[1] = "ON"
    with pytest.raises(DataError, match="require FIX mode"):
        SDG2000XSource(sweep_transport).set_square_duty_cycle(
            1,
            25.0,
            check_errors=False,
        )
    assert sweep_transport.writes == []

    advanced_transport = StatefulOutputTransport()
    advanced_transport.basics[1] = (
        "C1:BSWV WVTP,SQUARE,FRQ,1KHZ,AMP,4V,OFST,0V,PHSE,0,DUTY,50"
    )
    advanced_transport.burst[1] = "ON"
    with pytest.raises(DataError, match="advanced signal modes OFF"):
        SDG2000XSource(advanced_transport).set_square_duty_cycle(
            1,
            25.0,
            check_errors=False,
        )
    assert advanced_transport.writes == []


@pytest.mark.parametrize("failure", ["ignored", "ambiguous", "readback", "drift", "advanced"])
def test_set_square_duty_postwrite_failures_force_off_and_latch(failure: str) -> None:
    transport = StatefulOutputTransport()
    transport.basics[1] = (
        "C1:BSWV WVTP,SQUARE,FRQ,1KHZ,AMP,4V,OFST,0V,PHSE,0,DUTY,50"
    )
    command = "C1:BSWV DUTY,25"
    if failure == "ignored":
        transport.ignore_write_counts[command] = 1
    elif failure == "ambiguous":
        transport.fail_after_write_counts[command] = 1
    elif failure == "readback":
        transport.fail_readback_counts[command] = 1
    elif failure == "drift":
        transport.drift_write_counts[command] = 1
    else:
        transport.advanced_drift_write_counts[command] = 1
    driver = SDG2000XSource(transport)

    with pytest.raises(InstrumentError, match="confirmed OFF"):
        driver.set_square_duty_cycle(1, 25.0, check_errors=False)

    assert transport.outputs[1] == "OFF"
    assert transport.writes == [command, "C1:OUTP OFF"]
    assert driver.configuration_writes_blocked is True


@pytest.mark.parametrize("model", ["SDG2042X", "SDG2082X", "SDG2122X"])
def test_set_output_is_enabled_for_every_registered_model(model: str) -> None:
    transport = StatefulOutputTransport(model=model)

    status = SDG2000XSource(transport).set_output(1, True, check_errors=False)

    assert status.output == "ON"
    assert transport.outputs == {1: "ON", 2: "OFF"}
    assert transport.writes == ["C1:OUTP ON"]


@pytest.mark.parametrize(
    ("channel", "initial", "enabled", "target"),
    [
        (1, "OFF", True, "ON"),
        (1, "ON", False, "OFF"),
        (2, "OFF", True, "ON"),
        (2, "ON", False, "OFF"),
    ],
)
def test_set_output_covers_both_channels_and_both_transitions(
    channel: int,
    initial: str,
    enabled: bool,
    target: str,
) -> None:
    transport = StatefulOutputTransport()
    transport.outputs[channel] = initial

    status = SDG2000XSource(transport).set_output(
        channel,
        enabled,
        check_errors=False,
    )

    assert status.channel == channel
    assert status.output == target
    assert transport.outputs[channel] == target
    assert transport.writes == [f"C{channel}:OUTP {target}"]
    expected_queries = [
        "*IDN?",
        f"C{channel}:OUTP?",
        f"C{channel}:BSWV?",
        f"C{channel}:SWWV?",
    ]
    if enabled:
        expected_queries.extend(_output_safety_queries(channel))
    expected_queries.extend(
        [
        f"C{channel}:OUTP?",
        f"C{channel}:BSWV?",
        f"C{channel}:SWWV?",
        ]
    )
    if enabled:
        expected_queries.extend(_output_safety_queries(channel))
    assert transport.queries == expected_queries


@pytest.mark.parametrize(("initial", "enabled"), [("OFF", False), ("ON", True)])
def test_set_output_is_idempotent_without_a_write(initial: str, enabled: bool) -> None:
    transport = StatefulOutputTransport()
    transport.outputs[1] = initial

    status = SDG2000XSource(transport).set_output(1, enabled, check_errors=False)

    assert status.output == initial
    assert transport.writes == []
    assert transport.queries == [
        "*IDN?",
        "C1:OUTP?",
        "C1:BSWV?",
        "C1:SWWV?",
        *(_output_safety_queries(1) if enabled else []),
    ]


@pytest.mark.parametrize("channel", [0, 3, -1, True, "1"])
def test_set_output_rejects_invalid_channels_before_io(channel: object) -> None:
    transport = StatefulOutputTransport()

    with pytest.raises(DataError, match="channel must be 1 or 2"):
        SDG2000XSource(transport).set_output(  # type: ignore[arg-type]
            channel,
            True,
            check_errors=False,
        )

    assert transport.queries == []
    assert transport.writes == []


@pytest.mark.parametrize("enabled", [0, 1, "ON", None])
def test_set_output_rejects_non_boolean_state_before_io(enabled: object) -> None:
    transport = StatefulOutputTransport()

    with pytest.raises(DataError, match="enabled must be a boolean"):
        SDG2000XSource(transport).set_output(  # type: ignore[arg-type]
            1,
            enabled,
            check_errors=False,
        )

    assert transport.queries == []
    assert transport.writes == []


@pytest.mark.parametrize("check_errors", [True, 1, "false", None])
def test_set_output_rejects_unavailable_or_invalid_error_checks_before_io(
    check_errors: object,
) -> None:
    transport = StatefulOutputTransport()

    with pytest.raises(DataError, match="check_errors"):
        SDG2000XSource(transport).set_output(  # type: ignore[arg-type]
            1,
            True,
            check_errors=check_errors,
        )

    assert transport.queries == []
    assert transport.writes == []


@pytest.mark.parametrize("unsafe_state", ["sweep", "dc"])
def test_output_enable_rejects_an_unbounded_snapshot_before_write(
    unsafe_state: str,
) -> None:
    transport = StatefulOutputTransport()
    if unsafe_state == "sweep":
        transport.sweeps[1] = "ON"
    else:
        transport.basics[1] = "C1:BSWV WVTP,DC,OFST,0V"

    with pytest.raises(DataError, match="requires"):
        SDG2000XSource(transport).set_output(1, True, check_errors=False)

    assert transport.outputs[1] == "OFF"
    assert transport.writes == []


@pytest.mark.parametrize(
    "unsafe_mode",
    [
        "modulation",
        "burst",
        "harmonic",
        "combine",
        "noise_add",
        "TRACE",
        "TRDUCH",
        "FCOUP",
        "PCOUP",
        "ACOUP",
    ],
)
def test_output_enable_rejects_every_advanced_signal_mode_before_write(
    unsafe_mode: str,
) -> None:
    transport = StatefulOutputTransport()
    if unsafe_mode in {"TRACE", "TRDUCH", "FCOUP", "PCOUP", "ACOUP"}:
        transport.coupling[unsafe_mode] = "ON"
    else:
        getattr(transport, unsafe_mode)[1] = "ON"

    with pytest.raises(DataError, match="advanced signal modes OFF"):
        SDG2000XSource(transport).set_output(1, True, check_errors=False)

    assert transport.outputs[1] == "OFF"
    assert transport.writes == []


def test_output_enable_accepts_a_complete_disabled_harmonic_response() -> None:
    transport = StatefulOutputTransport()
    transport.query_overrides["C1:HARM?"] = (
        "C1:HARM HARMSTATE,OFF,HARMTYPE,ALL,HARMORDER,16,HARMAMP,0V,"
        "HARMDBC,-80dBc,HARMPHASE,360"
    )

    status = SDG2000XSource(transport).set_output(1, True, check_errors=False)

    assert status.output == "ON"
    assert transport.writes == ["C1:OUTP ON"]


@pytest.mark.parametrize(
    "response",
    [
        "C1:HARM HARMSTATE,OFF,HARMTYPE,EVEN",
        "C1:HARM HARMSTATE,ON,HARMTYPE,USER,HARMORDER,2,HARMAMP,0V,HARMDBC,-80dBc,HARMPHASE,0",
        "C1:HARM HARMSTATE,ON,HARMTYPE,EVEN,HARMORDER,1.5,HARMAMP,0V,HARMDBC,-80dBc,HARMPHASE,0",
        "C1:HARM HARMSTATE,ON,HARMTYPE,EVEN,HARMORDER,17,HARMAMP,0V,HARMDBC,-80dBc,HARMPHASE,0",
        "C1:HARM HARMSTATE,ON,HARMTYPE,EVEN,HARMORDER,2,HARMAMP,-1V,HARMDBC,-80dBc,HARMPHASE,0",
        "C1:HARM HARMSTATE,ON,HARMTYPE,EVEN,HARMORDER,2,HARMAMP,21V,HARMDBC,-80dBc,HARMPHASE,0",
        "C1:HARM HARMSTATE,ON,HARMTYPE,EVEN,HARMORDER,2,HARMAMP,1A,HARMDBC,-80dBc,HARMPHASE,0",
        "C1:HARM HARMSTATE,ON,HARMTYPE,EVEN,HARMORDER,2,HARMAMP,0V,HARMDBC,1dBc,HARMPHASE,0",
        "C1:HARM HARMSTATE,ON,HARMTYPE,EVEN,HARMORDER,2,HARMAMP,0V,HARMDBC,-201dBc,HARMPHASE,0",
        "C1:HARM HARMSTATE,ON,HARMTYPE,EVEN,HARMORDER,2,HARMAMP,0V,HARMDBC,-80dB,HARMPHASE,0",
        "C1:HARM HARMSTATE,ON,HARMTYPE,EVEN,HARMORDER,2,HARMAMP,0V,HARMDBC,-80dBc,HARMPHASE,361",
        "C1:HARM HARMSTATE,ON,HARMTYPE,EVEN,HARMORDER,2,HARMAMP,0V,HARMDBC,-80dBc,HARMPHASE,0,EXTRA,1",
    ],
)
def test_output_enable_strictly_validates_selected_harmonic_response(
    response: str,
) -> None:
    transport = StatefulOutputTransport()
    transport.query_overrides["C1:HARM?"] = response
    driver = SDG2000XSource(transport)

    with pytest.raises(DataError):
        driver.set_output(1, True, check_errors=False)

    assert transport.writes == []
    assert driver.configuration_writes_blocked is False


def test_output_enable_rejects_terminated_load_before_write() -> None:
    transport = StatefulOutputTransport()
    transport.loads[1] = "50OHM"

    with pytest.raises(DataError, match="high-impedance load"):
        SDG2000XSource(transport).set_output(1, True, check_errors=False)

    assert transport.outputs[1] == "OFF"
    assert transport.writes == []


@pytest.mark.parametrize(
    ("command", "response"),
    [
        ("C1:MDWV?", "C1:MDWV STATE,MAYBE"),
        ("C1:BTWV?", "C1:BTWV STATE,OFF,STATE,ON"),
        ("C1:HARM?", "C1:HARM HARMTYPE,EVEN"),
        ("C1:CMBN?", "C2:CMBN OFF"),
        ("C1:NOISE_ADD?", "C1:NOISE_ADD RATIO,100"),
        ("COUP?", "COUP TRACE,OFF,FCOUP,OFF,PCOUP,OFF"),
        ("COUP?", "COUP TRACE,OFF,FCOUP,OFF,PCOUP,OFF,ACOUP,MAYBE"),
    ],
)
def test_output_enable_rejects_malformed_advanced_state_before_write(
    command: str,
    response: str,
) -> None:
    transport = StatefulOutputTransport()
    transport.query_overrides[command] = response
    driver = SDG2000XSource(transport)

    with pytest.raises(DataError):
        driver.set_output(1, True, check_errors=False)

    assert transport.outputs[1] == "OFF"
    assert transport.writes == []
    assert driver.output_writes_blocked is False


def test_advanced_state_query_failure_before_write_does_not_latch() -> None:
    transport = StatefulOutputTransport()
    transport.fail_query_counts["C1:HARM?"] = 1
    driver = SDG2000XSource(transport)

    with pytest.raises(InstrumentError, match="query failure"):
        driver.set_output(1, True, check_errors=False)

    assert transport.outputs[1] == "OFF"
    assert transport.writes == []
    assert driver.output_writes_blocked is False


def test_output_readback_mismatch_forces_off_and_latches() -> None:
    transport = StatefulOutputTransport()
    transport.ignore_write_counts["C1:OUTP ON"] = 1
    driver = SDG2000XSource(transport)

    with pytest.raises(InstrumentError, match="confirmed OFF"):
        driver.set_output(1, True, check_errors=False)

    assert transport.outputs[1] == "OFF"
    assert transport.writes == ["C1:OUTP ON", "C1:OUTP OFF"]
    assert driver.output_writes_blocked is True

    io_counts = (len(transport.queries), len(transport.writes))
    with pytest.raises(InstrumentError, match="writes are blocked"):
        driver.set_output(1, True, check_errors=False)
    assert (len(transport.queries), len(transport.writes)) == io_counts

    assert driver.set_output(1, False, check_errors=False).output == "OFF"
    assert transport.writes[-1] == "C1:OUTP OFF"


def test_output_ambiguous_write_forces_off_and_latches() -> None:
    transport = StatefulOutputTransport()
    transport.fail_after_write_counts["C1:OUTP ON"] = 1
    driver = SDG2000XSource(transport)

    with pytest.raises(InstrumentError, match="confirmed OFF"):
        driver.set_output(1, True, check_errors=False)

    assert transport.outputs[1] == "OFF"
    assert transport.writes == ["C1:OUTP ON", "C1:OUTP OFF"]
    assert driver.output_writes_blocked is True


def test_output_readback_failure_forces_off_and_latches() -> None:
    transport = StatefulOutputTransport()
    transport.fail_readback_counts["C1:OUTP ON"] = 1
    driver = SDG2000XSource(transport)

    with pytest.raises(InstrumentError, match="confirmed OFF"):
        driver.set_output(1, True, check_errors=False)

    assert transport.outputs[1] == "OFF"
    assert transport.writes == ["C1:OUTP ON", "C1:OUTP OFF"]
    assert driver.output_writes_blocked is True


def test_output_non_output_drift_forces_off_and_latches() -> None:
    transport = StatefulOutputTransport()
    transport.drift_write_counts["C1:OUTP ON"] = 1
    driver = SDG2000XSource(transport)

    with pytest.raises(InstrumentError, match="confirmed OFF"):
        driver.set_output(1, True, check_errors=False)

    assert transport.outputs[1] == "OFF"
    assert transport.writes == ["C1:OUTP ON", "C1:OUTP OFF"]
    assert driver.output_writes_blocked is True


def test_output_advanced_state_drift_forces_off_and_latches() -> None:
    transport = StatefulOutputTransport()
    transport.advanced_drift_write_counts["C1:OUTP ON"] = 1
    driver = SDG2000XSource(transport)

    with pytest.raises(InstrumentError, match="confirmed OFF"):
        driver.set_output(1, True, check_errors=False)

    assert transport.outputs[1] == "OFF"
    assert transport.writes == ["C1:OUTP ON", "C1:OUTP OFF"]
    assert driver.output_writes_blocked is True


def test_output_disable_failure_uses_one_off_recovery_and_latches() -> None:
    transport = StatefulOutputTransport()
    transport.outputs[2] = "ON"
    transport.ignore_write_counts["C2:OUTP OFF"] = 1
    driver = SDG2000XSource(transport)

    with pytest.raises(InstrumentError, match="confirmed OFF"):
        driver.set_output(2, False, check_errors=False)

    assert transport.outputs[2] == "OFF"
    assert transport.writes == ["C2:OUTP OFF", "C2:OUTP OFF"]
    assert driver.output_writes_blocked is True


def test_output_recovery_failure_reports_uncertain_state_and_latches() -> None:
    transport = StatefulOutputTransport()
    transport.fail_after_write_counts["C1:OUTP ON"] = 1
    transport.fail_before_write_counts["C1:OUTP OFF"] = 1
    driver = SDG2000XSource(transport)

    with pytest.raises(InstrumentError, match="state is uncertain"):
        driver.set_output(1, True, check_errors=False)

    assert transport.outputs[1] == "ON"
    assert transport.writes == ["C1:OUTP ON", "C1:OUTP OFF"]
    assert driver.output_writes_blocked is True

    io_counts = (len(transport.queries), len(transport.writes))
    with pytest.raises(InstrumentError, match="writes are blocked"):
        driver.set_output(1, True, check_errors=False)
    assert (len(transport.queries), len(transport.writes)) == io_counts


def test_prewrite_snapshot_failure_does_not_write_or_latch() -> None:
    transport = StatefulOutputTransport()
    transport.fail_query_counts["C1:BSWV?"] = 1
    driver = SDG2000XSource(transport)

    with pytest.raises(InstrumentError, match="query failure"):
        driver.set_output(1, True, check_errors=False)

    assert transport.writes == []
    assert driver.output_writes_blocked is False


def _source_service(driver: SDG2000XSource, *, max_source_vpp: float) -> SourceService:
    config = SimpleNamespace(
        source=SimpleNamespace(
            resource="TCPIP::192.0.2.40::INSTR",
            driver="siglent.sdg2000x",
            default_channel=1,
            check_errors=False,
        ),
        safety_limits=SimpleNamespace(max_source_vpp=max_source_vpp),
    )
    return SourceService(config=config, logger=CommandLogger(), session=driver)


def test_core_source_service_allows_output_at_the_10_vpp_boundary() -> None:
    transport = StatefulOutputTransport()
    transport.basics[1] = "C1:BSWV WVTP,SINE,FRQ,1KHZ,AMP,10V,OFST,0V,PHSE,0"
    service = _source_service(SDG2000XSource(transport), max_source_vpp=10.0)

    with patch.object(service, "_require"):
        status = service.set_output(channel=1, enabled=True)

    assert status.output == "ON"
    assert transport.writes == ["C1:OUTP ON"]


def test_core_source_service_rejects_output_above_10_vpp_before_write() -> None:
    transport = StatefulOutputTransport()
    transport.basics[1] = (
        "C1:BSWV WVTP,SINE,FRQ,1KHZ,AMP,10.0001V,OFST,0V,PHSE,0"
    )
    service = _source_service(SDG2000XSource(transport), max_source_vpp=10.0)

    with patch.object(service, "_require"), pytest.raises(ConfigError, match="max_source_vpp"):
        service.set_output(channel=1, enabled=True)

    assert transport.outputs[1] == "OFF"
    assert transport.writes == []
