from __future__ import annotations

import pytest

from wavebench.errors import ConfigError, DataError, InstrumentError
from wavebench.instruments import DriverContext
from wavebench.instruments.capabilities import validate_declared_capabilities
from wavebench.instruments.models import ScopeChannelInputStateV2
from wavebench.instruments.scope_extensions import ScopeWaveformBinaryProfile
from wavebench.logging import CommandLogger
from wavebench.services.scope_service import assert_scope_high_impedance
from wavebench_rigol_mso8000 import descriptor as plugin_descriptor
from wavebench_rigol_mso8000.driver import MSO8104Scope
from wavebench_rigol_mso8000.parsers import RigolIdentity, parse_mso8104_identity


class FakeTransport:
    def __init__(self, responses: dict[str, str] | None = None):
        self.responses = responses or {}
        self.queries: list[str] = []
        self.close_calls = 0

    def query(self, command: str) -> str:
        self.queries.append(command)
        return self.responses[command]

    def close(self) -> None:
        self.close_calls += 1


def test_descriptor_is_executable_v2_metadata_without_io() -> None:
    descriptor = plugin_descriptor()

    assert descriptor.driver_id == "rigol.mso8104"
    assert descriptor.api_version == "wavebench.instrument.v2"
    assert descriptor.models == ("MSO8104",)
    assert descriptor.aliases == ()
    assert descriptor.capabilities == (
        "scope.idn",
        "scope.fetch_waveform",
        "scope.channel_coupling",
        "scope.channel_input_state_v2",
        "scope.autoscale",
        "scope.math_metadata",
        "scope.cursor_readout",
    )
    assert descriptor.backends == ("pyvisa",)
    assert descriptor.resource_schemes == ("tcpip", "usb", "gpib")
    assert descriptor.scope_coupling_policy == "switchable-termination"
    assert descriptor.wavebench_min_version == "0.8.24"
    assert descriptor.wavebench_max_version == "0.9.0"
    assert descriptor.version == "0.9.0"
    assert descriptor.scope_extensions is not None
    profile = descriptor.scope_extensions.waveform_binary_profile
    assert isinstance(profile, ScopeWaveformBinaryProfile)
    assert profile.transport_trailing == b"\n"
    assert len(profile.operations) == 1
    assert profile.operations[0].operation_kind == "fetch"
    assert profile.operations[0].response_max_bytes == 1_000
    assert profile.operations[0].operation_max_bytes == 1_000
    assert profile.operations[0].query_max_count == 1
    assert profile.operations[0].resynchronization_max_bytes == 65_536
    assert profile.operations[0].restore_order == (
        "scope.waveform_source",
        "scope.waveform_mode",
        "scope.waveform_format",
        "scope.waveform_points",
        "scope.waveform_transfer_window",
    )
    assert descriptor.validate_options({}) == {
        "max_total_points": 4_000_000,
        "max_chunk_points": 250_000,
    }


def test_factory_opens_exactly_one_core_transport_without_instrument_io() -> None:
    descriptor = plugin_descriptor()
    transport = FakeTransport()
    open_calls = 0

    def open_transport() -> FakeTransport:
        nonlocal open_calls
        open_calls += 1
        return transport

    context = DriverContext(
        driver_id=descriptor.driver_id,
        kind="scope",
        resource="TCPIP0::192.0.2.10::INSTR",
        backend="pyvisa",
        timeout_ms=1000,
        opc_timeout_ms=2000,
        logger=CommandLogger(),
        _transport_factory=open_transport,
    )

    driver = descriptor.factory(context)

    assert open_calls == 1
    assert driver.transport is transport
    assert driver.acquisition_timeout_s == 2.0
    assert driver.max_total_waveform_points == 4_000_000
    assert driver.max_byte_points_per_read == 250_000
    assert transport.queries == []
    validate_declared_capabilities(descriptor, driver)


@pytest.mark.parametrize(
    "options",
    [
        {"max_total_points": True},
        {"max_total_points": 4_000_001},
        {"max_chunk_points": 0},
        {"max_chunk_points": 1.0},
    ],
)
def test_factory_rejects_invalid_integer_options_before_open(
    options: dict[str, object],
) -> None:
    descriptor = plugin_descriptor()
    open_calls = 0

    def open_transport() -> FakeTransport:
        nonlocal open_calls
        open_calls += 1
        return FakeTransport()

    context = DriverContext(
        driver_id=descriptor.driver_id,
        kind="scope",
        resource="TCPIP0::192.0.2.10::INSTR",
        backend="pyvisa",
        timeout_ms=1000,
        opc_timeout_ms=2000,
        logger=CommandLogger(),
        _transport_factory=open_transport,
        options=options,
    )

    with pytest.raises(DataError, match="option"):
        descriptor.factory(context)

    assert open_calls == 0


