# WaveBench Core RFC: SDS3000 Impact Assessment

[中文](WAVEBENCH_CORE_RFC.md)

> Status: `Draft / Needs revision`
> Revision: `R1`
> Core baseline: WaveBench `0.8.24`
> API status: transport/session R1 released and adopted; this document's typed-scope-state proposals remain unfrozen
> Core implementation: `M1–M7 released` (migration baseline `a8e6b59`; release commit `dc7ce5b`)

## Conclusion

The SDS3054 plugin is functionally complete through M8 and adopts transport replay/session R1 from WaveBench `0.8.24`. P0 call-site migration, structured-error handling, and fault injection were first completed against core commit `a8e6b59`; the release commit is `dc7ce5b`. Its six declared capabilities—identity, error registers, channel coupling, waveform fetch, single-channel capture, and same-acquisition multi-channel capture—now use the released core contract. The wheel and descriptor minimum versions are both `0.8.24`, the upper bound remains `0.9`, and the executable plugin API remains `wavebench.instrument.v2`.

This document remains a plugin impact assessment, not a typed-scope public API specification. The first draft placed read-only state, generic patches, and partial status v2 too close together. Transport/session P0 is now adopted, while the analog/timebase/edge-trigger state and generic-write proposals in this document still require separate freezing. WaveBench `0.8.24` screenshot, acquisition, trace, and error-drain contracts are assessed individually, but SDS3000 does not declare them without sufficient evidence.

The machine-readable form is [`wavebench-core-rfc.json`](wavebench-core-rfc.json). This branch does not modify WaveBench core. Commit `a8e6b59` remains migration evidence, while runtime gates use WaveBench `0.8.24` at release commit `dc7ce5b`.

## Stage labels

Plugin milestones and RFC revisions use separate labels so that a completed plugin does not imply a frozen core API:

| Subject | Current state | Meaning |
| --- | --- | --- |
| SDS3000 plugin | `M8-functional-complete / P0-adopted` | The current six capabilities passed their gates; transport/session P0 is adopted |
| This plugin impact assessment | `R1-draft-needs-revision` | Typed-scope proposals remain open to revision; the separate Accepted transport/session R1 is authoritative |
| WaveBench core implementation | `M1–M7-released-in-0.8.24` | Migration baseline `a8e6b59`; release commit `dc7ce5b`; plugin minimum version `0.8.24` |

## Specification split and current status

This impact assessment splits the public contract into two independent specifications. The transport/session RFC is released and adopted; this document's typed-scope-state proposal remains a prerequisite for analog/timebase/edge-trigger P1 coding:

| Separate specification | Required frozen content | Gate |
| --- | --- | --- |
| Transport replay/session RFC | The default policy of existing `query()`, migration of old call sites, structured transport errors, command transmission count, partial responses, desynchronization, session-health ownership, recovery authorization, state-validation scope, and fail-closed behavior when a backend cannot support `read_continuation_only` | Released in WaveBench `0.8.24` and adopted by SDS3000 |
| Typed scope state RFC | Exact fields, `Protocol` signatures, static and runtime field support, `OperationSpec`, Service/CLI/run-plan consumption, v1 precedence, error envelopes, and three-vendor mappings | Before any P1 capability is frozen |

The transport RFC distinguishes source compatibility from observable behavior compatibility. Migrating consuming reads from automatic retries to `no_replay`, and stopping later instrument I/O on a poisoned session under `on_failure=continue`, are observable changes and cannot be described as entirely additive.

The transport RFC also freezes three session contracts: shared `InstrumentSessionState` owns health; only the core transaction coordinator may authorize bounded recovery and validation while state is `uncertain`; and leaving `uncertain` or reconnecting requires contract-defined synchronization, identity continuity, and affected-field validation. Ordinary Service calls and plugins receive no recovery authority and cannot treat unverified configuration as healthy.

## Confirmed core facts

