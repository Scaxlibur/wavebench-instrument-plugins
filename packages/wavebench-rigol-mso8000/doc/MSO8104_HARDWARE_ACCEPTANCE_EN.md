# MSO8104 Controlled Hardware Acceptance

[中文](MSO8104_HARDWARE_ACCEPTANCE.md)

Acceptance dates: 2026-08-24 through 2026-08-25

## Scope

This record covers the first controlled check of RIGOL MSO8104 identity, input safety, the waveform-binary path, measurement-statistics V2, FFT-status V2, acquisition-status V2, acquisition run-state, digital-status V2, and Snapshot V2. It does not record real resource addresses, serial numbers, raw waveforms, screenshots, or complete command logs.

Devices and runtime:

- scope: RIGOL MSO8104, firmware `00.02.02`;
- source: Siglent SDG2122X, firmware `2.01.01.39R7T2`;
- core: WaveBench `0.8.24`;
- transport: LAN/PyVISA with zero read retries.

SDG CH1 was connected to MSO CH1 and SDG CH2 to MSO CH2. The reviewed source profile was Sine, `1 kHz`, `1 Vpp`, and `0 V` offset. Local safety configuration further constrained `max_source_vpp = 1.0` and port voltage to `-0.6 V` through `0.6 V`.

## Safety sequence and result

1. A read-only Source V2 snapshot found both channels at Sine, `1 kHz`, `1 Vpp`, `0 V`, High-Z display load, harmonic OFF, and output OFF.
2. Read-only scope status returned CH1=`DCL` and CH2=`ACL`; both are WaveBench high-impedance safety tokens.
3. Source V2 OFF was requested separately for CH1 and CH2. A fresh read-only snapshot independently confirmed both OFF, `consistent`, and `healthy`.
4. CH1 and CH2 were each enabled only briefly in separate runs. After every waveform transaction, the outer cleanup requested the enabled channel OFF and used a fresh read-only snapshot to confirm CH1 and CH2 were both OFF.

Final verification was CH1 OFF, CH2 OFF, snapshot `consistent`, and session `healthy`. This run did not write scope input impedance, timebase, trigger, or autoscale settings.

## Hardware evidence obtained

- `scope.idn` strictly identified RIGOL MSO8104;
- `scope.channel_coupling` returned CH1=`DCL` and CH2=`ACL`;
- `scope.channel_input_state_v2` returned `dc + high_z + 1 MΩ` for both CH1 and CH2;
- `scope.measurement_statistics_v2` returned six finite aggregate values with `CNT=1000` for both `VPP,CHAN1` and `VPP,CHAN2`;
- `scope.fft_status_v2` returned `FFT + CHAN1 + HANN + VRMS + 0–1 MHz` for front-panel-configured MATH1;
- `scope.acquisition_status_v2` returned `NORM + 500 kSa/s + 10 kpts`, with average not applicable;
- `scope.acquisition_run_state` conservatively reported current AUTO as acquiring; with both sources OFF and high-impedance inputs, STOP→NORMAL/RUN→STOP confirmed stopped, waiting, stopped;
- `scope.digital_status_v2` returned display, label, POD range and `1.4 V` threshold, plus shared `0 s` timing calibration and `MEDIUM` size for D0 and D8;
- `scope.snapshot_v2` read identity and 13 licensed-option states in one call, with the other 55 fields explicitly unavailable;
- Source V2 dual-channel snapshot, OFF requests, and independent OFF readback completed;
- core preflight confirmed the safety limit, High-Z display load, and no active cross-channel relation before enable.

These results apply only to the stated model, firmware, LAN/PyVISA transport, and controlled procedure.

## Limited waveform acceptance

The earlier core `0.8.24` legacy binary path timed out after about `5 s` at `:WAVeform:DATA?`. Synchronization was therefore `unproven`, and the scope session was correctly marked `poisoned` under the fail-closed rule. That historical result is not payload, frequency, Vpp, or restoration evidence.

The current core worktree implements the standard waveform bounded-binary contract. An empty trailing profile safely rejects the extra post-payload byte with `binary_transport_trailing_error`; with exact `LF` trailing, core restores and freshly verifies the five `source`, `mode`, `format`, `points`, and `window` fields.

After confirming SDG CH1 to MSO CH1 and SDG CH2 to MSO CH2, separate short source runs used the `1 kHz / 1 Vpp / 0 V` profile:

- CH1 returned `1000` samples from `-2.5 ms` to `2.495 ms` at `5 µs` spacing, with a `1.05713 Vpp / 1000 Hz` summary;
- CH2 returned `1000` samples from `-2.5 ms` to `2.495 ms` at `5 µs` spacing, with a `1.0705 Vpp / 999.167 Hz` summary.

After each read, EXIT cleanup disabled the enabled source channel and a fresh Source V2 snapshot confirmed CH1 and CH2 OFF, `consistent`, and `healthy`.

## Restricted stopped-state MAX/DMAX acceptance

