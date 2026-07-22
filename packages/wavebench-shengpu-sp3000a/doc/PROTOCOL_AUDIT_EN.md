# SP3000A Remote Protocol and Capability Audit

[中文](PROTOCOL_AUDIT.md)

This project-authored audit is derived from vendor documentation. It does not replace the vendor manual and does not claim hardware acceptance. Its purpose is to freeze the safety boundaries, data semantics, and staged probing order for the first driver.

## Audit decision

SP3000A exposes enough protocol surface to become a native WaveBench sweep analyzer: identity and major state can be queried, CW/sweep source behavior can be configured, trigger and averaging can be selected, and magnitude, phase, marker, and selected instrument-analysis results can be read.

The first version must preserve these boundaries:

- Use the generic instrument kind `sweep_analyzer`; `frequency_response` is a data/capability domain, not a second instrument kind.
- Keep `OUTPRFORM:CONT` off by default and acquire one bounded trace only through explicit `OUTPRFORM?` queries.
- Never treat one low-level `read()` as a complete response; accumulate by verified termination or expected token count.
- Do not infer the wire encoding, alignment, or byte order of `OUTSTATEC?` from a C-like field declaration.
- Use independent stable queries as the source of truth for snapshot and restoration. Keep `OUTSTATEC?` only as raw evidence until verified.
- Keep absolute dBm, relative dB, and linear voltage magnitude semantics distinct.
- Do not silently present a derived frequency axis as device-returned data; every axis must carry its source.
- External detection, discriminator, reflection/VSWR, and continuous streaming remain option-gated or high-side-effect capabilities and are not enabled by default.
- Never automatically run `*RST`, `PRES`, state save/recall, clock/language changes, or RF enable.
- Writes, triggers, and output control must not be retried blindly.

## Evidence levels

| Level | Meaning | Permitted use |
|---|---|---|
| Manual claim | Explicitly documented but not yet verified on the target unit | Candidate design, probe plan, conservative bounds |
| Hardware observation | Repeatedly observed on one target unit | Model/firmware-specific implementation and tests |
| Stable contract | Manual, hardware, and offline tests agree | Public API, default behavior, and release claims |
| Unknown | Missing, contradictory, or not uniquely parseable | Fail closed or report unsupported |

Before promoting a capability to a stable contract, record transport, firmware, pre-state, response format, side effects, and restoration result.

## Communication and sessions

### Manual claims

- Interfaces: RS-232, USB Device, and LAN; GPIB is optional.
- Commands use an ASCII SCPI-like syntax.
- Candidate RS-232 baud rates: 2400, 4800, 9600, 19200, 38400, and 115200.
- No parity uses 8 data bits; odd/even parity uses 7 data bits.
- Command termination is LF (`0x0A`).
- `*IDN?` returns instrument identity.
- A remote command enters RMT; `SYSTem:LOCal` returns control to the front panel.

### Not frozen

- Stop bits, software/hardware flow control, and response termination.
- Whether CRLF is accepted or commands are echoed.
- LAN/USB framing, timeouts, and maximum response size.
- Whether every write returns `OK`; the manual makes only a broad statement.
- Whether the connection remains usable after `SYSTem:LOCal` returns `LOC`.

The transport must expose serial parameters and read/write termination explicitly. Common RS-232 conventions are not device facts. The first driver must not depend on a standard SCPI error queue because the available material does not declare `SYST:ERR?`, `*CLS`, `*ESR?`, `*STB?`, or `*OPC?`.

## Device-private errors

The documentation defines `ERRORNo00` through `ERRORNo08` for syntax, invalid state, range, forbidden zero, forbidden negative value, floating-point format, numeric lexical format, missing data, and excessive digit count.

Map all of them to deterministic, non-retryable driver errors. Preserve a redacted raw response and re-query state where useful. Do not force them into the standard SCPI negative error-code model.

## Source and sweep state

Candidate fields for the first snapshot are:

