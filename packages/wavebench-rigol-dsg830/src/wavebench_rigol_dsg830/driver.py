"""M0 snapshot driver plus staged M1/M2/M3 mappings for the RIGOL DSG830.

A1 hardware evidence authorizes the public ``rf_source.snapshot`` capability.
``get_rf_snapshot()`` remains observational only: it performs the fixed query
set and does not configure frequency or power, switch RF output, or control
modulation, Pulse, Sweep, trigger, or arbitrary SCPI.

``set_rf_output()`` and ``configure_cw()`` are available through the
production descriptor after A2/A3 evidence. ``configure_rf_modulation()``
remains available only to Core M3 tests and fake descriptors until the
separate A4 modulation evidence is independently reviewed.
"""

from __future__ import annotations

from decimal import Decimal
from math import isfinite
import re

from wavebench.instruments.rf_source_extensions import (
    RfAvailability,
    RfCwRequest,
    RfModulationDisableRequest,
    RfModulationKind,
    RfModulationRequest,
    RfModulationStateSnapshot,
    RfModulationSnapshot,
    RfModulationSource,
    RfModulationState,
    RfModulationWaveform,
    RfObserved,
    RfOutputRequest,
    RfPortSnapshot,
    RfProtectionStatus,
    RfPulseConfigureRequest,
    RfPulseMode,
    RfPulsePolarity,
    RfPulseSnapshot,
    RfPulseSource,
    RfPulseState,
    RfReasonCode,
    RfSourceSnapshot,
    RfSweepState,
)


