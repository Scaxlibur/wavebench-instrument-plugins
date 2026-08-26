# SDG2000X Frequency-Write Hardware Acceptance

[中文](SDG2000X_FREQUENCY_ACCEPTANCE.md)

## Conclusion

On 2026-08-21, `source.set_frequency` from `wavebench-siglent-sdg2000x` 0.4.0 completed controlled CH2 hardware acceptance on one `SDG2122X`. A 2 kHz write with output OFF and a live 5 kHz write with output ON both passed complete driver readback and RTM2032 closed-loop measurement. The original 1 kHz configuration was restored, and an independent final read confirmed source CH1 and CH2 OFF.

This evidence is not extrapolated to CH1, `SDG2042X`, or `SDG2082X`. CH1's preflight state contained an enabled harmonic mode with 0 V harmonic amplitude. Both the output gate and frequency transaction rejected that channel without a write, as designed. CH1 acceptance remains pending until harmonic state has a public, restorable transaction.

## Environment and boundary

- WaveBench: 0.8.23.
- Plugin: `wavebench-siglent-sdg2000x` 0.4.0.
- Source: `SDG2122X`, firmware `2.01.01.39R7T2`.
- Oscilloscope: `RTM2032`, firmware `06.010`.
- Path: source CH2 to scope CH2; the scope input remained high impedance.
- Core Vpp limit: 10 Vpp; measured output was approximately 4.08 Vpp.
- No `*RST`, network configuration, persistent storage, arbitrary-wave upload, or raw-SCPI bypass was used.

Every source write used the public WaveBench capability through `SourceService`. The scope used only its established `scope.fetch` data path. Analog-channel, probe, timebase, and trigger snapshots matched before and after acceptance.

## Procedure

1. Read both source channels and require CH1/CH2 OFF.
2. Confirm CH2 as a 1 kHz, 4 Vpp, 0 V offset sine wave.
3. Call `source.set_frequency` at 2 kHz while output is OFF and verify the complete safety context.
4. Enable CH2 through `source.output`, allow it to settle, and fetch 10,000 RTM2032 points.
5. Keep output ON, call `source.set_frequency` at 5 kHz, and fetch another 10,000 points.
6. Turn CH2 OFF, restore 1 kHz, compare scope configuration snapshots, and reread both source outputs.

## Closed-loop results

| Scenario | Driver readback | RTM2032 hysteresis estimate | FFT peak | Measured Vpp | Mean voltage | Samples |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| OFF-state write, then enable | 2,000 Hz | 2,000.00 Hz | 2,000.00 Hz | 4.080 V | -0.007 V | 10,000 |
| Live ON-state write | 5,000 Hz | 5,000.00 Hz | 5,000.00 Hz | 4.080 V | -0.008 V | 10,000 |

Both frequency measurements stayed within the 2% gate. Vpp remained well below the 10 Vpp hard limit, and mean voltage remained near 0 V.

## Transport audit and final state

From immediately before the first frequency write through final status verification, the source-session delta was:

- 99 queries;
- 5 write requests;
- 5 transmitted writes;
- 5 completed writes;
- 0 unknown write outcomes;
- 5 instrument-mutation writes.

The five writes were three frequency transactions, one ON, and one OFF. CH2 ended restored to 1 kHz, source CH1/CH2 ended OFF, and the scope configuration snapshot did not drift.

## Remaining coverage

- `SDG2042X` and `SDG2082X` have offline model/function limit tests but no hardware evidence.
- CH1 frequency acceptance remains pending because its pre-existing harmonic state triggered the plugin's safety rejection; the CH2 conclusion is not reused for CH1.
- The 1 µHz floor and each model's upper bound have offline boundary coverage only. Upper-band hardware acceptance requires appropriate 50 Ω termination and an RF measurement setup; the current high-impedance path cannot support that claim.
