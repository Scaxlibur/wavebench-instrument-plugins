# MSO8104 Coverage Milestones

[中文](MSO8104_COVERAGE_MILESTONES.md)

## Goal and evidence boundary

This plan divides the RIGOL MSO8000 programming surface into risk-ordered milestones M0 through M8. Initial development was offline-only. Later controlled hardware work uses only high-impedance inputs, a `1 kHz / 1 Vpp / 0 V` source profile, and independent source-OFF checks. Hardware findings apply only to the recorded model, firmware, transport, and procedure.

The first canonical target is `rigol.mso8104` in the `wavebench-rigol-mso8000` distribution. Shared documentation does not make MSO8064 or MSO8204 validated models.

## Common rules

- Use only public WaveBench Instrument API V2 descriptors, protocols, models, and transport methods.
- When the core lacks a safe interface, write an RFC and skip the capability instead of adding raw SCPI or a private escape hatch.
- Declare only capabilities backed by implementation and offline contract tests.
- Serialize all transport I/O with one reentrant lock.
- Reject non-finite values, inexact integers, unknown enums, ambiguous writes, and uncertain restoration.
- Do not declare `scope.errors` until the core can express a non-replayable consuming text query.
- Let the core transport decode IEEE/TMC blocks; the driver validates payloads.
- Exclude vendor material and laboratory data from wheels and sdists.

## Permanent default-deny surface

The base plugin does not expose raw SCPI, reset or setup slots, option installation, network reconfiguration, instrument file operations, calibration or self-test, a general 50-ohm setter, unrestricted trigger configuration, protocol setup, or AWG output.

## Status

| Milestone | Status | Scope |
| --- | --- | --- |
| M0 | Complete | Manual audit, core contract, evidence rules, default-deny boundary, distribution isolation |
| M1 | Offline complete | Minimal identity plugin and lifecycle |
| M2 | Offline complete | Input-termination safety; consuming-query RFC |
| M3 | Hardware complete for limited `DEF` known signal | Current-screen NORM/BYTE `DEF` waveform through the RFC-0008 bounded-binary contract |
| M4 | Default deny | Single, multi-channel, and bounded MAX/DMAX acquisition; acquisition recovery and hardware evidence remain incomplete |
| M5 | RFC and skip | PNG framing and menu visibility lack a provable core contract |
| M6 | Controlled digital-status V2 development | Legacy digital status and digital waveform remain skipped; V2 static state has core and hardware evidence |
| M7 | Controlled development | Autoscale, math metadata, restricted cursor, and portability V2 input/statistics/FFT/acquisition-status/digital-status/snapshot read subsets; all other candidates explicitly skipped |
| M8 | Offline complete | Documentation, full offline verification, and package audit |

## Milestone exits

- **M0:** Freeze `rigol.mso8104`, `pyvisa`, switchable termination, coupling-plus-impedance normalization, point-mode mapping, block ownership, RFC topics, and package exclusions.
- **M1:** Provide zero-I/O descriptor import, exactly one core transport, strict MSO8104 identity, idempotent close, and wheel/sdist lifecycle tests.
- **M2:** Provide `scope.channel_coupling` through combined coupling and impedance reads. Keep `scope.errors` disabled and document `scope.check_errors=false` until the RFC is resolved.
- **M3:** The current core worktree implements the RFC-0008 bounded standard-waveform executor. The plugin exposes only `DEF` with `LF` trailing, a `1,000`-byte bound, one binary query, and core-owned recovery. Under the recorded source condition, hardware returned CH1 `1.05713 Vpp / 1000 Hz` and CH2 `1.0705 Vpp / 999.167 Hz`; this is limited known-signal acceptance, not MAX/DMAX or capture evidence.
- **M4:** Capture remains paused. It requires complete run-state, acquisition, trigger, timebase, channel-display, and channel-vertical recovery evidence in addition to bounded binary transport.
- **M5:** RFC and skip. `:DISPlay:DATA?` has no documented IEEE/TMC block framing, while `:SAVE:IMAGe:DATA?` is a documented block but cannot prove the core's `include_menu=False` contract. [RFC-0003](rfcs/0003-scope-screenshot-framing-and-menu-contract.md) proposes a non-replayed raw-byte query and an explicit unknown-menu result. Do not declare `scope.screenshot`, guess framing, ignore parameters, or create instrument files.
- **M6:** Legacy `scope.digital_status` remains skipped because activity, technology, hysteresis, label visibility, and other mandatory fields cannot be queried. Core R1 now implements the portable V2 model from [RFC-0004](rfcs/0004-portable-scope-digital-status.md). The plugin declares only D0-D15 static V2 state: module presence, per-channel display/label, POD threshold, timing calibration, and size. D0/D8 hardware reads verified both POD boundaries; position, label-enabled, activity, technology, and hysteresis remain unavailable. `scope.digital_waveform` is still skipped because D0-D15 BYTE/WORD logic codes and WORD byte order are undefined. Do not infer any digital field from analog conversion or FakeTransport fixtures.
- **M7:** Offline complete. Version `0.5.0` adds guarded autoscale, `0.6.0` adds transactional math metadata, and `0.7.0` adds the same-source manual TIME+SEC or AMPL+SOUR cursor subset. [RFC-0005](rfcs/0005-portable-scope-snapshot.md) defers the monolithic snapshot; [RFC-0006](rfcs/0006-portable-scope-acquisition-contracts.md) defers acquisition status and average capture; [RFC-0007](rfcs/0007-portable-scope-analysis-reads.md) defers slot-based measurement statistics and mandatory-field FFT status while documenting broader cursor needs. Reference metadata and history timestamps are skipped for vendor evidence gaps. All 168 package tests pass offline; every device effect, result, axis, timing, and restoration claim remains hardware-unverified.
- **M8:** Offline complete. Descriptors, tests, READMEs, and matrices agree. Ruff, package tests, source/wheel package checks, real wheel/sdist builds, and disposable-environment install/remove checks pass; every hardware claim remains unverified.

