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
- [x] With outputs enabled, cross-check CH1/CH2 physical frequency, Vpp, and mean voltage on the RTM2032.

## M3: Basic write transactions

- [x] Evaluate and expose `source.output` separately; keep frequency, function, amplitude, and duty-cycle work separate.
- [x] Read complete pre-state. Enabling requires FIX, sweep OFF, and known Vpp amplitude and offset.
- [x] Send the target write once and verify it through an independent complete status query.
- [x] Latch further ON writes after a post-write failure, recover OFF, and report uncertain state when recovery fails.
- [x] Complete 4 Vpp high-impedance closed-loop acceptance on SDG2122X CH1/CH2 and leave both outputs OFF.
- [x] Expose `source.set_frequency` separately with model/function limits, complete safety snapshots, one-write readback, OFF recovery, and a session latch.
- [x] Complete SDG2122X CH2 closed loops for a 2 kHz OFF-state write and a live 5 kHz ON-state write; restore 1 kHz and leave both outputs OFF.
- [x] Expose `source.set_amplitude_vpp` separately with a 2 mVpp through 10 Vpp range and a joint offset-envelope check.
- [x] Expose `source.set_function` separately; allow live switching among four bounded periodic waves and require output OFF for Noise/DC.
- [x] Expose `source.set_square_duty_cycle` separately for FIX-mode square waves from 0.001% through 99.999%; reject clamped values through independent readback.
- [x] Complete SDG2122X CH2 loops for frequency, amplitude, four periodic functions, and 20%/80% square duty; restore Sine / 1 kHz / 4 Vpp and leave both outputs OFF.

## M4: Advanced command domains

- [ ] Treat modulation, sweep, burst, arbitrary-wave, and counter work as separate tasks rather than a raw-SCPI interface.
- [ ] Document irreversible or volatile effects for triggers and arbitrary-wave upload.
- [ ] Declare a capability only after its public WaveBench model and service consumer are defined.

## Hardware gate

Before hardware access, record the target model, firmware, redacted resource, initial output state, allowed commands, denied commands, success criteria, and restoration steps. The 2026-08-21 M3 acceptance set a 10 Vpp maximum and used 4 Vpp. Each channel received one ON and one OFF write, followed by independent new-session confirmation that both outputs were OFF.
