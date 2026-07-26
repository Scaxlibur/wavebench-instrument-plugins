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

The current external plugin is version `0.1.0` and declares four capabilities only: `dmm.idn`,
`dmm.read`, `dmm.function_status`, and `dmm.set_function`. It is a narrow TCPIP/PyVISA LAN driver
for a configured resource, not a general DM3000 SCPI shell. It exposes no error-queue, reset,
range, trigger, datalog, scan, or interface-configuration path. The short aliases `dm3000` and
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
| Basic function selection | `:FUNCtion:VOLTage:DC/AC`, `CURRent:DC/AC`, `RESistance`, `FRESistance`, `FREQuency`, `PERiod`, `CONTinuity`, `DIODe`, `CAPacitance` | `dmm.set_function` supports those eleven modes and reads back `:FUNCtion?` | **External hardware accepted** for DCV↔ACV; controlled 2026-07-26 probes also proved reversible DCV→FREQ/PERIOD→DCV transitions with finite readings. Other mappings are **partially offline tested** | Does not set range, resolution, trigger, or settling; current/resistance/continuity/diode/capacitance still lack a safe hardware matrix | **P1:** add exact parameterized tests for all selectors; hardware expansion must restore every tested mode |
| DC voltage ratio | `:FUNCtion:VOLTage:DC:RATIO`, `:MEASure:VOLTage:DC:RATIO?` | Not public; `RATIO` status is not accepted either | **Not covered** | Requires two inputs and has no ordinary physical unit; it needs explicit input and result semantics | Design a separate ratio capability first |
| Eleven scalar readings | `:MEASure:VOLTage:DC/AC?`, `CURRent:DC/AC?`, `RESistance?`, `FRESistance?`, `FREQuency?`, `PERiod?`, `CONTinuity?`, `DIODe?`, `CAPacitance?` | `dmm.read` returns shared `DmmReading(function, value, unit, raw)` | **DCV external hardware accepted** with 20/20 finite readings; 2026-07-26 also confirmed finite ACV, FREQ, and PERIOD responses in their selected modes; all eleven queries/unit mappings have parameterized offline tests | `read(function=...)` sends the query only. Current, resistance, continuity, diode, and capacitance remain unaccepted on hardware. The parser also does not explicitly reject `NaN`/`inf` | Document the preselected-function requirement; **P1:** reject nonfinite values and define mode-consistency policy |
| Automatic/manual measurement | `:MEASure AUTO|MANU`, `:MEASure?` | Not public | **Not covered** | Changes continuous-measurement behavior; in this manual `MEASure?` reports completion rather than a reading | Implement only after an explicit acquisition-state model exists |
| Range and autorange | Per-function `:MEASure:<function> <range>` and `:RANGe?` | Not public | **API not covered; controlled probes accepted:** safe distinct DCV/ACV range writes, readback, finite readings, and restoration passed; FREQ/PERIOD range queries passed | Writing a range selects manual mode; numbers and limits differ by function, and one probe cannot define a generic API | **M2/M3:** query-only current profile first; setters need per-function tables, readback, restoration, and failure latching |
| Input impedance, AC filter, secondary frequency | DCV `:IMPedance`, ACV `:FILTer`, ACV/ACI `:FREQ:*` | Not public | **API not covered:** distinct DCV 10 MOhm/10 GOhm switch and restore passed; ACV filter/frequency queries did not respond in this run | Impedance/filter affect results; display/hide mutates front-panel state; ACI naming is inconsistent | Expose DCV impedance query in M2; consider an independent restorative setter in M3 |
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

The implementation sends no `*RST`, `CMDSET`, range, resolution, trigger, calculate, datalog,
scan, interface, or error-queue command and has no generic raw-SCPI path. A complete
`dmm.set_function` transaction is one function-selection write followed by one `:FUNCtion?`
readback. A `dmm.read` operation is one measurement query only.

## Per-measurement evidence

| Public function | Function selection | Reading query | Unit | Offline evidence | External hardware evidence |
|---|---|---|---|---|---|
| `dcv` / `vdc` | `:FUNCtion:VOLTage:DC` | `:MEASure:VOLTage:DC?` | V | Exact query/unit test; selector mapping exists | **20/20 finite reads passed**; included in reversible cross-voltage switching |
| `acv` / `vac` | `:FUNCtion:VOLTage:AC` | `:MEASure:VOLTage:AC?` | V | Exact query/unit and exact ACV selector test | Reversible selection, finite reading, range switch, and restoration passed; not accuracy acceptance |
| `dci` / `idc` | `:FUNCtion:CURRent:DC` | `:MEASure:CURRent:DC?` | A | Exact query/unit test; selector mapping exists | None |
| `aci` / `iac` | `:FUNCtion:CURRent:AC` | `:MEASure:CURRent:AC?` | A | Exact query/unit test; selector mapping exists | None |
| `res` / `ohm` / `2wr` | `:FUNCtion:RESistance` | `:MEASure:RESistance?` | ohm | Exact query/unit test; selected long/short status tests | None |
| `fres` / `4wr` | `:FUNCtion:FRESistance` | `:MEASure:FRESistance?` | ohm | Exact query/unit and short-status tests | None |
| `freq` | `:FUNCtion:FREQuency` | `:MEASure:FREQuency?` | Hz | Exact query/unit and short-status tests | Reversible selection, finite reading, and input-voltage range query passed; not accuracy acceptance |
| `period` | `:FUNCtion:PERiod` | `:MEASure:PERiod?` | s | Exact query/unit and short-status tests | Reversible selection, finite reading, and input-voltage range query passed; not accuracy acceptance |
| `continuity` / `cont` | `:FUNCtion:CONTinuity` | `:MEASure:CONTinuity?` | ohm | Exact query/unit and short-status tests | None |
| `diode` | `:FUNCtion:DIODe` | `:MEASure:DIODe?` | V | Exact query/unit test; selector mapping exists | None |
| `cap` | `:FUNCtion:CAPacitance` | `:MEASure:CAPacitance?` | F | Exact query/unit and short-status tests | None |
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

1. **P1: harden the existing four capabilities.** Add exact parameterized selector tests for all
   eleven modes, reject nonfinite readings, document that `dmm.read` does not select a function,
   and consider an optional target/current-mode consistency preflight.
2. **P1: add a query-only current-measurement profile.** Begin with function, range, and resolution,
   then add function-specific impedance/filter fields. Unknown or inapplicable fields must be
   explicitly unavailable.
3. **P2: controlled range and resolution.** Each setter needs function gating, a mode-specific
   parameter table, write readback, clear failure semantics, and restoration. A generic integer
   range API must not hide function differences.
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
