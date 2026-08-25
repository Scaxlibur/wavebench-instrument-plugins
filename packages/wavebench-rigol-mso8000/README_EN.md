# WaveBench RIGOL MSO8000 Plugin (In Development)

This directory is the starting point for a WaveBench plugin for the RIGOL MSO8000 series, with the MSO8104 as the first target model. The MSO8104 is a 1 GHz, four-analog-channel mixed-signal oscilloscope; the programming guide also covers the MSO8064 and MSO8204.

## Current status

Development version `0.9.0` declares `scope.error_drain_v1`, `scope.fetch_waveform`, `scope.capture_waveform`, `scope.capture_waveforms`, `scope.acquisition_control`, `scope.channel_input_state_v2`, `scope.measurement_statistics_v2`, `scope.fft_status_v2`, `scope.acquisition_status_v2`, `scope.acquisition_run_state`, `scope.digital_status_v2`, `scope.snapshot_v2`, and `scope.cursor_readout_v2` through the bounded-binary and portability V2 contracts in the current WaveBench Core development branch. Bounded capture accepts only an already-stopped MAIN-timebase `DEF + BYTE` baseline. The descriptor limits a single capture to one binary query and a multi-channel capture to four, then Core restores and freshly verifies 13 acquisition, trigger, timebase, display/vertical, and transfer fields. After SINGLE, the driver reads back `SING`; terminal first `STOP` is a restricted control proof, while capture requires `WAIT` or `TD` followed by `STOP` as independent waveform-freshness evidence.

Hardware findings apply only to MSO8104 firmware `00.02.02`, LAN/PyVISA, and the controlled procedure. Bounded `DEF + BYTE` single- and multi-channel capture each returned `1,000` samples per channel with valid amplitude evidence under the `1 Vpp` safety limit. Both observed `WAIT → STOP`, then Core recovery polled `*OPC?` from `0` to `1` and freshly verified all 13 fields. A separate SINGLE-control acceptance observed `TD → STOP`. Every run ended with a new-session confirmation of source CH1/CH2 OFF, scope STOP, and high-impedance CH1/CH2 inputs. This does not establish other capture lengths, settings, transports, running-state MAX, or general measurement accuracy.

The restricted acquisition-control acceptance covers `start(normal)`→`stop`, plus post-arm `SING` readback followed by either terminal `STOP` or `WAIT`/`TD` progressing to `STOP`. Recovery `*OPC?` is used only to synchronize recovery writes; it is not acquisition-completion or waveform-freshness evidence.

Average capture remains undeclared. A controlled `capture_average_v2` probe used a stopped, high-impedance baseline and a 1 Vpp square signal. It wrote `:ACQuire:TYPE AVERages`, its legal `AVER` abbreviation, and PEAK/NORM controls, synchronizing each setting write before its type readback. Every readback remained `NORM`, and the subsequently consumed error record was `0,"No error"`. The current firmware/configuration therefore cannot enter average mode through this remote path. Even if that prerequisite changes, the manual does not bind trigger STOP, `*OPC?`, or preamble count to average completion. The production descriptor does not declare `scope.capture_average_v2`.

Current identity:

- Distribution: `wavebench-rigol-mso8000`
- Canonical driver ID: `rigol.mso8104`
- Kind: `scope`
- Target model: `MSO8104`
- Python: `>=3.11`
- WaveBench: `>=0.8.24,<0.9`

The required standard-waveform bounded API and portability V2 APIs are committed on the current core development branch but do not yet have an independent core release. Version `0.9.0` is therefore for development and controlled acceptance only, not a compatibility-wheel release claim.

## M8 offline release evidence

- All 370 MSO8104 package tests and repository-wide Ruff checks pass.
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

The descriptor declares `scope.screenshot_profile` and `scope.screenshot_v2` under a constrained contract. The current Core branch permits `8,388,608` bytes; the initial plugin profile narrows this to one `524,288`-byte response/operation, one binary query, `DEFINITE_BLOCK`, exact `LF` transport trailing, and `png/device/device`. The driver first reads `:SAVE:IMAGe:TYPE?` and requires `PNG`, then reads `:SAVE:IMAGe:DATA?`. It does not write TYPE, INVert, COLor, menu, or instrument files, and does not use `:DISPlay:DATA?`. The offline contract passes; actual payload, trailing bytes, PNG, session health, and empty error queue still require independent hardware acceptance. See [RFC-0003](doc/rfcs/0003-scope-screenshot-framing-and-menu-contract.md).

