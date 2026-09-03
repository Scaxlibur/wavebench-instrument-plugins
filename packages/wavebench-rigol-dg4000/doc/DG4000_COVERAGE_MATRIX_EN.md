# DG4000 Programming-Manual Coverage Matrix

[中文](DG4000_COVERAGE_MATRIX.md)

This page maps DG4000 programming-manual domains to the WaveBench capabilities and SCPI surface
currently exposed by the external `wavebench-rigol-dg4000` plugin. The
[package metadata](../pyproject.toml) is authoritative for the distribution version and entry
points, the [production descriptor](../src/wavebench_rigol_dg4000/descriptor.py) for models,
capabilities, and operation directions, and the [driver](../src/wavebench_rigol_dg4000/driver.py)
for exact commands and transaction behavior.

The [coverage milestones](DG4000_COVERAGE_MILESTONES_EN.md) record development order, exit gates,
and hardware evidence. Machine-readable evidence is under [`conformance/`](../conformance/).
Those records support traceability and do not independently add a current capability. A command
listed in this matrix is not public unless the production descriptor declares the corresponding
capability.

## Scope

The audit source is DG4000 family programming manual `PGB04008-1110`. It uses DG4162 for some
parameter examples and states that ranges vary with model, load, and frequency, so those numeric
limits are not projected onto DG4202. The local transcription is for internal audit only and lives
under the Git-ignored, wheel/sdist-excluded `doc/vendor-local/` directory.

This matrix groups the manual into auditable functional domains instead of treating set/query
variants, abbreviations, or transcription headings as a completion denominator. `rigol.dg4202`
retains the legacy capabilities; `rigol.dg4202-v2` adds only the restricted Sweep capabilities
declared by its descriptor. Neither is a general DG4000 SCPI shell.

## Current public write entry points

The DG descriptor sets `v1_route_migration_enabled=false`. V2 capabilities are called only through
explicit V2 entry points and do not take over legacy V1 routes; Sweep is public only through
`rigol.dg4202-v2`.

| Capability | Current entry point and boundary |
|---|---|
| `source.basic_configure_v2` | CLI `source basic-configure-v2`; run `source.basic_configure_v2`. Output must be OFF, frequency mode FIX, and the V2 snapshot fresh. Each request may change one Basic field. |
| `source.basic_live_configure_v2` | CLI `source basic-live-configure-v2`; run `source.basic_live_configure_v2`. Output must be ON, frequency mode FIX, and each request may change either frequency or Vpp. Output cycling is forbidden. |
| `source.output_v2` | CLI `source output-v2`; run `source.output_enable_v2` / `source.output_disable_v2`. Core applies V2 preflight and final-state readback independently to ON and OFF. |
| `source.sweep_configure_v2` | `rigol.dg4202-v2` only; run `source.sweep_configure_v2`. Output must be OFF, the V2 snapshot fresh, and Burst/Modulation OFF. Configuration has independent readback. |
| `source.sweep_fire_v2` | `rigol.dg4202-v2` only; run `source.sweep_fire_v2`. It requires a same-session configured Sweep, selected-channel output ON, and manual trigger. It is never blindly retried. |
| Legacy V1 routes | `source.set-*`, `source.output`, discrete frequency response, `arb-load`, basic restore, and their existing artifacts retain V1 contracts. |

The production descriptors expose no volatile-ARB, Burst, Coupling, Noise Overlay, or Sync write
capability beyond these entries. See the [coverage milestones](DG4000_COVERAGE_MILESTONES_EN.md)
for the accepted hardware scope and unpassed failure gates.

## Functional coverage

