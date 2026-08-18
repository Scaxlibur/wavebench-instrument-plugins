# MSO8104 Programming-Guide Coverage Matrix

[中文](MSO8104_COVERAGE_MATRIX.md)

See [MSO8104 Coverage Milestones](MSO8104_COVERAGE_MILESTONES_EN.md) for sequencing and safety rules. A command listed here is neither an implementation claim nor hardware evidence.

The audited source is RIGOL MSO8000 Programming Guide `PGA26006-1110`, which covers MSO8064, MSO8104, and MSO8204 and frequently uses MSO8204 examples. This plugin initially names only MSO8104.

| Domain | Manual surface | WaveBench contract | Plan and boundary |
| --- | --- | --- | --- |
| Identity | `*IDN?` | `scope.idn` | Offline complete; strict RIGOL/MSO8104 identity, hardware unverified |
| Error queue | `:SYSTem:ERRor[:NEXT]?` | `scope.errors` | RFC and skip; consuming text queries cannot disable replay through the current transport API |
| Input safety | channel coupling and impedance queries | `scope.channel_coupling` | M2; combine both values and fail closed for 50 ohms or unknown states |
| Analog state | display, scale, offset, bandwidth, probe | part of `scope.snapshot` | M7 review; never fabricate required snapshot fields |
| Acquisition/timebase/edge trigger | type, averages, depth, rate, main timebase, edge trigger | capture/status/snapshot | M4/M7; keep acquisition and restoration explicit |
| Current waveform | NORM/BYTE/preamble/data | `scope.fetch_waveform` | M3; at most 1000 screen points and no implicit stop |
| Deep waveform | MAX/RAW/TRACE and chunk ranges | fetch/capture | M4; hard point and memory limits; streaming needs a core RFC |
| Single and multi-channel capture | SINGLE/OPC plus per-source waveform | capture protocols | M4; one acquisition before all channel reads; no extra synchronization claim |
| Screenshot | display data or save-image data | `scope.screenshot` | M5; use core-supported block framing and no instrument files |
| Digital/MSO | LA state and D0-D15 waveform | digital status/waveform | M6; module gate, stopped acquisition, axis consistency, uint16 packing |
| Measurement, math, FFT, reference, cursor | corresponding query families | typed scope capabilities | M7 review; read existing configuration only and skip model mismatches |
| DVM and counter | DVM/counter families | no suitable scope capability | RFC and skip |
| AWG | source families | unresolved shared-resource multi-kind contract | RFC and skip |
| Protocol, mask, search, record | option-heavy application families | no base contract | RFC and skip |
| Reset, network, option install, files, calibration | system/storage families | none | Default deny |

## Waveform contract

BYTE conversion uses the ten-field preamble and these equations:

```text
voltage = (raw - y_origin - y_reference) * y_increment
x_start = x_origin - x_reference * x_increment
x_stop  = x_start + (points - 1) * x_increment
```

The driver requires exact payload length, finite axes, and finite converted samples. The core transport owns IEEE/TMC block decoding.

## Explicitly unverified

Hardware identity formatting, USB/LAN/GPIB behavior, the no-error sentinel, OPC acquisition semantics, screenshot framing, RAW chunk limits and throughput, WORD byte order, LA hardware/options, and all measurement accuracy remain unverified.
