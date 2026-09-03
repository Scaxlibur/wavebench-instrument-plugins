# SDS800X HD Feature-Coverage Development Roadmap

[中文](SDS800X_HD_COVERAGE_MILESTONES.md)

> Type: Development

This page records development stages, pending scope, and exit gates for new SDS800X HD
capabilities. It does not maintain the current capability list or repeat device, firmware, and
measurement results. The [production descriptor](../src/wavebench_siglent_sds800x_hd/descriptor.py)
is authoritative for current capabilities. See the [coverage matrix](SDS800X_HD_COVERAGE_MATRIX_EN.md)
for manual-domain mapping and current behavior, and the
[hardware acceptance record](SDS800X_HD_HARDWARE_ACCEPTANCE_EN.md) plus
[Scope R1.3 conformance](SDS800X_HD_R13_CONFORMANCE.md) for device-specific evidence.

## Shared rules

- A command in the shared SDS manual is not automatically an SDS800X HD capability. Check model,
  firmware, and the production descriptor first.
- A new Core contract does not automatically apply to the plugin. Driver, profile, descriptor, and
  hardware restoration evidence are completed separately.
- A Python method or offline test does not constitute a capability. Only descriptor declarations
  belong to the current public surface.
- Instrument I/O uses the Core transport; no raw-SCPI entry point is added.
- Hardware results apply only to the recorded device, firmware, transport, and procedure and are
  not projected onto other models or connection types.
- Reset, Autoset, system configuration, and instrument-file operations stay outside the base driver.

## Stage status

| Stage | Scope | Current development state | Next exit gate |
|---|---|---|---|
| M1 | Strict identity and query-only coupling | Capabilities declared | Each new model needs independent identity, channel-count, and response verification. |
| M2 | Preamble parsing, conversion, stopped-record waveform transaction | Implemented with offline tests | New formats require complete descriptor-length, byte-order, point-count, and failure-restoration tests. |
| M3 | TCPIP WORD/LSB, chunking, transfer restoration, Sequence rejection | Controlled hardware evidence exists | USB and additional models need separate acceptance; evidence belongs in Acceptance, not Current Reference. |
| M4 | SINGLE, Stop polling, single/multi-channel capture | Capabilities declared | A new acquisition mode needs independent completion proof, failure cleanup, and fresh readback. |
| R1.3 adoption | Screenshot and acquisition run-state/control | Capabilities and descriptor profiles declared | Profile changes must verify framing, budgets, state restoration, and conformance together. |

## Future capabilities

| Work item | Current development state | Next exit gate |
|---|---|---|
| Typed trace metadata/fetch | Not declared | Resolve the Core point limit versus supported long records; add a complete transfer baseline, profile, and hardware fresh readback. |
| Error drain | Not declared | CN11G provides no reliable queue command. Keep unavailable without real protocol evidence; never fabricate an empty result. |
| Math/FFT | No corresponding extension capability declared | Define an accurate contract for frequency axis, ready state, RBW, sample rate, and payload first. |
| Digital channels | Not declared | Confirm options, electrical thresholds, encoding, bit order, and restoration semantics. |
| Sequence/history | Not declared | Define frame identity, timestamps, appended preamble data, and bounded reads first. |
| Snapshot and configuration | Not declared | Prove each field's readability, applicability, write side effects, and complete restoration; do not create a falsely complete model. |
| Autoset | Denied by default | Review separately only after trigger, vertical, and timebase state can be saved and restored. |
| Other writes | Not declared | Model each domain separately; raw SCPI does not bypass capability and restoration gates. |

## Exit gate for each new capability

1. A Core typed model accurately represents values, inapplicable fields, and errors for this family.
2. Driver method, descriptor capability, profile, configuration fields, and permissions agree.
3. Exact FakeTransport tests cover normal behavior, malformed framing, invalid enums, timeout, and restoration failure.
4. Binary reads define framing, payload limits, trailing bytes, chunking, and resynchronization boundaries.
5. Writes or acquisition control have snapshot, readback, failure cleanup, fresh verification, and required latching.
6. Controlled hardware acceptance records model, firmware, transport, and unaccepted scope without resources, serials, or raw data.
7. Chinese/English Current Reference, navigation, generated plugin catalog, and package tests pass together.
