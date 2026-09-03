# DS1000Z Controlled Hardware Acceptance

[中文](DS1000Z_HARDWARE_ACCEPTANCE.md)

> Type: Historical evidence
> Scope: sanitized DS1104Z Plus regression on 2026-07-21
> Current capability entry: [generated plugin catalog](../../../doc/reference/plugin-catalog-en.md)

This page preserves results for a particular device, connection, and point in time. It does not
replace the production descriptor or imply equal analog-accuracy or performance coverage for every
DS1000Z model.

## Single-channel and long-record paths

Identity, an empty error queue, high-impedance CH1 coupling, a 1,200-point NORM read, explicit
autoscale, 2,400,000-point MAX and DMAX chunked reads, a PNG screenshot, and one-acquisition CH1/CH2
capture all passed. Each MAX/DMAX transfer used ten chunks of at most 250,000 points, and the error
queue was empty before and after the run.

## Four-channel path

Coupling queries passed for CH1–CH4. After one acquisition and one OPC wait, every channel returned
a finite 1,200-point waveform with a 2 µs sample interval, and the error queue remained empty. CH1
measured about 2.04 Vpp at the time. CH2–CH4 had no independent test signal, so the run validates
their communication and acquisition paths, not independent analog-amplitude accuracy.

## Performance and evidence boundary

The VXI-11 path took about 135 seconds per 2,400,000-point transfer at the time. This establishes
functional completeness, not optimized long-record performance. The acceptance wrote no real
configuration, resource, serial number, waveform, screenshot, or command log to the repository.

## Provenance

The initial `0.1.0` implementation was migrated from WaveBench's installable DS1000Z pilot package.
It preserves the original canonical ID, entry point, compatibility range, and driver semantics. This
repository is the source of truth for the external package after migration.
