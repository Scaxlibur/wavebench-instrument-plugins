# MSO8104 Programming-Guide Coverage Matrix

[中文](MSO8104_COVERAGE_MATRIX.md)

See [MSO8104 Coverage Milestones](MSO8104_COVERAGE_MILESTONES_EN.md) for sequencing and safety rules. A command listed here is neither an implementation claim nor hardware evidence.

The audited source is RIGOL MSO8000 Programming Guide `PGA26006-1110`, which covers MSO8064, MSO8104, and MSO8204 and frequently uses MSO8204 examples. This plugin initially names only MSO8104.

| Domain | Manual surface | WaveBench contract | Plan and boundary |
| --- | --- | --- | --- |
| Identity | `*IDN?` | `scope.idn` | Offline complete; strict RIGOL/MSO8104 identity, hardware unverified |
| Error queue | `:SYSTem:ERRor[:NEXT]?` | `scope.errors` | RFC and skip; consuming text queries cannot disable replay through the current transport API |
| Input safety | channel coupling and impedance queries | `scope.channel_coupling` | Offline complete; combine both values and let the core reject 50 ohms, GND, or unknown states by default |
| Autoscale | system autoscale enable and autoscale command | `scope.autoscale` | Offline complete; preflight enable state, acknowledge vertical/timebase/trigger mutation, and latch uncertain writes or OPC completion; hardware effect unverified |
| Analog state | display, scale, offset, bandwidth, probe | part of `scope.snapshot` | M7 review; never fabricate required snapshot fields |
| Acquisition/timebase/edge trigger | type, averages, depth, rate, main timebase, edge trigger | capture/status/snapshot | M4/M7; keep acquisition and restoration explicit |
| Current waveform | NORM/BYTE/preamble/data | `scope.fetch_waveform` | Offline complete; fixed 1000 displayed-channel points, six-field transfer-state restoration, and no implicit stop |
| Deep waveform | MAX/RAW and chunk ranges | fetch/capture | Offline complete; at most 250,000 points per block and four million total points per call; streaming needs a core RFC |
| Single and multi-channel capture | SINGLE, trigger status, and per-source waveform | capture protocols | Offline complete for DEF/MAX/DMAX; one SINGLE, STOP polling, consistent X axes, and no OPC completion claim |
| Math waveform metadata | MATH display and waveform MATH source/NORM/BYTE/preamble | `scope.math_metadata` | Offline complete for displayed slots in MAIN mode; restore six transfer fields and read no data; math results remain hardware-unverified |
| Screenshot | display data or save-image data | `scope.screenshot` | RFC and skip; DISPLAY framing is undocumented and SAVE DATA cannot prove `include_menu=False`; see RFC-0003 |
| Digital status | hardware-module and LA status queries | `scope.digital_status` | RFC and skip; the mandatory core model requires activity, technology, hysteresis, and other fields the device cannot query; see RFC-0004 |
| Digital waveform | D0-D15 waveform source and data | `scope.digital_waveform` | Manual-evidence gap and skip; the bitset model is suitable, but BYTE/WORD logic codes are undefined and WORD byte order is unclear |
| Measurement, FFT, reference, cursor | corresponding query families | typed scope capabilities | M7 review; read existing configuration only and skip model mismatches |
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
