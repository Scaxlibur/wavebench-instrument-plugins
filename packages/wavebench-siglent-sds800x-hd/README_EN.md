# WaveBench SIGLENT SDS800X HD Plugin

[中文](README.md)

A WaveBench instrument plugin for the SIGLENT SDS800X HD oscilloscope family. The SDS804X HD is the
current representative hardware baseline; exact identity responses and hardware scope for other
models remain bounded by the evidence pages.

## Start here

- [Find the current version, compatibility range, models, and capabilities](../../doc/reference/plugin-catalog-en.md)
- [Browse the SDS800X HD plugin documentation](doc/README_EN.md)
- [Install and manage WaveBench plugins](https://github.com/Scaxlibur/wavebench/blob/master/docs/how-to/manage-plugins.md)

## Current boundary

The implementation covers strict identity checks, analog-channel coupling, `DMAX` waveform reads and
single acquisitions, read-only measurement statistics, PNG screenshots, and standalone acquisition
run-state/control. The production descriptor and [coverage matrix](doc/SDS800X_HD_COVERAGE_MATRIX_EN.md)
are authoritative for exact capabilities, protocol behavior, model limits, and unsupported areas.

The family has fixed `1 MΩ` analog inputs and no internal `50 Ω` termination. CN11G documents no
error-queue command, so the plugin does not declare `scope.errors`. Waveform use must disable the
WaveBench error-queue check explicitly:

```toml
[scope]
driver = "siglent.sds800x-hd"
check_errors = false

[waveform]
format = "real"
byte_order = "lsbf"
points = "dmax"
```

Only `points="dmax"` is accepted. `points="def"`, `points="max"`, and `check_errors=True` fail before
instrument I/O. The plugin exposes no raw SCPI and does not assume protocol compatibility with other
SIGLENT families.

## Safety boundary

Descriptor import performs no instrument I/O, and the factory obtains its Core transport only through
`DriverContext.open_transport()`. Default tests use FakeTransport. Never commit real device resources,
serial numbers, raw waveforms, screenshots, or command logs.

## Development and license

The [plugin documentation](doc/README_EN.md) links local manuals, hardware acceptance, and Scope R1.3
conformance. Use the repository-level [editable development environment](../../doc/DEVELOPMENT_EN.md)
for source work. Project-authored code and documentation use the [MIT License](LICENSE); vendor material
is not part of the public distribution.
