# DSG830 Plugin Documentation

[中文](README.md)

This page separates the current DSG830 user contract from development evidence. Manual commands, fake-transport tests, and controlled hardware acceptance inform decisions, but only the production descriptor declares current capabilities.

## Current Reference

- [DSG830 capabilities and profiles](reference-en.md): current models, compatibility, exact profiles, safety preconditions, and explicit exclusions.
- [Repository plugin catalog](https://github.com/Scaxlibur/wavebench-instrument-plugins/blob/main/doc/reference/plugin-catalog-en.md): generated metadata version, entry-point, and capability summary from `pyproject.toml` and the descriptor.

## Historical and development evidence

- [DSG830 coverage milestones](DSG830_COVERAGE_MILESTONES_EN.md): A1–A5 development boundaries, acceptance conclusions, and unopened directions.

The source checkout's [`tools/` directory](https://github.com/Scaxlibur/wavebench-instrument-plugins/tree/main/packages/wavebench-rigol-dsg830/tools) retains the A2 output, A3 CW, A4 modulation/Pulse/Step Sweep, A4-MO, A5-0 trigger-configuration diagnostic, and A5 Pulse Output harnesses and resource-free setup templates. `tools/` is excluded from the sdist; installed-package documentation should use the repository link above.

These records preserve acceptance scope. They neither replace the current Reference nor authorize a hardware harness rerun.

## Vendor material

In a source checkout, vendor originals and converted copies belong in the ignored `doc/vendor-local/` directory and are excluded from Git and distributions. Public documentation must not contain real instrument addresses, serial numbers, credentials, raw captures, or laboratory-specific configuration.

Return to the [DSG830 plugin landing page](../README_EN.md).
