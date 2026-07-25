# SP3000A RS-232 Read-Only Protocol Acceptance

[中文](RS232_READONLY_ACCEPTANCE.md)

## Decision

The first M2 read-only probe was performed against one powered-on SP3000-series unit. At `9600 baud / 8N1 / no flow control / LF`, the RS-232 link reliably supports identity and a subset of core state queries. Several manual-listed candidate queries either timed out or returned the undocumented literal `Error` on the target firmware. The result is therefore **partial acceptance of scalar read-only protocol behavior; no trace query was authorized, and M2 is not fully closed**.

The initial read-only matrix sent no configuration, trigger, output, reset, save/recall, or remote-to-local command. After explicit authorization, two manual-scoped controlled writes were added: `OUTPRFORM:CONT OFF` to attempt to disable continuous trace streaming, followed by `SYSTem:LOCal` to attempt to return control to the panel. Neither produced the documented confirmation, and RF, sweep parameters, display, markers, detection, and stored slots were not changed. The real serial resource and laboratory-only logs are excluded from this public record.

## Session and framing

- Passive listening was quiet after opening the confirmed target resource and before the first query.
- `*IDN?` returned the same 38-byte ASCII line in 5/5 repetitions.
- The identity response states only `SHENGPU SP3000 Series Digital Sweeper`; it does not independently identify the SP30120 submodel or firmware revision. The operator and chassis identify the unit as SP30120. The family ID must not be used to infer the manual's SP30120A model.
- Each response ended with one LF (`0x0A`), with no CR, command echo, or extra ACK.
- One complete identity response may arrive across multiple low-level `read()` calls. A transport must accumulate through the verified terminator rather than treating one `read()` as one response.
- Identity queries completed in about 100 ms. Successful short state queries typically completed in about 50–100 ms. These observations inform an initial timeout design but are not completion-time guarantees for every state or firmware.
- One second of passive listening after the successful query set produced no late response or asynchronous data.

## Query matrix

|Query|Observed result|Wire shape and decision|
|---|---|---|
|`*IDN?`|Accepted; stable 5/5|ASCII text + LF; identifies only the SP3000 family|
|`RFSTAT?`|Accepted|`ON` or `OFF` + LF; the unit was already ON and was not changed|
|`OUTOHMSEL?`|Accepted|Decimal impedance value + LF|
|`CENS?`|Accepted|Two comma-separated scientific-notation values + LF|
|`STAS?`|Accepted|Two comma-separated scientific-notation values + LF; consistent with center/span|
|`CWFREQ?`|Accepted|One scientific-notation value + LF|
|`FREQOFFSET?`|Accepted|One scientific-notation value + LF|
|`SWET?`|Accepted|One scientific-notation value + LF|
|`SWET:MODE?`|Accepted|`LIN` or `LOG` + LF|
|`TRIM?`|Accepted|`CONT` or `SING` + LF; sweep execution, not trace streaming|
|`EXTT?`|Accepted|Returned `OFF` + LF in this run|
|`INPZ?`|Accepted|Decimal impedance value + LF|
|`POWEr?`|Not accepted|Returned undocumented `Error` + LF|
|`SWETAUTO?`|Not accepted|Returned undocumented `Error` + LF|
|`SWET:AVER?`|Not accepted|Returned undocumented `Error` + LF|
|`SWET:AVER:STATe?`|Not accepted|Returned undocumented `Error` + LF|
|`FUNC?`|Unconfirmed|No response within a bounded wait and no late bytes|
|`DETMODE?`|Unconfirmed|No response within a bounded wait and no late bytes|
|`AMPMEAS?` / `PHAMEAS?`|Unconfirmed|No response within a bounded wait and no late bytes|
|`OUTPRFORM:CONT?`|Unconfirmed|No response within two seconds and no late bytes|
|`OUTPRFORM:MODE?`|Unconfirmed|No response within a bounded wait and no late bytes|
|`OUTPRFORM:POINT?`|Unconfirmed|No response within a bounded wait and no late bytes|
|`OUTPRFORM:POINT:DATA?`|Unconfirmed|No response within a bounded wait and no late bytes|

