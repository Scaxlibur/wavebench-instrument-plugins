# DG4000 Programming-Manual Coverage Matrix

[中文](DG4000_COVERAGE_MATRIX.md)

See the [DG4000 coverage milestones](DG4000_COVERAGE_MILESTONES_EN.md) for implementation order,
transaction rules, and hardware exit gates. Version `0.7.0` preserves M0-M6 and adds a pure-query
`source.snapshot_v2` adapter. The M4/M5 CH1/CH2 gates, global counter-OFF M6 gate, and current
OFF/SIN/FIX Source V2 read gate have passed. Controlled writes in M7-M12 remain pending. Listing a
command in this matrix does not make it implemented.

## Purpose, scope, and counting method

This matrix compares the locally stored DG4000 Chinese programming manual with the external
`wavebench-rigol-dg4000` plugin, the bundled `dg4202` fallback, and recorded DG4202 evidence. It
separates manual availability, current public behavior, and evidence level. Manual examples for
DG4162, historical acceptance of the bundled driver, and the existence of a Python method are not
treated as acceptance of the current external plugin.

The audit input is the DG4000 Chinese programming manual marked firmware `00.01.12` and document
`PGB04008-1110`. Its 12,236-line Markdown transcription is in this plugin's `doc/vendor-local/`
directory. That directory is Git-ignored, excluded from wheels/sdists, and is not committed with
this document. The manual uses DG4162 for several parameter-range examples and explicitly warns
that ranges depend on model, load, and frequency. No DG4162 numeric limit is therefore projected
onto DG4202.

The manual's command-system list yields twelve domains in this matrix: ten named vendor
subsystems (`COUNter`, `COUPling`, `DISPlay`, `MEMory`, `MMEMory`, `OUTPut`, `PA`, `SOURce`,
`SYSTem`, `TRACe`), the separately listed `HCOPy:SDUMp:DATA?`, and IEEE 488.2 common commands.
The manual transcription's layout headings are not a completion denominator: set/query forms,
optional keywords, short forms, and transcription defects such as missing brackets and broken
headings make a percentage misleading. The matrix therefore reports auditable functional domains
and public-capability evidence rather than a falsely precise percentage.

The external plugin declares fourteen WaveBench capabilities. It is a controlled implementation
for basic DG4202 dual-channel output, read-only channel/sweep context, global counter context, and a
narrow arbitrary-wave upload path, not a general DG4000 SCPI shell and not a claim to every DG4000
model, firmware, or accessory feature.

Coverage labels:

- **External hardware accepted**: current external-plugin code, FakeTransport tests, and controlled DG4202 evidence exist.
- **Implemented / offline tested**: current code and exact offline command tests exist, without an external-plugin hardware conclusion for that item.
- **Historical hardware evidence, not migrated acceptance**: bundled-driver evidence exists but has not been repeated for the external plugin.
- **Diagnostic probe**: explicit query-only candidate probing that may consume the error queue; it is not a stable feature path.
- **Not covered**: no corresponding public external-plugin, bundled-fallback, or SourceService API exists.
- **Denied by default**: the manual command exists but network, storage, output, or global-state risk prevents exposure.

## Coverage matrix

