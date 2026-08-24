# MSO8104 Programming-Guide Coverage Matrix

[中文](MSO8104_COVERAGE_MATRIX.md)

See [MSO8104 Coverage Milestones](MSO8104_COVERAGE_MILESTONES_EN.md) for sequencing and safety rules. A command listed here is neither an implementation claim nor hardware evidence.

The audited source is RIGOL MSO8000 Programming Guide `PGA26006-1110`, which covers MSO8064, MSO8104, and MSO8204 and frequently uses MSO8204 examples. This plugin initially names only MSO8104.

| Domain | Manual surface | WaveBench contract | Plan and boundary |
| --- | --- | --- | --- |
| Identity | `*IDN?` | `scope.idn` | Hardware complete for MSO8104 firmware `00.02.02` over LAN/PyVISA; no model or firmware extrapolation |
| Error queue | `:SYSTem:ERRor[:NEXT]?` | `scope.errors` | RFC and skip; consuming text queries cannot disable replay through the current transport API |
| Input safety | channel coupling and impedance queries | `scope.channel_coupling` | Hardware complete for CH1=`DCL` and CH2=`ACL`, both core high-impedance tokens; the core rejects 50 ohms, GND, or unknown states by default |
| Autoscale | system autoscale enable and autoscale command | `scope.autoscale` | Offline complete; preflight enable state, acknowledge vertical/timebase/trigger mutation, and latch uncertain writes or OPC completion; hardware effect unverified |
| Complete snapshot | channel, timebase, probe, waveform, trigger, and partial health | `scope.snapshot` | RFC and skip; mandatory fields are unavailable and `*STB?` clears state; see RFC-0005 |
| Existing acquisition configuration | type, averages, depth, rate, run/stop/single | fetch/capture preconditions | M4 offline complete; preserve current settings, and do not expose unrestricted setters |
| Acquisition status | averages and trigger status | `scope.acquisition_status` | RFC and skip; no average-complete or segmented status, and trigger STOP is not average completion; see RFC-0006 |
| Average capture transaction | global acquisition type and average count | `scope.capture_average` | RFC and skip; the core requires single count/channel arithmetic and the device has no average-complete query; see RFC-0006 |
| Current waveform | NORM/BYTE/preamble/data | `scope.fetch_waveform` | Transport/recovery hardware pass; signal closure pending | The bounded profile in the current core worktree permits only `DEF`; exact `LF` trailing, `1,000` bytes, and one binary query pass on hardware, and core completes restore/fresh verification; returned data does not match the enabled source |
| Deep waveform | MAX/RAW and chunk ranges | fetch/capture | Default deny | MAX/DMAX have not completed bounded-profile and hardware acceptance; offline per-block and total limits remain documented |
| Single and multi-channel capture | SINGLE, trigger status, and per-source waveform | capture protocols | Default deny | capture still lacks complete acquisition, trigger, timebase, and channel-state recovery evidence; do not represent SINGLE or OPC as completed waveform acceptance |
| Math waveform metadata | MATH display and waveform MATH source/NORM/BYTE/preamble | `scope.math_metadata` | Offline complete for displayed slots in MAIN mode; restore six transfer fields and read no data; hardware restoration remains unverified |
| Manual cursor readout | cursor mode, type, source, unit, and delta queries | `scope.cursor_readout` | Restricted offline support for index 1 and same-source TIME+SEC or AMPL+SOUR; never move cursors; accuracy unverified |
| Screenshot | display data or save-image data | `scope.screenshot` | RFC and skip; DISPLAY framing is undocumented and SAVE DATA cannot prove `include_menu=False`; see RFC-0003 |
| Digital status | hardware-module and LA status queries | `scope.digital_status` | RFC and skip; the mandatory core model requires activity, technology, hysteresis, and other fields the device cannot query; see RFC-0004 |
| Digital waveform | D0-D15 waveform source and data | `scope.digital_waveform` | Manual-evidence gap and skip; the bitset model is suitable, but BYTE/WORD logic codes are undefined and WORD byte order is unclear |
| Measurement statistics | item/source statistics queries | `scope.measurement_statistics` | RFC and skip; the core addresses slots while the device cannot resolve slots or return a sample buffer; see RFC-0007 |
| FFT status | FFT source, window, unit, and frequency settings | `scope.fft_status` | RFC and skip; mandatory average-complete, RBW, and FFT sample-rate queries are absent; see RFC-0007 |
| Reference metadata | source, vertical display, and label settings | `scope.reference_metadata` | Vendor-evidence gap and skip; REF is not a waveform source, so axes, points, and Y resolution are unavailable |
| History timestamps | record enable/start/play/current/frame count | `scope.history_timestamps` | Vendor-evidence gap and skip; no per-frame relative or calendar timestamp exists |
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

USB/GPIB behavior, the no-error sentinel, OPC acquisition semantics, `DEF` known-signal closure, X/Y conversion and measurement accuracy, MAX/DMAX chunking and throughput, WORD byte order, LA hardware/options, and all measurement accuracy remain unverified.
