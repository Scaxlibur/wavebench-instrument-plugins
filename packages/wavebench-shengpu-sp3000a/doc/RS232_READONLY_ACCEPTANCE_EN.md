# SP3000A RS-232 Read-Only Protocol Acceptance

[中文](RS232_READONLY_ACCEPTANCE.md)

## Decision

The first M2 read-only probe was performed against one powered-on SP3000-series unit. At `9600 baud / 8N1 / no flow control / LF`, the RS-232 link reliably supports identity and a subset of core state queries. Several manual-listed candidate queries either timed out or returned the undocumented literal `Error` on the target firmware. The result is therefore **partial acceptance of scalar read-only protocol behavior; no trace query was authorized, and M2 is not fully closed**.

No configuration, trigger, output, reset, save/recall, or remote-to-local command was sent. RF, sweep, display, markers, detection, and stored slots were not changed. The real serial resource and laboratory-only logs are excluded from this public record.

## Session and framing

- Passive listening was quiet after opening the confirmed target resource and before the first query.
- `*IDN?` returned the same 38-byte ASCII line in 5/5 repetitions.
- The identity response states only `SHENGPU SP3000 Series Digital Sweeper`; it does not independently identify the SP30120A submodel or firmware revision.
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

## Safety decisions

- Because `OUTPRFORM:CONT?` did not respond, trace streaming could not be proven off.
- Because the unit was already at `RFSTAT=ON` and this stage forbids changing RF, no acquisition-format write was attempted.
- Consequently, `OUTPRFORM?` was deliberately skipped. No trace framing, point count, units, or frequency axis received hardware acceptance.
- No speculative command aliases were tried, failed queries were not retried, and `SYSTem:LOCal` was not used to change session state automatically.
- The exact undocumented literal `Error` must be treated as a device-private deterministic failure, not a value and not an automatic-retry condition.
- The accepted query set is eligible for an initial M3 query-only driver. Queries that timed out or returned `Error` must remain unsupported until the correct firmware commands are verified.

## Remaining M2 exit gates

Full M2 closure still requires:

1. operator confirmation that front-panel `Shift/Local` restores local control after RMT;
2. identification and verification of the target firmware's actual trace-streaming, return-mode, and point-count queries;
3. one bounded `OUTPRFORM?` only after trace streaming can be proven off;
4. independent evidence for the exact submodel and installed options instead of inferring SP30120A from the family-level IDN;
5. keeping M4 trace-format writes and parser validation separate from this stage.

Until those gates pass, the public status is “partially verified RS-232 scalar read-only protocol,” not “accepted SP30120A driver or trace acquisition.”
