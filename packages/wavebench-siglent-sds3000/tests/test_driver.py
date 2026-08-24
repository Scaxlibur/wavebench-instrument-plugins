from __future__ import annotations

import ast
from pathlib import Path
import struct

import numpy as np
import pytest

from wavebench.errors import (
    DataError,
    InstrumentError,
    OperationTimeout,
    SessionHealthError,
    StateDriftError,
    TransportIOError,
)
from wavebench.instruments.api import DriverContext
from wavebench.instruments.capabilities import validate_declared_capabilities
from wavebench.logging import CommandLogger
from wavebench.transport.contracts import (
    CommandTransmission,
    ReplayPolicy,
    ResponseProgress,
    Synchronization,
    TransportPhase,
)
from wavebench.transport.guarded import GuardedAuditedTransport
from wavebench.transport.session import InstrumentSessionState, SessionHealth
from wavebench_siglent_sds3000 import descriptor as plugin_descriptor
from wavebench_siglent_sds3000.driver import (
    SDS3000Scope,
    SDS3000Identity,
    parse_sds3000_identity,
)


DRIVER_PATH = Path(__file__).resolve().parents[1] / "src" / "wavebench_siglent_sds3000" / "driver.py"


class FakeTransport:
    def __init__(
        self,
        response: str = "LECROY,SDS3054,redacted,8.4.1",
        *,
        responses: dict[str, str] | None = None,
        response_sequences: dict[str, list[str]] | None = None,
        query_failures: dict[str, Exception] | None = None,
        binary_responses: dict[str, bytes | Exception] | None = None,
        failing_write: str | None = None,
        write_failures: dict[str, Exception] | None = None,
        opc_response: str | Exception = "*OPC 1",
    ) -> None:
        self.response = response
        self.responses = responses or {}
        self.response_sequences = response_sequences or {}
        self.query_failures = query_failures or {}
        self.binary_responses = binary_responses or {}
        self.failing_write = failing_write
        self.write_failures = write_failures or {}
        self.opc_response = opc_response
        self.writes: list[str] = []
        self.queries: list[str] = []
        self.query_policies: list[tuple[str, ReplayPolicy]] = []
        self.close_count = 0

    def write(self, command: str) -> None:
        self.writes.append(command)
        if command in self.write_failures:
            raise self.write_failures[command]
        if command == self.failing_write:
            raise OSError("simulated write failure")

    def query(self, command: str, *, replay: ReplayPolicy) -> str:
        self.queries.append(command)
        self.query_policies.append((command, replay))
        if command in self.query_failures:
            raise self.query_failures[command]
        if command in self.response_sequences:
            return self.response_sequences[command].pop(0)
        return self.responses.get(command, self.response)

    def query_bin_block(self, command: str, *, replay: ReplayPolicy) -> bytes:
        self.queries.append(command)
        self.query_policies.append((command, replay))
        response = self.binary_responses[command]
        if isinstance(response, Exception):
            raise response
        return response

    def query_opc(self, *, replay: ReplayPolicy) -> str:
        self.queries.append("*OPC?")
        self.query_policies.append(("*OPC?", replay))
        if isinstance(self.opc_response, Exception):
            raise self.opc_response
        return self.opc_response

    def close(self) -> None:
        self.close_count += 1


def _transport_failure(
    *,
    operation: str,
    synchronization: Synchronization,
    phase: TransportPhase = TransportPhase.READING,
) -> TransportIOError:
    return TransportIOError(
        "structured transport failure",
        operation=operation,
        phase=phase,
        replay_policy=ReplayPolicy.NO_REPLAY,
        command_transmission=CommandTransmission.SENT,
        response_progress=ResponseProgress.NONE,
        synchronization=synchronization,
        attempts=1,
    )


