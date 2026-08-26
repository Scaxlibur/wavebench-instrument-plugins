from __future__ import annotations

import importlib
import importlib.util

import pytest

from wavebench.instruments.rf_source_extensions import (
    RfAvailability,
    RfCwRequest,
    RfModulationDisableRequest,
    RfModulationKind,
    RfModulationRequest,
    RfModulationSource,
    RfModulationWaveform,
    RfOutputRequest,
    RfReasonCode,
)


class FakeTransport:
    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = dict(responses)
        self.query_calls: list[str] = []
        self.write_calls: list[str] = []
        self.close_calls = 0

    def query(self, command: str) -> str:
        self.query_calls.append(command)
        try:
            return self.responses[command]
        except KeyError as exc:
            raise AssertionError(f"unexpected DSG830 query: {command}") from exc

    def close(self) -> None:
        self.close_calls += 1

    def write(self, command: str) -> None:
        self.write_calls.append(command)


def _driver_type():
    spec = importlib.util.find_spec("wavebench_rigol_dsg830.driver")
    assert spec is not None
    return importlib.import_module("wavebench_rigol_dsg830.driver").DSG830RfSource


def test_driver_queries_identity_and_forwards_close() -> None:
    response = "RIGOL TECHNOLOGIES,DSG830,DSG8A170200001,00.01.01\n"
    transport = FakeTransport({"*IDN?": response})
    driver = _driver_type()(transport=transport)

    assert transport.query_calls == []
    assert driver.idn() == response
    assert transport.query_calls == ["*IDN?"]

    driver.close()

    assert transport.close_calls == 1


def _snapshot_responses(**changes: str) -> dict[str, str]:
    responses = {
        "*IDN?": "RIGOL TECHNOLOGIES,DSG830,DSG8A170200001,00.01.01\n",
        ":FREQ?": "4.00000000MHz\n",
        ":LEV?": "-20.00\n",
        ":OUTP?": "0\n",
        ":MOD:STAT?": "0\n",
        ":PULM:STAT?": "0\n",
        ":SWE:STAT?": "FREQ\n",
        ":STAT:QUES:POW:COND?": "3\n",
    }
    responses.update(changes)
    return responses


def test_driver_queries_documented_snapshot_fields_in_fixed_read_only_order() -> None:
    transport = FakeTransport(_snapshot_responses())
    driver = _driver_type()(transport=transport)
    snapshot = driver.get_rf_snapshot()

    assert transport.query_calls == [
        "*IDN?",
        ":FREQ?",
        ":LEV?",
        ":OUTP?",
        ":MOD:STAT?",
        ":PULM:STAT?",
        ":SWE:STAT?",
        ":STAT:QUES:POW:COND?",
    ]
    port = snapshot.ports[0]
    assert port.port_id == "rf_out"
    assert port.frequency_hz.value == 4_000_000.0
    assert port.power_dbm.value == -20.0
    assert port.output_enabled.value is False
    assert port.modulation.value.value == "disabled"
    assert port.pulse.value.value == "disabled"
    assert port.sweep.value.value == "enabled"
    assert snapshot.protection.value.active_codes == (
        "alc_unlocked",
        "output_power_protection",
    )
    assert driver.a1_snapshot_firmware() == "00.01.01"
    assert transport.write_calls == []


def test_driver_maps_one_offline_cw_request_to_one_documented_write() -> None:
    transport = FakeTransport(_snapshot_responses())
    driver = _driver_type()(transport=transport)

    driver.configure_cw(RfCwRequest(port_id="rf_out", frequency_hz=4_000_000.0))
    driver.configure_cw(RfCwRequest(port_id="rf_out", power_dbm=-20.0))

    assert transport.query_calls == []
    assert transport.write_calls == [":FREQ 4000000Hz", ":LEV -20dBm"]


def test_driver_rejects_an_offline_cw_request_for_another_port_before_write() -> None:
    transport = FakeTransport(_snapshot_responses())

    with pytest.raises(ValueError, match="port_id"):
        _driver_type()(transport=transport).configure_cw(
            RfCwRequest(port_id="other", frequency_hz=4_000_000.0)
        )

    assert transport.write_calls == []


def test_driver_maps_each_offline_rf_output_request_to_one_documented_write() -> None:
    transport = FakeTransport(_snapshot_responses())
    driver = _driver_type()(transport=transport)

    driver.set_rf_output(RfOutputRequest(port_id="rf_out", enabled=True))
    driver.set_rf_output(RfOutputRequest(port_id="rf_out", enabled=False))

    assert transport.query_calls == []
    assert transport.write_calls == [":OUTP ON", ":OUTP OFF"]


