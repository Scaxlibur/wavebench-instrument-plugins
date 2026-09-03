# SDG2000X Plugin Documentation

[中文](README.md)

This page separates the current SDG2000X user contract from development, protocol, and hardware evidence. The production descriptor declares current capabilities. Acceptance records preserve evidence for a particular model, firmware, wiring, and point in time; they do not independently promote public capabilities.

## Current Reference

- [SDG2000X current capability Reference](SDG2000X_COVERAGE_MATRIX_EN.md): current capabilities, Source V2 model/firmware restrictions, safety behavior, and explicit exclusions.
- [Repository plugin catalog](https://github.com/Scaxlibur/wavebench-instrument-plugins/blob/main/doc/reference/plugin-catalog-en.md): generated metadata version, entry-point, and capability summary from `pyproject.toml` and the descriptor.

## Development and contract records

- [Protocol audit](SDG2000X_PROTOCOL_AUDIT_EN.md)
- [Coverage milestones](SDG2000X_COVERAGE_MILESTONES_EN.md)
- [Source V2 A0 offline adapter record](SDG2000X_SOURCE_V2_A0_EN.md)
- [Source V2 A1/A2 hardware acceptance](SDG2000X_SOURCE_V2_A1_A2_ACCEPTANCE_EN.md)
- [Source V2 A3 hardware waveform acceptance](SDG2000X_SOURCE_V2_A3_ACCEPTANCE_EN.md)
- [Source V2 C3 candidate-package audit](SDG2000X_SOURCE_V2_RELEASE_AUDIT_EN.md)
- [Source V2 capability, state, and composite-output safety RFC](RFC_SOURCE_V2_CAPABILITY_STATE_SAFETY_EN.md)

These pages preserve implementation and review history. If they conflict with current behavior, package metadata, the production descriptor, the driver, and tests take precedence.

## Basic-interface acceptance evidence

- [Read-only hardware acceptance](SDG2000X_READONLY_ACCEPTANCE_EN.md)
- [Output-control hardware acceptance](SDG2000X_OUTPUT_ACCEPTANCE_EN.md)
- [Frequency-write hardware acceptance](SDG2000X_FREQUENCY_ACCEPTANCE_EN.md)
- [Basic-write hardware acceptance](SDG2000X_BASIC_WRITE_ACCEPTANCE_EN.md)
- [Public Source API dual-channel acceptance](SDG2000X_PUBLIC_DUAL_CHANNEL_ACCEPTANCE_EN.md)

## Advanced command-domain evidence

- [Harmonic protocol and spectrum acceptance](SDG2000X_HARMONIC_ACCEPTANCE_EN.md)
- [Modulation protocol and waveform acceptance](SDG2000X_MODULATION_ACCEPTANCE_EN.md)
- [Sweep protocol and waveform acceptance](SDG2000X_SWEEP_ACCEPTANCE_EN.md)
- [Burst protocol and waveform acceptance](SDG2000X_BURST_ACCEPTANCE_EN.md)
- [Pulse protocol and waveform acceptance](SDG2000X_PULSE_ACCEPTANCE_EN.md)
- [Read-only arbitrary probe acceptance](SDG2000X_ARBITRARY_PROBE_ACCEPTANCE_EN.md)
- [Full built-in arbitrary catalog acceptance](SDG2000X_BUILTIN_ARB_ACCEPTANCE_EN.md)
- [Special-waveform protocol and hardware acceptance](SDG2000X_SPECIAL_WAVEFORM_ACCEPTANCE_EN.md)
- [Dual-channel waveform Combine acceptance](SDG2000X_COMBINE_ACCEPTANCE_EN.md)
- [Phase mode, equal-phase, and invert acceptance](SDG2000X_PHASE_INVERT_ACCEPTANCE_EN.md)
- [Tracking, coupling, copy, and dual-trigger acceptance](SDG2000X_CHANNEL_INTERACTION_ACCEPTANCE_EN.md)
- [Auxiliary and global-state read-only acceptance](SDG2000X_AUXILIARY_READONLY_ACCEPTANCE_EN.md)

Acceptance evidence for an advanced command domain does not imply that a corresponding public capability exists in the production descriptor.

## Vendor material

- [SIGLENT SDG2000X product page](https://www.siglent.com/in/products-overview/sdg2000x/)
- [SIGLENT waveform-generator document downloads](https://siglentna.com/resources/documents/waveform-generators/)
- `doc/vendor-local/` usage in a source checkout

`doc/vendor-local/` exists only in a source checkout. Vendor originals and converted copies are excluded from Git and distributions. Return to the [SDG2000X plugin landing page](../README_EN.md).
