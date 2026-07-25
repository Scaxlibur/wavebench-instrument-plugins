from __future__ import annotations

from pathlib import Path

import pytest

from wavebench.errors import DataError
from wavebench_shengpu_sp3000a.trace_parser import SP30120TraceParser


EVIDENCE_DIR = (
    Path(__file__).resolve().parents[3]
    / "tool-of-rei"
    / "evidence"
    / "sp3000-m6"
)
TRUNCATED_EVIDENCE = (
    Path(__file__).resolve().parents[3]
    / "tool-of-rei"
    / "evidence"
    / "sp30120-m4"
    / "20260723-205918-baseline"
    / "012-curve-baseline.bin"
)


def test_all_trace_accepts_incremental_lf_terminated_frame() -> None:
    parser = SP30120TraceParser(mode="all", expected_points=3)

    assert parser.feed(b"-71.5,-70.0,") is None
    assert parser.feed(b"-69.25,0,1,-2\n") == parser.finish()
    frame = parser.finish()

    assert frame.amplitude == (-71.5, -70.0, -69.25)
    assert frame.phase == (0.0, 1.0, -2.0)
    assert frame.point_count == 3


def test_all_trace_accepts_local_501_point_hardware_evidence_if_available() -> None:
    evidence = EVIDENCE_DIR / "20260723T080101Z-outprform-initial.bin"
    if not evidence.exists():
        pytest.skip("private hardware evidence is not present")
    payload = evidence.read_bytes()
    parser = SP30120TraceParser(mode="all", expected_points=501)

    for offset in range(0, len(payload), 257):
        frame = parser.feed(payload[offset : offset + 257])

    assert frame is not None
    assert frame.point_count == 501
    assert frame.amplitude is not None
    assert frame.phase == (0.0,) * 501
    assert all(-80.0 < value < -60.0 for value in frame.amplitude)


def test_local_truncated_hardware_evidence_is_rejected_if_available() -> None:
    if not TRUNCATED_EVIDENCE.exists():
        pytest.skip("private truncated hardware evidence is not present")
    parser = SP30120TraceParser(mode="all", expected_points=501)

    assert parser.feed(TRUNCATED_EVIDENCE.read_bytes()) is None
    with pytest.raises(DataError, match="before the LF"):
        parser.finish()


@pytest.mark.parametrize(
    ("mode", "payload", "amplitude", "phase"),
    [
        ("amplitude", b"-72,-71\n", (-72.0, -71.0), None),
        ("phase", b"-180,180\r\n", None, (-180.0, 180.0)),
    ],
)
def test_single_quantity_trace_layout(
    mode: str,
    payload: bytes,
    amplitude: tuple[float, ...] | None,
    phase: tuple[float, ...] | None,
) -> None:
    frame = SP30120TraceParser(mode=mode, expected_points=2).feed(payload)

    assert frame is not None
    assert frame.amplitude == amplitude
    assert frame.phase == phase


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b"1,2,3\n", "expected 4, got 3"),
        (b"1,2,3,4,5\n", "expected 4, got 5"),
        (b"1,2,3,\n", "empty numeric token"),
        (b"1,2,nope,4\n", "token 2 is not numeric"),
        (b"1,2,nan,4\n", "token 2 must be finite"),
        (b"1,2,inf,4\n", "token 2 must be finite"),
        (b"1,2,3,4\nresidual", "bytes after the LF"),
        (b"1,2,3,\xff\n", "ASCII text only"),
    ],
)
def test_trace_rejects_malformed_frames(payload: bytes, message: str) -> None:
    parser = SP30120TraceParser(mode="all", expected_points=2)

    with pytest.raises(DataError, match=message):
        parser.feed(payload)


def test_trace_rejects_unterminated_frame() -> None:
    parser = SP30120TraceParser(mode="amplitude", expected_points=2)

    assert parser.feed(b"1,2") is None
    with pytest.raises(DataError, match="before the LF"):
        parser.finish()


def test_trace_enforces_byte_safety_limit() -> None:
    parser = SP30120TraceParser(
        mode="amplitude",
        expected_points=2,
        max_frame_bytes=4,
    )

    with pytest.raises(DataError, match="4 byte safety limit"):
        parser.feed(b"12345")


def test_trace_parser_is_single_use() -> None:
    parser = SP30120TraceParser(mode="amplitude", expected_points=1)
    assert parser.feed(b"1\n") is not None

    with pytest.raises(DataError, match="already completed"):
        parser.feed(b"2\n")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"mode": "unknown", "expected_points": 1},
        {"mode": "all", "expected_points": 0},
        {"mode": "all", "expected_points": 1, "max_frame_bytes": 0},
    ],
)
def test_trace_parser_validates_configuration(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        SP30120TraceParser(**kwargs)
