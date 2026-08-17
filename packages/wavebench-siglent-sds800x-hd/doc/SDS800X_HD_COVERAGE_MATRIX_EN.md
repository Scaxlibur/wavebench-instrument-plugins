# SDS800X HD Programming-Guide Coverage Matrix

[中文](SDS800X_HD_COVERAGE_MATRIX.md)

## Purpose and evidence boundary

This matrix compares the SIGLENT SDS Series Digital Oscilloscope Programming Guide,
revision `CN11G`, with the external WaveBench `siglent.sds800x-hd` plugin. It separates
manual claims, offline implementation, and hardware acceptance. A command in the shared SDS
manual is not automatically treated as an SDS800X HD capability.

The local conversion is split across three directories because of converter limits. Their three
`full.md` files remain under `doc/vendor-local/`, excluded from Git and the sdist. The manual's
support table gives `1.1.3.1` as the minimum SDS800X HD firmware, but it does not mark every
command by supported family. Model and firmware behavior therefore still require target-hardware
confirmation.

Evidence labels used here:

- **Implemented / offline verified**: driver and FakeTransport tests exist; no SDS800X HD hardware evidence exists yet.
- **Manual reviewed**: command and response semantics were reviewed, but no capability is exposed yet.
- **Core interface blocked**: the vendor protocol cannot be represented completely by the current WaveBench transport or public model.
- **Hardware blocked**: offline code cannot establish response framing, state transitions, or hardware-specific behavior.
- **Rejected by default**: the operation changes global state, writes instrument storage, or lacks a reliable restore boundary.

## Current coverage

| Domain | Manual surface | WaveBench mapping | Status | Boundary and next step |
|---|---|---|---|---|
| Identity | `*IDN?` | `scope.idn` | **Implemented / offline verified** | Strict four-field, manufacturer, and model checks still need a redacted hardware sample |
| Analog-channel coupling | `:CHANnel<n>:COUPling?`, returning `AC`, `DC`, or `GND` | `scope.channel_coupling` | **Implemented / offline verified** | Limit `<n>` by two- or four-channel model and reject unknown responses; hardware acceptance remains pending |
| Input termination | Shared manual lists `ONEMeg` and `FIFTy` | No standalone capability | **Rejected by default** | SDS800X HD product material specifies fixed `1 MΩ`; do not project the shared `FIFTy` setter onto this family |
| Error queue | CN11G documents no error-queue query | `scope.errors` | **Not covered** | Do not guess `SYSTem:ERRor?`; consuming queries also conflict with automatic retries on ordinary core queries |
| Waveform read | `SOURce`, `STARt`, `INTerval`, `POINt`, `MAXPoint?`, `WIDTh`, `BYTeorder`, `PREamble?`, and `DATA?` | `scope.fetch_waveform` | **Manual reviewed** | First version is limited to non-sequence analog channels, `INTerval 1`, explicit LSB, and strict definite blocks; record stability across chunks needs hardware confirmation |
| Single and multichannel capture | `TRIGger:MODE`, `RUN`, `STOP`, `STATus?`, and `*OPC?` | `scope.capture_waveform`, `scope.capture_waveforms` | **Hardware blocked** | The manual does not guarantee that `*OPC?` after `RUN` waits for a physical trigger; multichannel capture must read all channels after one acquisition |
| Trigger run state | `:TRIGger:STATus?` returns `Arm`, `Ready`, `Auto`, `Trig'd`, `Stop`, or `Roll` | No standalone capability | **Manual reviewed** | It cannot be mapped to public `ScopeAcquisitionStatus`, which describes averaging and segmented acquisition |
| Screenshot | `:PRINt? PNG,NORMal` or inverted form | `scope.screenshot` | **Core interface blocked / hardware blocked** | The example reads raw image bytes while the core exposes only definite-block queries; the command also has no reliable menu control |
| Autoset | `:AUToset` | `scope.autoscale` | **Rejected by default** | Changes trigger, vertical, and horizontal state without an error queue or restore loop |
| Acquisition status | `ACQuire:TYPE?`, `SEQuence?`, `NUMACq?`, and related queries | `scope.acquisition_status` | **Not covered** | Missing `average_complete`, option identity, capacity, and available-segment semantics prevent constructing the public model |
| Snapshot, measurement, digital, history, and analysis | Shared SDS subsystems | Corresponding optional Scope capabilities | **Not covered** | Review each capability for model, option, public-model, and restore semantics |
| Reset, system, and instrument filesystem | `*RST`, system settings, save/recall, image save, and related commands | No baseline capability | **Rejected by default** | May alter global state, networking, or persistent storage |

## Confirmed waveform-protocol boundary

`PREamble?` returns a definite-length binary block. Its fixed descriptor portion is 346 bytes;
sequence data may append timestamps, so a parser must not require the entire payload to be exactly
346 bytes. `DATA?` also uses a declared-length binary block. Parsers must honor that length and
must never apply `rstrip()` to binary data.

The first analog conversion uses these documented fields:

```text
vdiv = vertical_scale_raw * probe
offset = vertical_offset_raw * probe
voltage = raw_code * (vdiv / code_per_div) - offset
```

With `STARt 0` and `INTerval 1`, the time axis is:

```text
x[i] = horizontal_delay - timebase * 10 / 2 + i * sample_interval
```

Eight-bit samples are signed integers. ADC widths above eight bits use `WORD`, explicit LSB order,
and signed 16-bit decoding. The manual describes higher-resolution samples as left-aligned with
zero-filled low bits; the first version does not shift them. The driver must query `MAXPoint?`
instead of hard-coding the example limit.

## WaveBench core constraints

- The driver obtains a core transport only through `DriverContext.open_transport()` and owns idempotent cleanup.
- A capability is declared only after its public method is complete; runtime callability checks do not replace signature and semantic tests.
- `fetch_waveform(channel, points="dmax", check_errors=True)` returns the core `WaveformData` and `WaveformHeader` models rather than plugin-local copies.
- CN11G provides no error queue, so waveform support cannot pretend to fulfill `check_errors=True`; its configuration gate and failure behavior must be explicit before exposure.
- Multichannel capture configures every channel, performs one acquisition, and then reads each channel. It must not retrigger per channel.
- The current core PyVISA path does not apply the separate `opc_timeout_ms` to `query_opc()`, so acquisition cannot yet claim a separate OPC timeout guarantee.

## Development order

1. M1: strict identity parsing and read-only `scope.channel_coupling`, with offline tests.
2. M2: a pure 346-byte preamble parser and data-conversion tests, followed by analog-only `scope.fetch_waveform`.
3. M3: redacted TCPIP and USB binary samples to confirm chunking, WORD alignment, timebase values, and transfer-setting restoration.
4. M4: independently validate trigger transitions, OPC waiting, and one multichannel acquisition before considering capture capabilities.
5. Track screenshot, digital channels, FFT, sequence/history, Autoset, and writes as separate work items; do not bypass gates with raw SCPI.

## SCPI used directly today

```text
*IDN?
:CHANnel<n>:COUPling?
```

A command appearing in this matrix is not necessarily declared by the descriptor or verified on hardware.
