# DSG830 Plugin Documentation

[中文](README.md)

This directory records the public development boundary, offline validation, and future hardware evidence for the DSG830 plugin. Vendor originals and converted copies belong in [`vendor-local/`](vendor-local/README.md) and are excluded from Git and distribution artifacts.

Public documentation distinguishes manual statements, fake-transport results, and controlled hardware acceptance. A manual command or an offline test alone does not prove a production capability.

Current public documentation:

- [DSG830 Coverage Milestones](DSG830_COVERAGE_MILESTONES_EN.md)

The source checkout also provides a resource-free
[`A2 local-evidence setup template`](../tools/a2_output_evidence.setup.template.toml). The A2 harness and
regression tests completed the controlled hardware acceptance. The production descriptor now declares
`rf_source.output`; CW and later RF write capabilities remain closed.

The checkout now also provides an [`A3 local-evidence setup template`](../tools/a3_cw_evidence.setup.template.toml)
and its harness for the next CW loopback acceptance. They have passed offline regression only and have not produced
hardware evidence, so the production descriptor still does not declare `rf_source.cw_configure`.

Package `0.2.0` has completed the `rf_source` M0 read-only migration, M1 offline CW mapping, and M2 output transaction. A1 and A2 controlled hardware evidence have completed and been reviewed, so the production descriptor declares `rf_source.idn`, `rf_source.snapshot`, and `rf_source.output`; A3 local preparation is complete, while M1 CW and M3/M4 capabilities remain gated by A3–A5 hardware evidence. The milestone document defines the boundary and promotion gates.
