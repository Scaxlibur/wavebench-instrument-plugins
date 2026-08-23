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
- [x] Complete CH1/CH2 A4 loops through core `SourceService` for all five basic writes; all 23 writes completed with zero unknown outcomes.

## M4: Advanced command domains

- [x] Complete SDG2122X A4 spectrum acceptance for H2–H16 slots, H2/H3 amplitude, H2 phase, and ALL/EVEN/ODD; do not declare a lossy legacy capability.
- [x] Complete SDG2122X output-OFF protocol and A4 waveform acceptance for internal AM, DSB-AM, FM, PM, PWM, ASK, FSK, and PSK; external sources remain unwired.
- [x] Complete SDG2122X Sweep protocol and A4 waveform acceptance for LINE/LOG/STEP, UP/DOWN/UP_DOWN, and INT/MAN; EXT and Trigger Out remain unwired.
- [x] Complete SDG2122X finite INT/MAN Burst protocol and A4 cycle-count acceptance; EXT/Gate remain readback-only and INF failed physical acceptance.
- [x] Complete SDG2122X Pulse WIDTH/DUTY/RISE/FALL protocol and A4 waveform acceptance; DLY remains A3 and hold has no authoritative query field.
- [x] Complete core-Service zero-write `source.arbitrary_probe` acceptance on SDG2122X CH1/CH2; the real built-in catalog contains 199 entries.
- [x] Complete DDS selection, readback, and A4 non-flat-output smoke acceptance for 199/199 SDG2122X built-ins without upload or filesystem writes.
- [x] Complete A4 for Noise, -1/0/+1 V DC, and TARB at 1 MSa/s; record stable negative Noise Add behavior on this firmware.
- [x] Complete bidirectional unlike-frequency Combine plus A4 for `EQPHASE` and CH1/CH2 Invert.
- [x] Complete protocol acceptance for TRACE, F/P/A coupling, and bidirectional PACP; complete A4 for the main directions and repeated `TRDUCH` CH2-to-both Burst.
- [x] Complete an 18-query, zero-write A3 pass for Sync, Counter, reference clock, protection, system settings, and Cascade.
- [x] Keep modulation, Sweep, Burst, arbitrary-wave, and Counter work as separate domains rather than a universal SCPI interface.
- [x] Document volatile/external effects for triggers, arbitrary upload, reference clocks, and global state; perform no user-waveform upload or filesystem write.
- [x] Declare capabilities only after a public WaveBench model and Service consumer exist; retain other results as evidence and reusable RFC input.

## M5: Coverage and release closure

- [x] Version `0.8.0` reached 348 SDG plugin tests and 100% source coverage: 620/620 statements and 244/244 branches.
- [x] Semantically test response structure, numeric boundaries, composite-mode gates, post-write drift, non-converging recovery, and the session latch.
- [x] Pass the repository-wide `895 passed, 2 skipped`, Ruff, plugin package check, and `pip check`.
- [x] In a final independent read-only session, record 27 source queries, 54 scope queries, and zero writes on either instrument; both source outputs OFF and RTM2032 AUTO with no overload.
- [x] Release `SDG2042X` and `SDG2082X` under the common manual protocol and offline model matrix without fabricating other-model A4 evidence.

## M6: Source V2 A0 offline adapter

- [x] Declare `source.snapshot_v2`, `source.basic_configure_v2`, and `source.output_v2`, with a minimum core version of `0.8.24`.
- [x] Read CH1/CH2 through pure-read anchor/facet/anchor plans; the two-Sine fixture completes 38 queries and zero writes under the declared limit of 42.
- [x] Permit one audited write in each V2 Basic or Output MAIN phase, followed by the core's independent snapshot readback.
- [x] Verify V2 Basic frequency writes, Output ON/OFF, descriptor/wheel cross-checks, and legacy V1 Noise/DC function compatibility offline.
- [ ] A1: confirm real V2 snapshot responses, budgets, model, and firmware applicability.
- [ ] A2: confirm V2 Basic/Output readback, rejection branches, and recovery on hardware.
- [ ] A3: confirm timeout, disconnection, unknown write outcomes, and session health through core hardware consumers.

Noise `STDEV` and DC/Noise states without final Vpp/Offset are not represented as Vpp. Such legacy
`set_function` calls retain their V1 output-OFF transaction; this rule does not add RMS, crest-factor, or
statistical models.

## Hardware gate

Before hardware access, record the target model, firmware, redacted resource, initial output state, allowed commands, denied commands, success criteria, and restoration steps. The complete 2026-08-21 acceptance used a 10 Vpp maximum and a 9 Vpp active stop line; the highest measured output was 4.24 Vpp. A final independent session confirmed Sine / 1 kHz / 4 Vpp / OFF on both channels, with all composite modes other than restored original Harmonic states disabled.

Unwired Sync, Counter, external Trigger/Gate, external reference, and multi-device Cascade remain A3 or explicitly unaccepted. Software coverage is not substituted for electrical evidence.
