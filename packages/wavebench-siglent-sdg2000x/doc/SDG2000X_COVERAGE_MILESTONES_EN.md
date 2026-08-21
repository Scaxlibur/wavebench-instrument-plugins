# SDG2000X Coverage Milestones

[中文](SDG2000X_COVERAGE_MILESTONES.md)

## M0: Development baseline

- [x] Create an independent distribution, canonical driver ID, and MIT license.
- [x] Add bilingual READMEs, a coverage matrix, and a local-manual directory.
- [x] Implement query-only `source.idn` for both documented identity formats.
- [x] Use a fake transport to verify zero writes, wrong-model rejection, factory behavior, and close lifecycle.
- [x] Verify wheel entry point and licensing, sdist exclusion, and isolated installation discovery.

## M1: Programming-guide audit

- [x] Place the `PG02_E05C` SDG Series Programming Guide under `doc/vendor-local/`.
- [x] Record interfaces, command termination, and transport ownership; confirm that the guide defines no error-queue query.
- [x] Freeze the three supported models from the datasheet and record both `*IDN?` response formats.
- [x] Record a redacted `*IDN?` sample from `SDG2122X` firmware `2.01.01.39R7T2`; other models remain pending.
- [x] Classify channel, output, fixed-wave, modulation, sweep, burst, arbitrary-wave, and counter commands.

## M2: Strict read-only status

- [x] Implement CH1/CH2 `SourceStatus` before any write capability.
- [x] Parse units, enums, channel targets, and relationships fail-closed.
- [x] Prove complete status reads perform zero writes under a fake-transport guard.
- [x] Complete three stable CH1/CH2 rounds on one `SDG2122X`; the transport audit recorded zero write requests and the conclusion is not extrapolated.
- [ ] With outputs enabled, cross-check physical frequency, Vpp, and offset on the oscilloscope.

## M3: Basic write transactions

- [ ] Evaluate frequency, function, amplitude, duty-cycle, and output capabilities separately.
- [ ] Read restorable pre-state and confirm output OFF where required.
- [ ] Send each write once and verify it through an independent query.
- [ ] Latch further writes after ambiguity and report uncertain state when restoration fails.

## M4: Advanced command domains

- [ ] Treat modulation, sweep, burst, arbitrary-wave, and counter work as separate tasks rather than a raw-SCPI interface.
- [ ] Document irreversible or volatile effects for triggers and arbitrary-wave upload.
- [ ] Declare a capability only after its public WaveBench model and service consumer are defined.

## Hardware gate

Before hardware access, record the target model, firmware, redacted resource, initial output state, allowed commands, denied commands, success criteria, and restoration steps. The 2026-08-21 acceptance allowed identity and status queries only, and both outputs remained OFF. Output enable and oscilloscope capture still require separate authorization.