def test_every_transport_query_explicitly_uses_no_replay() -> None:
    tree = ast.parse(DRIVER_PATH.read_text(encoding="utf-8"))
    query_names = {"query", "query_bin_block", "query_float_list", "query_opc"}
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in query_names
        and isinstance(node.func.value, ast.Attribute)
        and node.func.value.attr == "transport"
    ]

    assert calls
    for call in calls:
        replay = next((keyword.value for keyword in call.keywords if keyword.arg == "replay"), None)
        assert replay is not None, f"line {call.lineno} has no explicit replay policy"
        assert ast.unparse(replay) == "ReplayPolicy.NO_REPLAY"


def test_descriptor_is_executable_v2_metadata_without_io() -> None:
    descriptor = plugin_descriptor()

    assert descriptor.driver_id == "siglent.sds3000"
    assert descriptor.api_version == "wavebench.instrument.v2"
    assert descriptor.wavebench_min_version == "0.8.24"
    assert descriptor.wavebench_max_version == "0.9.0"
    assert descriptor.kind == "scope"
    assert descriptor.models == ("SDS3054",)
    assert descriptor.aliases == ()
    assert descriptor.capabilities == (
        "scope.idn",
        "scope.errors",
        "scope.channel_coupling",
        "scope.fetch_waveform",
        "scope.capture_waveform",
        "scope.capture_waveforms",
    )
    assert descriptor.idn_patterns == (
        "*IDN LECROY,SDS3054,",
        "LECROY,SDS3054,",
    )
    assert descriptor.backends == ("pyvisa",)
    assert descriptor.resource_schemes == ("vicp", "tcpip")
    assert descriptor.scope_coupling_policy == "switchable-termination"
    assert descriptor.config_fields == (
        "connection.resource",
        "scope.driver",
        "waveform.*",
    )
    assert descriptor.validate_options({}) == {}


def test_factory_opens_only_the_context_transport_and_performs_no_io() -> None:
    transport = FakeTransport()
    descriptor = plugin_descriptor()
    context = DriverContext(
        driver_id=descriptor.driver_id,
        kind="scope",
        resource="configured-resource",
        backend="pyvisa",
        timeout_ms=1000,
        opc_timeout_ms=2000,
        logger=CommandLogger(),
        _transport_factory=lambda: transport,
        settings={},
        options=descriptor.validate_options({}),
    )

    driver = descriptor.factory(context)

    assert driver.transport is transport
    assert driver.io_timeout_ms == 1000
    assert driver.opc_timeout_ms == 2000
    assert transport.queries == []
    assert transport.writes == []
    validate_declared_capabilities(descriptor, driver)


def test_identity_parser_accepts_only_the_verified_device_baseline() -> None:
    assert parse_sds3000_identity(" LECROY,SDS3054,redacted,8.4.1\n") == SDS3000Identity(
        remote_manufacturer="LECROY",
        model="SDS3054",
        serial="redacted",
        firmware="8.4.1",
    )
    assert parse_sds3000_identity("*IDN LECROY,SDS3054,redacted,8.4.1\n") == SDS3000Identity(
        remote_manufacturer="LECROY",
        model="SDS3054",
        serial="redacted",
        firmware="8.4.1",
    )


@pytest.mark.parametrize(
    ("response", "error", "message"),
    [
        ("bad", DataError, "invalid"),
        ("*IDN? LECROY,SDS3054,redacted,8.4.1", InstrumentError, "not a supported"),
        ("SIGLENT,SDS3054,redacted,8.4.1", InstrumentError, "not a supported"),
        ("LECROY,SDS3024,redacted,8.4.1", InstrumentError, "unsupported.*model"),
        ("LECROY,SDS3054,redacted,8.5.0", InstrumentError, "unsupported.*firmware"),
    ],
)
def test_identity_gate_rejects_unsupported_targets_without_writes(
    response: str,
    error: type[Exception],
    message: str,
) -> None:
    transport = FakeTransport(response)
    scope = SDS3000Scope(transport)

    with pytest.raises(error, match=message):
        scope.idn()

    assert transport.queries == ["*IDN?"]
    assert transport.writes == []


