"""Temperature entities for the configured probe channels."""
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(BFourSensor(entry.runtime_data, index, entry.options.get("temperature_unit"))
                       for index in range(entry.data["probe_count"]))


class BFourSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator, index, unit=None):
        super().__init__(coordinator)
        self.index = index
        if unit is not None:
            self._attr_suggested_unit_of_measurement = unit
        self._attr_name = f"Probe {index + 1}"
        self._attr_unique_id = f"{coordinator.address}_probe_{index + 1}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
            connections={(CONNECTION_BLUETOOTH, coordinator.address)},
            name="BFOUR Grill BT5.0", manufacturer="BFOUR", model="Grill BT5.0 family",
        )

    @property
    def native_value(self):
        if self.coordinator.data is None:
            return None
        return self.coordinator.data[self.index]
