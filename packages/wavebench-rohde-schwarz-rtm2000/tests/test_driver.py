from __future__ import annotations

from threading import Event, Thread

import numpy as np
import pytest

from wavebench.errors import ConfigError, DataError, InstrumentError, OperationTimeout
from wavebench.instruments import (
    ScopeChannelDisplayBaseline,
    ScopeChannelDisplayRequest,
    ScopeChannelDisplayRestoreResult,
    ScopeChannelDisplayState,
)
from wavebench.instruments.api import DriverContext
from wavebench.instruments.capabilities import validate_declared_capabilities
from wavebench.instruments.models import (
    ScopeAcquisitionStatus,
    ScopeAnalogChannelSnapshot,
    ScopeAverageCaptureRequest,
    ScopeAverageConfiguration,
    ScopeChannelInputStateV2,
    ScopeCursorReadout,
    ScopeDerivedWaveformMetadata,
    ScopeDigitalChannelStatus,
    ScopeDigitalChannelStatusV2,
    ScopeDigitalPodStatusV2,
    ScopeDigitalSharedStatusV2,
    ScopeDigitalWaveformRequest,
    ScopeEdgeTriggerSnapshot,
    ScopeFftStatus,
    ScopeFftStatusV2,
    ScopeHealthSnapshot,
    ScopeHistoryTimestamp,
    ScopeHistoryTimestamps,
    ScopeIdentitySnapshot,
    ScopeMeasurementSelector,
    ScopeMeasurementStatistics,
    ScopeMeasurementStatisticsRequestV2,
    ScopeMeasurementStatisticsV2,
    ScopeProbeSnapshot,
    ScopeSnapshot,
    ScopeTimebaseSnapshot,
    ScopeWaveformMetadataSnapshot,
)
from wavebench.logging import CommandLogger
from wavebench_rohde_schwarz_rtm2000 import descriptor as plugin_descriptor
from wavebench_rohde_schwarz_rtm2000.driver import (
    RTM2000AnalogChannelSnapshot,
    RTM2000EdgeTriggerSnapshot,
    RTM2000HealthSnapshot,
    RTM2000IdentitySnapshot,
    RTM2000ProbeSnapshot,
    RTM2000TimebaseSnapshot,
    RTM2000TriggerControlError,
    RTM2000AverageCaptureError,
    RTM2000WaveformMetadataSnapshot,
    RTM2032Scope,
    parse_waveform_header,
)
from wavebench_rohde_schwarz_rtm2000.profiles import (
    RTM2000_FFT_STATUS_V2_READABLE_FIELDS,
    RTM2000_SCOPE_EXTENSIONS,
    RTM2000_SNAPSHOT_V2_READABLE_FIELDS,
)


class FakeTransport:
    def __init__(self, responses=None, float_lists=None):
        self.responses = responses or {}
        self.float_lists = float_lists or {}
        self.writes = []
        self.queries = []
        self.closed = False
        self.opc_error = None
        self.float_list_calls = []
        self.events = []

    def write(self, command):
        self.writes.append(command)

    def query(self, command):
        self.queries.append(command)
        return self.responses[command]

    def query_float_list(self, command, *, timeout_ms=None):
        self.queries.append(command)
        self.float_list_calls.append((command, timeout_ms))
        return self.float_lists[command]

    def query_bin_block(self, command):
        self.queries.append(command)
        return self.responses[command]

    def query_opc(self):
        self.queries.append("*OPC?")
        if self.opc_error is not None:
            raise self.opc_error
        return "1"

    def close(self):
        self.closed = True

    def record_event(self, direction, text):
        self.events.append((direction, text))


class TriggerControlTransport(FakeTransport):
    def __init__(
        self,
        *,
        level_v=0.53,
        source="CH2",
        questionable_before=0,
        fail_write_at=None,
        ignore_level_write=False,
        questionable_after=0,
        change_identity_after=False,
        channel_state="1",
        channel_coupling="DCL",
        channel_overload="0",
        change_holdoff_after=False,
    ):
        super().__init__()
        self.level_v = level_v
        self.source = source
        self.questionable_before = questionable_before
        self.fail_write_at = fail_write_at
        self.ignore_level_write = ignore_level_write
        self.questionable_after = questionable_after
        self.change_identity_after = change_identity_after
        self.channel_state = channel_state
        self.channel_coupling = channel_coupling
        self.channel_overload = channel_overload
        self.change_holdoff_after = change_holdoff_after

    def write(self, command):
        self.writes.append(command)
        if self.fail_write_at == len(self.writes):
            raise TimeoutError("simulated write timeout")
        if command.startswith("TRIGger:A:LEVel2 ") and not self.ignore_level_write:
            self.level_v = float(command.rsplit(" ", 1)[1])

    def query(self, command):
        self.queries.append(command)
        wrote = bool(self.writes)
        responses = {
            "*IDN?": (
                "Rohde&Schwarz,RTM2032,123456,changed"
                if wrote and self.change_identity_after
                else "Rohde&Schwarz,RTM2032,123456,3.500"
            ),
            "*OPT?": "B1,K1",
            "*STB?": "0",
            "STATUS:OPERation:CONDITION?": "8",
            "STATUS:QUESTIONable:CONDITION?": str(
                self.questionable_after if wrote else self.questionable_before
            ),
            "ACQuire:AVAilable?": "53",
            "ACQuire:COUNT?": "53",
            "ACQuire:SRATe?": "5e6",
            "TRIGger:A:TYPE?": "EDGE",
            "TRIGger:A:SOURce?": self.source,
            "TRIGger:A:MODE?": "AUTO",
            "TRIGger:A:EDGE:SLOPe?": "POS",
            "TRIGger:A:EDGE:COUpling?": "DC",
            "TRIGger:A:LEVel1?": f"{self.level_v:.12g}",
            "TRIGger:A:LEVel2?": f"{self.level_v:.12g}",
            "TRIGger:A:HYSTEResis?": "AUTO",
            "TRIGger:A:HOLDoff:MODE?": "OFF",
            "TRIGger:A:HOLDoff:TIME?": (
                "6e-8" if wrote and self.change_holdoff_after else "5e-8"
            ),
            "CHANnel2:STATE?": self.channel_state,
            "CHANnel2:COUPling?": self.channel_coupling,
            "CHANnel2:RANGE?": "4.0",
            "CHANnel2:SCALe?": "0.5",
            "CHANnel2:OFFSET?": "0.0",
            "CHANnel2:POSITION?": "-2.8",
            "CHANnel2:BANDwidth?": "FULL",
            "CHANnel2:POLarity?": "NORM",
            "CHANnel2:SKEW?": "0.0",
            "CHANnel2:LABel?": '"CAL"',
            "CHANnel2:LABel:STATE?": "ON",
            "CHANnel2:OVERload?": self.channel_overload,
            "CHANnel2:TYPE?": "SAMP",
        }
        return responses[command]


class AverageCaptureTransport(FakeTransport):
    def __init__(
        self,
        *,
        arithmetic="OFF",
        fail_write_at=None,
        ignore_restore=False,
        average_complete="1",
        opc_error=None,
    ):
        super().__init__(
            responses={
                "CHAN1:DATA:HEAD?": "0,1,2,1",
                "CHAN2:DATA:HEAD?": "0,1,2,1",
            },
            float_lists={
                "CHAN1:DATA?": [0.0, 1.0],
                "CHAN2:DATA?": [1.0, 0.0],
            },
        )
        self.average_count = 8
        self.single_count = 1
        self.arithmetic = arithmetic
        self.fail_write_at = fail_write_at
        self.ignore_restore = ignore_restore
        self.average_complete = average_complete
        self.opc_error = opc_error

    def write(self, command):
        self.writes.append(command)
        if self.fail_write_at == len(self.writes):
            raise TimeoutError("simulated write timeout")
        if command == "SINGle":
            return
        field, value = command.rsplit(" ", 1)
        if field == "ACQuire:AVERage:COUNt":
            parsed = int(value)
            if not self.ignore_restore or parsed != 8:
                self.average_count = parsed
        elif field == "ACQuire:NSINgle:COUNt":
            parsed = int(value)
            if not self.ignore_restore or parsed != 1:
                self.single_count = parsed
        elif field == "CHANnel1:ARITHmetics":
            if not self.ignore_restore or value != "OFF":
                self.arithmetic = value.upper()
        else:
            raise KeyError(command)

    def query(self, command):
        self.queries.append(command)
        responses = {
            "FORMat?": "REAL,32",
            "FORMat:BORDer?": "LSBF",
            "ACQuire:AVERage:COUNt?": str(self.average_count),
            "ACQuire:NSINgle:COUNt?": str(self.single_count),
            "CHANnel1:ARITHmetics?": self.arithmetic,
            "CHANnel2:ARITHmetics?": self.arithmetic,
            "ACQuire:AVERage:COMPlete?": self.average_complete,
            **self.responses,
        }
        return responses[command]


def test_descriptor_and_factory_preserve_core_transport_boundary():
    descriptor = plugin_descriptor()
    transport = FakeTransport()
    transport_opens = 0

    def open_transport():
        nonlocal transport_opens
        transport_opens += 1
        return transport

    context = DriverContext(
        driver_id=descriptor.driver_id,
        kind="scope",
        resource="configured-resource",
        backend="rsinstrument",
        timeout_ms=1000,
        opc_timeout_ms=2000,
        logger=CommandLogger(),
        _transport_factory=open_transport,
        settings={"check_errors": False},
        options=descriptor.validate_options({}),
    )

    driver = descriptor.factory(context)
    validate_declared_capabilities(descriptor, driver)

    assert descriptor.driver_id == "rohde-schwarz.rtm2032"
    assert descriptor.aliases == ()
    assert descriptor.backends == (
        "rsinstrument-socket",
        "rsinstrument",
        "rsinstrument-rsvisa",
        "rsinstrument-pyvisa-py",
    )
    assert descriptor.resource_schemes == ("tcpip",)
    assert descriptor.validate_options({}) == {"long_waveform_timeout_ms": 300_000}
    assert descriptor.scope_coupling_policy == "switchable-termination"
    assert descriptor.distribution == "wavebench-rohde-schwarz-rtm2000"
    assert descriptor.version == "0.14.0"
    assert descriptor.wavebench_min_version == "0.8.25"
    assert len(descriptor.capabilities) == 25
    assert {
        "scope.channel_display_configure_v2",
        "scope.channel_input_state_v2",
        "scope.digital_status_v2",
        "scope.snapshot_v2",
        "scope.measurement_statistics_v2",
        "scope.fft_status_v2",
    } <= set(descriptor.capabilities)
    assert descriptor.scope_extensions is RTM2000_SCOPE_EXTENSIONS
    assert descriptor.scope_extensions.snapshot_profile_v2.readable_fields == (
        RTM2000_SNAPSHOT_V2_READABLE_FIELDS
    )
    assert descriptor.scope_extensions.snapshot_profile_v2.max_queries == 2
    statistics_profile = descriptor.scope_extensions.measurement_statistics_profile_v2
    assert statistics_profile.slot_range == (1, 4)
    assert statistics_profile.max_queries == 7
    assert descriptor.scope_extensions.fft_status_profile_v2.readable_fields == (
        RTM2000_FFT_STATUS_V2_READABLE_FIELDS
    )
    assert descriptor.scope_extensions.fft_status_profile_v2.max_queries == 3
    assert descriptor.scope_extensions.channel_display_profile_v2.analog_channels == (
        1,
        2,
    )
    assert descriptor.scope_extensions.channel_display_profile_v2.snapshot_max_steps == 1
    assert descriptor.scope_extensions.channel_display_profile_v2.configure_max_steps == 2
    assert descriptor.scope_extensions.channel_display_profile_v2.restore_max_steps == 1
    assert descriptor.scope_extensions.channel_display_profile_v2.verify_max_steps == 1
    assert driver.transport is transport
    assert driver.check_errors_after_ops is False
    assert transport_opens == 1


