# WaveBench RIGOL DM3000 Plugin

[中文](README.md)

Executable WaveBench driver plugin for RIGOL DM3000/DM3058 digital multimeters. This
package supports LAN/VXI-11 connections through PyVISA only.

## Start here

- [Find the current version, compatibility range, models, and capabilities](../../doc/reference/plugin-catalog-en.md)
- [Read the current feature-coverage matrix](doc/DM3000_COVERAGE_MATRIX_EN.md)
- [Review development milestones and hardware evidence](doc/DM3000_COVERAGE_MILESTONES_EN.md)
- [Install and manage WaveBench plugins](https://github.com/Scaxlibur/wavebench/blob/master/docs/how-to/manage-plugins.md)

## Connection and capability boundary

The explicit `rigol.dm3000` ID selects this external LAN-only implementation. The short `dm3000`
and `dm3058` aliases continue to select the Core fallback with its RS-232 route. Before opening a
transport, the canonical driver rejects a serial backend and non-TCPIP resources such as ASRL, USB,
or GPIB.

The implementation covers common readings, measurement function and profile operations, read-only
trigger/calculation/system-interface status, and constrained function, DCV/ACV range, and DCV input-
impedance writes. The production descriptor and coverage matrix are authoritative for exact
capabilities, parameter limits, and rejection behavior.

## Example

The address below is reserved for documentation:

```toml
[dmm]
driver = "rigol.dm3000"
backend = "lan"
resource = "TCPIP::192.0.2.40::INSTR"
timeout_ms = 3000
settle_ms_before_read = 0
settle_ms_after_function_change = 500
```

Descriptor import performs no instrument I/O, and offline tests do not discover resources or send
SCPI. An ambiguous range or impedance write, failed restoration, or inability to prove restoration
of automatic/manual mode latches later configuration writes off for the current instance. Never
commit real addresses, serial numbers, readings, screenshots, or command logs.

## Development and license

Use the repository-level [editable development environment](../../doc/DEVELOPMENT_EN.md) for source
work and offline checks. This plugin is licensed under the [MIT License](LICENSE).
