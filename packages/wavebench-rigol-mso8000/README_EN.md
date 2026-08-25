# WaveBench RIGOL MSO8000 Plugin (In Development)

This directory is the starting point for a WaveBench plugin for the RIGOL MSO8000 series, with the MSO8104 as the first target model. The MSO8104 is a 1 GHz, four-analog-channel mixed-signal oscilloscope; the programming guide also covers the MSO8064 and MSO8204.

## Current status

Development version `0.9.0` retains the controlled MSO8104 identity and high-impedance CH1/CH2 evidence and declares `scope.fetch_waveform`, `scope.channel_input_state_v2`, `scope.measurement_statistics_v2`, `scope.fft_status_v2`, `scope.acquisition_status_v2`, `scope.digital_status_v2`, and `scope.cursor_readout_v2` through the bounded-binary and portability V2 contracts in the current WaveBench core development branch. The waveform entry currently accepts only `DEF`: it declares exact `LF` trailing, a `1,000`-byte response and operation limit, and one binary query; core owns recovery and fresh verification. Input-state V2 preserves original coupling, termination, and impedance. Statistics V2 accepts only explicit `item + sources`, issues six pure reads for a complete result, and rejects `include_buffer=True`. FFT V2 first proves that the math slot is `FFT`, then reads source, window, vertical unit, and frequency endpoints. Acquisition-status V2 reads acquisition type, sample rate, and memory depth, and reads the configured average count only in AVER mode. Digital-status V2 first proves the LA module is present, then reads per-channel display and label state, POD thresholds, and shared display state. Cursor V2 only reads a preconfigured global manual `TIME/AMPL` cursor. `scope.capture_waveform` and `scope.capture_waveforms` remain paused; see [RFC-0008](doc/rfcs/0008-bounded-waveform-block-trailing-contract.md).

Hardware findings apply only to MSO8104 firmware `00.02.02`, LAN/PyVISA, and the controlled procedure. Under the `DEF + LF` profile, CH1 returned `1.05713 Vpp / 1000 Hz` and CH2 returned `1.0705 Vpp / 999.167 Hz`. `scope.measurement_statistics_v2` read all six aggregate fields for both `VPP,CHAN1` and `VPP,CHAN2`, with `CNT=1000`; front-panel-configured MATH1 FFT returned CH1, HANN, VRMS, and `0–1 MHz`; current acquisition status returned NORM, `500 kSa/s`, and `10 kpts`; D0/D8 digital status confirmed the corresponding POD, `1.4 V` threshold, `0 s` timing calibration, and `MEDIUM` size. Separate `1 kHz / 1 Vpp / 0 V` source runs and fresh snapshots confirmed both outputs OFF after each read. This establishes conversion, summary, statistics-response, FFT-status-response, static-acquisition-status-response, static-digital-status-response, and five-field-recovery behavior only for the recorded condition; it is not general measurement accuracy, statistics-window semantics, FFT accuracy, average completion, logic-probe or logic-activity behavior, probe calibration, MAX/DMAX, or capture evidence.

Current identity:

- Distribution: `wavebench-rigol-mso8000`
- Canonical driver ID: `rigol.mso8104`
- Kind: `scope`
- Target model: `MSO8104`
- Python: `>=3.11`
- WaveBench: `>=0.8.24,<0.9`

The required standard-waveform bounded API and portability V2 APIs are committed on the current core development branch but do not yet have an independent core release. Version `0.9.0` is therefore for development and controlled acceptance only, not a compatibility-wheel release claim.

## M8 offline release evidence

- All 268 MSO8104 package tests and repository-wide Ruff checks pass.
- In a disposable sibling WaveBench-core layout, 715 root tests pass and two SP3000A private-hardware-evidence tests skip as expected.
- Package checks pass for both the source directory and the real wheel in the current WaveBench `0.8.24` development environment.
- The wheel/sdist contracts cover the single instrument entry point, WaveBench runtime dependency, MIT license, and public content; vendor-local material is absent.
- A disposable virtual environment passes installation, zero-I/O descriptor discovery, uninstall, and canonical-ID fallback.
- Local links resolve in all 61 tracked Markdown files.