The accepted core-state set was then read in three additional snapshots. Every field remained byte-for-byte stable. This shows that these queries did not alter the visible core state during this session; it does not establish equivalent behavior for every manual-listed query or firmware revision.

## M3 driver-path acceptance

The installable `wavebench-shengpu-sp3000a` 0.1.0 package passed one end-to-end read-only hardware acceptance run. After the target resource was opened through the WaveBench core serial transport, the plugin's `idn()` method confirmed the verified SP3000-family identity and `read_scalar_status()` successfully read and parsed every stable scalar field listed above.

This path sent only `*IDN?` and the fixed status-query allowlist. It did not call a transport write API or send trace, configuration, trigger, RF, save/recall, or Local commands. Descriptor import, entry-point discovery, and registry loading remain zero-I/O operations. This acceptance covers only the M3 query-only driver and scalar parser; it does not expand the M2 conclusions about trace transfer or local-state restoration.

## Safety decisions

- `OUTPRFORM:CONT?` did not respond. A later controlled `OUTPRFORM:CONT OFF` also returned neither `OK` nor another confirmation, so trace streaming still could not be proven off.
- Because the unit was already at `RFSTAT=ON` and this stage forbids changing RF, no acquisition-format write was attempted.
- Consequently, `OUTPRFORM?` was deliberately skipped. No trace framing, point count, units, or frequency axis received hardware acceptance.
- No speculative command aliases were tried and failed queries were not retried. A controlled `SYSTem:LOCal` closeout produced no documented `LOC`, so restoration of local state is also unproven.
- The exact undocumented literal `Error` must be treated as a device-private deterministic failure, not a value and not an automatic-retry condition.
- The accepted query set is eligible for an initial M3 query-only driver. Queries that timed out or returned `Error` must remain unsupported until the correct firmware commands are verified.

## Remaining M2 exit gates

Full M2 closure still requires:

1. operator confirmation that front-panel `Shift/Local` restores local control after RMT; serial `SYSTem:LOCal` currently has no `LOC` evidence;
2. identification and verification of the target firmware's actual trace-streaming, return-mode, and point-count queries;
3. one bounded `OUTPRFORM?` only after trace streaming can be proven off;
4. retaining the operator/chassis evidence for SP30120 and independently confirming installed options, without inferring SP30120A from the family-level IDN;
5. keeping M4 trace-format writes and parser validation separate from this stage.

Until those gates pass, the public status is “partially verified SP30120 RS-232 scalar read-only protocol,” not “accepted trace acquisition,” and the unit must not be relabeled SP30120A.

## Timeline boundary for later trace exploration

The statement that `OUTPRFORM?` was deliberately skipped accurately describes the initial M2 read-only session. Separate, later sessions were explicitly authorized to issue bounded trace queries and return-mode writes, but they did not produce an acceptable M4 conclusion:

- One baseline read returned only 739 numeric values without a confirmed LF termination boundary and with a substantial zero-valued tail. It is evidence of an incomplete or desynchronized frame only.
- Later reads repeatedly returned 1002 numeric values terminated by LF, shaped as 501 finite nonzero candidates followed by 501 zeros.
- Experiments labelled AMPT, PHASE, and ALL all had the same 501+501 shape. They therefore did not prove that return-mode writes took effect, and they could not distinguish a disabled phase measurement from invalid data or stale stream residue.
- Trace-shaped bytes were observed near writes intended to control continuous upload, return mode, or RF state instead of a recognizable acknowledgement, indicating possible mixing of control replies and asynchronous trace data in those sessions.

These observations remain private protocol evidence for M4. They do not overwrite the historical M2 record and do not accept a trace parser, point count, units, restoration behavior, or the `sweep_analyzer.trace` capability. M4 must re-establish a quiet session boundary with `CONT OFF`, then validate AMPT, PHASE, ALL, and at least two point counts against both expected token counts and LF termination.
