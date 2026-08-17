# SDG2000X Coverage Milestones

[中文](SDG2000X_COVERAGE_MILESTONES.md)

## M0: Development baseline

- [x] Create an independent distribution, canonical driver ID, and MIT license.
- [x] Add bilingual READMEs, a coverage matrix, and a local-manual directory.
- [x] Implement query-only `source.idn` for both documented identity formats.
- [x] Use a fake transport to verify zero writes, wrong-model rejection, factory behavior, and close lifecycle.
- [x] Verify wheel entry point and licensing, sdist exclusion, and isolated installation discovery.

## M1: Programming-guide audit

- [ ] Place the selected SDG Series Programming Guide revision under `doc/vendor-local/`.
- [ ] Record interfaces, command and response termination, timeouts, and error-queue semantics.
- [ ] Freeze supported models and redacted hardware `*IDN?` samples.
- [ ] Classify channel, output, fixed-wave, modulation, sweep, burst, arbitrary-wave, and counter commands.

## M2: Strict read-only status

- [ ] Implement a CH1/CH2 basic status profile before any write capability.
- [ ] Parse units, enums, channel targets, and relationships fail-closed.
- [ ] Prove the complete profile performs zero writes under a transport guard.
- [ ] Repeat controlled hardware reads without extrapolating to an unaccepted model or firmware.

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

Before hardware access, record the target model, firmware, redacted resource, initial output state, allowed commands, denied commands, success criteria, and restoration steps. Do not connect without explicit authorization.
