# DP800 Programming-Manual Coverage Matrix

[中文](DP800_COVERAGE_MATRIX.md)

This page maps DP800 programming-manual domains to the WaveBench capabilities and SCPI surface
currently exposed by the external `wavebench-rigol-dp800` plugin. The
[package metadata](../pyproject.toml) is authoritative for version, dependencies, and entry point;
the [production descriptor](../src/wavebench_rigol_dp800/descriptor.py) for models, channels,
configuration fields, and capabilities; and the [driver](../src/wavebench_rigol_dp800/driver.py)
for exact commands, parsing, and transaction behavior.

The [command-coverage development milestones](DP800_COVERAGE_MILESTONES_EN.md) record development
order, hardware acceptance, and exit gates. That historical/development record does not
independently add a current capability. A command in the manual or this matrix is not public unless
the production descriptor declares the corresponding capability.

## Scope

The audit source is RIGOL DP800 family programming manual `PGH03008-1110`. It spans multiple
models, A/non-A variants, channel counts, ranges, and options. Model parameters therefore are not
projected onto DP832A, and DP832A evidence is not projected onto the whole family. The local
transcription is for internal audit only and lives under the Git-ignored, wheel/sdist-excluded
`doc/vendor-local/` directory.

This matrix reports current coverage across the manual's 22 functional domains rather than using
set/query variants, abbreviations, or aliases as a completion denominator. The external plugin is a
narrow power-supply driver governed by safety policy, not a general DP800 SCPI shell.

## Functional coverage

| Domain | Manual command surface | Current public coverage | Current boundary |
|---|---|---|---|
| Identity and error queue | `*IDN?`, `:SYSTem:ERRor?`, `:SYSTem:VERSion?` | `power.idn`; configuration writes may read the error queue when configured | `errors()` consumes entries. Structured model/firmware and non-consuming health are not public. |
| IEEE 488.2 status, reset, trigger | `*CLS`, status registers, `*OPC?`, `*RST`, `*TRG`, `*TST?` | Nothing except `*IDN?` | Reset, trigger, and clearing status have global/output side effects and are denied by default. |
| Basic setpoints | `:APPLy` / `:APPLy?` | `power.status`; `power.set_voltage_current_limit` | Saves voltage/current, writes once, reads back, and restores on failure. Ambiguous results or unverifiable restoration latch configuration writes. |
| Live measurement | `:MEASure:ALL?` and scalar queries | `power.measurement`; `power.status` reuses the same snapshot | Uses one `:MEAS:ALL? CH<n>`. Scalar queries are not public, and measurement accuracy is not claimed. |
| Output state and CV/CC mode | `:OUTPut[:STATe]?`, `:OUTPut:CVCC?` / `:OUTPut:MODE?` | `power.status` | Unknown output/regulation enums fail closed and are not projected to unaccepted models. |
| Explicit output enable | `:OUTPut[:STATe] [CH<n>,]ON|OFF` | `power.output` | Directly affects the DUT. The driver writes once and reads back; on failure it forces OFF and never blindly retries ON. |
| OVP/OCP | state, threshold, trip, clear | `power.protection` reads and configures state/threshold/trip | Writes are ordered for safety and read back individually. Recovery never clears a newly observed trip. Clear commands are not public. |
| `SOURce` setpoint/protection aliases | level, step, triggered level, protection, range | No independent API; immediate setpoints and protection use `APPLy`/`OUTPut` | Step, triggered level, DP811 range, and protection clear are not public. Aliases are not counted twice. |
| Range, Sense, Track | `:OUTPut:RANGe/SENSe/TRACk` | Not public | Model/channel-dependent; Range changes limits, Sense requires remote wiring, and Track couples channels. |
| Timer and Delay | `:TIMEr:*`, `:OUTPut:TIMEr*`, `:DELAY:*` | Not public | May change real output over time or by condition. Current scalar snapshots cannot restore them, so start is denied. |
| Monitor | `:MONItor:*` | Not public | Conditions and actions may disable output or signal alarms and may require an option. |
| Trigger and `INITiate` | `:TRIGger:*`, `:INITiate`, `*TRG` | Not public | May change trigger levels, switch outputs, drive digital ports, or couple channels; denied by default. |
| Current-channel selection | `:INSTrument:NSELect/SELect` | Deliberately unused | Every current command carries `CH<n>`, avoiding hidden mutable current-channel state. |
| Recorder and Analyzer | `:RECorder:*`, `:ANALyzer:*` | Not public | Depend on options and file lifecycle; start/stop, file selection, and analysis mutate state. |
| Internal state, presets, external files | `:MEMory:*`, `:PRESet:*`, `:RECAll:*`, `:STORe:*`, `:MMEMory:*`, `*SAV/*RCL` | Not public | Save, overwrite, delete, recall, and load have persistent side effects and are denied by default. |
| Display and front panel | `:DISPlay:*`, brightness, contrast, lock/local/remote | Not public | Mutates global UI or impedes human takeover; ordinary measurement flows do not write front-panel state. |
| System diagnostics and status | self-test, SCPI version, `:STATus:QUEStionable:*` | Not public | Some event queries clear state; self-test conditions and latency have no public contract. |
| Communications and global setup | LAN, serial, GPIB, language, power-on, OTP, channel sync | Not public | Network writes may sever the session; other operations mutate persistent/global state and are denied by default. |
| License and option installation | `:LIC:SET` | Not public | Device-maintenance operation that mutates persistent state; denied by default. |

## Directly used SCPI surface

The commands below use normalized manual-style long names; the implementation uses compatible
short forms. This is neither a communication log nor a claim of separate accuracy or all-model
acceptance for every command.

```text
*IDN?
SYSTem:ERRor?

APPLy? CH<n>
MEASure:ALL[:DC]? CH<n>
OUTPut[:STATe]? CH<n>
OUTPut:MODE? CH<n>
OUTPut:OVP[:STATe]? CH<n>
OUTPut:OVP:VALue? CH<n>
OUTPut:OVP:QUES? CH<n>
OUTPut:OCP[:STATe]? CH<n>
OUTPut:OCP:VALue? CH<n>
OUTPut:OCP:QUES? CH<n>

APPLy CH<n>,<voltage>,<current>
OUTPut[:STATe] CH<n>,ON|OFF
OUTPut:OVP:VALue CH<n>,<voltage>
OUTPut:OVP[:STATe] CH<n>,ON|OFF
OUTPut:OCP:VALue CH<n>,<current>
OUTPut:OCP[:STATe] CH<n>,ON|OFF
```

`power.status` reads `APPLy?`, `MEASure:ALL?`, output state, and regulation mode in sequence.
`power.protection` reads six protection fields. If an intermediate query fails, the driver returns
no partial public model.

## Behavior and safety boundaries

- Core owns voltage/current safety limits, OVP/OCP relationships, pre-enable checks, run plans, and
  experiment-level restoration. Those rules are not DP800 SCPI coverage.
- Current commands always carry an explicit channel and do not mutate hidden current-channel state.
- A failed multi-write transaction attempts to restore the original snapshot. An ambiguous first
  write, changed trip, or unverifiable restoration latches further configuration writes.
- Settle delay, finite-number parsing, and descriptor validation do not prove output stability,
  correct wiring, measurement accuracy, or whole-family compatibility.

## Related sources

- [Production descriptor](../src/wavebench_rigol_dp800/descriptor.py)
- [Driver implementation](../src/wavebench_rigol_dp800/driver.py)
- [Development milestones and hardware evidence](DP800_COVERAGE_MILESTONES_EN.md)