| Domain | Manual command surface | Current public coverage | Evidence | Main gap and safety boundary | Recommendation |
|---|---|---|---|---|---|
| Identity and error queue | `*IDN?`, `:SYSTem:ERRor?`, `:SYSTem:VERSion?` | `source.idn`, `source.errors`; writes may check the error queue | **External hardware accepted** for sanitized identity and M1/M2/M4 error boundaries on DG4202 `00.01.14`; exact SCPI has offline tests | `errors()` reads and consumes the queue; no public SCPI-version, status-register, or non-consuming health API | Keep error reads explicit; define consumption semantics before adding health APIs |
| IEEE 488.2 save, reset, and trigger | `*RCL`, `*RST`, `*SAV`, `*TRG` | Not public | **Denied by default** | Save/recall overwrites nonvolatile state, reset mutates the instrument globally, and `*TRG` starts sweep/burst output | Consider only with a separate controlled transaction, snapshot, and human confirmation |
| CH1/CH2 basic status | `OUTPut?`, `SOURce:FUNCtion?`, `FREQuency?`, `VOLTage?` / `UNIT?` / `OFFSet?`, `PHASe?`, `SWEep:STATe?`, `APPLy?`, square duty | `source.status` retains the V1 result; `source.snapshot_v2` returns typed Basic, output-enabled, and before/after anchors for both channels, deriving frequency mode from documented `SWEep:STATe?` | **External hardware accepted**: V1 strict profile used 24 queries and zero writes; `0.7.0` completed 40 pure queries in the current OFF/SIN/FIX state with consistent anchors and healthy session state | Source V2 Output does not duplicate load/polarity already available from `source.channel_profile`; automatic restoration is unchanged | Keep V1 write routing unchanged; require pure-query, budget, and consistency contracts for new fields |
| Fixed frequency | `[:SOURce<n>]:FREQuency[:FIXed]`; sweep center/span/start/stop are in the same family | `source.set_frequency` is a transaction with snapshot, FIX selection, per-step readback, off-first recovery, and ambiguous-write latching | **External hardware accepted**: FIX write/readback and fresh-session restore passed on DG4202 `00.01.14` CH1/CH2 | `FREQ:MODE` is a DG4202 compatibility path not listed in this manual's frequency index; the M5 sweep profile is query-only and does not set these fields | Keep the explicit FIX-mode safety behavior; any sweep write needs an independent transaction |
| Basic functions and square duty | `FUNCtion[:SHAPe]`, `FUNCtion:SQUare:DCYCle`, plus `APPLy:SINusoid/SQUare/RAMP/PULSe/NOISe` | `source.set_function` for SIN/SQU/RAMP/PULS/NOIS/DC; `source.set_square_duty_cycle` | **External hardware accepted** for temporary SQU/37% duty, ON-to-OFF, and fresh-session SIN restore on CH1/CH2; other functions remain offline-only | No ramp symmetry, pulse width/edges, noise parameters, composite apply writes, or complete function-profile restoration | Define complete, readable, restorable profiles per function before further setters |
| Amplitude, units, offset, phase | `VOLTage`, `UNIT`, `OFFSet`, `HIGH`, `LOW`, `PHASe` | `source.set_amplitude_vpp` writes `UNIT VPP` plus amplitude; status reads offset/phase; arbitrary upload writes offset internally | **External hardware accepted** for the M2 CH1/CH2 0.8 Vpp transaction/restore and M4 CH1 2 Vpp plus CH2 1 Vpp analog loops; no public offset setter | No public offset/phase/high/low setter; core VPP limits do not replace model/load/frequency limits; DBM/VRMS are not public | Keep a VPP-first API; couple any additional units or level controls to load, limits, and restoration |
| Output enable | `OUTPut[<n>][:STATe] ON|OFF` | `source.output`; arbitrary upload does not enable output unless explicitly requested | **External hardware accepted** for explicit M2 ON-to-OFF and restore on CH1/CH2; M4 adds triangle loops on both channels | It directly affects the DUT; no implicit enable or retry | Keep it separate and require higher-level workflows to record the requested output state |
| Output load, polarity, noise, sync | `OUTPut:IMPedance/LOAD`, `POLarity`, `NOISe:*`, `SYNC:*` | `source.channel_profile` returns load, polarity, noise state/scale, and sync state/polarity read-only | **External hardware accepted**: M3 completed 45 queries and zero text/binary writes on DG4202 `00.01.14` CH1/CH2 with strict complete profiles | These fields are context for diagnostics and safety only; basic restore does not restore them and no setters are public | Keep read-only; any future writes require VPP coupling, complete snapshots, and restoration |
| Dual-channel coupling | `COUPling:AMPL/FREQuency/PHASe`, base channel, state | Not public | **Not covered** | One-channel changes can affect the other channel; the current single-channel snapshot cannot restore this safely | **P2:** design atomic dual-channel snapshot, restoration, and lockout first |
| Sweep and manual/external trigger | `SWEep:*`, frequency start/stop/center/span, `*TRG` | `source.sweep_profile` retains complete V1 readback; `source.snapshot_v2` reuses that strict profile as a typed Sweep facet when frequency mode is Sweep; no setter/trigger | **M5 external hardware accepted** for sweep-OFF/ON staging; the V2 active branch has exact offline tests, while the current FIX hardware snapshot correctly returns `inactive_by_anchor` | Restore still excludes complete Sweep, the V2 active branch lacks fresh hardware evidence, and `*TRG`/immediate trigger remain denied | Controlled writes still require a complete snapshot, per-field readback, external measurement, off-first restoration, and non-retryable trigger semantics |
| Burst, pulse, marker, harmonic | `BURSt:*`, `PULSe:*`, `MARKer:*`, `HARMonic:*` | `source.snapshot_v2` can return a complete Pulse facet, Burst OFF or a complete enabled facet, and a `PARTIAL` Harmonic facet with enabled/configured order/maximum order/preset; per-order amplitude/phase, Marker writes, and all configuration APIs remain private | **Pulse externally accepted; remaining active branches offline-tested**: CH1/CH2 completed a 52-query V2 snapshot and complete Pulse facets at output OFF, PULSE, and 1 Vpp; Burst OFF returned on hardware, while Burst ON/Harmonic active branches retain exact FakeTransport tests only | Harmonic does not claim components; Burst ON/Harmonic active states lack external V2 evidence; configuration and trigger paths lack complete restoration | Keep read-only; stage active hardware states through a separate controlled transaction, never a raw-SCPI bypass |
| Modulation | `MOD:AM/FM/PM/ASK/FSK/PSK/BPSK/QPSK/3FSK/4FSK/OSK/PWM:*` | `source.channel_profile` returns only modulation state/type; there are no mode-specific profiles or setters | **Partial read-only context hardware accepted**: M3 returned OFF/AM on CH1/CH2; parameter and write surfaces remain uncovered | State/type queries are not modulation capability; external sources, rates, polarity, and phase interact | **P3:** split capabilities by mode and do not bypass restoration with raw SCPI |
| Arbitrary upload: DAC14 | `TRACe:DATA:DAC VOLATILE,<binary-block>` or decimal DAC values | `source.arbitrary_upload` accepts only structurally and sample-validated little-endian `DG4000DacBlock`; the target must already be OFF, FIX, and sweep OFF; post-binary fields are read back, and failure latches while reporting volatile USER data as irreversible | **M4 external hardware accepted**: CH1/CH2 both completed output-off upload, readback, error-queue, analog frequency/Vpp/shape loop, and restoration | No public decimal/float upload, DAC16, or arbitrary editing/readback; upload overwrites volatile waveform memory and selects USER | Keep the current narrow protocol; establish lifecycle, readback, and restoration evidence separately before adding formats |
| Arbitrary diagnostic queries | Plugin candidates include `FUNC?`, `FUNC:USER?`, and several `SOURce:*ARB*` / `SOURce:*DATA*` queries | `source.arbitrary_probe` permits only question-mark candidates and records errors after each | **Diagnostic probe**; FakeTransport-covered | The manual places waveform data under `TRACe:DATA`, not `SOURce:DATA`; several candidates may properly return `-113`. Since `errors()` consumes the queue, this is not non-invasive health readout | Keep it an explicit troubleshooting tool; do not promote candidate acceptance/rejection to feature coverage |
| Arbitrary editing, float, DAC16 | `TRACe:DATA`, `DAC16`, `POINts`, `VALue`, `LOAD?`, interpolate | Not public | **Not covered** | Formats, memory lengths, automatic USER selection, and local-edit rules differ; DAC16 has fixed chunking conditions | **P2:** establish RAM/DDR lifecycle, byte order, and readback semantics first |
| Frequency counter | `COUNter:*` input setup, gate, statistics, results | `source.counter_profile` reads counter state, coupling, impedance, attenuation, gate, HF, level, sensitivity, statistics state/display all-or-nothing and queries the five-field measurement only while ON; no setter/auto/clear | **M6 external hardware accepted (OFF boundary)**: three rounds on DG4202 `00.01.14`, 39 queries and zero text/binary writes; counter/statistics stayed OFF, display stayed DIGITAL, and `measurement=None`; ON-tuple parsing is offline-only | 50-ohm/1-megaohm setup and counter enable affect cabling safety; statistics clear is destructive; no counter-ON hardware result exists | Keep read-only. If ON evidence is needed, use a separate controlled staging/restoration session and safe signal fixture without widening the capability |
| External PA | `PA:*` enable, gain, offset, polarity, save | Not public | **Denied by default** | It can create higher-power output and `PA:SAVE` persists device state | Keep out of the base DG4202 capability; require independent authorization and human safety checks |
| Display and screenshot | `DISPlay:*`, `HCOPy:SDUMp:DATA?` | Not public | **Not covered** | Brightness/saver write global front-panel state; screenshot needs binary-transfer and format acceptance | **P3:** only add a read-only screenshot if it has clear diagnostic value |
| Internal state slots | `MEMory:STATe:DELete/LOCK/VALid?`, IEEE `*SAV/*RCL` | Not public | **Denied by default** | They can overwrite, delete, lock, or recall user state and are not equivalent to temporary WaveBench restoration | Keep host-side artifacts/restoration logs; do not write instrument slots |
| External USB filesystem | `MMEMory:CATalog/CDIR/COPY/DEL/LOAD/MDIR/RDIR/STORe` | Not public | **Not covered** | The manual requires external storage; paths, deletion, overwrite, and `.RAF/.RSF` loading have persistent side effects | Keep out by default; require path sandboxing, file permission, and double confirmation for deletion |
| System communications and global setup | `SYSTem:COMMunicate:LAN:*`, USB class, language, key lock, beeper, power-on, reference oscillator, channel copy | Not public | **Denied by default** | LAN/IP/DHCP changes can sever the current session; USB/clock/power-on/language/channel copy change global behavior | Consider only safe identity/version reads; never write network configuration from ordinary workflows |
| Restart, shutdown, preset | `SYSTem:PRESet/RESTART/SHUTDOWN` | Not public | **Denied by default** | Interrupts experiments, loses the session, or resets global configuration | Maintenance-only, outside the production WaveBench driver |

