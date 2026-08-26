from __future__ import annotations

import importlib
import importlib.util

import pytest

from wavebench.instruments.rf_source_extensions import (
    RfAvailability,
    RfCwRequest,
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
