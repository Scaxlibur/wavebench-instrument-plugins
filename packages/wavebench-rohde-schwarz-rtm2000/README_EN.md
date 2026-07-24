# WaveBench R&S RTM2000 plugin

[中文](README.md)

An executable WaveBench oscilloscope plugin for the Rohde & Schwarz RTM2000 series, with the
RTM2032 as the current hardware baseline.

## Identity and development baseline

- distribution: `wavebench-rohde-schwarz-rtm2000`
- canonical driver ID: `rohde-schwarz.rtm2032`
- development baseline: WaveBench `60dffd0`
- WaveBench: `>=0.8,<0.9`
- Python: `>=3.11`
- default transport backend: core-provided `rsinstrument-socket`

This plugin targets the WaveBench `v0.8.0` release and does not maintain a legacy-core
compatibility matrix, run with `v0.7.0`, or automatically claim compatibility with a future `0.9` core. When installed, the explicit canonical ID `rohde-schwarz.rtm2032` selects
the external implementation. The short alias `rtm2032` always selects the built-in fallback.
Removing the plugin restores the built-in implementation for the canonical ID as well.

## Capabilities and boundary

- `*IDN?`, error queue, and explicit autoscale;
- current-waveform fetch and single acquisition;
- one acquisition followed by multi-channel waveform reads;
- channel-coupling queries and PNG screenshots;
- pass-through RTM2000 `DEF`, `MAX`, and `DMAX` point modes.

The plugin owns RTM2000 SCPI, header/REAL waveform parsing, and device-error semantics. Core retains
the RsInstrument session, timeouts, high-impedance guard, services, artifacts, run plans, and
experiment-level restoration. Empty or short waveform lists, invalid headers, non-PNG screenshots,
and OPC timeouts fail explicitly; the plugin does not pad, fabricate success, or retry blindly.

`backend = "lan"` selects RsInstrument SocketIO according to descriptor preference and does not
depend on VISA-C or pyvisa-py. Explicit diagnostic compatibility paths are `rsinstrument`,
`rsinstrument-rsvisa`, and `rsinstrument-pyvisa-py`; changing backend requires a fresh session,
and a failed response is never replayed automatically. Only `MAX` and `DMAX` waveform data reads
use the dedicated long-transfer timeout. Chunk progress, point/byte counts, elapsed time, and
throughput telemetry exclude addresses, serial numbers, and waveform contents.

## Configuration example

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

The example uses an RFC 5737 documentation address. Offline tests do not scan resources, connect to
instruments, or send real SCPI.

## Acceptance status

Version 0.1.0 completed controlled RTM2032 LAN/VXI-11 acceptance with a real wheel on 2026-07-24. Managed
install and healthy/load checks, canonical-versus-short-alias routing, dual-channel single
acquisition, complete `DEF`, `MAX`, and `DMAX` waveforms, autoscale, the high-impedance coupling
guard, PNG screenshots, 20/20 repeated dual-channel captures, and an empty error queue all passed.
`MAX` returned 10,000,000 points per channel and `DMAX` returned 6,250,000 points per channel. Long
records used a separate 300-second transfer bound rather than treating the shared 30-second timeout
as a protocol failure. A complete setup snapshot was saved before mutation; the setup blob,
configuration fingerprint, and active acquisition state were all confirmed restored afterward.
The acceptance did not modify the real `wavebench.toml` or commit real addresses, serial numbers,
waveforms, screenshots, snapshots, or command logs. Experiment-level snapshot and restoration stay
in core/acceptance tooling rather than the vendor driver.

Version 0.2.0 changes the preferred LAN transport to RsInstrument SocketIO while retaining the
explicit compatibility backends above. Offline gates cover descriptor routing, per-call
long-transfer timeouts, sanitized telemetry, and the wheel lifecycle. RTM2032 hardware acceptance
passed for SocketIO DEF/MAX/DMAX, screenshot, autoscale, 20/20 repeated capture, and an empty error
queue. Experiment-level `SYST:SET` restoration is not a plugin-driver responsibility: a SocketIO
write once applied the setup only partially, so the acceptance tool uses the verified VXI-11
512-byte protocol chunks and performs read-only comparison of the complete blob, configuration
fingerprint, and active acquisition state after reconnecting. The final snapshot was deleted and
no real address, serial number, waveform, or command log entered the commit.

## Development checks

```bash
python -m pytest -q packages/wavebench-rohde-schwarz-rtm2000/tests
python -m ruff check packages/wavebench-rohde-schwarz-rtm2000
python -m wavebench plugin package check packages/wavebench-rohde-schwarz-rtm2000
```

Do not commit real addresses, serial numbers, waveforms, screenshots, or command logs. This package
is licensed under the [MIT License](LICENSE).

## Origin

Version 0.1.0 was migrated from the built-in RTM2032 protocol implementation at WaveBench `973fc88`.
Only the vendor driver, descriptor, entry point, and FakeTransport tests moved into this package.
