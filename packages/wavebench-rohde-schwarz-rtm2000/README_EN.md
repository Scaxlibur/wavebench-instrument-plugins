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
- vendor-specific read-only identity/options/health snapshots that do not consume event registers or the error queue;
- typed RTM2032 CH1/CH2 analog-channel, timebase, and probe-metadata snapshots;
- typed current-waveform X/Y scaling, point-count, quantization, and values-per-sample metadata;
- a typed read-only basic edge-trigger snapshot for RTM2032 CH1/CH2;
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

## Programming-manual location

Place the RTM2000-series oscilloscope programming manual at:

```text
doc/vendor-local/RTM2000_programming_manual.pdf
```

The vendor's original filename may also be retained. All content under `doc/vendor-local/` except its explanatory README is ignored by Git, and the entire directory is excluded from the sdist, so vendor manuals are not pushed with the repository or published in public distribution artifacts. Project-authored SCPI indexes, capability matrices, and acceptance material should live separately under public `doc/` and distinguish manual claims from hardware-verified behavior.

See the [RTM2000 manual feature coverage matrix](doc/RTM2000_COVERAGE_MATRIX_EN.md) for the current comparison across the manual surface, external plugin, bundled fallback, and hardware evidence.

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

The 0.3.0 development line adds strict typed read-only identity/options/health snapshots. The health
snapshot reads only `*STB?`, operation/questionable condition, acquisition available/count, and sample
rate. It does not consume event registers or drain the error queue. This vendor-specific API does not
expand the WaveBench core capability declaration. Version 0.3.0 also adds RTM2032 CH1/CH2 analog-
channel, timebase, and probe-metadata snapshots. `FULL` bandwidth, `UNKN` impedance, and instrument
unavailable-value sentinels map to `None`; unknown values in closed enums, malformed open tokens,
non-finite values, unquoted text, and indexes outside CH1/CH2 fail closed. The command index establishes command-surface existence only; return
types come from controlled read-only RTM2032 measurements and are not generalized to every RTM2000
model. Hardware acceptance covered both channels, the current timebase, and passive-probe state and
left the status byte at zero. It read no event/error queue and sent no setting command.

Version 0.4.0 adds the vendor-specific read-only `waveform_metadata_snapshot(channel)` API. It
cross-checks `DATA:HEADER?`, `POINTs?`, X increment/origin, and returns Y increment/origin, vertical
quantization bits, and values per sample interval. Unknown, non-integral, non-finite, or mixed-record
X-axis responses fail closed. Controlled RTM2032 CH2 acceptance returned 10,000 points, a 200 ns X
increment, 20 mV/bit, and 8-bit resolution. Status byte, operation/questionable condition, and
acquisition count showed no error or count change, and no write was sent. On a running acquisition,
the operation condition may naturally move between waiting and non-waiting states during the trigger
cycle, so it is not treated as a constant before/after invariant. The fourth `DATA:HEADER?` field is
not a segment identity; history/segment identity remains outside this release claim.

The first version 0.5.0 increment adds the vendor-specific read-only `edge_trigger_snapshot()` API.
Its closed domains intentionally cover only the RTM2032 hardware-verified
`EDGE / CH1|CH2 / AUTO / POS / DC / hysteresis AUTO / holdoff OFF` baseline. Unknown trigger types,
sources, modes, slopes, coupling, or holdoff modes fail closed rather than inferring response domains
from the command index. Read-only CH2 calibration-square-wave acceptance returned a 0.53 V trigger
level and 50 ns holdoff time. Nine queries left status byte, questionable condition, and acquisition
count healthy, consumed no event/error queue, and sent no write.

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
