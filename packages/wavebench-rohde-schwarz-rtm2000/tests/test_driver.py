from __future__ import annotations

import numpy as np
import pytest

from wavebench.errors import DataError, InstrumentError, OperationTimeout
from wavebench.instruments.api import DriverContext
from wavebench.instruments.capabilities import validate_declared_capabilities
from wavebench.logging import CommandLogger
from wavebench_rohde_schwarz_rtm2000 import descriptor as plugin_descriptor
from wavebench_rohde_schwarz_rtm2000.driver import RTM2032Scope, parse_waveform_header


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
    assert driver.transport is transport
    assert driver.check_errors_after_ops is False
    assert transport_opens == 1


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


def test_header_parser_and_fetch_preserve_real_waveform_semantics():
    header = parse_waveform_header("-1e-3,1e-3,3,1")
    assert header.points == 3
    assert header.segment == 1
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


@pytest.mark.parametrize("header", ["bad", "0,1,0,1"])
def test_header_parser_rejects_invalid_or_zero_point_headers(header):
    with pytest.raises(DataError):
        parse_waveform_header(header)


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