Separate processes first used public read-only APIs to confirm source CH1/CH2 OFF, `consistent`, and `healthy`, scope CH1/CH2 as `dc + high_z + 1 MΩ`, and stopped run-state. Scope fetch then used read-write access while the source outputs remained OFF. Every fetch again requested both outputs OFF and verified them. No RUN, STOP, SINGLE, autoscale, timebase, vertical, trigger, or input-setting write was sent.

Bounded `scope.fetch_waveform` used `LF` trailing, no replay, a `250,000`-byte per-response limit, a `4,000,000`-byte operation limit, and at most 16 binary queries. MAX/DMAX both required observed STOP before temporary waveform-transfer setup; the driver read current memory depth and set `:WAVeform:POINts` to the minimum of memory depth, the runtime total-point limit, and 16 chunks. The current hardware memory depth was `10,000 pts`; this run set runtime limits to `20,000 pts` total and `2,500 pts` per chunk.

- CH1: DMAX returned `10,000` samples; stopped-state MAX returned `10,000` samples.
- CH2: DMAX returned `10,000` samples; stopped-state MAX returned `10,000` samples.

After every operation, core restored and freshly verified the five transfer fields `source`, `mode`, `format`, `points`, and `window`; a new scope session verified stopped state and a fresh Source V2 snapshot verified CH1/CH2 OFF, `consistent`, and `healthy`. This establishes only stopped-state MAX/DMAX fetch for the recorded model, firmware, LAN/PyVISA, `10 kpts` memory depth, and bounded chunk procedure. It is not running-state MAX, other memory depths, throughput, timeout, waveform-accuracy, or capture-semantics evidence.

## Portability V2 read-only follow-up

With both source outputs OFF, `scope.channel_input_state_v2` successfully read independent coupling, termination, and impedance for CH1 and CH2. This step did not write input settings.

`scope.cursor_readout_v2` accepts only a preconfigured global manual `TIME/AMPL` cursor and never moves or reconfigures it. The device returned `VBA`; the driver correctly rejected before any value query, so this is not cursor-readout acceptance. The final source snapshot again confirmed both outputs OFF, `consistent`, and `healthy`.

`scope.measurement_statistics_v2` uses an `item + sources` selector and does not access the legacy slot route. After separately enabling CH1 and CH2 for brief runs, it issued only CURRENT, AVERages, DEViation, MINimum, MAXimum, and CNT queries for `VPP,CHAN1` and `VPP,CHAN2`. It sent no statistics configuration, reset, display, or scope write.

- `VPP,CHAN1`: actual `1.0787 V`, average `0.099304 V`, standard deviation `0.088314 V`, minimum `0.064723 V`, maximum `1.1003 V`, and count `1000`;
- `VPP,CHAN2`: actual `1.0705 V`, average `0.095994 V`, standard deviation `0.083057 V`, minimum `0.06554 V`, maximum `1.1142 V`, and count `1000`.

This proves the six response fields and numeric/integer count parsing for the recorded condition. Statistics history is device-owned and was neither reset nor configured by the driver; average, standard deviation, minimum, and maximum are therefore not evidence of statistics-window semantics, signal accuracy, or cross-condition measurement behavior. EXIT cleanup disabled the enabled source channel after each run, and the final snapshot confirmed both CH1 and CH2 OFF, `consistent`, and `healthy`.

`scope.fft_status_v2` used MATH1 already configured at the front panel and did not create, modify, or restore FFT through SCPI. It first confirmed both source outputs OFF, `consistent`, and `healthy`, and CH1 as `dc + high_z + 1 MΩ`; it then read only operator, source, window, vertical unit, start frequency, and stop frequency. The response was MATH1 operator `FFT`, source `CHAN1`, window `HANN`, vertical unit `VRMS`, and a `0 Hz` to `1 MHz` frequency range. This run performed no source or scope write, waveform transfer, binary read, error-queue read, or FFT-state restoration. A separate Source V2 snapshot afterwards again confirmed both CH1 and CH2 OFF, `consistent`, and `healthy`.

This proves FFT-status response and the V2 unavailable-field boundary only for the recorded model, firmware, transport, and front-panel configuration. `average_complete`, RBW, and FFT sample rate remain unavailable; this is not FFT amplitude, frequency, frequency-axis, or window-effect accuracy evidence.

`scope.acquisition_status_v2` read only `:ACQuire:TYPE?`, `:ACQuire:SRATe?`, and `:ACQuire:MDEPth?`. The current type was NORM, so it did not read `:ACQuire:AVERages?`. The response was acquisition type `NORM`, sample rate `500000 Sa/s`, and memory depth `10000 pts`; the average partition was not applicable, while run state and segmented status were unavailable. This step sent no SINGLE, RUN, STOP, acquisition setter, trigger-status, OPC, status-register, or error-queue query, so it did not change acquisition or trigger state. Both source outputs were OFF, `consistent`, and `healthy` before and after, and CH1 was `dc + high_z + 1 MΩ`.

