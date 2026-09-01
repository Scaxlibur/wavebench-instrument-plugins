# WaveBench R&S RTM2000 plugin

[中文](README.md)

An executable WaveBench oscilloscope plugin for the Rohde & Schwarz RTM2000 series, with the
RTM2032 as the current hardware baseline.

## Identity and development baseline

- distribution: `wavebench-rohde-schwarz-rtm2000`
- canonical driver ID: `rohde-schwarz.rtm2032`
- development baseline: WaveBench `0.8.26`
- WaveBench: `>=0.8.26,<0.9`
- Python: `>=3.11`
- default transport backend: core-provided `rsinstrument-socket`

The plugin's 0.15.0 development line targets WaveBench `v0.8.26`, does not maintain a legacy-core
compatibility matrix, and does not automatically claim compatibility with a future `0.9` core. When installed, the explicit canonical ID `rohde-schwarz.rtm2032` selects
the external implementation. The short alias `rtm2032` always selects the built-in fallback.
Removing the plugin restores the built-in implementation for the canonical ID as well.

## Capabilities and boundary

- `*IDN?`, error queue, and explicit autoscale;
- vendor-specific read-only identity/options/health snapshots that do not consume event registers or the error queue;
- typed RTM2032 CH1/CH2 analog-channel, timebase, and probe-metadata snapshots;
- typed current-waveform X/Y scaling, point-count, quantization, and values-per-sample metadata;
- a typed read-only basic edge-trigger snapshot for RTM2032 CH1/CH2;
- read-only average/segmented acquisition state, with K15-only queries option-gated;
- controlled average acquisition, requiring the caller to confirm acquisition is stopped; it temporarily changes only average count, single count, and global channel arithmetic, reads the original configuration back after restoration, and latches further average writes if restoration is ambiguous;
- read-only K15 history timestamp tables for RTM2032 CH1/CH2;
- read-only statistics for an explicitly preconfigured automatic-measurement slot;
- read-only metadata/status for existing math, FFT, reference, and cursor state;
- read-only Scope V2 surfaces for channel input state, B1-gated digital status, a strict five-field
  identity snapshot, slot-1-to-4 measurement statistics without buffers, and three-field status for
  an explicitly configured FFT;
- `scope.channel_display_configure_v2` for RTM2032 CH1/CH2: core owns the typed baseline,
  post-write readback, failure restoration, and independent restoration verification, while the
  plugin performs only the selected channel's `STATE?` and `STATE ON/OFF` operations;
- `scope.focus_configure_v2` for RTM2000-series CH1/CH2: the RTM plugin profile declares channel,
  timebase, and V/div request guards, while core owns the complete joint baseline, post-write
  readback, failure restoration, and restoration verification;
- a vendor-specific minimal controlled RTM2032 CH2 edge-trigger configuration loop;
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

The second 0.5.0 increment adds `configure_ch2_edge_trigger(level_v=...)` without declaring a generic
trigger capability. It accepts only an enabled, non-overloaded, high-impedance `DCL/ACL` RTM2032 CH2
baseline and a finite level inside the current displayed range. Under the instance-wide reentrant I/O
lock it writes the fixed `EDGE / CH2 / AUTO / POS / DC / level` state, reads every field back,
requires the untouched hysteresis/holdoff settings to remain unchanged, and rechecks non-consuming
health and identity. Any timeout, readback mismatch, health fault, or identity drift after writing
begins permanently latches that instance's trigger-write path; subsequent calls fail with zero I/O.
There is no blind retry, automatic rollback, find-level, autoscale, single acquisition, error-queue
clear, or EVENT read. Persistent restoration remains the caller's responsibility. Controlled hardware
acceptance used a private fsync journal to change CH2 from 0.53 V to 0.65 V and restore 0.53 V; status
byte/questionable condition remained zero and acquisition count remained 53 before and after.

