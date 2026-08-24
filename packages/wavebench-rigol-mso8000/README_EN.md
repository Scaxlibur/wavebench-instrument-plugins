# WaveBench RIGOL MSO8000 Plugin (In Development)

This directory is the starting point for a WaveBench plugin for the RIGOL MSO8000 series, with the MSO8104 as the first target model. The MSO8104 is a 1 GHz, four-analog-channel mixed-signal oscilloscope; the programming guide also covers the MSO8064 and MSO8204.

## Current status

Development version `0.9.0` retains the controlled MSO8104 identity and high-impedance CH1/CH2 evidence and declares `scope.fetch_waveform` through the bounded-binary contract in the current WaveBench core worktree. That entry currently accepts only `DEF`: it declares exact `LF` trailing, a `1,000`-byte response and operation limit, and one binary query; core owns recovery and fresh verification. `scope.capture_waveform` and `scope.capture_waveforms` remain paused; see [RFC-0008](doc/rfcs/0008-bounded-waveform-block-trailing-contract.md).

Hardware findings apply only to MSO8104 firmware `00.02.02`, LAN/PyVISA, and the controlled procedure. CH1 `DEF` block transfer and core-owned transfer-state restoration pass, but the returned data does not match the enabled `1 kHz / 1 Vpp` source. Frequency, Vpp, X/Y conversion, and measurement accuracy therefore still lack known-signal closure evidence.

Current identity:

- Distribution: `wavebench-rigol-mso8000`
- Canonical driver ID: `rigol.mso8104`
- Kind: `scope`
- Target model: `MSO8104`
- Python: `>=3.11`
- WaveBench: `>=0.8.24,<0.9`

The required standard-waveform bounded API is still an uncommitted implementation in the current core worktree. Version `0.9.0` is therefore for development and controlled acceptance only, not a compatibility-wheel release claim.

## M8 offline release evidence

- All 171 MSO8104 package tests and repository-wide Ruff checks pass.
- In a disposable sibling WaveBench-core layout, 715 root tests pass and two SP3000A private-hardware-evidence tests skip as expected.
- Package checks pass for both the source directory and the real wheel in the current WaveBench `0.8.24` development environment.
- The wheel/sdist contracts cover the single instrument entry point, WaveBench runtime dependency, MIT license, and public content; vendor-local material is absent.
- A disposable virtual environment passes installation, zero-I/O descriptor discovery, uninstall, and canonical-ID fallback.
- Local links resolve in all 61 tracked Markdown files.

This evidence covers offline contracts and distribution integrity only. Model, firmware, transport, throughput, restoration, and measurement accuracy remain hardware-unverified.

## Directory layout

- `doc/vendor-local/`: local vendor manuals. Keep the original PDF and the converted Markdown here; all files except its README are ignored and excluded from distributions.
- `src/wavebench_rigol_mso8000/`: descriptor, driver, and strict parsers.
- `tests/`: FakeTransport unit tests; default tests must not connect to hardware.
- `pyproject.toml`: distribution metadata, WaveBench version range, and the single entry point.
- `doc/`: public coverage matrices and acceptance notes. Keep vendor source material out of public documentation.

## Design documents

- [MSO8104 coverage milestones](doc/MSO8104_COVERAGE_MILESTONES_EN.md)
- [MSO8104 programming-guide coverage matrix](doc/MSO8104_COVERAGE_MATRIX_EN.md)
- [MSO8104 controlled hardware acceptance](doc/MSO8104_HARDWARE_ACCEPTANCE_EN.md)

## Safety boundary

Descriptor import must not open a transport, scan ports, send SCPI, or create files. Never commit real resources, serial numbers, credentials, captures, screenshots, or command logs. Do not blindly retry instrument writes or acquisition triggers. When the core lacks a required safety interface, add an RFC and skip the capability instead of adding a raw SCPI escape hatch.

The descriptor accepts `tcpip`, `usb`, and `gpib` resource prefixes as a manual-backed, offline routing contract. This is not hardware connection evidence.

The descriptor does not declare `scope.screenshot`. The manual does not specify TMC block framing for `:DISPlay:DATA?`, while `:SAVE:IMAGe:DATA?` cannot prove the core's `include_menu=False` contract. [RFC-0003](doc/rfcs/0003-scope-screenshot-framing-and-menu-contract.md) records both gaps. The plugin does not guess framing, ignore request parameters, or create instrument files.

The descriptor also omits `scope.digital_status` and `scope.digital_waveform`. The mandatory core status model contains fields that MSO8000 cannot query; see [RFC-0004](doc/rfcs/0004-portable-scope-digital-status.md). The vendor manual does not define BYTE/WORD logic codes for D0-D15 waveform sources and leaves WORD byte order unclear. The plugin does not invent digital state from defaults or analog conversion.

`scope.autoscale` intentionally changes vertical, timebase, and trigger settings under the core operation contract. The driver first queries `:SYSTem:AUToscale?`, requires `check_errors=false`, and latches only the autoscale write domain when the command or OPC completion is uncertain. Its command sequence and fault handling are offline-tested; autoscale effect remains hardware-unverified.

`scope.math_metadata` accepts only displayed MATH1-MATH4 slots in MAIN timebase mode. The driver saves all six waveform-transfer fields, switches to NORM before selecting the MATH source and BYTE format, reads only the preamble, and restores the previous state. It does not read waveform data. `values_per_sample` remains unknown and Y resolution is the documented eight-bit BYTE transfer width. Math content, FFT accuracy, and device restoration remain hardware-unverified.

`scope.cursor_readout` reads only an explicitly preconfigured global manual cursor, represented by public cursor index `1`. It accepts same-source A/B cursors in `TIME + SEC` or `AMPL + SOUR` configurations and does not move or reconfigure them. Tracking, XY, measurement mode, dual-source, NONE, LA amplitude, and nonportable units fail closed. Readout accuracy remains hardware-unverified.

`channel_coupling()` combines channel coupling and input impedance. `AC/DC + OMEG` maps to the core high-impedance tokens `ACL/DCL`, while `AC/DC + FIFT` maps to the low-impedance tokens `AC/DC`; the core rejects 50 ohms, `GND`, and unknown states by default. The plugin does not declare `scope.errors` because `:SYSTem:ERRor?` consumes an entry while ordinary core text queries may replay. Future waveform service calls must explicitly set `scope.check_errors=false` until [RFC-0001](doc/rfcs/0001-nonreplayable-text-query.md) is implemented.

The bounded `scope.fetch_waveform` path accepts only `DEF`. It uses core `query_binary()` rather than legacy `query_bin_block()`; the descriptor profile fixes `LF` trailing, the `1,000`-byte bound, and no replay. CH1 successfully returned 1000 samples and core completed five-field transfer-state restoration and fresh verification, but the observed data is about `5.25 mVpp / 8.89 kHz`, not the enabled `1 Vpp / 1 kHz` source. There is no MAX, DMAX, CH2, or dual-channel claim.

The offline driver still retains the `250,000`-point block and `4,000,000`-point total limits for long records. MAX, DMAX, single capture, and multi-channel capture each require their own bounded profile and acquisition-recovery evidence, and remain unavailable.