The descriptor still omits legacy `scope.digital_status` and `scope.digital_waveform`. The legacy status model requires fields that MSO8000 cannot query. The vendor manual does not define BYTE/WORD logic codes for D0-D15 waveform sources and leaves WORD byte order unclear. The plugin does not invent digital state from defaults or analog conversion.

`scope.autoscale` intentionally changes vertical, timebase, and trigger settings under the core operation contract and does not promise restoration. The driver first queries `:SYSTem:AUToscale?` and requires `check_errors=false`. For MSO8104, the legacy `wait_opc=true` parameter explicitly means a fixed `3 s` settle: after one `:AUToscale` write, the driver waits `3 s`, does not query `*OPC?`, and then treats the operation as complete. A write or settle-wait failure latches only the autoscale write domain until the session is reopened. A controlled CH1 `1 Vpp / 1 kHz` probe used public autoscale followed by bounded fetch, which returned 1,000 samples with amplitude evidence; final state was both source outputs OFF, scope STOP, and CH1/CH2 high impedance. The fixed duration is this plugin's operational-completion policy, not proof of the instrument's internal autoscale algorithm, visible effect, or restoration. `wait_opc=false` explicitly skips the wait and has no hardware-completion acceptance.

`scope.math_metadata` accepts only displayed MATH1-MATH4 slots in MAIN timebase mode. The driver saves all six waveform-transfer fields, switches to NORM before selecting the MATH source and BYTE format, reads only the preamble, and restores the previous state. It does not read waveform data. The recorded MATH1 call returned 1,000 points, finite axes, and eight-bit BYTE metadata with final six-field restoration verification. `values_per_sample` remains unknown; math content, axis semantics for other slots/operators, and FFT accuracy are not inferred.

`scope.cursor_readout` remains the compatibility route for an explicitly preconfigured global manual cursor at public cursor index `1`. The new `scope.cursor_readout_v2` uses global addressing with `cursor_index=None`, and reads manual `TIME/AMPL` A/B sources, seconds/hertz/degrees/percent or source/percent units, and A/B/delta values without moving or reconfiguring cursors. Tracking, XY, measurement mode, NONE, and LA amplitude remain fail closed. The current hardware cursor is `VBA`, so V2 correctly rejects before value queries; accuracy remains hardware-unverified.

`scope.measurement_statistics_v2` covers the manual's statistics items with normalized uppercase item tokens and explicit `CHAN1`-`CHAN4` or `MATH1`-`MATH4` sources. `D0`-`D15` are limited to the documented period, frequency, width, duty, delay, and phase items. Delay and phase items require two sources; every other item requires one. The driver reads only CURRENT, AVERages, DEViation, MINimum, MAXimum, and CNT; it never writes statistics configuration, reset, or display state. Controlled hardware reads proved all six numeric responses and `CNT=1000` for `VPP,CHAN1` and `VPP,CHAN2`. Existing device history was not cleared, so average, standard deviation, minimum, and maximum are not evidence of signal accuracy or statistics-window semantics. The legacy `scope.measurement_statistics` capability remains undeclared.

`scope.fft_status_v2` accepts only MATH1-MATH4 FFT state already configured at the front panel. The driver queries `OPERator?` and requires `FFT`, then reads the FFT source, window, vertical unit, start frequency, and stop frequency; every step is a text query. The manual provides no provable query for `average_complete`, RBW, or FFT sample rate, so they are always listed in `unavailable_fields` and are never inferred from global acquisition sample rate, frequency range, or waveform points. Controlled MATH1 hardware reads confirmed `FFT + CHAN1 + HANN + VRMS + 0–1 MHz`; source CH1/CH2 were OFF, `consistent`, and `healthy` before and after. This is not FFT amplitude, frequency, or frequency-axis accuracy evidence.

