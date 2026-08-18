from __future__ import annotations

import struct

import numpy as np
import pytest

from wavebench.errors import DataError, InstrumentError, StateDriftError
from wavebench.instruments.api import DriverContext
from wavebench.instruments.capabilities import validate_declared_capabilities
from wavebench.logging import CommandLogger
from wavebench_siglent_sds3000 import descriptor as plugin_descriptor
from wavebench_siglent_sds3000.driver import (
    SDS3000Scope,
    SDS3000Identity,
    parse_sds3000_identity,
)


class FakeTransport:
    def __init__(
        self,
        response: str = "LECROY,SDS3054,redacted,8.4.1",
        *,
        responses: dict[str, str] | None = None,
        binary_responses: dict[str, bytes | Exception] | None = None,
        failing_write: str | None = None,
    ) -> None:
        self.response = response
        self.responses = responses or {}
        self.binary_responses = binary_responses or {}
        self.failing_write = failing_write
        self.writes: list[str] = []
        self.queries: list[str] = []
        self.close_count = 0

    def write(self, command: str) -> None:
        self.writes.append(command)
        if command == self.failing_write:
            raise OSError("simulated write failure")

    def query(self, command: str) -> str:
        self.queries.append(command)
        return self.responses.get(command, self.response)

    def query_bin_block(self, command: str) -> bytes:
        self.queries.append(command)
        response = self.binary_responses[command]
        if isinstance(response, Exception):
            raise response
        return response

    def close(self) -> None:
        self.close_count += 1


def test_descriptor_is_executable_v2_metadata_without_io() -> None:
    descriptor = plugin_descriptor()

    assert descriptor.driver_id == "siglent.sds3000"
    assert descriptor.api_version == "wavebench.instrument.v2"
    assert descriptor.kind == "scope"
    assert descriptor.models == ("SDS3054",)
    assert descriptor.aliases == ()
    assert descriptor.capabilities == (
        "scope.idn",
        "scope.errors",
        "scope.channel_coupling",
        "scope.fetch_waveform",
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


def test_fetch_waveform_rejects_malformed_saved_state_without_writes() -> None:
    transport = _waveform_transport()
    transport.responses["CFMT?"] = "DEF9,FLOAT,BIN"

    with pytest.raises(DataError, match=r"CFMT\?"):
        SDS3000Scope(transport).fetch_waveform(1, check_errors=False)

    assert transport.queries == ["*IDN?", "CHDR?", "CFMT?"]
    assert transport.writes == []
