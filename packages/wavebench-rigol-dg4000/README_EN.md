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

The offline M1/M2/M4 implementation is closed in `0.3.0`: all I/O shares one reentrant lock;
fixed-wave writes use a pre-write snapshot, per-step readback, off-first recovery, and ambiguous-
write latching; DAC14 upload is accepted only while the target channel is already OFF, in FIX
mode, with sweep OFF. Overwriting the volatile USER waveform is reported as an irreversible side
effect. DG4202 firmware `00.01.14` has passed the M1/M2 hardware exit gates. M4 is fully accepted
on CH1 and has protocol/readback/restoration acceptance on CH2; CH2 analog-shape acceptance still
requires a high-impedance scope connection. No result is extrapolated to another model, firmware,
or channel wiring.

The [DG4000 coverage matrix](doc/DG4000_COVERAGE_MATRIX_EN.md) maps vendor command domains to
current public APIs, offline/hardware evidence, and high-risk commands denied by default. The
[DG4000 coverage milestones](doc/DG4000_COVERAGE_MILESTONES_EN.md) define staged exit gates and
hardware-acceptance boundaries. The local vendor manual remains under ignored `doc/vendor-local/`
and is excluded from releases.

The Chinese README contains an RFC 5737 documentation resource. Never commit real resources, serial numbers, captures, screenshots, or command logs.

## License

This plugin is licensed under the [MIT License](LICENSE).

## Hardware acceptance boundary

An earlier controlled loop used external `wavebench-rigol-dg4000` to drive DG4202 CH1 with a 1 kHz, 1 Vpp sine wave and external `wavebench-rigol-ds1000z` to capture DS1104Z Plus CH1. Scope CH1 used AC coupling with fixed high-impedance input. A 1200-point DEF waveform measured 1000.000 Hz and 1.008 Vpp in WaveBench. Both instruments had clear error queues before and after the run, and the original generator CH1 state was restored in a `finally` path and verified by readback.

On 2026-07-27, current `0.3.0` worktree behavior was reaccepted on DG4202 firmware `00.01.14`.
M1 completed one strict CH1/CH2 profile with 24 queries and zero writes. M2 separately exercised
OFF, temporary SQU/different fixed frequencies/0.8 Vpp/37% duty, explicit ON-to-OFF, off-first
restore, and fresh-session field verification on both channels. Both channels ended at their
original SIN, 1 kHz, 5 Vpp, 0 V offset, FIX, sweep OFF, output ON state.

M4 separately uploaded a 64-point little-endian DAC14 triangle to CH1 and CH2 while output was
OFF, read back USER/1 kHz/1 Vpp/0 V, verified clear error queues, and confirmed restoration in new
sessions. CH1 then explicitly drove a 2 Vpp triangle into a high-impedance RTM2032. A 10,000-point
capture measured 997.26 Hz and 2.16 Vpp; triangle-template RMSE was 0.0390 V, 49.2% of the
sine-template RMSE. After restoration, the original sine measured 998.25 Hz and 5.12 Vpp. CH2 is
wired to a DMM, so its acceptance stops at protocol, readback, and restoration and does not claim
analog waveform shape. RTM2032 waveform fetch uses controlled transfer-format/point writes and is
not a zero-write scope session. Both uploads overwrite volatile USER data, an acknowledged
irreversible side effect. No real resource, serial number, raw waveform, or command log is stored.

## Development checks

Run the package tests, Ruff, WaveBench package inspection, and a managed-install dry run from an environment containing the matching WaveBench `v0.8.0` release.

Use the repository-level [editable development environment](../../doc/DEVELOPMENT_EN.md) for daily source work. Formal acceptance still uses a real wheel and a disposable virtual environment.

## Provenance

- `0.1.0` migrated the vendor-protocol portion of WaveBench's built-in DG4202 driver while leaving services and safety policy in core.
- `0.2.0` adds the bilingual M0-M12 coverage plan and release-artifact leak prevention without expanding capabilities.
- `0.3.0` delivers strict current-API validation, transactional fixed-wave writes, and fail-closed DAC14 handling. DG4202 `00.01.14` passes M1/M2 and the M4 CH1 hardware gate; M4 CH2 passes protocol/restoration only. No capability is added.