def test_digital_status_is_b1_gated_and_query_only():
    responses = {
        "*OPT?": "K15,B1",
        "DIGital5:CURRENT:STATE:MINimum?": "0",
        "DIGital5:CURRENT:STATE:MAXimum?": "1",
        "DIGital5:DISPLAY?": "ON",
        "DIGital5:TECHnology?": "TTL",
        "DIGital5:THReshold?": "1.4",
        "DIGital5:THCoupling?": "OFF",
        "DIGital5:Hysteresis?": "NORM",
        "DIGital5:DESKew?": "2e-9",
        "DIGital5:SIZE?": "SMAL",
        "DIGital5:POSITION?": "2.5",
        "DIGital5:LABel?": '"DATA"',
        "DIGital5:LABel:STATe?": "1",
    }
    transport = FakeTransport(responses=responses)

    status = RTM2032Scope(transport).get_digital_status(5)

    assert status == ScopeDigitalChannelStatus(
        channel=5,
        group_start_channel=4,
        group_stop_channel=7,
        displayed=True,
        activity="TOGGLE",
        technology="TTL",
        threshold_v=1.4,
        threshold_coupled=False,
        hysteresis="NORMAL",
        deskew_s=2e-9,
        size="SMALL",
        position_div=2.5,
        label="DATA",
        label_enabled=True,
    )
    assert transport.writes == []
    assert transport.queries == list(responses)
    assert not any(":DATA" in command for command in transport.queries)


def test_digital_status_requires_b1_before_channel_queries():
    transport = FakeTransport(responses={"*OPT?": "K15"})

    with pytest.raises(InstrumentError, match="option B1"):
        RTM2032Scope(transport).get_digital_status(0)

    assert transport.writes == []
    assert transport.queries == ["*OPT?"]


@pytest.mark.parametrize("channel", [-1, 16, True, 1.0, "1"])
def test_digital_status_rejects_invalid_channel_before_io(channel):
    transport = FakeTransport()

    with pytest.raises(DataError, match="0 through 15"):
        RTM2032Scope(transport).get_digital_status(channel)

    assert transport.writes == []
    assert transport.queries == []


def test_digital_status_rejects_impossible_activity_pair():
    transport = FakeTransport(
        responses={
            "*OPT?": "B1",
            "DIGital0:CURRENT:STATE:MINimum?": "1",
            "DIGital0:CURRENT:STATE:MAXimum?": "0",
        }
    )

    with pytest.raises(DataError, match="minimum is high but maximum is low"):
        RTM2032Scope(transport).get_digital_status(0)

    assert transport.writes == []
    assert transport.queries == [
        "*OPT?",
        "DIGital0:CURRENT:STATE:MINimum?",
        "DIGital0:CURRENT:STATE:MAXimum?",
    ]


def test_digital_status_normalizes_documented_abbreviations():
    responses = {
        "*OPT?": "B1",
        "DIGital15:CURRENT:STATE:MINimum?": "1",
        "DIGital15:CURRENT:STATE:MAXimum?": "1",
        "DIGital15:DISPLAY?": "0",
        "DIGital15:TECHnology?": "MAN",
        "DIGital15:THReshold?": "-1.3",
        "DIGital15:THCoupling?": "ON",
        "DIGital15:Hysteresis?": "MAX",
        "DIGital15:DESKew?": "0",
        "DIGital15:SIZE?": "MED",
        "DIGital15:POSITION?": "-2",
        "DIGital15:LABel?": '"D15"',
        "DIGital15:LABel:STATe?": "OFF",
    }

    status = RTM2032Scope(FakeTransport(responses=responses)).get_digital_status(15)

    assert status.activity == "HIGH"
    assert status.technology == "MANUAL"
    assert status.hysteresis == "MAXIMUM"
    assert status.size == "MEDIUM"
    assert (status.group_start_channel, status.group_stop_channel) == (12, 15)


def _digital_waveform_responses(channel, *, start=-2e-6, stop=1e-6, points=4):
    prefix = f"DIGital{channel}:DATA"
    return {
        f"{prefix}:POINts?": str(points),
        f"{prefix}:HEADer?": f"{start},{stop},{points},1",
        f"{prefix}:XORigin?": str(start),
        f"{prefix}:XINCrement?": "1e-6",
    }


def test_digital_waveform_is_b1_gated_query_only_and_packed_by_channel_number():
    responses = {"*OPT?": "B1,K15", "FORMat?": "ASC,0"}
    responses.update(_digital_waveform_responses(0))
    responses.update(_digital_waveform_responses(3))
    responses.update(_digital_waveform_responses(15))
    transport = FakeTransport(
        responses=responses,
        float_lists={
            "DIGital0:DATA?": [0, 1, 1, 0],
            "DIGital3:DATA?": [1, 0, 1, 0],
            "DIGital15:DATA?": [0, 0, 1, 1],
        },
    )

    waveform = RTM2032Scope(transport).get_digital_waveform(
        ScopeDigitalWaveformRequest((0, 3, 15), True)
    )

    assert waveform.channels == (0, 3, 15)
    assert waveform.samples.tolist() == [8, 1, 32777, 32768]
    assert waveform.samples.dtype == np.uint16
    assert waveform.x_start_s == -2e-6
    assert waveform.x_stop_s == 1e-6
    assert waveform.x_increment_s == 1e-6
    assert transport.writes == []
    assert transport.float_list_calls == [
        ("DIGital0:DATA?", 300_000),
        ("DIGital3:DATA?", 300_000),
        ("DIGital15:DATA?", 300_000),
    ]
    assert all(
        "SYST" not in command and "EVENT" not in command
        for command in transport.queries
    )


def test_digital_waveform_refuses_to_change_non_ascii_format():
    transport = FakeTransport(responses={"*OPT?": "B1", "FORMat?": "REAL,32"})

    with pytest.raises(DataError, match="ASC,0 or CSV,0"):
        RTM2032Scope(transport).get_digital_waveform(
            ScopeDigitalWaveformRequest((0,), True)
        )

    assert transport.queries == ["*OPT?", "FORMat?"]
    assert transport.writes == []


def test_digital_waveform_accepts_rtm2032_csv_ascii_format_readback():
    responses = {"*OPT?": "B1", "FORMat?": "CSV,0"}
    responses.update(_digital_waveform_responses(0))
    transport = FakeTransport(
        responses=responses,
        float_lists={"DIGital0:DATA?": [0, 1, 0, 1]},
    )

    waveform = RTM2032Scope(transport).get_digital_waveform(
        ScopeDigitalWaveformRequest((0,), True)
    )

    assert waveform.samples.tolist() == [0, 1, 0, 1]
    assert transport.writes == []


def test_digital_waveform_requires_b1_before_data_queries():
    transport = FakeTransport(responses={"*OPT?": "K15"})

    with pytest.raises(InstrumentError, match="B1"):
        RTM2032Scope(transport).get_digital_waveform(
            ScopeDigitalWaveformRequest((0,), True)
        )

    assert transport.queries == ["*OPT?"]
    assert transport.writes == []


def test_digital_waveform_rejects_cross_channel_axis_mismatch():
    responses = {"*OPT?": "B1", "FORMat?": "ASC,0"}
    responses.update(_digital_waveform_responses(0))
    responses.update(_digital_waveform_responses(1, start=-1e-6, stop=2e-6))
    transport = FakeTransport(
        responses=responses,
        float_lists={"DIGital0:DATA?": [0, 1, 0, 1]},
    )

    with pytest.raises(DataError, match="does not match"):
        RTM2032Scope(transport).get_digital_waveform(
            ScopeDigitalWaveformRequest((0, 1), True)
        )

    assert "DIGital1:DATA?" not in transport.queries
    assert transport.writes == []


def test_digital_waveform_rejects_header_axis_length_mismatch():
    responses = {"*OPT?": "B1", "FORMat?": "ASC,0"}
    responses.update(_digital_waveform_responses(0, stop=5e-6))
    transport = FakeTransport(responses=responses)

    with pytest.raises(DataError, match="point count"):
        RTM2032Scope(transport).get_digital_waveform(
            ScopeDigitalWaveformRequest((0,), True)
        )

    assert "DIGital0:DATA?" not in transport.queries
    assert transport.writes == []


def test_digital_waveform_rejects_nonbinary_samples():
    responses = {"*OPT?": "B1", "FORMat?": "ASC,0"}
    responses.update(_digital_waveform_responses(0))
    transport = FakeTransport(
        responses=responses,
        float_lists={"DIGital0:DATA?": [0, 1, 2, 0]},
    )

    with pytest.raises(DataError, match="0 or 1"):
        RTM2032Scope(transport).get_digital_waveform(
            ScopeDigitalWaveformRequest((0,), True)
        )

    assert transport.writes == []


def test_digital_waveform_rejects_zero_points_as_data_error():
    transport = FakeTransport(
        responses={
            "*OPT?": "B1",
            "FORMat?": "ASC,0",
            "DIGital0:DATA:POINts?": "0",
        }
    )

    with pytest.raises(DataError, match="out-of-range"):
        RTM2032Scope(transport).get_digital_waveform(
            ScopeDigitalWaveformRequest((0,), True)
        )

    assert transport.writes == []
    assert transport.float_list_calls == []