`scope.acquisition_status_v2` always reads `:ACQuire:TYPE?`, `:ACQuire:SRATe?`, and `:ACQuire:MDEPth?`; it reads `:ACQuire:AVERages?` only when type is `AVER`. The average partition is explicitly not applicable outside AVER mode; in AVER mode it reports only the configured count, while `average.complete` remains unavailable. Run state and segmented status are outside the profile. The driver does not send `:TRIGger:STATus?`, `*OPC?`, `*STB?`, or `*ESR?`, and never infers completion from STOP. Controlled hardware returned `NORM + 500 kSa/s + 10 kpts`; the later average-mode write probe also read back `NORM` throughout, so the AVER branch has no reachable-hardware evidence. Source CH1/CH2 were OFF, `consistent`, and `healthy` before and after. Legacy `scope.acquisition_status` and average capture remain undeclared.

`scope.acquisition_run_state` reads only `:TRIGger:STATus?`: STOP maps to stopped, WAIT maps to waiting, RUN and the recorded AUTO state map to acquiring, and TD normally remains unknown. Only in a just-read-back SINGLE transaction can TD be represented as a nonterminal arming observation, and it must be followed by STOP to form a state-transition proof. `scope.acquisition_control` is declared for `start(normal)`, `stop`, and restricted SINGLE completion. Bounded capture is independent from the terminal control proof: it rejects first STOP, requires `WAIT`/`TD → STOP`, and uses Core-owned 13-field recovery/fresh verification. Running-state MAX and capture lengths, timebases, channel sets, and transports outside the controlled procedure remain unverified.

`scope.digital_status_v2` accepts only D0-D15. Each call first queries the LA module bit; an absent module returns only `shared.module_present=false` and sends no `:LA:*?` query. With LA present, the driver uses six text queries for the per-channel display and label, the shared threshold of the owning POD, global timing calibration, and display size. `position_div` remains unavailable because the manual's query form is self-contradictory. `label_enabled`, activity, technology, and hysteresis have no provable query and are never replaced by defaults or UI active-channel state. Controlled D0 and D8 reads confirmed display, labels, their POD boundaries and `1.4 V` thresholds, plus `0 s` timing calibration and `MEDIUM` size; source CH1/CH2 were OFF, `consistent`, and `healthy` before and after. This is not evidence of logic-probe behavior, electrical threshold accuracy, logic activity, or digital-waveform encoding.

`scope.snapshot_v2` accepts only CH1-CH4 requests, but its current profile reads only current identity and licensed-option state: one `*IDN?` followed by the 13 manual-defined `:SYSTem:OPTion:STATus? <type>` queries. An empty options tuple is returned only after all 13 queries explicitly prove no installed option; no identity field is filled from the descriptor, cache, or model constants. The 55 health, channel, timebase, probe, waveform, and trigger fields are unavailable in stable order. Controlled hardware completed all 14 queries; source CH1/CH2 were OFF, `consistent`, and `healthy` before and after. The operation does not read status registers, the error queue, trigger state, waveform data, or binary data, and is not evidence for any unread partition or its accuracy.

`scope.error_drain_v1` sends every `:SYSTem:ERRor?` read through Core with explicit `ReplayPolicy.NO_REPLAY` and strictly parses `<integer>,"<message>"`. `0,"No error"` is the only hardware-observed terminator; nonzero records, malformed responses, and queue overflow all fail closed. With `scope.check_errors=true`, Core runs a bounded drain before and after bounded fetch/capture and reconciles the actual query count. The controlled public single-channel capture completed both empty drains, returned 1000 samples, and restored the safe final state. Nonempty-record and overflow paths currently have offline fault-injection evidence only. Legacy `scope.errors` remains undeclared, and old paths such as autoscale still require `check_errors=false`.

The bounded `scope.fetch_waveform` path supports `DEF`, stopped-state `MAX`, and stopped-state `DMAX`. It uses core `query_binary()` rather than legacy `query_bin_block()`; exact `LF` trailing, a `250,000`-byte per-response limit, a `4,000,000`-byte operation limit, up to 16 binary queries, and no replay are descriptor-owned. Before any MAX/DMAX transfer setup, the driver requires stopped state. Fetch evidence does not extend to running-state MAX or other ranges, timebases, memory depths, and probe conditions; bounded capture has separate acceptance above.

The driver retains the `250,000`-point block, `4,000,000`-point total, and 16-query long-record limits. Stopped-state MAX/DMAX fetch and bounded single/multi-channel capture each have limited hardware evidence. Running-state MAX and capture beyond the recorded point modes, timebases, channel sets, and transport remain unverified.