| State | Query | Key semantics |
|---|---|---|
| Function | `FUNC?` | `CW` / `SWEEP`; switching may clear frequency offset |
| RF output | `RFSTAT?` | Hazardous state; keep off during configuration |
| Output level | `POWEr?` | Interpret the query as dBm; restore separately from RF state |
| Output impedance | `OUTOHMSEL?` | 50 Ω / 75 Ω and affects level interpretation |
| Frequency window | `CENS?` or `STAS?` | Center/span and start/stop are two views of one state |
| CW frequency | `CWFREQ?` | Used only by CW plans |
| Frequency offset | `FREQOFFSET?` | Affects CW and sweep display/output |
| Sweep-time mode | `SWETAUTO?` | `AUTO` / `MANU` |
| Sweep time | `SWET?` | Requested manual time is not guaranteed completion time |
| Frequency-axis mode | `SWET:MODE?` | `LIN` / `LOG`; distinct from display mode |
| Averaging | `SWET:AVER?`, `SWET:AVER:STATe?` | Count and enabled state are separate |
| Sweep execution | `TRIM?` | `CONT` / `SING`; distinct from trace streaming |
| Trigger | `EXTT?` | Internal/external; external trigger changes single/continuous semantics |

Restoration must avoid invalid intermediate states: restore a frequency window atomically; restore average count before enable; restore function and the primary window before frequency offset; handle RF output last. On cancellation or error, the safe default is RF off. Re-enabling the previous output requires explicit restoration authorization.

Conservative SP30120A model bounds are provisionally:

- frequency: 20 Hz–120 MHz;
- output level: −80 dBm to +10 dBm;
- output impedance: 50 Ω / 75 Ω;
- manual sweep time: 300 ms–100 s;
- average count: 1–10000;
- returned points: 20–730.

These are model capability limits, not WaveBench default safety limits. A task still needs stricter user safety configuration.

## Trace output

### Layout established by documentation

`OUTPRFORM:MODE` selects:

- `AMPT`: `A[0] ... A[P-1]`;
- `PHASE`: `φ[0] ... φ[P-1]`;
- `ALL`: P magnitude values followed by P phase values.

`OUTPRFORM:POINT:DATA` accepts 20–730 and changes the current sweep point count. It is a sweep-plan write, not merely a return-format setting. `OUTPRFORM:POINT ON` uses the configured point count; `OFF` uses the device maximum. Query the current trace with `OUTPRFORM?` and a stored trace with `OUTPMEMOV n?`. The manual describes comma-separated floating-point values.

### Not established by documentation

- response termination, trailing commas, whitespace, and numeric spelling;
- presence or absence of an IEEE 488.2 block header;
- whether one response is fragmented or coalesced with another;
- framing under `CONT ON`, or whether one scan equals one frame;
- whether extra `POINT OFF` values are internal samples, interpolation, repetition, or padding;
- payload behavior when `ALL` conflicts with magnitude/phase enablement;
- linear/log endpoint inclusion and discretization formula;
- actual magnitude units under ABS, REL, and linear display modes.

The first parser must therefore receive expected mode, expected points, and current display/measurement state. A count mismatch, non-finite token, mode conflict, or unknown unit must yield an incomplete result or error, never silent padding or guessing.

## Frequency-axis and magnitude semantics

Every frequency axis needs a source:

- `device`: every frequency value was explicitly returned;
- `derived`: reconstructed from queried start/stop or center/span, axis mode, and point count;
- `unknown`: it cannot be reconstructed reliably.

The available trace description does not show a frequency array in `OUTPRFORM?`, so a derived axis is likely, but endpoint formulas require hardware verification. Until then, the model must allow `frequency_hz=None` rather than inventing a precise-looking axis.

Magnitude semantics must distinguish at least:

- absolute input level in dBm;
- gain/loss relative to source output in dB;
- linear display values in V or mV;
- unknown, with raw tokens and context retained.

Phase is provisionally in degrees. All arrays require equal-length and finite-value checks.

## Input, detection, and measurement enablement

Internal detection supports 50 Ω, 75 Ω, or high-impedance input. External detection requires an option. External polarity, range, and probe correction may only be used when capabilities explicitly declare that option.

`AMPMEAS` and `PHAMEAS` cannot both be off; disabling one may enable the other. Snapshot and restoration must treat them as a coupled state.

Display scale, reference level, reference position, and phase scale are presentation state and do not belong in the generic numeric frequency-response model. No stable independent remote command for ABS/REL was found, so treat that state as unknown until verified.

## Markers and instrument-side analysis

The instrument exposes up to five markers and may return frequency, magnitude, phase, and delta values. WaveBench can normalize read-only results as `MarkerReading`, but marker display, search, and continuous tracking have state side effects.