| Interface or model | Current conclusion | Follow-up |
| --- | --- | --- |
| `InstrumentTransport.query_bin_block()` | Sufficient for the current SDS3054 binary path and not replayed in the same session after failure | Preserve non-replayable behavior in a common transport contract |
| `PyVisaTransport.query()` / `query_opc()` | Core requires an explicit replay policy; unclassified calls default to `no_replay` | Plugin call sites are explicitly migrated, preserve structured errors, and adopt WaveBench `0.8.24` |
| `OperationSpec.effect=acquire` | Already requires `read_write`; core M7 declares capture/fetch field closures, verification fields, and restoration coverage | SDS3000 temporary `CHDR`, `CFMT`, `CORD`, and `WFSU` settings are mapped to the common closure; the plugin must not perform `uncertain → healthy` itself |
| `ScopeStatusSummary` | Already returns IDN, coupling, and missing capabilities | Reuse the existing partial-status path before adding a broad snapshot v2 |
| `PyVisaTransport` plus `PyVICP` | Sufficient for the current VICP text and binary connection | Do not add an SDS3000-specific core transport |

## P0-1: Non-replayable query contract

### Problem

Before R1 implementation, `InstrumentTransport` had no replay policy or common `query_once()` contract. WaveBench `0.8.24` releases an explicit `replay` keyword, a `no_replay` default, and structured transport errors. SDS3000 `CMR?`, `EXR?`, `DDR?`, acquisition-bound `*OPC?`, and all other query call sites explicitly use `no_replay`, with structured-error priority tests.

Before R1 implementation, `RsInstrumentTransport` and `SerialTransport` did not apply the same explicit retry loop. WaveBench `0.8.24` provides a backend-independent replay contract. Core owns the `GuardedAuditedTransport` health gate; the plugin cannot bypass it, authorize recovery, or perform `uncertain → healthy`.

### Minimum behavior

R1 freezes the existing `query()`, `query_opc()`, `query_bin_block()`, and `query_float_list()` method names and adds a keyword-only `replay` parameter to each method. The first version defines three explicit policies:

```text
safe_to_replay
no_replay
read_continuation_only
```

- `safe_to_replay`: used only when the caller explicitly declares that the query may be resent. The transport never infers safety from SCPI text.
- `no_replay`: transmits the command at most once. Timeout, partial response, or ambiguous completion never resends the command.
- `read_continuation_only`: may continue reading an already transmitted response but must not resend the command.

R1 does not add a parallel public `query_once()` method. Every backend reports command transmission count, response progress, and communication synchronization through the existing methods and structured errors.

The following calls default to `no_replay`:

- read-to-clear registers;
- acquisition-bound `*OPC?`;
- requests after any response byte has arrived;
- status reads whose replay safety cannot be proven.

Independent status polling may opt into replay only through an explicit operation contract. Not every `*OPC?` use has identical semantics.

### P0 exit gate (core release and plugin adoption complete)

- PyVISA, RsInstrument, Serial, `GuardedAuditedTransport`, and FakeTransport share one replay contract.
- Fault injection proves that a failed `no_replay` query transmits at most once.
- No first-version backend declares continuation support. `read_continuation_only` tests prove that the request fails before transmission with `attempts=0` and no command write. A later backend may continue the current response only after declaring the capability and passing dedicated tests.
- `TransportIOError` records replay policy, response progress, and communication synchronization. Telemetry contains only approved non-sensitive metrics and is not a substitute for structured error evidence.
- Every SDS3000 transport query explicitly uses `ReplayPolicy.NO_REPLAY`; fault injection for `CMR?`, `EXR?`, `DDR?`, and acquisition-bound `*OPC?` proves that failures are not replayed.
- The plugin `_acquire_once` path, OPC waits, and temporary restoration context managers preserve `TransportIOError` and `SessionHealthError`; a structured failure is not converted into an ordinary timeout and does not issue another unauthorized recovery command.
- Migration baseline is `a8e6b59`; formal adoption uses WaveBench `0.8.24` at release commit `dc7ce5b`, with both wheel and descriptor minimum versions set to `0.8.24`.

## P0-2: Shared session health and poison latch

### State model

```text
healthy -> uncertain -> poisoned -> closed
```

This axis describes whether the communication session is trustworthy. Configuration trust is represented by an epoch-scoped `verified_fields` set rather than a global `verified/unverified` boolean. A newly connected or reconnected communication session may be `healthy`, but `verified_fields` starts empty. Explicit read-only verification adds only the proven field closure and never expands an unrelated query into a claim that the whole instrument configuration is verified.