_FREQUENCY_MIN_HZ = 9_000.0
_FREQUENCY_MAX_HZ = 3_000_000_000.0
_POWER_MIN_DBM = -110.0
_POWER_MAX_DBM = 20.0
_INTERNAL_MODULATION_FREQUENCY_MIN_HZ = 10.0
_INTERNAL_MODULATION_FREQUENCY_MAX_HZ = 100_000.0
_AM_DEPTH_MIN_PERCENT = 0.0
_AM_DEPTH_MAX_PERCENT = 100.0
_FM_DEVIATION_MIN_HZ = 0.1
_FM_DEVIATION_MAX_HZ = 1_000_000.0
_PM_DEVIATION_MIN_RAD = 0.0
_PM_DEVIATION_MAX_RAD = 5.0
_PULSE_PERIOD_MIN_S = 40e-9
_PULSE_PERIOD_MAX_S = 170.0
_PULSE_WIDTH_MIN_S = 10e-9
_PULSE_WIDTH_MAX_S = _PULSE_PERIOD_MAX_S - _PULSE_WIDTH_MIN_S
_PULSE_MINIMUM_OFF_TIME_S = 10e-9
_NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?"
_FREQUENCY_RESPONSE = re.compile(
    rf"^(?P<value>{_NUMBER})(?P<unit>Hz|kHz|MHz|GHz)?$",
    re.IGNORECASE,
)
_FREQUENCY_FRACTION_GROUP_RESPONSE = re.compile(
    r"^(?P<leading>[+-]?\d+\.\d+) (?P<trailing>\d+)(?P<unit>Hz|kHz|MHz|GHz)?$",
    re.IGNORECASE,
)
_DECIMAL_RESPONSE = re.compile(rf"^{_NUMBER}$")
_RAD_RESPONSE = re.compile(rf"^(?P<value>{_NUMBER})(?:rad)?$", re.IGNORECASE)
_TIME_RESPONSE = re.compile(rf"^(?P<value>{_NUMBER})\s*(?P<unit>s|ms|us|ns)?$", re.IGNORECASE)
_TIME_FRACTION_GROUP_RESPONSE = re.compile(
    r"^(?P<leading>[+-]?\d+\.\d+) (?P<trailing>\d+)(?P<unit>s|ms|us|ns)?$",
    re.IGNORECASE,
)
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

    def configure_cw(self, request: RfCwRequest) -> None:
        """Send one documented CW setter for the single DSG830 RF port.

        Core owns the OFF-only preflight and independent snapshot readback.
        This method intentionally sends exactly one write and performs neither
        retry nor RF-output recovery.
        """

        if not isinstance(request, RfCwRequest):
            raise ValueError("DSG830 CW configuration requires RfCwRequest")
        if request.port_id != "rf_out":
            raise ValueError("DSG830 CW configuration requires port_id='rf_out'")
        if request.frequency_hz is not None:
            if not _FREQUENCY_MIN_HZ <= request.frequency_hz <= _FREQUENCY_MAX_HZ:
                raise ValueError("DSG830 CW frequency is outside the documented range")
            self.transport.write(f":FREQ {_format_scpi_real(request.frequency_hz)}Hz")
            return
        assert request.power_dbm is not None
        if not _POWER_MIN_DBM <= request.power_dbm <= _POWER_MAX_DBM:
            raise ValueError("DSG830 CW power is outside the documented range")
        self.transport.write(f":LEV {_format_scpi_real(request.power_dbm)}dBm")

    def get_rf_modulation_snapshot(
        self,
        port_id: str,
        kind: RfModulationKind,
    ) -> RfModulationSnapshot:
        """Read one complete, internal-sine M3 modulation profile without writes."""

        _require_modulation_target(port_id, kind)
        prefix = _modulation_prefix(kind)
        state = self.get_rf_modulation_state(port_id)
        responses: dict[str, str] = {}
        if kind in {RfModulationKind.FM, RfModulationKind.PM}:
            responses[":FMPM:TYPE?"] = self.transport.query(":FMPM:TYPE?")
        for suffix in ("SOUR?", "WAVE?", _modulation_value_query(kind), "FREQ?"):
            command = f":{prefix}:{suffix}"
            responses[command] = self.transport.query(command)

        selected_fm_pm_kind = (
            _parse_fm_pm_type(responses[":FMPM:TYPE?"])
            if kind in {RfModulationKind.FM, RfModulationKind.PM}
            else None
        )
        source = _parse_modulation_source(responses[f":{prefix}:SOUR?"])
        waveform = _parse_modulation_waveform(responses[f":{prefix}:WAVE?"])
        common = {
            "port_id": port_id,
            "kind": kind,
            "source": source,
            "waveform": waveform,
            "internal_frequency_hz": _parse_modulation_frequency_hz(
                responses[f":{prefix}:FREQ?"],
                f"{kind.value} modulation frequency",
            ),
            "selected_fm_pm_kind": selected_fm_pm_kind,
            "enabled_modes": state.enabled_modes,
            "global_enabled": state.global_enabled,
            "fault_codes": state.fault_codes,
        }
        if kind is RfModulationKind.AM:
            return RfModulationSnapshot(
                **common,
                depth_percent=_parse_am_depth_percent(responses[":AM:DEPT?"]),
            )
        if kind is RfModulationKind.FM:
            return RfModulationSnapshot(
                **common,
                frequency_deviation_hz=_parse_fm_deviation_hz(responses[":FM:DEV?"]),
            )
        return RfModulationSnapshot(
            **common,
            phase_deviation_rad=_parse_pm_deviation_rad(responses[":PM:DEV?"]),
        )

    def get_rf_modulation_state(self, port_id: str) -> RfModulationStateSnapshot:
        """Read M3 mode/global/fault state without source-dependent profile queries."""

        _require_modulation_port(port_id)
        state_commands = (
            ":MOD:STAT?",
            ":AM:STAT?",
            ":FM:STAT?",
            ":PM:STAT?",
            ":STAT:QUES:MOD:COND?",
        )
        responses = {command: self.transport.query(command) for command in state_commands}
        enabled_modes = tuple(
            mode
            for mode, command in (
                (RfModulationKind.AM, ":AM:STAT?"),
                (RfModulationKind.FM, ":FM:STAT?"),
                (RfModulationKind.PM, ":PM:STAT?"),
            )
            if _parse_binary(responses[command], f"{mode.value} modulation state")
        )
        return RfModulationStateSnapshot(
            port_id=port_id,
            enabled_modes=enabled_modes,
            global_enabled=_parse_binary(
                responses[":MOD:STAT?"],
                "global modulation state",
            ),
            fault_codes=_parse_modulation_fault_codes(responses[":STAT:QUES:MOD:COND?"]),
        )

    def configure_rf_modulation(self, request: RfModulationRequest) -> None:
        """Send one bounded internal-sine M3 configuration sequence without readback.

        Core owns RF-OFF preflight and independent postcondition readback.  This
        method sends the documented, mode-specific sequence exactly once and
        never enables RF output, retries writes, or performs recovery.
        """

        if not isinstance(request, RfModulationRequest):
            raise ValueError("DSG830 modulation configuration requires RfModulationRequest")
        _require_modulation_target(request.port_id, request.kind)
        _validate_modulation_request_range(request)
        prefix = _modulation_prefix(request.kind)
        if request.kind in {RfModulationKind.FM, RfModulationKind.PM}:
            self.transport.write(f":FMPM:TYPE {request.kind.value.upper()}")
        self.transport.write(f":{prefix}:SOUR INT")
        self.transport.write(f":{prefix}:WAVE SINE")
        self.transport.write(_modulation_value_write(request))
        self.transport.write(
            f":{prefix}:FREQ {_format_scpi_real(request.internal_frequency_hz)}Hz"
        )
        self.transport.write(f":{prefix}:STAT ON")
        self.transport.write(":MOD:STAT ON")

    def disable_rf_modulation(self, request: RfModulationDisableRequest) -> None:
        """Send the fixed M3 mode/global disable sequence without readback.

        Core owns the RF-OFF preflight and independent state-only readback.
        This method only disables the explicitly requested mode and then the
        global modulation switch; it never changes RF output or retries writes.
        """

        if not isinstance(request, RfModulationDisableRequest):
            raise ValueError("DSG830 modulation disable requires RfModulationDisableRequest")
        _require_modulation_target(request.port_id, request.kind)
        prefix = _modulation_prefix(request.kind)
        self.transport.write(f":{prefix}:STAT OFF")
        self.transport.write(":MOD:STAT OFF")

    def get_rf_pulse_snapshot(self, port_id: str) -> RfPulseSnapshot:
        """Read the documented pulse profile without touching Pulse I/O or triggers."""

        _require_pulse_port(port_id)
        commands = (
            ":PULM:SOUR?",
            ":PULM:MODE?",
            ":PULM:PER?",
            ":PULM:WIDT?",
            ":PULM:POL?",
            ":PULM:STAT?",
        )
        responses = {command: self.transport.query(command) for command in commands}
        return RfPulseSnapshot(
            port_id=port_id,
            source=_parse_pulse_source(responses[":PULM:SOUR?"]),
            mode=_parse_pulse_mode(responses[":PULM:MODE?"]),
            period_s=_parse_pulse_seconds(
                responses[":PULM:PER?"],
                "pulse period",
                minimum_s=_PULSE_PERIOD_MIN_S,
                maximum_s=_PULSE_PERIOD_MAX_S,
            ),
            width_s=_parse_pulse_seconds(
                responses[":PULM:WIDT?"],
                "pulse width",
                minimum_s=_PULSE_WIDTH_MIN_S,
                maximum_s=_PULSE_WIDTH_MAX_S,
            ),
            polarity=_parse_pulse_polarity(responses[":PULM:POL?"]),
            state=_as_pulse_state(_parse_binary(responses[":PULM:STAT?"], "pulse state")),
        )

    def configure_rf_pulse(self, request: RfPulseConfigureRequest) -> None:
        """Configure one disabled internal single-pulse profile without triggering.

        Core owns RF-OFF preflight and independent profile readback. This
        mapping never touches `:PULM:OUT`, trigger commands, or RF output, and
        ends by explicitly keeping pulse modulation disabled.
        """

        if not isinstance(request, RfPulseConfigureRequest):
            raise ValueError("DSG830 pulse configuration requires RfPulseConfigureRequest")
        _require_pulse_port(request.port_id)
        _validate_pulse_request_range(request)
        polarity = {
            RfPulsePolarity.NORMAL: "NORM",
            RfPulsePolarity.INVERTED: "INV",
        }[request.polarity]
        self.transport.write(":PULM:SOUR INT")
        self.transport.write(":PULM:MODE SING")
        self.transport.write(f":PULM:PER {_format_scpi_real(request.period_s)}s")
        self.transport.write(f":PULM:WIDT {_format_scpi_real(request.width_s)}s")
        self.transport.write(f":PULM:POL {polarity}")
        self.transport.write(":PULM:STAT OFF")

    def set_rf_output(self, request: RfOutputRequest) -> None:
        """Map one offline M2 output request to one documented setter.

        Core owns the safety preflight, independent readback, and bounded
        OFF recovery. This driver sends one write only and never queries,
        retries, or recovers on its own.
        """

        if not isinstance(request, RfOutputRequest):
            raise ValueError("DSG830 RF output control requires RfOutputRequest")
        if request.port_id != "rf_out":
            raise ValueError("DSG830 RF output control requires port_id='rf_out'")
        self.transport.write(":OUTP ON" if request.enabled else ":OUTP OFF")

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
    return _parse_frequency_response_hz(
        response,
        "frequency",
        minimum_hz=_FREQUENCY_MIN_HZ,
        maximum_hz=_FREQUENCY_MAX_HZ,
    )