| Domain | Manual command surface | Current public coverage | Current boundary |
|---|---|---|---|
| Identity and error queue | `*IDN?`, `:SYSTem:ERRor?`, `:SYSTem:VERSion?` | `source.idn`, `source.errors` | `errors()` reads and consumes the queue. SCPI version, status registers, and non-consuming health are not public. |
| IEEE 488.2 save, reset, and trigger | `*RCL`, `*RST`, `*SAV`, `*TRG` | Not public | Save/recall mutates nonvolatile state, reset changes the whole instrument, and `*TRG` may start Sweep/Burst output; these are denied by default. |
| CH1/CH2 basic status | output, function, frequency, voltage, offset, phase, Sweep state, apply, square duty | `source.status`; `source.snapshot_v2` returns typed Basic, output state, and before/after anchors for both channels | V2 Output does not duplicate load/polarity from `source.channel_profile`; snapshots do not expand automatic restoration. |
| Fixed frequency | `[:SOURce<n>]:FREQuency[:FIXed]` | `source.set_frequency` | The transaction snapshots, selects FIX, reads back each step, and uses off-first recovery. Ambiguous results latch writes. |
| Basic functions and square duty | `FUNCtion[:SHAPe]`, square duty, `APPLy:*` | `source.set_function`, `source.set_square_duty_cycle` | Ramp symmetry, pulse edges, noise parameters, and composite `APPLy` writes are not public. |
| Amplitude, units, offset, phase | `VOLTage`, `UNIT`, `OFFSet`, `HIGH`, `LOW`, `PHASe` | `source.set_amplitude_vpp`; status reads offset/phase | Public writes use VPP. There is no independent offset/phase/high/low setter; actual limits still depend on model, frequency, and load. |
| Output enable | `OUTPut[<n>][:STATe]` | `source.output` | The caller must request the transition explicitly. Arbitrary upload never enables output implicitly, and the driver does not blindly retry ON. |
| Load, polarity, Noise Overlay, Sync | `OUTPut:LOAD/POLarity/NOISe/SYNC` | `source.channel_profile`; typed Noise Overlay/Sync facets in `source.snapshot_v2` | Query-only. Basic restore excludes these fields, and no setter is public. |
| Dual-channel coupling | `COUPling:*` | `CHANNEL_SET` facet in `source.snapshot_v2` | Query-only. The descriptor declares no configure direction and no complete target/restore transaction exists. |
| Sweep and trigger | `SWEep:*`, frequency window, `*TRG` | `source.sweep_profile`; Sweep facet in `source.snapshot_v2`; configure/manual-fire through `rigol.dg4202-v2` | V2 does not restore a complete Sweep. Raw immediate trigger remains denied, and opt-in behavior does not migrate onto V1 routes. |
| Burst, Pulse, Marker, Harmonic | `BURSt:*`, `PULSe:*`, `MARKer:*`, `HARMonic:*` | Query-only facets in `source.snapshot_v2`; Harmonic is `PARTIAL` | Per-order Harmonic, Marker writes, and configure/trigger APIs are not public. Missing fields are not inferred from adjacent evidence. |
| Modulation | `MOD:*` | `source.channel_profile` and `source.snapshot_v2` return state/type query-only | No mode-specific parameters or setters are public. State/type queries are not modulation-control capability. |
| DAC14 arbitrary upload | `TRACe:DATA:DAC VOLATILE,<binary-block>` | `source.arbitrary_upload` | Accepts only validated little-endian `DG4000DacBlock`; target must be OFF, FIX, and Sweep OFF. Upload overwrites volatile USER data and cannot restore it. |
| Arbitrary diagnostic queries | `FUNC?`, `FUNC:USER?`, candidate ARB/DATA queries | `source.arbitrary_probe` | Accepts question-mark candidates only and records the error queue. This is troubleshooting, not stable arbitrary-wave capability. |
| Arbitrary editing, float, DAC16 | `TRACe:DATA`, `DAC16`, `POINts`, `VALue`, `LOAD?` | Not public | Formats, byte order, memory lifecycle, and readback have no public contract. |
| Frequency counter | `COUNter:*` | `source.counter_profile`, `source.counter_configure_v2`, `source.counter_enable_v2`, `source.counter_measure_v2` | Configuration writes one field at a time; enable/disable is separate; measurement requires enabled state. Auto, gate, HF, sensitivity, display, and clear are not public. |
| External PA | `PA:*` | Not public | It can create higher-power output and persist state, so it is denied by default. |
| Display and screenshot | `DISPlay:*`, `HCOPy:SDUMp:DATA?` | Not public | Display writes change global front-panel state; screenshot has no public transfer/format contract. |
| Internal state slots | `MEMory:*`, `*SAV/*RCL` | Not public | They may overwrite, delete, lock, or recall user state and are denied by default. |
| External filesystem | `MMEMory:*` | Not public | Paths, deletion, overwrite, and load have persistent side effects and are denied by default. |
| Communications and global setup | LAN, USB class, language, key lock, beeper, power-on, reference oscillator, channel copy | Not public | Network writes may sever the session; the remaining operations mutate global state and are denied by default. |
| Preset, restart, shutdown | `SYSTem:PRESet/RESTART/SHUTDOWN` | Not public | They interrupt experiments, lose the session, or change global configuration and are denied by default. |