Version 0.6.0 connects those seven read-only sections to WaveBench 0.8.1's optional
`scope.snapshot` contract. `get_snapshot(channel)` aggregates identity, health, the selected analog
channel, timebase, probe, waveform metadata, and edge-trigger snapshots under the same instance I/O
lock. Only this canonical external descriptor declares the capability, so `wavebench scope status
--channel N` becomes available without requiring other scope drivers to implement it. Existing
`RTM2000*Snapshot` import names remain compatibility aliases of the public core models. The aggregate
path still reads no EVENT/error queue and sends no setting command. Controlled RTM2032 acceptance now
covers identity, CH1/CH2 snapshots, and acquisition status.

Version 0.7.0 adds the optional `scope.acquisition_status` and `scope.history_timestamps`
contracts from WaveBench 0.8.2. Both paths are query-only. K15-only queries require an exact K15
token from `*OPT?`; timestamp rows are built by strict positional matching of the relative-time,
absolute-time, and date `:ALL?` tables in oldest-to-newest order. No history segment is selected,
no acquisition is started, and the error queue is not consumed. RTM2032 acceptance confirmed K15 and
the read-only average/segmented status. The history timestamp-table query timed out, was not retried,
and remains blocked.

Version 0.8.0 adds `scope.measurement_statistics`. The caller must explicitly confirm that slot 1-4
was configured before the command. Buffer reads additionally require explicit confirmation that
acquisition is stopped. The implementation never configures, enables, or resets a slot and never
queries or clears the error queue. `NAN` actual/statistical values are represented as unavailable;
timeouts leave the operation outcome unknown and are not retried. A caller-confirmed CH2 frequency
slot passed controlled actual/average/min/max/stddev/count acceptance; stopped-acquisition buffer
reading remains pending.

Version 0.9.0 adds query-only analysis surfaces. Math and reference commands return metadata only;
they do not read waveform payloads or alter the global transfer format. FFT and cursor status require
explicit confirmation that the corresponding front-panel object is already configured. The plugin
does not define an FFT expression, move cursors, update/save/load references, start acquisition, or
consume the error queue. Math metadata, FFT status, and vertical cursor delta readout passed controlled
RTM2032 acceptance with front-panel restoration. Reference metadata remains blocked because reference
storage was empty; `UPDATE` was not used to manufacture test data.

Version 0.10.0 connects the WaveBench 0.8.5 `scope.capture_average` contract. This is a narrow,
controlled write path that requires explicit `--acquisition-stopped` caller confirmation. It preflights
the existing `REAL,32` / `LSBF` transfer format, temporarily writes only `ACQuire:AVERage:COUNt`,
`ACQuire:NSINgle:COUNt`, and global `CHANnel:ARITHmetics`, issues one `SINGle`, confirms
`ACQuire:AVERage:COMPlete?`, and reads the current waveforms. It does not write `FORMat`, byte order,
point mode, timebase, vertical scale, trigger, or K15 history state. Both successful and failed
acquisitions restore and read back all three configuration fields; failed or mismatched restoration
latches that instance's average-write path, so later calls fail with zero I/O. This has offline
transaction coverage but no independent hardware-acceptance conclusion yet.

Version 0.11.0 adds the read-only `scope.digital_status` surface. Every call first requires an
exact B1 token from `*OPT?`, then reads the activity and existing display, technology, threshold,
threshold-coupling, hysteresis, deskew, size, position, and label state for one explicit D0-D15
channel. It does not read `DIGital:DATA?`, write digital configuration or transfer format, start or
stop acquisition, or consume the error queue. RTM2032 hardware acceptance covered all D0-D15
channels in one session: 208 queries, zero writes, zero binary reads, correct four-group mapping,
and stable repeated D0 results. End-to-end CLI reads also passed for D0 and D15. At acceptance time
all digital channels were hidden, reported LOW activity, and used a 1.4 V threshold; those observed
values do not constitute electrical-input or digital-waveform-payload acceptance.