def test_idn_validates_target_and_preserves_trimmed_response() -> None:
    response = "RIGOL TECHNOLOGIES,MSO8104,MSO8A000000000,00.01.02.03\n"
    transport = FakeTransport({"*IDN?": response})
    scope = MSO8104Scope(transport=transport)

    assert scope.idn() == response.strip()
    assert transport.queries == ["*IDN?"]


def test_identity_parser_splits_only_the_first_three_commas() -> None:
    identity = parse_mso8104_identity(
        "RIGOL TECHNOLOGIES,MSO8104,MSO8A000000000,00.01,build"
    )

    assert identity == RigolIdentity(
        manufacturer="RIGOL TECHNOLOGIES",
        model="MSO8104",
        serial_number="MSO8A000000000",
        firmware="00.01,build",
    )


@pytest.mark.parametrize(
    ("response", "message"),
    [
        ("", "invalid"),
        ("RIGOL TECHNOLOGIES,MSO8104,SERIAL", "invalid"),
        ("RIGOL TECHNOLOGIES,MSO8104,,00.01", "invalid"),
        ("OTHER,MSO8104,SERIAL,00.01", "manufacturer"),
        ("RIGOL TECHNOLOGIES,MSO8204,SERIAL,00.01", "model"),
    ],
)
def test_identity_parser_rejects_malformed_or_wrong_instruments(
    response: str,
    message: str,
) -> None:
    with pytest.raises(DataError, match=message):
        parse_mso8104_identity(response)


@pytest.mark.parametrize(
    ("coupling", "impedance", "expected"),
    [
        ("AC", "OMEG", "ACL"),
        ("DC", "OMEG", "DCL"),
        ("AC", "FIFT", "AC"),
        ("DC", "FIFT", "DC"),
        ("GND", "OMEG", "GND"),
        ("GND", "FIFT", "GND"),
    ],
)
def test_channel_coupling_combines_coupling_and_termination(
    coupling: str,
    impedance: str,
    expected: str,
) -> None:
    transport = FakeTransport(
        {
            ":CHANnel2:COUPling?": f" {coupling.lower()}\n",
            ":CHANnel2:IMPedance?": f" {impedance.lower()}\n",
        }
    )
    scope = MSO8104Scope(transport=transport)

    assert scope.channel_coupling(2) == expected
    assert transport.queries == [
        ":CHANnel2:COUPling?",
        ":CHANnel2:IMPedance?",
    ]


@pytest.mark.parametrize(
    ("coupling", "impedance", "expected"),
    [
        (
            "AC",
            "OMEG",
            ScopeChannelInputStateV2(
                channel=2,
                coupling="ac",
                termination="high_z",
                impedance_ohm=1_000_000.0,
            ),
        ),
        (
            "DC",
            "OMEG",
            ScopeChannelInputStateV2(
                channel=2,
                coupling="dc",
                termination="high_z",
                impedance_ohm=1_000_000.0,
            ),
        ),
        (
            "GND",
            "OMEG",
            ScopeChannelInputStateV2(
                channel=2,
                coupling="gnd",
                termination="high_z",
                impedance_ohm=1_000_000.0,
            ),
        ),
        (
            "AC",
            "FIFT",
            ScopeChannelInputStateV2(
                channel=2,
                coupling="ac",
                termination="50_ohm",
                impedance_ohm=50.0,
            ),
        ),
        (
            "DC",
            "FIFT",
            ScopeChannelInputStateV2(
                channel=2,
                coupling="dc",
                termination="50_ohm",
                impedance_ohm=50.0,
            ),
        ),
        (
            "GND",
            "FIFT",
            ScopeChannelInputStateV2(
                channel=2,
                coupling="gnd",
                termination="50_ohm",
                impedance_ohm=50.0,
            ),
        ),
    ],
)
def test_channel_input_state_v2_preserves_coupling_and_termination(
    coupling: str,
    impedance: str,
    expected: ScopeChannelInputStateV2,
) -> None:
    transport = FakeTransport(
        {
            ":CHANnel2:COUPling?": coupling,
            ":CHANnel2:IMPedance?": impedance,
        }
    )

    assert MSO8104Scope(transport=transport).get_channel_input_state_v2(2) == expected
    assert transport.queries == [
        ":CHANnel2:COUPling?",
        ":CHANnel2:IMPedance?",
    ]


