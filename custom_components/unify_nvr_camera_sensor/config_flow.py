import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import UnifyProtectAuthError, UnifyProtectClient
from .const import (
    CONF_CAMERA_NAMES,
    CONF_CAMERAS,
    CONF_GAP_THRESHOLD,
    CONF_NVR_HOST,
    CONF_PASSWORD,
    CONF_POLL_INTERVAL,
    CONF_USERNAME,
    DEFAULT_GAP_THRESHOLD,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _camera_options(cameras: list[dict]) -> list[dict]:
    options = []
    for cam in cameras:
        cam_id = cam.get("id")
        if not cam_id:
            _LOGGER.warning("Skipping camera record with missing id: %s", cam)
            continue
        options.append({"value": str(cam_id), "label": str(cam.get("name") or cam_id)})
    return options


def _camera_names_map(cameras: list[dict], selected_ids: list[str]) -> dict[str, str]:
    return {
        str(cam_id): str(cam.get("name") or cam_id)
        for cam in cameras
        if (cam_id := cam.get("id")) and cam_id in selected_ids
    }


def _cameras_schema(camera_options: list[dict], current_cameras: list[str], gap: int, poll: int) -> vol.Schema:
    return vol.Schema({
        vol.Required(CONF_CAMERAS, default=current_cameras): SelectSelector(
            SelectSelectorConfig(options=camera_options, multiple=True, mode=SelectSelectorMode.LIST)
        ),
        vol.Required(CONF_GAP_THRESHOLD, default=gap): NumberSelector(
            NumberSelectorConfig(min=1, max=60, step=1, mode=NumberSelectorMode.BOX, unit_of_measurement="min")
        ),
        vol.Required(CONF_POLL_INTERVAL, default=poll): NumberSelector(
            NumberSelectorConfig(min=10, max=3600, step=10, mode=NumberSelectorMode.BOX, unit_of_measurement="s")
        ),
    })


class UnifyNvrConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._host: str | None = None
        self._username: str | None = None
        self._password: str | None = None
        self._discovered_cameras: list[dict] = []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> "UnifyNvrOptionsFlow":
        return UnifyNvrOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            client = UnifyProtectClient(
                user_input[CONF_NVR_HOST],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            try:
                await client.connect()
                self._discovered_cameras = await client.get_cameras()

                if not self._discovered_cameras:
                    return self.async_abort(reason="no_cameras_found")

                await self.async_set_unique_id(user_input[CONF_NVR_HOST])
                self._abort_if_unique_id_configured()

                self._host = user_input[CONF_NVR_HOST]
                self._username = user_input[CONF_USERNAME]
                self._password = user_input[CONF_PASSWORD]
                return await self.async_step_cameras()
            except UnifyProtectAuthError as err:
                _LOGGER.warning("Authentication error for %s: %s", user_input[CONF_NVR_HOST], err)
                errors["base"] = "invalid_auth"
            except Exception as err:
                _LOGGER.exception("Unexpected error connecting to NVR %s", user_input[CONF_NVR_HOST])
                errors["base"] = "cannot_connect"
            finally:
                await client.close()

        schema = vol.Schema({
            vol.Required(CONF_NVR_HOST): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            vol.Required(CONF_USERNAME): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            vol.Required(CONF_PASSWORD): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
        })
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input or {}),
            errors=errors,
        )

    async def async_step_cameras(self, user_input=None):
        camera_options = _camera_options(self._discovered_cameras)
        _LOGGER.debug("Camera options for selection form: %s", camera_options)

        if user_input is not None:
            selected_ids: list[str] = user_input[CONF_CAMERAS]
            camera_names = _camera_names_map(self._discovered_cameras, selected_ids)
            _LOGGER.debug("Creating entry for cameras: %s", camera_names)
            return self.async_create_entry(
                title=f"Unify NVR ({self._host})",
                data={
                    CONF_NVR_HOST: self._host,
                    CONF_USERNAME: self._username,
                    CONF_PASSWORD: self._password,
                    CONF_CAMERAS: selected_ids,
                    CONF_CAMERA_NAMES: camera_names,
                    CONF_GAP_THRESHOLD: int(user_input[CONF_GAP_THRESHOLD]),
                    CONF_POLL_INTERVAL: int(user_input[CONF_POLL_INTERVAL]),
                },
            )

        return self.async_show_form(
            step_id="cameras",
            data_schema=_cameras_schema(camera_options, [], DEFAULT_GAP_THRESHOLD, DEFAULT_POLL_INTERVAL),
        )


class UnifyNvrOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry
        self._discovered_cameras: list[dict] = []

    async def async_step_init(self, user_input=None):
        if not self._discovered_cameras:
            client = UnifyProtectClient(
                self._entry.data[CONF_NVR_HOST],
                self._entry.data[CONF_USERNAME],
                self._entry.data[CONF_PASSWORD],
            )
            try:
                await client.connect()
                self._discovered_cameras = await client.get_cameras()
            except UnifyProtectAuthError:
                return self.async_abort(reason="invalid_auth")
            except Exception:
                _LOGGER.exception("Options flow: cannot connect to NVR")
                return self.async_abort(reason="cannot_connect")
            finally:
                await client.close()

        camera_options = _camera_options(self._discovered_cameras)
        current_cameras = self._entry.data.get(CONF_CAMERAS, [])
        current_gap = self._entry.data.get(CONF_GAP_THRESHOLD, DEFAULT_GAP_THRESHOLD)
        current_poll = self._entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)

        if user_input is not None:
            selected_ids: list[str] = user_input[CONF_CAMERAS]
            camera_names = _camera_names_map(self._discovered_cameras, selected_ids)
            new_data = {
                **self._entry.data,
                CONF_CAMERAS: selected_ids,
                CONF_CAMERA_NAMES: camera_names,
                CONF_GAP_THRESHOLD: int(user_input[CONF_GAP_THRESHOLD]),
                CONF_POLL_INTERVAL: int(user_input[CONF_POLL_INTERVAL]),
            }
            self.hass.config_entries.async_update_entry(self._entry, data=new_data)
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self._entry.entry_id)
            )
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=_cameras_schema(camera_options, current_cameras, current_gap, current_poll),
        )
