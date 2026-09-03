# WaveBench SIGLENT SDG2000X Plugin

[中文](README.md)

A WaveBench instrument plugin for the SIGLENT SDG2042X, SDG2082X, and SDG2122X function/arbitrary waveform generators. The package registers the canonical driver ID `siglent.sdg2000x`, declares no aliases, and does not replace a bundled WaveBench driver.

## Start here

- [Check current capabilities, compatibility, and explicit exclusions](doc/SDG2000X_COVERAGE_MATRIX_EN.md)
- [Read development records and hardware evidence](doc/README_EN.md)
- [Install and manage plugins with WaveBench Core](https://github.com/Scaxlibur/wavebench/blob/master/docs/how-to/manage-plugins.md)

The current metadata version is `0.8.2`. The package `pyproject.toml` and production descriptor are authoritative for the version, compatibility range, and capabilities. The repository-level generated [plugin catalog](https://github.com/Scaxlibur/wavebench-instrument-plugins/blob/main/doc/reference/plugin-catalog-en.md) provides a checked summary.

> `source.harmonics_disable_v2` applies only to `SDG2122X` firmware `2.01.01.39R7T2`. A registered model does not imply that every capability, firmware revision, or profile can be extrapolated across the family.

## Read-only start

Merge this fragment into a valid `wavebench.toml` that already contains `[connection]` and `[scope]`. It uses an RFC 5737 documentation address and starts with `read_only` access:

```toml
[source]
driver = "siglent.sdg2000x"
resource = "TCPIP::192.0.2.40::INSTR"
default_channel = 1
check_errors = false
access = "read_only"

[safety_limits]
max_source_vpp = 10.0
```

`read_only` permits identity and status queries while Core rejects writes. `check_errors = false` records that the current descriptor declares no error-queue capability. See the [WaveBench Core configuration Reference](https://github.com/Scaxlibur/wavebench/blob/master/docs/reference/configuration.md) for generic fields and workflows.

## Safety boundary

- Importing the descriptor creates no transport and performs no instrument I/O.
- The factory opens only the configured transport through `DriverContext`.
- Default tests use fake transports and neither scan resources nor connect to real instruments.
- Output enable requires readable waveform, amplitude, offset, and composite-mode state, followed by Core enforcement of `max_source_vpp`.
- A profile, model, firmware, output state, or post-write readback outside the contract fails closed.
- Historical hardware evidence for an advanced command domain does not create a current public capability or a raw-SCPI endpoint.
- Hardware tests require separate authorization and prior confirmation of the resource, firmware, termination, initial output state, safety limit, and recovery procedure.

See the [current capability Reference](doc/SDG2000X_COVERAGE_MATRIX_EN.md) for exact writes, the Source V2 query budget, and unsupported areas.

## Development checks

```bash
python -m pytest -q packages/wavebench-siglent-sdg2000x/tests
python -m ruff check packages/wavebench-siglent-sdg2000x
python -m wavebench plugin package check packages/wavebench-siglent-sdg2000x
```

Use the repository-level [editable development environment](https://github.com/Scaxlibur/wavebench-instrument-plugins/blob/main/doc/DEVELOPMENT_EN.md) for ordinary source work.

## License

This plugin uses the [MIT License](LICENSE).