This evidence covers offline contracts and distribution integrity only. Model, firmware, transport, throughput, restoration, and measurement accuracy remain hardware-unverified.

## Directory layout

- `doc/vendor-local/`: local vendor manuals. Keep the original PDF and the converted Markdown here; all files except its README are ignored and excluded from distributions.
- `src/wavebench_rigol_mso8000/`: descriptor, driver, and strict parsers.
- `tests/`: FakeTransport unit tests; default tests must not connect to hardware.
- `pyproject.toml`: distribution metadata, WaveBench version range, and the single entry point.
- `doc/`: public coverage matrices and acceptance notes. Keep vendor source material out of public documentation.

## Design documents

- [MSO8104 coverage milestones](doc/MSO8104_COVERAGE_MILESTONES_EN.md)
- [MSO8104 programming-guide coverage matrix](doc/MSO8104_COVERAGE_MATRIX_EN.md)
- [MSO8104 controlled hardware acceptance](doc/MSO8104_HARDWARE_ACCEPTANCE_EN.md)

## Safety boundary

Descriptor import must not open a transport, scan ports, send SCPI, or create files. Never commit real resources, serial numbers, credentials, captures, screenshots, or command logs. Do not blindly retry instrument writes or acquisition triggers. When the core lacks a required safety interface, add an RFC and skip the capability instead of adding a raw SCPI escape hatch.

The descriptor accepts `tcpip`, `usb`, and `gpib` resource prefixes as a manual-backed, offline routing contract. This is not hardware connection evidence.

The descriptor does not declare `scope.screenshot`. The manual does not specify TMC block framing for `:DISPlay:DATA?`, while `:SAVE:IMAGe:DATA?` cannot prove the core's `include_menu=False` contract. [RFC-0003](doc/rfcs/0003-scope-screenshot-framing-and-menu-contract.md) records both gaps. The plugin does not guess framing, ignore request parameters, or create instrument files.

The descriptor still omits legacy `scope.digital_status` and `scope.digital_waveform`. The legacy status model requires fields that MSO8000 cannot query. The vendor manual does not define BYTE/WORD logic codes for D0-D15 waveform sources and leaves WORD byte order unclear. The plugin does not invent digital state from defaults or analog conversion.

`scope.autoscale` intentionally changes vertical, timebase, and trigger settings under the core operation contract. The driver first queries `:SYSTem:AUToscale?`, requires `check_errors=false`, and latches only the autoscale write domain when the command or OPC completion is uncertain. Its command sequence and fault handling are offline-tested; autoscale effect remains hardware-unverified.

`scope.math_metadata` accepts only displayed MATH1-MATH4 slots in MAIN timebase mode. The driver saves all six waveform-transfer fields, switches to NORM before selecting the MATH source and BYTE format, reads only the preamble, and restores the previous state. It does not read waveform data. `values_per_sample` remains unknown and Y resolution is the documented eight-bit BYTE transfer width. Math content, FFT accuracy, and device restoration remain hardware-unverified.

`scope.cursor_readout` remains the compatibility route for an explicitly preconfigured global manual cursor at public cursor index `1`. The new `scope.cursor_readout_v2` uses global addressing with `cursor_index=None`, and reads manual `TIME/AMPL` A/B sources, seconds/hertz/degrees/percent or source/percent units, and A/B/delta values without moving or reconfiguring cursors. Tracking, XY, measurement mode, NONE, and LA amplitude remain fail closed. The current hardware cursor is `VBA`, so V2 correctly rejects before value queries; accuracy remains hardware-unverified.

`scope.measurement_statistics_v2` covers the manual's statistics items with normalized uppercase item tokens and explicit `CHAN1`-`CHAN4` or `MATH1`-`MATH4` sources. `D0`-`D15` are limited to the documented period, frequency, width, duty, delay, and phase items. Delay and phase items require two sources; every other item requires one. The driver reads only CURRENT, AVERages, DEViation, MINimum, MAXimum, and CNT; it never writes statistics configuration, reset, or display state. Controlled hardware reads proved all six numeric responses and `CNT=1000` for `VPP,CHAN1` and `VPP,CHAN2`. Existing device history was not cleared, so average, standard deviation, minimum, and maximum are not evidence of signal accuracy or statistics-window semantics. The legacy `scope.measurement_statistics` capability remains undeclared.

