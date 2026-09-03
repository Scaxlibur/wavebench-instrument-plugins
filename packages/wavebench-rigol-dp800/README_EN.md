# WaveBench RIGOL DP800 plugin

[中文](README.md)

An executable WaveBench instrument plugin for the RIGOL DP800 family, with DP832/DP832A
as the current public compatibility scope.

## Start here

- [Find the current version, compatibility range, models, and capabilities](../../doc/reference/plugin-catalog-en.md)
- [Read the current feature-coverage matrix](doc/DP800_COVERAGE_MATRIX_EN.md)
- [Review development milestones and hardware evidence](doc/DP800_COVERAGE_MILESTONES_EN.md)
- [Install and manage WaveBench plugins](https://github.com/Scaxlibur/wavebench/blob/master/docs/how-to/manage-plugins.md)

## Current boundary

Set `rigol.dp800` to select this external implementation; the short `dp800` alias always selects the
Core fallback. The implementation covers identity and error queues, channel state and measurements,
voltage/current limits, explicit output control, and OVP/OCP. The production descriptor and coverage
matrix are authoritative for exact capabilities, model scope, and protocol limits.

The plugin owns DP800 vendor SCPI, parsing, and readback. Core owns safety limits, relationships
between setpoints and protection thresholds, pre-output checks, services, run plans, and experiment-
level restoration.

## Configuration example

```toml
[connection]
backend = "lan"
resource = "TCPIP::192.0.2.50::INSTR"

[safety_limits]
max_power_voltage_v = 5.0
max_power_current_limit_a = 0.2

[power]
driver = "rigol.dp800"
default_channel = 1
check_errors = true
settle_ms_after_set = 2000
settle_ms_after_output = 500
```

The example uses an RFC 5737 documentation address. Offline tests do not scan resources, connect to
instruments, or send real SCPI.

## Safety boundary

Descriptor import performs no instrument I/O. Default tests do not scan resources, connect to an
instrument, or send real SCPI. Writes are not retried blindly. An ambiguous write, unverifiable
recovery, or new trip latches later configuration writes off for the current instance. Output
failure attempts to remain OFF, and protection recovery never sends `CLEAR`.

Never commit real addresses, serial numbers, setpoint snapshots, measurements, or command logs.

## Development and license

Use the repository-level [editable development environment](../../doc/DEVELOPMENT_EN.md) for source
work and offline checks. This plugin is licensed under the [MIT License](LICENSE).
