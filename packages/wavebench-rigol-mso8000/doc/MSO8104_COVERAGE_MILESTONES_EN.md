# MSO8104 Coverage Milestones

[中文](MSO8104_COVERAGE_MILESTONES.md)

## Goal and evidence boundary

This plan divides the RIGOL MSO8000 programming surface into risk-ordered milestones M0 through M8. The current development pass is offline-only: it uses the manual, FakeTransport tests, fault injection, package builds, and installation lifecycle checks. It does not connect to hardware and does not claim model, firmware, transport, throughput, restoration, or measurement evidence.

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
| M3 | Offline complete | Current-screen NORM/BYTE waveform |
| M4 | Offline complete | Single, multi-channel, and bounded MAX/DMAX acquisition |
| M5 | RFC and skip | PNG framing and menu visibility lack a provable core contract |
| M6 | RFC/evidence gap and skip | Incomplete status model and undefined digital payload encoding |
| M7 | In progress | Autoscale is offline complete; advanced reads remain under review |
| M8 | Not started | Documentation, full offline verification, and package audit |

## Milestone exits

- **M0:** Freeze `rigol.mso8104`, `pyvisa`, switchable termination, coupling-plus-impedance normalization, point-mode mapping, block ownership, RFC topics, and package exclusions.
- **M1:** Provide zero-I/O descriptor import, exactly one core transport, strict MSO8104 identity, idempotent close, and wheel/sdist lifecycle tests.
- **M2:** Provide `scope.channel_coupling` through combined coupling and impedance reads. Keep `scope.errors` disabled and document `scope.check_errors=false` until the RFC is resolved.
- **M3:** Provide `scope.fetch_waveform` for `DEF → NORMal + BYTE`, with visible-channel preflight, transfer-state restoration, strict preamble/payload validation, and no implicit STOP/SINGLE/AUTOSCALE.
- **M4:** Provide single and multi-channel capture plus bounded MAX/DMAX. One multi-channel call performs one acquisition, uses hard memory/point limits, never replays acquisition or binary queries, and preserves partial results through callbacks.
- **M5:** RFC and skip. `:DISPlay:DATA?` has no documented IEEE/TMC block framing, while `:SAVE:IMAGe:DATA?` is a documented block but cannot prove the core's `include_menu=False` contract. [RFC-0003](rfcs/0003-scope-screenshot-framing-and-menu-contract.md) proposes a non-replayed raw-byte query and an explicit unknown-menu result. Do not declare `scope.screenshot`, guess framing, ignore parameters, or create instrument files.
- **M6:** Skip both digital capabilities. The mandatory core status model includes activity, technology, hysteresis, and label visibility that MSO8000 cannot query; [RFC-0004](rfcs/0004-portable-scope-digital-status.md) proposes a portable optional-state model. The existing uint16 waveform model is suitable, but the manual does not define D0-D15 BYTE/WORD logic codes and leaves WORD byte order unclear. Do not infer them from analog conversion or FakeTransport fixtures.
- **M7:** Evaluate each existing typed scope capability independently. Version `0.5.0` adds guarded autoscale. Version `0.6.0` adds transactional `scope.math_metadata`. Version `0.7.0` adds a read-only cursor subset: public index 1, explicitly configured manual mode, same A/B source, and either TIME+SEC or AMPL+SOUR. It reads X delta/inverse or Y delta without moving cursors and rejects other modes, sources, or units. Missing fields, consuming reads, unsafe restoration, or absent core APIs result in an RFC and a skipped capability, not fabricated defaults. All 168 package tests pass offline; autoscale effects, math results, FFT axes, cursor accuracy, and restoration remain hardware-unverified.
- **M8:** Make descriptors, tests, READMEs, and matrices agree; pass Ruff, package tests, package check, real wheel/sdist, and disposable-environment install/remove checks; retain every hardware claim as unverified.

M1 offline evidence: version `0.1.0` passed package tests, Ruff, source package check, wheel/sdist content checks, and disposable-environment install/discovery/removal. No real `*IDN?` query was sent.

M2 offline evidence: version `0.2.0` covers strict four-channel validation, coupling and termination enums, all six known combinations, unknown responses, closed state, and the core high-impedance guard. No real channel query was sent; `scope.errors` remains skipped under RFC-0001.

M3 offline evidence: version `0.3.0` covers displayed-channel preflight, the strict ten-field preamble, an exact 1000-byte payload, X/Y conversion, six-field write/readback/restoration, non-replayed binary failure, ambiguous-write and restore-failure latches, and non-interleaving threaded transactions. All 66 package tests pass; no real waveform query was sent.

M4 offline evidence: version `0.4.0` extends the `0.3.1` single-acquisition contract with MAX/DMAX. BYTE blocks are capped at 250,000 points and all channels in one call share a hard four-million-point budget; over-budget responses fail before binary queries or array allocation. All 106 package tests cover restoration, block length, non-replay, partial callbacks under the total budget, MAX state-dependent semantics, the DMAX STOP precondition, and strict integer options. Hardware points, throughput, and timeouts remain unverified.
