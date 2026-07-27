# WaveBench RIGOL DG4000 Plugin

[中文](README.md)

An executable WaveBench instrument plugin for the dual-channel RIGOL DG4202 and compatible DG4000 function/arbitrary waveform generators.

## Identity and compatibility

- Distribution: `wavebench-rigol-dg4000`
- Canonical driver ID: `rigol.dg4202`
- WaveBench: `>=0.8,<0.9`
- Python: `>=3.11`
- Transport backend: `pyvisa`

This package targets the WaveBench `v0.8.0` release. It does not run with `v0.7.0` and does not automatically claim compatibility with a future `0.9` core.

The plugin defines no aliases. After installation, the explicit canonical ID `rigol.dg4202` selects the external implementation, while the short `dg4202` alias always selects WaveBench's built-in fallback. Removing the plugin also restores the built-in canonical implementation.

## Capabilities and boundaries

The driver supports identity/error queries, CH1/CH2 state, fixed frequency, function, VPP amplitude, square duty cycle, explicit output control, query-only arbitrary-wave capability probes, and upload of validated DAC14 blocks through WaveBench's public `DG4000DacBlock` contract.

WaveBench core retains waveform-file loading, normalization, DAC14 encoding, amplitude safety limits, services, run plans, state restoration, and artifacts. Descriptor import performs no instrument I/O, and default tests use only a fake transport. Writes and uploads are not retried blindly.

The [DG4000 coverage matrix](doc/DG4000_COVERAGE_MATRIX_EN.md) maps vendor command domains to
current public APIs, offline/hardware evidence, and high-risk commands denied by default. The
[DG4000 coverage milestones](doc/DG4000_COVERAGE_MILESTONES_EN.md) define staged exit gates and
hardware-acceptance boundaries. The local vendor manual remains under ignored `doc/vendor-local/`
and is excluded from releases.

The Chinese README contains an RFC 5737 documentation resource. Never commit real resources, serial numbers, captures, screenshots, or command logs.

## License

This plugin is licensed under the [MIT License](LICENSE).

## Hardware acceptance boundary

A controlled loop used external `wavebench-rigol-dg4000` to drive DG4202 CH1 with a 1 kHz, 1 Vpp sine wave and external `wavebench-rigol-ds1000z` to capture DS1104Z Plus CH1. Scope CH1 used AC coupling with fixed high-impedance input. A 1200-point DEF waveform measured 1000.000 Hz and 1.008 Vpp in WaveBench. Both instruments had clear error queues before and after the run, and the original generator CH1 state was restored in a `finally` path and verified by readback.

This acceptance covers only the controlled CH1 sine loop and restoration semantics. CH2 currently has FakeTransport coverage only, and the external plugin's arbitrary-wave upload was not repeated in this hardware run.

## Development checks

Run the package tests, Ruff, WaveBench package inspection, and a managed-install dry run from an environment containing the matching WaveBench `v0.8.0` release.

Use the repository-level [editable development environment](../../doc/DEVELOPMENT_EN.md) for daily source work. Formal acceptance still uses a real wheel and a disposable virtual environment.

## Provenance

- `0.1.0` migrated the vendor-protocol portion of WaveBench's built-in DG4202 driver while leaving services and safety policy in core.
- `0.2.0` adds the bilingual M0-M12 coverage plan and a real-sdist regression gate that excludes local vendor material; it adds no instrument capability.
