# WaveBench RIGOL DS1000Z Plugin

[中文](README.md)

An executable WaveBench instrument plugin for the four-channel RIGOL DS1104Z, DS1104Z Plus, DS1104Z-S Plus, and compatible DS1000Z oscilloscopes.

## Start here

- [Find the current version, compatibility range, models, and capabilities](../../doc/reference/plugin-catalog-en.md)
- [Read the controlled hardware acceptance record](doc/DS1000Z_HARDWARE_ACCEPTANCE_EN.md)
- [Install and manage WaveBench plugins](https://github.com/Scaxlibur/wavebench/blob/master/docs/how-to/manage-plugins.md)

## Scope

Set `driver = "rigol.ds1000z"` to select this external plugin. The built-in `ds1104` and `ds1000z`
aliases continue to select the Core fallback; this plugin defines no aliases.

The implementation covers identity and error-queue queries, CH1–CH4 coupling, explicit autoscale,
NORM/RAW/DMAX BYTE waveform reads, single- and four-channel capture, PNG screenshots, and transfer
telemetry. The production descriptor and generated plugin catalog are authoritative for exact
capabilities, models, configuration fields, and compatibility.

## Security boundary

The plugin opens only the configured transport through WaveBench's `DriverContext`. Importing the descriptor does not connect to an instrument. Python plugins are trusted code, not sandboxes.

The configuration example in the Chinese README uses an RFC 5737 documentation address. Default
tests use FakeTransport and do not scan resources, connect to instruments, or send real SCPI. Never
commit real instrument resources, serial numbers, captures, screenshots, or command logs.

## Development and license

Use the repository-level [editable development environment](../../doc/DEVELOPMENT_EN.md) for daily
source work and offline checks. This plugin is licensed under the [MIT License](LICENSE).
