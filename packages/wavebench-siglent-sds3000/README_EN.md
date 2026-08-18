# WaveBench SIGLENT SDS3000 Plugin (Under Development)

[中文](README.md)

This package provides an external WaveBench driver for the early SIGLENT SDS3000 oscilloscope family. It does not cover later products whose names include `X` or `HD`. The installable scaffold and strict identity gate are in place; only the offline-verified `scope.idn` capability is currently declared.

The first validation target is the SIGLENT SDS3054. Other models from the same generation will enter the compatibility range only when supported by vendor documentation and test evidence.

## Confirmed instrument identity

- Chassis model: SIGLENT SDS3054, 500 MHz, 4 GSa/s.
- Platform mark: `SIGLENT Powered by TELEDYNE LECROY`.
- Redacted remote identity: `LECROY,SDS3054,<serial>,8.4.1`.
- Front-panel remote mode: `TCPIP (VICP)`.
- Command family: Teledyne LeCroy MAUI/X-Stream Remote Command Set.

This identity constrains only the SDS3054 driver. It does not permit arbitrary LeCroy instruments or imply protocol compatibility with other SIGLENT SDS families.

## Current status

- Stage: M2 installable plugin scaffold.
- Distribution: `wavebench-siglent-sds3000`.
- Canonical driver ID: `siglent.sds3000`.
- Instrument kind: `scope`.
- Initial model: `SDS3054`.
- WaveBench compatibility: `>=0.8.22,<0.9`.
- Transport: WaveBench `pyvisa`, currently restricted to `tcpip` resources.
- Declared capability: `scope.idn`.

Descriptor loading and driver construction perform no instrument I/O. Calling `scope.idn` sends exactly one `*IDN?` and accepts only `LECROY,SDS3054,<serial>,8.4.1`. Other manufacturers, models, or firmware revisions are rejected without writes.

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

The repository-level `.gitignore` excludes everything under `doc/vendor-local/` except its explanatory README. Vendor material therefore does not enter Git. Project-authored protocol summaries, coverage matrices, and acceptance records will be written separately under `doc/`.

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
