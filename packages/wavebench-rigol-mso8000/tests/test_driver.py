from __future__ import annotations

import pytest

from wavebench.errors import ConfigError, DataError, InstrumentError
from wavebench.instruments import DriverContext
from wavebench.instruments.capabilities import validate_declared_capabilities
from wavebench.instruments.models import ScopeChannelInputStateV2
from wavebench.instruments.scope_extensions import (
    DriverErrorRecord,
    ErrorDrainResult,
    ScopeAcquisitionControlProfile,
    ScopeAcquisitionStatusProfileV2,
    ScopeCursorReadoutProfileV2,
    ScopeFftStatusProfileV2,
    ScopeMeasurementStatisticsProfileV2,
    ScopeScreenshotProfile,
    ScopeSnapshotProfileV2,
    ScopeWaveformBinaryProfile,
)
from wavebench.logging import CommandLogger
from wavebench.services.scope_service import assert_scope_high_impedance
from wavebench.transport.contracts import BinaryResponseFraming, ReplayPolicy
from wavebench_rigol_mso8000 import descriptor as plugin_descriptor
from wavebench_rigol_mso8000.driver import MSO8104Scope
from wavebench_rigol_mso8000.parsers import (
    RigolIdentity,
    parse_mso8104_error_queue_record,
    parse_mso8104_identity,
)


