# WaveBench RIGOL MSO8000 Plugin

[中文](README.md)

A WaveBench instrument plugin for the RIGOL MSO8000 mixed-signal oscilloscope series. The current
production descriptor registers only the MSO8104.

## Start here

- [Find the current version, compatibility range, model, and capabilities](../../doc/reference/plugin-catalog-en.md)
- [Browse the MSO8000 plugin documentation](doc/README_EN.md)
- [Install and manage WaveBench plugins](https://github.com/Scaxlibur/wavebench/blob/master/docs/how-to/manage-plugins.md)

## Current boundary

The implementation covers bounded waveform fetch/capture, non-replayed error draining, coupling,
autoscale, screenshots, and constrained math, statistics, FFT, acquisition, digital-state, snapshot,
and cursor interfaces. The production descriptor is authoritative for exact capabilities, binary
budgets, and profiles. The [coverage matrix](doc/MSO8104_COVERAGE_MATRIX_EN.md) explains current
behavior and unsupported areas; the [acceptance record](doc/MSO8104_HARDWARE_ACCEPTANCE_EN.md)
bounds the available hardware evidence.

Average capture is not declared. The `tcpip`, `usb`, and `gpib` resource schemes represent manual-
backed and offline routing contracts, not hardware acceptance for each connection type.

## Minimum configuration

```toml
[connection]
backend = "pyvisa"
resource = "TCPIP0::192.0.2.80::INSTR"

[scope]
driver = "rigol.mso8104"
default_channel = 1
check_errors = false
access = "read_write"
```

The example uses an RFC 5737 documentation address. Default tests do not scan resources, connect to
an instrument, or send real SCPI.

## Safety boundary

Descriptor import does not open a transport, scan ports, send SCPI, or create files. Instrument
writes and acquisition triggers are not retried blindly. If Core lacks a required safety interface,
the capability remains unavailable rather than gaining a raw-SCPI escape hatch. Never commit real
resources, serial numbers, credentials, waveforms, screenshots, or command logs.

## Development and license

The [plugin documentation](doc/README_EN.md) links milestones, RFCs, hardware evidence, and historical
status. Use the repository-level [editable development environment](../../doc/DEVELOPMENT_EN.md) for
source work. This plugin is licensed under the [MIT License](LICENSE).