Version 0.12.0 adds the read-only `scope.digital_waveform` surface. The caller must explicitly
confirm that acquisition is stopped. The driver gates B1 through `*OPT?`, requires the existing
transfer format to be ASCII (documented as `ASC,0`; RTM2032 hardware reports `CSV,0`), then queries `DIGital<n>:DATA:POINts?`, `HEADER?`, `XORigin?`,
`XINCrement?`, and `DATA?` for every selected channel. Sample counts and X axes must match exactly
before host-side Dn→`uint16` bit n packing. The path sends no writes, does not switch STOP/RUN,
does not alter format, points, display, or thresholds, and does not consume the error queue. It has
FakeTransport acceptance. An RTM2032 read-only preflight passed the B1 and `CSV,0` gates, but D0
was hidden and `DIGital0:DATA:POINts?` returned zero, so the driver stopped before `DATA?` and
digital-payload hardware acceptance remains pending.

Version 0.13.0 maps five existing read-only surfaces to the WaveBench 0.8.25 Scope V2 contracts.
Channel input state derives coupling and termination only from `CHANnel<n>:COUPling?`, with numeric
impedance explicitly unavailable. Digital status reuses the existing B1-gated queries and marks
threshold scope and timing calibration unavailable. Snapshot V2 is fixed to five identity fields and
two queries. Measurement statistics accepts only preconfigured slots 1-4, reads no buffer, and
requires all five aggregates to be finite. FFT status exposes only average complete, RBW, and sample
rate. These adapters add no SCPI writes and do not alter the V1 methods, host-side FFT analysis, or
waveform-capture logic.
Controlled read-only RTM2032 acceptance passed for CH1/CH2 input state, CH1/CH2 identity snapshots,
and D0 digital status. Every related session was forced to `read_only`, with zero write requests and
zero binary writes. Measurement-statistics and FFT V2 remain bounded by offline equivalence tests and
their existing V1 hardware evidence; this run did not pretend to have fresh front-panel configuration
confirmation by passing `configured=True` without evidence.

Version 0.14.0 adds `scope.channel_display_configure_v2`. The descriptor profile limits writable
analog channels to CH1/CH2 and budgets one baseline query, one setter write plus core fresh readback,
and, on failure, one restoration write plus one independent verification query. The plugin neither
retries nor expands the operation to timebase or vertical settings, and it does not duplicate core's
recovery state machine. Controlled RTM2032 firmware `06.010` acceptance ran with both DG4202 outputs
off and both scope channels high-impedance `DCL` and not overloaded. It changed CH2 from `ON` to
`OFF`, confirmed that state independently, then used core to restore `OFF` to `ON`. The restoration
transaction recorded one completed text write, zero unknown write outcomes, zero binary writes, and
a healthy session. A final zero-write full snapshot confirmed CH1/CH2 both restored to `ON`, `DCL`,
and not overloaded.

Version 0.15.0 adds `scope.focus_configure_v2`. The RTM plugin profile limits analog channels to
CH1/CH2 and declares plugin-side timebase, per-channel V/div, and I/O-step guards. Core reads the
complete time range/position plus display, range, V/div, position, and offset for both channels in
one baseline. It preserves the requested joint view after success and restores in fixed timebase,
channel-vertical, channel-display order after any failure, followed by fresh verification.
Representative RTM2032 firmware `06.010` acceptance ran with both DG4202 outputs off and both scope
inputs high-impedance `DCL` and not overloaded. It changed 5 ms to 10 ms, changed CH2 from 0.2 V/div
to 0.4 V/div, and hid CH1; fresh readback proved both the target and restored states. The operation
then restored 5 ms, both channels at 0.2 V/div, and both displays on. All six text writes completed,
with zero unknown outcomes and zero binary writes. A new read-only session independently confirmed
the complete baseline, and both DG4202 outputs remained off. This RTM2032 is the representative
hardware baseline for the RTM2000 series; per-model repetition is not required. Profile bounds are
plugin request guards, not a claim that every boundary value was exercised on hardware. Partial-write
and failed-restoration paths are covered by controlled offline fault injection, not by inducing live
communication faults.

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