`scope.fft_status_v2` accepts only MATH1-MATH4 FFT state already configured at the front panel. The driver queries `OPERator?` and requires `FFT`, then reads the FFT source, window, vertical unit, start frequency, and stop frequency; every step is a text query. The manual provides no provable query for `average_complete`, RBW, or FFT sample rate, so they are always listed in `unavailable_fields` and are never inferred from global acquisition sample rate, frequency range, or waveform points. Controlled MATH1 hardware reads confirmed `FFT + CHAN1 + HANN + VRMS + 0–1 MHz`; source CH1/CH2 were OFF, `consistent`, and `healthy` before and after. This is not FFT amplitude, frequency, or frequency-axis accuracy evidence.

`scope.acquisition_status_v2` always reads `:ACQuire:TYPE?`, `:ACQuire:SRATe?`, and `:ACQuire:MDEPth?`; it reads `:ACQuire:AVERages?` only when type is `AVER`. The average partition is explicitly not applicable outside AVER mode; in AVER mode it reports only the configured count, while `average.complete` remains unavailable. Run state and segmented status are outside the profile. The driver does not send `:TRIGger:STATus?`, `*OPC?`, `*STB?`, or `*ESR?`, and never infers completion from STOP. Controlled hardware returned `NORM + 500 kSa/s + 10 kpts`; source CH1/CH2 were OFF, `consistent`, and `healthy` before and after. Legacy `scope.acquisition_status`, all acquisition control, average capture, and single/multi-channel capture remain undeclared.

`scope.digital_status_v2` accepts only D0-D15. Each call first queries the LA module bit; an absent module returns only `shared.module_present=false` and sends no `:LA:*?` query. With LA present, the driver uses six text queries for the per-channel display and label, the shared threshold of the owning POD, global timing calibration, and display size. `position_div` remains unavailable because the manual's query form is self-contradictory. `label_enabled`, activity, technology, and hysteresis have no provable query and are never replaced by defaults or UI active-channel state. Controlled D0 and D8 reads confirmed display, labels, their POD boundaries and `1.4 V` thresholds, plus `0 s` timing calibration and `MEDIUM` size; source CH1/CH2 were OFF, `consistent`, and `healthy` before and after. This is not evidence of logic-probe behavior, electrical threshold accuracy, logic activity, or digital-waveform encoding.

`channel_coupling()` combines channel coupling and input impedance. `AC/DC + OMEG` maps to the core high-impedance tokens `ACL/DCL`, while `AC/DC + FIFT` maps to the low-impedance tokens `AC/DC`. The new `scope.channel_input_state_v2` does not use those compatibility tokens: it returns `ac/dc/gnd`, `high_z/50_ohm`, and the proven impedance independently. Hardware CH1/CH2 both returned `dc + high_z + 1 MΩ`. The core rejects 50 ohms, `GND`, and unknown states by default. The plugin does not declare `scope.errors` because `:SYSTem:ERRor?` consumes an entry while ordinary core text queries may replay. Future waveform service calls must explicitly set `scope.check_errors=false` until [RFC-0001](doc/rfcs/0001-nonreplayable-text-query.md) is implemented.

The bounded `scope.fetch_waveform` path accepts only `DEF`. It uses core `query_binary()` rather than legacy `query_bin_block()`; the descriptor profile fixes `LF` trailing, the `1,000`-byte bound, and no replay. Under the recorded `1 kHz / 1 Vpp / 0 V` source condition, CH1 returned `1.05713 Vpp / 1000 Hz` and CH2 returned `1.0705 Vpp / 999.167 Hz`; each read returned 1000 samples and completed five-field transfer-state restoration and fresh verification. This evidence does not extend to MAX, DMAX, single or multi-channel capture, or other ranges, timebases, and probe conditions.

The offline driver still retains the `250,000`-point block and `4,000,000`-point total limits for long records. MAX, DMAX, single capture, and multi-channel capture each require their own bounded profile and acquisition-recovery evidence, and remain unavailable.
