# RTM2000 manual feature coverage matrix

[中文](RTM2000_COVERAGE_MATRIX.md)

## Purpose and counting method

This matrix compares the locally stored RTM2000 programming-manual command index with the WaveBench external RTM2000 plugin, the bundled fallback, and recorded RTM2032 hardware acceptance. It separates manual claims, implemented product behavior, and hardware evidence; a command listed for the RTM2000 family is not assumed to be installed or supported on the current RTM2032.

The selected manual transcription has 1,490 lines containing 1,434 command-index entries and 1,417 exact unique command templates: 608 query-marked forms and 809 non-query forms. Further case-insensitive, whitespace-normalized parsing yields 1,416 templates (607 query-marked and 809 non-query); the final difference is one repeated/layout variant. These figures still include parameterized templates and a small number of OCR defects. They describe command-surface scale and are not a feature-completion denominator.

The external plugin currently declares twenty-four WaveBench capabilities, including five read-only Scope V2 capabilities added in 0.13.0. It is a hardware-accepted analog-waveform acquisition MVP with narrow read-only status and analysis surfaces plus one controlled average-acquisition transaction, not a general RTM2000 remote-control layer.

Coverage labels:

- **Hardware accepted**: implemented and offline-tested with controlled RTM2032 evidence.
- **Implemented**: code and offline tests exist, without a separate hardware conclusion for that detail.
- **Partial**: only a narrow subset of the manual family is covered.
- **Not covered**: no corresponding external-plugin, bundled-fallback, or generic ScopeService API.
- **Acceptance-tool only**: reserved for experiment restoration/acceptance rather than production driver use.
- **Option/model gated**: identity and installed options must be checked before exposure.

## Feature matrix

