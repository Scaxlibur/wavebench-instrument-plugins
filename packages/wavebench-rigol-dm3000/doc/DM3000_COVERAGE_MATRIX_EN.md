# DM3000 Programming-Manual Coverage Matrix

[中文](DM3000_COVERAGE_MATRIX.md)

See the [DM3000 feature-coverage milestones](DM3000_COVERAGE_MILESTONES_EN.md) for the exact
hardware protocol-acceptance commands, accepted/failed evidence, and staged implementation plan.
Diagnostic probes select future work; they do not mean the plugin already exposes those
capabilities.

## Purpose, scope, and counting method

This matrix compares the locally stored RIGOL DM3000 Chinese programming manual with the public
capabilities, actual SCPI, offline tests, and recorded DM3058 LAN evidence of the external
`wavebench-rigol-dm3000` plugin. It distinguishes commands documented by the vendor from behavior
actually exposed and accepted by the plugin. A manual entry, Python method, or acceptance of a
neighboring mode does not by itself establish complete feature coverage.

The audit input is DM3000 programming manual `PGC01010-1110`. Its current 4,017-line Markdown
transcription is stored in this package's Git-ignored `doc/vendor-local/` directory, which is
excluded from commits, wheels, and sdists. The cover lists DM3061/2/3/4 and DM3051/2/3/4, but does
not name the tested DM3058 separately. The manual is therefore treated as DM3000-family protocol
material, while DM3058 compatibility is accepted only where current code, observed firmware
responses, or recorded hardware evidence supports it. The complete manual is not projected onto
DM3058 by assumption.

Chapter 2 groups the RIGOL commands into ten domains: common, function, measurement, resolution,
system, utility/interface, trigger, calculation, datalog, and scan. Chapter 3 adds Agilent- and
Fluke-compatible command sets. The transcription contains missing headings, broken command names,
and apparent copy errors, including an RS-232 parity section that repeats the baud command. This
matrix therefore reports auditable functional domains and public capabilities rather than a
misleading completion percentage based on heading counts.

The current external plugin is version `0.3.0` and declares seven capabilities: `dmm.idn`,
`dmm.read`, `dmm.function_status`, `dmm.set_function`, query-only
`dmm.measurement_profile`, `dmm.set_voltage_range`, and `dmm.set_dcv_impedance`. It is a narrow TCPIP/PyVISA LAN driver
for a configured resource, not a general DM3000 SCPI shell. It exposes no error-queue, reset,
trigger, datalog, scan, or interface-configuration path. The short aliases `dm3000` and
`dm3058` remain bound to the bundled fallback; its serial support is not transport coverage of
this external package.

Coverage labels:

- **External hardware accepted**: current external code, offline implementation, and controlled DM3058 LAN evidence exist.
- **Implemented / offline tested**: code and focused FakeTransport tests exist, without external hardware acceptance for the detail.
- **Implemented / partially offline tested**: a code path exists, but tests make exact assertions for only part of the command family.
- **Not covered**: the manual documents the command, but the external plugin has no public capability or method for it.
- **Denied by default**: the command changes the command grammar, resets the instrument, disrupts connectivity, persists state, or starts a complex acquisition and should not be exposed by ordinary workflows.
- **Source uncertain**: the transcription or manual is visibly ambiguous and cannot support implementation without stronger material and hardware evidence.

## Coverage matrix

