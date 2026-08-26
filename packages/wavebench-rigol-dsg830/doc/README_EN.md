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

Package `0.2.0` has completed the `rf_source` M0 read-only migration, M1 CW mapping, M2 output transaction, and M3 internal-sine AM/FM/PM offline mapping. A1, A2, and A3 controlled hardware evidence have completed and been reviewed, so the production descriptor declares `rf_source.idn`, `rf_source.snapshot`, `rf_source.cw_configure`, and `rf_source.output`; `rf_source.modulation_configure` remains gated by A4, while M4/external-trigger capabilities remain gated by A4–A5. The milestone document defines the boundary and promotion gates.
