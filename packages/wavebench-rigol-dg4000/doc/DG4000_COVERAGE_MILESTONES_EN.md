# DG4000 Coverage Milestones

[中文](DG4000_COVERAGE_MILESTONES.md)

## 1. Purpose and status

This document divides the broad DG4000 programming surface into M0-M12. Milestone numbers express risk order, not command counts or completion percentages. A milestone is complete only when code, failure paths, release artifacts, and the required hardware evidence all pass its exit gate.

Current version: `wavebench-rigol-dg4000 0.4.0`.

| Milestone | Status | Scope |
|---|---|---|
| M0 | **Complete** | Command audit, public boundary, evidence levels, artifact isolation |
| M1 | **Complete** | Strict input, response, model, and read-only snapshot handling for current APIs |
| M2 | **Complete** | Transactional fixed-wave and output writes |
| M3 | **Complete** | Complete read-only channel profile and bounded restore contract |
| M4 | **Complete** | DAC14 arbitrary-wave transaction and external-plugin hardware reacceptance |
| M5 | Not started | Query-only sweep profile |
| M6 | Not started | Non-destructive counter profile |
| M7 | Not started | Controlled sweep transaction and trigger |
| M8 | Not started | Controlled pulse/burst/marker profiles |
| M9 | Not started | Atomic dual-channel coupling |
| M10 | Not started | Basic AM/FM/PM/PWM modulation |
| M11 | Not started | Advanced modulation, harmonics, and arbitrary-wave formats |
| M12 | Not started | Model/channel acceptance matrix and release convergence |

M0 completion adds no instrument function. Version 0.4.0 completes M1/M2/M3 and the complete M4
hardware exit gate on both CH1 and CH2.

## 2. Rules shared by all milestones

- Expose no raw-SCPI escape hatch. Every operation enters through a narrow capability, strict parameter model, and explicit permission.
- Every numeric input and instrument numeric response must be finite. NaN, positive/negative infinity, and unparseable values fail closed.
- Enumerations use explicit allowlists. Unknown values are never guessed as OFF, FIX, SIN, or a default unit.
- Every channel-targeted API carries an explicit channel. CH1/CH2 behavior never depends on the front-panel selection.
- One reentrant lock serializes all transport I/O. Snapshot, write, readback, error check, and recovery cannot interleave.
- A complete pre-write snapshot is mandatory; otherwise there are zero writes. Every changed field is read back; a write returning without exception is not success evidence.
- A first-write timeout, disconnect, or any failure that cannot prove whether the command reached the instrument is ambiguous: never retry it blindly, and latch later configuration writes for that driver.
- A deterministic failure may attempt conservative recovery. Ambiguous, failed, or unverifiable recovery also latches the driver.
- Output-related recovery first forces the target channel OFF, restores other fields, and restores the original output only after every field succeeds. A failed recovery leaves output OFF.
- `SYSTem:ERRor?` consumes the error queue. Health APIs declare that behavior; write transactions inspect it only at explicit boundaries.
- `*CLS` clears status and is not a query-only probe. Binary-block writes are state changes that cannot be retried blindly.
- Hardware evidence is separated by model, channel, firmware, and capability. A DG4202 CH1 result is not extrapolated to CH2 or another DG4000 model.
- Tests, docs, and artifacts contain no real resources, serial numbers, command logs, screenshots, or raw waveforms.

## 3. Permanently denied by default

M0-M12 do not automatically expose:

- instrument slots and reset: `*SAV`, `*RCL`, `*RST`, `MEMory:STATe:DELete/LOCK`, `SYSTem:PRESet`;
- external storage: `MMEMory:COPY/DELete/LOAD/MDIRectory/STORe`;
- network and connection-wide configuration: `SYSTem:COMMunicate:LAN:*` and USB class;
- session interruption: `SYSTem:RESTART` and `SYSTem:SHUTDOWN`;
- the external power amplifier: `PA:*`;
- context-free `*TRG`, bare sweep/burst immediate triggers, or any raw write bypassing a capability.

If these are ever needed, they require a separate permission model, explicit human confirmation, and a separate project rather than an ordinary WaveBench experiment flow.

## 4. M0 — Command audit and release boundary

**Status: complete.**

Delivered scope:

- inventoried `COUNter`, `COUPling`, `DISPlay`, `MEMory`, `MMEMory`, `OUTPut`, `PA`, `SOURce`, `SYSTem`, `TRACe`, `HCOPy:SDUMp:DATA?`, and IEEE 488.2 domains;
- separated external-plugin hardware acceptance, offline validation, historical unmigrated evidence, diagnostic probes, uncovered areas, and default-denied commands;
- froze the canonical `rigol.dg4202` and built-in short-name fallback migration semantics;
- added bilingual matrices/milestones, MIT metadata, and a real-sdist content check;
- kept the wheel limited to the Python package and license, explicitly excluded `doc/vendor-local/`
  from sdist, and included the four public coverage documents in sdist.