This evidence covers only static NORM acquisition status for the recorded condition. AVER configured count, average completion, run state, segmented status, and every capture-completion condition remain hardware-unverified; trigger STOP must not imply average complete.

`scope.acquisition_run_state` issued only `:TRIGger:STATus?`. The initial AUTO state was conservatively mapped to acquiring; with both source outputs OFF and CH1/CH2 at `dc + high_z + 1 MΩ`, managed STOP returned stopped, NORMAL/RUN returned waiting, and final STOP returned stopped. No waveform, OPC, status-register, or error-queue read occurred, and no timebase, vertical, or acquisition-type setting changed.

Core binds start, stop, and completion-style SINGLE into the one `scope.acquisition_control` capability. A public-API `start(normal)` then `stop` returned an observable active/stopped loop with both sources OFF and high-impedance inputs. A no-signal SINGLE probe failed closed as intended, and Core cleanup plus fresh verification were hardware-confirmed; that proves failure recovery only, not acquisition completion. A limited-signal CH1 SINGLE probe also produced no success evidence: a live safety preflight confirmed sine, fixed frequency, High-Z display load, amplitude no greater than `1 Vpp`, and a `±0.6 V` port envelope, but the first observable state was still STOP, without a nonterminal-to-STOP transition. Two controlled source-off `*OPC?` probes both returned `1`, while subsequent independent run-state reads were still waiting; OPC therefore proves command processing only, not a trigger, completion, or fresh waveform. The historical VXI-11 EOF and blocked-session arm/readback outcomes likewise are not completion evidence. Each attempt was followed by an independent new-session confirmation of source CH1/CH2 OFF, `consistent`, `healthy`, stopped scope, and high-impedance CH1/CH2 inputs. Because SINGLE completion remains hardware-unproven, the descriptor does not declare `scope.acquisition_control`, and this does not enable capture.

`scope.digital_status_v2` first confirmed both source outputs OFF, `consistent`, and `healthy`, and both CH1/CH2 as `dc + high_z + 1 MΩ`. Each D0 and D8 call first queried the LA module bit. With the module present, it read only per-channel display, label, the threshold of the owning POD, global timing calibration, and display size: six text queries total. D0 returned displayed, label `D0`, POD1 (D0-D7), `1.4 V`, `0 s`, and `MEDIUM`; D8 returned displayed, label `D8`, POD2 (D8-D15), and the same shared values. `position_div`, `label_enabled`, activity, technology, and hysteresis were all unavailable by contract. No `:LA:*` setter, waveform/binary read, acquisition/trigger, OPC, status-register, or error-queue query was sent, and no source or scope write occurred. A separate Source V2 snapshot afterwards again confirmed CH1 and CH2 OFF, `consistent`, and `healthy`.

This evidence covers only the recorded model, firmware, transport, and D0/D8 static-status responses. It does not prove logic-probe attachment, electrical threshold accuracy, logic activity, position semantics, label-display enable, or digital-waveform encoding.

`scope.snapshot_v2` first confirmed both source outputs OFF, `consistent`, and `healthy`, and both CH1/CH2 as `dc + high_z + 1 MΩ`. The public core `ScopeService.snapshot_v2()` call used a pure-read profile of one `*IDN?` plus the 13 manual-defined `:SYSTem:OPTion:STATus? <type>` queries, for 14 text queries total. Identity and options both originated in that call; the 13 responses explicitly established the current installed set, so an empty options tuple would never come from a default or cache. The 55 health, channel, timebase, probe, waveform, and trigger fields were unavailable in stable order. No `*STB?`, `*ESR?`, error-queue, trigger, waveform, or binary read was sent, and no source or scope write occurred. A separate Source V2 snapshot afterwards again confirmed CH1 and CH2 OFF, `consistent`, and `healthy`.

This evidence covers only identity and licensed-option status for the recorded model, firmware, and transport. It does not prove the unread health, channel, timebase, probe, waveform, or trigger partitions, or their accuracy.

## Acceptance boundary and next conditions

This record covers only the current-screen `DEF + LF` 1000-point path and the recorded stopped-state `MAX/DMAX + LF` 10000-point path, each for the stated model, firmware, transport, memory depth, and procedure. It is not general X/Y-conversion or measurement-accuracy evidence across ranges, timebases, or probe conditions.

`scope.acquisition_control`, running-state MAX, completion-style `SINGLE`, `scope.capture_waveform`, and `scope.capture_waveforms` have no releasable hardware acceptance from this work and remain default denied. `*OPC?` is ruled out as a completion candidate. Advancing them first requires a SINGLE nonterminal-to-STOP transition, record identity, or acquisition-count completion proof, followed by the corresponding acquisition-state recovery and separate low-voltage hardware procedure; each step must still begin with both source outputs OFF. RFC-0009 proposes only an arm operation that makes no completion claim.
