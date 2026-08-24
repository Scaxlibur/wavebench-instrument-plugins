# SDG2000X Source V2 A3 Hardware Waveform Acceptance

[中文](SDG2000X_SOURCE_V2_A3_ACCEPTANCE.md)

## Conclusion

On 2026-08-24, `source.basic_configure_v2` completed A3 hardware waveform acceptance on one `SDG2122X`
running firmware `2.01.01.39R7T2` and one RTM2032. The high-impedance wiring was manually confirmed as
SDG CH1 → RTM2032 CH1 and SDG CH2 → RTM2032 CH2; both scope channels reported `DCL` coupling.

Eight scope captures covered the four declared Basic functions—Sine, Square, Ramp, and Pulse—on CH1 and CH2.
Every capture used a 2 kHz, 2 Vpp operating point; Square additionally verified 25% duty cycle. Every plan
quality gate and expectation passed. A final independent V2 snapshot returned Sine / 1 kHz / 1 Vpp / 0 V /
Harmonic OFF / output OFF on both channels.

This record proves `source.basic_configure_v2` waveform behavior only at the operating points listed below. It
does not extrapolate to other models, firmware, frequency or amplitude ranges, loads, or undeclared fields. It
is neither C3 release sign-off nor hardware fault-injection or recovery evidence.

## Software, Wiring, and Safety Boundary

- Core source version: WaveBench `0.8.24` development line; Source contract revision `R7`.
- Plugin: `wavebench-siglent-sdg2000x` `0.8.2`, canonical driver ID `siglent.sdg2000x`.
- The controlled configuration set `max_source_vpp` to 5 Vpp. All A3 outputs were 2 Vpp, below that limit and
  the authorized 10 Vpp ceiling.
- Every plan used `run check → run verify → run intent → run plan`. No raw SCPI was used and
  `wavebench.toml` was not changed.
- Each enable affected one source channel for about 0.3 s, followed immediately by disabling that channel.
  CH1 and CH2 were not enabled together.
- Private run records retain intent, operation artifacts, capture packages, and reports. Resource addresses,
  serial numbers, and raw responses are excluded from this document and release artifacts.

## Operating Points and Measurements

Each capture used 10,000 samples at about 2 MSa/s across about ten cycles. The frequency quality gate was
1.900–2.100 kHz and the Vpp quality gate was 1.6–2.4 Vpp. The two Square captures additionally required
20%–30% duty. Screenshots were manually reviewed and match the requested waveform form.

| Source channel | Requested function | Requested values | Measured Vpp | Measured frequency | Measured duty | Result |
| --- | --- | --- | --- | --- | --- | --- |
| CH1 | Square | 2 kHz, 2 Vpp, 25% | 2.032 Vpp | about 2.000 kHz | 25% | passed |
| CH1 | Ramp | 2 kHz, 2 Vpp | 2.000 Vpp | about 2.000 kHz | not applicable | passed |
| CH1 | Pulse | 2 kHz, 2 Vpp | 2.032 Vpp | about 2.000 kHz | 40% (observed) | passed |
| CH1 | Sine | 2 kHz, 2 Vpp | 2.016 Vpp | about 2.000 kHz | not applicable | passed |
| CH2 | Ramp | 2 kHz, 2 Vpp | 2.016 Vpp | about 2.001 kHz | not applicable | passed |
| CH2 | Square | 2 kHz, 2 Vpp, 25% | 2.048 Vpp | about 2.000 kHz | 25% | passed |
| CH2 | Pulse | 2 kHz, 2 Vpp | 2.048 Vpp | about 2.000 kHz | 40% (observed) | passed |
| CH2 | Sine | 2 kHz, 2 Vpp | 2.032 Vpp | about 2.001 kHz | not applicable | passed |

The 40% Pulse value is an observation from this device state, not a currently declared Source V2 Basic Pulse-
duty configuration. Square 25% is confirmed jointly by the `square_duty_cycle_percent` request, independent
readback, and scope measurement. Square/Pulse waveform mean changes with duty cycle; it is not a change to the
`offset_v` parameter.

## Transactions and Final State

The three controlled plans contained 12, 20, and 26 steps respectively, and every step reported `ok`. They
saved 42 Source V2 operation records. Three initial Output-OFF requests were already at target; all remaining
requests completed, and no recovery record was produced.

After the three plans, a new V2 snapshot confirmed:

- CH1: Sine / 1 kHz / 1 Vpp / 0 V / Harmonic OFF / output OFF.
- CH2: Sine / 1 kHz / 1 Vpp / 0 V / Harmonic OFF / output OFF.
- Every Source V2 operation retained `healthy` session health.

Scope capture changes acquisition, timebase, vertical, trigger, and waveform-transfer settings on the selected
scope channel. The RTM2032 currently supplies only a partial `scope status` summary rather than a complete
`scope.snapshot`; this run does not claim that those scope settings were restored. Final CH1/CH2 coupling
readback was `DCL`.

## Not Proven

- Other models, firmware, termination, loads, frequency/amplitude ranges, or simultaneous CH1/CH2 output.
- `offset_v` is a readable safety state in the current adapter but not an exposed V2 Basic write field. This run
  records only the pre-enable and final 0 V readback.
- Transport failure, ambiguous writes, and post-write mismatches. Those branches have A0 fault-injection, not
  hardware, evidence.
- Harmonic configuration/enable, modulation, Sweep, Burst, arbitrary upload, external triggering, or any other
  advanced capability.
- No final plugin-wheel conformance manifest existed when this acceptance ran; later candidate manifests and
  release sign-off status are recorded separately.
