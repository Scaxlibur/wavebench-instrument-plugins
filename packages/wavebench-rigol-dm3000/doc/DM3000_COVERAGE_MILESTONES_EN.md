# DM3000 Feature-Coverage Milestones

[中文](DM3000_COVERAGE_MILESTONES.md)

This document turns the DM3000 programming-manual surface into implementable and auditable
milestones. It also records controlled LAN protocol acceptance performed on one DM3058 on
2026-07-26. It is the execution plan for the
[coverage matrix](DM3000_COVERAGE_MATRIX_EN.md), not a general raw-SCPI allowlist.

The manual cover lists DM3061/2/3/4 and DM3051/2/3/4 but does not name DM3058 separately.
Hardware results below therefore prove acceptance by the tested DM3058 firmware only and are not
projected onto the whole family. No real address, serial number, or exact measured value is
retained.

## Acceptance rules

Protocol acceptance is separate from measurement-accuracy acceptance:

- **Query accepted:** a complete response arrives within the bounded timeout and parses against a
  defined type or enum. A measured value must also be finite, never `NaN` or infinity.
- **Response only, semantics unresolved:** a response exists, but its value or field meaning is
  implausible or insufficiently defined and cannot be promoted to public support.
- **Controlled write accepted:** read the original value, write a distinct safe target, read back
  the target, restore the original in a `finally` path, and read back the restored value. Writing
  the same value back does not count.
- **No response:** the query times out or does not return a complete response in a fresh session.
  This does not prove every related model lacks the command, but the tested DM3058 cannot be
  claimed as accepted.
- **Skipped:** a prerequisite is absent or the physical risk is unacceptable, such as no scan
  board or external wiring that makes current/resistance/continuity/diode/capacitance modes unsafe.

Every failed query was followed by session closure. The probe sent neither `*CLS` nor error-queue
queries. An ambiguous first write would have latched and stopped all later writes; no such failure
occurred, and every state change that was attempted was restored.

The run proves command, parsing, and restoration contracts only. It does not prove range,
impedance, frequency, or calibration accuracy. Final state was verified as DCV, original DCV/ACV
ranges, 10 MOhm input, AUTO trigger, and calculation disabled.

## Hardware protocol-acceptance summary

### Accepted queries

Only the plugin's four existing capabilities are formal APIs. Other commands below were controlled
diagnostic probes used to decide which milestones are feasible.

| Domain | Accepted command surface | Note |
|---|---|---|
| Identity and command set | `*IDN?`, `CMDSET?` | IDN was redacted; command set reported RIGOL. No command-set switch was sent |
| Current function and completion | `:FUNCtion?`, `:MEASure?` | Both responses parsed |
| DCV | `:MEASure:VOLTage:DC?`, `:MEASure:VOLTage:DC:RANGe?`, `:MEASure:VOLTage:DC:IMPedance?` | Reading was finite; range and impedance parsed |
| ACV | `:MEASure:VOLTage:AC?`, `:MEASure:VOLTage:AC:RANGe?` | Verified only after explicit ACV selection; reading was finite |
| Frequency | `:MEASure:FREQuency?`, `:MEASure:FREQuency:RANGe?` | Verified in frequency mode; reading was finite |
| Period | `:MEASure:PERiod?`, `:MEASure:PERiod:RANGe?` | Verified in period mode; reading was finite |
| System status | `:SYSTem:BEEPer:STATe?`, `:SYSTem:LANGuage?`, `:SYSTem:FORMat:DECimal?`, `:SYSTem:FORMat:SEParate?`, `:SYSTem:DISPlay:BRIGht?` | Queries parsed; format writes remain denied |
| Options and identity | `:SYSTem:SCANserial?`, `:SYSTem:MACaddr?`, `:SYSTem:LANserial?` | Scan and interface modules reported absent; MAC was format-checked only and not retained |
| Interface status | LAN `DHCP?`, `IP?`, `MASK?`, `GATEway?`, `DNS?`; GPIB `ADDRess?`; RS-232 `BAUD?`, diagnostic `PARity?` | Query-only; no connection setting was changed. `PARity?` tests the intended spelling behind a manual copy error |
| Trigger status | `:TRIGger:SOURce?`, `AUTO:INTerval?`, `AUTO:HOLD?`, `AUTO:HOLD:SENSitivity?`, `SINGle?`, `EXT?`, `VMComplete:POLar?`, `VMComplete:PULSewidth?` | `ms`-suffixed responses were unit-aware parsed |
| Calculation status | `:CALCulate:FUNCtion?`, `STATistic:COUNt?`, `DB:REFerence?`, `DBM:REFerence?` | Count may use scientific notation and should be parsed as a finite nonnegative number |
| Enabled statistics | `:CALCulate:STATistic:AVERage?`, `MIN?`, `MAX?` | Queried only while the corresponding calculation was controlled-enabled; finite responses |

`:SYSTem:OPENtimes?` returned an integer, but it was implausibly large. It remains “response only,
semantics unresolved” and must not be published as a trusted power-cycle count.

### Controlled writes and restoration accepted

