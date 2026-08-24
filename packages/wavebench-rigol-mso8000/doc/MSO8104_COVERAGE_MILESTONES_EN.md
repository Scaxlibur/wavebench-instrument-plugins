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
| M3 | Transport/recovery hardware pass; signal closure pending | Current-screen NORM/BYTE `DEF` waveform through the RFC-0008 bounded-binary contract |
| M4 | Default deny | Single, multi-channel, and bounded MAX/DMAX acquisition; acquisition recovery and hardware evidence remain incomplete |
| M5 | RFC and skip | PNG framing and menu visibility lack a provable core contract |
| M6 | RFC/evidence gap and skip | Incomplete status model and undefined digital payload encoding |
| M7 | Offline complete | Autoscale, math metadata, restricted cursor; all other candidates explicitly skipped |
| M8 | Offline complete | Documentation, full offline verification, and package audit |

## Milestone exits

- **M0:** Freeze `rigol.mso8104`, `pyvisa`, switchable termination, coupling-plus-impedance normalization, point-mode mapping, block ownership, RFC topics, and package exclusions.
- **M1:** Provide zero-I/O descriptor import, exactly one core transport, strict MSO8104 identity, idempotent close, and wheel/sdist lifecycle tests.
- **M2:** Provide `scope.channel_coupling` through combined coupling and impedance reads. Keep `scope.errors` disabled and document `scope.check_errors=false` until the RFC is resolved.
- **M3:** The current core worktree implements the RFC-0008 bounded standard-waveform executor. The plugin exposes only `DEF` with `LF` trailing, a `1,000`-byte bound, one binary query, and core-owned recovery. Transport and recovery pass on hardware; known-signal closure remains pending.
- **M4:** Capture remains paused. It requires complete run-state, acquisition, trigger, timebase, channel-display, and channel-vertical recovery evidence in addition to bounded binary transport.
- **M5:** RFC and skip. `:DISPlay:DATA?` has no documented IEEE/TMC block framing, while `:SAVE:IMAGe:DATA?` is a documented block but cannot prove the core's `include_menu=False` contract. [RFC-0003](rfcs/0003-scope-screenshot-framing-and-menu-contract.md) proposes a non-replayed raw-byte query and an explicit unknown-menu result. Do not declare `scope.screenshot`, guess framing, ignore parameters, or create instrument files.
- **M6:** Skip both digital capabilities. The mandatory core status model includes activity, technology, hysteresis, and label visibility that MSO8000 cannot query; [RFC-0004](rfcs/0004-portable-scope-digital-status.md) proposes a portable optional-state model. The existing uint16 waveform model is suitable, but the manual does not define D0-D15 BYTE/WORD logic codes and leaves WORD byte order unclear. Do not infer them from analog conversion or FakeTransport fixtures.
- **M7:** Offline complete. Version `0.5.0` adds guarded autoscale, `0.6.0` adds transactional math metadata, and `0.7.0` adds the same-source manual TIME+SEC or AMPL+SOUR cursor subset. [RFC-0005](rfcs/0005-portable-scope-snapshot.md) defers the monolithic snapshot; [RFC-0006](rfcs/0006-portable-scope-acquisition-contracts.md) defers acquisition status and average capture; [RFC-0007](rfcs/0007-portable-scope-analysis-reads.md) defers slot-based measurement statistics and mandatory-field FFT status while documenting broader cursor needs. Reference metadata and history timestamps are skipped for vendor evidence gaps. All 168 package tests pass offline; every device effect, result, axis, timing, and restoration claim remains hardware-unverified.
- **M8:** Offline complete. Descriptors, tests, READMEs, and matrices agree. Ruff, package tests, source/wheel package checks, real wheel/sdist builds, and disposable-environment install/remove checks pass; every hardware claim remains unverified.

M1 offline evidence: version `0.1.0` passed package tests, Ruff, source package check, wheel/sdist content checks, and disposable-environment install/discovery/removal. No real `*IDN?` query was sent.

M2 offline evidence: version `0.2.0` covers strict four-channel validation, coupling and termination enums, all six known combinations, unknown responses, closed state, and the core high-impedance guard. No real channel query was sent; `scope.errors` remains skipped under RFC-0001.

M3 offline evidence: version `0.3.0` covers displayed-channel preflight, the strict ten-field preamble, an exact 1000-byte payload, X/Y conversion, six-field write/readback/restoration, non-replayed binary failure, ambiguous-write and restore-failure latches, and non-interleaving threaded transactions. The MSO8104 `0.9.0` development integration adds a bounded `DEF` driver method, a five-field core-owned recovery proof, and executor integration tests; 171 package tests pass. The second LAN/PyVISA attempt proves exact `LF` trailing, 1000 samples, and core-owned restoration. Its observed waveform is about `5.25 mVpp / 8.89 kHz`, not the enabled `1 Vpp / 1 kHz` source; known-signal closure and conversion accuracy remain pending.

M4 offline evidence: version `0.4.0` extends the `0.3.1` single-acquisition contract with MAX/DMAX. BYTE blocks are capped at 250,000 points and all channels in one call share a hard four-million-point budget; over-budget responses fail before binary queries or array allocation. All 106 package tests cover restoration, block length, non-replay, partial callbacks under the total budget, MAX state-dependent semantics, the DMAX STOP precondition, and strict integer options. The binary blocker is now addressed in the current core worktree, but neither capture capability is declared: SINGLE or trigger STOP is not presented as waveform-capture acceptance without the wider acquisition recovery proof.

M8 offline evidence: all 168 package tests and Ruff pass for version `0.7.0`. In a disposable sibling-repository layout containing WaveBench core, the root suite passes 715 tests and skips two SP3000A tests as expected because private hardware evidence is absent. WaveBench `0.8.22` validates both the source directory and the real wheel. The wheel contains one `wavebench.instruments` entry point, one valid WaveBench runtime dependency, the MIT license, and plugin code. The sdist contains the public READMEs, matrices, milestones, RFCs, tests, and license. Neither artifact contains vendor-local material. A disposable virtual environment passes wheel installation, zero-I/O descriptor discovery, uninstall, and canonical-ID fallback. Local links in all 61 tracked Markdown files resolve. No real instrument was connected.

The `0.9.0` development regression adds three bounded-waveform integration tests in the current WaveBench `0.8.24` worktree: 171 package tests, Ruff, and source/wheel package checks pass. The required core API is not separately released, so this is not a public wheel-release claim.
