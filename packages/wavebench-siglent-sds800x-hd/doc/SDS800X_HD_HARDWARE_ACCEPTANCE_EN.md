# SDS800X HD Hardware Acceptance

[中文](SDS800X_HD_HARDWARE_ACCEPTANCE.md)

## Scope

On 2026-08-20, the current external plugin and WaveBench `0.8.22` completed a first
TCPIP/VXI-11 acceptance run on an SDS804X HD. A DG4202 CH1 drove scope CH1 and CH2 on the same
electrical node. Public evidence excludes instrument IPs, serial numbers, raw waveforms, and full
SCPI logs.

The run covered only declared capabilities: identity, CH1–CH4 coupling, and stopped,
non-sequence `DMAX` waveform fetch with `check_errors=False`. Screenshot, Autoset, capture, error
queue, sequence waveforms, and other undeclared capabilities were not tested.

## Instruments and baseline

| Instrument | Firmware | Baseline |
|---|---|---|
| SIGLENT SDS804X HD | `4.8.12.1.1.6.5` | Trigger `Trig'd`; sequence OFF; `500 us/div`; memory management AUTO; depth `100k` |
| RIGOL DG4202 | `00.01.14` | CH1 ON; SIN; `1 kHz`; `5 Vpp`; `0 V` offset; FIX; sweep OFF; High-Z/INFINITY load semantics |

The generator already provided a suitable signal, so the run sent it no configuration or output
writes. Scope CH1–CH4 coupling all read back as DC. CH1 and CH2 used `1×` probe factors and
`1 V/div` for waveform acceptance.

## Identity and gates

- The four-field IDN format, manufacturer, SDS804X HD model, 14-character ASCII serial, and
  firmware field passed. The serial remains only in temporary local logs.
- All four coupling queries returned `DC`.
- A running-state `fetch_waveform` call failed after `TRIGger:STATus?` returned `Trig'd`, with no
  waveform write or binary query.
- The harness used documented `:TRIGger:STOP` before a read and `:TRIGger:RUN` afterward. The
  driver itself sent no acquisition-control command.
- A managed path using a real `WaveBenchConfig` and `ScopeService.fetch_waveform(1)` also passed,
  returning the core `WaveformData` / `WaveformHeader`, `100000` points, and the same sample
  interval. It performed one identity query, one preamble binary query, and one data binary query.

## Real preamble difference

The SDS804X HD non-sequence preamble returned:

```text
read_frames = 0
sum_frames = 1
segment = -1
```

The initial parser incorrectly required `segment >= 0`, so the first read failed before data
transfer. Version `0.3.1` accepts this verified non-sequence signature and retains the manual's
`segment=1` form while rejecting other frame combinations.

The WORD preamble reported a 346-byte descriptor, WORD/LSB, `100000` points, `200000` data bytes,
16 ADC bits, a `50.000000584 ns` sample interval, and `MAXPoint=5000000`.

## CH1 and CH2 results

Both channels returned `100000` finite samples with matching headers and strictly increasing time
axes.

| Metric | CH1 | CH2 |
|---|---:|---:|
| FFT peak | `999.999988 Hz` | `999.999988 Hz` |
| Smoothed crossing frequency | `1000.0191 Hz` | `1000.0170 Hz` |
| Fitted `1 kHz` sine Vpp | `5.0280 V` | `5.0100 V` |
| Raw min/max Vpp | `5.1000 V` | `5.0292 V` |
| Mean | `-45.2 mV` | `-38.6 mV` |
| `1 kHz` fit correlation | `0.999932` | `0.999994` |

Direct CH1/CH2 correlation was `0.999997`, and fitted Vpp differed by about `0.36%`. Frequency,
amplitude, time-axis, and channel-consistency gates passed.

A raw zero-crossing estimator misclassified quantization and noise crossings near zero as MHz
content. Acceptance instead cross-checked an FFT, a 101-point smoothed crossing estimate, and a
fixed-frequency least-squares sine fit.

## Transfer restoration

The test preset a valid alternate state:

```text
SOURCE=C2, START=10, INTERVAL=2, POINT=1000, WIDTH=WORD, BYTEorder=MSB
```

Both a successful CH1 read and a locally injected post-transfer `RuntimeError` restored all six
fields exactly. The harness then restored and verified the pre-test
`C1 / 0 / 1 / 0 / BYTE / LSB` state. Restoration did not hide the injected primary error.

## Remaining gates

- The `100000`-point record was below `MAXPoint=5000000`, so hardware executed one `DATA?`; true
  multi-chunk concatenation still has only FakeTransport evidence.
- Documented `:ACQuire:MMANagement FMDepth`, `ACQ:MMAN FMD`, and `:ACQuire:MDEPth 10M` attempts
  left this firmware at `AUTO / 100k`. No undocumented variant was attempted. AUTO, `100k`, the
  original timebase, horizontal delay, and running state were restored.
- USBTMC, other SDS800X HD models, sequence-ON hardware gating, and a real multi-chunk record remain
  pending.
- A documented `:ACQuire:SEQuence ON` attempt while stopped still read back OFF on this firmware,
  so the sequence-ON driver gate was not reached. The harness restored OFF and running state and
  did not try an undocumented variant.

## Final state

DG4202 CH1 remained ON, SIN, `1 kHz`, `5 Vpp`, `0 V`, FIX, and sweep OFF. The SDS804X HD returned
to running, sequence OFF, AUTO memory management, `100k` depth, `500 us/div`, and waveform transfer
`C1 / 0 / 1 / 0 / BYTE / LSB`. Sensitive evidence remained outside the repository.
