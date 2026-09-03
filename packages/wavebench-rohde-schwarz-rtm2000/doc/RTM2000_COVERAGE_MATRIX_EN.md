# RTM2000 Manual Feature-Coverage Matrix

[中文](RTM2000_COVERAGE_MATRIX.md)

This page maps RTM2000 programming-manual domains to the WaveBench capabilities currently exposed
by the external `wavebench-rohde-schwarz-rtm2000` plugin. The [package metadata](../pyproject.toml)
is authoritative for version, dependencies, and entry point; the
[production descriptor](../src/wavebench_rohde_schwarz_rtm2000/descriptor.py) for models, backends,
configuration fields, and capabilities; [profiles](../src/wavebench_rohde_schwarz_rtm2000/profiles.py)
for request boundaries; and the [driver](../src/wavebench_rohde_schwarz_rtm2000/driver.py) for exact
SCPI and runtime behavior.

The [feature-coverage development roadmap](RTM2000_COVERAGE_MILESTONES_EN.md) records future order
and exit gates. The [development and acceptance archive](archive/RTM2000_README_0.15_EN.md) retains
hardware and negative evidence for particular versions, devices, and dates. Those records support
traceability and do not independently add a current capability.

## Scope

The local RTM2000 programming-manual index spans multiple models, firmware revisions, and options
and contains a small number of duplicates and OCR defects. This matrix reports the current public
surface by functional domain rather than treating command counts as completion. A manual command,
driver method, or one successful hardware run cannot replace a production-descriptor declaration.

`rohde-schwarz.rtm2032` is the external plugin's canonical driver ID. The short `rtm2032` alias
belongs to the Core fallback. The external plugin provides bounded waveform acquisition, query-only
state/analysis, and controlled view configuration; it is not a general RTM2000 remote-control layer.

## Functional coverage

