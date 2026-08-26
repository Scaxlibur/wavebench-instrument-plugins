# WaveBench SIGLENT SDS3000 Plugin

[中文](README.md)

This package provides an external WaveBench driver for the early SIGLENT SDS3000 oscilloscope family. It does not cover later products whose names include `X` or `HD`. The installable plugin now includes a strict identity gate, error-register reads, channel-coupling mapping, binary waveform reads, and single- or same-acquisition multi-channel capture.

The first validation target is the SIGLENT SDS3054. Other models from the same generation will enter the compatibility range only when supported by vendor documentation and test evidence.

## Confirmed instrument identity

- Chassis model: SIGLENT SDS3054, 500 MHz, 4 GSa/s.
- Platform mark: `SIGLENT Powered by TELEDYNE LECROY`.
- Redacted remote identity: `*IDN LECROY,SDS3054,<serial>,8.4.1`.
- Front-panel remote mode: `TCPIP (VICP)`.
- Command family: Teledyne LeCroy MAUI/X-Stream Remote Command Set.

This identity constrains only the SDS3054 driver. It does not permit arbitrary LeCroy instruments or imply protocol compatibility with other SIGLENT SDS families.

## Current status

- Stage: M8 functionally complete; WaveBench `0.8.24` transport/session P0 is adopted.
- Distribution: `wavebench-siglent-sds3000`.
- Canonical driver ID: `siglent.sds3000`.
- Instrument kind: `scope`.
- Initial model: `SDS3054`.
- WaveBench compatibility: `>=0.8.24,<0.9`.
- Transport: WaveBench `pyvisa`; `VICP::<host>::INSTR` is verified using `PyVICP>=1.1,<2`.
- Declared capabilities: `scope.idn`, `scope.errors`, `scope.channel_coupling`, `scope.fetch_waveform`, `scope.capture_waveform`, and `scope.capture_waveforms`.

“M8 functionally complete” means that these capabilities are implemented and passed their defined acceptance gates. The plugin adopts the WaveBench `0.8.24` transport/session P0 contract, including explicit non-replay policies, structured-error propagation, and shared-session-health fault injection. The wheel and descriptor minimum versions are both `0.8.24`; the upper bound remains `0.9`, and `api_version` remains `wavebench.instrument.v2`. See the [core RFC](doc/WAVEBENCH_CORE_RFC_EN.md) for the impact assessment and verification evidence.

P0 adoption was revalidated with dual-channel SDG2000X input at 1 kHz, 1 Vpp, and 0 V offset per channel. SDS3054 CH1 and CH2 were both `DCL`, and the final independent readback confirmed both generator outputs OFF. See the redacted [hardware acceptance](doc/HARDWARE_ACCEPTANCE_EN.md).

Descriptor loading and driver construction perform no instrument I/O. Calling `scope.idn` sends exactly one `*IDN?` and accepts only `*IDN LECROY,SDS3054,<serial>,8.4.1`, plus the corresponding bare identity when `CHDR OFF` suppresses the response header. Other manufacturers, models, or firmware revisions are rejected without writes.

When the front panel selects `TCP/IP (VICP)`, use `VICP::<host>::INSTR`. `TCPIP::<host>::INSTR` means VXI-11 and is valid only after the front panel is switched to `LXI (VXI-11)`; the two resource forms are not interchangeable.

`scope.channel_coupling` maps MAUI `A1M`, `D1M`, `D50`, and `GND` to WaveBench `ACL`, `DCL`, `DC`, and `GND`. An `OVL` response is treated as a 50-ohm input overload and stops the operation. `scope.errors` reads and clears `CMR`, `EXR`, and `DDR` in order; it is an existing WaveBench `stateful_read`, not a side-effect-free query.

`scope.fetch_waveform` uses the existing WaveBench waveform models and `query_bin_block()` transport interface. It snapshots `CHDR`, `CFMT`, `CORD`, and `WFSU`, temporarily selects `DEF9,WORD,BIN` with low byte first and one segment, then restores the original state in reverse order. A restoration failure becomes `StateDriftError`. Only the `WF?` read direction is implemented; writing `WF` back into internal memory remains quarantined and is not reported as supported.

