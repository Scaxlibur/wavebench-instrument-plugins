# SP30120 Command Certification Plan

[中文](COMMAND_CERTIFICATION_PLAN.md) | [Command matrix](COMMAND_CERTIFICATION_MATRIX_EN.md)

This document defines per-command certification for the laboratory SP30120. The vendor material covers the SP3000A family and names SP30120A; a family-only `*IDN?` response cannot relabel the non-A target as SP30120A. Every conclusion is scoped to the observed device and firmware behavior.

## Certification states

|State|Meaning|Driver policy|
|---|---|---|
|`verified-read`|At least three stable query cycles with known framing, semantics, and side effects|May enter a typed read API|
|`verified-control`|Snapshot, write, readback, independent effect, restoration, and restored readback all pass|May enter a bounded typed control API|
|`manual-only`|Restricted to a controlled manual experiment, including observed data whose semantics remain open|Retain evidence; advertise no capability|
|`unsupported-firmware`|Canonical syntax under the correct precondition errors, times out, or has no observable effect|Do not send; document the device/firmware boundary|
|`unsafe-quarantined`|Causes loss of communication, a frozen panel, or unreliable recovery|Statically isolate and never retry|
|`option-absent`|Depends on an uninstalled option|Advertise no capability|
|`doc-ambiguous`|Syntax, model scope, or response structure is insufficient for safe certification|Fail closed|
|`untested`|Not yet exercised on hardware|Do not expose|

## Common gates

Each query starts at a quiet serial boundary, uses only canonical manual syntax, and accumulates through LF or a bounded limit. A single low-level `read()` is never a response boundary. Identity and the core state fingerprint are checked after the target query. Errors, timeouts, and silence are not retried automatically.

Every write must:

1. prove a quiet boundary, valid identity, and RF OFF;
2. persist the original value, exact target, exact restoration command, and phase to a private recovery journal;
3. send exactly one target write;
4. confirm it through an independent query or state snapshot;
5. restore the original value and read it back again;
6. reconfirm identity, RF OFF, and the core fingerprint;
7. repeat three complete cycles before becoming `verified-control`.

Missing acknowledgement is not failure by itself because this firmware silently accepts verified `TRIM SING/CONT` writes. A write without verifiable readback or independent effect never passes. Loss of communication, a non-quiet boundary, failed restoration, or a frozen panel stops the run and requires an operator power cycle.

## M0–M3 scope

- **M0:** deduplicate the manual inventory; record parameters, options, OCR ambiguity, and current evidence; build a private one-command runner with explicit resource input, journal-before-write, RF-OFF interlock, fingerprint checks, and quarantine tests.
- **M1:** exercise documented queries that remain inside the M0–M3 safety boundary and have an explicit bounded-response rule. Distinguish no active data, an absent option, and unsupported firmware. A query whose semantics belong to M5 marker measurement or M6 storage is not pulled forward merely because it is syntactically read-only.
- **M2:** certify only reversible low-impact state with reliable query and restoration: beep, display/reference state, clock display, language, single/continuous sweep, trigger state, and low-impact marker visibility/selection. Test remote-to-local behavior separately.
- **M3:** keep RF OFF throughout and certify sweep/measurement configuration: CW/SWEEP, frequency window, CW frequency, offset, sweep timing/automatic mode, averaging, input impedance/range, and amplitude/phase state. Do not repeat rejected trace writes; quarantine `SWET:MODE LOG`.

## Explicitly outside this run

RF ON and real output validation; output level/impedance certification; reset, save, recall, or slot overwrite; automatic marker analysis; unconfirmed external-detector/frequency-discriminator/GPIB option writes; USB/LAN/GPIB transports; and any quarantined or speculative spelling. These require later RF, marker, storage/reset, option, or transport stages.

## 2026-07-25 hardware certification result

This run kept RF OFF throughout. Sixteen low-side-effect queries each accumulated at least five complete successful journals: `CENT?`, `SPAN?`, `STOP?`, `INPLSW?`, `FMT?`, `SETSCALE?`, `SETREFL?`, `SETREFP?`, `SETCTIME?`, `CLOCKSW?`, `LANGSEL?`, and `MARK1?` through `MARK5?`. Every run began at a quiet boundary and rebuilt the complete core fingerprint after the target response.

The following reversible controls each passed three consecutive journal-before-write, one-write, independent-query, full-fingerprint, restore, restore-query, and original-fingerprint cycles:

- `TRIM CONT→SING→CONT`;
- `SETREFP 4→5→4`;
- `CLOCKSW ON→OFF→ON`;
- `LANGSEL CHINESE→ENGLISH→CHINESE`;
- `EXTT OFF→ONSWEE→OFF`.

The final state was independently rechecked as RF OFF, TRIM CONT, reference position 4, clock display ON, Chinese UI, and external trigger OFF, with no active quarantine. RF OFF has one observed one-way ON-to-OFF safety transition only and does not certify generic RF control.

These private certification operations remain disconnected from the production descriptor and driver. Frequency-window writes, display-scale writes, date/time writes, marker visibility, impedances, FUNC, amplitude/phase, and trace configuration remain uncertified or stricter because of coupled state, anomalous responses, missing readback, or firmware failure.

## Code admission

Hardware success first enters an exact protocol/error mapping, then a typed vendor method with FakeTransport and restoration tests, and only then a generic WaveBench capability when the semantics fit. There is no arbitrary SCPI passthrough. Public commits exclude real resources, serial numbers, raw responses, laboratory addresses, and recovery journals. Each feature family receives a separate signed local commit; no automatic push, tag, or release is allowed.
