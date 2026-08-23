# SDG2000X Source V2 A0 Offline Adapter Record

[中文](SDG2000X_SOURCE_V2_A0.md)

## Conclusion

Plugin version `0.8.1` declares `source.snapshot_v2`, `source.basic_configure_v2`, and
`source.output_v2`. This record proves A0 offline contracts only: descriptor validation, query plans,
SCPI forms, send counts, core phase authorization, and pre-write rejection use fake transports. It is
not Source V2 hardware acceptance for any model or firmware.

Existing SDG2122X V1 acceptance remains evidence for the legacy capabilities. It does not substitute
for Source V2 A1, A2, or A3.

## Implemented Scope

- `source.snapshot_v2` executes pure-read anchor/facet/anchor plans for CH1 and CH2, without selector
  or configuration writes.
- `source.basic_configure_v2` covers Sine, Square, Ramp, and Pulse function changes, frequency, Vpp,
  and square duty cycle. One request accepts one `SET` field. `offset_v` is rejected before I/O because
  no verified SCPI write evidence is registered.
- `source.output_v2` supports independent ON/OFF transitions for both physical outputs. Independent
  outputs may be ON together; this adapter has no global single-output restriction.
- V2 MAIN sends one audited `BSWV` or `OUTP` write. The core performs the independent postcondition
  snapshot.

Output enable still requires FIX mode, Sweep OFF, readable Vpp and Offset, high-impedance display load,
and inactive known advanced modes. Output disable does not depend on Vpp, Offset, or load information and
is available for one-step core recovery.

## Query and Send Counts

Each anchor phase reads `*IDN?` once, then reads `OUTP?`, `BSWV?`, `SWWV?`, modulation, Burst, Harmonic
(Sine only), Combine, Noise Add, and Coupling for each channel. The Output facet reuses the matching Basic
snapshot and issues no extra `OUTP?` query.

With both fixture channels set to Sine, a complete Source V2 snapshot performs 38 queries and zero writes,
below the descriptor limit of 42 queries. A0 tests also prove that Basic and Output MAIN writes issue no
driver query.

## Noise, DC, and V1 Compatibility

The current SDG2000X `BSWV?` form reports `STDEV` for Noise and may not report final Vpp and Offset for
Noise or DC. The adapter does not guess or convert those values into Vpp. These modes are therefore absent
from the current V2 Basic profile and cannot prove a V2 output-enable state.

The core retains the V1 `set_function` setter for legacy calls that cannot be represented losslessly: Sine
to Noise, and Noise/DC to a provable periodic waveform, continue through the existing output-OFF transaction.
Periodic requests fully represented by the V2 profile continue through V2. This routing does not add an RMS,
crest-factor, or statistical Noise safety model.

## Remaining Gates

- A1: confirm real V2 snapshot responses and budgets for an explicitly authorized model, firmware,
  resource, and transport/backend.
- A2: validate V2 Basic and Output command completion, readback, rejection branches, and recovery.
- A3: validate timeout, disconnection, unknown write outcome, and session health through core consumers.

Hardware testing requires separate authorization. Offline fixtures are not device-behavior evidence.