`scope.capture_waveform` and `scope.capture_waveforms` share one atomic acquisition transaction. The driver snapshots trigger mode, timebase, V/div, and trace state before `STOP → ARM → WAIT → *OPC?`; after requiring `TRMD STOP`, it reads every requested channel without retriggering and restores acquisition and transfer state in reverse order. Three dual-channel 1 kHz, 1 Vpp hardware rounds passed.

## Programming-manual drop location

Place vendor manuals or local conversion output under:

```text
doc/vendor-local/
```

The current local source is the February 2026 *Oscilloscopes Remote Control and Automation Manual*. The upload converter split the 411-page source into three segments of 200, 200, and 11 pages. Project-authored audit documentation records their order and hashes. Retain the vendor filename when possible. A normalized filename may be used when needed:

```text
Oscilloscopes_Remote_Control_and_Automation_Manual_2026-02.pdf
```

This manual is newer than the instrument firmware `8.4.1`, and some sections explicitly require MAUI `8.5.0.0+`. Explicitly documented entities form the audit denominator, but an entity counts as supported by firmware `8.4.1` only after offline evidence or safe hardware testing confirms it. Model operator manuals, datasheets, and release notes may be placed in the same directory.

See [`doc/MANUAL_BASELINE_EN.md`](doc/MANUAL_BASELINE_EN.md) for source hashes, segment order, applicability boundaries, and the coverage denominator.

See [`doc/COMMAND_COVERAGE_EN.md`](doc/COMMAND_COVERAGE_EN.md) for the complete denominator and dispositions. The current catalog freezes 578 explicit entities, including 478 callable entities, with zero unclassified entries.

See [`doc/WAVEBENCH_CAPABILITY_MATRIX_EN.md`](doc/WAVEBENCH_CAPABILITY_MATRIX_EN.md) for all 26 WaveBench `0.8.24` scope capabilities. Six are declared; every other item has an explicit firmware, option, core-model, or safety disposition. The cross-vendor core impact RFC remains `Draft / Needs revision`; transport/session P0 is adopted, while typed-scope and generic-write proposals remain open. This plugin branch does not modify WaveBench core.

Redacted hardware results are in [`doc/HARDWARE_ACCEPTANCE_EN.md`](doc/HARDWARE_ACCEPTANCE_EN.md). They contain no resource address, serial number, raw waveform, screenshot, or command log.

The repository-level `.gitignore` excludes everything under `doc/vendor-local/` except its explanatory README. Vendor material therefore does not enter Git. Project-authored protocol summaries, coverage matrices, and acceptance records are kept under `doc/`.

## Review order after the manuals arrive

1. Record each title, document number, revision, publication date, applicable platform, and SHA-256.
2. Separate IEEE 488.2 legacy commands from the `VBS app...` Automation object hierarchy and establish the firmware `8.4.1` boundary.
3. Verify VICP, VXI-11, and USBTMC behavior against existing WaveBench transports.
4. Review termination, communication headers, error semantics, waveform templates, binary transfer, screenshots, and state effects.
5. Freeze the distribution, canonical driver ID, identity gate, and supported models.
6. Add capabilities through M3–M8 only after FakeTransport tests and tiered hardware acceptance.

## Safety boundaries

- Do not infer this protocol from SDS3000X, SDS3000X HD, or other newer SIGLENT SDS manuals.
- Do not create a public interface outside WaveBench to fill missing capabilities; submit a separate core proposal when required.
- Descriptor import must not connect to an instrument, scan resources, create files, or mutate global state.
- A driver may obtain the core transport only through `DriverContext.open_transport()`.
- Instrument writes, output changes, and acquisition triggers must not be retried blindly.
- Real resources, serial numbers, credentials, raw waveforms, screenshots, and laboratory logs must not be committed.

## License boundary

Project-authored documentation in this directory is covered by the repository's root MIT License. Vendor material placed under `doc/vendor-local/` retains its original rights status; it does not become MIT-licensed and is not part of a public distribution.
