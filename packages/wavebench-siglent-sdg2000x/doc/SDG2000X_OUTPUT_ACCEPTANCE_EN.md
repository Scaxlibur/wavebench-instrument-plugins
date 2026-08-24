# SDG2000X Output-control Hardware Acceptance

[中文](SDG2000X_OUTPUT_ACCEPTANCE.md)

## Conclusion

On 2026-08-21, `source.output` from `wavebench-siglent-sdg2000x` 0.3.0 completed controlled hardware acceptance on one `SDG2122X` running firmware `2.01.01.39R7T2`. CH1 and CH2 each completed one ON, oscilloscope fetch, and OFF sequence. Each source session sent exactly one ON write and one OFF write, with zero unknown write outcomes.

The WaveBench core safety limit was 10 Vpp. Acceptance preserved the instrument's existing 1 kHz, 4 Vpp, 0 V offset sine configuration and sent no frequency, amplitude, or function writes. An `RTM2032` fetched 10,000 points from the corresponding channel. Measured frequency, Vpp, and mean voltage passed the acceptance thresholds on both paths. A separate new session confirmed both source outputs OFF at the end. The scope reported no overload or error state, and its channel, probe, timebase, and trigger snapshots matched their preflight values.

## Environment

- Plugin: `wavebench-siglent-sdg2000x` 0.3.0.
- Core: WaveBench 0.8.23.
- Source: `SDG2122X`, firmware `2.01.01.39R7T2`.
- Oscilloscope: `RTM2032`, firmware `06.010`.
- Cabling: SDG CH1 to RTM CH1; SDG CH2 to RTM CH2.
- Access: `read_write` for both instruments, still constrained by WaveBench capability and transport guards.
- Safety configuration: `safety_limits.max_source_vpp = 10.0`.
- Error policy: `source.check_errors = false`, because the E05C programming guide defines no accepted error-queue query.
- Resources, serial numbers, raw waveforms, and temporary configuration remained local and were not added to the repository.

## M3 transaction contract

`set_output(channel, enabled, *, check_errors=True) -> SourceStatus` matches the core `SourceDriver` interface. If `check_errors` is not `false`, the driver rejects the operation before any I/O instead of pretending that the unavailable `source.errors` capability succeeded.

The normal enable path is:

1. Validate the channel, Boolean state, and error policy.
2. Read a complete `SourceStatus`. Enabling requires FIX mode, sweep OFF, and known Vpp amplitude and voltage offset.
3. Let the core `SourceService` enforce `max_source_vpp`.
4. Return an already-matching state without a write.
5. Send `C<n>:OUTP ON|OFF` once, then perform an independent complete status readback and require every non-output channel field to remain unchanged.
6. After any post-write failure, latch further ON writes for the session and attempt one safe OFF recovery with readback. A failed recovery reports uncertain output state. Emergency OFF remains available while latched.

The descriptor exposes `source.output` for all three models listed by the guide. Fake transports verify the same command contract under each model identity. Hardware evidence in this document applies only to the tested `SDG2122X` and firmware revision.

## Offline gate

The 87 package tests cover:

- ON and OFF on CH1 and CH2, plus zero-write idempotent returns.
- `source.output` routing for all three registered models.
- Pre-I/O rejection of invalid channels, non-Boolean states, unsupported error checks, sweep state, and snapshots without bounded Vpp.
- Readback mismatch, readback failure, non-output drift, ambiguous write results, successful OFF recovery, and failed recovery.
- Zero-I/O rejection of ON after latching, while emergency OFF remains available.
- Core acceptance at exactly 10 Vpp and zero-write rejection at 10.0001 Vpp.

## Preflight state

| Field | CH1 | CH2 |
| --- | ---: | ---: |
| Output | `OFF` | `OFF` |
| Function | `SIN` | `SIN` |
| Frequency | 1 kHz | 1 kHz |
| Amplitude | 4 Vpp | 4 Vpp |
| Offset | 0 V | 0 V |
| Frequency mode | `FIX` | `FIX` |
| Sweep | `OFF` | `OFF` |

Both RTM2032 channels were enabled with `DCL` high-impedance inputs, 2 V/div, 16 V range, 0 V offset, and no overload. The time range was 5 ms, and waveform metadata reported 10,000 points with 500 ns increments.

## Closed-loop measurements

Acceptance limits were 5% frequency error, 15% Vpp error, and 0.2 V difference between measured mean and configured offset.

| Source channel | RTM channel | Points | Measured frequency | Frequency error | Measured Vpp | Vpp error | Measured mean | Result |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| CH1 | CH1 | 10,000 | 1000.500 Hz | 0.0500% | 4.160 V | 4.00% | -0.023 V | Pass |
| CH2 | CH2 | 10,000 | 998.502 Hz | 0.1498% | 4.080 V | 2.00% | -0.009 V | Pass |

The source audit counters were identical for each channel:

| Counter | Per-channel result |
| --- | ---: |
| Query | 25 |
| Write request | 2 |
| Write transmitted | 2 |
| Write completed | 2 |
| Write outcome unknown | 0 |
| Binary write request | 0 |
| Instrument mutation write | 2 |

Each RTM2032 fetch session issued six queries and four data-transfer setup writes, with zero unknown write outcomes. The path did not run autoscale, single acquisition, screenshot, or scope reset.

## Restoration and limits

- Each fetch was followed by OFF and readback in the same source session's `finally` path.
- A separate new session then performed safe OFF convergence and read CH1/CH2 status. Both outputs were `OFF`.
- Final RTM2032 snapshots reported `DCL`, 2 V/div, 16 V range, 0 V offset, no overload, a false error-queue-nonempty flag, and questionable condition 0 on both channels. Channel, probe, timebase, and trigger fields exactly matched preflight.
- This acceptance covers only `source.output`. Frequency, function, amplitude, duty-cycle, sweep, burst, trigger, and arbitrary-wave writes remain disabled.
- Hardware tests did not deliberately inject transport failures. Fake transports cover ambiguous writes, readback failures, and failed recovery.
- `SDG2042X` and `SDG2082X` use the same documented output command contract and are enabled in the descriptor, but still require their own hardware evidence.
