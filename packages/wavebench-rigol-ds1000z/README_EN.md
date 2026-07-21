# WaveBench RIGOL DS1000Z Plugin

[中文](README.md)

An executable WaveBench instrument plugin for the four-channel RIGOL DS1104Z, DS1104Z Plus, DS1104Z-S Plus, and compatible DS1000Z oscilloscopes.

## Identity and compatibility

- Distribution: `wavebench-rigol-ds1000z`
- Canonical driver ID: `rigol.ds1000z`
- WaveBench: `>=0.7,<1`
- Python: `>=3.11`
- Transport backend: `pyvisa`

The plugin does not define aliases. WaveBench's built-in `ds1104` and `ds1000z` compatibility aliases continue to select the built-in fallback. Use `driver = "rigol.ds1000z"` to select this plugin explicitly.

## Capabilities

- Instrument identity and error queue queries;
- CH1-CH4 coupling queries and explicit autoscale;
- NORM, RAW, and DMAX BYTE waveform reads;
- RAW long-record transfers in chunks of at most 250,000 points;
- CH1-CH4 single-channel capture and one-acquisition four-channel capture;
- PNG screenshots;
- Chunk, transfer, and conversion telemetry.

## Security boundary

The plugin opens only the configured transport through WaveBench's `DriverContext`. Importing the descriptor does not connect to an instrument. Python plugins are trusted code, not sandboxes.

The configuration example in the Chinese README uses an RFC 5737 documentation address. Never commit real instrument resources, serial numbers, captures, screenshots, or command logs.

## Development checks

Run the package tests, Ruff, WaveBench package inspection, and a managed-install dry run from an environment containing WaveBench 0.7.x. The default tests use a fake transport and never scan for or connect to hardware.

## Hardware acceptance boundary

On 2026-07-21, a sanitized DS1104Z Plus regression passed identity, an empty error queue, high-impedance CH1 coupling, a 1,200-point NORM read, explicit autoscale, 2,400,000-point MAX and DMAX chunked reads, a PNG screenshot, and a one-acquisition CH1/CH2 capture. Each MAX/DMAX transfer used ten chunks of at most 250,000 points, and the error queue was empty before and after the run.

A four-channel hardware-path regression later that day queried coupling on CH1-CH4 and returned a finite 1,200-point waveform for every channel after one acquisition and one OPC wait. All four waveforms used a 2 µs sample interval, and the error queue was empty before and after the run. CH1 measured about 2.04 Vpp at the time. CH2-CH4 had no independent test signals connected, so this run validates their communication and acquisition paths, not independent analog-amplitude accuracy.

The current VXI-11 path took about 135 seconds per 2,400,000-point transfer. This proves functional completeness, not optimized long-record performance. No real resource, capture, screenshot, or command log was written to this repository.

## Provenance

The initial 0.1.0 implementation was migrated from WaveBench's installable DS1000Z pilot package. It preserves the original canonical ID, entry point, compatibility range, and driver semantics. This repository is the source of truth for the external package after migration.
