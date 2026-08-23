# SDG2000X Source V2 A0 Offline Adapter Record

[中文](SDG2000X_SOURCE_V2_A0.md)

## Conclusion

Plugin version `0.8.2` declares `source.snapshot_v2`, `source.basic_configure_v2`, `source.output_v2`, and
`source.harmonics_disable_v2`. This record proves A0 offline contracts only: descriptor validation, query plans,
SCPI forms, send counts, core phase authorization, pre-write rejection, and injected-failure closeout use
fake transports. It is
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
- `source.harmonics_disable_v2` only disables an observed Harmonic state; it does not configure or enable
  Harmonic. It applies only to CH1/CH2 of an `SDG2122X` with firmware `2.01.01.39R7T2`, while Sine and
  target output OFF are proven. An already-disabled state sends no MAIN write; an enabled state sends only
  `C<n>:HARM HARMSTATE,OFF`, then the core independently reads Harmonic and output state.
- V2 MAIN sends one audited `BSWV`, `OUTP`, or `HARM` write. The core performs the independent postcondition
  snapshot.

Output enable still requires FIX mode, Sweep OFF, readable Vpp and Offset, high-impedance display load,
and inactive known advanced modes. Output disable does not depend on Vpp, Offset, or load information and
is available for one-step core recovery. After a readable Basic or Output postcondition mismatch, the core
attempts V2 OFF once. An ambiguous write that poisons the session sends no additional OFF, and an ambiguous
OFF is not retried.

## Query and Send Counts

Each anchor phase reads `*IDN?` once, then reads `OUTP?`, `BSWV?`, `SWWV?`, modulation, Burst, Harmonic
(Sine only), Combine, Noise Add, and Coupling for each channel. The Output and Harmonic facets reuse the
matching Basic snapshot and issue no extra `OUTP?` or `HARM?` query.

With both fixture channels set to Sine, a complete Source V2 snapshot performs 38 queries and zero writes,
below the descriptor limit of 44 queries. A0 tests also prove that Basic, Output, and Harmonic-disable MAIN writes issue no
driver query. The core validates the plan deadline and query budget after it receives the execution record;
that validation is not A1 evidence from a real device.

## Noise, DC, and V1 Compatibility

The current SDG2000X `BSWV?` form reports `STDEV` for Noise and may not report final Vpp and Offset for
Noise or DC. The adapter does not guess or convert those values into Vpp. These modes are therefore absent
from the current V2 Basic profile and cannot prove a V2 output-enable state.

The core retains the V1 `set_function` setter for legacy calls that cannot be represented losslessly: Sine
to Noise, and Noise/DC to a provable periodic waveform, continue through the existing output-OFF transaction.
Periodic requests fully represented by the V2 profile continue through V2. This routing does not add an RMS,
crest-factor, or statistical Noise safety model.

## Remaining Gates

- A1: confirm real V2 snapshot responses, budgets, and the Harmonic-state facet for an explicitly authorized
  model, firmware, resource, and transport/backend.
- A2: validate V2 Output ON/OFF, independent readback, and OFF recovery; also confirm V2 Basic command
  acceptance and readback form, plus Harmonic disable and readback on the exact runtime target.
- A3: use a scope loopback to confirm declared V2 Basic writes for frequency, Vpp, function, and duty
  cycle, recording offset, termination, tolerance, and the final OFF state.

Timeout, disconnection, and unknown-write fault injection are A0 contracts. Any real transport-fault
evidence requires a separate record and does not substitute for A1–A3.

Hardware testing requires separate authorization. Offline fixtures are not device-behavior evidence.