## Directly used SCPI surface

The following is normalized to manual-style long names; code uses compatible short forms such as
`SOUR`, `OUTP`, and `VOLT`. It is neither a communication log nor a claim that every command has
external-plugin hardware acceptance.

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

Two deliberate exceptions need separate treatment:

- The implementation uses `:SOUR<n>:FREQ:MODE?` / `... FIX` to prevent a fixed-frequency write
  from being interpreted as a sweep parameter. This DG4202 compatibility path is not in the
  selected manual's frequency command list, so code presence is not manual coverage.
- Arbitrary upload writes `*CLS` before uploading to clear/check current upload errors. `*CLS` is
  not among the five IEEE 488.2 commands indexed by this manual and clears the queue, so it is not
  read-only diagnostics.

## WaveBench safeguards outside manual coverage

- Core loads CSV/NPY, rejects NaN/inf, normalizes samples, and encodes DAC14; the plugin receives
  `DG4000DacBlock` and does not duplicate parsing or safety policy.
- `max_source_vpp`, explicit `output_on`, run-plan safety, artifacts, and optional source-state
  restore are workflow safeguards, not DG4000 SCPI coverage.
- Driver basic-state transaction recovery covers output, function, frequency, frequency mode,
  amplitude unit/value, offset, and square duty. Core run restore remains the narrower
  output/function/frequency/amplitude/duty contract and starts with output OFF. Neither restores
  phase, load, modulation, the complete sweep profile, or overwritten volatile USER data.
