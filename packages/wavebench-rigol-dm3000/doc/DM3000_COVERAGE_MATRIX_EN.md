# DM3000 Programming-Manual Coverage Matrix

[中文](DM3000_COVERAGE_MATRIX.md)

This page maps DM3000 programming-manual domains to the WaveBench capabilities and SCPI surface
currently exposed by the external `wavebench-rigol-dm3000` plugin. The
[package metadata](../pyproject.toml) is authoritative for version, dependencies, and entry point;
the [production descriptor](../src/wavebench_rigol_dm3000/descriptor.py) for models, transport,
configuration fields, and capabilities; and the [driver](../src/wavebench_rigol_dm3000/driver.py)
for exact commands, parsing, and transaction behavior.

The [coverage milestones](DM3000_COVERAGE_MILESTONES_EN.md) record diagnostic probes, hardware
protocol acceptance, implementation order, and exit gates. That historical/development record does
not independently add a current capability. A command appearing in the manual or this matrix is not
public unless the production descriptor declares the corresponding capability.

## Scope

The audit source is DM3000 family programming manual `PGC01010-1110`. Its cover lists
DM3061/2/3/4 and DM3051/2/3/4 but does not identify DM3058 separately, so the manual is not by
itself proof of DM3058 compatibility. The local transcription is for internal audit only and lives
under the Git-ignored, wheel/sdist-excluded `doc/vendor-local/` directory.

This matrix reports current coverage by functional domain rather than counting transcription
headings or set/query variants. The external plugin is a configured TCPIP/PyVISA driver, not a
general DM3000 SCPI shell. The short aliases `dm3000` / `dm3058` still select the Core-bundled
fallback; its serial support is not transport coverage of this external package.

## Functional coverage

| Domain | Manual command surface | Current public coverage | Current boundary |
|---|---|---|---|
| Identity | `*IDN?` | `dmm.idn` | Returns the raw string; model, serial, and firmware are not exposed as structured fields. |
| Instrument reset | `*RST` | Not public | Changes measurement, trigger, calculation, and global state; denied by default. |
| Command-set selection | `CMDSET RIGOL/AGILENT/FULUKE`, `CMDSET?` | Not public | Changes the instrument-wide grammar. The plugin is fixed to the RIGOL set, and the manual also contains `FULUKE`/`FLUKE` ambiguity. |
| Current function | `:FUNCtion?` | `dmm.function_status` | Accepts only explicitly supported long/short symbols. Unknown responses raise `DataError`; `RATIO` is not in the current mapping. |
| Basic function selection | DCV, ACV, DCI, ACI, RES, FRES, FREQ, PERIOD, CONT, DIODE, CAP | `dmm.set_function` | Reads back `:FUNCtion?`; does not set range, resolution, trigger, or settling. |
| DC voltage ratio | `:FUNCtion:VOLTage:DC:RATIO`, `:MEASure:VOLTage:DC:RATIO?` | Not public | Requires two inputs and independent result semantics; it cannot be represented as an ordinary scalar mapping. |
| Eleven scalar readings | Per-function `:MEASure:<function>?` | `dmm.read` | Sends only the target query and does not select a function. Nonfinite values are rejected; a finite response is not measurement-accuracy evidence. |
| Automatic/manual measurement | `:MEASure AUTO|MANU`, `:MEASure?` | Not public | Changes continuous measurement. In this manual, `:MEASure?` reports completion rather than a reading. |
| Range | Per-function `:RANGe?` and `:MEASure:<function> <range>` | `dmm.measurement_profile` reads discrete `range_code`; `dmm.set_voltage_range` covers active DCV/ACV and codes `0..4` | A range write forces manual mode, but the device has no matching mode query. A failed transaction latches the instance even if range restoration succeeds. |
| Input impedance, AC filter, secondary frequency | DCV `:IMPedance`, ACV `:FILTer`, ACV/ACI `:FREQ:*` | The profile reads DCV impedance; `dmm.set_dcv_impedance` writes `10M/10G` | The setter changes neither function nor range; `10G` is allowed only for range codes `0..2`. AC filter/frequency fields are not public. |
| Display digits and measurement resolution | `:DIGit*`, `:RESolution:*` | Not public | Display digits are not acquisition resolution, and model/firmware semantics are insufficient for extrapolation from the manual. |
| Query-only system/interface state | beeper, language, format, brightness, option serial, DHCP, GPIB, RS-232 | `dmm.system_interface_status` | Redacted, all-or-nothing snapshot. It does not read MAC, IP, hostname, clock, raw IDN, or raw responses and sends no configuration writes. |
| Power-on/default and interface configuration | power-on/default, LAN/GPIB/RS-232 writes | Not public | May mutate persistent state or sever the current session; denied by default. |
| Trigger system | source, auto interval/hold, single count, external, VMC | `dmm.trigger_status` | Reads existing state only. It does not trigger, change the source, or drive VMC output. |
| Calculation and statistics | mode, count, min/max/average, dB/dBm reference | `dmm.calculation_status`, `dmm.calculation_statistics` | Statistics require explicit caller confirmation and rechecking the active mode. The driver never enables, clears, or triggers implicitly. NULL/dB/dBm/limit setters are not public. |
| Datalog | status, configure, run/stop, binary fetch | Not public | No reliable state or binary-format contract exists; start, stop, and configuration also mutate acquisition state. |
| Scan board and projects | `:SCAN:*` | Not public | Option-dependent and includes persistent project plus multi-channel run side effects. |
| Agilent/Fluke compatibility sets | compatible SCPI and short commands | Not public | Require instrument-wide command-set switching and are not free aliases for the RIGOL driver. |