| Domain | Manual command surface | Current public coverage | Evidence | Main gap and safety boundary | Recommendation |
|---|---|---|---|---|---|
| Identity | `*IDN?` | `dmm.idn` returns the raw response | **External hardware accepted** in migration acceptance and post-reinstall smoke; exact single-query offline test | Model, serial, and firmware are not parsed into structured fields; real values are not retained in public docs | Keep the narrow query; define a redacted artifact before structured identity |
| Instrument reset | `*RST` | Not public | **Denied by default** | Restores factory defaults across measurement, trigger, calculation, and related global state | Keep outside ordinary DMM workflows; consider only a maintenance command with confirmation |
| Command-set selection | `CMDSET RIGOL/AGILENT/FULUKE`, `CMDSET?` | Not public | **Denied by default / source uncertain** | Changes the instrument-wide command grammar; the manual also uses both `FULUKE` and `FLUKE` spellings | Pin the plugin to the RIGOL set; do not bypass it with raw SCPI |
| Current function | `:FUNCtion?` | `dmm.function_status`; normalizes long symbols and observed short DM3058 symbols such as `RES`, `2WR`, `4WR`, `FREQ`, `PERI`, `CONT`, and `CAP` | **External hardware accepted**; selected short-symbol parser cases have offline tests | The parser does not accept the manual's `RATIO`; unknown responses raise `DataError` | Require observed responses and per-item parser tests before adding modes |
| Basic function selection | `:FUNCtion:VOLTage:DC/AC`, `CURRent:DC/AC`, `RESistance`, `FRESistance`, `FREQuency`, `PERiod`, `CONTinuity`, `DIODe`, `CAPacitance` | `dmm.set_function` supports those eleven modes and reads back `:FUNCtion?` | **Offline and DM3058 open-probe accepted:** all eleven modes completed target readback, finite response, and per-run DCV restoration | Does not set range, resolution, trigger, or settling; open-probe evidence does not prove wiring, unit semantics, or accuracy | M1 complete; accuracy and dedicated fixtures remain separate acceptance |
| DC voltage ratio | `:FUNCtion:VOLTage:DC:RATIO`, `:MEASure:VOLTage:DC:RATIO?` | Not public; `RATIO` status is not accepted either | **Not covered** | Requires two inputs and has no ordinary physical unit; it needs explicit input and result semantics | Design a separate ratio capability first |
| Eleven scalar readings | `:MEASure:VOLTage:DC/AC?`, `CURRent:DC/AC?`, `RESistance?`, `FRESistance?`, `FREQuency?`, `PERiod?`, `CONTinuity?`, `DIODe?`, `CAPacitance?` | `dmm.read` returns shared `DmmReading(function, value, unit, raw)` | **Offline and DM3058 open-probe accepted:** all eleven queries returned finite values; DCV also has 20/20 repeated-read evidence | `read(function=...)` sends the query only and does not select a function. A finite response is not accuracy evidence; the parser rejects `NaN`/`inf` | Keep the preselected-function requirement; validate accuracy separately |
| Automatic/manual measurement | `:MEASure AUTO|MANU`, `:MEASure?` | Not public | **Not covered** | Changes continuous-measurement behavior; in this manual `MEASure?` reports completion rather than a reading | Implement only after an explicit acquisition-state model exists |
| Range and measurement mode | Per-function `:MEASure:<function> <range>`, `:RANGe?`, and `:MEASure AUTO|MANU` without a matching mode query | Profile returns the discrete code with autorange unavailable; setter covers active DCV/ACV and codes `0..4` only | **M3 external hardware accepted:** the tested DM3058 completed DCV and ACV `0 -> 1 -> 0` write, readback, and restoration cycles. The manual defines code `0` as the smallest range, not autorange | A range write also forces manual mode, but that state cannot be queried; failed transactions therefore latch writes even after range restoration | Protocol and restoration are accepted; validate measurement accuracy separately |
| Input impedance, AC filter, secondary frequency | DCV `:IMPedance`, ACV `:FILTer`, ACV/ACI `:FREQ:*` | Profile reads DCV impedance; setter controls `10M/10G`, with `10G` limited to range codes `0..2` | **M3 external hardware accepted:** the tested DM3058 completed a `10M -> 10G -> 10M` cycle; range code `3` at `10G` was rejected before writing. AC filter/frequency queries did not respond | The setter does not switch function or range; ambiguous writes and failed readback/restoration latch the instance | Protocol, constraint, and final safe state are accepted; omit nonresponding fields |
| Display digits | Per-function `:DIGit?` and `:DIGit INC|DEC|5|6|7` | Not public | **Not covered; no response on tested DM3058** for DCV/ACV/FREQ/PERIOD queries | Display digits are not acquisition resolution and must not share one capability | Leave unimplemented without different-firmware evidence and a concrete need |
| Measurement resolution | Eight `:RESolution:*` families | Not public | **Not covered; no response on tested DM3058** for DCV/ACV queries | Discrete values are model-dependent despite the manual's 0/1/2 table | Do not project the manual onto DM3058; wait for stronger model/firmware evidence |
| System diagnostic queries | `:SYSTem:SCANSerial?`, `MACAddr?`, `LANSerial?`, `OPENtimes?` | Not public | **API not covered; queries partly accepted:** option/interface identifiers parsed and MAC was format-checked; `OPENtimes?` semantics were implausible and not accepted | MAC is sensitive identity and must not enter default artifacts | Add a redacted query-only identity extension only for a concrete gating need |
| Beeper, language, clock, display, formatting | `:SYSTem:BEEPer*`, `LANGuage`, `CLOCk:*`, `DISPlay:*`, `FORMat:*` | Not public | **API not covered:** beeper/language/format/brightness queries passed; beeper and brightness restorative writes passed; clock and contrast queries did not respond | Decimal/separator changes may break parsing; global front-panel writes do not belong in normal measurement APIs | M5 may expose query-only status; keep format/language/clock writes denied |
| Power-on and system defaults | `:SYSTem:CONFigure:POWeron`, `:SYSTem:CONFigure:DEFault` | Not public | **Denied by default** | Changes persistent or instrument-wide state | Maintenance workflows only |
| LAN/GPIB/RS-232 configuration | `:UTILity:INTerface:LAN:*`, `GPIB:ADDRess`, `RS232:BAUD/PARity` | Not public | **Writes denied; query probes partly accepted:** LAN DHCP/IP/mask/gateway/DNS, GPIB address, and RS-232 baud/parity were readable; hostname/domain did not respond | Interface writes can sever the active session; the manual parity section repeats baud commands. This package accepts TCPIP/PyVISA only | M5 may expose redacted query-only status; never write connection settings in normal measurement flows |
| Trigger system | `:TRIGger:SOURce`, auto interval/hold, single count/triggered, external, VMC polarity/pulse width | Not public | **API not covered; query probes accepted:** eight status fields parsed; distinct hold/sensitivity/single/ext/VMC pulse-width writes and restores passed. AUTO interval setter was ignored and failed acceptance | Changes timing or drives VMC; no trigger action or source change was performed | **M4:** query-only profile first; review setters individually and disable AUTO interval setter |
| Math and statistics | `:CALCulate:FUNCtion`, min/max/average/count | Not public | **API not covered; controlled probes accepted:** AVERAGE/MIN/MAX/TOTAL, corresponding finite query, and restoration to NONE passed | A probe does not imply a public setter; statistics depend on the active mode and series | **M4:** read existing status/statistics without implicitly enabling, clearing, or triggering |
| NULL, dB, dBm, limit | `:CALCulate:NULL:OFFSet`, `DB[:REFerence]`, `DBM[:REFerence]`, `LIMit:*` | Not public | **Not covered** | Setters change the meaning of later readings; references and units depend on the active function | Expose only as an independent, snapshot-and-restore calculation profile |
| Datalog status and configuration | `:DATAlog?`, `CONFigure:*`, `RUN`, `STOP` | Not public | **Writes denied; current DM3058 queries did not respond** | Status/configuration queries attempted in this run returned no complete response; start/stop/configuration also have significant state | **M7 blocked:** wait for a supported device and reliable status before designing bounded controlled capture |
| Datalog binary retrieval | `:DATAlog:FETCHdata <packet>` | Not public | **Not covered / source uncertain** | Each packet contains 512 32-bit values; the manual calls for a vendor driver/DLL and configuration-dependent valid-count extraction; it is not an ordinary ASCII query | Do not implement until byte order, value format, and DLL-free decoding are established |
| Scan board and projects | `:SCAN:*` task/project/run/fetch/save/load/delete/cardID | Not public | **Denied; tested device explicitly lacks the scan board and queries did not respond** | Project writes are persistent and run/stop controls multi-channel acquisition | **M7 blocked:** wait for equipped hardware, then gate a separate capability through option identity |
| Agilent compatibility set | Compatible `CALCulate`, `CONFigure`, `SENSe`, `TRIGger`, `DATA`, `MEMory`, and related SCPI | Not public | **Denied by default** | Requires instrument-wide `CMDSET AGILENT`; its grammar cannot be mixed into the RIGOL driver | Do not count as free aliases; a future implementation should be a separate driver/profile |
| Fluke compatibility set | `VDC`, `VAC`, `ADC`, `AAC`, `OHMS`, `MEAS?`, and related short commands | Not public | **Denied by default** | Also requires command-set switching, with different short-command semantics and responses | Do not mix into the current capabilities |

