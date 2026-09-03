# SDG2000X current capability Reference

[中文](SDG2000X_COVERAGE_MATRIX.md)

This page defines the capabilities, applicability, and failure boundaries currently declared by the `siglent.sdg2000x` production descriptor. The package metadata version is `0.8.2`; it identifies the source contract in this repository without depending on a separate PyPI, Git tag, or GitHub Release state.

## Synopsis

| Item | Current value |
| --- | --- |
| Distribution | `wavebench-siglent-sdg2000x` |
| Driver ID | `siglent.sdg2000x` |
| Registered models | `SDG2042X`, `SDG2082X`, `SDG2122X` |
| WaveBench | `>=0.8.24,<0.9` |
| Python | `>=3.11` |
| Backend | `pyvisa` |
| Configuration fields | `source.resource`, `source.driver`, `safety_limits.max_source_vpp` |

The Source V2 topology contains CH1 and CH2. Its snapshot query contract is pure read, permits at most `44` queries, and has a `5000 ms` timeout.

## Current capabilities

| Capability | Exact scope and behavior |
| --- | --- |
| `source.idn` | Reads and matches SDG2000X-family identity. |
| `source.status` | Reads basic waveform, frequency, amplitude, offset, and output state for one channel. |
| `source.set_frequency` | Sets fixed-wave frequency with model and current-waveform limits. Automatic Sweep-to-FIX selection is allowed only while output is OFF. |
| `source.set_function` | Sets bounded periodic waves. Sine, Square, Ramp, and Pulse follow the normal contract; Noise/DC require output OFF. |
| `source.set_amplitude_vpp` | Sets `2 mVpp–10 Vpp`; the amplitude-plus-offset envelope must remain within `±10 V`. |
| `source.set_square_duty_cycle` | Applies only to a FIX-mode Square wave and fails closed on frequency-dependent clamping or readback mismatch. |
| `source.output` | Reads, enables, or disables channel output. Enable requires FIX, readable Vpp/Offset, known composite modes OFF, and the `max_source_vpp` check. |
| `source.arbitrary_probe` | Probes arbitrary-wave state without upload, deletion, or replacement. |
| `source.snapshot_v2` | Performs a pure-read anchor/facet/anchor snapshot on CH1/CH2 with identity, Basic, Output, and conditionally activated Harmonics facets. |
| `source.basic_configure_v2` | Performs one-field Basic MAIN configuration for Sine, Square, Ramp, or Pulse on CH1/CH2. Fixed frequency, Vpp, and Square duty are writable; `offset_v` is not currently writable. |
| `source.output_v2` | Independently reads, enables, or disables CH1/CH2. Each MAIN request writes the target field once, followed by an independent Core snapshot. |
| `source.harmonics_disable_v2` | Applies only to `SDG2122X` / `2.01.01.39R7T2`, Sine, and target output OFF. It reads or disables Harmonic and never configures or enables it. |

## Source V2 model and firmware restrictions

The Basic and Output feature applicability adds no model or firmware restriction beyond the registered-model runtime contract. Current controlled hardware evidence primarily uses an `SDG2122X` running firmware `2.01.01.39R7T2`. That evidence does not replace the descriptor or automatically establish other models, firmware revisions, or physical operating points.

The Harmonic feature has an explicit restriction:

- the model must be `SDG2122X`;
- firmware must be `2.01.01.39R7T2`;
- the target channel must be Sine with output OFF;
- an already-disabled state sends no MAIN write; an enabled state sends only one `HARMSTATE,OFF`;
- Core then independently reads Harmonic and output state.

The Harmonic profile can read orders 2–16 with absolute-Vpp or relative-dB amplitudes, but its only public write direction is `DISABLE`.

## Side effects and failure behavior

- Descriptor import performs no instrument I/O. The factory opens only the configured transport.
- A `read_only` session permits reads only; Core rejects mismatched access before a write.
- V1 and V2 writes must satisfy the target-channel, waveform, output, safety-limit, and readback contracts.
- V2 Basic and Output each write the target configuration once. A post-write failure attempts output OFF and latches later configuration writes for the session.
- Source V2 does not represent Noise/DC `STDEV` or nominal values as Vpp; calls without a lossless V2 state retain the safer V1 path.
- Historical harnesses and raw SCPI cannot bypass the current descriptor.

## Currently unsupported

The production descriptor declares no error queue, modulation, Sweep, Burst, Pulse-parameter, arbitrary upload/delete, Combine, phase/Invert, tracking/coupling/copy, Sync, Counter, external-reference, Cascade, or raw-SCPI capability.

Some command domains have controlled hardware evidence, but they remain unavailable when Core lacks a lossless model or the descriptor declares no capability. Evidence is for traceability and is not a second current capability table.

## Sources

- [Package metadata](../pyproject.toml)
- [Production descriptor](../src/wavebench_siglent_sdg2000x/descriptor.py)
- [Driver implementation](../src/wavebench_siglent_sdg2000x/driver.py)
- [Driver tests](../tests/test_driver.py)
- [Wheel and descriptor tests](../tests/test_wheel.py)
- [Development records and hardware evidence](README_EN.md)
