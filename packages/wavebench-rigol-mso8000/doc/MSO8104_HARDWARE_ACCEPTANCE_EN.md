# MSO8104 Controlled Hardware Acceptance

[中文](MSO8104_HARDWARE_ACCEPTANCE.md)

Acceptance dates: 2026-08-24 through 2026-08-25

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
4. CH1 and CH2 were each enabled only briefly in separate runs. After every waveform transaction, the outer cleanup requested the enabled channel OFF and used a fresh read-only snapshot to confirm CH1 and CH2 were both OFF.

Final verification was CH1 OFF, CH2 OFF, snapshot `consistent`, and session `healthy`. This run did not write scope input impedance, timebase, trigger, or autoscale settings.

## Hardware evidence obtained

- `scope.idn` strictly identified RIGOL MSO8104;
- `scope.channel_coupling` returned CH1=`DCL` and CH2=`ACL`;
- `scope.channel_input_state_v2` returned `dc + high_z + 1 MΩ` for both CH1 and CH2;
- Source V2 dual-channel snapshot, OFF requests, and independent OFF readback completed;
- core preflight confirmed the safety limit, High-Z display load, and no active cross-channel relation before enable.

These results apply only to the stated model, firmware, LAN/PyVISA transport, and controlled procedure.

## Limited waveform acceptance

The earlier core `0.8.24` legacy binary path timed out after about `5 s` at `:WAVeform:DATA?`. Synchronization was therefore `unproven`, and the scope session was correctly marked `poisoned` under the fail-closed rule. That historical result is not payload, frequency, Vpp, or restoration evidence.

The current core worktree implements the standard waveform bounded-binary contract. An empty trailing profile safely rejects the extra post-payload byte with `binary_transport_trailing_error`; with exact `LF` trailing, core restores and freshly verifies the five `source`, `mode`, `format`, `points`, and `window` fields.

After confirming SDG CH1 to MSO CH1 and SDG CH2 to MSO CH2, separate short source runs used the `1 kHz / 1 Vpp / 0 V` profile:

- CH1 returned `1000` samples from `-2.5 ms` to `2.495 ms` at `5 µs` spacing, with a `1.05713 Vpp / 1000 Hz` summary;
- CH2 returned `1000` samples from `-2.5 ms` to `2.495 ms` at `5 µs` spacing, with a `1.0705 Vpp / 999.167 Hz` summary.

After each read, EXIT cleanup disabled the enabled source channel and a fresh Source V2 snapshot confirmed CH1 and CH2 OFF, `consistent`, and `healthy`.

## Portability V2 read-only follow-up

With both source outputs OFF, `scope.channel_input_state_v2` successfully read independent coupling, termination, and impedance for CH1 and CH2. This step did not write input settings.

`scope.cursor_readout_v2` accepts only a preconfigured global manual `TIME/AMPL` cursor and never moves or reconfigures it. The device returned `VBA`; the driver correctly rejected before any value query, so this is not cursor-readout acceptance. The final source snapshot again confirmed both outputs OFF, `consistent`, and `healthy`.

## Acceptance boundary and next conditions

This record covers only the current-screen `DEF + LF`, 1000-point path for the stated model, firmware, transport, and source condition. It is not general X/Y-conversion or measurement-accuracy evidence across ranges, timebases, or probe conditions.

`MAX`, `DMAX`, `SINGLE`, `scope.capture_waveform`, and `scope.capture_waveforms` have no hardware acceptance from this work and remain default denied. Advancing them requires their own bounded profile, acquisition-state recovery, offline fault contracts, and a separate low-voltage hardware procedure; each step must still begin with both source outputs OFF.