## Directly used SCPI surface

The list below is the complete instrument-command surface that current external-plugin source can
send, shown with the implementation's spelling. It is not a communication log and does not claim
hardware acceptance for every command.

```text
*IDN?
:FUNCtion?

:MEASure:VOLTage:DC?
:MEASure:VOLTage:AC?
:MEASure:CURRent:DC?
:MEASure:CURRent:AC?
:MEASure:RESistance?
:MEASure:FRESistance?
:MEASure:FREQuency?
:MEASure:PERiod?
:MEASure:CONTinuity?
:MEASure:DIODe?
:MEASure:CAPacitance?

:MEASure:VOLTage:DC:RANGe?
:MEASure:VOLTage:AC:RANGe?
:MEASure:CURRent:DC:RANGe?
:MEASure:CURRent:AC:RANGe?
:MEASure:RESistance:RANGe?
:MEASure:FRESistance:RANGe?
:MEASure:FREQuency:RANGe?
:MEASure:PERiod:RANGe?
:MEASure:CAPacitance:RANGe?
:MEASure:VOLTage:DC:IMPedance?
:MEASure:VOLTage:DC <0..4>
:MEASure:VOLTage:AC <0..4>
:MEASure:VOLTage:DC:IMPedance <10M|10G>

:FUNCtion:VOLTage:DC
:FUNCtion:VOLTage:AC
:FUNCtion:CURRent:DC
:FUNCtion:CURRent:AC
:FUNCtion:RESistance
:FUNCtion:FRESistance
:FUNCtion:FREQuency
:FUNCtion:PERiod
:FUNCtion:CONTinuity
:FUNCtion:DIODe
:FUNCtion:CAPacitance
```