def test_identity_and_health_snapshots_are_read_only_and_typed():
    transport = FakeTransport(
        responses={
            "*IDN?": "Rohde&Schwarz,RTM2032,123456,3.500",
            "*OPT?": "B1, K1, K2",
            "*STB?": "4",
            "STATUS:OPERation:CONDITION?": "8",
            "STATUS:QUESTIONable:CONDITION?": "0",
            "ACQuire:AVAilable?": "53",
            "ACQuire:COUNT?": "53",
            "ACQuire:SRATe?": "5.000000000E+06",
        }
    )
    scope = RTM2032Scope(transport)

    identity = scope.identity_snapshot()
    health = scope.health_snapshot()

    assert identity.manufacturer == "Rohde&Schwarz"
    assert identity.model == "RTM2032"
    assert identity.serial_number == "123456"
    assert identity.firmware == "3.500"
    assert identity.options == ("B1", "K1", "K2")
    assert health.status_byte == 4
    assert health.operation_condition == 8
    assert health.questionable_condition == 0
    assert health.acquisition_available == 53
    assert health.acquisition_count == 53
    assert health.sample_rate_hz == 5_000_000.0
    assert health.error_queue_nonempty is True
    assert health.waiting_for_trigger is True
    assert transport.writes == []
    assert transport.queries == [
        "*IDN?",
        "*OPT?",
        "*STB?",
        "STATUS:OPERation:CONDITION?",
        "STATUS:QUESTIONable:CONDITION?",
        "ACQuire:AVAilable?",
        "ACQuire:COUNT?",
        "ACQuire:SRATe?",
    ]


def test_acquisition_status_reads_average_and_k15_segment_state_without_writes():
    transport = FakeTransport(
        responses={
            "*OPT?": "B1 - MSO 16 Logic Channels,K15 - History/Segmented Memory",
            "ACQuire:AVERage:COUNt?": "16",
            "ACQuire:AVERage:COMPlete?": "1",
            "ACQuire:SEGMented:STATe?": "OFF",
            "ACQuire:SEGMented:MAXimum?": "ON",
            "ACQuire:COUNt?": "1000",
            "ACQuire:AVAilable?": "24",
        }
    )

    status = RTM2032Scope(transport).get_acquisition_status()

    assert status == ScopeAcquisitionStatus(16, True, True, False, True, 1000, 24)
    assert transport.writes == []
    assert transport.queries == [
        "*OPT?",
        "ACQuire:AVERage:COUNt?",
        "ACQuire:AVERage:COMPlete?",
        "ACQuire:SEGMented:STATe?",
        "ACQuire:SEGMented:MAXimum?",
        "ACQuire:COUNt?",
        "ACQuire:AVAilable?",
    ]


def test_acquisition_status_skips_k15_queries_when_option_is_absent():
    transport = FakeTransport(
        responses={
            "*OPT?": "B1",
            "ACQuire:AVERage:COUNt?": "8",
            "ACQuire:AVERage:COMPlete?": "0",
        }
    )

    status = RTM2032Scope(transport).get_acquisition_status()

    assert status == ScopeAcquisitionStatus(8, False, False, None, None, None, None)
    assert transport.writes == []
    assert transport.queries == [
        "*OPT?",
        "ACQuire:AVERage:COUNt?",
        "ACQuire:AVERage:COMPlete?",
    ]


def test_controlled_average_capture_restores_global_configuration():
    transport = AverageCaptureTransport()
    request = ScopeAverageCaptureRequest((1, 2), 16, True)

    result = RTM2032Scope(transport).capture_average(request)

    assert result.request == request
    assert tuple(waveform.channel for waveform in result.waveforms) == (1, 2)
    assert result.configuration_before == ScopeAverageConfiguration(
        8, 1, ((1, "OFF"), (2, "OFF"))
    )
    assert result.configuration_after == result.configuration_before
    assert result.restored_fields == (
        "ACQuire:AVERage:COUNt",
        "ACQuire:NSINgle:COUNt",
        "CHANnel:ARITHmetics",
    )
    assert transport.writes == [
        "ACQuire:AVERage:COUNt 16",
        "ACQuire:NSINgle:COUNt 16",
        "CHANnel1:ARITHmetics AVERage",
        "SINGle",
        "ACQuire:AVERage:COUNt 8",
        "ACQuire:NSINgle:COUNt 1",
        "CHANnel1:ARITHmetics OFF",
    ]
    assert not any(
        command.startswith(("*CLS", "FORMat ", "FORMat:BORDer ", "CHAN:DATA:POIN"))
        for command in transport.writes
    )


def test_controlled_average_capture_requires_existing_real_lsbf_transfer():
    transport = AverageCaptureTransport()
    transport.query = lambda command: "ASCii" if command == "FORMat?" else "MSBF"

    with pytest.raises(DataError, match="REAL,32 with LSBF"):
        RTM2032Scope(transport).capture_average(
            ScopeAverageCaptureRequest((1,), 8, True)
        )

    assert transport.writes == []


def test_controlled_average_capture_rejects_ambiguous_real_transfer_width():
    transport = AverageCaptureTransport()
    original_query = transport.query
    transport.query = lambda command: "REAL" if command == "FORMat?" else original_query(command)

    with pytest.raises(DataError, match="REAL,32 with LSBF"):
        RTM2032Scope(transport).capture_average(
            ScopeAverageCaptureRequest((1,), 8, True)
        )

    assert transport.writes == []


def test_controlled_average_capture_rejects_inconsistent_global_arithmetic():
    transport = AverageCaptureTransport()
    original_query = transport.query

    def query(command):
        if command == "CHANnel2:ARITHmetics?":
            transport.queries.append(command)
            return "SMOOTH"
        return original_query(command)

    transport.query = query

    with pytest.raises(DataError, match="affects all channels"):
        RTM2032Scope(transport).capture_average(
            ScopeAverageCaptureRequest((1,), 8, True)
        )

    assert transport.writes == []


def test_controlled_average_capture_restores_after_acquisition_failure():
    transport = AverageCaptureTransport(average_complete="0")
    scope = RTM2032Scope(transport)

    with pytest.raises(RTM2000AverageCaptureError) as failure:
        scope.capture_average(ScopeAverageCaptureRequest((1,), 8, True))

    assert failure.value.phase == "acquisition-unknown"
    assert transport.average_count == 8
    assert transport.single_count == 1
    assert transport.arithmetic == "OFF"
    assert scope.average_writes_blocked is True


def test_controlled_average_capture_latches_after_opc_timeout():
    transport = AverageCaptureTransport(opc_error=TimeoutError("timeout"))
    scope = RTM2032Scope(transport)

    with pytest.raises(RTM2000AverageCaptureError) as failure:
        scope.capture_average(ScopeAverageCaptureRequest((1,), 8, True))

    assert failure.value.phase == "acquisition-unknown"
    assert scope.average_writes_blocked is True


def test_controlled_average_capture_treats_first_write_timeout_as_ambiguous():
    transport = AverageCaptureTransport(fail_write_at=1)
    scope = RTM2032Scope(transport)

    with pytest.raises(RTM2000AverageCaptureError) as first:
        scope.capture_average(ScopeAverageCaptureRequest((1,), 8, True))

    assert first.value.phase == "write-uncertain"
    assert transport.writes == [
        "ACQuire:AVERage:COUNt 8",
        "ACQuire:AVERage:COUNt 8",
        "ACQuire:NSINgle:COUNt 1",
        "CHANnel1:ARITHmetics OFF",
    ]
    assert scope.average_writes_blocked is True

    io_after_first = (tuple(transport.writes), tuple(transport.queries))
    with pytest.raises(RTM2000AverageCaptureError) as second:
        scope.capture_average(ScopeAverageCaptureRequest((1,), 8, True))
    assert second.value.phase == "blocked"
    assert (tuple(transport.writes), tuple(transport.queries)) == io_after_first


def test_controlled_average_capture_latches_when_restore_is_ambiguous():
    transport = AverageCaptureTransport(ignore_restore=True)
    scope = RTM2032Scope(transport)

    with pytest.raises(RTM2000AverageCaptureError) as first:
        scope.capture_average(ScopeAverageCaptureRequest((1,), 8, True))

    assert first.value.phase == "restore"
    writes_after_first = tuple(transport.writes)
    with pytest.raises(RTM2000AverageCaptureError) as second:
        scope.capture_average(ScopeAverageCaptureRequest((1,), 8, True))
    assert second.value.phase == "blocked"
    assert tuple(transport.writes) == writes_after_first


def test_history_timestamps_requires_k15_before_querying_tables():
    transport = FakeTransport(responses={"*OPT?": "B1"})

    with pytest.raises(InstrumentError, match="option K15"):
        RTM2032Scope(transport).get_history_timestamps(1)

    assert transport.writes == []
    assert transport.queries == ["*OPT?"]


def test_history_timestamps_strictly_zips_oldest_to_newest_tables():
    transport = FakeTransport(
        responses={
            "*OPT?": "B1,k15",
            "CHANnel2:HISTORY:TSRelative:ALL?": "-0.25,-0.0",
            "CHANnel2:HISTORY:TSABsolute:ALL?": "10,30,1.25,10,30,1.5",
            "CHANnel2:HISTORY:TSDate:ALL?": "2026,7,26,2026,7,26",
        }
    )

    table = RTM2032Scope(transport).get_history_timestamps(2)

    assert table == ScopeHistoryTimestamps(
        channel=2,
        entries=(
            ScopeHistoryTimestamp(1, -0.25, 2026, 7, 26, 10, 30, 1.25),
            ScopeHistoryTimestamp(2, -0.0, 2026, 7, 26, 10, 30, 1.5),
        ),
    )
    assert transport.writes == []
    assert transport.queries == [
        "*OPT?",
        "CHANnel2:HISTORY:TSRelative:ALL?",
        "CHANnel2:HISTORY:TSABsolute:ALL?",
        "CHANnel2:HISTORY:TSDate:ALL?",
    ]


@pytest.mark.parametrize(
    ("command", "response", "message"),
    [
        ("CHANnel1:HISTORY:TSRelative:ALL?", "-0.1,-0.2,0", "out-of-order"),
        ("CHANnel1:HISTORY:TSRelative:ALL?", "-0.1,-0.01", "near zero"),
        ("CHANnel1:HISTORY:TSRelative:ALL?", "-0.1,nan", "non-finite"),
        ("CHANnel1:HISTORY:TSABsolute:ALL?", "24,0,0,10,0,0", "out-of-range"),
        ("CHANnel1:HISTORY:TSDate:ALL?", "2026,2,30,2026,3,1", "out-of-range"),
    ],
)
def test_history_timestamps_rejects_malformed_tables(command, response, message):
    responses = {
        "*OPT?": "K15 - History/Segmented Memory",
        "CHANnel1:HISTORY:TSRelative:ALL?": "-0.1,0",
        "CHANnel1:HISTORY:TSABsolute:ALL?": "10,0,0,10,0,1",
        "CHANnel1:HISTORY:TSDate:ALL?": "2026,7,26,2026,7,26",
    }
    responses[command] = response

    with pytest.raises(DataError, match=message):
        RTM2032Scope(FakeTransport(responses=responses)).get_history_timestamps(1)


