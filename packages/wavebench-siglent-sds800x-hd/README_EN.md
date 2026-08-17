# WaveBench SIGLENT SDS800X HD Plugin

[中文](README.md)

An external WaveBench driver package for the SIGLENT SDS800X HD oscilloscope family. Version 0.2.0 completes M1 with strict identity and analog-channel coupling queries. It does not expose waveform acquisition or state-changing operations.

## Current status

- Distribution: `wavebench-siglent-sds800x-hd` `0.2.0`
- Canonical driver ID: `siglent.sds800x-hd`
- Instrument kind: `scope`
- Backend: WaveBench core `pyvisa` transport
- Resource schemes: `tcpip`, `usb`
- Declared capabilities: `scope.idn`, `scope.channel_coupling`
- WaveBench: `>=0.8,<0.9`

Descriptor import performs no instrument I/O. The factory obtains exactly one core transport through `DriverContext.open_transport()`. The driver validates the four `*IDN?` fields, manufacturer, supported model, and 14-character ASCII serial, then caches the stable identity. Before reading coupling, it applies the model-specific two- or four-channel limit and sends `:CHANnel<n>:COUPling?`; only `AC`, `DC`, and `GND` are accepted. `close()` releases the transport idempotently.

## Product scope

The official data sheet lists these models:

- Two channels: `SDS802X HD`, `SDS812X HD`, and `SDS822X HD`.
- Four channels: `SDS804X HD`, `SDS814X HD`, and `SDS824X HD`.

The model range, LAN/USB interfaces, and SCPI remote-control support come from the [official SIGLENT SDS800X HD product material](https://www.siglent.com/int/products-overview/sds800x-hd/). The `idn_patterns` use public model strings, and the strict parser follows the CN11G four-field format. Model whitespace, casing, and firmware formatting remain outside hardware acceptance until a redacted `*IDN?` sample is available.

The official data sheet specifies fixed `1 MΩ` analog inputs with no internal `50 Ω` termination, so the descriptor initially declares `fixed-high-impedance`. Coupling queries, probe attenuation, and external termination conditions still require target-hardware confirmation before waveform acquisition is enabled.

## Current read-only capabilities

- `scope.idn` returns the validated original `*IDN?` text and caches it for the current driver session.
- `scope.channel_coupling` returns uppercase `AC`, `DC`, or `GND`; invalid types, channels missing from a model, and unknown responses fail at the driver boundary.

A direct coupling query reads identity first, preventing a CH3 or CH4 command on a two-channel model. The WaveBench status fallback already calls `idn()` first in the same session, so that path does not duplicate the identity query.

## Capabilities not exposed

Version 0.2.0 does not declare:

- `scope.errors`
- `scope.autoscale`
- `scope.fetch_waveform`
- `scope.capture_waveform` / `scope.capture_waveforms`
- `scope.screenshot`
- any status, measurement, math, digital-channel, or history capability

Other commands from the programming guide enter the driver and descriptor only after format review, FakeTransport tests, and controlled hardware acceptance where required. The plugin has no raw-SCPI surface and does not assume that another SIGLENT family uses an identical protocol.

## Programming-guide drop location

The local `CN11G` guide and its converted content remain under:

```text
doc/vendor-local/
```

Converter limits split the current copy across three directories. The manual support table lists `1.1.3.1` as the minimum SDS800X HD firmware. The official entry is [SDS800X HD Series Programming Guide](https://www.siglent.com/na/sds800x-hd-series-programming-guide/); project-authored conclusions are in the [coverage matrix](doc/SDS800X_HD_COVERAGE_MATRIX_EN.md).

The repository-level `.gitignore` excludes every file under `doc/vendor-local/` except its explanatory README, and the sdist build excludes the whole directory. Vendor PDFs therefore do not enter Git pushes or public distributions. Project-authored protocol summaries, capability matrices, and acceptance records belong elsewhere under `doc/`.

## Next-stage gates

M2 now contains an unexposed pure parsing layer for the 346-byte preamble, descriptor byte order,
signed 8/16-bit samples, WORD sample byte order, probe scaling, voltage conversion, and the
ten-division time axis. The descriptor still does not declare `scope.fetch_waveform`; pure-function
tests do not establish an instrument read transaction.

1. Obtain a redacted `*IDN?` sample and verify identity plus two- and four-channel coupling responses.
2. Define the `check_errors` failure boundary and transfer-setting restoration for `scope.fetch_waveform` without an error queue.
3. Use TCPIP and USB samples to verify binary blocks, chunking, WORD alignment, and timebase values.
4. Verify `*OPC?` waiting and one multichannel acquisition before considering capture or write capabilities.

## License

Project-authored code and documentation in this directory are licensed under the [MIT License](LICENSE). Locally retained vendor manuals do not thereby become MIT-licensed and are not part of the public distribution.
