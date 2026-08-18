# WaveBench Core Impact Assessment for SDS3000

[中文](WAVEBENCH_CORE_RFC.md)

## Conclusion

The SDS3054 plugin completes M0–M6 without a WaveBench core change. VICP text and binary waveform operations passed hardware acceptance through the existing `PyVisaTransport` and `query_bin_block()`. Existing `acquire` effects already require `read_write` access for `scope.fetch_waveform` and `scope.capture_waveform(s)`.

This assessment proposes two additive RFCs and does not modify the sibling WaveBench repository. Both proposals apply to SIGLENT/LeCroy SDS3000, RIGOL DS1000Z, and Rohde & Schwarz RTM2000. The machine-readable impact matrix is [`wavebench-core-rfc.json`](wavebench-core-rfc.json).

## RFC 1: Scope configuration state and controlled patches

WaveBench currently exposes only the narrow, read-only `scope.channel_coupling` surface. All three drivers write vertical scale and timebase inside capture, but none has a generic public configuration contract:

| Driver | Existing fact | Current gap |
| --- | --- | --- |
| `siglent.sds3000` | Controlled capture uses `CPL/TRA/VDIV/TDIV/TRMD`; the manual also defines `OFST/TRSE/TRSL/TRCP/TRLV` | No termination or coupling setter; this acceptance required a manual CH1 change from 50 ohm to 1 Mohm |
| `rigol.ds1000z` | Internal `set_vertical_scale()` and `set_time_range()` methods exist; capture uses the current trigger | Setters are not capabilities and have no common snapshot, readback, or failure-restoration contract |
| `rohde-schwarz.rtm2032` | Complete analog/timebase/edge-trigger snapshots and internal setters exist, plus a CH2-specific trigger method | A CH2-specific method cannot be a generic API, and its failure latch is not a cross-driver contract |

Read and write capabilities should be separate:

```text
scope.analog_channel_state       -> get_analog_channel_state(channel)
scope.analog_channel_configure   -> patch_analog_channel(channel, patch)
scope.timebase_state             -> get_timebase_state()
scope.timebase_configure         -> patch_timebase(patch)
scope.edge_trigger_state         -> get_edge_trigger_state()
scope.edge_trigger_configure     -> patch_edge_trigger(patch)
```

Common analog fields should include `enabled`, `coupling`, `termination_ohm`, `scale_v_per_div`, `offset_v`, `bandwidth_limit_hz`, and `probe_ratio`. Timebase fields should include `scale_s_per_div`, `range_s`, `position_s`, and `reference`. Edge-trigger fields should include `source`, `mode`, `slope`, `coupling`, `level_v`, and `holdoff_s`.

Every state object needs `supported_fields`. A patch must use an explicit `UNSET` value for “do not modify”; `None` must not ambiguously mean “unchanged”, “automatic”, and “unknown”. Vendor tokens, SCPI strings, and VBS paths do not belong in public models.

Operation contract:

- State reads retain `stateful_read` and allow both access modes.
- Patches use `write` and require `read_write`; unsupported fields fail before I/O.
- Read every field that may change before the first write, perform exact readback, and restore in reverse order on failure.
- Never retry writes, `*OPC?`, or a request after any partial response.
- Restoration failure raises `StateDriftError` and latches the session against further writes until it is closed.
- Use the existing connection timeout and a separate operation-complete budget only when the vendor operation needs one.

This is additive. Existing `scope.channel_coupling` remains and can later become a compatibility view of `analog_channel_state`. Existing capture arguments and result models do not change. DS1000Z can expose fixed termination as read-only, while RTM2000 and SDS3000 can advertise writable support through `supported_fields`.

## RFC 2: Partially representable status models v2

The current `ScopeSnapshot` requires identity, health, analog channel, timebase, probe, waveform metadata, and a complete edge trigger. `ScopeAcquisitionStatus` also requires average and segmented-option fields.

RTM2000 can fill these models, but that does not justify fabricated fields in every scope. SDS3054 can safely read identity, coupling, trigger mode, and some waveform metadata. DS1000Z can read identity, coupling, and waveform state. Neither external plugin can honestly declare the all-or-nothing v1 snapshot.

Add versioned capabilities without relaxing v1 in place:

```text
scope.snapshot_v2
scope.acquisition_status_v2
```

Suggested models:

```text
ScopeSnapshotV2(
    components: Mapping[component_name, typed_component],
    unavailable: Mapping[component_name, unavailable_reason],
    complete: bool,
)

ScopeAcquisitionStatusV2(
    run_state,
    trigger_state?,
    average_count?,
    average_complete?,
    segmented_enabled?,
    segment_capacity?,
    segments_available?,
    supported_fields,
)
```

`unavailable_reason` must be a closed enum such as `unsupported`, `option_missing`, `not_configured`, `firmware_unverified`, or `query_failed`. It must not carry executable vendor text. A failed operation and an unavailable field remain distinct; defaults never impersonate device state.

Both operations use `stateful_read` and allow read-only access. Non-consuming queries may use the existing read retry policy; read-to-clear registers may not be replayed. Each component receives an explicit timeout. The v1 capabilities and types remain unchanged, so RTM2000 does not need to migrate. Deprecation, if any, is a later versioned decision rather than an `0.8.x` break.

## Core changes not recommended

- **VICP transport:** the existing PyVISA path works with the plugin-owned `PyVICP` dependency.
- **Waveform binary API:** `query_bin_block()` is sufficient for SDS3054 `WAVEDESC` and `DAT1`.
- **A new transactional effect:** `acquire` already requires `read_write`; restoration and failure-latch requirements should first be attached to concrete capability contracts.
- **An SDS3000 raw screenshot transport:** `SCDP` sends output to the configured hardcopy device, while `SCDP?` returns status rather than image bytes.
- **Dynamic descriptor probing:** descriptor loading remains zero-I/O; typed operations perform option checks and fail closed.

## Permanently rejected

Do not add arbitrary raw SCPI, arbitrary VBS, MAUI `app` reflection, caller-supplied restoration commands, or a transport handle that bypasses identity, access, and audit controls. The manual catalog is an audit ledger, not a command executor.

## If core implementation proceeds

Core work belongs on a separate conventionally named WaveBench branch with separate commits. Acceptance requires three-vendor FakeTransport contracts, zero-I/O rejection of unsupported fields, no write retry, exact readback, reverse restoration, restoration-failure latching, v1 regression coverage, and zero-I/O descriptor loading. The plugin raises its minimum WaveBench version only after a core release; this branch does not depend on unpublished interfaces.
