# MSO8104 Programming-Guide Coverage Matrix

[中文](MSO8104_COVERAGE_MATRIX.md)

This page maps MSO8000 programming-guide domains to the WaveBench capabilities currently exposed
by the external `wavebench-rigol-mso8000` plugin. The [package metadata](../pyproject.toml) is
authoritative for version, dependencies, and entry point; the
[production descriptor](../src/wavebench_rigol_mso8000/descriptor.py) for model, capabilities,
binary profiles, and request limits; and the [driver](../src/wavebench_rigol_mso8000/driver.py) for
exact SCPI, parsing, and restoration behavior.

The [controlled hardware acceptance record](MSO8104_HARDWARE_ACCEPTANCE_EN.md) retains device,
firmware, transport, test conditions, exact results, and unaccepted scope. The
[coverage milestones](MSO8104_COVERAGE_MILESTONES_EN.md) retain development order and historical
decisions. Those records support traceability and do not independently add a current capability.

## Scope

The audited source is RIGOL MSO8000 Programming Guide `PGA26006-1110`. It covers MSO8064,
MSO8104, and MSO8204 and frequently uses MSO8204 examples; the production descriptor registers
only MSO8104. Manual commands and parameters for other models therefore do not automatically apply
to this plugin.

This matrix answers what the production descriptor currently exposes and the boundaries of that
public behavior. A manual command, Python method, completed milestone, or one successful hardware
run cannot replace a descriptor declaration.

## Functional coverage

| Domain | Manual surface | Current public capability | Current boundary |
|---|---|---|---|
| Identity | `*IDN?` | `scope.idn` | Matches only the MSO8104 identity pattern registered by the descriptor; no model or firmware extrapolation. |
| Error queue | `:SYSTem:ERRor[:NEXT]?` | `scope.error_drain_v1` | Consuming reads are `NO_REPLAY`; records are parsed strictly and terminate on zero error. Legacy `scope.errors` is not declared. |
| Input safety | coupling, termination, impedance queries | `scope.channel_coupling`, `scope.channel_input_state_v2` | Legacy returns the Core high-impedance token; V2 separates coupling, termination, and impedance. Unknown combinations fail closed. |
| Autoscale | system autoscale enable and autoscale command | `scope.autoscale` | Mutates vertical, timebase, and trigger state without promising restoration. Failure latches the relevant write path. |
| Complete legacy snapshot | channel, timebase, probe, waveform, trigger, health | Not declared | The device cannot reliably supply every required field in the public model. |
| Snapshot V2 | identity and licensed-option status | `scope.snapshot_v2` | Reads only fields declared by the descriptor profile; remaining health, channel, timebase, probe, waveform, and trigger fields are unavailable. |
| Existing acquisition configuration | type, averages, depth, rate, run/stop/single | Used as fetch/capture preconditions | No arbitrary acquisition-configuration setter is public. |
| Legacy acquisition status | averages and trigger status | Not declared | The legacy contract requires average-completion and segmented state that the device cannot reliably prove. |
| Acquisition status V2 | type, sample rate, memory depth, AVER count | `scope.acquisition_status_v2` | Returns only readable or conditionally applicable profile fields. STOP, OPC, and configured count never imply completion. |
| Acquisition run state | `:TRIGger:STATus?` | `scope.acquisition_run_state` | Maps stopped/waiting/acquiring/unknown; observing state does not prove SINGLE completion. |
| Acquisition control | `:RUN`, `:STOP`, `:SINGle`, status queries | `scope.acquisition_control` | Exposes only `start(normal)`, `stop`, and completion-style SINGLE. Writes are not blindly retried, and `*OPC?` alone is not completion proof. |
| Average capture | global acquisition type and average count | Not declared | The current plugin cannot reliably enter average mode and prove completion. |
| Current-screen waveform | NORM/BYTE/preamble/data | `scope.fetch_waveform` | Supports bounded `DEF` reads; payload, axes, and converted samples must be complete and finite. |
| Deep waveform | MAX/RAW and chunks | `scope.fetch_waveform` | Reads MAX/DMAX only after observed stopped state and within descriptor limits for points, response size, operation size, and query count. |
| Single/multi-channel capture | SINGLE, trigger status, per-source waveform | `scope.capture_waveform`, `scope.capture_waveforms` | Supports the declared MAIN/`DEF + BYTE` baseline. Multi-channel capture triggers once, then reads each channel. Restore fields and budgets come from the descriptor. |
| Math metadata | MATH display and waveform preamble | `scope.math_metadata` | Reads metadata, not math data, and makes no claim about calculation content or accuracy. |
| Cursor readout | mode, type, source, unit, value, delta | `scope.cursor_readout`, `scope.cursor_readout_v2` | Legacy retains a narrow manual same-source subset. V2 accepts only profile-supported addressing, sources, and unit combinations and never moves cursors. |
| Screenshot | image type and binary data | `scope.screenshot_profile`, `scope.screenshot_v2` | Accepts only the descriptor's `png/device/device` request. Returned data is strictly validated and converted in memory; no device file or display setting is changed. |
| Legacy digital status | module and LA status | Not declared | The device cannot provide every required legacy-model field. |
| Digital status V2 | module, display, label, threshold, timing calibration, size | `scope.digital_status_v2` | Checks the LA module first and sends no LA query when absent. Returns static state only and does not infer activity or waveform encoding. |
| Digital waveform | D0-D15 source and data | Not declared | BYTE/WORD logic codes and WORD byte order lack a sufficient public contract. |
| Measurement statistics | `:MEASure:STATistic:ITEM?` | `scope.measurement_statistics_v2` | Requires explicit item/source, does not support buffer, and never changes configuration, clears statistics, or writes display state. |
| FFT status | MATH operator and FFT queries | `scope.fft_status_v2` | Requires FFT operator first and returns only declared profile fields. Average completion, RBW, and FFT sample rate are not inferred. |
| Reference metadata | source, vertical scale/offset, label | Not declared | Current manual/device interfaces cannot fully express axes, points, and Y resolution. |
| History timestamps | record state, frame, timestamp | Not declared | Frame numbers cannot substitute for per-frame relative or calendar timestamps. |
| DVM, counter, AWG | corresponding vendor families | Not declared | Current Scope contracts or shared-resource models are insufficient; raw SCPI does not bypass them. |
| Protocol, mask, search, record | option-heavy application families | Not declared | Require independent option, restoration, and result models. |
| Reset, network, option install, files, calibration | system and storage families | Not declared | High-side-effect maintenance operations are denied in ordinary experiment workflows. |