Transitions may skip states. An unknown write result enters `uncertain` when the transport can still prove synchronization; only bounded restoration and verification are then permitted. A possibly desynchronized channel enters `poisoned` immediately. `uncertain` returns to `healthy` only when the channel remains synchronized and restoration is independently read back. `poisoned` cannot recover within the original session.

| Phase | Result | Session behavior |
| --- | --- | --- |
| Preflight rejection | No I/O occurred | Remains `healthy` |
| New connection or reconnect | Communication channel is re-established | `healthy` with an empty `verified_fields`; instrument configuration is not assumed to be restored |
| Unknown write result | The instrument may have changed | Becomes `uncertain` if synchronization is proven; otherwise immediately `poisoned` |
| Post-write readback failure | Current value cannot be proved | Becomes `uncertain`; only restoration and verification I/O are allowed |
| Restoration failure | Original state is unknown | `poisoned` |
| Restoration success | The channel is synchronized and the related field closure passes independent tolerance checks | Returns from `uncertain` to `healthy`, adds only proven fields to `verified_fields`, and records actual quantized values |
| Close | Session is no longer usable | `closed` |

### Responsibility split

- Core: replay policy, common error taxonomy, shared session health, pre-operation gate, and `on_failure=continue` stop behavior.
- Plugin: affected-field closure, snapshots, restoration order, vendor-valid combinations, and quantization tolerance.
- Transport: whether a command was transmitted, whether a response was partial, and whether the communication channel may be desynchronized.

WaveBench `0.8.24` places the latch on the shared `InstrumentSessionState`, not a temporary `ScopeService`. Run plans reuse one scope session. When a failed step specifies `on_failure=continue`, every later instrument operation on a poisoned session must fail before transport I/O. Only local audit, closing the old session, and establishing a new session remain available as lifecycle actions. Reconstructing a Service does not clear the latch. The plugin covers this gate and does not reset health in the driver.

### Distinct error classes

- Preflight or validation error: zero I/O, healthy session.
- Write failure proven before transmission: failed operation, reusable session.
- Unknown write result with a synchronized channel: uncertain session, limited to restoration and verification.
- Desynchronized or unprovably synchronized channel: poisoned session.
- Readback mismatch: failed transaction followed by restoration.
- Independent readback mismatch after restoration: `StateDriftError` plus a poisoned session.
- Structured failure of a restoration or verification exchange: preserve `TransportIOError` or `SessionHealthError` and poison the session.
- Later operation on a poisoned session: stable session-health error before I/O.

## P1-1: Typed read-only state

After a released core containing R1, completed plugin P0 adoption, and a frozen typed-scope RFC, the first scope capabilities are read-only:

```text
scope.analog_channel_state
scope.timebase_state
scope.edge_trigger_state
```

Each capability must define:

1. A public `Protocol` and immutable typed model.
2. `OperationSpec`, effect, risk, timeout, and `changed_fields`.
3. A `ScopeService` consumer.
4. Stable JSON and strict behavior.
5. Precedence when the new capability coexists with v1.

A capability string and driver method alone do not form a usable core interface. CLI and run-plan support may arrive in explicit stages, but the RFC must name the consumers included in each release.

### Field metadata

`supported_fields` cannot express readable-but-not-writable fields. The first model needs at least:

```text
readable
writable
type
unit
enum
minimum
maximum
quantization
```

`UNSET` means unchanged. `None` is valid only when a field defines an explicit automatic, clear, or other nullable meaning; it never implicitly means unknown or omitted. Serialization omits `UNSET` instead of emitting JSON `null`.

Field availability describes only device states returned by a successful operation:

```text
unsupported
supported_but_not_readable
stale_or_unknown
valid_value
```

`query_failed` is not an availability member. A failed query uses the structured operation-error envelope; it is not an unsupported feature and must not silently become a successful partial result.

### Composite analog-input semantics

SDS3000 `A1M/D1M/D50/GND` encodes coupling and termination together. They cannot be treated as two independent writable fields. The first state model may expose normalized coupling, termination, and a typed composite input state, but termination remains read-only and all legal or unrepresentable combinations must be defined.