Results such as −3 dB, −20 dB, Q, peak/valley, reflection coefficient, and VSWR must carry `method=instrument`. These functions are mutually interacting, may track continuously, may move markers automatically, or require calibration. The first version defines result containers only, not a generic write workflow.

Reflection/VSWR depends on fixtures, options, and a full-reflection reference. It must be option-gated and cannot be claimed solely from the SP3000A family name.

## `OUTSTATEC?` and stored state

The material lists a C-like `NowState` field set with level, averaging, sweep time, display, marker, impedance, trigger, points, and detection state, but it does not define wire encoding.

First-version rules:

1. permit an explicit read-only `OUTSTATEC?` probe;
2. retain the complete response as restricted raw evidence;
3. do not unpack it as a C struct;
4. do not replace independent snapshot/restoration queries with it;
5. provide no parser until ASCII/binary framing, field order, width, endianness, and alignment are verified.

Stored trace/state slot documentation conflicts among 1–9, 1–10, and 1–18. Provisionally expose trace slots 1–10, but verify slot 10. State recall is high-side-effect and excluded from first-version probing.

## Staged probe plan

### L0: offline parser and FakeTransport

- Parse identity, enums, scientific numbers, paired frequencies, and private errors.
- Parse bounded AMPT/PHASE/ALL token sequences.
- Reject count mismatch, non-finite values, trailing garbage, and unit ambiguity.
- Validate snapshot/restoration order without opening a transport.
- Verify that cancellation, timeout, and error do not cause blind retry.

Gate: fully offline; every unknown protocol point has an explicit failure test.

### L1: read-only queries

Base candidate order:

1. `*IDN?`;
2. `OUTPRFORM:CONT?`;
3. function, RF, level, impedance, frequency window, timing, axis mode, averaging, trigger, and sweep execution;
4. magnitude/phase enablement, detector mode, and input impedance;
5. current point-count and return-mode queries;
6. `OUTPRFORM?`;

Markers, stored slots, and `OUTSTATEC?` are not part of base L1. They require separately approved read-only probes after scalar queries and bounded-trace framing are stable. Every query enters RMT, so the test must record that session side effect and use a verified controlled procedure to return local control.

Gate: every query succeeds repeatedly, response boundaries are known, key configuration is unchanged, RMT/local cleanup is proven, and public records contain no resource or identity details.

### L2: configuration with RF unchanged, followed by restoration

First prove RF is off. Change one item at a time—`OUTPRFORM:CONT OFF`, return mode, or `OUTPRFORM:POINT ON/OFF`—and run snapshot → set → query confirmation → restore → query confirmation. `CONT ON`, `OUTPRFORM:POINT:DATA`, sweep parameters, reset, and state save/recall remain forbidden.

Gate: every field restores, all implicit coupling is recorded, and RF remains off after any failure.

### L3: controlled output and measurement

`OUTPRFORM:POINT:DATA`, the sweep plan, trigger, averaging, input/output impedance, source level, RF, and markers all belong to L3. After wiring, load, impedance, frequency, and level limits are confirmed, perform through calibration and a controlled DUT measurement. RF enable requires explicit authorization. A finally path first makes the output safe and only then restores prior state if authorized.

Gate: magnitude/phase traces repeat, axis and units are verified, instrument analysis agrees with WaveBench or an independent instrument, and fault-injected restoration succeeds.

## First-version non-goals

- continuous trace streaming;
- automatic `*RST` / `PRES`;
- state save or recall;
- automatic local/remote switching;
- clock, language, or beeper management;
- external-detector, discriminator, reflection, or VSWR write workflows;
- automatic marker search/tracking;
- unpacking `OUTSTATEC?` as a C struct;
- automatic retry based on unknown protocol behavior.

## Input to the M1 public contract

The core public model should express vendor-neutral semantics only:

- `SweepPlan`: CW/SWEEP, frequency window, linear/log, auto/manual time, continuous/single, internal/external trigger, averaging, points, and source-output plan;
- `FrequencyResponseTrace`: magnitude, phase, frequency axis, units, axis source, integrity, timestamp, and raw-evidence reference;
- `SweepAnalyzerSnapshot`: independently queryable and restorable stable fields;
- `MarkerReading`: frequency, magnitude, phase, and delta;
- `InstrumentMeasurementResult`: name, value, unit, and instrument/core method source;
- `TraceIntegrity`: completeness, expected/actual points, and warnings.

SP3000A-private commands, option enums, and `NowState` fields must not enter the core public API.
