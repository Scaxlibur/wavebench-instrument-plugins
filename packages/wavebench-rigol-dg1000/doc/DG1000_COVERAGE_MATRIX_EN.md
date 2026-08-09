# RIGOL DG1000 coverage matrix

[中文](DG1000_COVERAGE_MATRIX.md)

This document records the public boundary for `wavebench-rigol-dg1000` `0.1.0`. The default gate
uses FakeTransport tests, wheel checks, and managed-install lifecycle checks only. Hardware
acceptance must be separately authorized, and public records must contain sanitized conclusions
instead of real resources, serial numbers, waveforms, screenshots, or command logs.

## Model scope

| Model family | Command layout | Current status |
| --- | --- | --- |
| DG1022 / DG1022A | legacy `:CH2` suffix | Covered by FakeTransport; no completed hardware acceptance is claimed |
| DG1022Z / DG1032Z / DG1062Z | `:SOUR<n>:` prefix | Covered by FakeTransport; DG1032Z can be used for a future closed-loop hardware gate |
| DG1000 / DG1000Z compatible models | selected by recognized IDN | Unknown models fail closed |

## Capability boundary

| WaveBench capability | Status | Notes |
| --- | --- | --- |
| `source.idn` | Declared | `*IDN?` identity readback |
| `source.errors` | Declared | `SYST:ERR?` error queue |
| `source.status` | Declared | CH1/CH2 basic status: output, function, frequency, VPP, offset, phase, sweep, and square duty cycle |
| `source.set_frequency` | Declared | Fixed-frequency setting; sweep can be explicitly disabled by configuration |
| `source.set_function` | Declared | Basic function setting |
| `source.set_amplitude_vpp` | Declared | VPP amplitude setting |
| `source.set_square_duty_cycle` | Declared | Square duty-cycle setting |
| `source.output` | Declared | Explicit output switching |
| `source.harmonic_profile` / `source.harmonic_configure` | Not declared | DG1000 add / harmonic-superposition mode is outside the supported surface; when enabled, actual fundamental and harmonic outputs are likely different from configured values and inaccurate |
| `source.arbitrary_upload` | Not declared | Does not reuse the DG4000/DG4202 arbitrary-waveform upload path |
| modulation / burst / counter / full sweep profile | Not declared | Vendor menu features are not mapped to generic WaveBench capabilities |

## Acceptance rules

- capabilities describe implemented and tested behavior only;
- descriptor import must not connect to instruments, scan ports, or send SCPI;
- the factory must open the configured transport only through `DriverContext.open_transport()`;
- after write failures, do not automatically retry output switching, triggers, or data paths whose
  response has started being consumed;
- hardware acceptance should record recoverable state, external measurement evidence, and output-off
  checks, with public submissions sanitized.
