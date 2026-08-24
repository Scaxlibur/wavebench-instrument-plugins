# SDG2000X Full Built-in Arbitrary Catalog Acceptance

[中文](SDG2000X_BUILTIN_ARB_ACCEPTANCE.md)

## Conclusion

On 2026-08-21, one `SDG2122X` running firmware `2.01.01.39R7T2` completed A4 smoke acceptance for its entire built-in arbitrary catalog. Real `STL? BUILDIN` returned indices 0–198, totaling 199 entries. Every index completed selection readback, short output, and RTM2032 acquisition:

- selection readback: 199/199;
- catalog/selection name match: 199/199;
- physical acquisitions: 199/199;
- non-flat signal detected: 199/199;
- weak or flat signals: 0;
- maximum measured output: 0.72 Vpp;
- maximum absolute voltage: 0.36 V.

The pass used DDS, 1 kHz, 0.5 Vpp, and 0 V offset. It did not upload, delete, overwrite, or read user waveforms. The result proves that every advertised built-in index can be selected and produces controlled non-flat output; it is not per-shape calibration of all 199 functions, distortion, or amplitude accuracy.

## Environment and safety boundary

- WaveBench: 0.8.23.
- Plugin: `wavebench-siglent-sdg2000x` 0.8.0.
- Source: `SDG2122X`, firmware `2.01.01.39R7T2`.
- Oscilloscope: `RTM2032`, firmware `06.010`.
- Path: source CH2 to high-impedance scope CH2.
- Playback mode: DDS.
- Playback settings: 1 kHz, 0.5 Vpp, 0 V offset.
- Stop conditions: measured output reaching 9 Vpp or absolute voltage exceeding 5 V.

Harmonic, Modulation, Sweep, Burst, Combine, Noise Add, and Coupling were confirmed inactive. Each index followed “confirm OFF → select and read back → ON → acquire → OFF”. A separate 2 Vpp conservative envelope remained well below the project hard limit.

## Coverage method

The catalog came dynamically from real `STL? BUILDIN`, not a copied table. Every entry had to satisfy:

1. completed `C2:ARWV INDEX,<index>` write;
2. matching index from `C2:ARWV?`;
3. case-insensitive selection name equal to the catalog name;
4. at least 1000 RTM2032 points;
5. measured output below 2 Vpp and absolute voltage below 5 V;
6. Vpp above 0.03 V and centered RMS above 0.003 V.

The final criterion excludes a flat, missing, or pure noise-floor acquisition. It does not measure mathematical shape error.

## Guide discrepancy

The E05C model table lists built-in SDG2000X indices as 2–198. This instrument's catalog and selection command both accepted 0–198, so the pass covered all 199 entries actually advertised by the hardware. The plugin does not extrapolate this discrepancy to SDG2042X/SDG2082X or use it to expand a write capability.

## Transport audit and restoration

The formal pass used 806 queries and 809 writes. Every write was transmitted and completed, with zero unknown outcomes. It restored the original arbitrary selection, CH2 Sine / 1 kHz / 4 Vpp / 0 V, both outputs OFF, and unchanged RTM2032 channel/probe/timebase/trigger snapshots with no overload.

A separate fresh session reconfirmed both outputs OFF using 13 queries and zero writes.

## Product boundary

- The only public product capability remains read-only `source.arbitrary_probe`; full-catalog writes belonged to a one-off managed acceptance script and are not caller-accessible.
- No `WVDT` or local/network/USB filesystem write was sent.
- `STL? USER` was not queried, and evidence contains no user waveform names.
- 199/199 is selection/output smoke coverage for this firmware's built-in catalog, not 100% coverage of other models, firmware, sample-rate modes, or analog performance.