def _parse_frequency_response_hz(
    response: object,
    label: str,
    *,
    minimum_hz: float,
    maximum_hz: float,
) -> float:
    value = _clean_response(response, label)
    match = _FREQUENCY_RESPONSE.fullmatch(value)
    if match is None:
        grouped = _FREQUENCY_FRACTION_GROUP_RESPONSE.fullmatch(value)
        if grouped is not None:
            normalized = (
                grouped.group("leading")
                + grouped.group("trailing")
                + (grouped.group("unit") or "")
            )
            match = _FREQUENCY_RESPONSE.fullmatch(normalized)
    if match is None:
        raise ValueError(f"DSG830 {label} response has an invalid format")
    frequency = _parse_finite(match.group("value"), label)
    multiplier = {
        None: 1.0,
        "HZ": 1.0,
        "KHZ": 1_000.0,
        "MHZ": 1_000_000.0,
        "GHZ": 1_000_000_000.0,
    }[match.group("unit").upper() if match.group("unit") is not None else None]
    frequency_hz = frequency * multiplier
    if not minimum_hz <= frequency_hz <= maximum_hz:
        raise ValueError(f"DSG830 {label} response is outside the documented range")
    return frequency_hz


def _parse_power_dbm(response: object) -> float:
    value = _clean_response(response, "power")
    if _DECIMAL_RESPONSE.fullmatch(value) is None:
        raise ValueError("DSG830 power response has an invalid format")
    power_dbm = _parse_finite(value, "power")
    if not _POWER_MIN_DBM <= power_dbm <= _POWER_MAX_DBM:
        raise ValueError("DSG830 power response is outside the documented range")
    return power_dbm