The implementation sends no `*RST`, `CMDSET`, resolution, trigger, calculate, datalog, scan,
interface, or error-queue command and has no generic raw-SCPI path. A complete
`dmm.set_function` transaction is one function-selection write followed by one `:FUNCtion?`
readback. A `dmm.read` operation is one measurement query only.

## Per-measurement evidence

| Public function | Function selection | Reading query | Unit | Offline evidence | External hardware evidence |
|---|---|---|---|---|---|
| `dcv` / `vdc` | `:FUNCtion:VOLTage:DC` | `:MEASure:VOLTage:DC?` | V | Exact query/unit test; selector mapping exists | **20/20 finite reads passed**; included in reversible cross-voltage switching |
| `acv` / `vac` | `:FUNCtion:VOLTage:AC` | `:MEASure:VOLTage:AC?` | V | Exact query/unit and exact ACV selector test | Reversible selection, finite reading, range switch, and restoration passed; not accuracy acceptance |
| `dci` / `idc` | `:FUNCtion:CURRent:DC` | `:MEASure:CURRent:DC?` | A | Exact query/unit/selector tests | Open-probe accepted; not accuracy acceptance |
| `aci` / `iac` | `:FUNCtion:CURRent:AC` | `:MEASure:CURRent:AC?` | A | Exact query/unit/selector tests | Open-probe accepted; not accuracy acceptance |
| `res` / `ohm` / `2wr` | `:FUNCtion:RESistance` | `:MEASure:RESistance?` | ohm | Exact query/unit/selector and status-parser tests | Open-probe accepted; not accuracy acceptance |
| `fres` / `4wr` | `:FUNCtion:FRESistance` | `:MEASure:FRESistance?` | ohm | Exact query/unit/selector and status-parser tests | Open-probe accepted; not accuracy acceptance |
| `freq` | `:FUNCtion:FREQuency` | `:MEASure:FREQuency?` | Hz | Exact query/unit and short-status tests | Reversible selection, finite reading, and input-voltage range query passed; not accuracy acceptance |
| `period` | `:FUNCtion:PERiod` | `:MEASure:PERiod?` | s | Exact query/unit and short-status tests | Reversible selection, finite reading, and input-voltage range query passed; not accuracy acceptance |
| `continuity` / `cont` | `:FUNCtion:CONTinuity` | `:MEASure:CONTinuity?` | ohm | Exact query/unit/selector and status-parser tests | Open-probe accepted; not accuracy acceptance |
| `diode` | `:FUNCtion:DIODe` | `:MEASure:DIODe?` | V | Exact query/unit/selector tests | Open-probe accepted; not accuracy acceptance |
| `cap` | `:FUNCtion:CAPacitance` | `:MEASure:CAPacitance?` | F | Exact query/unit/selector and status-parser tests | Open-probe accepted; not accuracy acceptance |
| ratio | Not public | Not public | Undefined | None | None |

