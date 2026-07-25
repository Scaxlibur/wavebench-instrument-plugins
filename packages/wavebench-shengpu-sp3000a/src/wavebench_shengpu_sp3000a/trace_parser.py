from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal

from wavebench.errors import DataError


TraceMode = Literal["amplitude", "phase", "all"]


@dataclass(frozen=True)
class SP30120TraceFrame:
    amplitude: tuple[float, ...] | None
    phase: tuple[float, ...] | None

    @property
    def point_count(self) -> int:
        values = self.amplitude if self.amplitude is not None else self.phase
        assert values is not None
        return len(values)


class SP30120TraceParser:
    """Incrementally parse one ASCII comma-separated trace terminated by LF."""

    def __init__(
        self,
        *,
        mode: TraceMode,
        expected_points: int,
        max_frame_bytes: int | None = None,
    ) -> None:
        if mode not in {"amplitude", "phase", "all"}:
            raise ValueError("trace mode must be amplitude, phase, or all")
        if expected_points < 1:
            raise ValueError("expected_points must be >= 1")
        if max_frame_bytes is not None and max_frame_bytes < 1:
            raise ValueError("max_frame_bytes must be >= 1")
        self.mode = mode
        self.expected_points = expected_points
        self.expected_tokens = expected_points * (2 if mode == "all" else 1)
        self.max_frame_bytes = max_frame_bytes or max(128, self.expected_tokens * 32 + 1)
        self._buffer = bytearray()
        self._complete = False

    def feed(self, data: bytes) -> SP30120TraceFrame | None:
        if self._complete:
            raise DataError("SP30120 trace parser already completed a frame")
        if not data:
            return None
        if len(self._buffer) + len(data) > self.max_frame_bytes:
            raise DataError(
                f"SP30120 trace exceeded {self.max_frame_bytes} byte safety limit"
            )
        lf_index = data.find(b"\n")
        if lf_index < 0:
            self._buffer.extend(data)
            return None
        if lf_index != len(data) - 1:
            raise DataError("SP30120 trace has bytes after the LF frame terminator")
        self._buffer.extend(data[:-1])
        self._complete = True
        return self._parse_complete_frame()

    def finish(self) -> SP30120TraceFrame:
        if not self._complete:
            raise DataError("SP30120 trace ended before the LF frame terminator")
        return self._parse_complete_frame()

    def _parse_complete_frame(self) -> SP30120TraceFrame:
        try:
            payload = self._buffer.decode("ascii")
        except UnicodeDecodeError as exc:
            raise DataError("SP30120 trace must contain ASCII text only") from exc
        if payload.endswith("\r"):
            payload = payload[:-1]
        if not payload:
            raise DataError("SP30120 returned an empty trace frame")
        raw_tokens = payload.split(",")
        if any(not token.strip() for token in raw_tokens):
            raise DataError("SP30120 trace contains an empty numeric token")
        if len(raw_tokens) != self.expected_tokens:
            raise DataError(
                "SP30120 trace token count mismatch: "
                f"expected {self.expected_tokens}, got {len(raw_tokens)}"
            )
        values: list[float] = []
        for index, token in enumerate(raw_tokens):
            try:
                value = float(token)
            except ValueError as exc:
                raise DataError(
                    f"SP30120 trace token {index} is not numeric: {token!r}"
                ) from exc
            if not isfinite(value):
                raise DataError(f"SP30120 trace token {index} must be finite")
            values.append(value)
        if self.mode == "amplitude":
            return SP30120TraceFrame(amplitude=tuple(values), phase=None)
        if self.mode == "phase":
            return SP30120TraceFrame(amplitude=None, phase=tuple(values))
        return SP30120TraceFrame(
            amplitude=tuple(values[: self.expected_points]),
            phase=tuple(values[self.expected_points :]),
        )