@pytest.mark.parametrize("channel", [0, 5, -1, 1.0, True, "1", None])
def test_channel_coupling_rejects_invalid_channel_without_io(channel: object) -> None:
    transport = FakeTransport()
    scope = MSO8104Scope(transport=transport)

    with pytest.raises(DataError, match="integer from 1 through 4"):
        scope.channel_coupling(channel)  # type: ignore[arg-type]

    assert transport.queries == []


@pytest.mark.parametrize("channel", [0, 5, -1, 1.0, True, "1", None])
def test_channel_input_state_v2_rejects_invalid_channel_without_io(channel: object) -> None:
    transport = FakeTransport()

    with pytest.raises(DataError, match="integer from 1 through 4"):
        MSO8104Scope(transport=transport).get_channel_input_state_v2(channel)  # type: ignore[arg-type]

    assert transport.queries == []


@pytest.mark.parametrize("response", ["", "ACL", "UNKNOWN", "DC,AC"])
def test_channel_coupling_rejects_unknown_coupling(response: str) -> None:
    transport = FakeTransport(
        {
            ":CHANnel1:COUPling?": response,
            ":CHANnel1:IMPedance?": "OMEG",
        }
    )

    with pytest.raises(DataError, match="channel coupling"):
        MSO8104Scope(transport=transport).channel_coupling(1)

    assert transport.queries == [
        ":CHANnel1:COUPling?",
        ":CHANnel1:IMPedance?",
    ]


@pytest.mark.parametrize("response", ["", "50", "FIFTY", "UNKNOWN"])
def test_channel_coupling_rejects_unknown_impedance(response: str) -> None:
    transport = FakeTransport(
        {
            ":CHANnel3:COUPling?": "DC",
            ":CHANnel3:IMPedance?": response,
        }
    )

    with pytest.raises(DataError, match="channel impedance"):
        MSO8104Scope(transport=transport).channel_coupling(3)

    assert transport.queries == [
        ":CHANnel3:COUPling?",
        ":CHANnel3:IMPedance?",
    ]


@pytest.mark.parametrize(
    ("coupling", "impedance", "message"),
    [
        ("UNKNOWN", "OMEG", "channel coupling"),
        ("DC", "UNKNOWN", "channel impedance"),
    ],
)
def test_channel_input_state_v2_rejects_unknown_response(
    coupling: str,
    impedance: str,
    message: str,
) -> None:
    transport = FakeTransport(
        {
            ":CHANnel1:COUPling?": coupling,
            ":CHANnel1:IMPedance?": impedance,
        }
    )

    with pytest.raises(DataError, match=message):
        MSO8104Scope(transport=transport).get_channel_input_state_v2(1)

    assert transport.queries == [
        ":CHANnel1:COUPling?",
        ":CHANnel1:IMPedance?",
    ]


def test_core_guard_accepts_only_high_impedance_mapping_by_default() -> None:
    assert (
        assert_scope_high_impedance(
            "DCL",
            channel=1,
            coupling_policy="switchable-termination",
        )
        == "DCL"
    )
    with pytest.raises(ConfigError, match="50 ohm"):
        assert_scope_high_impedance(
            "DC",
            channel=1,
            coupling_policy="switchable-termination",
        )
    with pytest.raises(ConfigError, match="not recognized"):
        assert_scope_high_impedance(
            "GND",
            channel=1,
            coupling_policy="switchable-termination",
        )


class AutoscaleTransport(FakeTransport):
    def __init__(self, enabled_response: str = "1") -> None:
        super().__init__({":SYSTem:AUToscale?": enabled_response})
        self.writes: list[str] = []
        self.opc_calls = 0
        self.opc_response = "1"
        self.write_error: Exception | None = None
        self.opc_error: Exception | None = None

    def write(self, command: str) -> None:
        self.writes.append(command)
        if self.write_error is not None:
            raise self.write_error

    def query_opc(self) -> str:
        self.opc_calls += 1
        if self.opc_error is not None:
            raise self.opc_error
        return self.opc_response


