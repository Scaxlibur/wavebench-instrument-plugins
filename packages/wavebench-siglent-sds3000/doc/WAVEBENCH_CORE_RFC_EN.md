# WaveBench Core RFC: SDS3000 Impact Assessment

[中文](WAVEBENCH_CORE_RFC.md)

> Status: `Draft / Needs revision`
> Revision: `R1`
> Core baseline: WaveBench `0.8.22`
> API status: not frozen
> Core implementation: not started

## Conclusion

The SDS3054 plugin is functionally complete through M8, while P0 safety hardening remains pending. Its six declared capabilities—identity, error registers, channel coupling, waveform fetch, single-channel capture, and same-acquisition multi-channel capture—do not depend on new interfaces from this RFC. VICP text and binary waveform operations passed hardware acceptance through the existing `PyVisaTransport`, `PyVICP`, and `query_bin_block()` path. Those results do not claim that non-replayable queries or shared session health are implemented.

This document is suitable as a core impact assessment and implementation roadmap, but it is not a directly implementable or accepted public API specification. The first draft placed read-only state, generic patches, and partial status v2 too close together without fully defining replay policy, shared-session latching, field permissions, core consumers, or electrical safety gates. R1 promotes those foundations to P0 and defers generic writes and `ScopeSnapshotV2`. Separate transport and typed-scope RFCs must be frozen before core implementation begins.

The machine-readable form is [`wavebench-core-rfc.json`](wavebench-core-rfc.json). This branch does not modify WaveBench core or depend on unpublished interfaces.

## Stage labels

Plugin milestones and RFC revisions use separate labels so that a completed plugin does not imply a frozen core API:

| Subject | Current state | Meaning |
| --- | --- | --- |
| SDS3000 plugin | `M8-functional-complete` | The current six capabilities passed their offline and hardware gates; P0 safety hardening remains pending |
| This RFC | `R1-draft-needs-revision` | Contracts remain open to revision; the public API is not frozen |
| WaveBench core implementation | `not-started` | No implementation commit or plugin minimum-version increase exists |

## Specifications required before core implementation

R1 defines problem boundaries, priorities, and implementation order only. Two separate specifications are prerequisites for coding:

| Separate specification | Required frozen content | Gate |
| --- | --- | --- |
| Transport replay/session RFC | The default policy of existing `query()`, migration of old call sites, structured transport errors, command transmission count, partial responses, desynchronization, session-health ownership, recovery authorization, state-validation scope, and fail-closed behavior when a backend cannot support `read_continuation_only` | Before any P0 core implementation |
| Typed scope state RFC | Exact fields, `Protocol` signatures, static and runtime field support, `OperationSpec`, Service/CLI/run-plan consumption, v1 precedence, error envelopes, and three-vendor mappings | Before any P1 capability is frozen |

The transport RFC must distinguish source compatibility from observable behavior compatibility. Migrating consuming reads from automatic retries to `no_replay`, and stopping later instrument I/O on a poisoned session under `on_failure=continue`, are observable changes and cannot be described as entirely additive.

The transport RFC must also freeze three session contracts: the single authoritative owner and lifecycle of health state; the transaction coordinator allowed to perform plugin-declared bounded recovery and validation under the session lock while state is `uncertain`; and the communication synchronization, identity continuity, affected-field closure, and plugin-declared invariants required to leave `uncertain` or trust configuration after reconnect. Ordinary Service calls receive no recovery authority and cannot treat unverified configuration as healthy.

## Confirmed core facts

| Interface or model | Current conclusion | Follow-up |
| --- | --- | --- |
| `InstrumentTransport.query_bin_block()` | Sufficient for the current SDS3054 binary path and not replayed in the same session after failure | Preserve non-replayable behavior in a common transport contract |
| `PyVisaTransport.query()` / `query_opc()` | VICP works, but text queries and `*OPC?` enter the general read-retry path | Add an explicit replay policy in P0; do not resend consuming reads or acquisition-bound `*OPC?` |
| `OperationSpec.effect=acquire` | Already requires `read_write`; no new effect is needed solely for access control | `changed_fields` and restoration audit are incomplete and remain core gaps |
| `ScopeStatusSummary` | Already returns IDN, coupling, and missing capabilities | Reuse the existing partial-status path before adding a broad snapshot v2 |
| `PyVisaTransport` plus `PyVICP` | Sufficient for the current VICP text and binary connection | Do not add an SDS3000-specific core transport |

## P0-1: Non-replayable query contract

### Problem

`InstrumentTransport` has no replay policy or common `query_once()` contract. `PyVisaTransport.query()` and `query_opc()` can resend the complete query. SDS3000 `CMR?`, `EXR?`, and `DDR?` are read-to-clear registers: the first request may consume the state, while a retry after timeout may return an empty value and hide the original error.