def test_driver_rejects_an_offline_rf_output_request_for_another_port_before_write() -> None:
    transport = FakeTransport(_snapshot_responses())

    with pytest.raises(ValueError, match="port_id"):
        _driver_type()(transport=transport).set_rf_output(
            RfOutputRequest(port_id="other", enabled=True)
        )

    assert transport.write_calls == []


def test_driver_a1_firmware_accessor_rejects_unsafe_idn_firmware_without_extra_query() -> None:
    transport = FakeTransport(
        _snapshot_responses(**{"*IDN?": "RIGOL TECHNOLOGIES,DSG830,redacted,unsafe firmware"})
    )
    driver = _driver_type()(transport=transport)

    driver.get_rf_snapshot()

    assert driver.a1_snapshot_firmware() is None
    assert transport.query_calls == [
        "*IDN?",
        ":FREQ?",
        ":LEV?",
        ":OUTP?",
        ":MOD:STAT?",
        ":PULM:STAT?",
        ":SWE:STAT?",
        ":STAT:QUES:POW:COND?",
    ]


def test_driver_returns_fail_closed_unknown_observations_for_unknown_sweep_or_protection_bits() -> None:
    responses = _snapshot_responses()
    responses[":SWE:STAT?"] = "not-used"
    responses[":STAT:QUES:POW:COND?"] = "8"
    transport = FakeTransport(responses)

    snapshot = _driver_type()(transport=transport).get_rf_snapshot()

    assert snapshot.ports[0].sweep.availability is RfAvailability.UNKNOWN
    assert snapshot.ports[0].sweep.reason_code is RfReasonCode.RESPONSE_INVALID_VALUE
    assert snapshot.protection.availability is RfAvailability.UNKNOWN
    assert snapshot.protection.reason_code is RfReasonCode.RESPONSE_INVALID_VALUE


def _modulation_responses(
    kind: RfModulationKind,
    *,
    selected_fm_pm_kind: RfModulationKind | None = None,
    **changes: str,
) -> dict[str, str]:
    responses = {
        ":MOD:STAT?": "0\n",
        ":AM:STAT?": "0\n",
        ":FM:STAT?": "0\n",
        ":PM:STAT?": "0\n",
        ":STAT:QUES:MOD:COND?": "0\n",
    }
    prefix = kind.value.upper()
    responses[f":{prefix}:SOUR?"] = "INT\n"
    responses[f":{prefix}:WAVE?"] = "SINE\n"
    responses[f":{prefix}:FREQ?"] = "1.00000000kHz\n"
    if kind is RfModulationKind.AM:
        responses[":AM:DEPT?"] = "50.00\n"
    elif kind is RfModulationKind.FM:
        selected = selected_fm_pm_kind or RfModulationKind.FM
        responses[":FMPM:TYPE?"] = f"{selected.value.upper()}\n"
        responses[":FM:DEV?"] = "20.00000000kHz\n"
    else:
        selected = selected_fm_pm_kind or RfModulationKind.PM
        responses[":FMPM:TYPE?"] = f"{selected.value.upper()}\n"
        responses[":PM:DEV?"] = "2.000000rad\n"
    responses.update(changes)
    return responses


def test_driver_reads_state_only_before_source_dependent_profile_queries() -> None:
    transport = FakeTransport(
        {
            ":MOD:STAT?": "0\n",
            ":AM:STAT?": "0\n",
            ":FM:STAT?": "0\n",
            ":PM:STAT?": "0\n",
            ":STAT:QUES:MOD:COND?": "0\n",
        }
    )

    snapshot = _driver_type()(transport=transport).get_rf_modulation_state("rf_out")

    assert transport.query_calls == [
        ":MOD:STAT?",
        ":AM:STAT?",
        ":FM:STAT?",
        ":PM:STAT?",
        ":STAT:QUES:MOD:COND?",
    ]
    assert transport.write_calls == []
    assert snapshot.port_id == "rf_out"
    assert snapshot.enabled_modes == ()
    assert snapshot.global_enabled is False
    assert snapshot.fault_codes == ()


