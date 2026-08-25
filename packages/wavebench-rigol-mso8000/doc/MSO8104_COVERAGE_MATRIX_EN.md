# MSO8104 Programming-Guide Coverage Matrix

[中文](MSO8104_COVERAGE_MATRIX.md)

See [MSO8104 Coverage Milestones](MSO8104_COVERAGE_MILESTONES_EN.md) for sequencing and safety rules. A command listed here is neither an implementation claim nor hardware evidence.

The audited source is RIGOL MSO8000 Programming Guide `PGA26006-1110`, which covers MSO8064, MSO8104, and MSO8204 and frequently uses MSO8204 examples. This plugin initially names only MSO8104.

| Domain | Manual surface | WaveBench contract | Plan and boundary |
| --- | --- | --- | --- |
| Identity | `*IDN?` | `scope.idn` | Hardware complete for MSO8104 firmware `00.02.02` over LAN/PyVISA; no model or firmware extrapolation |
| Error queue | `:SYSTem:ERRor[:NEXT]?` | `scope.errors` | RFC and skip; consuming text queries cannot disable replay through the current transport API |
| Input safety | channel coupling and impedance queries | `scope.channel_coupling`, `scope.channel_input_state_v2` | Hardware complete: the legacy route retains core high-impedance tokens, while V2 separately returns coupling, termination, and impedance. CH1/CH2 V2 both returned `dc + high_z + 1 MΩ`; the core rejects 50 ohms, GND, or unknown states by default |
| Autoscale | system autoscale enable and autoscale command | `scope.autoscale` | Offline complete; preflight enable state, acknowledge vertical/timebase/trigger mutation, and latch uncertain writes or OPC completion; hardware effect unverified |
| Complete snapshot | channel, timebase, probe, waveform, trigger, and partial health | `scope.snapshot` | RFC and skip; mandatory fields are unavailable and `*STB?` clears state; see RFC-0005 |
| Snapshot V2 | `*IDN?` and 13 `:SYSTem:OPTion:STATus? <type>` queries | `scope.snapshot_v2` | Hardware verified for restricted identity/licensed options | Fourteen fixed text queries read identity and every manual-defined licensed-option status in one call; an empty options tuple exists only if all 13 explicitly prove not installed. All 55 health, channel, timebase, probe, waveform, and trigger fields are unavailable in stable order; no status register, error queue, trigger, waveform, or binary read occurs |
| Existing acquisition configuration | type, averages, depth, rate, run/stop/single | fetch/capture preconditions | M4 offline complete; preserve current settings, and do not expose unrestricted setters |
| Acquisition status (legacy) | averages and trigger status | `scope.acquisition_status` | RFC and skip; the legacy model requires average completion and segmented status, while trigger STOP is not average completion; see RFC-0006 |
| Acquisition status V2 | `:ACQuire:TYPE?`, `:ACQuire:SRATe?`, `:ACQuire:MDEPth?`, and `:ACQuire:AVERages?` in AVER mode | `scope.acquisition_status_v2` | Hardware verified for restricted NORM | Three fixed pure queries, with a fourth configured-count read only in AVER mode. Current response was `NORM + 500 kSa/s + 10 kpts`; average is not applicable in NORM, and run state/segmented status are unavailable. No trigger, OPC, or status-register query occurs and STOP never implies completion; AVER semantics and average completion remain unverified |
| Acquisition run state | `:TRIGger:STATus?` | `scope.acquisition_run_state` | Hardware verified for restricted observation | One text query: STOP→stopped, WAIT→waiting, RUN/AUTO→acquiring, and TD→unknown. Hardware moved from AUTO through STOP, then observed WAIT after NORMAL/RUN, and finally STOP; state observation does not prove SINGLE completion |
| Acquisition control | `:RUN`, `:STOP`, `:SINGle`, `:TRIGger:SWEep?`, and `:ACQuire:TYPE?` | `scope.acquisition_control` | Default deny | Core binds start, stop, and completion-style SINGLE into one capability. `start(normal)`→`stop` returned active/stopped on hardware, and no-signal SINGLE Core cleanup/fresh verification passed on hardware. A limited-signal CH1 SINGLE first observed STOP, not a nonterminal→STOP completion transition; historical EOF/blocked-session outcomes are also not completion evidence, so it remains undeclared |
| Average capture transaction | global acquisition type and average count | `scope.capture_average` | RFC and skip; the core requires single count/channel arithmetic and the device has no average-complete query; see RFC-0006 |
| Current waveform | NORM/BYTE/preamble/data | `scope.fetch_waveform` | Hardware complete for limited `DEF`: exact `LF` trailing, `1,000` bytes, and one binary query pass on hardware, and core completes restore/fresh verification. Under the recorded `1 kHz / 1 Vpp / 0 V` source condition, CH1 returned `1.05713 Vpp / 1000 Hz` and CH2 returned `1.0705 Vpp / 999.167 Hz` |
| Deep waveform | MAX/RAW and chunk ranges | `scope.fetch_waveform` | Hardware complete for restricted stopped-state MAX/DMAX | The one bounded profile limits each response to `250,000` bytes, an operation to `4,000,000` bytes, and binary I/O to 16 queries. MAX/DMAX first require observed STOP, then read memory depth and narrow points to the minimum of memory depth, the runtime total-point limit, and 16 chunks; they never send RUN/STOP/SINGLE. With both sources OFF, CH1/CH2 high impedance, `10 kpts` current memory depth, and `20 kpts / 2.5 kpts chunks`, both MAX and DMAX returned `10,000` samples on both channels and completed five-field restore/fresh verification. Running-state MAX, other depths, throughput, timeout, and capture remain unverified |
| Single and multi-channel capture | SINGLE, trigger status, and per-source waveform | capture protocols | Default deny | capture still lacks complete acquisition, trigger, timebase, and channel-state recovery evidence; do not represent SINGLE or OPC as completed waveform acceptance |
| Math waveform metadata | MATH display and waveform MATH source/NORM/BYTE/preamble | `scope.math_metadata` | Offline complete for displayed slots in MAIN mode; restore six transfer fields and read no data; hardware restoration remains unverified |
| Manual cursor readout | cursor mode, type, source, unit, value, and delta queries | `scope.cursor_readout`, `scope.cursor_readout_v2` | Restricted offline support: V2 uses global addressing and reads manual TIME/AMPL A/B sources, units, A/B values, and deltas without moving cursors. Current hardware is VBA, so it rejects before value queries; accuracy remains unverified |
| Screenshot | display data or save-image data | `scope.screenshot` | RFC and skip; DISPLAY framing is undocumented and SAVE DATA cannot prove `include_menu=False`; see RFC-0003 |
| Digital status (legacy) | hardware-module and LA status queries | `scope.digital_status` | RFC and skip; the legacy model requires activity, technology, hysteresis, and other fields the device cannot query; see RFC-0004 |
| Digital status V2 | `:SYSTem:MODules?`, `:LA:DIGital:DISPlay?`, `:LA:DIGital:LABel?`, `:LA:POD<n>:THReshold?`, `:LA:TCALibrate?`, and `:LA:SIZE?` | `scope.digital_status_v2` | Hardware verified for restricted D0/D8 static state | Each call first reads the LA module bit; an absent module returns only `shared.module_present=false` and sends no `:LA:*?` query. With LA present, six fixed text queries return display, label, POD range and `1.4 V` threshold, `0 s` timing calibration, and `MEDIUM` size for D0/D8. Position, label-enabled, activity, technology, and hysteresis stay unavailable; the operation neither reads waveform data nor infers logic activity or encoding |
| Digital waveform | D0-D15 waveform source and data | `scope.digital_waveform` | Manual-evidence gap and skip; the bitset model is suitable, but BYTE/WORD logic codes are undefined and WORD byte order is unclear |
| Measurement statistics | `:MEASure:STATistic:ITEM? <type>,<item>,<source...>` | `scope.measurement_statistics_v2` | Hardware complete for restricted `VPP,CHAN1/CHAN2`: explicit item/source only, six pure reads for CURRENT, AVERages, DEViation, MINimum, MAXimum, and CNT, and `include_buffer=True` rejected. Both controlled VPP reads returned complete numeric results with `CNT=1000`; no statistics configuration, reset, or display write occurs. The legacy slot route remains undeclared; other item/source, dual-source/digital-source semantics, and statistics accuracy remain unverified |
| FFT status | `:MATH<n>:OPERator?` and `:MATH<n>:FFT:*?` | `scope.fft_status_v2` | Hardware verified for restricted MATH1 | First require `OPERator? == FFT`, then read source, window, vertical unit, and start/stop frequency in six pure queries. Front-panel MATH1 returned `FFT + CHAN1 + HANN + VRMS + 0–1 MHz`; source CH1/CH2 were OFF, `consistent`, and `healthy` before and after. Average completion, RBW, and FFT sample rate are always unavailable and never inferred from global sample rate, frequency range, or points. This is not FFT accuracy evidence; the legacy route remains undeclared |
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

USB/GPIB behavior, the no-error sentinel, OPC acquisition semantics, SINGLE nonterminal-to-STOP completion, X/Y conversion and measurement accuracy beyond the recorded `DEF + LF` `1 kHz / 1 Vpp / 0 V` condition, running-state MAX and MAX/DMAX chunking/throughput at other memory depths, WORD byte order, Snapshot V2 health/channel/timebase/probe/waveform/trigger fields, logic-probe behavior, electrical threshold accuracy, logic activity, digital-waveform encoding, and all other measurement accuracy remain unverified. No-signal SINGLE failure recovery is hardware-confirmed but is not completion evidence.
