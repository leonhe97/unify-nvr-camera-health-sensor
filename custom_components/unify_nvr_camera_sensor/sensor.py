from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_CAMERA_NAMES, CONF_CAMERAS, DOMAIN
from .coordinator import UnifyNvrCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: UnifyNvrCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    camera_ids: list[str] = entry.data[CONF_CAMERAS]
    camera_names: dict[str, str] = entry.data.get(CONF_CAMERA_NAMES, {})

    async_add_entities([
        entity
        for cam_id in camera_ids
        for entity in (
            RecordingGapSensor(coordinator, cam_id, camera_names.get(cam_id, cam_id)),
            LastConfirmedRecordingSensor(coordinator, cam_id, camera_names.get(cam_id, cam_id)),
        )
    ])


class _BaseCameraSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: UnifyNvrCoordinator, camera_id: str, camera_name: str, key: str) -> None:
        super().__init__(coordinator)
        self._camera_id = camera_id
        self._camera_name = camera_name
        self._attr_unique_id = f"{camera_id}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._camera_id)},
            name=self._camera_name,
            manufacturer="Ubiquiti",
            model="UniFi Protect Camera",
        )

    @property
    def _camera_data(self) -> dict:
        return self.coordinator.data.get(self._camera_id, {}) if self.coordinator.data else {}


class RecordingGapSensor(_BaseCameraSensor):
    _attr_name = "Recording Gap"
    _attr_icon = "mdi:timer-alert-outline"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, camera_id, camera_name) -> None:
        super().__init__(coordinator, camera_id, camera_name, "recording_gap")

    @property
    def native_value(self) -> int | None:
        gap = self._camera_data.get("gap_minutes")
        return round(gap) if gap is not None else None

    @property
    def extra_state_attributes(self) -> dict:
        data = self._camera_data
        return {
            "last_check_had_recording": data.get("last_check_had_recording"),
            "last_check_time": data.get("last_check_time"),
        }


class LastConfirmedRecordingSensor(_BaseCameraSensor):
    _attr_name = "Last Confirmed Recording"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-check-outline"

    def __init__(self, coordinator, camera_id, camera_name) -> None:
        super().__init__(coordinator, camera_id, camera_name, "last_confirmed_recording")

    @property
    def native_value(self):
        return self._camera_data.get("last_confirmed_recording")