| Feature domain | Manual surface | Current coverage | Hardware state | Main gap | Recommendation |
|---|---|---|---|---|---|
| Identity, synchronization, basic errors | IEEE 488.2 common commands and `SYSTem:ERRor:*` | `*IDN?`, `*OPT?`, non-consuming health snapshot, five-field identity `scope.snapshot_v2`, `*CLS`, `*OPC?` wait, explicit error queue | **Hardware accepted**: CH1/CH2 Snapshot V2 read-only acceptance passed | No self-test or complete event-register API | Identity/options/health P1 complete; keep EVENT reads explicit |
| Acquisition control | 16 templates for modes, averaging, sample/record rates, interpolation, segmented acquisition, and availability | Read-only available/count/sample-rate plus average/segmented status, `SINGle` acquisition, explicit `AUToscale`, and controlled `scope.capture_average` | **Read-only status hardware accepted; average transaction implemented, pending independent hardware acceptance** | No run/stop, segmented acquisition, write-rate, or interpolation API | Keep explicit stopped confirmation, readback restoration, and latching for average; **P2** segmented plans |
| Analog channel setup | About 48 templates for state, coupling, range, scale, offset, position, bandwidth, polarity, skew, label, overload, and thresholds | Typed read-only RTM2032 CH1/CH2 state and `scope.channel_input_state_v2`; V2 maps only coupling/termination and marks numeric impedance unavailable, plus existing enable/scale/position writes | **Hardware accepted**: CH1/CH2 V2 input-state read-only acceptance passed | No threshold readback; setters lack general snapshot/restoration | Read-only P1 complete; retain impedance and restoration guards for writes |
| Analog waveform transfer | `CHANnel<m>:DATA*`, envelope data, independent X/Y metadata | REAL/LSBF, header + data, `DEF/MAX/DMAX`, sequential channel reads after one acquisition, and typed X/Y scaling, point-count, quantization, and values-per-sample snapshots | **Hardware accepted** | No envelope, history/segment selection, or streaming-block API; no added cross-channel hardware-synchronization guarantee | Metadata complete; **P2** segmented/history/envelope |
| Timebase, zoom, timestamp | 12 timebase templates plus zoom and timestamp navigation | Typed read-only acquisition time/divisions/position/range/reference/scale/roll plus existing `TIMebase:RANGe` write; K15-gated strict history timestamp-table API | **Basic timebase hardware accepted; history timestamp query blocked by instrument timeout** | No zoom; no successful timestamp-table hardware evidence | Keep the strict K15 gate and do not retry/clear errors implicitly; investigate history state separately |
| Trigger system | About 159 templates for A/B, edge, width, runt, rise time, pattern, TV, holdoff, external, protocol, and trigger out | Typed read-only basic edge-trigger snapshot for CH1/CH2; vendor-specific controlled RTM2032 CH2 `EDGE/AUTO/POS/DC/level` setter; single capture reuses front-panel state | **Read-only and CH2 write/restore hardware accepted** | Setter accepts only healthy, high-impedance, non-overloaded CH2 and an in-range level; no automatic restoration journal, other trigger types, B trigger, or output | P1 complete; keep restoration responsibility explicit and design a separate transaction model before broader writes |
| Automatic measurements/statistics | 20 templates for slots, source/main, actual, peaks, mean, standard deviation, and waveform count | `scope.measurement_statistics` and `scope.measurement_statistics_v2`; V2 reads only caller-confirmed preconfigured slots 1-4, supports no buffer, and requires complete finite aggregates | **Existing configured-slot path hardware accepted; V2 adapter offline verified** for CH2 frequency actual/average/min/max/stddev/count; unconfigured-slot timeout remains a negative boundary | Stopped-acquisition buffer read is not hardware accepted and is outside the V2 profile | Keep caller confirmation mandatory; require stopped confirmation for buffer reads; never configure/reset slots or consume the error queue in this API |
| Cursors | About 27 templates for X/Y, delta, ratio, tracking, and results | `scope.cursor_readout` for explicitly preconfigured cursor state | **Vertical delta hardware accepted**; other cursor functions remain offline-tested | No production cursor setup or position writes | Readout is complete for the narrow capability; keep placement as a separate controlled action |
| Math and FFT | About 51 templates for expression, math/envelope data, window, span, and RBW | `scope.math_metadata`, guarded `scope.fft_status`, `scope.fft_status_v2` limited to average complete/RBW/sample rate, and `scope.reference_metadata` for existing state | **Existing math metadata and FFT status hardware accepted; V2 adapter offline verified**; reference metadata blocked because the instrument had no valid stored reference | No payload read, production expression setup, or reference update/save/load | Keep stateful configuration separate, preserve reference storage, and keep host DSP distinct |
| Spectrum/spectrogram | 107 templates for spectrum waveforms, frequency axis, RBW, markers, history, and spectrogram | Not covered | None | Complete spectrum-analysis application absent | **P3, option gated** with a separate capability |
| Search | About 119 templates for edge/width/runt/pattern, result lists, and protocol search | Not covered | None | No search plan, results, or navigation | **P3**, after history/trigger/protocol models mature |
| Mask test | About 36 templates for mask data, counts, actions, save/load | Not covered | None | No mask lifecycle, violation model, or action safety policy | **P3**; separate read-only results from destructive actions |
| Digital/MSO channels | About 33 templates for digital data, thresholds, technology, deskew, and history | B1-gated `scope.digital_status` and `scope.digital_status_v2`; V2 marks threshold scope and timing calibration unavailable; `scope.digital_waveform` reads each Dn under the existing ASCII format (manual `ASC,0`, RTM2032 readback `CSV,0`) and host-packs uint16 | **Scalar status hardware accepted**: existing D0-D15 and CLI acceptance remains valid, and D0 V2 read-only acceptance passed; digital waveform passed FakeTransport, while hardware read-only preflight passed B1/format gating but stopped before `DATA?` because D0 was hidden and reported zero points | Digital waveform payload hardware acceptance is pending; no configuration writes, history, or bus decode; no electrical-input acceptance | Run zero-write payload/axis-consistency acceptance against a stable stopped record; treat electrical acceptance separately |
| Serial/parallel bus decoding | About 249 templates for I²C, SPI/SSPI, UART, CAN, LIN, I²S, ARINC, MIL-STD, parallel buses, and frame results | Not covered | None | No bus setup, frame list, field parser, or history model | **P3, split by option**; do not fold into the basic scope capability |
| Protocol trigger/search | Large protocol subsets under trigger and search | Not covered | None | Depends on bus sources, thresholds, protocol format, and options | **P3**, after read-only bus decode |
| DVM and frequency counter | Six DVM and three counter templates | Not covered | None | No source/type/result/status API | **P2, option gated**, suitable for small read-only capabilities |
| Probe metadata/setup | About 18 templates for identity, attenuation, bandwidth, impedance, offset, and mode | Read-only RTM2032 CH1/CH2 attenuation, bandwidth, capacitance, impedance, name, and type | **Hardware accepted** | No probe ID fields, DC offset, mode, or safety-limit integration | Basic P1 complete; add identity/safety integration later and defer writes |
| Reference curves | About 19 templates for source/save/load/state, scaling, and data | Read-only `scope.reference_metadata` for an existing stored reference | **Implemented; hardware blocked by empty reference storage** (`DATA:HEADer?` reported zero points and later metadata queries timed out) | No safe test fixture without overwriting internal reference storage; no data payload or state management | Wait for a user-created reference; do not call `UPDATE`, save, or load merely to manufacture acceptance evidence |
| Display and screenshot | 24 display plus eight hardcopy templates | PNG, color scheme, menu inclusion | **Hardware accepted** | No grid, palette, persistence, XY, virtual-screen, page, or printer setup | Screenshot satisfies MVP; others **P3** |
| Instrument filesystem/export | 16 `MMEMory` templates plus waveform, measurement, search, and power export | Not covered; WaveBench saves host-side artifacts only | None | No instrument filesystem or report export | **Out of default scope**; require a path sandbox and separate permission |
| Setup snapshot/restoration | `SYSTem:SET`, `MMEMory:STORE/LOAD:STATE` | Not exposed by production driver; setup blob used by acceptance tooling | **Acceptance path passed** | SocketIO setup writes were once partial; reliable restoration uses controlled VXI-11 chunks | Keep **acceptance-tool only** |
| Status registers/health | Operation/questionable/status-byte, overload, mask, limit status | Non-consuming health snapshot plus channel-overload readback | **Hardware accepted** | No mask/limit aggregation or event-register API | Basic P1 complete; keep EVENT reads explicit and consuming |
| Power analysis | About 358 templates for quality, harmonics, ripple, switching, SOA, efficiency, inrush, and modulation | Not covered | None | Separate application domain with probes, deskew, reports, and many result types | **P3, option gated, separate capability/package** |
| Calibration, reset, system settings | Calibration, `*RST`, preset, clock, language, beeper, education mode | Not covered | None | Global mutation and manual-recovery risk | **Denied by default** or explicit acceptance-tool authorization only |

