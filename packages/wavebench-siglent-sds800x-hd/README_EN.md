# WaveBench SIGLENT SDS800X HD Plugin

[中文](README.md)

An external WaveBench driver package for the SIGLENT SDS800X HD oscilloscope family. Version 0.1.0 is an M0 development scaffold: it is installable, discoverable, and capable of an identity query, but it does not expose waveform acquisition or state-changing operations.

## Current status

- Distribution: `wavebench-siglent-sds800x-hd` `0.1.0`
- Canonical driver ID: `siglent.sds800x-hd`
- Instrument kind: `scope`
- Backend: WaveBench core `pyvisa` transport
- Resource schemes: `tcpip`, `usb`
- Declared capability: `scope.idn`
- WaveBench: `>=0.8,<0.9`

Descriptor import performs no instrument I/O. The factory obtains exactly one core transport through `DriverContext.open_transport()`. The current driver only sends `*IDN?` and provides `close()` for transport cleanup.

## Product scope

The official data sheet lists these models:

- Two channels: `SDS802X HD`, `SDS812X HD`, and `SDS822X HD`.
- Four channels: `SDS804X HD`, `SDS814X HD`, and `SDS824X HD`.

The model range, LAN/USB interfaces, and SCPI remote-control support come from the [official SIGLENT SDS800X HD product material](https://www.siglent.com/int/products-overview/sds800x-hd/). The initial `idn_patterns` use public model strings only; they are not treated as complete identity authentication until a redacted hardware `*IDN?` sample is available.

The official data sheet specifies fixed `1 MΩ` analog inputs with no internal `50 Ω` termination, so the descriptor initially declares `fixed-high-impedance`. Coupling queries, probe attenuation, and external termination conditions still require target-hardware confirmation before waveform acquisition is enabled.

## Capabilities not exposed

Version 0.1.0 does not declare:

- `scope.errors`
- `scope.autoscale`
- `scope.fetch_waveform`
- `scope.capture_waveform` / `scope.capture_waveforms`
- `scope.screenshot`
- `scope.channel_coupling`
- any status, measurement, math, digital-channel, or history capability

Commands from the programming guide enter the driver and descriptor only after command-format review, fake-transport tests, and controlled hardware acceptance where required. The M0 scaffold is not a raw-SCPI surface and does not assume that another SIGLENT family uses an identical protocol.

## Programming-guide drop location

Place the local programming guide at:

```text
doc/vendor-local/SDS800XHD_Series_ProgrammingGuide.pdf
```

The actual downloaded filename may retain its version suffix. The official entry is [SDS800X HD Series Programming Guide](https://www.siglent.com/na/sds800x-hd-series-programming-guide/).

The repository-level `.gitignore` excludes every file under `doc/vendor-local/` except its explanatory README, and the sdist build excludes the whole directory. Vendor PDFs therefore do not enter Git pushes or public distributions. Project-authored protocol summaries, capability matrices, and acceptance records belong elsewhere under `doc/`.

## Next-stage gates

1. Add and record the programming-guide version locally.
2. Review termination, error-queue, screenshot, and waveform binary-block formats.
3. Obtain a redacted `*IDN?` sample and tighten identity matching.
4. Implement read-only error and current-waveform paths before acquisition or writes.
5. Add fake-transport tests and controlled hardware evidence for each capability.

## License

Project-authored code and documentation in this directory are licensed under the [MIT License](LICENSE). Locally retained vendor manuals do not thereby become MIT-licensed and are not part of the public distribution.