class FakeTransport:
    def __init__(self, responses: dict[str, str] | None = None):
        self.responses = responses or {}
        self.queries: list[str] = []
        self.close_calls = 0

    def query(
        self,
        command: str,
        *,
        replay: ReplayPolicy = ReplayPolicy.NO_REPLAY,
    ) -> str:
        del replay
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
        "scope.error_drain_v1",
        "scope.fetch_waveform",
        "scope.capture_waveform",
        "scope.capture_waveforms",
        "scope.channel_coupling",
        "scope.channel_input_state_v2",
        "scope.autoscale",
        "scope.screenshot_profile",
        "scope.screenshot_v2",
        "scope.math_metadata",
        "scope.measurement_statistics_v2",
        "scope.fft_status_v2",
        "scope.acquisition_status_v2",
        "scope.acquisition_run_state",
        "scope.acquisition_control",
        "scope.digital_status_v2",
        "scope.snapshot_v2",
        "scope.cursor_readout",
        "scope.cursor_readout_v2",
    )
    assert descriptor.backends == ("pyvisa",)
    assert descriptor.resource_schemes == ("tcpip", "usb", "gpib")
    assert descriptor.scope_coupling_policy == "switchable-termination"
    assert descriptor.wavebench_min_version == "0.8.24"
    assert descriptor.wavebench_max_version == "0.9.0"
    assert descriptor.version == "0.9.0"
    assert descriptor.scope_extensions is not None
    screenshot_profile = descriptor.scope_extensions.screenshot_profile
    assert isinstance(screenshot_profile, ScopeScreenshotProfile)
    screenshot_variant = screenshot_profile.select(
        screenshot_profile.variants[0].request
    )
    assert screenshot_variant.request.format == "png"
    assert screenshot_variant.request.menu_mode == "device"
    assert screenshot_variant.request.color_mode == "device"
    assert screenshot_variant.media_type == "image/png"
    assert screenshot_variant.framing is BinaryResponseFraming.DEFINITE_BLOCK
    assert screenshot_variant.response_max_bytes == 8_388_608
    assert screenshot_variant.operation_max_bytes == 8_388_608
    assert screenshot_variant.resynchronization_max_bytes == 0
    assert screenshot_variant.query_max_count == 1
    assert screenshot_variant.changed_fields == ()
    assert screenshot_variant.restore_order == ()
    assert screenshot_variant.snapshot_max_steps == 0
    assert screenshot_variant.restore_max_steps == 0
    assert screenshot_variant.verify_max_steps == 0
    assert screenshot_variant.transport_trailing_hex == "0a"
    profile = descriptor.scope_extensions.waveform_binary_profile
    assert isinstance(profile, ScopeWaveformBinaryProfile)
    assert profile.transport_trailing == b"\n"
    fetch, capture_single, capture_multiple = profile.operations
    assert fetch.operation_kind == "fetch"
    assert fetch.response_max_bytes == 250_000
    assert fetch.operation_max_bytes == 4_000_000
    assert fetch.query_max_count == 16
    assert fetch.resynchronization_max_bytes == 65_536
    assert fetch.restore_order == (
        "scope.waveform_source",
        "scope.waveform_mode",
        "scope.waveform_format",
        "scope.waveform_points",
        "scope.waveform_transfer_window",
    )
    for operation, expected_kind, expected_operation_bytes, expected_query_count in (
        (capture_single, "capture_single", 1_000, 1),
        (capture_multiple, "capture_multiple", 4_000, 4),
    ):
        assert operation.operation_kind == expected_kind
        assert operation.response_max_bytes == 1_000
        assert operation.operation_max_bytes == expected_operation_bytes
        assert operation.query_max_count == expected_query_count
        assert operation.resynchronization_max_bytes == 65_536
        assert operation.restore_order == (
            "scope.acquisition",
            "scope.trigger",
            "scope.timebase",
            "scope.channel_display",
            "scope.channel_vertical",
            "scope.waveform_source",
            "scope.waveform_mode",
            "scope.query_response_header",
            "scope.waveform_format",
            "scope.waveform_byte_order",
            "scope.waveform_points",
            "scope.waveform_transfer_window",
            "scope.run_state",
        )
        assert operation.snapshot_max_steps == 32
        assert operation.restore_max_steps == 32
        assert operation.verify_max_steps == 32
    assert descriptor.validate_options({}) == {
        "max_total_points": 4_000_000,
        "max_chunk_points": 250_000,
    }
    cursor_profile = descriptor.scope_extensions.cursor_readout_profile_v2
    assert isinstance(cursor_profile, ScopeCursorReadoutProfileV2)
    assert cursor_profile.addressing == "global"
    assert cursor_profile.max_queries == 9
    assert cursor_profile.readable_fields == (
        "source_a",
        "source_b",
        "x_a",
        "x_b",
        "x_delta",
        "inverse_x_delta",
        "y_a",
        "y_b",
        "y_delta",
    )
    assert cursor_profile.conditionally_applicable_fields == (
        "x_a",
        "x_b",
        "x_delta",
        "inverse_x_delta",
        "y_a",
        "y_b",
        "y_delta",
    )
    statistics_profile = descriptor.scope_extensions.measurement_statistics_profile_v2
    assert isinstance(statistics_profile, ScopeMeasurementStatisticsProfileV2)
    assert statistics_profile.selector_modes == ("item_sources",)
    assert statistics_profile.max_queries == 6
    assert statistics_profile.supports_buffer is False
    assert statistics_profile.item_source_count_range == (1, 2)
    assert statistics_profile.supported_items[0:3] == ("VMAX", "VMIN", "VPP")
    assert statistics_profile.supported_items[-2:] == ("FRPHASE", "FFPHASE")
    fft_profile = descriptor.scope_extensions.fft_status_profile_v2
    assert isinstance(fft_profile, ScopeFftStatusProfileV2)
    assert fft_profile.readable_fields == (
        "source",
        "window",
        "vertical_unit",
        "frequency_start_hz",
        "frequency_stop_hz",
    )
    assert fft_profile.max_queries == 6
    assert fft_profile.allowed_effect == "pure_read"
    acquisition_profile = descriptor.scope_extensions.acquisition_status_profile_v2
    assert isinstance(acquisition_profile, ScopeAcquisitionStatusProfileV2)
    assert acquisition_profile.readable_fields == (
        "acquisition_type",
        "sample_rate_hz",
        "memory_depth",
        "average",
        "average.configured_count",
    )
    assert acquisition_profile.conditionally_applicable_fields == ("average",)
    assert acquisition_profile.max_queries == 4
    assert acquisition_profile.allowed_effect == "pure_read"
    control_profile = descriptor.scope_extensions.acquisition_control_profile
    assert isinstance(control_profile, ScopeAcquisitionControlProfile)
    assert control_profile.supported_continuous_modes == ("normal",)
    assert control_profile.single_arm_semantics == "atomic_configure_and_arm"
    assert control_profile.arm_resets_acquisition_count is True
    assert control_profile.failure_restore_order == ("scope.trigger", "scope.acquisition")
    assert control_profile.single_mode_readback_allows_terminal_stop is True
    snapshot_profile = descriptor.scope_extensions.snapshot_profile_v2
    assert isinstance(snapshot_profile, ScopeSnapshotProfileV2)
    assert snapshot_profile.readable_fields == (
        "identity.manufacturer",
        "identity.model",
        "identity.serial_number",
        "identity.firmware",
        "identity.options",
    )
    assert snapshot_profile.conditionally_applicable_fields == ()
    assert snapshot_profile.max_queries == 14
    assert snapshot_profile.allowed_effect == "pure_read"


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


class ErrorQueueTransport(FakeTransport):
    def __init__(self, records: list[str]) -> None:
        super().__init__()
        self.records = list(records)
        self.replays: list[ReplayPolicy] = []
        self.error: Exception | None = None

    def query(
        self,
        command: str,
        *,
        replay: ReplayPolicy = ReplayPolicy.NO_REPLAY,
    ) -> str:
        assert command == ":SYSTem:ERRor?"
        self.queries.append(command)
        self.replays.append(replay)
        if self.error is not None:
            raise self.error
        try:
            return self.records.pop(0)
        except IndexError as exc:
            raise AssertionError("error queue queried after its configured records") from exc