## P1-2: Acquisition state and control contracts

WaveBench `0.8.24` releases `scope.acquisition_run_state` and `scope.acquisition_control`. Public acquisition phases are `unknown/stopped/ready/arming/waiting/acquiring/rolling/stopping/complete/error`; trigger modes are `auto/normal/single/roll/unknown`. The control contract also requires continuous start, stop, single acquisition, baseline snapshot, restoration, and independent verification.

SDS3000 does not currently declare either capability. Average, segmented acquisition, option inventory, and history frame counts remain separate capabilities.

| Vendor | Current evidence | Mappable content | Unresolved issue |
| --- | --- | --- | --- |
| SDS3000 | `TRMD?` returns `AUTO/NORM/SINGLE/STOP` | `STOP` proves only stopped; the other tokens are closer to trigger mode | Running, waiting, and armed cannot be distinguished; `SEQ` remains `firmware-unverified` and is excluded as evidence |
| DS1000Z | The current driver has only `:STOP`, `:SINGle`, and `*OPC?` synchronization | Actions and completion synchronization only; no read-only state mapping | Manual review and controlled read-only evidence are required; current state cannot be inferred from the last command |
| RTM2000 | `STATUS:OPERation:CONDITION?` bit 3 and `TRIGger:A:MODE?` | Waiting-for-trigger and the supported trigger-mode subset | The current driver has no common running/stopped readback |

The core contract is frozen, but each plugin still needs per-value mappings, unmappable values, static support, and runtime-unavailability rules. A query failure remains an operation error; `unknown` means that the instrument returned successfully but could not be mapped. SDS3000 `TRMD?` evidence cannot distinguish the complete acquisition phase set and does not cover generic continuous-start, stop, or single-acquisition failure recovery and independent verification, so both capabilities remain `firmware-unverified` for this plugin.

## P2: Narrow configuration patches

Write capabilities are reviewed only after P0, typed read-only state, core consumers, and contract tests are complete:

```text
scope.analog_channel_configure
scope.timebase_configure
```

First-version candidate fields are limited to:

- `enabled`;
- `scale_v_per_div`;
- `offset_v`;
- `scale_s_per_div`;
- `position_s`.

The first version excludes:

- termination;
- composite coupling and termination writes;
- `scope.edge_trigger_configure`;
- arbitrary vendor fields or tokens.

Empty patches, unsupported or read-only fields, invalid values, and field conflicts fail before I/O. A successful transaction snapshots, writes, reads back, and compares quantized values. A failed transaction restores in plugin-declared reverse order while core maintains session health.

Audit distinguishes:

```text
declared_changed_fields
observed_changed_fields
restored_fields
state_uncertain
session_poisoned
```

`changed_fields` describes instrument fields that may be touched during the transaction, not only values retained after completion. Existing `scope.capture`, `scope.capture_waveforms`, `scope.capture_multiple`, and `scope.fetch_waveform` specs also require an audit of timebase, vertical scale, trace, trigger mode, and waveform-transfer state.

## Termination safety boundary

`read_write` means that policy permits a write. It does not prove that wiring, source output, signal amplitude, or load conditions are safe for 50 Ω. The WaveBench project boundary does not allow ordinary automation to change scope input impedance. R1 therefore decides:

- termination is read-only in the first public state model;
- generic patches do not include termination;
- even 50 Ω to high impedance is not a default automated action;
- any future dedicated capability requires explicit safety confirmation, zero-write preflight, source-state proof, independent readback, failure latching, and hardware evidence;
- high impedance to 50 Ω requires a separate and stricter risk review and cannot rely on ordinary `read_write` access.

## `ScopeSnapshotV2` and acquisition status

### `ScopeSnapshotV2`

R1 does not freeze `ScopeSnapshotV2`. Existing `ScopeStatusSummary` already provides IDN, coupling, and missing capabilities for drivers without a complete `scope.snapshot`.

If a v2 model is revisited, it must use closed, versioned component types and field-level `Availability[T]`. An arbitrary `Mapping[str, typed_component]` is not accepted as a stable public model. Runtime `query_failed` must not be downgraded to an ordinary unavailable reason.

### `ScopeAcquisitionStatusV2`