## Directly used SCPI surface

The commands below use normalized manual-style long names; the implementation uses compatible
short forms. This is neither a communication log nor a claim of separate hardware acceptance for
every command.

```text
*IDN?
SYSTem:ERRor?
OUTPut<n>?
SOURce<n>:FUNCtion[:SHAPe]?
SOURce<n>:FREQuency[:FIXed]?
SOURce<n>:VOLTage?  SOURce<n>:VOLTage:UNIT?  SOURce<n>:VOLTage:OFFSet?
SOURce<n>:PHASe?  SOURce<n>:SWEep:STATe?  SOURce<n>:APPLy?
SOURce<n>:FUNCtion:SQUare:DCYCle?
OUTPut<n>:LOAD?  OUTPut<n>:POLarity?
OUTPut<n>:NOISe:STATe?  OUTPut<n>:NOISe:SCALe?
OUTPut<n>:SYNC:STATe?  OUTPut<n>:SYNC:POLarity?
COUPling[:STATe]?  COUPling:CHannel:BASE?
COUPling:AMPLitude:DEViation?  COUPling:FREQuency:DEViation?
COUPling:PHASe:DEViation?
SOURce<n>:BURSt:STATe?  SOURce<n>:MOD:STATe?  SOURce<n>:MOD:TYPe?
SOURce<n>:MARKer:STATe?  SOURce<n>:PULSe:HOLD?
SOURce<n>:FREQuency:STARt?  SOURce<n>:FREQuency:STOP?
SOURce<n>:FREQuency:CENTer?  SOURce<n>:FREQuency:SPAN?
SOURce<n>:SWEep:SPACing?  SOURce<n>:SWEep:STEP?  SOURce<n>:SWEep:TIME?
SOURce<n>:SWEep:HTIMe:STARt?  SOURce<n>:SWEep:HTIMe:STOP?
SOURce<n>:SWEep:RTIMe?  SOURce<n>:SWEep:TRIGger:SOURce?
SOURce<n>:SWEep:TRIGger:SLOPe?  SOURce<n>:SWEep:TRIGger:TRIGOut?
SOURce<n>:MARKer:FREQuency?
COUNter[:STATe]?  COUNter:MEASure?  COUNter:COUPing?  COUNter:IMPedance?
COUNter:ATTenuation?  COUNter:GATEtime?  COUNter:HF?  COUNter:LEVel?
COUNter:SENSitive?  COUNter:STATIstics:STATe?  COUNter:STATIstics:DISPlay?

OUTPut<n> ON|OFF
SOURce<n>:FREQuency[:FIXed] <frequency>
SOURce<n>:FUNCtion[:SHAPe] <basic-wave>
SOURce<n>:VOLTage:UNIT VPP  SOURce<n>:VOLTage <vpp>
SOURce<n>:FUNCtion:SQUare:DCYCle <percent>
TRACe:DATA:DAC VOLATILE,<IEEE-488.2-binary-block>
SOURce<n>:VOLTage:OFFSet <voltage>  SOURce<n>:FUNCtion[:SHAPe] USER
```

The implementation also uses `:SOUR<n>:FREQ:MODE?` / `... FIX` to prevent fixed-frequency writes
from being interpreted in Sweep mode; that DG4202 compatibility path is not in the selected
manual's frequency index. Arbitrary upload also writes `*CLS`, so it clears prior error state and
is not read-only diagnostics.

## Behavior and safety boundaries

- Core loads CSV/NPY, rejects nonfinite values, normalizes samples, and encodes DAC14. The plugin
  receives `DG4000DacBlock`.
- Basic-state transactions restore only output, function, frequency, frequency mode, amplitude
  unit/value, offset, and square duty. Phase, load, modulation, complete Sweep state, and overwritten
  volatile USER data are outside restoration.
- `source.channel_profile`, `source.sweep_profile`, and `source.counter_profile` are all-or-nothing,
  query-only contexts. They neither enable features implicitly nor expand automatic restoration.
- Descriptor validation proves capability-to-method mapping, not vendor-command semantics, hardware
  compatibility, or measurement accuracy.

## Related sources

- [Production descriptor](../src/wavebench_rigol_dg4000/descriptor.py)
- [Driver implementation](../src/wavebench_rigol_dg4000/driver.py)
- [Coverage milestones and acceptance boundaries](DG4000_COVERAGE_MILESTONES_EN.md)
- [Machine-readable conformance](../conformance/)
