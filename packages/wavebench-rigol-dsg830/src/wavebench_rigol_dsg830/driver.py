"""Read-only M0 driver for the RIGOL DSG830 RF signal generator.

The public production descriptor declares only ``rf_source.idn`` until A1
hardware evidence exists.  ``get_rf_snapshot()`` is intentionally present for
strict offline parser tests and is not production-reachable through Core before
that capability promotion.
"""

from __future__ import annotations

from math import isfinite
import re

from wavebench.instruments.rf_source_extensions import (
    RfAvailability,
    RfModulationState,
    RfObserved,
    RfPortSnapshot,
    RfProtectionStatus,
    RfPulseState,
    RfReasonCode,
    RfSourceSnapshot,
    RfSweepState,
)


_FREQUENCY_MIN_HZ = 9_000.0
_FREQUENCY_MAX_HZ = 3_000_000_000.0
_POWER_MIN_DBM = -110.0
_POWER_MAX_DBM = 20.0
_NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?"
_FREQUENCY_RESPONSE = re.compile(
    rf"^(?P<value>{_NUMBER})(?P<unit>Hz|kHz|MHz|GHz)?$",
    re.IGNORECASE,
)
_DECIMAL_RESPONSE = re.compile(rf"^{_NUMBER}$")
_INTEGER_RESPONSE = re.compile(r"^\d+$")
_IDN_VENDOR = "RIGOL TECHNOLOGIES"
_IDN_MODEL = "DSG830"
_A1_FIRMWARE_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

_SNAPSHOT_QUERIES = (
    "*IDN?",
    ":FREQ?",
    ":LEV?",
    ":OUTP?",
    ":MOD:STAT?",
    ":PULM:STAT?",
    ":SWE:STAT?",
    ":STAT:QUES:POW:COND?",
)


class DSG830RfSource:
    """Strictly parse documented, read-only DSG830 snapshot queries."""

    def __init__(self, *, transport) -> None:
        self.transport = transport
        self._a1_snapshot_firmware: str | None = None

    def idn(self) -> str:
        return self.transport.query("*IDN?")

    def get_rf_snapshot(self) -> RfSourceSnapshot:
        responses = {command: self.transport.query(command) for command in _SNAPSHOT_QUERIES}
        self._a1_snapshot_firmware = _parse_idn(responses["*IDN?"])
        return RfSourceSnapshot(
            ports=(
                RfPortSnapshot(
                    port_id="rf_out",
                    frequency_hz=RfObserved.value_of(
                        _parse_frequency_hz(responses[":FREQ?"])
                    ),
                    power_dbm=RfObserved.value_of(_parse_power_dbm(responses[":LEV?"])),
                    output_enabled=RfObserved.value_of(
                        _parse_binary(responses[":OUTP?"], "RF output")
                    ),
                    modulation=RfObserved.value_of(
                        _as_modulation_state(
                            _parse_binary(responses[":MOD:STAT?"], "modulation state")
                        )
                    ),
                    pulse=RfObserved.value_of(
                        _as_pulse_state(
                            _parse_binary(responses[":PULM:STAT?"], "pulse modulation state")
                        )
                    ),
                    sweep=_parse_sweep_state(responses[":SWE:STAT?"]),
                ),
            ),
            protection=_parse_protection_status(responses[":STAT:QUES:POW:COND?"]),
        )

    def a1_snapshot_firmware(self) -> str | None:
        """Return the safe firmware token from the current A1 snapshot query set.

        This accessor performs no I/O. It is intentionally only consumed by the
        local A1 evidence harness after a successful ``get_rf_snapshot()`` call.
        """

        return self._a1_snapshot_firmware

    def close(self) -> None:
        self.transport.close()


# Compatibility alias for the seed's internal class name.  The descriptor
# always constructs the RF-specific name above.
DSG830Source = DSG830RfSource


def _clean_response(response: object, label: str) -> str:
    if not isinstance(response, str):
        raise ValueError(f"DSG830 {label} response must be text")
    value = response.strip()
    if not value:
        raise ValueError(f"DSG830 {label} response must not be empty")
    return value