def test_history_timestamps_rejects_table_length_mismatch():
    transport = FakeTransport(
        responses={
            "*OPT?": "K15",
            "CHANnel1:HISTORY:TSRelative:ALL?": "-0.1,0",
            "CHANnel1:HISTORY:TSABsolute:ALL?": "10,0,1",
            "CHANnel1:HISTORY:TSDate:ALL?": "2026,7,26,2026,7,26",
        }
    )

    with pytest.raises(DataError, match="inconsistent segment counts"):
        RTM2032Scope(transport).get_history_timestamps(1)


def test_history_timestamps_rejects_calendar_order_mismatch():
    transport = FakeTransport(
        responses={
            "*OPT?": "K15",
            "CHANnel1:HISTORY:TSRelative:ALL?": "-0.1,0",
            "CHANnel1:HISTORY:TSABsolute:ALL?": "10,0,1,10,0,0",
            "CHANnel1:HISTORY:TSDate:ALL?": "2026,7,26,2026,7,26",
        }
    )

    with pytest.raises(DataError, match="not oldest-to-newest"):
        RTM2032Scope(transport).get_history_timestamps(1)


def test_measurement_statistics_reads_existing_slot_without_writes_or_error_queue():
    transport = FakeTransport(
        responses={
            "MEASurement2:CATegory?": "AMPTime",
            "MEASurement2:RESult:ACTual?": "NAN",
            "MEASurement2:RESult:AVG?": "0.9",
            "MEASurement2:RESult:STDDev?": "0.1",
            "MEASurement2:RESult:NPEak?": "0.7",
            "MEASurement2:RESult:PPEak?": "1.1",
            "MEASurement2:RESult:WFMCount?": "42",
        }
    )

    stats = RTM2032Scope(transport).get_measurement_statistics(
        2,
        configured_slot=True,
    )

    assert stats == ScopeMeasurementStatistics(
        2, "AMPTIME", None, 0.9, 0.1, 0.7, 1.1, 42
    )
    assert transport.writes == []
    assert transport.queries == [
        "MEASurement2:CATegory?",
        "MEASurement2:RESult:ACTual?",
        "MEASurement2:RESult:AVG?",
        "MEASurement2:RESult:STDDev?",
        "MEASurement2:RESult:NPEak?",
        "MEASurement2:RESult:PPEak?",
        "MEASurement2:RESult:WFMCount?",
    ]


def test_measurement_statistics_reads_buffer_only_with_stopped_confirmation():
    transport = FakeTransport(
        responses={
            "MEASurement1:CATegory?": "AMPT",
            "MEASurement1:RESult:ACTual?": "1.0",
            "MEASurement1:RESult:AVG?": "0.9",
            "MEASurement1:RESult:STDDev?": "0.1",
            "MEASurement1:RESult:NPEak?": "0.7",
            "MEASurement1:RESult:PPEak?": "1.1",
            "MEASurement1:RESult:WFMCount?": "2",
            "MEASurement1:STATistics:VALue:ALL?": "0.8,1.0",
        }
    )

    stats = RTM2032Scope(transport).get_measurement_statistics(
        1,
        configured_slot=True,
        include_buffer=True,
        acquisition_stopped=True,
    )

    assert stats.buffered_values == (0.8, 1.0)
    assert transport.queries[-1] == "MEASurement1:STATistics:VALue:ALL?"
    assert transport.writes == []


@pytest.mark.parametrize("slot", [0, 5])
def test_measurement_statistics_rejects_invalid_slot_before_io(slot):
    transport = FakeTransport()

    with pytest.raises(ValueError, match="slot must be"):
        RTM2032Scope(transport).get_measurement_statistics(
            slot,
            configured_slot=True,
        )

    assert transport.queries == []


def test_measurement_statistics_requires_configured_slot_before_io():
    transport = FakeTransport()

    with pytest.raises(ValueError, match="slot is already configured"):
        RTM2032Scope(transport).get_measurement_statistics(
            1,
            configured_slot=False,
        )

    assert transport.queries == []


def test_measurement_statistics_requires_stopped_acquisition_before_buffer_io():
    transport = FakeTransport()

    with pytest.raises(ValueError, match="acquisition is stopped"):
        RTM2032Scope(transport).get_measurement_statistics(
            1,
            configured_slot=True,
            include_buffer=True,
        )

    assert transport.queries == []


@pytest.mark.parametrize(
    ("command", "response", "message"),
    [
        ("MEASurement1:RESult:ACTual?", "inf", "non-finite"),
        ("MEASurement1:RESult:WFMCount?", "-1", "out-of-range"),
        ("MEASurement1:STATistics:VALue:ALL?", "1,nan", "non-finite"),
    ],
)
def test_measurement_statistics_rejects_invalid_values(command, response, message):
    responses = {
        "MEASurement1:CATegory?": "AMPT",
        "MEASurement1:RESult:ACTual?": "1.0",
        "MEASurement1:RESult:AVG?": "0.9",
        "MEASurement1:RESult:STDDev?": "0.1",
        "MEASurement1:RESult:NPEak?": "0.7",
        "MEASurement1:RESult:PPEak?": "1.1",
        "MEASurement1:RESult:WFMCount?": "2",
        "MEASurement1:STATistics:VALue:ALL?": "0.8,1.0",
    }
    responses[command] = response

    with pytest.raises(DataError, match=message):
        RTM2032Scope(FakeTransport(responses=responses)).get_measurement_statistics(
            1,
            configured_slot=True,
            include_buffer=command.endswith("ALL?"),
            acquisition_stopped=command.endswith("ALL?"),
        )


def _derived_metadata_responses(prefix):
    return {
        f"{prefix}:HEADer?": "-1,1,3,1",
        f"{prefix}:POINts?": "3",
        f"{prefix}:XINCrement?": "1",
        f"{prefix}:XORigin?": "-1",
        f"{prefix}:YINCrement?": "0.5",
        f"{prefix}:YORigin?": "0",
        f"{prefix}:YRESolution?": "32",
    }


def test_math_waveform_metadata_is_query_only_and_does_not_read_data():
    prefix = "CALCulate:MATH2:DATA"
    transport = FakeTransport(responses=_derived_metadata_responses(prefix))

    metadata = RTM2032Scope(transport).get_math_waveform_metadata(2)

    assert metadata == ScopeDerivedWaveformMetadata(
        "math", 2, None, -1.0, 1.0, 3, 1, 1.0, -1.0, 0.5, 0.0, 32
    )
    assert transport.writes == []
    assert f"{prefix}?" not in transport.queries


def test_reference_waveform_metadata_queries_catalog_and_is_query_only():
    prefix = "REFCurve3:DATA"
    responses = _derived_metadata_responses(prefix)
    responses["REFCurve3:SOURce:CATalog?"] = "CH1"
    transport = FakeTransport(responses=responses)

    metadata = RTM2032Scope(transport).get_reference_waveform_metadata(3)

    assert metadata == ScopeDerivedWaveformMetadata(
        "reference", 3, "CH1", -1.0, 1.0, 3, 1, 1.0, -1.0, 0.5, 0.0, 32
    )
    assert transport.writes == []
    assert not any("UPDATE" in query or "SAVE" in query or "LOAD" in query for query in transport.queries)


def test_fft_status_requires_configured_confirmation_before_io():
    transport = FakeTransport()

    with pytest.raises(ValueError, match="configured as FFT"):
        RTM2032Scope(transport).get_fft_status(1, configured_fft=False)

    assert transport.queries == []


def test_fft_status_is_narrow_and_query_only():
    transport = FakeTransport(
        responses={
            "CALCulate:MATH1:FFT:AVERAGE:COMPLETE?": "1",
            "CALCulate:MATH1:FFT:BANDwidth:RESolution:ADJusted?": "10",
            "CALCulate:MATH1:FFT:SRATe?": "1000000",
        }
    )

    status = RTM2032Scope(transport).get_fft_status(1, configured_fft=True)

    assert status == ScopeFftStatus(1, True, 10.0, 1_000_000.0)
    assert transport.writes == []


def test_cursor_readout_requires_configured_confirmation_before_io():
    transport = FakeTransport()

    with pytest.raises(ValueError, match="already configured"):
        RTM2032Scope(transport).get_cursor_readout(1, configured_cursor=False)

    assert transport.queries == []


@pytest.mark.parametrize(
    ("function", "responses", "expected"),
    [
        ("RMS", {"CURSor1:RESult?": "1.25"}, ScopeCursorReadout(1, "CH1", "RMS", result=1.25)),
        (
            "VERTical",
            {"CURSor1:XDELta:VALue?": "0.001", "CURSor1:XDELta:INVerse?": "1000"},
            ScopeCursorReadout(1, "CH1", "VERTICAL", x_delta_s=0.001, inverse_x_delta_hz=1000.0),
        ),
        (
            "VERT",
            {"CURSor1:XDELta:VALue?": "0.001", "CURSor1:XDELta:INVerse?": "1000"},
            ScopeCursorReadout(1, "CH1", "VERTICAL", x_delta_s=0.001, inverse_x_delta_hz=1000.0),
        ),
        (
            "HORIZontal",
            {"CURSor1:YDELta:VALue?": "2", "CURSor1:YDELta:SLOPe?": "0.5"},
            ScopeCursorReadout(1, "CH1", "HORIZONTAL", y_delta=2.0, inverse_y_delta=0.5),
        ),
        (
            "PAIRed",
            {"CURSor1:XDELta:VALue?": "0.001", "CURSor1:YDELta:VALue?": "2"},
            ScopeCursorReadout(1, "CH1", "PAIRED", x_delta_s=0.001, y_delta=2.0),
        ),
        ("VRATio", {"CURSor1:XRATio:VALue?": "0.5"}, ScopeCursorReadout(1, "CH1", "VRATIO", x_ratio=0.5)),
        ("HRATio", {"CURSor1:YRATio:VALue?": "0.25"}, ScopeCursorReadout(1, "CH1", "HRATIO", y_ratio=0.25)),
    ],
)
def test_cursor_readout_queries_only_result_for_current_function(function, responses, expected):
    responses = {
        "CURSor1:SOURce?": "CH1",
        "CURSor1:FUNCTION?": function,
        **responses,
    }
    transport = FakeTransport(responses=responses)

    assert RTM2032Scope(transport).get_cursor_readout(
        1, configured_cursor=True
    ) == expected
    assert transport.writes == []