def _parse_modulation_frequency_hz(response: object, label: str) -> float:
    return _parse_frequency_response_hz(
        response,
        label,
        minimum_hz=_INTERNAL_MODULATION_FREQUENCY_MIN_HZ,
        maximum_hz=_INTERNAL_MODULATION_FREQUENCY_MAX_HZ,
    )


def _parse_am_depth_percent(response: object) -> float:
    return _parse_decimal_range(
        response,
        "AM modulation depth",
        minimum=_AM_DEPTH_MIN_PERCENT,
        maximum=_AM_DEPTH_MAX_PERCENT,
    )


def _parse_fm_deviation_hz(response: object) -> float:
    return _parse_frequency_response_hz(
        response,
        "FM deviation",
        minimum_hz=_FM_DEVIATION_MIN_HZ,
        maximum_hz=_FM_DEVIATION_MAX_HZ,
    )


def _parse_pm_deviation_rad(response: object) -> float:
    value = _clean_response(response, "PM deviation")
    match = _RAD_RESPONSE.fullmatch(value)
    if match is None:
        raise ValueError("DSG830 PM deviation response has an invalid format")
    deviation = _parse_finite(match.group("value"), "PM deviation")
    if not _PM_DEVIATION_MIN_RAD <= deviation <= _PM_DEVIATION_MAX_RAD:
        raise ValueError("DSG830 PM deviation response is outside the documented range")
    return deviation