| Domain | Manual surface | Current public capability | Current boundary |
|---|---|---|---|
| Identity, errors, health | IEEE 488.2, `SYSTem:ERRor:*`, status conditions | `scope.idn`, `scope.errors`, `scope.snapshot`, `scope.snapshot_v2` | Snapshot V2 guarantees only identity fields in its profile. EVENT and error-queue reads are consuming and are not implicit health reads. |
| Autoscale | `AUToscale` | `scope.autoscale` | Explicit action that mutates vertical, timebase, and trigger state; capture never invokes it implicitly. |
| Acquisition state | mode, average, sample/record rate, segmented, available/count | `scope.acquisition_status` | Reads existing state. Option-dependent fields are gated, and undefined completion is not inferred from counts or OPC. |
| Average acquisition | average count, single count, channel arithmetic, `SINGle` | `scope.capture_average` | Caller confirms stopped acquisition. The transaction changes only bounded fields and restores them; unknown outcome latches the write path. |
| Analog input | coupling, termination, range, scale, offset, position, bandwidth, probe | `scope.channel_coupling`, `scope.channel_input_state_v2`, `scope.snapshot` | V2 maps coupling/termination and may leave numeric impedance unavailable. Core enforces the high-impedance policy. |
| Channel display | channel state | `scope.channel_display_configure_v2` | Profile permits CH1/CH2 only. Core owns baseline, readback, restoration, and verification; the plugin performs the controlled display write. |
| Multi-channel focus | time range, channel display, V/div | `scope.focus_configure_v2` | Accepts CH1/CH2 and timebase/vertical requests within the profile. It does not configure position, offset, coupling, termination, or bandwidth. |
| Analog waveform | REAL/LSBF, header, data, `DEF/MAX/DMAX` | `scope.fetch_waveform`, `scope.capture_waveform`, `scope.capture_waveforms` | Reads channels sequentially after one acquisition and adds no cross-channel hardware-synchronization guarantee. Long records use a separate timeout. |
| Waveform metadata | X/Y scaling, point count, quantization, values per sample | `scope.snapshot` | Header field four is values per sample interval, not a segment ID. |
| Timebase and history | range, position, zoom, history timestamp | `scope.snapshot`, `scope.history_timestamps`, `scope.focus_configure_v2` | History is K15-gated. Frame numbers do not substitute for timestamps, and timeout is not blindly retried or cleared. Zoom is not public. |
| Trigger | edge and other trigger families | `scope.snapshot` reads current basic edge state; capture reuses existing settings | The production descriptor declares no generic trigger-configuration capability. Driver-specific methods are not current WaveBench capabilities. |
| Measurement statistics | slot, source, actual, aggregates, buffer | `scope.measurement_statistics`, `scope.measurement_statistics_v2` | Reads caller-confirmed preconfigured slots. V2 permits slots 1–4 and no buffer; it never configures or resets slots. |
| Cursor | X/Y, delta, ratio, tracking | `scope.cursor_readout` | Reads caller-confirmed preconfigured cursor state; no production setup or positioning API. |
| Math and FFT | expression, metadata, FFT state/RBW | `scope.math_metadata`, `scope.fft_status`, `scope.fft_status_v2` | V2 returns only profile fields. It does not configure expressions or treat host DSP as instrument FFT capability. |
| Reference curve | source, state, scale, data, save/load | `scope.reference_metadata` | Reads an existing reference only; it does not update/save/load or fetch the payload. |
| Digital/MSO | D0-D15 state, threshold, deskew, data | `scope.digital_status`, `scope.digital_status_v2`, `scope.digital_waveform` | Checks B1 first. Waveform reads require a stopped record and compatible existing format and do not configure threshold, display, or transfer format. |
| Spectrum/spectrogram | spectrum data, axis, RBW, marker, history | Not public | Option-dependent analysis application requiring an independent model. |
| Search, mask, protocol decode/trigger | results, navigation, actions, bus configuration | Not public | Depend on options, input models, restoration, and result contracts; raw SCPI does not bypass them. |
| DVM and counter | source, type, result, state | Not public | No declared typed capability or option boundary exists. |
| Display and screenshot | display state, hardcopy | `scope.screenshot`, `scope.channel_display_configure_v2`, `scope.focus_configure_v2` | Screenshot returns PNG. Grid, palette, persistence, XY, virtual-screen, and printer setup are not public. |
| Instrument filesystem/export | `MMEMory`, instrument-side export | Not public | Host-side WaveBench artifacts are not instrument filesystem support. Paths and persistent writes are denied by default. |
| Setup save/restore | `SYSTem:SET`, state store/load | Not public | Setup blobs belong to acceptance restoration tooling, not the production configuration API. |
| Power analysis | quality, harmonics, ripple, switching, SOA, and related domains | Not public | Independent application area requiring probes, deskew, options, and result models. |
| Calibration, reset, global setup | calibration, `*RST`, preset, clock, language, network | Not public | Global/persistent mutation belongs only in separately authorized maintenance workflows. |

## Protocol and safety boundaries

- The driver uses supported abbreviated SCPI. The table indexes manual domains; the
  [driver](../src/wavebench_rohde_schwarz_rtm2000/driver.py) is the complete source for actual
  commands, avoiding a second manually maintained allowlist here.
- `DEF`, `MAX`, and `DMAX` are passed through to the device. Long waveform reads use the descriptor
  option's separate timeout, and failed reads are not replayed automatically.
- Capture reads coupling first. Core rejects potentially 50-ohm `AC`/`DC` by default; continuation
  requires explicit opt-in, while `ACL`/`DCL` are high-impedance paths.
- Channel-display and focus channels, numeric ranges, step budgets, and restoration order are defined
  by [profiles](../src/wavebench_rohde_schwarz_rtm2000/profiles.py).
- Host-side CSV/NPY/PNG artifacts, DSP analysis, and acceptance setup restoration are not RTM2000
  SCPI capabilities.

## Related sources

- [Production descriptor](../src/wavebench_rohde_schwarz_rtm2000/descriptor.py)
- [Descriptor profiles](../src/wavebench_rohde_schwarz_rtm2000/profiles.py)
- [Driver implementation](../src/wavebench_rohde_schwarz_rtm2000/driver.py)
- [Feature-coverage development roadmap](RTM2000_COVERAGE_MILESTONES_EN.md)
- [0.1.0–0.15.0 development and acceptance archive](archive/RTM2000_README_0.15_EN.md)