def test_idn_queries_once_and_close_is_idempotent() -> None:
    transport = FakeTransport()
    scope = SDS3000Scope(transport)

    assert scope.idn() == "LECROY,SDS3054,redacted,8.4.1"
    assert transport.queries == ["*IDN?"]
    assert transport.writes == []

    scope.close()
    scope.close()
    assert transport.close_count == 1


@pytest.mark.parametrize(
    ("response", "coupling"),
    [
        ("A1M", "ACL"),
        ("C2:CPL D1M", "DCL"),
        ("C2:COUPLING D50", "DC"),
        ("GND", "GND"),
    ],
)
def test_channel_coupling_maps_maui_tokens_to_wavebench_values(
    response: str,
    coupling: str,
) -> None:
    transport = FakeTransport(responses={"C2:CPL?": response})

    assert SDS3000Scope(transport).channel_coupling(2) == coupling
    assert transport.queries == ["*IDN?", "C2:CPL?"]
    assert transport.writes == []


@pytest.mark.parametrize("channel", [False, 0, 5])
def test_channel_coupling_rejects_invalid_channels_before_io(channel: int) -> None:
    transport = FakeTransport()

    with pytest.raises(DataError, match="CH1, CH2, CH3, or CH4"):
        SDS3000Scope(transport).channel_coupling(channel)

    assert transport.queries == []
    assert transport.writes == []


def test_channel_coupling_rejects_overload_and_unknown_responses() -> None:
    overload = FakeTransport(responses={"C1:CPL?": "C1:CPL OVL"})
    with pytest.raises(InstrumentError, match="overload"):
        SDS3000Scope(overload).channel_coupling(1)

    unknown = FakeTransport(responses={"C1:CPL?": "C1:CPL MAGIC"})
    with pytest.raises(DataError, match=r"C1:CPL\?"):
        SDS3000Scope(unknown).channel_coupling(1)


def test_error_registers_are_read_once_and_only_nonzero_values_are_returned() -> None:
    transport = FakeTransport(
        responses={
            "CMR?": "CMR 0",
            "EXR?": "EXR? 21",
            "DDR?": "2",
        }
    )
    scope = SDS3000Scope(transport)

    assert scope.errors() == ["EXR 21", "DDR 2"]
    assert transport.queries == ["*IDN?", "CMR?", "EXR?", "DDR?"]
    assert transport.writes == []


def test_error_register_parser_rejects_bad_values_and_limit_before_writes() -> None:
    bad = FakeTransport(responses={"CMR?": "CMR 14"})
    with pytest.raises(DataError, match="out-of-range CMR"):
        SDS3000Scope(bad).errors()
    assert bad.writes == []

    invalid_limit = FakeTransport()
    with pytest.raises(DataError, match="positive integer"):
        SDS3000Scope(invalid_limit).errors(limit=0)
    assert invalid_limit.queries == []


def test_assert_no_errors_uses_the_stateful_register_snapshot() -> None:
    clear = FakeTransport(responses={"CMR?": "0", "EXR?": "0", "DDR?": "0"})
    SDS3000Scope(clear).assert_no_errors()

    active = FakeTransport(responses={"CMR?": "1", "EXR?": "0", "DDR?": "0"})
    with pytest.raises(InstrumentError, match="CMR 1"):
        SDS3000Scope(active).assert_no_errors()


def test_read_to_clear_failure_is_no_replay_and_blocks_later_io() -> None:
    failure = _transport_failure(
        operation="query",
        synchronization=Synchronization.PROVEN,
    )
    inner = FakeTransport(query_failures={"CMR?": failure})
    state = InstrumentSessionState(epoch_id="sds-errors-epoch")
    guarded = GuardedAuditedTransport(inner, session_state=state)
    scope = SDS3000Scope(guarded)

    with pytest.raises(TransportIOError) as captured:
        scope.errors()

    assert captured.value is failure
    assert inner.queries == ["*IDN?", "CMR?"]
    assert inner.query_policies == [
        ("*IDN?", ReplayPolicy.NO_REPLAY),
        ("CMR?", ReplayPolicy.NO_REPLAY),
    ]
    assert state.health is SessionHealth.UNCERTAIN

    query_count = len(inner.queries)
    with pytest.raises(SessionHealthError):
        scope.channel_coupling(1)
    assert len(inner.queries) == query_count
    assert state.health is SessionHealth.UNCERTAIN


