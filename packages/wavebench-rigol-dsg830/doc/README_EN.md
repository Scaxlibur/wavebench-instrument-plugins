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
`rf_source.cw_configure`; modulation, Pulse, Sweep, and trigger remain closed.

The checkout also provides an [`A4 local-evidence setup template`](../tools/a4_modulation_evidence.setup.template.toml)
and its harness, which has entered controlled hardware validation. It configures one internal-Sine AM/FM/PM mode per
invocation, then disables that same mode after configuration readback; the final snapshot must establish both RF output
and modulation OFF. It does not read scope or invoke RF-output control. AM and FM sequences passed, while PM still has
a strict readback mismatch. Explicit `--recover` only writes a private recovery record. Explicit `--diagnose` retains
the `read_only` configuration, reads the selected profile plus initial/final RF snapshots, and records a zero-write
audit. Neither record is A4 capability-promotion evidence.

Package `0.2.0` has completed the `rf_source` M0 read-only migration, M1 CW mapping, M2 output transaction, M3 internal-sine AM/FM/PM offline mapping, and mode-specific disable. A1, A2, and A3 controlled hardware evidence have completed and been reviewed, so the production descriptor declares `rf_source.idn`, `rf_source.snapshot`, `rf_source.cw_configure`, and `rf_source.output`; A4 has passed for AM and FM but has no qualifying PM evidence, so `rf_source.modulation_configure` and `rf_source.modulation_disable` remain outside the production descriptor while M4/external-trigger capabilities remain gated by A4–A5. The milestone document defines the boundary and promotion gates.