def _parse_pulse_seconds(
    response: object,
    label: str,
    *,
    minimum_s: float,
    maximum_s: float,
) -> float:
    value = _clean_response(response, label)
    match = _TIME_RESPONSE.fullmatch(value)
    if match is None:
        grouped = _TIME_FRACTION_GROUP_RESPONSE.fullmatch(value)
        if grouped is not None:
            normalized = (
                grouped.group("leading")
                + grouped.group("trailing")
                + (grouped.group("unit") or "")
            )
            match = _TIME_RESPONSE.fullmatch(normalized)
    if match is None:
        raise ValueError(f"DSG830 {label} response has an invalid format")
    seconds = float(
        Decimal(match.group("value"))
        * {
            None: Decimal("1"),
            "S": Decimal("1"),
            "MS": Decimal("1e-3"),
            "US": Decimal("1e-6"),
            "NS": Decimal("1e-9"),
        }[match.group("unit").upper() if match.group("unit") is not None else None]
    )
    if not isfinite(seconds):
        raise ValueError(f"DSG830 {label} response must be finite")
    if not minimum_s <= seconds <= maximum_s:
        raise ValueError(f"DSG830 {label} response is outside the documented range")
    return seconds


def _parse_decimal_range(
    response: object,
    label: str,
    *,
    minimum: float,
    maximum: float,
) -> float:
    value = _clean_response(response, label)
    if _DECIMAL_RESPONSE.fullmatch(value) is None:
        raise ValueError(f"DSG830 {label} response has an invalid format")
    parsed = _parse_finite(value, label)
    if not minimum <= parsed <= maximum:
        raise ValueError(f"DSG830 {label} response is outside the documented range")
    return parsed


def _parse_modulation_source(response: object) -> RfModulationSource:
    value = _clean_response(response, "modulation source").upper()
    if value in {"INT", "INTERNAL"}:
        return RfModulationSource.INTERNAL
    if value in {"EXT", "EXTERNAL"}:
        return RfModulationSource.EXTERNAL
    raise ValueError("DSG830 modulation source response must be INT or EXT")


def _parse_pulse_source(response: object) -> RfPulseSource:
    value = _clean_response(response, "pulse source").upper()
    if value in {"INT", "INTERNAL"}:
        return RfPulseSource.INTERNAL
    if value in {"EXT", "EXTERNAL"}:
        return RfPulseSource.EXTERNAL
    raise ValueError("DSG830 pulse source response must be INT or EXT")


def _parse_pulse_mode(response: object) -> RfPulseMode:
    value = _clean_response(response, "pulse mode").upper()
    if value in {"SING", "SINGLE"}:
        return RfPulseMode.SINGLE
    if value == "TRAIN":
        return RfPulseMode.TRAIN
    raise ValueError("DSG830 pulse mode response must be SINGLE or TRAIN")


def _parse_pulse_polarity(response: object) -> RfPulsePolarity:
    value = _clean_response(response, "pulse polarity").upper()
    if value in {"NORM", "NORMAL"}:
        return RfPulsePolarity.NORMAL
    if value in {"INV", "INVERSE"}:
        return RfPulsePolarity.INVERTED
    raise ValueError("DSG830 pulse polarity response must be NORMAL or INVERSE")


def _parse_modulation_waveform(response: object) -> RfModulationWaveform:
    value = _clean_response(response, "modulation waveform").upper()
    if value == "SINE":
        return RfModulationWaveform.SINE
    if value in {"SQUA", "SQUARE"}:
        return RfModulationWaveform.SQUARE
    raise ValueError("DSG830 modulation waveform response must be SINE or SQUA")


def _parse_fm_pm_type(response: object) -> RfModulationKind:
    value = _clean_response(response, "FM/PM type").upper()
    if value == "FM":
        return RfModulationKind.FM
    if value == "PM":
        return RfModulationKind.PM
    raise ValueError("DSG830 FM/PM type response must be FM or PM")