def _word_descriptor(*, points: int = 4) -> bytes:
    block = bytearray(346)
    block[0:8] = b"WAVEDESC"
    block[16:26] = b"LECROY_2_4"
    struct.pack_into("<h", block, 32, 1)
    struct.pack_into("<h", block, 34, 1)
    struct.pack_into("<i", block, 36, len(block))
    struct.pack_into("<i", block, 60, points * 2)
    struct.pack_into("<i", block, 116, points)
    struct.pack_into("<i", block, 124, 0)
    struct.pack_into("<i", block, 128, points - 1)
    struct.pack_into("<i", block, 132, 0)
    struct.pack_into("<i", block, 136, 0)
    struct.pack_into("<i", block, 140, 1)
    struct.pack_into("<i", block, 144, 1)
    struct.pack_into("<f", block, 156, 0.5)
    struct.pack_into("<f", block, 160, 0.0)
    struct.pack_into("<f", block, 176, 0.25)
    struct.pack_into("<d", block, 180, -0.5)
    block[196] = ord("V")
    block[244] = ord("S")
    return bytes(block)


def _waveform_transport(
    *,
    data_response: bytes | Exception = struct.pack("<4h", -2, 0, 2, 4),
    failing_write: str | None = None,
) -> FakeTransport:
    return FakeTransport(
        responses={
            "CHDR?": "CHDR SHORT",
            "CFMT?": "COMM_FORMAT DEF9,BYTE,BIN",
            "CORD?": "HI",
            "WFSU?": "WFSU SN,0,FP,2,NP,10,SP,4",
        },
        binary_responses={
            "C1:WF? DESC": _word_descriptor(),
            "C1:WF? DAT1": data_response,
        },
        failing_write=failing_write,
    )


def test_fetch_waveform_uses_existing_capability_and_restores_transfer_state() -> None:
    transport = _waveform_transport()
    waveform = SDS3000Scope(transport).fetch_waveform(
        channel=1,
        points="DMAX",
        check_errors=False,
    )

    np.testing.assert_allclose(waveform.voltages_v, [-1.0, 0.0, 1.0, 2.0])
    np.testing.assert_allclose(waveform.times_s, [-0.5, -0.25, 0.0, 0.25])
    assert transport.queries == [
        "*IDN?",
        "CHDR?",
        "CFMT?",
        "CORD?",
        "WFSU?",
        "C1:WF? DESC",
        "C1:WF? DAT1",
    ]
    assert transport.writes == [
        "CHDR OFF",
        "CFMT DEF9,WORD,BIN",
        "CORD LO",
        "WFSU SP,0,NP,0,FP,0,SN,1",
        "WFSU SP,4,NP,10,FP,2,SN,0",
        "CORD HI",
        "CFMT DEF9,BYTE,BIN",
        "CHDR SHORT",
    ]


@pytest.mark.parametrize("points", ["", "all", 1, None])
def test_fetch_waveform_rejects_invalid_points_before_io(points) -> None:
    transport = _waveform_transport()

    with pytest.raises(DataError, match="DEF, MAX, or DMAX"):
        SDS3000Scope(transport).fetch_waveform(1, points=points, check_errors=False)

    assert transport.queries == []
    assert transport.writes == []


