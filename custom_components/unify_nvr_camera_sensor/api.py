import logging
import time

from uiprotect import ProtectApiClient
from uiprotect.exceptions import NotAuthorized

_LOGGER = logging.getLogger(__name__)


class UnifyProtectAuthError(Exception):
    pass


class UnifyProtectConnectionError(Exception):
    pass


class UnifyProtectClient:
    def __init__(self, host: str, username: str, password: str, port: int = 443) -> None:
        self._api = ProtectApiClient(
            host=host,
            port=port,
            username=username,
            password=password,
            verify_ssl=False,
        )

    async def connect(self) -> None:
        try:
            await self._api.update()
            _LOGGER.info(
                "Connected to UniFi Protect NVR: %s",
                self._api.bootstrap.nvr.display_name,
            )
        except NotAuthorized as err:
            raise UnifyProtectAuthError("Authentication failed") from err
        except Exception as err:
            raise UnifyProtectConnectionError(f"Cannot connect to NVR: {err}") from err

    async def get_cameras(self) -> list[dict]:
        cameras = list(self._api.bootstrap.cameras.values())
        result = [
            {"id": cam.id, "name": cam.display_name or cam.id}
            for cam in cameras
        ]
        _LOGGER.debug(
            "Bootstrap returned %d camera(s): %s",
            len(result),
            [(c["id"], c["name"]) for c in result],
        )
        return result

    async def get_recording_snapshot_bytes(
        self, camera_id: str, lookback_seconds: int
    ) -> bytes | None:
        """Fetch raw recording-snapshot bytes from lookback_seconds ago."""
        ts = int((time.time() - lookback_seconds) * 1000)

        _LOGGER.debug(
            "Checking recording for camera %s at ts=%d (%ds ago)",
            camera_id,
            ts,
            lookback_seconds,
        )
        return await self._api.api_request_raw(
            f"cameras/{camera_id}/recording-snapshot",
            method="get",
            params={"ts": ts},
            raise_exception=False,
        )

    async def check_recording_at(self, camera_id: str, lookback_seconds: int) -> bool:
        """Return True if the camera has a recording from lookback_seconds ago."""
        result = await self.get_recording_snapshot_bytes(camera_id, lookback_seconds)
        has_recording = bool(result and len(result) > 0)
        _LOGGER.debug(
            "Camera %s recording %ds ago: %s (%d bytes)",
            camera_id,
            lookback_seconds,
            has_recording,
            len(result) if result else 0,
        )
        return has_recording

    async def refresh(self) -> None:
        """Re-fetch bootstrap to keep the session alive."""
        await self._api.update()
        _LOGGER.debug("Session refreshed")

    async def close(self) -> None:
        try:
            await self._api.close_session()
        except Exception:
            pass