def test_vendor_snapshot_names_are_core_compatible_aliases():
    assert RTM2000IdentitySnapshot is ScopeIdentitySnapshot
    assert RTM2000HealthSnapshot is ScopeHealthSnapshot
    assert RTM2000AnalogChannelSnapshot is ScopeAnalogChannelSnapshot
    assert RTM2000TimebaseSnapshot is ScopeTimebaseSnapshot
    assert RTM2000ProbeSnapshot is ScopeProbeSnapshot
    assert RTM2000WaveformMetadataSnapshot is ScopeWaveformMetadataSnapshot
    assert RTM2000EdgeTriggerSnapshot is ScopeEdgeTriggerSnapshot


def test_get_snapshot_returns_all_read_only_sections_from_one_channel():
    scope = RTM2032Scope(FakeTransport())
    expected = ScopeSnapshot(
        identity=ScopeIdentitySnapshot("Rohde&Schwarz", "RTM2032", "123", "3.5", ()),
        health=ScopeHealthSnapshot(0, 0, 0, 1, 1, 1_000_000.0, False, False),
        channel=ScopeAnalogChannelSnapshot(
            2, True, "DCL", 8.0, 1.0, 0.0, 0.0, None, "NORM", 0.0,
            "input", True, False, "SAMPLE",
        ),
        timebase=ScopeTimebaseSnapshot(0.001, 10, 0.0, 0.001, 50.0, 0.0001, False),
        probe=ScopeProbeSnapshot(2, 10.0, None, None, 10_000_000.0, "P10", "PASSIVE"),
        waveform=ScopeWaveformMetadataSnapshot(
            2, -0.0005, 0.0005, 1000, 1, 1e-6, -0.0005, 0.001, 0.0, 8,
        ),
        trigger=ScopeEdgeTriggerSnapshot("EDGE", 2, "AUTO", "POS", "DC", 0.1, "AUTO", "OFF", 1e-6),
    )

    scope.identity_snapshot = lambda: expected.identity
    scope.health_snapshot = lambda: expected.health
    scope.analog_channel_snapshot = lambda channel: expected.channel
    scope.timebase_snapshot = lambda: expected.timebase
    scope.probe_snapshot = lambda channel: expected.probe
    scope.waveform_metadata_snapshot = lambda channel: expected.waveform
    scope.edge_trigger_snapshot = lambda: expected.trigger

    assert scope.get_snapshot(2) == expected


@pytest.mark.parametrize(
    ("command", "response"),
    [
        ("*STB?", "256"),
        ("STATUS:OPERation:CONDITION?", "-1"),
        ("STATUS:QUESTIONable:CONDITION?", "bad"),
        ("ACQuire:AVAilable?", "1.5"),
        ("ACQuire:COUNT?", "-1"),
        ("ACQuire:SRATe?", "nan"),
    ],
)
def test_health_snapshot_rejects_invalid_numeric_responses(command, response):
    responses = {
        "*STB?": "0",
        "STATUS:OPERation:CONDITION?": "8",
        "STATUS:QUESTIONable:CONDITION?": "0",
        "ACQuire:AVAilable?": "1",
        "ACQuire:COUNT?": "1",
        "ACQuire:SRATe?": "1e6",
    }
    responses[command] = response

    with pytest.raises(DataError, match="response"):
        RTM2032Scope(FakeTransport(responses=responses)).health_snapshot()


@pytest.mark.parametrize(
    ("idn", "options"),
    [
        ("Rohde&Schwarz,RTM2032,serial", "B1"),
        ("Rohde&Schwarz,Other,serial,firmware", "B1"),
        ("Rohde&Schwarz,RTM2032,serial,firmware", "B1,,K1"),
    ],
)
def test_identity_snapshot_rejects_malformed_responses(idn, options):
    transport = FakeTransport(responses={"*IDN?": idn, "*OPT?": options})

    with pytest.raises(DataError):
        RTM2032Scope(transport).identity_snapshot()


def test_edge_trigger_snapshot_is_strict_typed_and_read_only():
    transport = FakeTransport(
        responses={
            "TRIGger:A:TYPE?": "EDGE",
            "TRIGger:A:SOURce?": "CH2",
            "TRIGger:A:MODE?": "AUTO",
            "TRIGger:A:EDGE:SLOPe?": "POS",
            "TRIGger:A:EDGE:COUpling?": "DC",
            "TRIGger:A:LEVel2?": "5.3000E-01",
            "TRIGger:A:HYSTEResis?": "AUTO",
            "TRIGger:A:HOLDoff:MODE?": "OFF",
            "TRIGger:A:HOLDoff:TIME?": "5.00000E-08",
        }
    )

    snapshot = RTM2032Scope(transport).edge_trigger_snapshot()

    assert snapshot.trigger_type == "EDGE"
    assert snapshot.source_channel == 2
    assert snapshot.mode == "AUTO"
    assert snapshot.slope == "POS"
    assert snapshot.coupling == "DC"
    assert snapshot.level_v == 0.53
    assert snapshot.hysteresis_mode == "AUTO"
    assert snapshot.holdoff_mode == "OFF"
    assert snapshot.holdoff_time_s == 50e-9
    assert transport.writes == []
    assert transport.queries == [
        "TRIGger:A:TYPE?",
        "TRIGger:A:SOURce?",
        "TRIGger:A:MODE?",
        "TRIGger:A:EDGE:SLOPe?",
        "TRIGger:A:EDGE:COUpling?",
        "TRIGger:A:LEVel2?",
        "TRIGger:A:HYSTEResis?",
        "TRIGger:A:HOLDoff:MODE?",
        "TRIGger:A:HOLDoff:TIME?",
    ]


@pytest.mark.parametrize(
    ("command", "response"),
    [
        ("TRIGger:A:TYPE?", "PULSE"),
        ("TRIGger:A:SOURce?", "EXT"),
        ("TRIGger:A:MODE?", "NORM"),
        ("TRIGger:A:EDGE:SLOPe?", "NEG"),
        ("TRIGger:A:EDGE:COUpling?", "AC"),
        ("TRIGger:A:LEVel2?", "nan"),
        ("TRIGger:A:HYSTEResis?", "0.1"),
        ("TRIGger:A:HOLDoff:MODE?", "TIME"),
        ("TRIGger:A:HOLDoff:TIME?", "0"),
    ],
)
def test_edge_trigger_snapshot_rejects_unverified_or_malformed_responses(
    command, response
):
    responses = {
        "TRIGger:A:TYPE?": "EDGE",
        "TRIGger:A:SOURce?": "CH2",
        "TRIGger:A:MODE?": "AUTO",
        "TRIGger:A:EDGE:SLOPe?": "POS",
        "TRIGger:A:EDGE:COUpling?": "DC",
        "TRIGger:A:LEVel2?": "0.53",
        "TRIGger:A:HYSTEResis?": "AUTO",
        "TRIGger:A:HOLDoff:MODE?": "OFF",
        "TRIGger:A:HOLDoff:TIME?": "5e-8",
    }
    responses[command] = response

    with pytest.raises(DataError):
        RTM2032Scope(FakeTransport(responses=responses)).edge_trigger_snapshot()


def test_configure_ch2_edge_trigger_uses_canonical_writes_and_exact_readback():
    transport = TriggerControlTransport()
    scope = RTM2032Scope(transport)

    snapshot = scope.configure_ch2_edge_trigger(level_v=0.65)

    assert snapshot.source_channel == 2
    assert snapshot.level_v == 0.65
    assert scope.trigger_writes_blocked is False
    assert transport.writes == [
        "TRIGger:A:TYPE EDGE",
        "TRIGger:A:SOURce CH2",
        "TRIGger:A:MODE AUTO",
        "TRIGger:A:EDGE:SLOPe POS",
        "TRIGger:A:EDGE:COUpling DC",
        "TRIGger:A:LEVel2 0.65",
    ]
    assert transport.queries.count("TRIGger:A:LEVel2?") == 2
    assert transport.queries.count("*IDN?") == 2
    assert transport.queries.count("*OPT?") == 2


@pytest.mark.parametrize("level_v", [True, None, "0.65", float("nan"), float("inf")])
def test_configure_ch2_edge_trigger_rejects_invalid_level_without_io(level_v):
    transport = TriggerControlTransport()

    with pytest.raises(DataError):
        RTM2032Scope(transport).configure_ch2_edge_trigger(level_v=level_v)

    assert transport.queries == []
    assert transport.writes == []


@pytest.mark.parametrize(
    "transport",
    [
        TriggerControlTransport(questionable_before=1),
        TriggerControlTransport(source="CH1"),
        TriggerControlTransport(channel_state="0"),
        TriggerControlTransport(channel_coupling="DC"),
        TriggerControlTransport(channel_overload="1"),
    ],
)
def test_configure_ch2_edge_trigger_preflight_failure_does_not_latch(transport):
    scope = RTM2032Scope(transport)

    with pytest.raises(RTM2000TriggerControlError) as exc_info:
        scope.configure_ch2_edge_trigger(level_v=0.65)

    assert exc_info.value.phase == "preflight"
    assert scope.trigger_writes_blocked is False
    assert transport.writes == []


def test_configure_ch2_edge_trigger_rejects_level_outside_current_range():
    transport = TriggerControlTransport()
    scope = RTM2032Scope(transport)

    with pytest.raises(RTM2000TriggerControlError) as exc_info:
        scope.configure_ch2_edge_trigger(level_v=2.1)

    assert exc_info.value.phase == "preflight"
    assert scope.trigger_writes_blocked is False
    assert transport.writes == []


@pytest.mark.parametrize(
    ("transport", "expected_phase"),
    [
        (TriggerControlTransport(fail_write_at=1), "write"),
        (TriggerControlTransport(ignore_level_write=True), "readback"),
        (TriggerControlTransport(change_holdoff_after=True), "readback"),
        (TriggerControlTransport(questionable_after=1), "health-postcheck"),
        (TriggerControlTransport(change_identity_after=True), "identity-postcheck"),
    ],
)
def test_trigger_write_uncertainty_latches_and_next_write_has_zero_io(
    transport, expected_phase
):
    scope = RTM2032Scope(transport)

    with pytest.raises(RTM2000TriggerControlError) as exc_info:
        scope.configure_ch2_edge_trigger(level_v=0.65)

    assert exc_info.value.phase == expected_phase
    assert scope.trigger_writes_blocked is True
    query_count = len(transport.queries)
    write_count = len(transport.writes)
    with pytest.raises(RTM2000TriggerControlError) as blocked:
        scope.configure_ch2_edge_trigger(level_v=0.7)
    assert blocked.value.phase == "blocked"
    assert len(transport.queries) == query_count
    assert len(transport.writes) == write_count


