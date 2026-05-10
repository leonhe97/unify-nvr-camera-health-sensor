import asyncio
import logging
from datetime import datetime, timedelta, timezone

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import UnifyProtectClient
from .const import CONF_GAP_THRESHOLD, DOMAIN

_LOGGER = logging.getLogger(__name__)


class UnifyNvrCoordinator(DataUpdateCoordinator):
    def __init__(
        self,
        hass: HomeAssistant,
        client: UnifyProtectClient,
        camera_ids: list[str],
        poll_interval: int,
        gap_threshold: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=poll_interval),
        )
        self._client = client
        self._camera_ids = camera_ids
        self._lookback_seconds = gap_threshold * 60
        # Persists between polls: last time each camera's recording was confirmed
        self._last_confirmed: dict[str, datetime] = {}

    async def _check_camera(self, camera_id: str) -> tuple[str, dict]:
        try:
            has_recording = await self._client.check_recording_at(
                camera_id, self._lookback_seconds
            )
            now = datetime.now(tz=timezone.utc)

            if has_recording:
                self._last_confirmed[camera_id] = now

            last_confirmed = self._last_confirmed.get(camera_id)
            gap_minutes = (
                (now - last_confirmed).total_seconds() / 60
                if last_confirmed is not None
                else None
            )
            return camera_id, {
                "last_confirmed_recording": last_confirmed,
                "gap_minutes": gap_minutes,
                "last_check_had_recording": has_recording,
                "last_check_time": now,
            }
        except Exception as err:
            _LOGGER.warning("Failed to check recording for camera %s: %s", camera_id, err)
            last_confirmed = self._last_confirmed.get(camera_id)
            return camera_id, {
                "last_confirmed_recording": last_confirmed,
                "gap_minutes": None,
                "last_check_had_recording": None,
                "last_check_time": datetime.now(tz=timezone.utc),
            }

    async def _async_update_data(self) -> dict[str, dict]:
        try:
            await self._client.refresh()
            _LOGGER.debug("Polling %d camera(s)", len(self._camera_ids))
            pairs = await asyncio.gather(
                *[self._check_camera(cam_id) for cam_id in self._camera_ids]
            )
            return dict(pairs)
        except Exception as err:
            raise UpdateFailed(f"Error fetching recording data: {err}") from err