def test_fetch_waveform_restores_state_when_binary_read_fails() -> None:
    transport = _waveform_transport(data_response=TimeoutError("interrupted"))

    with pytest.raises(TimeoutError, match="interrupted"):
        SDS3000Scope(transport).fetch_waveform(1, check_errors=False)

    assert transport.writes[-4:] == [
        "WFSU SP,4,NP,10,FP,2,SN,0",
        "CORD HI",
        "CFMT DEF9,BYTE,BIN",
        "CHDR SHORT",
    ]


def test_fetch_waveform_reports_state_drift_when_restore_fails() -> None:
    transport = _waveform_transport(failing_write="CHDR SHORT")

    with pytest.raises(StateDriftError, match="CHDR") as captured:
        SDS3000Scope(transport).fetch_waveform(1, check_errors=False)

    assert captured.value.expected == {"CHDR": "SHORT"}
    assert captured.value.diff["CHDR"]["actual"] == "unknown"


def test_structured_restore_failure_stops_remaining_restore_writes() -> None:
    failure = _transport_failure(
        operation="write",
        synchronization=Synchronization.LOST,
        phase=TransportPhase.SENDING,
    )
    inner = _waveform_transport()
    inner.write_failures["WFSU SP,4,NP,10,FP,2,SN,0"] = failure
    state = InstrumentSessionState(epoch_id="sds-restore-epoch")
    guarded = GuardedAuditedTransport(inner, session_state=state)

    with pytest.raises(TransportIOError) as captured:
        SDS3000Scope(guarded).fetch_waveform(1, check_errors=False)

    assert captured.value is failure
    assert state.health is SessionHealth.POISONED
    assert inner.writes == [
        "CHDR OFF",
        "CFMT DEF9,WORD,BIN",
        "CORD LO",
        "WFSU SP,0,NP,0,FP,0,SN,1",
        "WFSU SP,4,NP,10,FP,2,SN,0",
    ]


def test_fetch_waveform_rejects_malformed_saved_state_without_writes() -> None:
    transport = _waveform_transport()
    transport.responses["CFMT?"] = "DEF9,FLOAT,BIN"

    with pytest.raises(DataError, match=r"CFMT\?"):
        SDS3000Scope(transport).fetch_waveform(1, check_errors=False)

    assert transport.queries == ["*IDN?", "CHDR?", "CFMT?"]
    assert transport.writes == []


def _capture_transport(
    *,
    final_trigger_mode: str = "STOP",
    trace_states: dict[int, str] | None = None,
    failing_write: str | None = None,
) -> FakeTransport:
    traces = trace_states or {1: "ON", 2: "ON"}
    responses = {
        "TDIV?": "TDIV 2 MS",
        "C1:VDIV?": "C1:VDIV 200 MV",
        "C2:VDIV?": "C2:VDIV 200 MV",
        "CHDR?": "OFF",
        "CFMT?": "DEF9,WORD,BIN",
        "CORD?": "LO",
        "WFSU?": "SP,0,NP,0,FP,0,SN,1",
        **{f"C{channel}:TRA?": f"C{channel}:TRA {state}" for channel, state in traces.items()},
    }
    return FakeTransport(
        responses=responses,
        response_sequences={"TRMD?": ["TRMD AUTO", f"TRMD {final_trigger_mode}"]},
        binary_responses={
            "C1:WF? DESC": _word_descriptor(),
            "C1:WF? DAT1": struct.pack("<4h", -2, 0, 2, 4),
            "C2:WF? DESC": _word_descriptor(),
            "C2:WF? DAT1": struct.pack("<4h", -4, -2, 0, 2),
        },
        failing_write=failing_write,
    )


