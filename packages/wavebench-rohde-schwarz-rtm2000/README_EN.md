# WaveBench R&S RTM2000 Plugin

[中文](README.md)

A WaveBench instrument plugin for the Rohde & Schwarz RTM2000 oscilloscope series, using the RTM2032
as its representative hardware baseline.

## Start here

- [Find the current version, compatibility range, models, and capabilities](../../doc/reference/plugin-catalog-en.md)
- [Browse the RTM2000 plugin documentation](doc/README_EN.md)
- [Install and manage WaveBench plugins](https://github.com/Scaxlibur/wavebench/blob/master/docs/how-to/manage-plugins.md)

## Scope

Set `driver = "rohde-schwarz.rtm2032"` to select this external plugin. The short `rtm2032` alias
always selects the Core fallback; after removal, the canonical ID also falls back to the built-in
implementation.

The implementation covers analog waveform capture, coupling, explicit autoscale, screenshots,
read-only state and analysis data, and controlled average acquisition, channel display, and
multi-channel focus configuration. Option-dependent behavior such as B1 and K15 remains explicitly
gated, and unsupported advanced applications are not exposed through raw SCPI. The production
descriptor and generated plugin catalog are authoritative for exact capabilities, profiles,
configuration fields, and compatibility.

LAN connections use the Core-provided `rsinstrument-socket` backend by default. Other RsInstrument
backends declared by the descriptor can be selected explicitly for compatibility diagnosis. A
backend change requires a new session, and failed reads are not replayed automatically.

## Minimum configuration

```toml
[connection]
backend = "lan"
resource = "TCPIP::192.0.2.60::INSTR"

[scope]
driver = "rohde-schwarz.rtm2032"
default_channel = 1
check_errors = true

[scope.options]
long_waveform_timeout_ms = 300000
```

The example uses an RFC 5737 documentation address. Default tests do not scan resources, connect to
instruments, or send real SCPI.

## Safety boundary

The plugin owns RTM2000 vendor SCPI, waveform parsing, and device-error semantics. Core owns sessions,
permissions, high-impedance protection, artifacts, run plans, and experiment-level recovery. Never
commit real instrument resources, serial numbers, waveforms, screenshots, or command logs.

## Development and license

Use the repository-level [editable development environment](../../doc/DEVELOPMENT_EN.md) for source
development and offline checks. This plugin is licensed under the [MIT License](LICENSE).