@pytest.mark.parametrize(
    ("kind", "value_field", "expected_value", "expected_queries"),
    (
        (
            RfModulationKind.AM,
            "depth_percent",
            50.0,
            [
                ":MOD:STAT?",
                ":AM:STAT?",
                ":FM:STAT?",
                ":PM:STAT?",
                ":STAT:QUES:MOD:COND?",
                ":AM:SOUR?",
                ":AM:WAVE?",
                ":AM:DEPT?",
                ":AM:FREQ?",
            ],
        ),
        (
            RfModulationKind.FM,
            "frequency_deviation_hz",
            20_000.0,
            [
                ":MOD:STAT?",
                ":AM:STAT?",
                ":FM:STAT?",
                ":PM:STAT?",
                ":STAT:QUES:MOD:COND?",
                ":FMPM:TYPE?",
                ":FM:SOUR?",
                ":FM:WAVE?",
                ":FM:DEV?",
                ":FM:FREQ?",
            ],
        ),
        (
            RfModulationKind.PM,
            "phase_deviation_rad",
            2.0,
            [
                ":MOD:STAT?",
                ":AM:STAT?",
                ":FM:STAT?",
                ":PM:STAT?",
                ":STAT:QUES:MOD:COND?",
                ":FMPM:TYPE?",
                ":PM:SOUR?",
                ":PM:WAVE?",
                ":PM:DEV?",
                ":PM:FREQ?",
            ],
        ),
    ),
)
def test_driver_reads_complete_internal_sine_modulation_profile(
    kind: RfModulationKind,
    value_field: str,
    expected_value: float,
    expected_queries: list[str],
) -> None:
    transport = FakeTransport(_modulation_responses(kind))

    snapshot = _driver_type()(transport=transport).get_rf_modulation_snapshot("rf_out", kind)

    assert transport.query_calls == expected_queries
    assert transport.write_calls == []
    assert snapshot.port_id == "rf_out"
    assert snapshot.kind is kind
    assert snapshot.selected_fm_pm_kind is (
        kind if kind in {RfModulationKind.FM, RfModulationKind.PM} else None
    )
    assert snapshot.source is RfModulationSource.INTERNAL
    assert snapshot.waveform is RfModulationWaveform.SINE
    assert snapshot.internal_frequency_hz == 1_000.0
    assert getattr(snapshot, value_field) == expected_value
    assert snapshot.enabled_modes == ()
    assert snapshot.global_enabled is False
    assert snapshot.fault_codes == ()


@pytest.mark.parametrize(
    ("kind", "selected_fm_pm_kind"),
    (
        (RfModulationKind.FM, RfModulationKind.PM),
        (RfModulationKind.PM, RfModulationKind.FM),
    ),
)
def test_driver_reports_a_different_inactive_fm_pm_selection_without_rejecting_profile_readback(
    kind: RfModulationKind,
    selected_fm_pm_kind: RfModulationKind,
) -> None:
    transport = FakeTransport(
        _modulation_responses(kind, selected_fm_pm_kind=selected_fm_pm_kind)
    )

    snapshot = _driver_type()(transport=transport).get_rf_modulation_snapshot("rf_out", kind)

    assert snapshot.kind is kind
    assert snapshot.selected_fm_pm_kind is selected_fm_pm_kind
    assert transport.write_calls == []


def test_driver_reports_an_inactive_external_square_profile_without_rejecting_readback() -> None:
    transport = FakeTransport(
        _modulation_responses(
            RfModulationKind.AM,
            **{
                ":AM:SOUR?": "EXT\n",
                ":AM:WAVE?": "SQUA\n",
            },
        )
    )

    snapshot = _driver_type()(transport=transport).get_rf_modulation_snapshot(
        "rf_out",
        RfModulationKind.AM,
    )

    assert snapshot.source is RfModulationSource.EXTERNAL
    assert snapshot.waveform is RfModulationWaveform.SQUARE
    assert snapshot.enabled_modes == ()
    assert transport.write_calls == []


def test_driver_accepts_the_documented_frequency_response_with_one_fraction_group_space() -> None:
    transport = FakeTransport(
        _modulation_responses(RfModulationKind.AM, **{":AM:FREQ?": "1.000 00kHz\n"})
    )

    snapshot = _driver_type()(transport=transport).get_rf_modulation_snapshot(
        "rf_out",
        RfModulationKind.AM,
    )

    assert snapshot.internal_frequency_hz == 1_000.0