def _parse_modulation_fault_codes(response: object) -> tuple[str, ...]:
    value = _clean_response(response, "modulation condition")
    if _INTEGER_RESPONSE.fullmatch(value) is None:
        raise ValueError("DSG830 modulation condition response must be an integer")
    condition = int(value)
    if not 0 <= condition <= 1:
        raise ValueError("DSG830 modulation condition response is outside the documented range")
    return ("am_overmodulation",) if condition else ()


def _require_modulation_target(port_id: object, kind: object) -> None:
    _require_modulation_port(port_id)
    if not isinstance(kind, RfModulationKind):
        raise ValueError("DSG830 modulation configuration requires a supported modulation kind")


def _require_modulation_port(port_id: object) -> None:
    if port_id != "rf_out":
        raise ValueError("DSG830 modulation configuration requires port_id='rf_out'")


def _require_pulse_port(port_id: object) -> None:
    if port_id != "rf_out":
        raise ValueError("DSG830 pulse configuration requires port_id='rf_out'")


def _modulation_prefix(kind: RfModulationKind) -> str:
    return {
        RfModulationKind.AM: "AM",
        RfModulationKind.FM: "FM",
        RfModulationKind.PM: "PM",
    }[kind]


def _modulation_value_query(kind: RfModulationKind) -> str:
    return {
        RfModulationKind.AM: "DEPT?",
        RfModulationKind.FM: "DEV?",
        RfModulationKind.PM: "DEV?",
    }[kind]


def _modulation_value_write(request: RfModulationRequest) -> str:
    prefix = _modulation_prefix(request.kind)
    if request.kind is RfModulationKind.AM:
        return f":{prefix}:DEPT {_format_scpi_real(request.value)}"
    if request.kind is RfModulationKind.FM:
        return f":{prefix}:DEV {_format_scpi_real(request.value)}Hz"
    return f":{prefix}:DEV {_format_scpi_real(request.value)}rad"


def _validate_modulation_request_range(request: RfModulationRequest) -> None:
    if not (
        _INTERNAL_MODULATION_FREQUENCY_MIN_HZ
        <= request.internal_frequency_hz
        <= _INTERNAL_MODULATION_FREQUENCY_MAX_HZ
    ):
        raise ValueError("DSG830 modulation frequency is outside the documented range")
    minimum, maximum = {
        RfModulationKind.AM: (_AM_DEPTH_MIN_PERCENT, _AM_DEPTH_MAX_PERCENT),
        RfModulationKind.FM: (_FM_DEVIATION_MIN_HZ, _FM_DEVIATION_MAX_HZ),
        RfModulationKind.PM: (_PM_DEVIATION_MIN_RAD, _PM_DEVIATION_MAX_RAD),
    }[request.kind]
    if not minimum <= request.value <= maximum:
        raise ValueError("DSG830 modulation value is outside the documented range")


def _validate_pulse_request_range(request: RfPulseConfigureRequest) -> None:
    if not _PULSE_PERIOD_MIN_S <= request.period_s <= _PULSE_PERIOD_MAX_S:
        raise ValueError("DSG830 pulse period is outside the documented range")
    if not _PULSE_WIDTH_MIN_S <= request.width_s <= _PULSE_WIDTH_MAX_S:
        raise ValueError("DSG830 pulse width is outside the documented range")
    if request.width_s > request.period_s - _PULSE_MINIMUM_OFF_TIME_S:
        raise ValueError("DSG830 pulse width violates the documented minimum off time")


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


def _format_scpi_real(value: float) -> str:
    """Format a finite SCPI real without locale or non-finite spellings."""

    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError("DSG830 SCPI real value must be finite")
    return format(value, ".12g")


def _as_modulation_state(enabled: bool) -> RfModulationState:
    return RfModulationState.ENABLED if enabled else RfModulationState.DISABLED


def _as_pulse_state(enabled: bool) -> RfPulseState:
    return RfPulseState.ENABLED if enabled else RfPulseState.DISABLED