def test_error_queue_parser_retains_signed_code_and_comma_message() -> None:
    assert parse_mso8104_error_queue_record(' -222,"Data, out of range"\n') == (
        -222,
        "Data, out of range",
    )


@pytest.mark.parametrize(
    "response",
    (
        "",
        "0,No error",
        "zero,\"No error\"",
        '0,"unterminated',
        '0,"embedded \" quote"',
        '0,"non-ascii é"',
        '0,"trailing" extra',
    ),
)
def test_error_queue_parser_rejects_ambiguous_response(response: str) -> None:
    with pytest.raises(DataError, match="error queue"):
        parse_mso8104_error_queue_record(response)


def test_error_drain_uses_no_replay_and_retains_consumed_records() -> None:
    transport = ErrorQueueTransport(
        ['-222,"Data, out of range"', '0,"No error"']
    )

    result = MSO8104Scope(transport=transport).drain_errors(max_records=16)

    assert result == ErrorDrainResult(
        records=(
            DriverErrorRecord(
                code=-222,
                message="Data, out of range",
                severity="error",
                source="mso8104",
            ),
        ),
        terminated=True,
        query_count=2,
    )
    assert transport.queries == [":SYSTem:ERRor?", ":SYSTem:ERRor?"]
    assert transport.replays == [ReplayPolicy.NO_REPLAY, ReplayPolicy.NO_REPLAY]


def test_error_drain_reports_overflow_with_required_extra_query() -> None:
    transport = ErrorQueueTransport(
        [
            '-100,"First"',
            '-200,"Second"',
            '-300,"Third"',
        ]
    )

    result = MSO8104Scope(transport=transport).drain_errors(max_records=2)

    assert result == ErrorDrainResult(
        records=(
            DriverErrorRecord(-100, "First", "error", "mso8104"),
            DriverErrorRecord(-200, "Second", "error", "mso8104"),
        ),
        terminated=False,
        query_count=3,
        overflow_record=DriverErrorRecord(-300, "Third", "error", "mso8104"),
    )
    assert len(transport.queries) == 3
    assert transport.replays == [ReplayPolicy.NO_REPLAY] * 3


@pytest.mark.parametrize("max_records", (0, 257, True, 1.0, "1"))
def test_error_drain_rejects_invalid_limit_without_io(max_records: object) -> None:
    transport = ErrorQueueTransport(['0,"No error"'])

    with pytest.raises(DataError, match="max_records"):
        MSO8104Scope(transport=transport).drain_errors(max_records=max_records)  # type: ignore[arg-type]

    assert transport.queries == []


def test_error_drain_propagates_one_transport_failure_without_retry() -> None:
    transport = ErrorQueueTransport(['0,"No error"'])
    transport.error = InstrumentError("injected consuming-query failure")

    with pytest.raises(InstrumentError, match="injected consuming-query failure"):
        MSO8104Scope(transport=transport).drain_errors(max_records=1)

    assert transport.queries == [":SYSTem:ERRor?"]
    assert transport.replays == [ReplayPolicy.NO_REPLAY]


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
        self.write_error: Exception | None = None

    def write(self, command: str) -> None:
        self.writes.append(command)
        if self.write_error is not None:
            raise self.write_error

def test_autoscale_preflights_enable_and_uses_fixed_settle_period() -> None:
    transport = AutoscaleTransport()
    scope = MSO8104Scope(transport=transport)
    pauses: list[float] = []
    scope._sleep = pauses.append

    scope.autoscale(wait_opc=True, check_errors=False)

    assert transport.queries == [":SYSTem:AUToscale?"]
    assert transport.writes == [":AUToscale"]
    assert pauses == [3.0]
    assert scope.autoscale_writes_blocked is False


def test_autoscale_can_explicitly_skip_fixed_settle_wait() -> None:
    transport = AutoscaleTransport()

    MSO8104Scope(transport=transport).autoscale(
        wait_opc=False,
        check_errors=False,
    )

    assert transport.writes == [":AUToscale"]


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


def test_autoscale_settle_failure_latches_without_reissuing_write() -> None:
    transport = AutoscaleTransport()

    def fail_settle(_: float) -> None:
        raise InstrumentError("injected settle failure")

    scope = MSO8104Scope(transport=transport, _sleep=fail_settle)

    with pytest.raises(InstrumentError, match="settle wait failed"):
        scope.autoscale(wait_opc=True, check_errors=False)

    assert scope.autoscale_writes_blocked is True
    assert transport.writes == [":AUToscale"]


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