def test_single_capture_uses_wait_opc_and_restores_every_changed_field() -> None:
    transport = _capture_transport(trace_states={1: "OFF"})
    waveform = SDS3000Scope(transport).capture_waveform(
        1,
        check_errors=False,
        time_range_s=0.01,
        vertical_scale_v_per_div=0.2,
    )

    np.testing.assert_allclose(waveform.voltages_v, [-1.0, 0.0, 1.0, 2.0])
    assert transport.writes == [
        "STOP",
        "TDIV 0.001",
        "C1:VDIV 0.2",
        "C1:TRA ON",
        "ARM",
        "WAIT 28",
        "C1:TRA OFF",
        "C1:VDIV 200 MV",
        "TDIV 2 MS",
        "TRMD AUTO",
    ]
    assert transport.queries.count("*OPC?") == 1
    assert transport.queries.count("C1:WF? DAT1") == 1


def test_dual_capture_uses_one_acquisition_for_both_channels_and_callbacks() -> None:
    transport = _capture_transport()
    started: list[int | None] = []
    completed: list[int] = []

    waveforms = SDS3000Scope(transport).capture_waveforms(
        [1, 2],
        check_errors=False,
        on_channel_start=started.append,
        on_waveform=lambda channel, waveform: completed.append(channel),
    )

    assert list(waveforms) == [1, 2]
    np.testing.assert_allclose(waveforms[1].voltages_v, [-1.0, 0.0, 1.0, 2.0])
    np.testing.assert_allclose(waveforms[2].voltages_v, [-2.0, -1.0, 0.0, 1.0])
    assert transport.writes == ["STOP", "ARM", "WAIT 28", "TRMD AUTO"]
    assert transport.writes.count("ARM") == 1
    assert transport.queries.count("*OPC?") == 1
    assert started == [1, 2]
    assert completed == [1, 2]


def test_capture_timeout_fails_before_waveform_read_and_restores_trigger_mode() -> None:
    transport = _capture_transport(final_trigger_mode="SINGLE")

    with pytest.raises(OperationTimeout, match="did not complete"):
        SDS3000Scope(transport).capture_waveform(1, check_errors=False)

    assert transport.writes == ["STOP", "ARM", "WAIT 28", "TRMD AUTO"]
    assert not any(query.endswith("WF? DESC") for query in transport.queries)


def test_structured_opc_failure_is_not_wrapped_or_followed_by_restore_io() -> None:
    failure = _transport_failure(
        operation="query_opc",
        synchronization=Synchronization.PROVEN,
    )
    inner = _capture_transport()
    inner.opc_response = failure
    state = InstrumentSessionState(epoch_id="sds-opc-epoch")
    guarded = GuardedAuditedTransport(inner, session_state=state)

    with pytest.raises(TransportIOError) as captured:
        SDS3000Scope(guarded).capture_waveform(1, check_errors=False)

    assert captured.value is failure
    assert state.health is SessionHealth.UNCERTAIN
    assert inner.writes == ["STOP", "ARM", "WAIT 28"]
    assert inner.query_policies[-1] == ("*OPC?", ReplayPolicy.NO_REPLAY)


def test_capture_restore_failure_is_reported_as_state_drift() -> None:
    transport = _capture_transport(
        trace_states={1: "OFF"},
        failing_write="C1:TRA OFF",
    )

    with pytest.raises(StateDriftError, match="C1:TRA") as captured:
        SDS3000Scope(transport).capture_waveform(1, check_errors=False)

    assert captured.value.expected == {"C1:TRA": "OFF"}
    assert transport.writes[-1] == "TRMD AUTO"


@pytest.mark.parametrize(
    ("channels", "time_range_s", "vertical_scale_v_per_div"),
    [
        ([], None, None),
        ([1, 1], None, None),
        ([0], None, None),
        ([1], 0.0, None),
        ([1], None, float("nan")),
    ],
)
def test_capture_rejects_invalid_requests_before_io(
    channels,
    time_range_s,
    vertical_scale_v_per_div,
) -> None:
    transport = _capture_transport()

    with pytest.raises(DataError):
        SDS3000Scope(transport).capture_waveforms(
            channels,
            check_errors=False,
            time_range_s=time_range_s,
            vertical_scale_v_per_div=vertical_scale_v_per_div,
        )

    assert transport.queries == []
    assert transport.writes == []