`RsInstrumentTransport` and `SerialTransport` do not currently apply the same explicit retry loop, but that is not a backend-independent guarantee. `GuardedAuditedTransport` only delegates to its inner transport.

### Minimum behavior

R1 does not freeze final method names, but the implementation must define at least three explicit policies:

```text
safe_to_replay
no_replay
read_continuation_only
```

- `safe_to_replay`: used only when the caller explicitly declares that the query may be resent. The transport never infers safety from SCPI text.
- `no_replay`: transmits the command at most once. Timeout, partial response, or ambiguous completion never resends the command.
- `read_continuation_only`: may continue reading an already transmitted response but must not resend the command.

`query_once()` may be a convenience entry point, but it cannot replace the underlying contract. Every backend must make command transmission count, response continuation, partial response, and communication uncertainty observable.

The following calls default to `no_replay`:

- read-to-clear registers;
- acquisition-bound `*OPC?`;
- requests after any response byte has arrived;
- status reads whose replay safety cannot be proven.

Independent status polling may opt into replay only through an explicit operation contract. Not every `*OPC?` use has identical semantics.

### P0 exit gate

- PyVISA, RsInstrument, Serial, `GuardedAuditedTransport`, and FakeTransport share one replay contract.
- Fault injection proves that a failed `no_replay` query transmits at most once.
- `read_continuation_only` tests prove that response reading can continue without another command write.
- Telemetry records replay policy, partial response, and uncertainty without recording sensitive payloads.
- SDS3000 `CMR?`, `EXR?`, and `DDR?` migrate only after the core primitive is released.

## P0-2: Shared session health and poison latch

### State model

```text
healthy -> uncertain -> poisoned -> closed
```

This axis describes whether the communication session is trustworthy. Instrument configuration verification is a separate `verified/unverified` marker. A newly connected or reconnected communication session may be `healthy`, but its configuration starts `unverified` and becomes `verified` only after an explicit read-only baseline check.

Transitions may skip states. An unknown write result enters `uncertain` when the transport can still prove synchronization; only bounded restoration and verification are then permitted. A possibly desynchronized channel enters `poisoned` immediately. `uncertain` returns to `healthy` only when the channel remains synchronized and restoration is independently read back. `poisoned` cannot recover within the original session.

| Phase | Result | Session behavior |
| --- | --- | --- |
| Preflight rejection | No I/O occurred | Remains `healthy` |
| New connection or reconnect | Communication channel is re-established | `healthy + unverified`; only explicit baseline verification is allowed before configuration is trusted |
| Unknown write result | The instrument may have changed | Becomes `uncertain` if synchronization is proven; otherwise immediately `poisoned` |
| Post-write readback failure | Current value cannot be proved | Becomes `uncertain`; only restoration and verification I/O are allowed |
| Restoration failure | Original state is unknown | `poisoned` |
| Restoration success | The channel is synchronized and original state passes tolerance checks | Returns from `uncertain` to `healthy + verified` and records actual quantized values |
| Close | Session is no longer usable | `closed` |

### Responsibility split

- Core: replay policy, common error taxonomy, shared session health, pre-operation gate, and `on_failure=continue` stop behavior.
- Plugin: affected-field closure, snapshots, restoration order, vendor-valid combinations, and quantization tolerance.
- Transport: whether a command was transmitted, whether a response was partial, and whether the communication channel may be desynchronized.

The latch belongs to the shared driver/session, not a temporary `ScopeService`. Run plans reuse one scope session. When a failed step specifies `on_failure=continue`, every later instrument operation on a poisoned session must fail before transport I/O. Only local audit, closing the old session, and establishing a new session remain available as lifecycle actions. Reconstructing a Service does not clear the latch.

### Distinct error classes

- Preflight or validation error: zero I/O, healthy session.
- Write failure proven before transmission: failed operation, reusable session.
- Unknown write result with a synchronized channel: uncertain session, limited to restoration and verification.
- Desynchronized or unprovably synchronized channel: poisoned session.
- Readback mismatch: failed transaction followed by restoration.
- Restoration failure: `StateDriftError` plus poisoned session.
- Later operation on a poisoned session: stable session-health error before I/O.

## P1-1: Typed read-only state

After P0, the first scope capabilities are read-only:

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

## P1-2: Candidate acquisition-state axes

`scope.acquisition_run_state` is currently only a candidate name. It is not in the implementation queue, and R1 does not freeze a single `run/stop/wait/armed` enum. Continuous acquisition state and trigger phase are different semantic axes. At minimum, the typed-scope RFC must evaluate:

- execution state: running, stopped, and unknown;
- trigger phase: idle, waiting, armed, triggered, and unknown;
- trigger mode: auto, normal, single, and unknown.

