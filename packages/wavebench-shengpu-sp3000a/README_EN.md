# WaveBench Shengpu SP30120 Plugin

[中文](README.md)

An external WaveBench driver plugin for the Shengpu SP30120 digital sweep analyzer. The distribution retains the early incubation name `wavebench-shengpu-sp3000a`; that name does not assert that the SP30120 is the SP30120A described by the local manual.

## Current status

M3 now provides an installable query-only distribution, a V2 entry point, a driver, FakeTransport tests, and a wheel lifecycle test:

- Distribution: `wavebench-shengpu-sp3000a` 0.1.0
- Canonical driver ID: `shengpu.sp30120`
- Instrument kind: `sweep_analyzer`
- Backend: WaveBench core `serial` transport
- Declared capability: `sweep_analyzer.idn`
- WaveBench: `>=0.8,<0.9`

The driver also exposes the hardware-verified scalar state subset: RF state, input/output impedance, center/span and start/stop frequencies, CW frequency, offset, sweep time, linear/logarithmic mode, continuous/single execution, and external-trigger state. It sends only fixed allowlisted queries and does not retry device-private errors automatically.

A generic `SweepAnalyzerSnapshot` requires a complete effective plan including function, power, averaging, and measurement state. Those fields are not reliably queryable on the target firmware, so version 0.1.0 does not declare `sweep_analyzer.status`. `frequency_response` remains a generic capability and data domain, not another instrument kind. M4 trace framing, point count, units, and frequency-axis semantics are unverified, so trace, marker, and analysis capabilities are also omitted. Configuration, triggering, and RF output methods are not exposed.

See the [remote protocol and capability audit](doc/PROTOCOL_AUDIT_EN.md) and [RS-232 read-only protocol acceptance](doc/RS232_READONLY_ACCEPTANCE_EN.md).

## Safety boundary

- Descriptor import and registry discovery perform zero instrument I/O. The factory opens exactly one core transport through `DriverContext.open_transport()`.
- Identity validation accepts only the hardware-observed `SHENGPU SP3000 Series Digital Sweeper` family string, with tolerance limited to case, whitespace, and a trailing period. The string does not prove a submodel or firmware version.
- `ERRORNo00` through `ERRORNo08` and the target firmware's undocumented literal `Error` are deterministic failures and are never retried automatically.
- Version 0.1.0 exposes no raw SCPI, writes, trace acquisition, state restoration, Local switching, or RF control.
- Real serial resources, serial numbers, and raw logs must not enter the public repository.

This package targets the WaveBench `v0.8.0` release. It does not run with `v0.7.0` and does not automatically claim compatibility with a future `0.9` core.

## Manual drop location

Copy the local Markdown manual to:

```text
doc/vendor-local/SP3000A_manual.md
```

Git ignores all content under `doc/vendor-local/` except its explanatory README, and the sdist build excludes the entire directory. Local manuals are therefore absent from both repository pushes and public distribution artifacts. Project-authored capability matrices, communication notes, SCPI summaries, trace-format documentation, and acceptance plans will live under `doc/` and will distinguish manual claims from hardware-verified behavior.

## License

Project-authored code and documentation in this directory are licensed under the [MIT License](LICENSE). Locally retained vendor manuals and transcriptions do not thereby become MIT-licensed and are not part of the public distribution.
