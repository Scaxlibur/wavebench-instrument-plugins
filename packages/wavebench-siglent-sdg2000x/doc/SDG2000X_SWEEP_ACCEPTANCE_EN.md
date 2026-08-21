# SDG2000X Sweep Protocol and Waveform Acceptance

[中文](SDG2000X_SWEEP_ACCEPTANCE.md)

## Conclusion

On 2026-08-21, one `SDG2122X` running firmware `2.01.01.39R7T2` completed output-OFF Sweep protocol characterization and A4 waveform acceptance. LINE, LOG, STEP, UP, DOWN, and UP_DOWN all read back from the instrument. All six internally triggered combinations traversed a measurable 1–10 kHz span on an RTM2032, and one manually triggered sweep was also observed.

The carrier was Sine, 2 Vpp, and 0 V offset. Maximum measured output was 2.24 Vpp, below the 9 V stop threshold and 10 Vpp hard limit. All 87 writes in the formal pass completed, with zero unknown outcomes.

The current core `SourceSweepProfile` requires complete values for steps, start/stop holds, return time, trigger slope, and marker state. This firmware does not return several of those fields and returns only `STATE,OFF` while disabled. The plugin inserts no fake defaults and declares no lossy Sweep capability. See the [Source V2 RFC](RFC_SOURCE_V2_CAPABILITY_STATE_SAFETY_EN.md).

## Environment and safety boundary

- WaveBench: 0.8.23.
- Plugin: `wavebench-siglent-sdg2000x` 0.7.0.
- Source: `SDG2122X`, firmware `2.01.01.39R7T2`.
- Oscilloscope: `RTM2032`, firmware `06.010`.
- Path: source CH2 to high-impedance scope CH2.
- Sweep range: 1–10 kHz; sweep time: 0.6 s.
- Carrier: Sine, 2 Vpp, 0 V offset.

Output was disabled before each configuration. Harmonic, Modulation, Burst, Combine, Noise Add, and Coupling were confirmed inactive. Once Sweep was enabled, only the managed acceptance script controlled output directly. Public `source.output` continues to reject Sweep ON by design; this evidence does not expose a product write capability.

## Protocol results

| Field or combination | Firmware result | Acceptance |
| --- | --- | --- |
| `SWMD` | LINE, LOG, and STEP read back | A3 |
| `DIR` | UP, DOWN, and UP_DOWN read back | A3 |
| `TRSR` | INT, MAN, and EXT read back | A3 |
| `TRMD` | ON/OFF read back | A3; trigger output unwired |
| `EDGE` | EXT RISE/FALL read back | A3; no physical external trigger |
| `EDGE` | Not returned for MAN | Not claimed |
| `MARK_STATE` / `MARK_FREQ` | Marker ON not returned | Not claimed |
| `STARTTIME` / `ENDTIME` / `BACKTIME` | Not returned after writes | Not claimed |
| `MTRIG` | One action sent and a sweep measured | A4 / T1 |

Missing fields were not interpreted as zero or OFF. EXT Edge and Trigger Out evidence proves configuration response only, not electrical behavior.

## Waveform results

Each combination collected 18 valid waveform snapshots and estimated each snapshot independently. A low-amplitude acquisition at a sweep wrap could be reacquired, while any measurement reaching 9 Vpp terminated the run.

| Mode | Direction | Measured frequency span | Measured Vpp |
| --- | --- | ---: | ---: |
| LINE | UP | 1.04–9.43 kHz | 2.16 V |
| LINE | DOWN | 1.87–9.43 kHz | 2.16–2.24 V |
| LOG | UP | 1.07–8.93 kHz | 2.16–2.24 V |
| LOG | DOWN | 1.15–9.62 kHz | 2.16–2.24 V |
| STEP | UP | 0.999–10.00 kHz | 2.16 V |
| LINE | UP_DOWN | 1.23–9.80 kHz | 2.16 V |
| LINE / MAN | UP | 0.997–8.55 kHz | 2.16–2.24 V |

LINE median frequency was approximately 5.2–6.0 kHz, while LOG was 2.8–3.6 kHz, consistent with different linear and logarithmic dwell distributions. STEP/UP had a median near 1 kHz, showing different endpoint dwell behavior; this pass proves the stepped span but does not invent an unreturned step count.

One `MTRIG` action produced a 0.997–8.55 kHz sweep and then returned to the start waiting state. This is software-trigger T1 evidence, not external physical-trigger T2.

## Transport audit and restoration

The formal pass used 72 queries and 87 writes. Every write was transmitted and completed, with zero unknown outcomes. It ended with both outputs OFF, both Sweep states OFF, CH2 restored to Sine / 1 kHz / 4 Vpp / 0 V, unchanged RTM2032 channel/probe/timebase/trigger snapshots, and no overload.

A separate fresh session reconfirmed both outputs OFF using 13 queries and zero writes.

## Coverage boundary

- The EXT trigger input and dedicated Trigger Out were unwired, so A5/T2 is not claimed.
- Marker, hold, and return-time fields do not read back on this firmware; no core fields were fabricated.
- Disabled Sweep hides its configuration. Acceptance restores a known safe baseline but does not claim restoration of unknown hidden parameters.
- Evidence applies only to the tested SDG2122X firmware.