Exit evidence:

- package tests, Ruff, and `wavebench plugin package check` pass;
- the real wheel has one `wavebench.instruments` entry point and contains the MIT LICENSE;
- the real sdist contains no local vendor material.

## 5. M1 — Strict closure of current APIs

**Status: complete.** Adds no capability. The CH1/CH2 zero-write gate passed on DG4202 firmware `00.01.14`.

Target queries: `*IDN?`, `SYSTem:ERRor?`, `OUTPut<n>?`, `SOURce<n>:FUNCtion?`, `FREQuency?`, `VOLTage?`, `VOLTage:UNIT?`, `VOLTage:OFFSet?`, `PHASe?`, `FREQuency:MODE?`, `SWEep:STATe?`, `APPLy?`, and `FUNCtion:SQUare:DCYCle?`.

Requirements:

- reject non-finite frequency, Vpp, offset, and duty inputs; reject non-finite response fields instead of returning a partially trusted `SourceStatus`;
- use strict enums for output, function, unit, frequency mode, and sweep state;
- parse manufacturer/model from `*IDN?`, separating models that may be identified read-only from models permitted for accepted writes;
- make aggregate status all-or-nothing; any query failure produces no write;
- align the instance `check_errors_after_ops` default for direct-driver and Service calls;
- preserve the query-only `source.arbitrary_probe` boundary, documenting its error-queue consumption and that a candidate `-113` is not a capability result.

Exit gate:

- failure injection covers every query position, empty responses, non-finite numbers, unknown enums, and invalid channels;
- relevant core/fallback and external-plugin behavior stays aligned;
- real DG4202 CH1 and CH2 each complete one zero-write profile with sanitized query-set and final-error evidence.

2026-07-27 evidence: one read-only CH1/CH2 session issued 24 queries and zero writes. Both channels
reported ON/SIN/1 kHz/5 Vpp/0 V/FIX/sweep OFF and the final error queue was clear. Firmware is
recorded as `00.01.14`; serial number and resource address are not recorded.

## 6. M2 — Fixed-wave and output write transactions

**Status: complete.** Covers current `source.set_frequency`, `set_function`, `set_amplitude_vpp`, `set_square_duty_cycle`, and `source.output`.

Target commands:

```text
SOURce<n>:FREQuency:MODE FIX
SOURce<n>:FREQuency[:FIXed] <frequency>
SOURce<n>:FUNCtion[:SHAPe] <wave>
SOURce<n>:VOLTage:UNIT VPP
SOURce<n>:VOLTage <vpp>
SOURce<n>:FUNCtion:SQUare:DCYCle <percent>
OUTPut<n> ON|OFF
```

`FREQuency:MODE FIX` is an existing DG4202 compatibility path absent from the local manual's
frequency command index. M2 must validate it with a target-firmware probe and hardware readback;
the current code alone is not vendor-manual evidence.

Transaction requirements:

- use one driver-level `RLock`; write only after a complete snapshot; read back each target field with an explicit tolerance;
- treat amplitude unit+value as one transaction and FIX-mode+frequency as one transaction;
- on failure, force OFF, restore function/frequency/unit/amplitude/duty, and restore the original output last;
- before output ON, recheck the core Vpp safety limit, complete profile, and error boundary;
- latch configuration writes after an ambiguous write, an unverifiable post-write state, or failed recovery; while latched, allow only diagnostics and an explicitly defined emergency output-off path;
- make run restore use the same off-first rule instead of modifying a live waveform.

Exit gate:

- inject failure at every snapshot query, forward write, readback, error check, and restore write;
- prove public I/O on one instance does not interleave under concurrency;
- separately accept low-Vpp/high-impedance fixed sine, square duty, ON→OFF, and field-by-field restore on DG4202 CH1 and CH2;
- exercise first-write ambiguity and recovery failure through a controlled proxy/fault injector, not by unplugging the instrument and guessing the result.

2026-07-27 evidence: CH1 and CH2 separately ran OFF, temporary SQU/different fixed frequencies/
0.8 Vpp/37% duty, explicit ON-to-OFF, and off-first restoration. Fresh sessions verified each
field. Both channels ended at their original ON/SIN/1 kHz/5 Vpp/0 V/FIX/sweep OFF state with a
clear error queue. The fault matrix remains FakeTransport-injected; disconnects are not treated
as state evidence.

## 7. M3 — Complete read-only channel profile and restore claims

**Status: complete.**

Add query-only context:

```text
OUTPut<n>:LOAD? / IMPedance?
OUTPut<n>:POLarity?
OUTPut<n>:NOISe:STATe? / NOISe:SCALe?
OUTPut<n>:SYNC:STATe? / SYNC:POLarity?
SOURce<n>:BURSt:STATe?
SOURce<n>:MOD:STATe? / MOD:TYPe?
SOURce<n>:MARKer:STATe?
SOURce<n>:PULSe:HOLD?
```

The profile distinguishes:

- **restorable fields** already written and transactionally restored by WaveBench;
- **read-only context** used to reject unsafe operations but not yet auto-restored;
- **irreversible side effects**, such as overwriting volatile USER waveform data.

Exit gate: CH1/CH2 profiles are all-or-nothing, finite/enum strict, and zero-write. README, artifacts, and run restore no longer describe current basic restoration as a full instrument-state restore.

2026-07-27 evidence: external plugin `0.4.0` read CH1 and CH2 on DG4202 firmware `00.01.14`
in one controlled session. Transport guards prohibited every text/binary write. The gate completed
45 queries, zero text writes, and zero binary writes, returning all basic state and
load/polarity/noise/sync/burst/modulation/marker/pulse-hold context for both channels. The error
queue is consuming, so this gate did not read it. M3 does not widen basic restoration; read-only
context and volatile USER contents remain outside automatic restoration.

## 8. M4 — DAC14 arbitrary-wave transaction and hardware reacceptance

**Status: complete. CH1 and CH2 both pass the complete hardware exit gate.**

Target commands: `TRACe:DATA:DAC VOLATILE,<IEEE-488.2 binary block>`, fixed playback frequency, `VOLTage:UNIT VPP`, Vpp, offset, `FUNCtion USER`, and explicit output.

Frozen boundary: accept only a core-generated and validated `DG4000DacBlock`; DAC14, little-endian, volatile destination. No raw bytes, decimal tables, DAC16, or file paths.

Preflight and transaction:

- the target channel must already be OFF, FIX, with sweep OFF; M3 can now read burst/modulation state reliably, but the current M4 upload transaction does not yet include those fields in preflight and therefore does not claim to validate them; do not silently make it safe;
- `output_on=false` means the channel remains OFF after upload, not that a pre-existing ON state is preserved;
- do not retry the binary block blindly. An ambiguous first binary write latches the driver and records unknown volatile-waveform state;
- read back USER/frequency/Vpp/offset after upload; enable output only after an explicit request and a repeated safety check;
- recovery starts with OFF and restores all supported prior fields. Prior volatile USER contents are not restorable and must be recorded in the artifact.

Hardware exit gate:

1. With DG4202 CH1 OFF, upload a low-point-count, 1 kHz, 1 Vpp, 0 V-offset DAC14 triangle or sine.
2. Read back USER/frequency/Vpp/offset and a clear error queue.
3. Explicitly enable output, verify frequency/Vpp/shape with a high-impedance scope, then disable output.
4. Restore and verify each field in a new session.
5. Repeat separately on CH2. Historical built-in-driver evidence cannot substitute for external-plugin acceptance.

2026-07-27 evidence: CH1 and CH2 each uploaded one 64-point little-endian DAC14 triangle while
OFF/FIX/sweep OFF, read back USER/1 kHz/1 Vpp/0 V, observed a clear error queue, and confirmed the
original state in a fresh session. CH1 separately drove a 2 Vpp triangle into a high-impedance
RTM2032. A 10,000-point capture measured 997.26 Hz and 2.16 Vpp; triangle-template RMSE was
0.0390 V, 49.2% of sine-template RMSE. The restored sine measured 998.25 Hz and 5.12 Vpp. CH2 was
then connected to the high-impedance RTM2032 CH2 input and repeated step 3 with a 1 kHz, 1 Vpp
triangle. It measured 999.75 Hz and 1.12 Vpp; normalized triangle-template RMSE was 0.09285,
sine-template RMSE was 0.2196, and their ratio was 0.4229. The original DG4202 CH2 state was then
restored and the error queue was clear; scope timebase, range, and trigger settings were unchanged
across the gate. Both uploads overwrote volatile USER data.

## 9. M5 — Query-only sweep profile

**Status: not started; P2.** Query an existing sweep without starting, stopping, or triggering it.

At minimum, capture `SWEep:STATe?`, `FREQuency:STARt?/STOP?/CENTer?/SPAN?`, `SWEep:SPACing?`, `SWEep:STEP?`, `SWEep:TIME?`, hold/return time, trigger source/slope/trigger-out, and marker state/frequency.

Exit gate: strict enums and internal relationship checks; no partial profile after any failed query. Validate three zero-write rounds with instrument output OFF and sweep preset both OFF and ON.