These names and values are design inputs, not public API. Average, segmented acquisition, option inventory, and history frame counts remain separate capabilities.

| Vendor | Current evidence | Mappable content | Unresolved issue |
| --- | --- | --- | --- |
| SDS3000 | `TRMD?` returns `AUTO/NORM/SINGLE/STOP` | `STOP` proves only stopped; the other tokens are closer to trigger mode | Running, waiting, and armed cannot be distinguished; `SEQ` remains `firmware-unverified` and is excluded as evidence |
| DS1000Z | The current driver has only `:STOP`, `:SINGle`, and `*OPC?` synchronization | Actions and completion synchronization only; no read-only state mapping | Manual review and controlled read-only evidence are required; current state cannot be inferred from the last command |
| RTM2000 | `STATUS:OPERation:CONDITION?` bit 3 and `TRIGger:A:MODE?` | Waiting-for-trigger and the supported trigger-mode subset | The current driver has no common running/stopped readback |

The typed-scope RFC must define per-value mappings for all three vendors, unmappable values, static support, and runtime unavailability. A query failure remains an operation error; `unknown` means that the instrument returned successfully but could not be mapped. No public capability is frozen until at least one axis has verifiable readback on all three vendors.

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

The broad proposal is split and deferred. R1 does not freeze `scope.acquisition_run_state`; the typed-scope RFC must first resolve three-vendor mappings for execution, trigger phase, and trigger mode. Average, segmented, and option status later receive separate typed capabilities. Existing v1 models remain unchanged.

## Core consumption and compatibility contract

Every new capability requires:

- a `Protocol` and typed model;
- `OperationSpec`, effect, risk, timeout, `changed_fields`, and restoration coverage;
- a `ScopeService` method;
- stable JSON and error envelope;
- strict behavior and v1/v2 precedence;
- an explicit statement of whether CLI and run plans are included in the first release.

New symbols should remain source-additive: existing `scope.channel_coupling`, capture arguments, v1 snapshot, and acquisition status types do not change in place. R1 does not freeze the default replay policy of existing `query()`. Moving consuming reads to `no_replay`, replacing implicit retries with structured errors, and blocking later I/O under `on_failure=continue` on a poisoned session are intentional observable behavior changes. The transport RFC must include a call-site migration inventory, release notes, and regression tests. The plugin raises its minimum WaveBench version only after a core release.

## Release and version gates

The current plugin uses three concurrent version gates. Wheel metadata declares `wavebench>=0.8.22,<0.9`; the descriptor declares `wavebench_min_version="0.8.22"` and `wavebench_max_version="0.9.0"`; and the descriptor explicitly declares `api_version="wavebench.instrument.v2"`. These independently gate dependency resolution, runtime core compatibility, and the executable plugin API.

Before the plugin adopts P0 core behavior:

1. P0 must exist in a released WaveBench version rather than an unpublished commit.
2. The wheel and descriptor lower bounds move together to the first P0 release, and the upper bound is reviewed again.
3. The current `api_version` remains only if `wavebench.instrument.v2` stays compatible. An incompatible executable-plugin contract requires a new core API version and a matching literal in the plugin descriptor.
4. Registry validation rejects an API or core-version mismatch before driver-factory or transport I/O.
5. Isolated wheel installation tests verify `Requires-Dist`, descriptor bounds, `api_version`, and the entry point together.

R1 does not raise any current version gate.

## Acceptance test matrix

The plugin's `test_core_rfc.py` verifies only this document's JSON structure. It does not prove that core behavior exists. Behavioral contracts belong in the WaveBench core repository.

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

1. Merge R1 as an impact assessment and implementation roadmap while keeping “M8 functionally complete, P0 safety hardening pending,” RFC R1, and core-not-started status distinct.
2. Freeze a separate transport replay/session RFC, then implement replay policy, non-replayable queries, structured errors, and session gates on a separate WaveBench branch.
3. Complete P0 transport and shared-session contract tests.
4. Audit the `OperationSpec` of `scope.capture`, `scope.capture_waveforms`, `scope.capture_multiple`, and `scope.fetch_waveform` for actual side effects, `changed_fields`, risk, and restoration coverage.
5. Freeze a separate typed-scope state RFC covering channel/timebase/edge-trigger fields, core consumers, v1 precedence, and three-vendor mappings.
6. Implement only frozen typed read-only state. Continue collecting three-vendor acquisition-state evidence without promising `scope.acquisition_run_state`.
7. After a formal P0 core release, raise the wheel and descriptor version gates together and review `api_version` before the plugin adopts the new behavior.
8. Review narrow scale, offset, and timebase patches in a separate RFC after safety evidence exists.
9. Revisit termination writes, generic trigger writes, and snapshot v2 separately and last.

No generic scope write API is frozen until both P0 exit gates pass.
