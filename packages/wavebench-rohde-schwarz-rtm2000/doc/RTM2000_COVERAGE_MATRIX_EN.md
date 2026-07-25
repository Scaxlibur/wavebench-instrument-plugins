# RTM2000 manual feature coverage matrix

[中文](RTM2000_COVERAGE_MATRIX.md)

## Purpose and counting method

This matrix compares the locally stored RTM2000 programming-manual command index with the WaveBench external RTM2000 plugin, the bundled fallback, and recorded RTM2032 hardware acceptance. It separates manual claims, implemented product behavior, and hardware evidence; a command listed for the RTM2000 family is not assumed to be installed or supported on the current RTM2032.

The selected manual transcription has 1,490 lines containing 1,434 command-index entries and 1,417 exact unique command templates: 608 query-marked forms and 809 non-query forms. Further case-insensitive, whitespace-normalized parsing yields 1,416 templates (607 query-marked and 809 non-query); the final difference is one repeated/layout variant. These figures still include parameterized templates and a small number of OCR defects. They describe command-surface scale and are not a feature-completion denominator.

The external plugin currently declares eight WaveBench capabilities and directly uses roughly twenty SCPI templates. It is a hardware-accepted analog-waveform acquisition MVP, not a general RTM2000 remote-control layer.

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
| Identity, synchronization, basic errors | IEEE 488.2 common commands and `SYSTem:ERRor:*` | `*IDN?`, `*OPT?`, non-consuming health snapshot, `*CLS`, `*OPC?` wait, explicit error queue | **Hardware accepted** | No self-test or complete event-register API | Identity/options/health P1 complete; keep EVENT reads explicit |
| Acquisition control | 16 templates for modes, averaging, sample/record rates, interpolation, segmented acquisition, and availability | Read-only available/count/sample-rate state, `SINGle` acquisition, and explicit `AUToscale` | **Partially accepted** | No run/stop, average, segmented, write-rate, or interpolation API | Read-only P1 complete; **P2** bounded average/segmented plans |
| Analog channel setup | About 48 templates for state, coupling, range, scale, offset, position, bandwidth, polarity, skew, label, overload, and thresholds | Typed read-only RTM2032 CH1/CH2 state plus existing enable/scale/position writes | **Hardware accepted** | No threshold readback; setters lack general snapshot/restoration | Read-only P1 complete; retain impedance and restoration guards for writes |
| Analog waveform transfer | `CHANnel<m>:DATA*`, envelope data, independent X/Y metadata | REAL/LSBF, header + data, `DEF/MAX/DMAX`, sequential channel reads after one acquisition | **Hardware accepted** | No envelope, explicit X/Y metadata, history/segment selection, or streaming-block API; no added cross-channel hardware-synchronization guarantee | **P1** metadata; **P2** segmented/history/envelope |
| Timebase, zoom, timestamp | 12 timebase templates plus zoom and timestamp navigation | Typed read-only acquisition time/divisions/position/range/reference/scale/roll plus existing `TIMebase:RANGe` write | **Hardware accepted** | No zoom or timestamp support | Basic P1 complete; **P2** zoom/history timestamp |
| Trigger system | About 159 templates for A/B, edge, width, runt, rise time, pattern, TV, holdoff, external, protocol, and trigger out | No trigger configuration; single capture reuses front-panel state | Existing-trigger capture only | No source, mode, type, level, slope, holdoff, B trigger, or output | **P1** minimal edge-trigger closed loop; layer all other types |
| Automatic measurements/statistics | 20 templates for slots, source/main, actual, peaks, mean, standard deviation, and waveform count | Not covered | None | Host analysis cannot read instrument measurement results | **P1** high-value read-only extension |
| Cursors | About 27 templates for X/Y, delta, ratio, tracking, and results | Not covered | None | No cursor setup or result reads | **P2** results first, controlled placement later |
| Math and FFT | About 51 templates for expression, math/envelope data, window, span, and RBW | Not covered | None | No instrument math/FFT setup or waveform readout | **P2** read math/FFT waveforms; keep host DSP a separate source |
| Spectrum/spectrogram | 107 templates for spectrum waveforms, frequency axis, RBW, markers, history, and spectrogram | Not covered | None | Complete spectrum-analysis application absent | **P3, option gated** with a separate capability |
| Search | About 119 templates for edge/width/runt/pattern, result lists, and protocol search | Not covered | None | No search plan, results, or navigation | **P3**, after history/trigger/protocol models mature |
| Mask test | About 36 templates for mask data, counts, actions, save/load | Not covered | None | No mask lifecycle, violation model, or action safety policy | **P3**; separate read-only results from destructive actions |
| Digital/MSO channels | About 33 templates for digital data, thresholds, technology, deskew, and history | Not covered | None | No digital waveform/logic-width/threshold model | **P3, option gated** |
| Serial/parallel bus decoding | About 249 templates for I²C, SPI/SSPI, UART, CAN, LIN, I²S, ARINC, MIL-STD, parallel buses, and frame results | Not covered | None | No bus setup, frame list, field parser, or history model | **P3, split by option**; do not fold into the basic scope capability |
| Protocol trigger/search | Large protocol subsets under trigger and search | Not covered | None | Depends on bus sources, thresholds, protocol format, and options | **P3**, after read-only bus decode |
| DVM and frequency counter | Six DVM and three counter templates | Not covered | None | No source/type/result/status API | **P2, option gated**, suitable for small read-only capabilities |
| Probe metadata/setup | About 18 templates for identity, attenuation, bandwidth, impedance, offset, and mode | Read-only RTM2032 CH1/CH2 attenuation, bandwidth, capacitance, impedance, name, and type | **Hardware accepted** | No probe ID fields, DC offset, mode, or safety-limit integration | Basic P1 complete; add identity/safety integration later and defer writes |
| Reference curves | About 19 templates for source/save/load/state, scaling, and data | Not covered | None | No reference waveform readout or state management | **P2** read/download first, save/load later |
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
3. Minimal edge-trigger closed loop for source/mode/slope/level/find-level, with snapshot, independent readback, and explicit restoration responsibility.
4. Read-only automatic measurement results/statistics, clearly distinguished from host-side DSP.
5. Waveform metadata and segment/history identity so separate acquisitions or segments cannot be conflated.

### P2: analysis and specialized acquisition

- average/segmented acquisition and history/timestamps;
- math/FFT/reference waveforms;
- cursor, DVM, and counter results;
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
- Hardware side: public README evidence for RTM2032 `DEF/MAX/DMAX`, dual-channel single acquisition, autoscale, coupling, screenshot, 20/20 repeat capture, empty error queue, and restoration.
- This matrix did not access an instrument and does not promote code presence to hardware acceptance.