## 10. M6 — Non-destructive counter profile

**Status: not started; P2.**

Allowed queries: `COUNter:STATe?`, `MEASure?`, `COUPing?`, `IMPedance?`, `ATTenuation?`, `GATEtime?`, `HF?`, `LEVel?`, `SENSitive?`, and statistics state/display.

Default-deny `COUNter:AUTO`, `STATIstics:CLEAr`, and automatic counter enablement. If the counter is OFF, return that state and an explicit no-measurement result; never turn the input on. A 50-ohm value is read-only here; any future setter requires a separate cabling confirmation.

Exit gate: unknown/non-finite responses fail closed, repeated queries do not change counter/statistics state, and a real DG4202 produces zero-write evidence.

## 11. M7 — Controlled sweep transaction

**Status: not started; P2.** Requires M2, M3, and M5.

The transaction covers start/stop or center/span, spacing/steps/time, marker, trigger source/slope/trigger-out, and sweep state. A manual immediate trigger or `*TRG` exists only as one explicit action inside an established, readback-confirmed sweep session.

Exit gate: complete snapshot→write→readback→external measurement→OFF→restore. Any failure leaves output OFF. Accept CH1/CH2 separately; never expose a generic sweep without load and frequency constraints.

## 12. M8 — Pulse, burst, and marker

**Status: not started; P2/P3.**

- Pulse profile: hold mode, width/duty, delay, and leading/trailing transitions.
- Burst profile: mode, cycles, phase, internal period, delay, gate polarity, trigger source/slope/trigger-out.
- Marker is exposed only inside the relevant sweep/burst profile, not as a global bare setter.

Implement query-only first, then transactional writes. Separate output enable from trigger. Never retry an immediate trigger. The exit gate includes output-off failure convergence, edge/duty constraints, and oscilloscope time-domain evidence.

## 13. M9 — Atomic dual-channel coupling

**Status: not started; P3.**

Cover `COUPling:STATe`, base channel, and amplitude/frequency/phase coupling states and deviations. One operation affects both channels, so it requires a two-channel snapshot, one device lock, and two-channel recovery. If either channel cannot be read, perform zero writes.

Exit gate: configure/read back with CH1/CH2 OFF, then perform a low-risk closed loop. Inject faults into every write and recovery. A failed recovery leaves both outputs OFF and latches the device.

## 14. M10 — Basic modulation

**Status: not started; P3.**

The first group considers state, type, internal source, internal frequency/function, and depth/deviation for AM/FM/PM/PWM. External modulation sources remain out of scope. Each modulation type receives its own profile and capability rather than one giant generic dictionary.

Exit gate: reuse M2/M3 transaction foundations; configure while modulation is OFF, read back each field, explicitly enable, collect scope/spectrum evidence, disable, and restore. Mode-inapplicable fields may not be guessed or leaked from a previous mode.

## 15. M11 — Advanced modulation, harmonics, and arbitrary-wave formats

**Status: not started; P3.**

Candidates include ASK/FSK/PSK/BPSK/QPSK/3FSK/4FSK/OSK, harmonic order/type/user/amplitude/phase, and `TRACe:DATA:DAC16`, points/value/interpolate/load queries under a contract distinct from DAC14.

Every candidate first needs a manual/firmware probe, independent data contract, and resource-limit audit. DAC16 cannot reuse `DG4000DacBlock` while pretending to be DAC14. Freeze chunking, byte order, maximum points, RAM/DDR lifetime, and readback semantics first. These may remain in backlog permanently without a concrete experiment need.

## 16. M12 — Model matrix and release convergence

**Status: not started.**

M12 adds no raw SCPI or high-side-effect maintenance command. It converges:

- a model, firmware, CH1/CH2, backend, and evidence-level matrix for every public capability;
- external-plugin versus built-in-fallback differential tests;
- lifecycle, wheel/sdist, editable install, upgrade/downgrade/uninstall fallback, and public install docs;
- slow transport, query/write timeout, partial binary failure, concurrency, latched behavior, and artifact redaction;
- compatibility range and changelog language that never turns “identifiable model” into “accepted model.”

Final exit requires every public write capability to have normal-path, failure-matrix, recovery/latch evidence and hardware acceptance on an explicitly named model/channel. Everything else remains uncovered or denied by default.

## 17. Current evidence boundary

- External-plugin hardware accepted: M1/M2/M3 dual-channel gates and complete M4 CH1/CH2 gates
  on DG4202 firmware `00.01.14`.
- Historical evidence remains provenance only and no longer substitutes for current-plugin acceptance.
- Not passed: M5-M12.

Any status upgrade must update both matrices, both milestone documents, both READMEs, tests, and real build-artifact checks together.
