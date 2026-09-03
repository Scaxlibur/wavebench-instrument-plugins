# WaveBench SIGLENT SDS3000 Plugin

[中文](README.md)

This package targets the early SIGLENT SDS3000 oscilloscope family and excludes later products whose
names contain `X` or `HD`. The production descriptor currently registers only the verified SDS3054.

## Start here

- [Find the current version, compatibility range, model, and capabilities](../../doc/reference/plugin-catalog-en.md)
- [Browse the SDS3000 plugin documentation](doc/README_EN.md)
- [Install and manage WaveBench plugins](https://github.com/Scaxlibur/wavebench/blob/master/docs/how-to/manage-plugins.md)

## Current boundary

The implementation covers strict identity checks, error-register reads, channel coupling, binary
waveform reads, and single- or same-acquisition multi-channel capture. The production descriptor and
[WaveBench capability matrix](doc/WAVEBENCH_CAPABILITY_MATRIX_EN.md) are authoritative for exact
capabilities, firmware and option limits, unsupported areas, and protocol dispositions.

The SDS3054 uses the Teledyne LeCroy MAUI/X-Stream command family. When the front panel selects
`TCP/IP (VICP)`, use `VICP::<host>::INSTR`. `TCPIP::<host>::INSTR` denotes VXI-11 and requires the
front-panel `LXI (VXI-11)` mode. The resource forms are not interchangeable.

This identity and protocol boundary does not extend to arbitrary LeCroy instruments, SDS3000X,
SDS3000X HD, or other SIGLENT SDS families.

## Safety boundaries

- Do not infer this protocol from SDS3000X, SDS3000X HD, or other newer SIGLENT SDS manuals.
- Do not create a public interface outside WaveBench to fill missing capabilities; submit a separate core proposal when required.
- Descriptor import must not connect to an instrument, scan resources, create files, or mutate global state.
- A driver may obtain the core transport only through `DriverContext.open_transport()`.
- Instrument writes, output changes, and acquisition triggers must not be retried blindly.
- Real resources, serial numbers, credentials, raw waveforms, screenshots, and laboratory logs must not be committed.

## Development and license

The [plugin documentation](doc/README_EN.md) covers local manuals, audit order, and publishing
boundaries. Use the repository-level [editable development environment](../../doc/DEVELOPMENT_EN.md)
for source work. Project-authored code and documentation use the [MIT License](LICENSE); vendor
material retains its original rights status and is not part of the public distribution.