## Binary-profile boundaries

Exact response/operation budgets, query limits, trailing bytes, restoration order, and screenshot
variants are defined by `ScopeDescriptorExtensions` in the
[production descriptor](../src/wavebench_rigol_mso8000/descriptor.py). This document does not
maintain a second numeric table.

- `fetch`, `capture_single`, and `capture_multiple` use independent waveform operation profiles.
- `capture_multiple` triggers one acquisition and then reads multiple channels; it never retriggers
  per channel.
- Screenshot uses `DEFINITE_BLOCK` framing and changes no image type, menu, color, or device file.
- `tcpip`, `usb`, and `gpib` resource schemes describe routing contracts, not hardware acceptance
  for every connection type.

## Waveform conversion contract

BYTE waveforms use the manual's ten-field preamble:

```text
format,type,points,count,xincrement,xorigin,xreference,yincrement,yorigin,yreference
```

The driver creates public `WaveformData` with:

```text
voltage = (raw - y_origin - y_reference) * y_increment
x_start = x_origin - x_reference * x_increment
x_stop  = x_start + (points - 1) * x_increment
```

Payload length must exactly match the point count, and axes and converted samples must be finite.
Core transport owns IEEE/TMC block framing; the plugin does not parse `#N<length>` twice.

## Related sources

- [Production descriptor](../src/wavebench_rigol_mso8000/descriptor.py)
- [Driver implementation](../src/wavebench_rigol_mso8000/driver.py)
- [Controlled hardware acceptance and unaccepted scope](MSO8104_HARDWARE_ACCEPTANCE_EN.md)
- [Development milestones and historical decisions](MSO8104_COVERAGE_MILESTONES_EN.md)
- [Related RFCs](rfcs/README.md) (Chinese)
