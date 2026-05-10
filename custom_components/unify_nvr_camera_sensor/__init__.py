import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

_LOGGER = logging.getLogger(__name__)

from .api import UnifyProtectAuthError, UnifyProtectClient, UnifyProtectConnectionError
from .const import (
    CONF_CAMERAS,
    CONF_GAP_THRESHOLD,
    CONF_NVR_HOST,
    CONF_PASSWORD,
    CONF_POLL_INTERVAL,
    CONF_USERNAME,
    DOMAIN,
)
from .coordinator import UnifyNvrCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = UnifyProtectClient(
        entry.data[CONF_NVR_HOST],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )
    _LOGGER.info("Setting up Unify NVR Camera Sensor for %s", entry.data[CONF_NVR_HOST])
    try:
        await client.connect()
    except UnifyProtectAuthError as err:
        await client.close()
        raise ConfigEntryNotReady("Authentication failed") from err
    except (UnifyProtectConnectionError, Exception) as err:
        await client.close()
        raise ConfigEntryNotReady("Cannot reach NVR") from err

    coordinator = UnifyNvrCoordinator(
        hass,
        client,
        entry.data[CONF_CAMERAS],
        entry.data[CONF_POLL_INTERVAL],
        entry.data[CONF_GAP_THRESHOLD],
    )
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await client.close()
        raise

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data["client"].close()
    return unload_ok
