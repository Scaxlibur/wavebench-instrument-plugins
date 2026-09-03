# WaveBench RIGOL DSG830 Plugin

[中文](README.md)

A WaveBench instrument plugin for the RIGOL DSG830 RF signal generator. The package registers the canonical driver ID `rigol.dsg830`, declares no aliases, and does not replace a bundled WaveBench driver.

## Start here

- [Check current capabilities, profiles, and restrictions](doc/reference-en.md)
- [Read development milestones and hardware evidence](doc/README_EN.md)
- [Install and manage plugins with WaveBench Core](https://github.com/Scaxlibur/wavebench/blob/master/docs/how-to/manage-plugins.md)

Package metadata and the production descriptor are authoritative for the current metadata version, compatibility range, and capabilities. The repository-level generated [plugin catalog](https://github.com/Scaxlibur/wavebench-instrument-plugins/blob/main/doc/reference/plugin-catalog-en.md) provides a checked summary.

## Read-only start

This configuration uses an RFC 5737 documentation address and allows identity and status queries only:

```toml
[rf_source]
driver = "rigol.dsg830"
resource = "TCPIP::192.0.2.83::INSTR"
access = "read_only"
```

A `read_only` configuration performs no reset, RF-output transition, frequency or power write, modulation, Pulse, or Sweep configuration. See the [WaveBench Core configuration Reference](https://github.com/Scaxlibur/wavebench/blob/master/docs/reference/configuration.md) for exact generic fields and workflows.

## Safety boundary

- Importing the descriptor creates no transport, scans no ports, and sends no SCPI.
- The factory opens only the configured transport through `DriverContext`.
- Writes require explicit `read_write` access plus the corresponding capability, device state, port safety limits, and readback.
- The 50-ohm dBm reference for `rf_out` does not prove the actual termination; WaveBench does not infer a load from a connector name.
- Rear-panel `PULSE IN/OUT` and the 50-ohm RF output are separate interfaces and must not share electrical assumptions.
- Hardware tests require separate authorization and prior confirmation of the resource, firmware, termination, initial output state, safety limits, and recovery procedure.

Default tests use fake transports and do not connect to real instruments. See the [current Reference](doc/reference-en.md) for the available write surface, fixed profiles, and explicit exclusions.

## Development checks

```bash
python -m pytest -q packages/wavebench-rigol-dsg830/tests
python -m ruff check packages/wavebench-rigol-dsg830
python -m wavebench plugin package check packages/wavebench-rigol-dsg830
```

Use the repository-level [editable development environment](https://github.com/Scaxlibur/wavebench-instrument-plugins/blob/main/doc/DEVELOPMENT_EN.md) for ordinary source work.

## License

This plugin uses the [MIT License](LICENSE).