def test_autoscale_preflights_enable_and_waits_once() -> None:
    transport = AutoscaleTransport()
    scope = MSO8104Scope(transport=transport)

    scope.autoscale(wait_opc=True, check_errors=False)

    assert transport.queries == [":SYSTem:AUToscale?"]
    assert transport.writes == [":AUToscale"]
    assert transport.opc_calls == 1
    assert scope.autoscale_writes_blocked is False


def test_autoscale_can_explicitly_skip_opc_wait() -> None:
    transport = AutoscaleTransport()

    MSO8104Scope(transport=transport).autoscale(
        wait_opc=False,
        check_errors=False,
    )

    assert transport.writes == [":AUToscale"]
    assert transport.opc_calls == 0


@pytest.mark.parametrize(
    ("wait_opc", "check_errors"),
    [(1, False), (True, 0), (True, True)],
)
def test_autoscale_rejects_unsupported_arguments_before_io(
    wait_opc: object,
    check_errors: object,
) -> None:
    transport = AutoscaleTransport()

    with pytest.raises((ConfigError, DataError)):
        MSO8104Scope(transport=transport).autoscale(
            wait_opc=wait_opc,  # type: ignore[arg-type]
            check_errors=check_errors,  # type: ignore[arg-type]
        )

    assert transport.queries == []
    assert transport.writes == []
    assert transport.opc_calls == 0


@pytest.mark.parametrize("enabled_response", ["0", "OFF", "", "2"])
def test_autoscale_refuses_disabled_or_invalid_preflight_without_write(
    enabled_response: str,
) -> None:
    transport = AutoscaleTransport(enabled_response)

    with pytest.raises((ConfigError, DataError)):
        MSO8104Scope(transport=transport).autoscale(
            wait_opc=True,
            check_errors=False,
        )

    assert transport.writes == []
    assert transport.opc_calls == 0


def test_autoscale_ambiguous_write_latches_only_autoscale_domain() -> None:
    transport = AutoscaleTransport()
    transport.write_error = InstrumentError("injected write failure")
    scope = MSO8104Scope(transport=transport)

    with pytest.raises(InstrumentError, match="write outcome is uncertain"):
        scope.autoscale(wait_opc=True, check_errors=False)

    assert scope.autoscale_writes_blocked is True
    assert scope.waveform_writes_blocked is False
    assert scope.acquisition_writes_blocked is False
    first_queries = list(transport.queries)
    with pytest.raises(InstrumentError, match="autoscale writes are blocked"):
        scope.autoscale(wait_opc=True, check_errors=False)
    assert transport.queries == first_queries
    assert transport.writes == [":AUToscale"]


@pytest.mark.parametrize("bad_opc", ["0", "", " 2 "])
def test_autoscale_invalid_completion_latches_without_replay(bad_opc: str) -> None:
    transport = AutoscaleTransport()
    transport.opc_response = bad_opc
    scope = MSO8104Scope(transport=transport)

    with pytest.raises(InstrumentError, match="completion is uncertain"):
        scope.autoscale(wait_opc=True, check_errors=False)

    assert scope.autoscale_writes_blocked is True
    assert transport.writes == [":AUToscale"]
    assert transport.opc_calls == 1


def test_autoscale_opc_failure_latches_without_reissuing_write() -> None:
    transport = AutoscaleTransport()
    transport.opc_error = InstrumentError("injected OPC failure")
    scope = MSO8104Scope(transport=transport)

    with pytest.raises(InstrumentError, match="completion is uncertain"):
        scope.autoscale(wait_opc=True, check_errors=False)

    assert scope.autoscale_writes_blocked is True
    assert transport.writes == [":AUToscale"]
    assert transport.opc_calls == 1


def test_close_is_idempotent_and_blocks_later_queries() -> None:
    transport = FakeTransport(
        {"*IDN?": "RIGOL TECHNOLOGIES,MSO8104,SERIAL,00.01"}
    )
    scope = MSO8104Scope(transport=transport)

    scope.close()
    scope.close()

    assert transport.close_calls == 1
    with pytest.raises(InstrumentError, match="closed"):
        scope.idn()
    with pytest.raises(InstrumentError, match="closed"):
        scope.channel_coupling(1)
    with pytest.raises(InstrumentError, match="closed"):
        scope.fetch_waveform(channel=1, points="DEF", check_errors=False)
    with pytest.raises(InstrumentError, match="closed"):
        scope.get_math_waveform_metadata(1)
    assert transport.queries == []
