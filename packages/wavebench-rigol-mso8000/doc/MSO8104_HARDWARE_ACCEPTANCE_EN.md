# MSO8104 Controlled Hardware Acceptance

[中文](MSO8104_HARDWARE_ACCEPTANCE.md)

Acceptance date: 2026-08-24

## Scope

This record covers the first controlled check of RIGOL MSO8104 identity, input safety, and the waveform-binary path. It does not record real resource addresses, serial numbers, raw waveforms, screenshots, or complete command logs.

Devices and runtime:

- scope: RIGOL MSO8104, firmware `00.02.02`;
- source: Siglent SDG2122X, firmware `2.01.01.39R7T2`;
- core: WaveBench `0.8.24`;
- transport: LAN/PyVISA with zero read retries.

SDG CH1 was connected to MSO CH1 and SDG CH2 to MSO CH2. The reviewed source profile was Sine, `1 kHz`, `1 Vpp`, and `0 V` offset. Local safety configuration further constrained `max_source_vpp = 1.0` and port voltage to `-0.6 V` through `0.6 V`.

## Safety sequence and result

1. A read-only Source V2 snapshot found both channels at Sine, `1 kHz`, `1 Vpp`, `0 V`, High-Z display load, harmonic OFF, and output OFF.
2. Read-only scope status returned CH1=`DCL` and CH2=`ACL`; both are WaveBench high-impedance safety tokens.
3. Source V2 OFF was requested separately for CH1 and CH2. A fresh read-only snapshot independently confirmed both OFF, `consistent`, and `healthy`.
4. Only CH1 was briefly enabled; CH2 remained OFF. The outer cleanup requested CH1 OFF and CH2 OFF, then used a fresh read-only snapshot to confirm the final state.

Final verification was CH1 OFF, CH2 OFF, snapshot `consistent`, and session `healthy`. This run did not write scope input impedance, timebase, trigger, or autoscale settings.

## Hardware evidence obtained

- `scope.idn` strictly identified RIGOL MSO8104;
- `scope.channel_coupling` returned CH1=`DCL` and CH2=`ACL`;
- Source V2 dual-channel snapshot, OFF requests, and independent OFF readback completed;
- core preflight confirmed the safety limit, High-Z display load, and no active cross-channel relation before enable.

These results apply only to the stated model, firmware, LAN/PyVISA transport, and controlled procedure.

## Waveform blocker

With CH1 briefly enabled, the MSO returned a valid ten-field BYTE preamble for `1000` points with finite X/Y calibration. The subsequent `:WAVeform:DATA?` timed out after about `5 s` through the core `0.8.24` legacy binary path. Core marked synchronization `unproven`, poisoned the scope session, and correctly denied later waveform-transfer restore writes.

No payload, frequency, Vpp, X/Y conversion, or transfer-state restoration result was accepted. CH2, dual-channel, MAX, DMAX, and SINGLE hardware acceptance were not attempted. [RFC-0008](rfcs/0008-bounded-waveform-block-trailing-contract.md) records the missing core binary contract and the conditions for resuming acceptance.