## Directly covered SCPI surface

The external driver mainly uses the following equivalent command families:

```text
*IDN?  *CLS  *OPC?
SYSTem:ERRor[:NEXT]?
AUToscale  SINGle
TIMebase:RANGe
CHANnel<n>:STATE  CHANnel<n>:COUPling?
CHANnel<n>:SCALe  CHANnel<n>:POSition
FORMat[:DATA]  FORMat:BORder
CHANnel:DATA:POINTs
CHANnel<n>:DATA:HEADer?  CHANnel<n>:DATA?
HCOPy:LANGuage  HCOPy:COLor:SCHeme  HCOPy:MENU  HCOPy:DATA?
```

The implementation uses supported short forms. This list normalizes them to manual-style long forms for auditing and is not a raw communication log.

## WaveBench core coverage outside instrument SCPI

- Reads coupling before capture and rejects potentially 50 Ω `AC` / `DC` by default; continuation requires explicit opt-in. `ACL` / `DCL` are accepted as high-impedance paths.
- Atomically records capture artifacts as CSV, NPY, metadata, screenshots, and sanitized command logs; failure metadata and already-produced evidence are retained.
- Uses capability checks, a restricted external-plugin override slot, and uninstall fallback so plugin installation cannot falsely advertise unimplemented features.
- Keeps `AUToscale` explicit rather than silently changing front-panel state during capture.

