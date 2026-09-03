# WaveBench Shengpu SP30120 Plugin

[中文](README.md)

An external WaveBench driver plugin for the Shengpu SP30120 digital sweep analyzer. The distribution retains the early incubation name `wavebench-shengpu-sp3000a`; that name does not assert that the SP30120 is the SP30120A described by the local manual.

## Start here

- [Find the current version, compatibility range, model, and capabilities](../../doc/reference/plugin-catalog-en.md)
- [Browse SP3000A development and evidence documentation](doc/README_EN.md)
- [Install and manage WaveBench plugins](https://github.com/Scaxlibur/wavebench/blob/master/docs/how-to/manage-plugins.md)

## Current boundary

The production descriptor declares only `sweep_analyzer.idn`. The driver also provides certified
scalar-state reads and five vendor-specific RF-OFF controls, but they do not constitute generic
SweepPlan, trace, analysis, configure, or trigger capabilities. The development index links the
command matrix and acceptance evidence that define exact command states and rejection boundaries.

There is no raw-SCPI surface, RF-output control, or uncertified parameter write. Curve framing, point
counts, units, and frequency-axis semantics do not yet form a verifiable contract, so exploratory
results are not exposed as frequency-response capability.

## Safety boundary

- Descriptor import and registry discovery perform zero instrument I/O. The factory opens exactly one core transport through `DriverContext.open_transport()`.
- Identity validation accepts only the hardware-observed `SHENGPU SP3000 Series Digital Sweeper` family string, with tolerance limited to case, whitespace, and a trailing period. The string does not prove a submodel or firmware version.
- `ERRORNo00` through `ERRORNo08` and the target firmware's undocumented literal `Error` are deterministic failures and are never retried automatically.
- Only vendor-specific RF-OFF setters listed by the certification matrix can write. There is no raw SCPI, trace acquisition, generic restoration, Local switching, RF control, or other write surface.
- Real serial resources, serial numbers, and raw logs must not enter the public repository.

## Development and license

The [development documentation](doc/README_EN.md) defines local vendor-material storage and publishing
boundaries. Use the repository-level [editable development environment](../../doc/DEVELOPMENT_EN.md)
for source work. Project-authored code and documentation use the [MIT License](LICENSE); vendor
material is not part of the public distribution.
