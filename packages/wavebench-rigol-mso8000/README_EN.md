# WaveBench RIGOL MSO8000 Plugin (In Development)

This directory is the starting point for a WaveBench plugin for the RIGOL MSO8000 series, with the MSO8104 as the first target model. The MSO8104 is a 1 GHz, four-analog-channel mixed-signal oscilloscope; the programming guide also covers the MSO8064 and MSO8204.

## Current status

M0 through M4 are offline complete. Version `0.4.0` declares identity, coupling, fetch, single-capture, and multi-capture capabilities. Screenshot, digital, and consuming error-queue capabilities remain incomplete.

This development pass is offline-only. It uses the manual, FakeTransport tests, fault injection, builds, and installation lifecycle checks, and does not connect to hardware. Model, firmware, transport, throughput, restoration, and measurement claims remain unverified.

Current identity:

- Distribution: `wavebench-rigol-mso8000`
- Canonical driver ID: `rigol.mso8104`
- Kind: `scope`
- Target model: `MSO8104`
- Python: `>=3.11`
- WaveBench: `>=0.8.22,<0.9`

## Directory layout

- `doc/vendor-local/`: local vendor manuals. Keep the original PDF and the converted Markdown here; all files except its README are ignored and excluded from distributions.
- `src/wavebench_rigol_mso8000/`: descriptor, driver, and strict parsers.
- `tests/`: FakeTransport unit tests; default tests must not connect to hardware.
- `pyproject.toml`: distribution metadata, WaveBench version range, and the single entry point.
- `doc/`: public coverage matrices and acceptance notes. Keep vendor source material out of public documentation.

## Design documents

- [MSO8104 coverage milestones](doc/MSO8104_COVERAGE_MILESTONES_EN.md)
- [MSO8104 programming-guide coverage matrix](doc/MSO8104_COVERAGE_MATRIX_EN.md)

## Safety boundary

Descriptor import must not open a transport, scan ports, send SCPI, or create files. Never commit real resources, serial numbers, credentials, captures, screenshots, or command logs. Do not blindly retry instrument writes or acquisition triggers. When the core lacks a required safety interface, add an RFC and skip the capability instead of adding a raw SCPI escape hatch.

The descriptor accepts `tcpip`, `usb`, and `gpib` resource prefixes as a manual-backed, offline routing contract. This is not hardware connection evidence.

`channel_coupling()` combines channel coupling and input impedance. `AC/DC + OMEG` maps to the core high-impedance tokens `ACL/DCL`, while `AC/DC + FIFT` maps to the low-impedance tokens `AC/DC`; the core rejects 50 ohms, `GND`, and unknown states by default. The plugin does not declare `scope.errors` because `:SYSTem:ERRor?` consumes an entry while ordinary core text queries may replay. Future waveform service calls must explicitly set `scope.check_errors=false` until [RFC-0001](doc/rfcs/0001-nonreplayable-text-query.md) is implemented.

The waveform path accepts `DEF`, `MAX`, and `DMAX`. DEF uses `NORMal + BYTE + 1000` points; MAX retains its manual-defined running/stopped semantics; DMAX uses RAW and fetch requires an already stopped acquisition. The driver restores SOURCE, MODE, FORMAT, POINTS, START, and STOP. Long records use BYTE blocks of at most 250,000 points and a hard four-million-point total across all channels in one call. `scope.options.max_chunk_points` and `scope.options.max_total_points` may only tighten these limits. A block is queried exactly once through the core `query_bin_block()` API.

`capture_waveform(s)` requires every target channel to be displayed and MAIN timebase mode. A multi-channel call sends one `:SINGle`, polls `:TRIGger:STATus?` until STOP, then reads channels and checks X-axis consistency. It does not use `*OPC?` as acquisition evidence and never forces STOP, RUN, or another trigger. Timeout or uncertain status latches acquisition writes. Time-range and vertical-scale arguments remain unsupported, and capture leaves the scope in the natural STOP state reached by SINGLE.
