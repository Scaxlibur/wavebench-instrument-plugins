# DSG830 current capability Reference

[中文](reference.md)

This page defines the exact current boundary declared by the `rigol.dsg830` production descriptor. The package metadata version is `0.2.0`; it identifies the source contract in this repository and is not a separate PyPI, Git tag, or GitHub Release claim.

## Synopsis

| Item | Current value |
| --- | --- |
| Distribution | `wavebench-rigol-dsg830` |
| Driver ID | `rigol.dsg830` |
| Model | `DSG830` |
| WaveBench | `>=0.8.25,<0.9` |
| Python | `>=3.11` |
| Backend | `pyvisa` |
| Resource schemes | `tcpip`, `usb` |
| Configuration fields | `rf_source.resource`, `rf_source.driver` |

The descriptor range for `rf_out` is `9 kHz–3 GHz` and `-110–20 dBm`, with power referenced to 50 ohms. That reference defines the power contract and does not prove the actual termination.

## Declared capabilities

| Capability | Exact scope and behavior |
| --- | --- |
| `rf_source.idn` | Reads and strictly matches DSG830 identity. |
| `rf_source.snapshot` | Reads identity, frequency, power, RF output, modulation, Pulse, Sweep, and protection state without writes. |
| `rf_source.cw_configure` | Reads or configures `rf_out` frequency and dBm power; configuration requires RF OFF and the complete OFF-only preflight. |
| `rf_source.output` | Reads, enables, or disables `rf_out`; ordinary RF ON requires modulation disabled plus Core port limits, a fresh snapshot, and independent readback. |
| `rf_source.modulation_configure` | Configures internal-sine AM, FM, or PM only while RF is OFF and leaves RF OFF. |
| `rf_source.modulation_disable` | Disables one known active mode and global modulation while RF is OFF; it is not a reset. |
| `rf_source.modulated_output_enable` | Enables RF only for an already configured and exactly read-back fixed low-power AM/FM/PM profile; success performs one RF ON. |
| `rf_source.pulse_configure` | Configures the internal/single Pulse profile on `rf_out` and leaves Pulse OFF. |
| `rf_source.pulse_output` | Reads, enables, or disables the fixed output profile on `pulse_in_out`; it neither detects nor configures the receiver. |
| `rf_source.sweep_configure` | Configures the fixed frequency-only Step Sweep profile and leaves Sweep disabled; it does not execute or trigger Sweep. |

## Profiles

### CW and RF output

- Frequency: `9 kHz–3 GHz`.
- Power: `-110–20 dBm`, referenced to 50 ohms.
- The descriptor marks `alc_heater_detector_30min`, `alc_unlocked`, and `output_power_protection` as write-blocking protection conditions.
- Output enable must satisfy the Core safety contract. The driver does not infer the actual load or termination from a connector name.

### Internal-sine modulation

| Mode | RF-OFF configuration range | Internal frequency | Fixed modulated-output profile |
| --- | --- | --- | --- |
| AM | `0–100 %` | `10 Hz–100 kHz` | `50 %` at `1 kHz` |
| FM | `0.1 Hz–1 MHz` deviation | `10 Hz–100 kHz` | `20 kHz` deviation at `1 kHz` |
| PM | `1.25 rad` | `10 Hz–100 kHz` | `1.25 rad` at `1 kHz` |

`rf_source.modulated_output_enable` limits output power to `-50 dBm`. Ordinary `rf_source.output` cannot enable RF while modulation is active.

### Pulse

- `rf_source.pulse_configure` supports internal/single only, with normal or inverted polarity.
- Period: `40 ns–170 s`.
- Width: `10 ns–169.99999999 s`, with a `10 ns` minimum OFF time.
- `rf_source.pulse_output` applies only to interface `pulse_in_out` in the output direction and fixes `0 V`/`3.3 V`, about `600 ohms`, internal/single/normal, period `1 ms`, and width `100 µs`.
- `pulse_in_out` and the 50-ohm `rf_out` are separate interfaces. Pulse Output declares no receiver, cable, or load state.

### Step Sweep

- Type: `STEP`.
- Direction: `FWD`.
- Shape: `RAMP`.
- Spacing: `LIN`.
- Frequency: `9 kHz–3 GHz`.
- Points: `2–65535`.
- Dwell: `20 ms–100 s`.

The capability configures and reads the profile, then leaves Sweep disabled.

## Side effects and failure behavior

- A `read_only` session permits identity and status reads only.
- Writes require explicit `read_write` access and the state, safety configuration, and readback contract for the capability.
- Out-of-profile requests, unknown preconditions, active protection, or mismatched post-write readback fail closed and cannot be bypassed through raw SCPI.
- An uncertain output-enable result is not retried; recovery is limited to a guarded OFF action.
- Descriptor import performs no instrument I/O. The factory opens only the configured transport.

## Currently unsupported

The production descriptor does not declare an error queue, `rf_source.trigger_snapshot`, Pulse input, `TRIGGER IN`, trigger, Sweep execution/fire, sync/reference, Level Sweep, list, or arbitrary SCPI passthrough.

## Sources

- [Package metadata](../pyproject.toml)
- [Production descriptor](../src/wavebench_rigol_dsg830/descriptor.py)
- [Descriptor tests](../tests/test_descriptor.py)
- [Historical milestones and hardware evidence](DSG830_COVERAGE_MILESTONES_EN.md)
- [Documentation index](README_EN.md)
