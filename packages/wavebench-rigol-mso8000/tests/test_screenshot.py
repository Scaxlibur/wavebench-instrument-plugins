from __future__ import annotations

import zlib

import pytest

from wavebench.errors import ConfigError, DataError
from wavebench.instruments.scope_extensions import ScopeScreenshotRequest
from wavebench.services.scope_extension_service import ScopeExtensionService
from wavebench.transport.contracts import (
    BinaryQueryResult,
    BinaryResponseFraming,
    ReplayPolicy,
)
from wavebench.transport.guarded import GuardedAuditedTransport
from wavebench.transport.session import SessionHealth
from wavebench_rigol_mso8000 import descriptor as plugin_descriptor
from wavebench_rigol_mso8000.driver import MSO8104Scope


def _png(width: int = 2, height: int = 3) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        crc = zlib.crc32(kind + payload) & 0xFFFFFFFF
        return len(payload).to_bytes(4, "big") + kind + payload + crc.to_bytes(4, "big")

    ihdr = width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00"
    rows = b"".join(b"\x00" + b"\x00" * (width * 3) for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


class ScreenshotBackend:
    resource = "TCPIP::192.0.2.10::INSTR"
    _wavebench_binary_budget_parameters = True

    def __init__(self, *, image_type: str = "PNG", payload: bytes | None = None) -> None:
        self.image_type = image_type
        self.payload = _png() if payload is None else payload
        self.queries: list[tuple[str, ReplayPolicy]] = []
        self.writes: list[str] = []
        self.binary_requests: list[
            tuple[str, BinaryResponseFraming, int, ReplayPolicy, bytes, int]
        ] = []
        self.transport_trailing = b"\n"
        self.close_calls = 0

    def record_event(self, direction: str, text: str) -> None:
        del direction, text

    def query(
        self,
        command: str,
        *,
        replay: ReplayPolicy = ReplayPolicy.NO_REPLAY,
    ) -> str:
        self.queries.append((command, replay))
        if command == "*IDN?":
            return "RIGOL TECHNOLOGIES,MSO8104,MSO8A000000000,00.02.02"
        if command == ":SAVE:IMAGe:TYPE?":
            return self.image_type
        raise AssertionError(f"unexpected text query: {command}")

    def query_binary(
        self,
        command: str,
        *,
        framing: BinaryResponseFraming,
        max_bytes: int,
        timeout_ms: int | None = None,
        replay: ReplayPolicy = ReplayPolicy.NO_REPLAY,
        _transport_trailing: bytes = b"",
        _resynchronization_max_bytes: int = 0,
    ) -> BinaryQueryResult:
        del timeout_ms
        self.binary_requests.append(
            (
                command,
                framing,
                max_bytes,
                replay,
                _transport_trailing,
                _resynchronization_max_bytes,
            )
        )
        assert len(self.payload) <= max_bytes
        actual_trailing = _transport_trailing or self.transport_trailing
        header_bytes = 2 + len(str(len(self.payload)))
        return BinaryQueryResult(
            data=self.payload,
            framing=framing,
            declared_length=len(self.payload),
            framing_header_bytes=header_bytes,
            consumed_bytes=header_bytes + len(self.payload) + len(actual_trailing),
            transport_trailing_bytes=actual_trailing,
        )

    def query_float_list(
        self,
        command: str,
        *,
        timeout_ms: int | None = None,
        replay: ReplayPolicy = ReplayPolicy.NO_REPLAY,
    ) -> list[float]:
        del command, timeout_ms, replay
        raise AssertionError("unexpected float query")

    def query_bin_block(
        self,
        command: str,
        *,
        replay: ReplayPolicy = ReplayPolicy.NO_REPLAY,
    ) -> bytes:
        del command, replay
        raise AssertionError("legacy binary query is forbidden")

    def query_opc(
        self,
        *,
        replay: ReplayPolicy = ReplayPolicy.NO_REPLAY,
    ) -> str:
        del replay
        raise AssertionError("unexpected OPC query")

    def write(self, command: str) -> None:
        self.writes.append(command)

    def write_bytes(self, command: bytes) -> None:
        del command
        raise AssertionError("unexpected binary write")

    def close(self) -> None:
        self.close_calls += 1


def _service(backend: ScreenshotBackend) -> tuple[ScopeExtensionService, GuardedAuditedTransport]:
    transport = GuardedAuditedTransport(backend)
    return (
        ScopeExtensionService(
            driver=MSO8104Scope(transport=transport),
            descriptor=plugin_descriptor(),
            session_state=transport.session_state,
            connection_timeout_ms=1_000,
        ),
        transport,
    )


def test_screenshot_profile_requires_preconfigured_png_without_binary_io() -> None:
    backend = ScreenshotBackend(image_type="JPEG")
    scope = MSO8104Scope(transport=backend)

    with pytest.raises(ConfigError, match="PNG image type"):
        scope.get_screenshot_profile()

    assert backend.queries == [(":SAVE:IMAGe:TYPE?", ReplayPolicy.NO_REPLAY)]
    assert backend.binary_requests == []
    assert backend.writes == []


def test_screenshot_v2_uses_one_bounded_definite_block_without_writes() -> None:
    backend = ScreenshotBackend()
    service, transport = _service(backend)

    result = service.screenshot_v2(ScopeScreenshotRequest())
    screenshot = result.value

    assert screenshot.media_type == "image/png"
    assert (screenshot.width_px, screenshot.height_px) == (2, 3)
    assert screenshot.data == backend.payload
    assert backend.queries == [
        ("*IDN?", ReplayPolicy.NO_REPLAY),
        (":SAVE:IMAGe:TYPE?", ReplayPolicy.NO_REPLAY),
    ]
    assert backend.binary_requests == [
        (
            ":SAVE:IMAGe:DATA?",
            BinaryResponseFraming.DEFINITE_BLOCK,
            524_288,
            ReplayPolicy.NO_REPLAY,
            b"\n",
            0,
        )
    ]
    assert backend.writes == []
    assert transport.session_state.health is SessionHealth.HEALTHY


@pytest.mark.parametrize(
    ("image_type", "expected_exception"),
    [("JPEG", ConfigError), ("WEBP", DataError)],
)
def test_screenshot_v2_rejects_unusable_image_type_before_binary_query(
    image_type: str,
    expected_exception: type[Exception],
) -> None:
    backend = ScreenshotBackend(image_type=image_type)
    service, _ = _service(backend)

    with pytest.raises(expected_exception):
        service.screenshot_v2(ScopeScreenshotRequest())

    assert backend.binary_requests == []
    assert backend.writes == []


@pytest.mark.parametrize(
    "payload",
    [b"", b"not-a-png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 16],
)
def test_screenshot_v2_rejects_invalid_png_without_replay(payload: bytes) -> None:
    backend = ScreenshotBackend(payload=payload)
    service, transport = _service(backend)

    with pytest.raises(DataError, match="PNG"):
        service.screenshot_v2(ScopeScreenshotRequest())

    assert len(backend.binary_requests) == 1
    assert backend.writes == []
    assert transport.session_state.health is SessionHealth.HEALTHY


def test_screenshot_direct_driver_rejects_unexpected_transport_trailing() -> None:
    backend = ScreenshotBackend()
    backend.transport_trailing = b"\r\n"
    scope = MSO8104Scope(transport=backend)

    with pytest.raises(DataError, match="transport trailing"):
        scope.capture_screenshot(ScopeScreenshotRequest(), baseline=None)

    assert len(backend.binary_requests) == 1
    assert backend.writes == []
