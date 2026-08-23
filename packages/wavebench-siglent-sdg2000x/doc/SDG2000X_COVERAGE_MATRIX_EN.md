# SDG2000X Coverage Matrix

[中文](SDG2000X_COVERAGE_MATRIX.md)

## Current conclusion

Version `0.8.1` declares eleven capabilities: the legacy identity, status, five basic writes, and read-only
arbitrary probe, plus `source.snapshot_v2`, `source.basic_configure_v2`, and `source.output_v2`. The first
eight have SDG2122X core-consumer hardware evidence. The three new capabilities currently have A0 offline
contracts only and make no Source V2 hardware claim for any model. Registered-model V1 capabilities remain
released under the common manual contract and offline model matrix.

Source V2 C3 remains incomplete. The offline audit verifies the current package's version, declarations, and
test boundary; A1–A3, a stable core, and final release-artifact sign-off remain separate work. See the
[C3 release-audit preparation](SDG2000X_SOURCE_V2_RELEASE_AUDIT_EN.md).

Advanced command domains have the broadest practical domain-specific protocol/A4 evidence, but no lossy write capability or raw-SCPI endpoint is declared where the core lacks an exact state model. Historical coverage numbers apply to version `0.8.0`; current Source V2 coverage is established by the present offline test report, not by carrying forward those numbers. Code coverage does not establish physical evidence for unwired ports or unavailable models.

## Coverage status

| Command domain | WaveBench capability | Current status | Exit condition |
| --- | --- | --- | --- |
| Instrument identity | `source.idn` | Passed on `SDG2122X` / `2.01.01.39R7T2`; other registered models released by the common protocol | New models or response variants still need redacted evidence |
| System error queue | None | Disabled | Confirm the query, empty-queue semantics, and whether reads consume state |
| Basic channel status | `source.status` | Repeated SDG2122X read-only rounds are stable; CH1/CH2 have frequency, Vpp, mean, and final independent zero-write evidence | Accept new firmware response variants separately |
| Source V2 snapshot | `source.snapshot_v2` | A0: pure-read CH1/CH2 anchor/facet/anchor plan, 38-query Sine fixture, zero writes | A1 confirms real responses, budgets, models, and firmware |
| Source V2 basic configuration | `source.basic_configure_v2` | A0: CH1/CH2 one-field Basic MAIN writes, core readback, and one OFF recovery for Sine/Square/Ramp/Pulse; `offset_v` is pre-write rejected | A2 confirms hardware command acceptance and readback form; A3 uses a scope loopback for frequency, Vpp, function, and duty |
| Source V2 output | `source.output_v2` | A0: independent CH1/CH2 ON/OFF, one-write MAIN, core readback, and one OFF recovery after a readable mismatch; independent outputs may be ON together | A2 confirms hardware transitions, independent readback, and OFF recovery |
| Output control | `source.output` | All models pass offline; SDG2122X CH1/CH2 passed core-Service ON→A4→OFF with zero unknown writes | Add other-model A4 only when hardware is available |
| Fixed-wave frequency | `source.set_frequency` | SDG2122X CH1/CH2 cover OFF-state and live-ON writes; model/function boundaries are fully covered offline | Add other-model A4 only when hardware is available |
| Fixed-wave amplitude | `source.set_amplitude_vpp` | SDG2122X CH1/CH2 cover OFF and live-ON writes; 2 mVpp–10 Vpp, offset envelope, and drift branches are 100% covered | Add other-model A4 only when hardware is available |
| Fixed-wave function | `source.set_function` | Sine/Square/Ramp pass core loops on CH1/CH2; Pulse passes on CH2; Noise/DC remain OFF-config-only publicly | Wait for a reusable Noise/DC safety model |
| Square-wave duty cycle | `source.set_square_duty_cycle` | CH2 20%/80% measured 0.200/0.800; final CH1 30% and CH2 70% measured 0.287/0.6949 | Frequency-dependent high-rate clamping remains strict fail-closed readback |
| Pulse parameters | No lossless capability yet | SDG2122X 25%/65% duty and 20/40 µs edges pass A4; DLY is A3 only | Declare after Source V2 supports unknown hold; add an independent delay reference |
| Harmonics | No lossless capability yet | SDG2122X H2–H16 slots pass; H2/H3 amplitude, H2 phase, and ALL/EVEN/ODD pass A4 spectrum tests | Declare after a variable/selected-only Source V2 model exists |
| Modulation | No lossless capability yet | SDG2122X internal AM/DSB-AM/FM/PM/PWM/ASK/FSK/PSK pass protocol and A4 waveform tests | Declare after Source V2 supports disabled-state absence and vendor ranges; wire external sources |
| Sweep | No lossless capability yet | SDG2122X LINE/LOG/STEP, UP/DOWN/UP_DOWN, and INT/MAN pass protocol and A4 waveform tests; EXT is readback-only | Declare after Source V2 supports absent fields; wire external trigger |
| Burst | No lossless capability yet | Finite INT/MAN pass cycle/repetition A4; `TRDUCH` CH2-to-both passes; EXT/Gate are readback-only; INF did not form a continuous carrier | Wire external trigger/gate; use a discriminated Source V2 model |
| Noise / DC / TARB | No lossless capability yet | Noise and -1/0/+1 V DC pass A4; the 20 MHz lower clamp is A3; TARB 1 MSa/s is non-flat; Noise Add remains stably OFF on this unit | Use non-periodic amplitude facets; recheck Noise Add on other firmware |
| Arbitrary waveforms | `source.arbitrary_probe` | Dual-channel core zero-write probing passed; 199/199 built-ins passed selection/readback/A4; TARB has separate A4 | Upload, deletion, and user catalog remain denied by default |
| Combine | No lossless capability yet | CH1←CH2 and CH2←CH1 unlike-frequency A4 pass; source output relay need not be ON | Model participants, worst-case envelope, and mutual exclusions first |
| Phase mode / Invert | No lossless capability yet | `EQPHASE` leaves 0.27°; CH1/CH2 inversion is about 179.9°; actual token is `PHASE-LOCKED` | Split single-field polarity/phase facets before declaration |
| Tracking / Coupling / Copy | No lossless capability yet | TRACE, F/P/A ratio/deviation, and CH1→CH2 PACP have A4; reverse PACP has A3 | Source V2 must model conditional fields, actions, and cross-channel transactions |
| Sync / Counter / Clock / Cascade | None | An 18-query zero-write pass succeeded; Sync and Counter OFF, ROSC INT, Cascade OFF; unwired ports have no A4 claim | Add dedicated Sync, Counter, external-reference, and second-source wiring |
| Code paths | Not applicable | V1 historical release: 348 tests, 620/620 statements, and 244/244 branches; new V2 A0 tests run separately | Run the current plugin tests and coverage report; do not inflate metrics with empty assertions |

