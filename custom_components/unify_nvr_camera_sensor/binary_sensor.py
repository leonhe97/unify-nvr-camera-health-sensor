from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_CAMERA_NAMES, CONF_CAMERAS, CONF_GAP_THRESHOLD, DOMAIN
from .coordinator import UnifyNvrCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: UnifyNvrCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    camera_ids: list[str] = entry.data[CONF_CAMERAS]
    camera_names: dict[str, str] = entry.data.get(CONF_CAMERA_NAMES, {})
    threshold: int = entry.data[CONF_GAP_THRESHOLD]

    async_add_entities([
        RecordingProblemSensor(coordinator, cam_id, camera_names.get(cam_id, cam_id), threshold)
        for cam_id in camera_ids
    ])


class RecordingProblemSensor(CoordinatorEntity, BinarySensorEntity):
    # is_on=True means there IS a problem (aligns with PROBLEM device class)
    _attr_has_entity_name = True
    _attr_name = "Recording Problem"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self,
        coordinator: UnifyNvrCoordinator,
        camera_id: str,
        camera_name: str,
        threshold: int,
    ) -> None:
        super().__init__(coordinator)
        self._camera_id = camera_id
        self._camera_name = camera_name
        self._threshold = threshold
        self._attr_unique_id = f"{camera_id}_recording_problem"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._camera_id)},
            name=self._camera_name,
            manufacturer="Ubiquiti",
            model="UniFi Protect Camera",
        )

    @property
    def is_on(self) -> bool | None:
        if not self.coordinator.data:
            return None
        data = self.coordinator.data.get(self._camera_id, {})
        gap = data.get("gap_minutes")
        if gap is None:
            return None
        return gap > self._threshold