## Directly used SCPI surface

The list below is the complete instrument-command surface that current external-plugin source may
send. It is not a communication log and does not claim separate hardware acceptance for every
command.

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

:TRIGger:SOURce?
:TRIGger:AUTO:INTerval?
:TRIGger:AUTO:HOLD?
:TRIGger:AUTO:HOLD:SENSitivity?
:TRIGger:SINGle?
:TRIGger:EXT?
:TRIGger:VMComplete:POLar?
:TRIGger:VMComplete:PULSewidth?

:CALCulate:FUNCtion?
:CALCulate:STATistic:COUNt?
:CALCulate:STATistic:MIN?
:CALCulate:STATistic:MAX?
:CALCulate:STATistic:AVERage?
:CALCulate:DB:REFerence?
:CALCulate:DBM:REFerence?

:SYSTem:BEEPer:STATe?
:SYSTem:LANGuage?
:SYSTem:FORMat:DECimal?
:SYSTem:FORMat:SEParate?
:SYSTem:DISPlay:BRIGht?
:SYSTem:SCANserial?
:SYSTem:LANserial?
:UTILity:INTerface:LAN:DHCP?
:UTILity:INTerface:GPIB:ADDRess?
:UTILity:INTerface:RS232:BAUD?
:UTILity:INTerface:RS232:PARity?
```

The implementation sends no `*RST`, `CMDSET`, resolution, trigger/calculation write, Datalog,
scan, interface, or error-queue command and has no generic raw-SCPI path. A complete
`dmm.set_function` transaction is one selection write plus one `:FUNCtion?` readback;
`dmm.read` sends one measurement query only.

## Measurement function mapping

| Public function | Function selection | Reading query | Unit |
|---|---|---|---|
| `dcv` / `vdc` | `:FUNCtion:VOLTage:DC` | `:MEASure:VOLTage:DC?` | V |
| `acv` / `vac` | `:FUNCtion:VOLTage:AC` | `:MEASure:VOLTage:AC?` | V |
| `dci` / `idc` | `:FUNCtion:CURRent:DC` | `:MEASure:CURRent:DC?` | A |
| `aci` / `iac` | `:FUNCtion:CURRent:AC` | `:MEASure:CURRent:AC?` | A |
| `res` / `ohm` / `2wr` | `:FUNCtion:RESistance` | `:MEASure:RESistance?` | ohm |
| `fres` / `4wr` | `:FUNCtion:FRESistance` | `:MEASure:FRESistance?` | ohm |
| `freq` | `:FUNCtion:FREQuency` | `:MEASure:FREQuency?` | Hz |
| `period` | `:FUNCtion:PERiod` | `:MEASure:PERiod?` | s |
| `continuity` / `cont` | `:FUNCtion:CONTinuity` | `:MEASure:CONTinuity?` | ohm |
| `diode` | `:FUNCtion:DIODe` | `:MEASure:DIODe?` | V |
| `cap` | `:FUNCtion:CAPacitance` | `:MEASure:CAPacitance?` | F |
| ratio | Not public | Not public | Undefined |

## Behavior and safety boundaries

- The descriptor rejects non-`pyvisa`, non-`TCPIP`, serial, ASRL, USB, and GPIB configurations
  before transport opening.
- `dmm.read` does not select a function implicitly; the caller must confirm or set the current mode.
- Configuration writes use readback and restoration. An ambiguous first write, failed readback, or
  unverifiable restoration latches further configuration writes for the current instance.
- Descriptor validation and finite-number parsing do not prove correct wiring, measurement accuracy,
  or compatibility with the entire DM3000 family.

## Related sources

- [Production descriptor](../src/wavebench_rigol_dm3000/descriptor.py)
- [Driver implementation](../src/wavebench_rigol_dm3000/driver.py)
- [Coverage milestones and hardware evidence](DM3000_COVERAGE_MILESTONES_EN.md)