| Feature | Write surface | Result |
|---|---|---|
| Voltage-input function selection | `:FUNCtion:VOLTage:AC`, `:FUNCtion:FREQuency`, `:FUNCtion:PERiod`, restore `:FUNCtion:VOLTage:DC` | Target readback, finite corresponding reading, and restoration passed |
| DCV input impedance | `:MEASure:VOLTage:DC:IMPedance 10M/10G` | Distinct-value switch, readback, and restore passed; 10 GOhm used only on a low DCV range |
| DCV range | `:MEASure:VOLTage:DC <range>` | Safe adjacent-range change, finite reading, and restoration passed |
| ACV range | `:MEASure:VOLTage:AC <range>` | Safe adjacent-range change, finite reading, and restoration passed |
| Beeper state | `:SYSTem:BEEPer:STATe ON/OFF` | Toggle and restore passed; no audible beeper-test command was sent |
| Display brightness | `:SYSTem:DISPlay:BRIGht <value>` | One-step change, readback, and restore passed |
| Trigger parameters | `AUTO:HOLD`, `AUTO:HOLD:SENSitivity`, `SINGle`, `EXT`, `VMComplete:PULSewidth` | Distinct-value write, readback, and restore passed; no manual trigger or trigger-source change |
| Calculation mode | `:CALCulate:FUNCtion AVERAGE/MIN/MAX/TOTAL`, restore `NONE` | Mode readback, finite statistic response, and restore passed |

`:TRIGger:AUTO:INTerval 200` was ignored; readback remained `400ms`. Restoration remained healthy,
so the query is usable but the setter is **not accepted** on this DM3058 and must not enter a
supported write API.

### No response or not eligible

| Domain | Current result |
|---|---|
| Display digits and resolution | DCV/ACV/FREQ/PERIOD `:DIGit?` and DCV/ACV `:RESolution:*?` did not respond |
| ACV extensions | `:FILTer?`, `:FREQuency?`, and `:FREQuency:STATe?` did not respond; standalone FREQ mode does work |
| Clock and contrast | `:SYSTem:CLOCK:STATe?`, `DATE?`, `TIME?`, and `:SYSTem:DISPlaycontrast?` did not respond |
| LAN text fields | `:UTILity:INTerface:LAN:HOST?` and `DOMain?` did not respond |
| Calculation extensions | `:CALCulate:NULL:OFFSet?`, `:CALCulate:LIMit:LOWer?`, and `UPPer?` did not respond |
| Datalog | `:DATAlog?` and every `:DATAlog:CONFigure:*?` query attempted in this run did not respond |
| Scan | `:SCAN:CURRent:CYCLE?` and `PROJname?` did not respond; the instrument also reported no scan board |
| High-risk maintenance | `*RST`, `CMDSET <set>`, interface writes, defaults/power-on configuration, and clock writes remain denied |
| Wiring-dependent modes | DCI, ACI, 2/4-wire resistance, continuity, diode, capacitance, and ratio were not selected; first require removal of external voltage or a dedicated safe fixture |

## Coverage milestones

### M0: command inventory and evidence boundary — complete

- Chinese and English matrices cover common, function, measurement, resolution, system,
  interface, trigger, calculation, datalog, scan, and compatibility command sets.
- Vendor material stays under `doc/vendor-local/` and is explicitly excluded from wheels and
  sdists.
- DM3058 hardware evidence remains separate from manual model coverage.

### M1: harden the four current capabilities — partially complete

Public capabilities remain `dmm.idn`, `dmm.read`, `dmm.function_status`, and `dmm.set_function`.

- IDN, current function, finite DCV/ACV/FREQ/PERIOD responses, and voltage-input restoration are
  hardware-confirmed.
- Pending: explicitly reject `NaN` and infinity in `dmm.read`.
- Pending: optional preflight requiring requested and current function to match.
- DCI, ACI, resistance, continuity, diode, and capacitance remain offline mappings only.

### M2: query-only measurement profile — next implementation target

Proposed `dmm.measurement_profile` should query only fields applicable to the current function:

- Common: `:FUNCtion?`, `:MEASure?`;
- DCV: reading, range, input impedance;
- ACV: reading and range;
- FREQ: reading and input-voltage range;
- PERIOD: reading and input-voltage range.

Unsupported digits/resolution/filter fields must be explicitly unavailable, never fabricated.

### M3: controlled voltage-input configuration — implementable

Expose function selection, DCV/ACV range, and DCV impedance separately rather than through one
generic integer setter. Read before write, use per-function range tables, read back after write,
restore on failure, and latch configuration writes if restoration fails. Never modify trigger,
calculation, display, format, or interface state implicitly.

### M4: query-only trigger and existing statistics — implementable

- `dmm.trigger_status` can cover the eight accepted trigger queries.
- `dmm.calculation_status` can cover current mode, count, and dB/dBm references.
- `dmm.calculation_statistics` may read min/max/average only when the caller confirms that the
  matching calculation is already active; it must not enable, clear, or trigger implicitly.
- Controlled setters require a separate review; the AUTO interval setter is disabled.

### M5: system and interface query-only status — conditionally implementable

A redacted query-only snapshot is feasible, but default artifacts must not retain MAC, IP,
hostname, or domain. Writes to networking, GPIB, RS-232, formatting, language, clock, defaults, or
power-on configuration remain prohibited.

### M6: other electrical modes — waiting for a safe fixture

DCI, ACI, 2/4-wire resistance, continuity, diode, capacitance, and ratio require explicit terminal,
source-disconnect, fuse, range, and load checks. A mere response cannot bypass physical safety.

### M7: datalog and scan — blocked

- Datalog queries do not respond on the current DM3058, so binary packet decoding cannot start.
- The scan board is absent and SCAN queries also do not respond.
- No capability is published without a supported device, format/endianness evidence, size bounds,
  and stop/restoration contracts.

## Release gate

A new capability is hardware-accepted only when it has a public typed model, driver contract,
descriptor declaration, exact FakeTransport command tests, Service/CLI preflight, real response
evidence, and restoration evidence for every write. Diagnostic probes do not themselves count as
public plugin coverage.