These improve experiment safety and traceability but do not count as RTM2000 manual-command coverage.

## Recommended roadmap

### P1: turn the capture MVP into a diagnosable basic scope driver

1. Read-only `identity/options/health` snapshot covering `*OPT?`, acquisition, and non-consuming status conditions. **Complete.**
2. Typed RTM2032 CH1/CH2 analog-channel, timebase, and probe state. **Basic fields complete and hardware accepted.**
3. Basic edge trigger: the strict read-only snapshot and minimal controlled CH2 source/type/mode/slope/coupling/level loop are complete. It does not call find-level implicitly, and the production setter does not pretend to own a persistent restoration journal.
4. Read-only automatic measurement results/statistics, clearly distinguished from host-side DSP. **Caller-confirmed configured-slot statistics are hardware accepted; stopped-acquisition buffer read remains pending.**
5. Waveform scaling and shape metadata. **Complete and hardware accepted.** `DATA:HEADER?` field four is values per sample interval, not a segment ID; segment/history identity requires a separate history/timestamp path.

### P2: analysis and specialized acquisition

- average/segmented acquisition and history/timestamps; **the controlled average transaction is implemented but awaits independent hardware acceptance; segmented acquisition remains deferred; the K15 timestamp-table query timed out and remains blocked**;
- math/FFT/reference waveforms; **math metadata and FFT status are hardware accepted; reference metadata awaits a valid pre-existing reference**;
- cursor, DVM, and counter results; **vertical cursor readout is hardware accepted; DVM/counter remain uncovered**;
- read-only probe identity and attenuation/impedance safety integration.

### P3: option-specific applications

- spectrum/spectrogram;
- digital/MSO and bus decode;
- protocol trigger/search;
- mask testing;
- power analysis.

These domains must not be bypassed through a generic raw-SCPI entry point. They need capability contracts, option detection, restoration policy, and explicit permissions.

## Boundaries that are not defects

- The index spans multiple RTM2000 models, firmware revisions, and options. Missing option commands are not automatically basic-driver defects.
- WaveBench host-side CSV/NPY/PNG artifacts do not constitute instrument-side `MMEMory`/`EXPort` support.
- Host DSP may compute FFT/THD but does not constitute instrument `CALCulate:MATH:FFT`, `SPECtrum`, or `POWer` result support.
- Setup-blob restoration is an acceptance safety mechanism and should not become a production configuration API merely because the manual lists `SYSTem:SET`.
- Sequential channel reads after one acquisition do not add or prove a cross-channel hardware-synchronization guarantee.

## Evidence boundary

- Manual side: a locally stored RTM2000 programming-manual command index used only for internal auditing and excluded from distributions.
- Implementation side: current external `driver.py`/`descriptor.py`, the WaveBench bundled fallback, and ScopeService.
- Hardware side: controlled RTM2032 evidence for `DEF/MAX/DMAX`, dual-channel single acquisition, autoscale, coupling, screenshot, repeat capture, restoration, configured-slot measurement statistics, math/FFT metadata, vertical cursor readout, and B1-gated D0-D15 digital scalar-status queries. The latest session also records negative evidence for history timestamps and empty reference storage.
- Hardware labels require an explicit controlled probe and state-restoration check; code presence alone is never promoted to hardware acceptance.
