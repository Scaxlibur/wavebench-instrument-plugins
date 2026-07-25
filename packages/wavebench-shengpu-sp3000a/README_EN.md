# WaveBench Shengpu SP30120 Plugin

[中文](README.md)

An external WaveBench driver plugin for the Shengpu SP30120 digital sweep analyzer. The distribution retains the early incubation name `wavebench-shengpu-sp3000a`; that name does not assert that the SP30120 is the SP30120A described by the local manual.

## Current status

Version 0.2.0 adds M3.5 vendor-specific, typed RF-OFF controls to the M3 query-only baseline:

- Distribution: `wavebench-shengpu-sp3000a` 0.2.0
- Canonical driver ID: `shengpu.sp30120`
- Instrument kind: `sweep_analyzer`
- Backend: WaveBench core `serial` transport
- Declared capability: `sweep_analyzer.idn`
- WaveBench: `>=0.8,<0.9`

The driver also exposes the hardware-verified scalar state subset: RF state, input/output impedance, center/span and start/stop frequencies, CW frequency, offset, sweep time, linear/logarithmic mode, continuous/single execution, and external-trigger state. It sends only fixed allowlisted queries and does not retry device-private errors automatically.

An M0–M3 command-certification run, with RF held OFF, passed three consecutive reversible cycles for TRIM, reference position, clock display, UI language, and external trigger. Version 0.2.0 exposes them as vendor-specific typed methods on `SP30120SweepAnalyzer`: `set_trim()`, `set_reference_position()`, `set_clock_display()`, `set_ui_language()`, and `set_external_trigger()`; matching read APIs use only each command's stable query. They do not satisfy the generic SweepPlan contract, so the descriptor still declares only `sweep_analyzer.idn`.

Each valid setter invocation performs one canonical write under one instance lock: identity and RF-OFF preflight, a complete core fingerprint, original-value query, write, independent exact readback, RF-OFF postcheck, and core-fingerprint plus identity postchecks. It never retries or restores the original value automatically. Any post-write exception, readback mismatch, RF-not-OFF state, or fingerprint drift permanently latches that instance's write path; later writes are rejected with zero I/O. Close the instance and independently verify the instrument before reopening it. RF ON is only an interlock failure and is never changed automatically.

A generic `SweepAnalyzerSnapshot` requires a complete effective plan including function, power, averaging, and measurement state. Those fields are not reliably queryable on the target firmware, so version 0.2.0 does not declare `sweep_analyzer.status`. `frequency_response` remains a generic capability and data domain, not another instrument kind. M4 trace framing, point count, units, and frequency-axis semantics are unverified, so trace, marker, analysis, generic configure, and trigger capabilities are also omitted. The driver exposes no RF-output, frequency-window, SweepPlan, arbitrary-SCPI, or uncertified-parameter write surface.

M4 trace-protocol confirmation completed controlled hardware exploration but did not pass. `OUTPRFORM?` repeatably returns complete LF-terminated 1002-token frames (501 finite amplitude candidates followed by 501 zeroes); however, canonical and compact MODE, POINT, CONT, amplitude/phase-measurement, and 20/200/730-point writes did not change either an independent `OUTSTATEC?` snapshot or the curve shape. The firmware also supplies no verifiable readback for these configuration queries. Version 0.2.0 therefore declares no trace capability and does not promote exploratory frames into a frequency-response contract.

M4 now includes a strict offline parser that is not wired into the descriptor or driver. It accumulates through LF, requires exactly P finite values for a single mode or 2P finite values for ALL, and rejects short or long frames, malformed tokens, non-ASCII data, NaN/Inf, trailing bytes, and unterminated frames. Private 501+501 complete evidence and a 739-token truncation exercise that parser, but this validates framing logic only; it does not accept write commands, mode changes, point counts, units, restoration, or a trace capability.

See the [remote protocol and capability audit](doc/PROTOCOL_AUDIT_EN.md), [RS-232 read-only protocol acceptance](doc/RS232_READONLY_ACCEPTANCE_EN.md), [command certification plan](doc/COMMAND_CERTIFICATION_PLAN_EN.md), and [per-command matrix](doc/COMMAND_CERTIFICATION_MATRIX_EN.md). Manual-only commands do not enter the driver before satisfying those gates.

## Safety boundary

- Descriptor import and registry discovery perform zero instrument I/O. The factory opens exactly one core transport through `DriverContext.open_transport()`.
- Identity validation accepts only the hardware-observed `SHENGPU SP3000 Series Digital Sweeper` family string, with tolerance limited to case, whitespace, and a trailing period. The string does not prove a submodel or firmware version.
- `ERRORNo00` through `ERRORNo08` and the target firmware's undocumented literal `Error` are deterministic failures and are never retried automatically.
- Version 0.2.0 exposes only the five vendor-specific RF-OFF setters above; it exposes no raw SCPI, trace acquisition, generic restoration, Local switching, RF control, or other writes.
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