M1 offline evidence: version `0.1.0` passed package tests, Ruff, source package check, wheel/sdist content checks, and disposable-environment install/discovery/removal. No real `*IDN?` query was sent.

M2 offline evidence: version `0.2.0` covers strict four-channel validation, coupling and termination enums, all six known combinations, unknown responses, closed state, and the core high-impedance guard. No real channel query was sent; `scope.errors` remains skipped under RFC-0001.

Development follow-up: the current core development branch provides `scope.channel_input_state_v2`. The plugin adds a lossless V2 mapping that preserves AC/DC/GND, high_z/50_ohm, and `1_000_000/50` ohms without reverse-mapping legacy tokens. All 199 package tests, Ruff, and package check pass. Read-only hardware queries confirmed CH1/CH2 as `dc + high_z + 1 MΩ`; source CH1/CH2 were OFF, `consistent`, and `healthy` before and after.

M3 offline evidence: version `0.3.0` covers displayed-channel preflight, the strict ten-field preamble, an exact 1000-byte payload, X/Y conversion, six-field write/readback/restoration, non-replayed binary failure, ambiguous-write and restore-failure latches, and non-interleaving threaded transactions. The MSO8104 `0.9.0` development integration adds a bounded `DEF` driver method, a five-field core-owned recovery proof, and executor integration tests; 171 package tests pass. With corrected CH1/CH2 wiring, independent `1 kHz / 1 Vpp / 0 V` source runs returned 1000 samples: CH1 `1.05713 Vpp / 1000 Hz` and CH2 `1.0705 Vpp / 999.167 Hz`. Both reads completed core-owned restoration and fresh verification; EXIT cleanup then confirmed both source outputs OFF. This is limited `DEF` evidence, not general conversion accuracy or any other point mode.

M7 development follow-up: the current core development branch also provides `scope.cursor_readout_v2`. The plugin uses global addressing for manual TIME/AMPL A/B sources, seconds/hertz/degrees/percent or source/percent units, and A/B/delta values without moving cursors. Current hardware is VBA, so V2 rejects before value queries; accuracy remains hardware-unverified.

M7 development follow-up: the current core development branch also provides `scope.measurement_statistics_v2`. The plugin declares a read-only `item_sources` profile covering the manual's statistics items. Each call reads CURRENT, AVERages, DEViation, MINimum, MAXimum, and CNT; statistics buffers and requests outside the item/source constraints are rejected. Controlled `VPP,CHAN1` and `VPP,CHAN2` reads proved six finite response fields and `CNT=1000`, with no statistics configuration, reset, or display write. Other item/source behavior, dual-source/digital-source semantics, and statistics accuracy remain unverified. All 221 package tests, Ruff checks, and wheel lifecycle tests pass.