- `source.channel_profile` is an independent, all-or-nothing read-only context. It does not change
  the basic-restore field set or add load, polarity, noise, sync, burst, modulation, marker, or
  pulse hold to automatic restoration.
- `source.sweep_profile` is also an independent, all-or-nothing read-only context. It does not
  start, stop, or trigger a sweep and does not add the frequency window, spacing, timing, trigger,
  or marker fields to automatic restoration.
- `source.counter_profile` is a global, all-or-nothing read-only context. While the counter is OFF,
  it returns `measurement=None` without querying a measurement. It does not enable the counter,
  send `AUTO` or statistics clear, or add input/statistics fields to automatic restoration.
- Descriptor capability validation proves that declared methods exist and are callable. It does not
  prove SCPI semantics, response parsing, or hardware compatibility.

## Recommended roadmap

1. **P2/P3: M7-M10 controlled write transactions.** Completed Sweep/Pulse/Burst read facets are
   not configuration capability; writes still need independent models, snapshots, restoration,
   and latching.
2. **P3: M11 advanced features.** Harmonic is currently a `PARTIAL` read facet; keep per-order
   components, advanced modulation, and DAC16 as separate models.
3. **Out of default scope: filesystem, network, internal state slots, PA, restart/shutdown.** They
   need a permission model and human confirmation distinct from ordinary experiments.

