# WaveBench RIGOL DG4000 Plugin

[中文](README.md)

A WaveBench instrument plugin for the dual-channel RIGOL DG4202 and compatible DG4000
function/arbitrary waveform generators.

## Start here

- [Find the current version, entry points, models, and capabilities](../../doc/reference/plugin-catalog-en.md)
- [Browse the DG4000 plugin documentation](doc/README_EN.md)
- [Install and manage WaveBench plugins](https://github.com/Scaxlibur/wavebench/blob/master/docs/how-to/manage-plugins.md)

## Driver entries

- `rigol.dg4202`: retains existing V1 routes and exposes the declared Source V2 Basic, Output, and Counter operations.
- `rigol.dg4202-v2`: explicit opt-in entry for constrained Sweep configure/manual-fire operations.
- `rigol.dg4202-v2-workspace`: explicit opt-in entry for unscoped volatile-ARB workspace replacement.

None of the entries declares an alias; the short `dg4202` alias always selects the Core fallback.
The production descriptors and generated plugin catalog are authoritative for each entry's exact
capabilities, profiles, version range, and conformance evidence references.

The implementation also covers strict read-only snapshots and profiles, fixed-wave configuration,
output control, and validated DAC14 uploads. Core owns waveform-file loading, normalization,
amplitude safety limits, services, run plans, state restoration, and artifacts.

## Minimum configuration

```toml
[connection]
backend = "lan"
resource = "TCPIP::192.0.2.30::INSTR"

[source]
driver = "rigol.dg4202"
model_hint = "DG4202"
default_channel = 1
check_errors = true
```

The example uses an RFC 5737 documentation address. Advanced Sweep or volatile-workspace behavior
requires explicit selection of the corresponding opt-in driver ID.

## Safety boundary

Descriptor import performs no instrument I/O. Default tests do not scan resources, connect to an
instrument, or send real SCPI. Output control, arbitrary-wave uploads, and other writes are not
retried blindly. Volatile USER/workspace content may be overwritten and cannot be promised restored.
Never commit real resources, serial numbers, waveforms, screenshots, or command logs.

## Development and license

The [plugin documentation](doc/README_EN.md) links the coverage matrix, milestones, conformance, and
historical acceptance material. Use the repository-level
[editable development environment](../../doc/DEVELOPMENT_EN.md) for source work. This plugin is
licensed under the [MIT License](LICENSE).