def test_close_cannot_interleave_with_trigger_control_transaction():
    entered_write = Event()
    release_write = Event()

    class BlockingTriggerTransport(TriggerControlTransport):
        def write(self, command):
            if not self.writes:
                entered_write.set()
                assert release_write.wait(timeout=2)
            super().write(command)

    transport = BlockingTriggerTransport()
    scope = RTM2032Scope(transport)
    setter_errors = []

    def run_setter():
        try:
            scope.configure_ch2_edge_trigger(level_v=0.65)
        except Exception as exc:  # pragma: no cover - asserted below
            setter_errors.append(exc)

    setter = Thread(target=run_setter)
    closer = Thread(target=scope.close)

    setter.start()
    assert entered_write.wait(timeout=2)
    closer.start()
    assert transport.closed is False
    release_write.set()
    setter.join(timeout=2)
    closer.join(timeout=2)

    assert not setter.is_alive()
    assert not closer.is_alive()
    assert setter_errors == []
    assert transport.closed is True


def test_analog_channel_snapshot_is_typed_and_read_only():
    transport = FakeTransport(
        responses={
            "CHANnel2:BANDwidth?": "FULL",
            "CHANnel2:STATE?": "1",
            "CHANnel2:COUPling?": "DCL",
            "CHANnel2:RANGE?": "4.0",
            "CHANnel2:SCALe?": "0.5",
            "CHANnel2:OFFSET?": "0.0",
            "CHANnel2:POSITION?": "-2.8",
            "CHANnel2:POLarity?": "NORM",
            "CHANnel2:SKEW?": "0.0",
            "CHANnel2:LABel?": '"CAL"',
            "CHANnel2:LABel:STATE?": "ON",
            "CHANnel2:OVERload?": "0",
            "CHANnel2:TYPE?": "SAMP",
        }
    )

    snapshot = RTM2032Scope(transport).analog_channel_snapshot(2)

    assert snapshot.channel == 2
    assert snapshot.enabled is True
    assert snapshot.coupling == "DCL"
    assert snapshot.range_v == 4.0
    assert snapshot.scale_v_per_div == 0.5
    assert snapshot.offset_v == 0.0
    assert snapshot.position_div == -2.8
    assert snapshot.bandwidth_hz is None
    assert snapshot.polarity == "NORM"
    assert snapshot.skew_s == 0.0
    assert snapshot.label == "CAL"
    assert snapshot.label_enabled is True
    assert snapshot.overloaded is False
    assert snapshot.acquisition_type == "SAMP"
    assert transport.writes == []
    assert transport.queries == [
        "CHANnel2:STATE?",
        "CHANnel2:COUPling?",
        "CHANnel2:RANGE?",
        "CHANnel2:SCALe?",
        "CHANnel2:OFFSET?",
        "CHANnel2:POSITION?",
        "CHANnel2:BANDwidth?",
        "CHANnel2:POLarity?",
        "CHANnel2:SKEW?",
        "CHANnel2:LABel?",
        "CHANnel2:LABel:STATE?",
        "CHANnel2:OVERload?",
        "CHANnel2:TYPE?",
    ]


def test_timebase_snapshot_is_typed_and_read_only():
    transport = FakeTransport(
        responses={
            "TIMebase:ACQTime?": "2e-3",
            "TIMebase:DIVisions?": "10",
            "TIMebase:POSition?": "0",
            "TIMebase:RANGE?": "2e-3",
            "TIMebase:REFerence?": "50",
            "TIMebase:SCALe?": "2e-4",
            "TIMebase:ROLL:ENABLE?": "OFF",
        }
    )

    snapshot = RTM2032Scope(transport).timebase_snapshot()

    assert snapshot.acquisition_time_s == 2e-3
    assert snapshot.divisions == 10
    assert snapshot.position_s == 0.0
    assert snapshot.range_s == 2e-3
    assert snapshot.reference_percent == 50.0
    assert snapshot.scale_s_per_div == 2e-4
    assert snapshot.roll_enabled is False
    assert transport.writes == []
    assert transport.queries == [
        "TIMebase:ACQTime?",
        "TIMebase:DIVisions?",
        "TIMebase:POSition?",
        "TIMebase:RANGE?",
        "TIMebase:REFerence?",
        "TIMebase:SCALe?",
        "TIMebase:ROLL:ENABLE?",
    ]


def test_probe_snapshot_maps_unavailable_values_to_none():
    transport = FakeTransport(
        responses={
            "PROBe1:SETup:IMPedance?": "UNKN",
            "PROBe1:SETup:ATTenuation:AUTO?": "1",
            "PROBe1:SETup:BANDwidth?": "9.91E+37",
            "PROBe1:SETup:CAPacitance?": "9.91E+37",
            "PROBe1:SETup:NAME?": '""',
            "PROBe1:SETup:TYPE?": "NONE",
        }
    )

    snapshot = RTM2032Scope(transport).probe_snapshot(1)

    assert snapshot.channel == 1
    assert snapshot.attenuation_factor == 1.0
    assert snapshot.bandwidth_hz is None
    assert snapshot.capacitance_f is None
    assert snapshot.impedance_ohm is None
    assert snapshot.name == ""
    assert snapshot.probe_type == "NONE"
    assert transport.writes == []
    assert transport.queries == [
        "PROBe1:SETup:ATTenuation:AUTO?",
        "PROBe1:SETup:BANDwidth?",
        "PROBe1:SETup:CAPacitance?",
        "PROBe1:SETup:IMPedance?",
        "PROBe1:SETup:NAME?",
        "PROBe1:SETup:TYPE?",
    ]


@pytest.mark.parametrize("channel", [0, 3, True])
def test_channel_and_probe_snapshots_reject_invalid_channels_without_io(channel):
    for method_name in ("analog_channel_snapshot", "probe_snapshot"):
        transport = FakeTransport()
        with pytest.raises(DataError, match="channel must be 1 or 2"):
            getattr(RTM2032Scope(transport), method_name)(channel)
        assert transport.queries == []
        assert transport.writes == []


@pytest.mark.parametrize(
    ("command", "response"),
    [
        ("CHANnel1:STATE?", "MAYBE"),
        ("CHANnel1:COUPling?", "UNKNOWN"),
        ("CHANnel1:RANGE?", "nan"),
        ("CHANnel1:LABel?", "unquoted"),
        ("CHANnel1:TYPE?", "bad token"),
    ],
)
def test_analog_channel_snapshot_rejects_malformed_responses(command, response):
    responses = {
        "CHANnel1:BANDwidth?": "FULL",
        "CHANnel1:STATE?": "1",
        "CHANnel1:COUPling?": "DCL",
        "CHANnel1:RANGE?": "4.0",
        "CHANnel1:SCALe?": "0.5",
        "CHANnel1:OFFSET?": "0.0",
        "CHANnel1:POSITION?": "0.0",
        "CHANnel1:POLarity?": "NORM",
        "CHANnel1:SKEW?": "0.0",
        "CHANnel1:LABel?": '"CH1"',
        "CHANnel1:LABel:STATE?": "0",
        "CHANnel1:OVERload?": "0",
        "CHANnel1:TYPE?": "SAMP",
    }
    responses[command] = response

    with pytest.raises(DataError):
        RTM2032Scope(FakeTransport(responses=responses)).analog_channel_snapshot(1)


@pytest.mark.parametrize(
    ("command", "response"),
    [
        ("TIMebase:ACQTime?", "0"),
        ("TIMebase:DIVisions?", "10.5"),
        ("TIMebase:POSition?", "nan"),
        ("TIMebase:REFerence?", "101"),
        ("TIMebase:ROLL:ENABLE?", "MAYBE"),
    ],
)
def test_timebase_snapshot_rejects_malformed_responses(command, response):
    responses = {
        "TIMebase:ACQTime?": "2e-3",
        "TIMebase:DIVisions?": "10",
        "TIMebase:POSition?": "0",
        "TIMebase:RANGE?": "2e-3",
        "TIMebase:REFerence?": "50",
        "TIMebase:SCALe?": "2e-4",
        "TIMebase:ROLL:ENABLE?": "OFF",
    }
    responses[command] = response

    with pytest.raises(DataError):
        RTM2032Scope(FakeTransport(responses=responses)).timebase_snapshot()


@pytest.mark.parametrize(
    ("command", "response"),
    [
        ("PROBe1:SETup:ATTenuation:AUTO?", "0"),
        ("PROBe1:SETup:BANDwidth?", "nan"),
        ("PROBe1:SETup:CAPacitance?", "-1"),
        ("PROBe1:SETup:IMPedance?", "BAD"),
        ("PROBe1:SETup:NAME?", "unquoted"),
        ("PROBe1:SETup:TYPE?", "bad token"),
    ],
)
def test_probe_snapshot_rejects_malformed_responses(command, response):
    responses = {
        "PROBe1:SETup:ATTenuation:AUTO?": "1",
        "PROBe1:SETup:BANDwidth?": "9.91E+37",
        "PROBe1:SETup:CAPacitance?": "9.91E+37",
        "PROBe1:SETup:IMPedance?": "UNKN",
        "PROBe1:SETup:NAME?": '""',
        "PROBe1:SETup:TYPE?": "NONE",
    }
    responses[command] = response

    with pytest.raises(DataError):
        RTM2032Scope(FakeTransport(responses=responses)).probe_snapshot(1)


def test_waveform_metadata_snapshot_is_typed_read_only_and_consistent():
    transport = FakeTransport(
        responses={
            "CHANnel2:DATA:HEADer?": "-1e-3,1e-3,1001,1",
            "CHANnel2:DATA:POINTs?": "1001",
            "CHANnel2:DATA:XINCrement?": "2e-6",
            "CHANnel2:DATA:XORigin?": "-1e-3",
            "CHANnel2:DATA:YINCrement?": "1e-3",
            "CHANnel2:DATA:YORigin?": "-0.128",
            "CHANnel2:DATA:YRESolution?": "8",
        }
    )

    snapshot = RTM2032Scope(transport).waveform_metadata_snapshot(2)

    assert snapshot.channel == 2
    assert snapshot.x_start_s == -1e-3
    assert snapshot.x_stop_s == 1e-3
    assert snapshot.points == 1001
    assert snapshot.values_per_sample == 1
    assert snapshot.x_increment_s == 2e-6
    assert snapshot.x_origin_s == -1e-3
    assert snapshot.y_increment_v == 1e-3
    assert snapshot.y_origin_v == -0.128
    assert snapshot.y_resolution_bits == 8
    assert transport.writes == []
    assert transport.queries == [
        "CHANnel2:DATA:HEADer?",
        "CHANnel2:DATA:POINTs?",
        "CHANnel2:DATA:XINCrement?",
        "CHANnel2:DATA:XORigin?",
        "CHANnel2:DATA:YINCrement?",
        "CHANnel2:DATA:YORigin?",
        "CHANnel2:DATA:YRESolution?",
    ]


