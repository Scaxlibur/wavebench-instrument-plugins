# DSG830 Plugin Documentation

[中文](README.md)

This directory records the public development boundary, offline validation, and future hardware evidence for the DSG830 plugin. Vendor originals and converted copies belong in [`vendor-local/`](vendor-local/README.md) and are excluded from Git and distribution artifacts.

Public documentation distinguishes manual statements, fake-transport results, and controlled hardware acceptance. A manual command or an offline test alone does not prove a production capability.

Current public documentation:

- [DSG830 Coverage Milestones](DSG830_COVERAGE_MILESTONES_EN.md)

Package `0.2.0` has completed the `rf_source` M0 read-only migration and M1 offline CW mapping, and is progressing the M2 offline output transaction. A1 controlled read-only hardware evidence has completed and been reviewed, so the production descriptor declares only `rf_source.idn` and `rf_source.snapshot`; M1/M2 remain fake-descriptor-only and A2–A5 still gate every write capability independently. The milestone document defines the boundary and promotion gates.
