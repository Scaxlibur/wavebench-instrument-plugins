# SDG2000X Modulation Protocol and Waveform Acceptance

[中文](SDG2000X_MODULATION_ACCEPTANCE.md)

## Conclusion

On 2026-08-21, one `SDG2122X` running firmware `2.01.01.39R7T2` completed output-OFF protocol characterization and A4 waveform acceptance for AM, DSB-AM, FM, PM, PWM, ASK, FSK, and PSK. Every mode used an internal modulation source. Carrier amplitude was 2 Vpp; the worst-case 50% AM envelope budget was 3 Vpp. Maximum measured output was 3.12 Vpp, below the 9 V stop threshold and 10 Vpp hard limit.

Current core modulation profiles require complete internal-source parameters even when `enabled=False`, while SDG returns only `STATE,OFF`. The core internal-modulation frequency range is also narrower than the SDG datasheet's 1 MHz maximum. The plugin does not insert fake defaults and does not declare a lossy modulation capability. See the [Source V2 RFC](RFC_SOURCE_V2_CAPABILITY_STATE_SAFETY_EN.md).

## Environment and safety boundary

- WaveBench: 0.8.23.
- Plugin: `wavebench-siglent-sdg2000x` 0.7.0.
- Source: `SDG2122X`, firmware `2.01.01.39R7T2`.
- Oscilloscope: `RTM2032`, firmware `06.010`.
- Path: source CH2 to high-impedance scope CH2.
- Analog/digital carrier: Sine, 20 kHz, 2 Vpp, 0 V; PWM used a 10 kHz Pulse carrier.
- Internal modulation/key rate: 1 kHz.
- AM depth: 50%; FM deviation: 2 kHz; PM deviation: 90°; PWM `DDEVI`: 20%; FSK hop: 25 kHz.

Each mode was configured and fully queried with output OFF. Output was enabled only for acquisition and immediately disabled afterward. No external modulation connection was available, so external-source acceptance is not claimed.

## Protocol characterization

The OFF-output protocol pass verified real response fields for all eight types. PWM hardware response distinguishes second-based width `DEVI` from percent duty `DDEVI`; the waveform test explicitly used `DDEVI,20`.

The protocol pass used 90 queries and 82 completed writes with zero unknown outcomes. It ended with modulation OFF, Sine / 1 kHz / 4 Vpp restored, and both outputs OFF.

## Waveform results

Every mode used 10,000 points. Fixed-frequency amplitudes used Hann-window complex projection, envelopes used the analytic signal, FSK used smoothed instantaneous frequency, and PSK used 20 kHz down-converted baseband polarity.

| Type | Physical evidence | Vpp |
| --- | --- | ---: |
| AM | Envelope P05/P95 0.502/1.489 V; estimated depth 49.6% | 3.120 V |
| DSB-AM | 19/21 kHz sidebands 0.499/0.498 V; 20 kHz carrier 0.0007 V | 2.160 V |
| FM | 19/21 kHz sidebands 0.577/0.578 V; instantaneous P20/P80 18.46/21.57 kHz | 2.160 V |
| PM | 19/21 kHz sidebands 0.565/0.565 V; instantaneous P20/P80 18.77/21.20 kHz | 2.160 V |
| PWM | Per-cycle duty P05/P95 31.0%/69.5% | 2.160 V |
| ASK | Envelope P05/P95 0.034/1.056 V | 2.160 V |
| FSK | Smoothed instantaneous P20/P80 19.95/25.08 kHz | 2.160 V |
| PSK | Down-converted positive/negative polarity 51.9%/48.1%; 19/21 kHz 0.650/0.619 V | 2.160 V |

Every waveform stayed within ±1.56 V with near-zero mean and no scope overload.

## Transport audit and restoration

The formal A4 waveform pass used 39 queries and 107 writes. All writes were transmitted and completed, with zero unknown outcomes. It ended with modulation OFF, CH2 restored to Sine / 1 kHz / 4 Vpp / 0 V, both outputs OFF, unchanged RTM2032 channel/probe/timebase/trigger snapshots, and no overload.

## Coverage boundary

- Only internal modulation sources were accepted. EXT and CH1/CH2 cross-modulation lack physical wiring.
- Evidence applies only to the tested SDG2122X firmware.
- Digital-keying evidence verifies behavior and spectrum/envelope, not calibrated modulation error, EVM, or phase noise.
- Because disabled state and ranges cannot map losslessly to current core profiles, this remains managed protocol and A4 evidence rather than a declared product capability.
