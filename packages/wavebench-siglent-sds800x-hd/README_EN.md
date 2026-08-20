# WaveBench SIGLENT SDS800X HD Plugin

[中文](README.md)

An external WaveBench driver package for the SIGLENT SDS800X HD oscilloscope family. Version 0.5.0 provides strict identity, analog-channel coupling, stopped-record and single-acquisition `DMAX` reads, plus read-only statistics for preconfigured measurement slots. Single- and multi-chunk reads, single- and dual-channel capture, sequence rejection, and measurement statistics are hardware accepted on an SDS804X HD.

## Current status

- Distribution: `wavebench-siglent-sds800x-hd` `0.5.0`
- Canonical driver ID: `siglent.sds800x-hd`
- Instrument kind: `scope`
- Backend: WaveBench core `pyvisa` transport
- Resource schemes: `tcpip`, `usb`
- Declared capabilities: `scope.idn`, `scope.channel_coupling`, `scope.fetch_waveform`, `scope.capture_waveform`, `scope.capture_waveforms`, `scope.measurement_statistics`
- WaveBench: `>=0.8,<0.9`

Descriptor import performs no instrument I/O. The factory obtains exactly one core transport through `DriverContext.open_transport()`. The driver validates the four `*IDN?` fields, manufacturer, supported model, and 14-character ASCII serial, then caches the stable identity. Before reading coupling, it applies the model-specific two- or four-channel limit and sends `:CHANnel<n>:COUPling?`; only `AC`, `DC`, and `GND` are accepted. Waveforms use the core `query_bin_block()` transport and return the core `WaveformData` / `WaveformHeader` models. `close()` releases the transport idempotently.

## Product scope

The official data sheet lists these models:

- Two channels: `SDS802X HD`, `SDS812X HD`, and `SDS822X HD`.
- Four channels: `SDS804X HD`, `SDS814X HD`, and `SDS824X HD`.

The model range, LAN/USB interfaces, and SCPI remote-control support come from the [official SIGLENT SDS800X HD product material](https://www.siglent.com/int/products-overview/sds800x-hd/). The `idn_patterns` use public model strings, and the strict parser follows the CN11G four-field format. A redacted SDS804X HD sample is now accepted; exact responses from the other five models remain pending.

The official data sheet specifies fixed `1 MΩ` analog inputs with no internal `50 Ω` termination, so the descriptor declares `fixed-high-impedance`. Coupling, `1×` probe factors, and the high-impedance connection were confirmed on the SDS804X HD; other models remain pending.

## Current capabilities

- `scope.idn` returns the validated original `*IDN?` text and caches it for the current driver session.
- `scope.channel_coupling` returns uppercase `AC`, `DC`, or `GND`; invalid types, channels missing from a model, and unknown responses fail at the driver boundary.
- `scope.fetch_waveform` reads an already-stopped, non-sequence analog record and currently supports only `points="dmax"`.
- `scope.capture_waveform` / `scope.capture_waveforms` perform one SINGLE acquisition, wait for Stop, and read one or more analog channels; only `points="dmax"` is currently supported.
- `scope.measurement_statistics` reads an already configured and enabled advanced-measurement slot without creating slots, enabling statistics, or resetting history.

A direct coupling query reads identity first, preventing a CH3 or CH4 command on a two-channel model. The WaveBench status fallback already calls `idn()` first in the same session, so that path does not duplicate the identity query.

Waveform fetch does not start a new acquisition and sends no `RUN`, `SINGLE`, or `STOP`. The driver requires `:TRIGger:STATus?` to return `Stop` and `:ACQuire:SEQuence?` to return `OFF`, then saves `SOURCE`, `START`, `INTERVAL`, `POINT`, `WIDTH`, and `BYTEorder`. The transaction temporarily selects `WORD`, `LSB`, `START 0`, `INTERVAL 1`, and `POINT 0`, reads chunks according to `MAXPoint?`, and restores the original transfer state in dependency order on both success and failure.

Single capture writes and verifies `TRIGger:MODE SINGLE`, sends `TRIGger:RUN`, polls `TRIGger:STATus?` until Stop, and then requires `ACQuire:NUMACq? >= 1`. A timeout or ignored mode write sends `TRIGger:STOP`. Multichannel capture performs one acquisition and then reads every requested channel from the same stopped record. It does not use `*OPC?` as a substitute for physical trigger completion.

Statistics calls require explicit confirmation that the slot is already configured. The driver also verifies advanced-measurement mode, the slot switch, and the statistics switch before reading current, mean, minimum, maximum, standard deviation, and count. History is read only after explicit confirmation that acquisition is stopped. All statistics paths are query-only.

CN11G documents no error-queue query, so the plugin does not declare `scope.errors`. WaveBench requires that capability when `scope.check_errors=true`; waveform use therefore requires explicit configuration:

```toml
[scope]
driver = "siglent.sds800x-hd"
check_errors = false

[waveform]
format = "real"
byte_order = "lsbf"
points = "dmax"
```

Direct driver calls with `check_errors=True`, `points="def"`, or `points="max"` fail before any instrument I/O. CN11G specifies only an integer NR1 parameter for `WAVeform:POINt`; this version does not invent unverified instrument keywords for WaveBench `DEF/MAX` modes.

## Capabilities not exposed

Version 0.5.0 does not declare:

- `scope.errors`
- `scope.autoscale`
- `scope.screenshot`
- standalone RUN/STOP/SINGLE control or any other status, measurement-configuration, math, digital-channel, or history capability

Other commands from the programming guide enter the driver and descriptor only after format review, FakeTransport tests, and controlled hardware acceptance where required. The plugin has no raw-SCPI surface and does not assume that another SIGLENT family uses an identical protocol. `scope.fetch_waveform` reads an existing record; it is not equivalent to `capture_waveform`.

## Programming-guide drop location

The local `CN11G` guide and its converted content remain under:

```text
doc/vendor-local/
```

Converter limits split the current copy across three directories. The manual support table lists `1.1.3.1` as the minimum SDS800X HD firmware. The official entry is [SDS800X HD Series Programming Guide](https://www.siglent.com/na/sds800x-hd-series-programming-guide/); project-authored conclusions are in the [coverage matrix](doc/SDS800X_HD_COVERAGE_MATRIX_EN.md) and [hardware acceptance record](doc/SDS800X_HD_HARDWARE_ACCEPTANCE_EN.md).

The repository-level `.gitignore` excludes every file under `doc/vendor-local/` except its explanatory README, and the sdist build excludes the whole directory. Vendor PDFs therefore do not enter Git pushes or public distributions. Project-authored protocol summaries, capability matrices, and acceptance records belong elsewhere under `doc/`.

## Next-stage gates

1. Obtain redacted `*IDN?` samples from additional SDS800X HD models and verify identity plus two- and four-channel coupling responses.
2. When USB hardware becomes available, verify binary blocks, WORD alignment, timebase values, and transfer-state restoration; real TCPIP multi-chunk reading is accepted.
3. Consider `DEF/MAX` point modes only after explicit protocol or hardware evidence; do not guess keywords.
4. Extend screenshot, standalone acquisition control, and math only after reviewing the `R1.2 Draft`
   [generic Scope RFC](../../doc/rfcs/WaveBench_scope通用扩展接口RFC.md) and freezing the core
   contract; do not bypass the core with private raw SCPI.

## License

Project-authored code and documentation in this directory are licensed under the [MIT License](LICENSE). Locally retained vendor manuals do not thereby become MIT-licensed and are not part of the public distribution.