def test_waveform_metadata_snapshot_rejects_invalid_channel_without_io():
    transport = FakeTransport()

    with pytest.raises(DataError, match="must be 1 or 2"):
        RTM2032Scope(transport).waveform_metadata_snapshot(3)

    assert transport.queries == []
    assert transport.writes == []


@pytest.mark.parametrize(
    ("command", "response"),
    [
        ("CHANnel1:DATA:HEADer?", "nan,1,1001,1"),
        ("CHANnel1:DATA:HEADer?", "1,-1,1001,1"),
        ("CHANnel1:DATA:POINTs?", "1000"),
        ("CHANnel1:DATA:XINCrement?", "0"),
        ("CHANnel1:DATA:XINCrement?", "3e-6"),
        ("CHANnel1:DATA:XORigin?", "nan"),
        ("CHANnel1:DATA:XORigin?", "-2e-3"),
        ("CHANnel1:DATA:YINCrement?", "-1"),
        ("CHANnel1:DATA:YORigin?", "inf"),
        ("CHANnel1:DATA:YRESolution?", "8.5"),
    ],
)
def test_waveform_metadata_snapshot_rejects_malformed_or_inconsistent_responses(
    command,
    response,
):
    responses = {
        "CHANnel1:DATA:HEADer?": "-1e-3,1e-3,1001,1",
        "CHANnel1:DATA:POINTs?": "1001",
        "CHANnel1:DATA:XINCrement?": "2e-6",
        "CHANnel1:DATA:XORigin?": "-1e-3",
        "CHANnel1:DATA:YINCrement?": "1e-3",
        "CHANnel1:DATA:YORigin?": "0",
        "CHANnel1:DATA:YRESolution?": "8",
    }
    responses[command] = response

    with pytest.raises(DataError):
        RTM2032Scope(FakeTransport(responses=responses)).waveform_metadata_snapshot(1)


def test_header_parser_and_fetch_preserve_real_waveform_semantics():
    header = parse_waveform_header("-1e-3,1e-3,3,1")
    assert header.points == 3
    assert header.segment is None
    transport = FakeTransport(
        responses={"CHAN2:DATA:HEAD?": "-1e-3,1e-3,3,1"},
        float_lists={"CHAN2:DATA?": [-0.25, 0.0, 0.25]},
    )

    waveform = RTM2032Scope(transport).fetch_waveform(
        channel=2,
        points="def",
        check_errors=False,
    )

    assert waveform.channel == 2
    assert waveform.header.segment is None
    np.testing.assert_allclose(waveform.voltages_v, [-0.25, 0.0, 0.25])
    assert transport.writes == [
        "CHAN2:STAT ON",
        "FORM REAL",
        "FORM:BORD LSBF",
        "CHAN:DATA:POIN DEF",
    ]
    assert transport.float_list_calls == [("CHAN2:DATA?", None)]
    assert any(
        direction == "telemetry"
        and "operation=rtm2000_waveform" in text
        and "point_mode=DEF" in text
        and "points=3" in text
        for direction, text in transport.events
    )


@pytest.mark.parametrize("points", ["MAX", "dmax"])
def test_long_record_modes_use_dedicated_transfer_timeout(points):
    transport = FakeTransport(
        responses={"CHAN1:DATA:HEAD?": "0,1,2,1"},
        float_lists={"CHAN1:DATA?": [0.0, 1.0]},
    )
    scope = RTM2032Scope(transport, long_waveform_timeout_ms=456_000)

    waveform = scope.fetch_waveform(
        channel=1,
        points=points,
        check_errors=False,
    )

    assert waveform.sample_count == 2
    assert transport.float_list_calls == [("CHAN1:DATA?", 456_000)]


def test_descriptor_rejects_invalid_long_record_timeout():
    descriptor = plugin_descriptor()

    with pytest.raises(ValueError, match="must be >= 1000"):
        descriptor.validate_options({"long_waveform_timeout_ms": 999})


def test_fetch_accepts_full_length_all_zero_waveform():
    transport = FakeTransport(
        responses={"CHAN1:DATA:HEAD?": "0,1,4,1"},
        float_lists={"CHAN1:DATA?": [0.0, 0.0, 0.0, 0.0]},
    )

    waveform = RTM2032Scope(transport).fetch_waveform(
        channel=1,
        points="DEF",
        check_errors=False,
    )

    assert waveform.sample_count == 4
    np.testing.assert_array_equal(waveform.voltages_v, np.zeros(4))


@pytest.mark.parametrize(
    "header",
    [
        "bad",
        "0,1,0,1",
        "0,1,2.5,1",
        "0,1,2,1.5",
        "0,1,2,0",
        "0,1,2,1,extra",
        "nan,1,2,1",
        "0,inf,2,1",
        "1,0,2,1",
        "0,0,2,1",
    ],
)
def test_header_parser_rejects_invalid_or_zero_point_headers(header):
    with pytest.raises(DataError):
        parse_waveform_header(header)


def test_public_header_parser_does_not_mislabel_values_per_sample_as_segment():
    assert parse_waveform_header("0,1,2,2").segment is None


@pytest.mark.parametrize("values", [[], [0.0]])
def test_fetch_rejects_empty_or_short_waveform_data(values):
    transport = FakeTransport(
        responses={"CHAN1:DATA:HEAD?": "0,1,2,1"},
        float_lists={"CHAN1:DATA?": values},
    )

    with pytest.raises(DataError, match="waveform length mismatch"):
        RTM2032Scope(transport).fetch_waveform(
            channel=1,
            points="DEF",
            check_errors=False,
        )


def test_single_capture_timeout_is_explicit_and_not_retried():
    transport = FakeTransport()
    transport.opc_error = TimeoutError("timeout")

    with pytest.raises(OperationTimeout, match="single acquisition timed out"):
        RTM2032Scope(transport).capture_waveform(
            channel=1,
            points="DEF",
            check_errors=False,
        )

    assert transport.writes.count("SINGle") == 1
    assert transport.queries.count("*OPC?") == 1


def test_dual_channel_capture_uses_one_acquisition_and_reports_callbacks():
    transport = FakeTransport(
        responses={
            "CHAN1:STAT?": "1",
            "CHAN2:STAT?": "ON",
            "CHAN1:DATA:HEAD?": "0,1,2,1",
            "CHAN2:DATA:HEAD?": "0,1,2,1",
            "SYST:ERR?": '0,"No error"',
        },
        float_lists={
            "CHAN1:DATA?": [0.0, 1.0],
            "CHAN2:DATA?": [1.0, 0.0],
        },
    )
    started = []
    completed = []

    waveforms = RTM2032Scope(transport).capture_waveforms(
        channels=[1, 2],
        points="DEF",
        on_channel_start=started.append,
        on_waveform=lambda channel, waveform: completed.append(
            (channel, waveform.sample_count)
        ),
    )

    assert list(waveforms) == [1, 2]
    assert started == [1, 2, None]
    assert completed == [(1, 2), (2, 2)]
    assert transport.writes.count("SINGle") == 1
    assert transport.queries.count("*OPC?") == 1


def test_dual_channel_capture_rejects_inactive_channel_before_trigger():
    transport = FakeTransport(
        responses={"CHAN1:STAT?": "1", "CHAN2:STAT?": "0"}
    )

    with pytest.raises(DataError, match="channel 2 did not become active"):
        RTM2032Scope(transport).capture_waveforms(
            channels=[1, 2],
            points="DEF",
            check_errors=False,
        )

    assert "SINGle" not in transport.writes


def test_screenshot_error_queue_autoscale_and_close():
    png = b"\x89PNG\r\n\x1a\nrtm"
    transport = FakeTransport(
        responses={
            "HCOP:DATA?": png,
            "SYST:ERR?": '0,"No error"',
        }
    )
    scope = RTM2032Scope(transport)

    scope.autoscale()
    assert scope.screenshot_png(include_menu=True, color_scheme="MONO") == png
    scope.close()

    assert transport.writes[:1] == ["AUToscale"]
    assert transport.writes[-3:] == [
        "HCOP:LANG PNG",
        "HCOP:COL:SCH MONO",
        "HCOP:MENU ON",
    ]
    assert transport.closed


def test_screenshot_and_error_queue_fail_closed():
    with pytest.raises(DataError, match="not a PNG"):
        RTM2032Scope(
            FakeTransport(responses={"HCOP:DATA?": b"not-png"})
        ).screenshot_png()

    transport = FakeTransport(
        responses={"SYST:ERR?": '-100,"Command error"'}
    )
    with pytest.raises(InstrumentError, match="error queue is not empty"):
        RTM2032Scope(transport).assert_no_errors()
    assert len(transport.queries) == 16


@pytest.mark.parametrize(
    ("response", "coupling", "termination"),
    [
        ("AC", "ac", "50_ohm"),
        ("ACL", "ac", "high_z"),
        ("DC", "dc", "50_ohm"),
        ("DCL", "dc", "high_z"),
        ("GND", "gnd", "unknown"),
    ],
)
def test_channel_input_state_v2_maps_portable_coupling_without_writes(
    response,
    coupling,
    termination,
):
    command = "CHANnel2:COUPling?"
    transport = FakeTransport(responses={command: response})

    assert RTM2032Scope(transport).get_channel_input_state_v2(2) == (
        ScopeChannelInputStateV2(
            channel=2,
            coupling=coupling,
            termination=termination,
            impedance_ohm=None,
            unavailable_fields=("impedance_ohm",),
        )
    )
    assert transport.queries == [command]
    assert transport.writes == []


def _channel_display_baseline(
    channel: int,
    *,
    enabled: bool,
) -> ScopeChannelDisplayBaseline:
    return ScopeChannelDisplayBaseline(
        context_id="context",
        session_epoch="epoch",
        baseline_nonce="nonce",
        snapshot=ScopeChannelDisplayState(channel=channel, enabled=enabled),
        restore_order=("scope.channel_display",),
    )


@pytest.mark.parametrize(
    ("response", "enabled"),
    [("1", True), ("ON", True), ("0", False), ("OFF", False)],
)
def test_channel_display_state_v2_is_typed_and_read_only(response, enabled):
    command = "CHANnel2:STATE?"
    transport = FakeTransport(responses={command: response})

    assert RTM2032Scope(transport).get_channel_display_state_v2(2) == (
        ScopeChannelDisplayState(channel=2, enabled=enabled)
    )
    assert transport.queries == [command]
    assert transport.writes == []