## Evidence boundary

- **Manual**: the local vendor manual is used only for internal audit and is excluded from releases.
- **Implementation**: external `driver.py`/`descriptor.py` and FakeTransport tests; bundled-driver
  history only distinguishes provenance and does not automatically accept the external plugin.
- **External hardware**: DG4202 firmware `00.01.14` passes the M1-M5 dual-channel gates and the M6
  global counter-OFF gate. M3
  completed 45 queries and zero text/binary writes under guards that rejected every write. M4 CH1
  passes protocol, a 64-point DAC14 triangle loop into a high-impedance RTM2032, and restoration;
  10,000 points measured 997.26 Hz and 2.16 Vpp with 0.0390 V triangle-template RMSE. M4 CH2 uses
  the same 64-point triangle and passes protocol, a 1 Vpp high-impedance RTM2032 loop, and
  restoration; it measured 999.75 Hz and 1.12 Vpp, with normalized triangle/sine-template RMSE of
  0.09285/0.2196 (ratio 0.4229), while scope timebase, range, and trigger settings stayed unchanged.
  M5 read CH1/CH2 three times in each output-OFF, sweep-OFF/ON preset state. Each read-only session
  completed 104 queries and zero text/binary writes; complete channel/sweep profiles matched their
  initial snapshots after restoration. M6 read three complete profiles with the counter OFF,
  issuing 39 queries and zero text/binary writes; counter/statistics/display state was unchanged and
  `measurement=None` was explicit. Version `0.7.0` also completed a 40-query Source V2 snapshot in
  the CH1/CH2 OFF/SIN/FIX state, then a 52-query snapshot and complete Pulse facets at output OFF,
  PULSE, and 1 Vpp. Both had matching anchors and healthy session state; a fresh final session
  verified OFF/SIN/1 kHz/5 Vpp/0 V/FIX restoration on both channels. Active Sweep, Burst ON,
  Harmonic, and the counter-ON tuple still lack fresh hardware evidence.
- **Historical arbitrary evidence**: prior bundled-driver evidence remains provenance only. The
  current external plugin now has independent CH1/CH2 protocol evidence and does not substitute
  historical results for acceptance.

Only a controlled command, device readback or external measurement, and any required restoration
check may promote an item to **External hardware accepted**.
