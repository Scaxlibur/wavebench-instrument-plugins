# SDS3054 Hardware Acceptance

[中文](HARDWARE_ACCEPTANCE.md)

## Conclusion

SDS3054 firmware `8.4.1` passed controlled VICP text, binary waveform, single-acquisition, and same-acquisition dual-channel testing. DG4202 CH1 was connected to SDS3054 CH1 and CH2. The acceptance signal was a 1 kHz, 1 Vpp, 0 V offset sine wave with both scope inputs at 1 MΩ.

The machine-readable redacted evidence is [`hardware-acceptance.json`](hardware-acceptance.json). It contains summary metrics only, with no resource address, serial number, raw waveform, screenshot, command log, or restoration journal.

## Safety gate

The first preflight found scope CH1 at 50 Ω while the source was already enabled at the 5 Vpp ceiling. WaveBench immediately disabled the source. No waveform read or remote impedance change was attempted. After CH1 was manually changed to 1 MΩ, the source remained OFF and three consecutive checks reported `DCL` for both CH1 and CH2 before testing continued.

The complete source profile reported a high-impedance load. Before output was enabled, the procedure:

1. confirmed output OFF;
2. configured `SIN / 1 kHz / 1 Vpp` while preserving 0 V offset;
3. rechecked both scope inputs for high impedance;
4. enabled output and captured;
5. guaranteed output OFF before restoring the original profile on every exit path.

## M4: Waveform transfer

With the generator OFF, both CH1 and CH2 returned 100,002 points. Every transaction snapshotted `CHDR/CFMT/CORD/WFSU`, selected `DEF9,WORD,BIN`, low-byte-first, single-segment transfer, and restored the original values. A new session confirmed:

```text
CHDR  SHORT
CFMT  DEF9,BYTE,BIN
CORD  LO
WFSU  SP,0,NP,0,FP,0,SN,0
```

The current parser handled the real descriptor, 100,002-point payload, scaling, and time axis on both channels. No waveform array was retained.

## M5: Same-acquisition dual-channel capture

Each round executed one acquisition and then read CH1 and CH2 from that state. Limits were 1 kHz ±2%, 1 Vpp ±10%, no more than 5% channel Vpp difference, and normalized correlation of at least 0.98.

| Round | CH1 frequency | CH1 Vpp | CH2 frequency | CH2 Vpp | Vpp difference | Correlation |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 999.900 Hz | 1.013335 V | 1000.200 Hz | 1.006668 V | 0.6601% | 0.999946 |
| 2 | 1000.000 Hz | 1.013335 V | 1000.200 Hz | 1.006668 V | 0.6601% | 0.999946 |
| 3 | 1000.000 Hz | 1.013335 V | 1000.100 Hz | 1.006668 V | 0.6601% | 0.999947 |

Every channel returned 100,002 points with no quality warning. Each round audited 33 text queries, four binary queries, and 18 transactional state writes. All 18 writes completed, with zero blocked requests and zero binary writes. Trigger mode, timebase, both V/div settings, trace enable state, and transfer state were restored exactly after every round.

`scope.capture_waveform` delegates to the single-channel form of this transaction. The dual-channel `scope.capture_waveforms` path was exercised directly on hardware.

## Independent postcheck

A fresh read-only session verified the result instead of trusting the acceptance session itself:

- DG4202 output was OFF, with the prior 5 Vpp setting and complete channel profile restored.
- SDS3054 CH1 and CH2 were both `DCL`.
- Trigger mode was `AUTO` and timebase was `1E-3 S`.
- CH1 and CH2 were `360E-3 V` and `200E-3 V`, respectively.
- CH1 trace was ON and CH2 trace was OFF.
- `CHDR/CFMT/CORD/WFSU` matched the M4 values.
- The postcheck completed 13 queries and zero writes.

## Evidence boundary

This acceptance covers only SDS3054 firmware `8.4.1`, the current VICP path, and the six declared capabilities. It does not promote other models, options, Automation objects, or dangerous instructions from the 2026 rolling manual to supported hardware behavior.
