# DSG830 Plugin Documentation

[中文](README.md)

This directory records the public development boundary, offline validation, and future hardware evidence for the DSG830 plugin. Vendor originals and converted copies belong in [`vendor-local/`](vendor-local/README.md) and are excluded from Git and distribution artifacts.

Public documentation distinguishes manual statements, fake-transport results, and controlled hardware acceptance. A manual command or an offline test alone does not prove a production capability.

Current public documentation:

- [DSG830 Coverage Milestones](DSG830_COVERAGE_MILESTONES_EN.md)

The source checkout also provides a resource-free
[`A2 local-evidence setup template`](../tools/a2_output_evidence.setup.template.toml). The A2 harness and
regression tests completed the controlled hardware acceptance. The production descriptor now declares
`rf_source.output`.

The checkout also provides an [`A3 local-evidence setup template`](../tools/a3_cw_evidence.setup.template.toml) and
its harness. A3 has completed and been reviewed, so the production descriptor now declares
`rf_source.cw_configure`; M3 modulation, Pulse, and Step Sweep are each promoted by their own A4 evidence, while modulated RF output, Sweep execution/fire, and trigger remain closed.

The checkout also provides an [`A4 local-evidence setup template`](../tools/a4_modulation_evidence.setup.template.toml)
and its harness, which completed controlled hardware acceptance. It configures one internal-Sine AM/FM/PM mode per
invocation, then disables that same mode after configuration readback; the final snapshot must establish both RF output
and modulation OFF. It does not read scope or invoke RF-output control. AM, FM, and PM sequences passed. PM is fixed to
the `1.25 rad` production profile so the capability matches strict readback evidence. Explicit `--recover` only writes a private recovery record. Explicit `--diagnose` retains
the `read_only` configuration, reads the selected profile plus initial/final RF snapshots, and records a zero-write
audit. Neither record is new A4 capability-promotion evidence.

The checkout also provides an [`A4-MO local-evidence setup template`](../tools/a4_modulated_output_evidence.setup.template.toml)
and harness. Its Core/plugin code and fake regressions are complete, but controlled hardware acceptance is pending. It
only validates fixed AM `50 %` at `1 kHz` and RF `1 MHz` at `-50 dBm`: configure AM with RF OFF, enable RF once, read
signal presence from CH2's current `DEF` buffer, then explicitly turn RF OFF, disable AM/global modulation, and verify
the baseline. CH2 must be explicitly declared 50 ohms; scope data do not calculate dBm, frequency, or modulation depth.
The harness neither reads nor controls CH1, does not treat LF OUTPUT as modulation evidence, and does not use trigger,
sync, or rear Pulse I/O. It uses an in-memory fixed non-production descriptor; the current production descriptor does
not declare `rf_source.modulated_output_enable`, and ordinary `rf_source.output on` still requires modulation disabled.

The checkout also provides an [`A4 Pulse local-evidence setup template`](../tools/a4_pulse_evidence.setup.template.toml)
and its harness. It only validates an internal/single Pulse configuration on `rf_out`: initial, postcondition, and final
snapshots must all establish RF output, modulation, Pulse, and Sweep OFF with no active protection. `--execute` fixes
period, width, and polarity while keeping Pulse OFF; `--diagnose` retains `read_only` and a zero-write audit. It does not
read scope, invoke RF output, use rear Pulse I/O, or trigger. Both normal and inverted polarity passed independent
configuration, readback, final-off, and audit review. The evidence promotes `rf_source.pulse_configure`; the historical
harness now rejects reruns.

Package `0.2.0` has completed the `rf_source` M0 read-only migration, M1 CW mapping, M2 output transaction, M3 internal-sine AM/FM/PM mapping and mode-specific disable, the M3-MO modulated-output safety contract, plus M4 internal/single Pulse and frequency-only Step Sweep hardware acceptance. A1, A2, A3, and A4 modulation/Pulse/Step Sweep evidence have completed and been reviewed, so the production descriptor declares `rf_source.idn`, `rf_source.snapshot`, `rf_source.cw_configure`, `rf_source.output`, `rf_source.modulation_configure`, `rf_source.pulse_configure`, and `rf_source.sweep_configure`. A4-MO private hardware acceptance is still pending, and the production descriptor does not declare `rf_source.modulated_output_enable`. A5-0 adds a strict query-only logical trigger-configuration mapping, but the production descriptor does not declare `rf_source.trigger_snapshot` and does not treat `rf_out` as a physical trigger/sync connector. PM is limited to the `1.25 rad` production profile; `rf_source.modulation_disable`, external-trigger, Sweep-execution/fire, Level-Sweep, and list capabilities remain independently gated. The milestone document defines the boundary and promotion gates.

The source checkout includes an [A4 Step Sweep local-evidence setup template](../tools/a4_step_sweep_evidence.setup.template.toml) and its harness. It only validates an RF-OFF/Sweep-OFF frequency-only profile; it does not read scope, invoke RF output, arm/fire, or trigger. The diagnostic path has zero writes and execution remains explicitly authorized. Both paths passed controlled hardware acceptance with independent final-off verification, and `rf_source.sweep_configure` is production-declared; the historical harness rejects reruns.

The source checkout also includes an [A5-0 trigger-configuration diagnostic setup template](../tools/a5_trigger_snapshot_evidence.setup.template.toml) and its harness. Its default mode performs static preflight only; explicit `--diagnose` runs one private zero-write diagnostic against the unchanged `read_only` configuration. Initial and final RF snapshots must both establish RF output, modulation, Pulse, and Sweep OFF with no active protection before it reads the six logical trigger-configuration fields. The successful budget is 22 queries and zero writes. It sends no trigger, rear-panel configuration, RF-output, arm/fire, or scope operation. The isolated diagnostic completed with final RF OFF and healthy closure verified; it is not A5 hardware evidence or a production-capability promotion.