@pytest.mark.parametrize(("enabled", "token"), [(True, "ON"), (False, "OFF")])
def test_channel_display_configure_v2_writes_requested_state(enabled, token):
    transport = FakeTransport()
    request = ScopeChannelDisplayRequest(channel=1, enabled=enabled)

    assert RTM2032Scope(transport).configure_channel_display_v2(
        request,
        baseline=_channel_display_baseline(1, enabled=not enabled),
    ) is None
    assert transport.queries == []
    assert transport.writes == [f"CHANnel1:STATE {token}"]


@pytest.mark.parametrize(("enabled", "token"), [(True, "ON"), (False, "OFF")])
def test_channel_display_restore_v2_replays_baseline(enabled, token):
    transport = FakeTransport()
    baseline = _channel_display_baseline(2, enabled=enabled)

    result = RTM2032Scope(transport).restore_channel_display_v2(baseline)

    assert result == ScopeChannelDisplayRestoreResult(
        status="completed",
        attempted_fields=("scope.channel_display",),
        restored_fields=("scope.channel_display",),
    )
    result.validate_for(baseline)
    assert transport.queries == []
    assert transport.writes == [f"CHANnel2:STATE {token}"]


def test_channel_display_v2_rejects_invalid_channel_and_baseline_before_io():
    transport = FakeTransport()
    driver = RTM2032Scope(transport)

    with pytest.raises(DataError, match="RTM2032 channel must be 1 or 2"):
        driver.get_channel_display_state_v2(3)
    with pytest.raises(DataError, match="RTM2032 channel must be 1 or 2"):
        driver.configure_channel_display_v2(
            ScopeChannelDisplayRequest(channel=3, enabled=True),
            baseline=_channel_display_baseline(3, enabled=False),
        )
    with pytest.raises(ValueError, match="baseline uses a different channel"):
        driver.configure_channel_display_v2(
            ScopeChannelDisplayRequest(channel=2, enabled=True),
            baseline=_channel_display_baseline(1, enabled=False),
        )
    with pytest.raises(DataError, match="RTM2032 channel must be 1 or 2"):
        driver.restore_channel_display_v2(
            _channel_display_baseline(3, enabled=False)
        )

    assert transport.queries == []
    assert transport.writes == []


def test_channel_display_state_v2_rejects_malformed_response_without_writes():
    command = "CHANnel1:STATE?"
    transport = FakeTransport(responses={command: "MAYBE"})

    with pytest.raises(DataError, match="invalid CHANnel1:STATE\\? response"):
        RTM2032Scope(transport).get_channel_display_state_v2(1)

    assert transport.queries == [command]
    assert transport.writes == []


def test_digital_status_v2_reuses_verified_b1_status_without_inventing_fields():
    responses = {
        "*OPT?": "K15,B1",
        "DIGital5:CURRENT:STATE:MINimum?": "0",
        "DIGital5:CURRENT:STATE:MAXimum?": "1",
        "DIGital5:DISPLAY?": "ON",
        "DIGital5:TECHnology?": "TTL",
        "DIGital5:THReshold?": "1.4",
        "DIGital5:THCoupling?": "OFF",
        "DIGital5:Hysteresis?": "NORM",
        "DIGital5:DESKew?": "2e-9",
        "DIGital5:SIZE?": "SMAL",
        "DIGital5:POSITION?": "2.5",
        "DIGital5:LABel?": '"DATA"',
        "DIGital5:LABel:STATe?": "1",
    }
    transport = FakeTransport(responses=responses)

    assert RTM2032Scope(transport).get_digital_status_v2(5) == (
        ScopeDigitalChannelStatusV2(
            channel=5,
            displayed=True,
            position_div=2.5,
            label="DATA",
            label_enabled=True,
            activity="TOGGLE",
            technology="TTL",
            hysteresis="NORMAL",
            pod=ScopeDigitalPodStatusV2(
                start_channel=4,
                stop_channel=7,
                threshold_v=1.4,
            ),
            shared=ScopeDigitalSharedStatusV2(
                module_present=True,
                size="SMALL",
            ),
            unavailable_fields=(
                "pod.threshold_scope",
                "shared.timing_calibration_s",
            ),
        )
    )
    assert transport.queries == list(responses)
    assert transport.writes == []


def test_snapshot_v2_is_identity_only_and_matches_descriptor_query_budget():
    transport = FakeTransport(
        responses={
            "*IDN?": "Rohde&Schwarz,RTM2032,123,3.5",
            "*OPT?": "B1,K15",
        }
    )
    result = RTM2032Scope(transport).get_snapshot_v2(
        1,
        fields=RTM2000_SNAPSHOT_V2_READABLE_FIELDS,
    )

    assert result.identity == ScopeIdentitySnapshot(
        "Rohde&Schwarz",
        "RTM2032",
        "123",
        "3.5",
        ("B1", "K15"),
    )
    RTM2000_SCOPE_EXTENSIONS.snapshot_profile_v2.validate_result(result, channel=1)
    assert transport.queries == ["*IDN?", "*OPT?"]
    assert transport.writes == []


def test_snapshot_v2_rejects_non_profile_fields_without_io():
    transport = FakeTransport()

    with pytest.raises(ConfigError, match="exact readable field profile"):
        RTM2032Scope(transport).get_snapshot_v2(
            1,
            fields=(*RTM2000_SNAPSHOT_V2_READABLE_FIELDS, "health.status_byte"),
        )

    assert transport.queries == []
    assert transport.writes == []


def test_measurement_statistics_v2_maps_complete_slot_aggregates():
    responses = {
        "MEASurement2:CATegory?": "AMPTime",
        "MEASurement2:RESult:ACTual?": "1.0",
        "MEASurement2:RESult:AVG?": "0.9",
        "MEASurement2:RESult:STDDev?": "0.1",
        "MEASurement2:RESult:NPEak?": "0.7",
        "MEASurement2:RESult:PPEak?": "1.1",
        "MEASurement2:RESult:WFMCount?": "42",
    }
    transport = FakeTransport(responses=responses)
    request = ScopeMeasurementStatisticsRequestV2(
        selector=ScopeMeasurementSelector(slot=2),
        configured=True,
    )

    result = RTM2032Scope(transport).get_measurement_statistics_v2(request)

    assert result == ScopeMeasurementStatisticsV2(
        selector=request.selector,
        category="AMPTIME",
        actual=1.0,
        average=0.9,
        standard_deviation=0.1,
        minimum=0.7,
        maximum=1.1,
        waveform_count=42,
    )
    RTM2000_SCOPE_EXTENSIONS.measurement_statistics_profile_v2.validate_result(
        result,
        request=request,
    )
    assert transport.queries == list(responses)
    assert transport.writes == []


def test_measurement_statistics_v2_rejects_incomplete_aggregate():
    responses = {
        "MEASurement2:CATegory?": "AMPTime",
        "MEASurement2:RESult:ACTual?": "NAN",
        "MEASurement2:RESult:AVG?": "0.9",
        "MEASurement2:RESult:STDDev?": "0.1",
        "MEASurement2:RESult:NPEak?": "0.7",
        "MEASurement2:RESult:PPEak?": "1.1",
        "MEASurement2:RESult:WFMCount?": "42",
    }
    request = ScopeMeasurementStatisticsRequestV2(
        selector=ScopeMeasurementSelector(slot=2),
        configured=True,
    )

    with pytest.raises(DataError, match="finite aggregate values"):
        RTM2032Scope(FakeTransport(responses=responses)).get_measurement_statistics_v2(
            request
        )


def test_fft_status_v2_maps_only_profiled_fields():
    responses = {
        "CALCulate:MATH1:FFT:AVERAGE:COMPLETE?": "1",
        "CALCulate:MATH1:FFT:BANDwidth:RESolution:ADJusted?": "10",
        "CALCulate:MATH1:FFT:SRATe?": "1000000",
    }
    transport = FakeTransport(responses=responses)

    result = RTM2032Scope(transport).get_fft_status_v2(1, configured_fft=True)

    assert result == ScopeFftStatusV2(
        math_index=1,
        average_complete=True,
        resolution_bandwidth_hz=10.0,
        sample_rate_hz=1_000_000.0,
        unavailable_fields=(
            "source",
            "window",
            "vertical_unit",
            "frequency_start_hz",
            "frequency_stop_hz",
        ),
    )
    RTM2000_SCOPE_EXTENSIONS.fft_status_profile_v2.validate_result(
        result,
        math_index=1,
    )
    assert transport.queries == list(responses)
    assert transport.writes == []


@pytest.mark.parametrize(
    ("invoke", "error", "message"),
    [
        (
            lambda driver: driver.get_channel_input_state_v2(3),
            DataError,
            "RTM2032 channel must be 1 or 2",
        ),
        (
            lambda driver: driver.get_digital_status_v2(16),
            DataError,
            "RTM2000 digital channel must be an integer from 0 through 15",
        ),
        (
            lambda driver: driver.get_snapshot_v2(
                3,
                fields=RTM2000_SNAPSHOT_V2_READABLE_FIELDS,
            ),
            DataError,
            "RTM2032 channel must be 1 or 2",
        ),
        (
            lambda driver: driver.get_measurement_statistics_v2(
                ScopeMeasurementStatisticsRequestV2(
                    selector=ScopeMeasurementSelector(slot=5),
                    configured=True,
                )
            ),
            ValueError,
            "supports slots 1 through 4",
        ),
        (
            lambda driver: driver.get_measurement_statistics_v2(
                ScopeMeasurementStatisticsRequestV2(
                    selector=ScopeMeasurementSelector(slot=1),
                    configured=True,
                    include_buffer=True,
                    acquisition_stopped=True,
                )
            ),
            ValueError,
            "does not support buffers",
        ),
        (
            lambda driver: driver.get_fft_status_v2(1, configured_fft=False),
            ValueError,
            "explicit confirmation",
        ),
    ],
)
def test_scope_v2_invalid_requests_fail_before_io(invoke, error, message):
    transport = FakeTransport()

    with pytest.raises(error, match=message):
        invoke(RTM2032Scope(transport))

    assert transport.queries == []
    assert transport.writes == []


def test_digital_status_v2_preserves_b1_gate_without_writes():
    transport = FakeTransport(responses={"*OPT?": "K15"})

    with pytest.raises(InstrumentError, match="requires installed option B1"):
        RTM2032Scope(transport).get_digital_status_v2(0)

    assert transport.queries == ["*OPT?"]
    assert transport.writes == []