## Denied by default

- Do not send `*RST` or another global preset command.
- User-facing output enable remains limited to the core operation contracts behind `source.output` or `source.output_v2`; advanced hardware scripts are not a public raw endpoint.
- Do not expose raw SCPI.
- Do not upload, delete, or overwrite user arbitrary waves or state files.
- Do not switch external reference, protection, Counter, Cascade, or unknown-load auxiliary outputs merely for coverage.
- Do not equate a product-page feature with an implemented capability.

## Sources of truth

- [SIGLENT SDG2000X product page](https://www.siglent.com/in/products-overview/sdg2000x/)
- [SIGLENT waveform-generator document downloads](https://siglentna.com/resources/documents/waveform-generators/)
- Local guide: `doc/vendor-local/SDG_Series_Programming_Guide_E05C.pdf`, revision `PG02_E05C`
- [Protocol audit](SDG2000X_PROTOCOL_AUDIT_EN.md)
- [Read-only hardware acceptance](SDG2000X_READONLY_ACCEPTANCE_EN.md)
- [Output-control hardware acceptance](SDG2000X_OUTPUT_ACCEPTANCE_EN.md)
- [Frequency-write hardware acceptance](SDG2000X_FREQUENCY_ACCEPTANCE_EN.md)
- [Basic-write hardware acceptance](SDG2000X_BASIC_WRITE_ACCEPTANCE_EN.md)
- [Source V2 A0 offline adapter record](SDG2000X_SOURCE_V2_A0_EN.md)
- [Source V2 C3 release-audit preparation](SDG2000X_SOURCE_V2_RELEASE_AUDIT_EN.md)
- [Harmonic protocol and spectrum acceptance](SDG2000X_HARMONIC_ACCEPTANCE_EN.md)
- [Modulation protocol and waveform acceptance](SDG2000X_MODULATION_ACCEPTANCE_EN.md)
- [Sweep protocol and waveform acceptance](SDG2000X_SWEEP_ACCEPTANCE_EN.md)
- [Burst protocol and waveform acceptance](SDG2000X_BURST_ACCEPTANCE_EN.md)
- [Pulse protocol and waveform acceptance](SDG2000X_PULSE_ACCEPTANCE_EN.md)
- [Read-only arbitrary probe acceptance](SDG2000X_ARBITRARY_PROBE_ACCEPTANCE_EN.md)
- [Full built-in arbitrary catalog acceptance](SDG2000X_BUILTIN_ARB_ACCEPTANCE_EN.md)
- [Public Source API dual-channel acceptance](SDG2000X_PUBLIC_DUAL_CHANNEL_ACCEPTANCE_EN.md)
- [Special-waveform protocol and hardware acceptance](SDG2000X_SPECIAL_WAVEFORM_ACCEPTANCE_EN.md)
- [Dual-channel waveform Combine acceptance](SDG2000X_COMBINE_ACCEPTANCE_EN.md)
- [Phase mode, equal-phase, and invert acceptance](SDG2000X_PHASE_INVERT_ACCEPTANCE_EN.md)
- [Tracking, coupling, copy, and dual-trigger acceptance](SDG2000X_CHANNEL_INTERACTION_ACCEPTANCE_EN.md)
- [Auxiliary and global-state read-only acceptance](SDG2000X_AUXILIARY_READONLY_ACCEPTANCE_EN.md)
- [Reusable Source V2 RFC](RFC_SOURCE_V2_CAPABILITY_STATE_SAFETY_EN.md)
- Current descriptor, driver, and fake-transport tests
