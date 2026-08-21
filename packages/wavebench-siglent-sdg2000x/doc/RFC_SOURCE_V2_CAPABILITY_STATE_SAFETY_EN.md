# RFC: Source V2 Capability, State, and Composite-Output Safety

Status: Draft  
Scope: WaveBench core-interface proposal; this repository stores the draft and does not modify core

## Summary

The current Source basics work for identity, fixed-wave status, setters, and output control. Advanced features expose distinctions that cannot be represented safely by adding more required fields or plain `Optional` values: unsupported, mode-inapplicable, intentionally unqueried, unavailable after failure, and semantically unknown states are different.

This RFC proposes an additive Source V2 model with:

- structured model/channel/operation capability descriptions;
- explicit field availability;
- state-activated status facets;
- variable sparse harmonic components;
- a conservative composite-output budget covering harmonics, modulation, noise, combine, load, and offset;
- evidence levels separating offline, protocol, readback, waveform, and physical-trigger acceptance.

The design is intentionally multi-vendor. It covers combined-response and state-dependent sources, DG4000-like sources with scalar queries and an error queue, and third-party instruments that implement only a basic SCPI subset.

## Motivation

Observed incompatibilities include:

- Noise/DC legitimately return `SourceStatus.amplitude=None`, while the current service calls `isfinite()` and raises raw `TypeError` before output control.
- Some harmonic queries are valid only in SINE mode; treating every query as unconditionally read-only can timeout and poison a transport session.
- Disabled modulation, burst, and counter subsystems may return only `STATE,OFF`, while current profiles require every active-mode parameter.
- The current harmonic profile requires exactly H2–H16 and has no `enabled` field. Some instruments support a different maximum order or return only the selected component.
- Pulse responses may contain both width and duty but omit the driver's required hold mode.
- Sweep, burst, counter, and coupling field sets differ materially across vendors.

Basic Vpp is not a complete safety budget. Harmonics, AM envelope, noise peaks, DC level, channel combine, display-load compensation, frequency derating, and shared power limits can all change the actual terminal waveform.

## Proposal

### Capability description

Keep coarse capability IDs for routing and add structured details:

```python
@dataclass(frozen=True)
class SourceFeatureCapability:
    feature: str
    support: SupportState
    operations: frozenset[SourceOperation]
    channels: frozenset[int]
    modes: frozenset[str]
    constraints: Mapping[str, object]
    evidence_ref: str | None = None
```

Read support does not imply write support, and internal trigger acceptance does not imply an external Gate connection was tested.

### Availability

```python
class Availability(str, Enum):
    VALUE = "value"
    UNSUPPORTED = "unsupported"
    NOT_APPLICABLE = "not_applicable"
    NOT_QUERIED = "not_queried"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Observed(Generic[T]):
    availability: Availability
    value: T | None = None
    reason_code: str | None = None
    evidence: tuple[str, ...] = ()
```

Only `VALUE` participates in numeric safety calculations. A safety-relevant `UNAVAILABLE` or `UNKNOWN` value must fail output enable closed.

### Facets and state-dependent queries

Source V2 groups basic, output, harmonic, modulation, sweep, burst, pulse, and arbitrary state into facets. Query planning reads anchors first, activates only legal facet queries, and rereads anchors at the end. A changed anchor marks the snapshot inconsistent.

Harmonic-only-in-SINE behavior is one activation rule, not a vendor field in core.

### Harmonics

```python
@dataclass(frozen=True)
class HarmonicComponent:
    order: int
    enabled: Observed[bool]
    amplitude: Observed[ComponentAmplitude]
    phase_deg: Observed[float]


@dataclass(frozen=True)
class HarmonicFacet:
    enabled: bool
    selection: str
    components: tuple[HarmonicComponent, ...]
    maximum_supported_order: int | None
    completeness: str
    amplitude_semantics: str
```

Components are unique by order and may be sparse. A selected-only response must not fabricate every unobserved order as zero. Write requests explicitly choose patch or replace-all semantics.

### Composite safety budget

```python
@dataclass(frozen=True)
class CompositeOutputBudget:
    dc_offset_v: float
    ac_peak_upper_v: float
    minimum_v_lower: float
    maximum_v_upper: float
    vpp_upper_v: float
    rms_upper_v: float | None
    display_load_ohm: float | None
    actual_termination_ohm: Observed[float]
    confidence: BudgetConfidence
    contributors: tuple[SafetyContributor, ...]
```

For independent sinusoidal components, a conservative bound is:

```text
A_ac,max <= sum(abs(A_k))
V_min >= offset - A_ac,max
V_max <= offset + A_ac,max
Vpp_max <= 2 * A_ac,max
```

AM multiplies by the maximum envelope factor. Combine sums channel contributors conservatively. Sweep uses the maximum across its path. Noise cannot claim a proven deterministic peak bound without an explicit model.

Output enable checks Vpp, absolute voltage, display-load versus actual termination, frequency derating, shared limits, and availability of every contributing facet.

### Transactions

V2 uses one target write per field, independent full readback, closure verification, no retry after an unknown result, fail-safe OFF, independent OFF verification, and a session mutation latch after ambiguity or failed recovery. An error queue is optional supporting evidence, not a universal requirement.

### Acceptance levels

| Level | Evidence |
| --- | --- |
| A0 | Offline fixtures and fault injection |
| A1 | Hardware read-only query legality and response shape |
| A2 | Safe output ON/OFF and recovery |
| A3 | Oscilloscope loop for basic waveform behavior |
| A4 | Harmonic spectrum, modulation envelope, sweep path, burst count |
| A5 | Real external trigger, Gate, Sync, or inter-channel timing wiring |

Reports record model, firmware, port map, termination, safety budget, set/read/measured values, tolerance, final OFF, and explicit gaps.

## Compatibility and migration

1. Keep V1 unchanged.
2. Add V2 capabilities or a descriptor schema version explicitly.
3. Adapt V1 basic/output state into minimal V2 facets.
4. Permit lossy V2-to-V1 flattening for display only, never advanced safety decisions.
5. Prefer V2 for new advanced capabilities; do not keep adding vendor-special fields to V1.
6. Drivers declare legacy advanced capabilities only when mapping is lossless.

## Rejected alternatives

- More plain `Optional` fields: availability semantics remain ambiguous.
- Vendor-specific core fields: core becomes a protocol catalog.
- Zero/default placeholders: creates false harmonic, burst, and modulation state.
- Hidden writes inside a query-only profile: violates access semantics and read-only sessions.

## Suggested phases

1. Add availability, facets, and structured capability descriptions.
2. Return typed configuration errors for non-value basic fields.
3. Add state-dependent query planning and consistency checks.
4. Add composite-output safety budgeting and termination evidence.
5. Migrate harmonic, modulation, pulse, sweep, and burst.
6. Migrate counter, coupling, arbitrary waveform, and device-level multi-channel budgets.
7. Add an acceptance-evidence schema and report aggregation.

## Acceptance criteria

- Two existing sources with materially different protocols complete pilot migrations.
- A basic-only third-party driver needs no fake advanced fields.
- Harmonics express different maximum orders, sparse components, selected-only completeness, and enabled state.
- Noise/DC and disabled facets never cause raw `TypeError`.
- Unknown/unavailable safety contributors fail output enable closed.
- Display-load/high-impedance voltage-doubling risk is representable.
- A report cannot claim A5 without physical trigger/sync wiring.
- Existing V1 basics and configuration continue to work.