The broad `ScopeAcquisitionStatusV2` proposal remains deferred. WaveBench `0.8.24` splits minimal run state and control into `scope.acquisition_run_state` and `scope.acquisition_control`; average, segmented, and option status still receive separate typed capabilities. Existing v1 models remain unchanged.

## Core consumption and compatibility contract

Every new capability requires:

- a `Protocol` and typed model;
- `OperationSpec`, effect, risk, timeout, `changed_fields`, and restoration coverage;
- a `ScopeService` method;
- stable JSON and error envelope;
- strict behavior and v1/v2 precedence;
- an explicit statement of whether CLI and run plans are included in the first release.

New symbols should remain source-additive: existing `scope.channel_coupling`, capture arguments, v1 snapshot, and acquisition status types do not change in place. Core R1 freezes a `no_replay` default for `query()`, structured errors, and poisoned-session gates. Moving consuming reads to `no_replay`, replacing implicit retries with structured errors, and blocking later I/O under `on_failure=continue` on a poisoned session are intentional observable behavior changes. Plugin call-site migration, offline regression, version-gate updates, and the adopted marker are complete.

## Release and version gates

The current plugin uses three concurrent version gates. Wheel metadata declares `wavebench>=0.8.24,<0.9`; the descriptor declares `wavebench_min_version="0.8.24"` and `wavebench_max_version="0.9.0"`; and the descriptor explicitly declares `api_version="wavebench.instrument.v2"`. These independently gate dependency resolution, runtime core compatibility, and the executable plugin API.

Before the plugin adopts P0 core behavior:

1. P0 must exist in a released WaveBench version rather than an unpublished commit.
2. The wheel and descriptor lower bounds move together to the first P0 release, and the upper bound is reviewed again.
3. Core R1 has decided that `wavebench.instrument.v2` remains compatible, so this adoption retains that value. The adoption change still verifies that the core constant and plugin descriptor match. A new API version is required only if the executable-plugin contract changes incompatibly again before release.
4. Registry validation rejects an API or core-version mismatch before driver-factory or transport I/O.
5. Isolated wheel installation tests verify `Requires-Dist`, descriptor bounds, `api_version`, and the entry point together.

This atomic adoption commit moves both wheel and descriptor minimum versions to `0.8.24`. The reviewed `0.9.0` upper bound and `wavebench.instrument.v2` remain unchanged.

### Plugin P0 adoption checklist

Core R1 is released in WaveBench `0.8.24`. Call-site migration, fault injection, version-gate updates, and the adopted marker are completed in this atomic commit; final status depends on the isolated wheel checks.

1. [x] WaveBench `0.8.24` at `master` commit `dc7ce5b` contains R1.
2. [x] Classify every plugin transport query explicitly; `CMR?`, `EXR?`, `DDR?`, and acquisition-bound `*OPC?` use `no_replay`.
3. [x] Preserve `TransportIOError` and `SessionHealthError` through `_acquire_once`, OPC waits, and temporary restoration context managers; do not issue a second unauthorized recovery or validation I/O.
4. [x] Plugin fault injection covers transmission counts, `uncertain`/`poisoned` latching, and zero later ordinary I/O. Core baseline tests cover `on_failure=continue` and a new `epoch_id` after close/reconnect. The plugin has no recovery authorization and does not perform `uncertain → healthy`.
5. [x] In one atomic adoption commit, set the wheel `Requires-Dist` and descriptor minimum to `0.8.24`, retain the reviewed `0.9.0` upper bound and `api_version="wavebench.instrument.v2"`, and run isolated wheel, descriptor, entry-point, and API-version compatibility tests.

## Acceptance test matrix

The plugin's `test_core_rfc.py` verifies only this document's JSON structure. Plugin call sites, error priority, and fault injection are covered by `test_driver.py`; shared-session, run, and reconnect contracts remain proven by WaveBench core tests.

