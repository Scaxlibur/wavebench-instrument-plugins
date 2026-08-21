# SDG2000X Read-only Arbitrary Probe Acceptance

[中文](SDG2000X_ARBITRARY_PROBE_ACCEPTANCE.md)

## Conclusion

On 2026-08-21, `source.arbitrary_probe` from `wavebench-siglent-sdg2000x` 0.8.0 completed dual-channel A1 hardware acceptance on one `SDG2122X` running firmware `2.01.01.39R7T2`. Core `SourceService` returned `ArbitraryQueryProbeResult` records for current selection, sample-rate mode, and the built-in catalog on CH1 and CH2. All three records per channel had `accepted=True`.

The formal pass used six queries and zero writes. Both outputs remained OFF. This capability never uploads, deletes, or overwrites a waveform and does not query the user catalog.

## Core interface mapping

The plugin exactly implements the core protocol:

```python
def probe_arbitrary_queries(
    self,
    channel: int,
) -> list[ArbitraryQueryProbeResult]: ...
```

Its fixed allowlist is:

| Label | Query | Purpose |
| --- | --- | --- |
| `current_selection` | `C<n>:ARWV?` | Current arbitrary index and name |
| `sample_rate_mode` | `C<n>:SRATE?` | DDS/TARB mode and available sample-rate fields |
| `builtin_catalog` | `STL? BUILDIN` | Built-in waveform catalog |

Callers cannot replace candidates, so the method is not a raw-SCPI escape hatch. SDG2000X has no confirmed usable error queue, therefore each result has an explicit empty `errors` list. A per-query failure is recorded in that result's `exception`, and probing continues.

## Hardware results

| Channel | Current selection | Sample-rate response | Built-in catalog |
| --- | --- | --- | --- |
| CH1 | INDEX and NAME present, 28 characters | DDS, 17 characters | 199 entries, 2692 characters |
| CH2 | INDEX and NAME present, 28 characters | DDS, 17 characters | 199 entries, 2692 characters |

The real catalog covered indices 0–198, totaling 199 entries. The E05C model table lists SDG2000X built-in indices as 2–198, while this instrument also returned indices 0 and 1. The plugin preserves the raw probe response and does not extrapolate the discrepancy to other models.

## Transport audit

The pass used `read_only` access:

- queries: 6;
- write requests: 0;
- transmitted writes: 0;
- completed writes: 0;
- unknown write outcomes: 0;
- instrument mutation writes: 0.

Public `source.status` reconfirmed both outputs OFF at the end.

## Offline verification

The 0.8.0 package suite reported `323 passed`, covering the core result type and descriptor capability, exact query order on both channels, continuation after one query exception, explicit empty errors without an error queue, pre-I/O rejection of invalid channels including `True` and `1.0`, and installed-wheel version/entry-point/capability checks.

## Coverage boundary

- `STL? USER` is not queried, avoiding user waveform names in default probe output.
- No `ARWV`, `SRATE`, `WVDT`, or filesystem write command is sent.
- Catalog presence does not prove A4 output behavior for every built-in waveform.
- Hardware evidence applies only to the tested SDG2122X firmware. SDG2042X/SDG2082X are enabled under the same documented query contract only.

