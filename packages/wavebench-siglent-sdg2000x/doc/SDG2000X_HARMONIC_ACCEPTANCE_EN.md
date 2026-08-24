# SDG2000X Harmonic Protocol and Spectrum Acceptance

[中文](SDG2000X_HARMONIC_ACCEPTANCE.md)

## Conclusion

On 2026-08-21, one `SDG2122X` running firmware `2.01.01.39R7T2` completed selected-slot protocol characterization and A4 harmonic-spectrum acceptance. H2–H16 were selectable, writable, and independently readable. RTM2032 FFT measurements cross-checked H2/H3 amplitude, H2 phase, and ALL/EVEN/ODD selection. The conservative composite budget was 6 Vpp and the maximum measured result was 4.80 Vpp, below the 9 V stop threshold and 10 Vpp hard limit.

The current core `SourceHarmonicProfile` requires a complete fixed H2–H16 tuple, while SDG `HARM?` returns only the selected slot and reading another slot requires a `HARMORDER` write. The core model also lacks the overall harmonic-enable state. The plugin therefore does not declare `source.harmonic_profile` or `source.harmonic_configure`, and it does not fabricate zero-valued unread slots. See the reusable [Source V2 RFC](RFC_SOURCE_V2_CAPABILITY_STATE_SAFETY_EN.md).

## Environment and safety boundary

- WaveBench: 0.8.23.
- Plugin: `wavebench-siglent-sdg2000x` 0.7.0; selected-slot parser commit `7362f3d`.
- Source: `SDG2122X`, firmware `2.01.01.39R7T2`.
- Oscilloscope: `RTM2032`, firmware `06.010`.
- Path: source CH1 to scope CH1 on the existing high-impedance loop.
- Fundamental: Sine, 1 kHz, 4 Vpp, 0 V offset.
- Test components: H2=1.2 Vpp and H3=0.8 Vpp.
- Worst-case in-phase budget: `4 + 1.2 + 0.8 = 6 Vpp`.
- Stop threshold: measured 9 Vpp; hard limit: 10 Vpp.

Output was confirmed OFF before each harmonic configuration change and turned OFF immediately after each acquisition. No reset, network, persistent-storage, or arbitrary-upload command was used.

## Slots and manual discrepancy

The programming guide uses a model-dependent maximum `M`, the datasheet says 10 harmonics, and the user guide says 16. With temporary `HARMTYPE=ALL`, hardware selected and read back every slot from H2 through H16.

The restored state was `HARMSTATE=ON`, `HARMTYPE=EVEN`, `HARMORDER=2`, `HARMAMP=0 Vpp`, `HARMDBC=-80 dBc`, and `HARMPHASE=0°`.

Slot enumeration used 23 queries and 18 completed writes, with zero unknown outcomes. Both outputs ended OFF.

## Spectrum results

Every acquisition used 10,000 points and a Hann-window FFT with 200 Hz resolution.

| Scenario | Measured Vpp | Fundamental | H2/fundamental | H3/fundamental | H2 relative phase |
| --- | ---: | ---: | ---: | ---: | ---: |
| Harmonic OFF baseline | 4.160 V | 1,000 Hz | 0.0011 | 0.0010 | Not phase evidence |
| ALL, H2 at 0° | 4.720 V | 1,000 Hz | 0.2992 | 0.0009 | 90.35° |
| ALL, H2 at 90° | 4.160 V | 1,000 Hz | 0.3008 | 0.0014 | -179.96° |
| ALL, H2+H3 | 4.800 V | 1,000 Hz | 0.2980 | 0.2005 | 90.28° |
| EVEN | 4.720 V | 1,000 Hz | 0.2985 | 0.0013 | 90.26° |
| ODD | 3.600 V | 1,000 Hz | 0.0020 | 0.2002 | H2 suppressed |

Changing programmed H2 phase from 0° to 90° produced a 89.69° relative change after cancelling free-running fundamental phase. EVEN suppressed H3 and ODD suppressed H2.

## Transport audit and restoration

The formal spectrum interval used 64 queries and 128 writes. All 128 writes were transmitted and completed, with zero unknown outcomes. The count includes zeroing 15 slots, configuring test components, six ON/OFF acquisitions, and full slot restoration.

The final state restored harmonic `EVEN/H2/ON/0 V/0°`, retained CH1 Sine / 1 kHz / 4 Vpp / 0 V, left CH1/CH2 OFF, preserved the RTM2032 channel/probe/timebase/trigger snapshots, and caused no overload.

## Coverage boundary

- Evidence applies to the tested SDG2122X firmware only.
- `HARMDBC` has strict parsing and existing -80 dBc readback, but no separate dBc-write spectrum acceptance.
- The cable path was not phase calibrated. The 89.69° result is a same-path relative change, not absolute phase calibration.
- Because the core cannot losslessly express selected-only completeness and enable state, no product capability is declared. This is managed protocol and A4 hardware evidence.