@pytest.mark.parametrize(
    ("modulation_request", "expected_writes"),
    (
        (
            RfModulationRequest(
                port_id="rf_out",
                kind=RfModulationKind.AM,
                internal_frequency_hz=1_000.0,
                depth_percent=50.0,
            ),
            [
                ":AM:SOUR INT",
                ":AM:WAVE SINE",
                ":AM:DEPT 50",
                ":AM:FREQ 1000Hz",
                ":AM:STAT ON",
                ":MOD:STAT ON",
            ],
        ),
        (
            RfModulationRequest(
                port_id="rf_out",
                kind=RfModulationKind.FM,
                internal_frequency_hz=1_000.0,
                frequency_deviation_hz=20_000.0,
            ),
            [
                ":FMPM:TYPE FM",
                ":FM:SOUR INT",
                ":FM:WAVE SINE",
                ":FM:DEV 20000Hz",
                ":FM:FREQ 1000Hz",
                ":FM:STAT ON",
                ":MOD:STAT ON",
            ],
        ),
        (
            RfModulationRequest(
                port_id="rf_out",
                kind=RfModulationKind.PM,
                internal_frequency_hz=1_000.0,
                phase_deviation_rad=2.0,
            ),
            [
                ":FMPM:TYPE PM",
                ":PM:SOUR INT",
                ":PM:WAVE SINE",
                ":PM:DEV 2",
                ":PM:FREQ 1000Hz",
                ":PM:STAT ON",
                ":MOD:STAT ON",
            ],
        ),
    ),
)
def test_driver_maps_each_internal_sine_modulation_request_to_fixed_writes(
    modulation_request: RfModulationRequest,
    expected_writes: list[str],
) -> None:
    transport = FakeTransport({})

    _driver_type()(transport=transport).configure_rf_modulation(modulation_request)

    assert transport.query_calls == []
    assert transport.write_calls == expected_writes


@pytest.mark.parametrize(
    "kind",
    (RfModulationKind.AM, RfModulationKind.FM, RfModulationKind.PM),
)
def test_driver_maps_each_modulation_disable_request_to_fixed_mode_and_global_writes(
    kind: RfModulationKind,
) -> None:
    transport = FakeTransport({})

    _driver_type()(transport=transport).disable_rf_modulation(
        RfModulationDisableRequest(port_id="rf_out", kind=kind)
    )

    assert transport.query_calls == []
    assert transport.write_calls == [f":{kind.value.upper()}:STAT OFF", ":MOD:STAT OFF"]


def test_driver_rejects_invalid_modulation_target_or_readback_before_unsafe_use() -> None:
    transport = FakeTransport({})
    driver = _driver_type()(transport=transport)
    invalid_port = RfModulationRequest(
        port_id="other",
        kind=RfModulationKind.AM,
        internal_frequency_hz=1_000.0,
        depth_percent=50.0,
    )

    with pytest.raises(ValueError, match="port_id"):
        driver.configure_rf_modulation(invalid_port)
    with pytest.raises(ValueError, match="port_id"):
        driver.disable_rf_modulation(
            RfModulationDisableRequest(port_id="other", kind=RfModulationKind.AM)
        )
    with pytest.raises(ValueError, match="frequency"):
        driver.configure_rf_modulation(
            RfModulationRequest(
                port_id="rf_out",
                kind=RfModulationKind.FM,
                internal_frequency_hz=1.0,
                frequency_deviation_hz=20_000.0,
            )
        )
    assert transport.write_calls == []

    malformed = FakeTransport(
        _modulation_responses(RfModulationKind.AM, **{":AM:SOUR?": "unsupported"})
    )
    with pytest.raises(ValueError, match="source response must be INT or EXT"):
        _driver_type()(transport=malformed).get_rf_modulation_snapshot(
            "rf_out",
            RfModulationKind.AM,
        )


@pytest.mark.parametrize(
    ("command", "response", "message"),
    (
        (":FREQ?", "8kHz", "frequency response is outside"),
        (":LEV?", "nan", "power response has an invalid format"),
        (":OUTP?", "ON", "RF output response must be 0 or 1"),
        (":STAT:QUES:POW:COND?", "invalid", "condition response must be an integer"),
        ("*IDN?", "RIGOL TECHNOLOGIES,DSG815,serial,firmware", "identity response"),
    ),
)
def test_driver_rejects_bad_documented_snapshot_responses(
    command: str,
    response: str,
    message: str,
) -> None:
    transport = FakeTransport(_snapshot_responses(**{command: response}))

    with pytest.raises(ValueError, match=message):
        _driver_type()(transport=transport).get_rf_snapshot()
