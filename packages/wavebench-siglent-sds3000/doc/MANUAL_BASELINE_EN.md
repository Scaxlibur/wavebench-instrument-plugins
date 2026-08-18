# SDS3000 Programming Manual Baseline

[中文](MANUAL_BASELINE.md)

## Conclusion

The current source is Teledyne LeCroy's February 2026 *Oscilloscopes Remote Control and Automation Manual*. It covers the MAUI/XStreamDSO remote-control system but is not specific to the SDS3054. The target instrument runs firmware `8.4.1`, while parts of the manual require `8.5.0.0+` or newer software. A documented entity therefore does not automatically count as supported by the instrument.

Explicitly documented entities form the completeness denominator. Offline protocol evidence and tiered hardware tests determine whether firmware `8.4.1` actually supports each entity. The machine-readable record is [`manual-baseline.json`](manual-baseline.json).

## Source and segmentation

The upload converter split one 411-page source into three PDFs. These ranges refer to source-PDF sequence pages, not printed manual pages.

| Segment | Source sequence pages | Pages | Bytes | SHA-256 |
| --- | --- | ---: | ---: | --- |
| `segment-001` | 1–200 | 200 | 2,588,943 | `1a035e879600ee75d1d381c1fe8e5c2bcffc09d3fbc0fa02d4db46d82d04af53` |
| `segment-002` | 201–400 | 200 | 914,888 | `bb316a51ccd76ff58f4aa6ecab68da6ef993086cfd605b6fdd7395501379edeb` |
| `segment-003` | 401–411 | 11 | 125,917 | `39dac5d034da11fe3df2d7d13a0ffd2edb48e8c05efda2ee023f1cd93dcda55f` |

Content continuity verifies the order: segment 1 ends at printed page `6-32`, segment 2 spans printed pages `6-33` through `7-198`, and segment 3 begins at `7-199` and ends at `7-208` followed by a blank trailing page.

The upload system regenerated all three PDFs with PDFium. Their file creation timestamps are conversion metadata, not the publication date or a vendor revision identifier.

## Device applicability boundary

| Field | Frozen value |
| --- | --- |
| Physical brand | SIGLENT |
| Chassis model | SDS3054 |
| Redacted remote identity | `LECROY,SDS3054,<serial>,8.4.1` |
| Protocol platform | Teledyne LeCroy MAUI/XStreamDSO |
| Initial support scope | SDS3054 only |

Entities without evidence on SDS3054 firmware `8.4.1` begin as `firmware-unverified`. Model-, option-, or platform-specific entities use `model-not-applicable` or `option-absent` as appropriate.

## Completeness denominator

The M1 audit covers:

1. all 164 rows in Part 7's “Commands and Queries by Short Form” table;
2. explicitly documented Part 4 Automation objects, actions, methods, and CVARs;
3. explicitly documented Part 5 Result Interface properties;
4. no additional CVARs that the manual mentions but does not enumerate.

Each entity requires a stable ID, manual location, read/write direction, parameters or response, version and option constraints, side effects, safety class, WaveBench mapping, and disposition. M1 requires reproducible totals, unique stable IDs, and zero unclassified entities.

The allowed dispositions are `implemented`, `planned`, `core-gap-rfc`, `firmware-unverified`, `option-absent`, `model-not-applicable`, and `unsafe-quarantined`.

Coverage means auditing and explicitly disposing every documented entity. It must never be achieved by exposing arbitrary SCPI or VBS execution.

## Read-only verification

With vendor material still under `doc/vendor-local/`, verify the baseline with:

```bash
find doc/vendor-local -type f -name '*_origin.pdf' -print0 \
  | sort -z \
  | xargs -0 sha256sum

find doc/vendor-local -type f -name '*_origin.pdf' -print0 \
  | sort -z \
  | xargs -0 -n1 pdfinfo
```

Vendor PDFs, conversion images, and full-text Markdown are excluded by the repository-level `.gitignore` and must not enter Git, wheels, or source distributions.
