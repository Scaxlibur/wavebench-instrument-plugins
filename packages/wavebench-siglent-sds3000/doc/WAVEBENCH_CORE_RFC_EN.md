# WaveBench Core RFC: SDS3000 Impact Assessment

[中文](WAVEBENCH_CORE_RFC.md)

> Status: `Draft / Needs revision`
> Revision: `R1`
> Core baseline: WaveBench `0.8.22`
> API status: not frozen
> Core implementation: not started

## Conclusion

The SDS3054 plugin has completed M0–M8. Its six declared capabilities—identity, error registers, channel coupling, waveform fetch, single-channel capture, and same-acquisition multi-channel capture—do not depend on new interfaces from this RFC. VICP text and binary waveform operations passed hardware acceptance through the existing `PyVisaTransport`, `PyVICP`, and `query_bin_block()` path.

This document remains a core impact assessment and pre-implementation specification, not an accepted public API. The first draft placed read-only state, generic patches, and partial status v2 too close together without fully defining replay policy, shared-session latching, field permissions, core consumers, or electrical safety gates. R1 promotes those foundations to P0 and defers generic writes and `ScopeSnapshotV2`.

The machine-readable form is [`wavebench-core-rfc.json`](wavebench-core-rfc.json). This branch does not modify WaveBench core or depend on unpublished interfaces.

## Stage labels

Plugin milestones and RFC revisions use separate labels so that a completed plugin does not imply a frozen core API:

| Subject | Current state | Meaning |
| --- | --- | --- |
| SDS3000 plugin | `M8-complete` | The current six capabilities passed their offline and hardware gates |
| This RFC | `R1-draft-needs-revision` | Contracts remain open to revision; the public API is not frozen |
| WaveBench core implementation | `not-started` | No implementation commit or plugin minimum-version increase exists |

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

Transitions may skip states; an unknown write outcome can move directly from `healthy` to `poisoned`. Only closing the old session and reconnecting can create a new `healthy` session.

| Phase | Result | Session behavior |
| --- | --- | --- |
| Preflight rejection | No I/O occurred | Remains `healthy` |
| Unknown write result | The instrument may have changed | Immediately `poisoned` |
| Post-write readback failure | Current value cannot be proved | Becomes `uncertain`; moves to `poisoned` unless restoration is proven |
| Restoration failure | Original state is unknown | `poisoned` |
| Restoration success | Original state passes tolerance checks | Returns to `healthy` and records actual quantized values |
| Close | Session is no longer usable | `closed` |

### Responsibility split

- Core: replay policy, common error taxonomy, shared session health, pre-operation gate, and `on_failure=continue` stop behavior.
- Plugin: affected-field closure, snapshots, restoration order, vendor-valid combinations, and quantization tolerance.
- Transport: whether a command was transmitted, whether a response was partial, and whether the communication channel may be desynchronized.

The latch belongs to the shared driver/session, not a temporary `ScopeService`. Run plans reuse one scope session. When a failed step specifies `on_failure=continue`, later instrument work still rejects a poisoned session before I/O. Reconstructing a Service does not clear the latch.

### Distinct error classes

- Preflight or validation error: zero I/O, healthy session.
- Write failure proven before transmission: failed operation, reusable session.
- Unknown write result: poisoned session.
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

Field state distinguishes:

```text
unsupported
supported_but_not_readable
query_failed
stale_or_unknown
valid_value
```

`query_failed` is an operation failure, not an unsupported feature, and must not silently become a successful partial result.

### Composite analog-input semantics

SDS3000 `A1M/D1M/D50/GND` encodes coupling and termination together. They cannot be treated as two independent writable fields. The first state model may expose normalized coupling, termination, and a typed composite input state, but termination remains read-only and all legal or unrepresentable combinations must be defined.

## P1-2: Minimal acquisition run state

Start with one narrow capability:

```text
scope.acquisition_run_state
```

It represents a closed set such as run, stop, wait, armed, and an explicit unknown value. Average, segmented acquisition, option inventory, and history frame counts remain separate capabilities.

A query failure remains an operation error, not `unknown`. `unknown` means that the instrument returned successfully but cannot be mapped to a more specific public state.

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

`changed_fields` describes instrument fields that may be touched during the transaction, not only values retained after completion. Existing `scope.capture`, `scope.capture_waveforms`, and `scope.fetch_waveform` specs also require an audit of timebase, vertical scale, trace, trigger mode, and waveform-transfer state.

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

The broad proposal is split and deferred. Implement `scope.acquisition_run_state` first. Average, segmented, and option status later receive separate typed capabilities. Existing v1 models remain unchanged.

## Core consumption and compatibility contract

Every new capability requires:

- a `Protocol` and typed model;
- `OperationSpec`, effect, risk, timeout, `changed_fields`, and restoration coverage;
- a `ScopeService` method;
- stable JSON and error envelope;
- strict behavior and v1/v2 precedence;
- an explicit statement of whether CLI and run plans are included in the first release.

All changes remain additive. Existing `scope.channel_coupling`, capture arguments, v1 snapshot, and acquisition status types do not change in place. The plugin raises its minimum WaveBench version only after a core release.

## Acceptance test matrix

The plugin's `test_core_rfc.py` verifies only this document's JSON structure. It does not prove that core behavior exists. Behavioral contracts belong in the WaveBench core repository.

| Layer | Required cases | Instrument connection in default CI |
| --- | --- | --- |
| Transport contract | Three replay policies, partial response, single transmission, backend and Guarded consistency | No |
| Session transaction | Zero-I/O preflight, unknown write result, readback failure, reverse restoration, shared latch, `on_failure=continue` | No |
| Typed state / patch | Empty patch, read-only, unsupported, invalid values, conflicts, `UNSET`, quantization | No |
| Service / CLI / run plan | Capability consumer, OperationSpec, JSON, strict mode, v1 regression, session-health diagnostics | No |
| Three-vendor fake driver | Common semantics for SDS3000, DS1000Z, and RTM2000 | No |
| Opt-in hardware | Real transport, approved wiring, safe writes, failure recovery, and fresh-session verification | Yes |

## Cross-vendor applicability

| Common problem | SDS3000 | DS1000Z | RTM2000 |
| --- | --- | --- | --- |
| Non-replayable status or synchronization query | Read-to-clear registers and acquisition-bound `*OPC?` | Error and acquisition synchronization queries need explicit policy | The RsInstrument backend still needs a public contract |
| Shared session latch | Capture temporarily changes several state families | Internal capture setters may fail | Stronger restoration exists but is not a core contract |
| Read-only channel, timebase, trigger state | Manual and hardware evidence cover a subset | Coupling and configuration paths exist | Complete snapshots provide a contract baseline |
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

1. Review R1 and keep plugin M8, RFC R1, and core-not-started status distinct.
2. Implement replay policy, non-replayable query primitives, and transport contract tests on a separate WaveBench branch.
3. Implement shared session health, poison semantics, error taxonomy, and run-plan gates.
4. Implement typed read-only channel, timebase, and edge-trigger state.
5. Implement `scope.acquisition_run_state`.
6. Review narrow scale, offset, and timebase patches after safety evidence exists.
7. Revisit termination, generic trigger writes, and snapshot v2 last.

No generic scope write API is frozen until both P0 exit gates pass.