def _parse_idn(response: object) -> str | None:
    value = _clean_response(response, "identity")
    fields = tuple(item.strip() for item in value.split(","))
    if (
        len(fields) != 4
        or fields[0].upper() != _IDN_VENDOR
        or fields[1].upper() != _IDN_MODEL
        or not fields[2]
        or not fields[3]
    ):
        raise ValueError("DSG830 identity response does not match the documented model")
    firmware = fields[3]
    return firmware if _A1_FIRMWARE_TOKEN.fullmatch(firmware) is not None else None


def _parse_frequency_hz(response: object) -> float:
    value = _clean_response(response, "frequency")
    match = _FREQUENCY_RESPONSE.fullmatch(value)
    if match is None:
        raise ValueError("DSG830 frequency response has an invalid format")
    frequency = _parse_finite(match.group("value"), "frequency")
    multiplier = {
        None: 1.0,
        "HZ": 1.0,
        "KHZ": 1_000.0,
        "MHZ": 1_000_000.0,
        "GHZ": 1_000_000_000.0,
    }[match.group("unit").upper() if match.group("unit") is not None else None]
    frequency_hz = frequency * multiplier
    if not _FREQUENCY_MIN_HZ <= frequency_hz <= _FREQUENCY_MAX_HZ:
        raise ValueError("DSG830 frequency response is outside the documented range")
    return frequency_hz


def _parse_power_dbm(response: object) -> float:
    value = _clean_response(response, "power")
    if _DECIMAL_RESPONSE.fullmatch(value) is None:
        raise ValueError("DSG830 power response has an invalid format")
    power_dbm = _parse_finite(value, "power")
    if not _POWER_MIN_DBM <= power_dbm <= _POWER_MAX_DBM:
        raise ValueError("DSG830 power response is outside the documented range")
    return power_dbm


def _parse_binary(response: object, label: str) -> bool:
    value = _clean_response(response, label)
    if value == "0":
        return False
    if value == "1":
        return True
    raise ValueError(f"DSG830 {label} response must be 0 or 1")


def _parse_sweep_state(response: object) -> RfObserved[RfSweepState]:
    value = _clean_response(response, "sweep state").upper().replace(" ", "")
    if value == "OFF":
        return RfObserved.value_of(RfSweepState.DISABLED)
    if value in {
        "FREQ",
        "FREQUENCY",
        "LEV",
        "LEVEL",
        "LEV,FREQ",
        "LEVEL,FREQUENCY",
        "LEV,FREQUENCY",
        "LEVEL,FREQ",
    }:
        return RfObserved.value_of(RfSweepState.ENABLED)
    return RfObserved.missing(RfAvailability.UNKNOWN, RfReasonCode.RESPONSE_INVALID_VALUE)


def _parse_protection_status(response: object) -> RfObserved[RfProtectionStatus]:
    value = _clean_response(response, "power protection condition")
    if _INTEGER_RESPONSE.fullmatch(value) is None:
        raise ValueError("DSG830 power protection condition response must be an integer")
    condition = int(value)
    if not 0 <= condition <= 32_767:
        raise ValueError("DSG830 power protection condition response is outside the documented range")
    if condition & ~0b111:
        return RfObserved.missing(RfAvailability.UNKNOWN, RfReasonCode.RESPONSE_INVALID_VALUE)
    active_codes = tuple(
        code
        for bit, code in (
            (0b100, "alc_heater_detector_30min"),
            (0b001, "alc_unlocked"),
            (0b010, "output_power_protection"),
        )
        if condition & bit
    )
    return RfObserved.value_of(RfProtectionStatus(active_codes=active_codes))


def _parse_finite(value: str, label: str) -> float:
    parsed = float(value)
    if not isfinite(parsed):
        raise ValueError(f"DSG830 {label} response must be finite")
    return parsed


def _as_modulation_state(enabled: bool) -> RfModulationState:
    return RfModulationState.ENABLED if enabled else RfModulationState.DISABLED


def _as_pulse_state(enabled: bool) -> RfPulseState:
    return RfPulseState.ENABLED if enabled else RfPulseState.DISABLED