| Layer | Required cases | Instrument connection in default CI |
| --- | --- | --- |
| Transport contract | Three replay policies, partial response, single transmission, backend and Guarded consistency | No |
| Session transaction | Zero-I/O preflight, unknown write outcome entering uncertain when synchronization is proven and poisoned when it is not, readback failure, reverse restoration, shared latch, `on_failure=continue` | No |
| Typed read-only state | Read-only and unsupported fields, availability, structured query errors, termination patch rejection before I/O | No |
| Service / CLI / run plan | Capability consumer, OperationSpec, JSON, strict mode, existing v1 regression only, session-health diagnostics | No |
| Plugin version gate | Wheel `Requires-Dist`, descriptor min/max, `api_version`, entry point, and zero-I/O rejection | No |
| Three-vendor fake driver | Only per-value mappings frozen with evidence by the typed-scope RFC; no invented common semantics | No |
| Opt-in hardware | Real transport for released P0/P1 operations, read-only state mappings on approved instruments, and configuration revalidation after reconnect | Yes |

Termination-write safety gates and hardware tests, plus `ScopeSnapshotV2` v1/v2 coexistence tests, move to their own future RFCs and are not R1 acceptance criteria. Empty-patch, invalid-value, conflict, quantized-readback, and restoration matrices for P2 are frozen only when P2 re-enters implementation scope.

## Cross-vendor applicability

| Common problem | SDS3000 | DS1000Z | RTM2000 |
| --- | --- | --- | --- |
| Non-replayable status or synchronization query | Read-to-clear registers and acquisition-bound `*OPC?` | Error and acquisition synchronization queries need explicit policy | The RsInstrument backend still needs a public contract |
| Shared session latch | Capture temporarily changes several state families | Internal capture setters may fail | Stronger restoration exists but is not a core contract |
| Read-only channel, timebase, trigger state | Manual and hardware evidence cover a subset | Coupling and configuration paths exist | Complete snapshots provide a contract baseline |
| Acquisition and trigger state axes | `TRMD?` combines mode with stopped state | The current driver has no read-only status query | A waiting bit and trigger mode are readable, but common run/stop readback is absent |
| Narrow patch | VDIV/TDIV/OFST | Vertical scale and time range | Existing setters and readback provide reference behavior |

P0 foundations apply to every instrument kind and are not SDS3000-specific. P1 and P2 scope capabilities have common semantics across at least three scope families.

## Core changes not made or permanently rejected

- Do not add an SDS3000-specific VICP core backend; the existing PyVISA path works with plugin-owned `PyVICP`.
- Do not replace `query_bin_block()`; the current SDS3054 binary path passed hardware acceptance.
- Do not add a raw screenshot transport for SDS3000; `SCDP?` returns status, not image payload.
- Do not probe instruments or options while loading descriptors.
- Do not relax required v1 model fields in place.
- Permanently reject arbitrary raw SCPI, arbitrary VBS, MAUI `app` reflection, caller-supplied restoration commands, and transport handles that bypass identity, access, or audit controls.

## Recommended implementation order

1. Keep this document as a plugin impact assessment, distinguishing “M8 functionally complete,” “P0 adopted,” and the still-draft typed-scope-state and generic-write proposals.
2. Retain core commit `a8e6b59` as the migration-test baseline and use WaveBench `0.8.24` release commit `dc7ce5b` for runtime version gates.
3. Call-site migration, structured-error handling, and fault injection are complete. Core M7 `OperationSpec` coverage for `scope.capture`, `scope.capture_waveforms`, `scope.capture_multiple`, and `scope.fetch_waveform` includes SDS3000 temporary `CHDR`, `CFMT`, `CORD`, and complete `WFSU` state.
4. Complete one atomic adoption commit: raise the wheel and descriptor minimum versions together, review the upper bound, confirm `api_version`, run isolated compatibility tests, and mark the plugin adopted after all checks pass.
5. Freeze a separate typed-scope state RFC covering channel/timebase/edge-trigger fields, core consumers, v1 precedence, and three-vendor mappings.
6. Implement only frozen typed read-only state with device evidence. Continue collecting SDS3000 firmware and restoration evidence for the released acquisition, trace, screenshot, and error-drain extensions without declaring them early.
7. Review narrow scale, offset, and timebase patches in a separate RFC after safety evidence exists.
8. Revisit termination writes, generic trigger writes, and snapshot v2 separately and last.

No generic scope write API is frozen until the typed-scope RFC, typed read-only state, core consumers, and corresponding contract tests are complete.
