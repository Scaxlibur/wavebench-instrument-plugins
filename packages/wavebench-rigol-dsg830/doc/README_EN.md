# DSG830 Plugin Documentation

[中文](README.md)

This directory records the public development boundary, offline validation, and future hardware evidence for the DSG830 plugin. Vendor originals and converted copies belong in [`vendor-local/`](vendor-local/README.md) and are excluded from Git and distribution artifacts.

Public documentation distinguishes manual statements, fake-transport results, and controlled hardware acceptance. A manual command or an offline test alone does not prove a production capability.

Current public documentation:

- [DSG830 Coverage Milestones](DSG830_COVERAGE_MILESTONES_EN.md)

Package `0.2.0` has completed the offline `rf_source` M0 parser and descriptor migration, but its production descriptor still declares only `rf_source.idn`. Snapshot waits for A1 controlled hardware evidence; Core capability gates reject an undeclared snapshot before transport I/O. The milestone document defines the boundary and promotion gates.