## WaveBench safeguards outside manual-command coverage

- The descriptor rejects non-`pyvisa`, non-`TCPIP`, serial, ASRL, USB, and GPIB configurations
  before transport opening. This is a plugin boundary, not implementation of a DM3000 SCPI command.
- Capability preflight, session lifecycle, pre-read settling, run-plan artifacts, and numeric
  `expect` evaluation belong to WaveBench core and do not count as manual-command coverage.
- Descriptor capability validation proves only that declared methods exist and are callable. It
  does not prove SCPI semantics, instrument responses, correct wiring, or measurement accuracy.
- A `set_function` readback proves that the instrument reports the requested mode. It does not
  prove that terminals, range, resolution, filter, trigger, and the applied signal are suitable for
  the next measurement.

## Recommended roadmap

See the [feature-coverage milestones](DM3000_COVERAGE_MILESTONES_EN.md) for exact commands and
release gates. The overall order is:

1. **M1: harden the original four capabilities — complete.** All eleven selectors have exact
   parameterized tests, nonfinite readings are rejected, and `dmm.read` does not select a function.
   Optional target/current-mode preflight remains outside this milestone.
2. **M2: query-only measurement profile — complete.** Covers the current function, accepted
   discrete range code, and DCV impedance. Measurement mode and CONT/DIODE inapplicable fields stay
   unavailable.
3. **M3: controlled voltage-input configuration — complete.** DCV/ACV
   range and DCV impedance have function gates, parameter limits, readback, restoration, and latching.
4. **P2: read existing statistics and trigger state.** Do not implicitly enable, clear, trigger, or
   reset instrument state.
5. **P3: datalog.** First resolve binary format, byte order, valid counts, size limits, timeout,
   stop/finally behavior, and artifacts. The scan board should be a separate option-gated capability.
6. **Out of default scope: command-set switching, reset/default, network/serial configuration, and
   persistent scan-project writes.** These require permissions and confirmation distinct from
   ordinary measurement workflows.

## Evidence boundary

- **Manual:** the local `vendor-local` transcription is for internal audit only. This document does
  not reproduce the complete manual or include it in a release. Transcription ambiguity is not
  treated as reliable protocol fact.
- **Implementation:** external `driver.py`, `descriptor.py`, FakeTransport tests, and WaveBench's
  shared DMM service/run-plan contracts.
- **External hardware:** the recorded 2026-07-24 managed-install/routing/DCV work plus controlled
  query and restorative-write protocol acceptance on 2026-07-26. The latter covered finite
  ACV/FREQ/PERIOD responses, DCV/ACV ranges, DCV impedance, trigger queries, existing statistics,
  and selected system/interface queries. The milestone document contains the exact list. No real
  address, serial number, or measured value was retained.
- **Not accepted:** measurement accuracy, DCI/ACI/resistance/continuity/diode/capacitance,
  digits/resolution, datalog, scan, and compatibility sets remain unaccepted. Diagnostic probes do
  not themselves create public capabilities.

An item may be promoted to **External hardware accepted** only when current external code, focused
offline tests, real command acceptance/readback, and required restoration evidence all exist.