M7 development follow-up: the current core development branch also provides `scope.fft_status_v2`. The plugin first proves `OPERator? == FFT` for the target math slot, then reads source, window, vertical unit, and start/stop frequency; no I/O other than those six text queries occurs. Average completion, RBW, and FFT sample rate remain unavailable and are never inferred from global acquisition values. All 238 package tests, Ruff checks, and wheel lifecycle tests pass. A controlled front-panel-configured MATH1 read returned `FFT + CHAN1 + HANN + VRMS + 0–1 MHz`; source CH1/CH2 were OFF, `consistent`, and `healthy` before and after. This is not FFT accuracy evidence.

M7 development follow-up: the current core development branch also provides `scope.acquisition_status_v2`. The plugin always reads acquisition type, sample rate, and memory depth, and reads the configured average count only in `AVER` mode. Average is not applicable outside AVER; `average.complete`, run state, and segmented status are not reported and are never inferred from trigger STOP, OPC, or the configured count. All 253 package tests, Ruff checks, and wheel lifecycle tests pass. Controlled hardware returned `NORM + 500 kSa/s + 10 kpts`; source CH1/CH2 were OFF, `consistent`, and `healthy` before and after. AVER semantics and every completion state remain unverified.

M7 development follow-up: the current core development branch also provides `scope.digital_status_v2`. Each call first reads the LA module bit; an absent module returns only `shared.module_present=false` and sends no `:LA:*?` query. With LA present, D0-D15 map to POD1 (D0-D7) or POD2 (D8-D15), and six text queries read display, label, POD threshold, global timing calibration, and size. Position, label-enabled, activity, technology, and hysteresis remain unavailable; no digital waveform is read. All 268 package tests, Ruff checks, and wheel lifecycle tests pass. Controlled D0/D8 reads returned displayed state, the matching label/POD, `1.4 V`, `0 s`, and `MEDIUM`; source CH1/CH2 were OFF, `consistent`, and `healthy` before and after. Logic-probe behavior, electrical threshold accuracy, logic activity, and encoding semantics remain unverified.

M7 development follow-up: the current core development branch also provides `scope.snapshot_v2`. The plugin declares an identity/licensed-option static profile only: one `*IDN?` plus 13 `:SYSTem:OPTion:STATus? <type>` queries, for 14 pure text queries. Identity and options originate in the same call; an empty options tuple is valid only after all 13 explicitly prove not installed. The 55 health, channel, timebase, probe, waveform, and trigger fields remain unavailable, and the operation does not read `*STB?`, `*ESR?`, the error queue, trigger state, waveform, or binary data. All 282 package tests, Ruff checks, and wheel lifecycle tests pass. Controlled hardware completed the profile with source CH1/CH2 OFF, `consistent`, and `healthy` before and after. The six unread partitions and their accuracy remain unverified.

M4 offline evidence: version `0.4.0` extends the `0.3.1` single-acquisition contract with MAX/DMAX. BYTE blocks are capped at 250,000 points and all channels in one call share a hard four-million-point budget; over-budget responses fail before binary queries or array allocation. All 106 package tests cover restoration, block length, non-replay, partial callbacks under the total budget, MAX state-dependent semantics, the DMAX STOP precondition, and strict integer options. The binary blocker is now addressed in the current core worktree, but neither capture capability is declared: SINGLE or trigger STOP is not presented as waveform-capture acceptance without the wider acquisition recovery proof.

M8 offline evidence: all 168 package tests and Ruff pass for version `0.7.0`. In a disposable sibling-repository layout containing WaveBench core, the root suite passes 715 tests and skips two SP3000A tests as expected because private hardware evidence is absent. WaveBench `0.8.22` validates both the source directory and the real wheel. The wheel contains one `wavebench.instruments` entry point, one valid WaveBench runtime dependency, the MIT license, and plugin code. The sdist contains the public READMEs, matrices, milestones, RFCs, tests, and license. Neither artifact contains vendor-local material. A disposable virtual environment passes wheel installation, zero-I/O descriptor discovery, uninstall, and canonical-ID fallback. Local links in all 61 tracked Markdown files resolve. No real instrument was connected.

The `0.9.0` development regression in the current WaveBench `0.8.24` worktree includes bounded-waveform, input, cursor, measurement-statistics, FFT-status, acquisition-status, digital-status, and snapshot V2 integration tests: all 282 package tests, Ruff checks, and source/wheel lifecycle tests pass. The required core API is not separately released, so this is not a public wheel-release claim.
