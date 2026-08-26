# DSG830 Plugin Documentation

[中文](README.md)

This directory records the public development boundary, offline validation, and future hardware evidence for the DSG830 plugin. Vendor originals and converted copies belong in [`vendor-local/`](vendor-local/README.md) and are excluded from Git and distribution artifacts.

Public documentation distinguishes manual statements, fake-transport results, and controlled hardware acceptance. A manual command or an offline test alone does not prove a production capability.

Current public documentation:

- [DSG830 Coverage Milestones](DSG830_COVERAGE_MILESTONES_EN.md)

Package `0.2.0` has completed the offline `rf_source` M0 parser and descriptor migration. A1 controlled read-only hardware evidence has completed and been reviewed, so the production descriptor declares `rf_source.idn` and `rf_source.snapshot`; A2–A5 still gate every remaining capability independently. The milestone document defines the boundary and promotion gates.
