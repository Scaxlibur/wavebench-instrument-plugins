# SDG2000X Basic-Write Hardware Acceptance

[中文](SDG2000X_BASIC_WRITE_ACCEPTANCE.md)

## Conclusion

On 2026-08-21, `wavebench-siglent-sdg2000x` 0.7.0 completed CH2 hardware acceptance for the core's current basic Source write surface on one `SDG2122X`:

- `source.set_frequency`;
- `source.set_function`;
- `source.set_amplitude_vpp`;
- `source.set_square_duty_cycle`;
- `source.output`.

Periodic functions and live frequency, amplitude, and duty-cycle updates passed complete driver readback plus RTM2032 closed-loop measurement. The maximum measured Vpp was 4.24 V, below the 10 Vpp hard limit. The scope did not overload and its configuration snapshot did not drift. The source ended restored to Sine, 1 kHz, 4 Vpp, with CH1/CH2 OFF.

Noise and DC completed configuration readback only while output was OFF. The current core `SourceService.set_output` calls `isfinite()` on `SourceStatus.amplitude=None`, raising `TypeError` before any instrument write. The plugin does not fabricate a Vpp value and the core remains unchanged; this issue is carried into a multi-vendor Source state/safety RFC.

## Environment and boundary

- WaveBench: 0.8.23.
- Final plugin version: `wavebench-siglent-sdg2000x` 0.7.0.
- Source: `SDG2122X`, firmware `2.01.01.39R7T2`.
- Oscilloscope: `RTM2032`, firmware `06.010`.
- Path: source CH2 to scope CH2; the scope input remained high impedance.
- Core Vpp limit: 10 Vpp.
- No `*RST`, network configuration, persistent storage, arbitrary-wave upload, or raw-SCPI bypass was used.

## Frequency and amplitude

| Capability | Scenario | Set/readback | RTM2032 frequency | RTM2032 Vpp | Mean |
| --- | --- | ---: | ---: | ---: | ---: |
| Frequency | OFF-state write, then enable | 2,000 Hz | 2,000.00 Hz | 4.080 V | -0.007 V |
| Frequency | Live ON-state write | 5,000 Hz | 5,000.00 Hz | 4.080 V | -0.008 V |
| Amplitude | OFF-state write, then enable | 2.0 Vpp | 998.00 Hz | 2.160 V | -0.003 V |
| Amplitude | Live ON-state write | 3.0 Vpp | 1,000.75 Hz | 3.120 V | -0.003 V |

Each waveform contained 10,000 points. Frequency error remained below 2%. The scope retained its existing 2 V/div setting rather than changing range to produce cosmetically closer amplitude numbers.

## Function

With CH2 output ON, the test switched live through Square, Ramp, Pulse, and Sine. Every waveform remained near 1 kHz and 4 Vpp:

| Function | Frequency | Vpp | Minimum | Maximum | Normalized RMS | High fraction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Square | 1,000.00 Hz | 4.160 V | -2.120 V | 2.040 V | 0.953 | 0.500 |
| Ramp | 1,000.00 Hz | 4.080 V | -2.040 V | 2.040 V | 0.564 | 0.496 |
| Pulse | 1,000.01 Hz | 4.160 V | -2.120 V | 2.040 V | 0.762 | 0.200 |
| Sine | 999.75 Hz | 4.080 V | -2.040 V | 2.040 V | 0.690 | 0.498 |

Pulse retained the instrument's existing 20% high fraction, so its mean was approximately -1.20 V; this is consistent with a 0 V midpoint offset. Noise and DC function writes, strict response parsing, and OFF-state readback passed. Output enable remained denied.

## Square duty cycle

The test wrote 40% with output OFF, then wrote 20% and 80% live. Physical high fractions were 0.200 and 0.800:

| Set/readback | Frequency | Vpp | Measured high fraction | Mean |
| ---: | ---: | ---: | ---: | ---: |
| 20% | 1,000.00 Hz | 4.160 V | 0.200 | -1.204 V |
| 80% | 1,000.00 Hz | 4.160 V | 0.800 | 1.182 V |

Square duty was restored to 50% before restoring Sine.

## Fail-closed evidence

The first function acceptance attempt timed out on `HARM?` after Sine→Square. E05C states that Harmonic Command is available only when the basic wave is SINE. The previous implementation treated `HARM?` as an unconditional safety query, causing transport-session failure; that session could not verify OFF.

Recovery and correction were:

1. Stop the waveform sequence immediately.
2. Use a fresh WaveBench session to request OFF on the channel needing convergence.
3. Independently read CH1/CH2 and confirm both OFF.
4. Make harmonic query activation function-dependent: omit `HARM?` outside SINE and query it again when returning to SINE.
5. Add tests for zero harmonic queries outside SINE and reactivated harmonic state when returning to SINE.
6. Rerun complete function acceptance.

The fix is commit `d7e1b03`. The emergency fresh session completed one OFF write with zero unknown outcomes; formal acceptance then passed.

## Transport audit

| Phase | Queries | Write requests | Completed | Unknown | Final state |
| --- | ---: | ---: | ---: | ---: | --- |
| Frequency | 99 | 5 | 5 | 0 | Restored 1 kHz; both OFF |
| Amplitude | 99 | 5 | 5 | 0 | Restored 4 Vpp; both OFF |
| Function | 179 | 9 | 9 | 0 | Restored Sine; both OFF |
| Duty cycle | 150 | 8 | 8 | 0 | Restored 50% and Sine; both OFF |

## Remaining coverage

- CH1 basic-write loops remain pending because its pre-existing harmonic state is rejected without a write.
- `SDG2042X` and `SDG2082X` have offline contract evidence only.
- Noise/DC lack a reusable core voltage-state and safety-budget model, so output-waveform acceptance is not claimed.
- The 1 µHz floor, model upper frequency bounds, and 0.001%/99.999% duty limits are offline boundaries. They cannot be presented as full-range physical acceptance with the current high-impedance path and 5 ms acquisition window.
