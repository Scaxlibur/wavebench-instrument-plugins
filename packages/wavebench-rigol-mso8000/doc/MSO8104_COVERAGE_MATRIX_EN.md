# MSO8104 Programming-Guide Coverage Matrix

[中文](MSO8104_COVERAGE_MATRIX.md)

See [MSO8104 Coverage Milestones](MSO8104_COVERAGE_MILESTONES_EN.md) for sequencing and safety rules. A command listed here is neither an implementation claim nor hardware evidence.

The audited source is RIGOL MSO8000 Programming Guide `PGA26006-1110`, which covers MSO8064, MSO8104, and MSO8204 and frequently uses MSO8204 examples. This plugin initially names only MSO8104.

| Domain | Manual surface | WaveBench contract | Plan and boundary |
| --- | --- | --- | --- |
| Identity | `*IDN?` | `scope.idn` | Offline complete; strict RIGOL/MSO8104 identity, hardware unverified |
| Error queue | `:SYSTem:ERRor[:NEXT]?` | `scope.errors` | RFC and skip; consuming text queries cannot disable replay through the current transport API |
| Input safety | channel coupling and impedance queries | `scope.channel_coupling` | Offline complete; combine both values and let the core reject 50 ohms, GND, or unknown states by default |
| Analog state | display, scale, offset, bandwidth, probe | part of `scope.snapshot` | M7 review; never fabricate required snapshot fields |
| Acquisition/timebase/edge trigger | type, averages, depth, rate, main timebase, edge trigger | capture/status/snapshot | M4/M7; keep acquisition and restoration explicit |
| Current waveform | NORM/BYTE/preamble/data | `scope.fetch_waveform` | Offline complete; fixed 1000 displayed-channel points, six-field transfer-state restoration, and no implicit stop |
| Deep waveform | MAX/RAW and chunk ranges | fetch/capture | Offline complete; at most 250,000 points per block and four million total points per call; streaming needs a core RFC |
| Single and multi-channel capture | SINGLE, trigger status, and per-source waveform | capture protocols | Offline complete for DEF/MAX/DMAX; one SINGLE, STOP polling, consistent X axes, and no OPC completion claim |
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
