"""Temperature entities for the configured probe channels."""
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfTemperature, EntityCategory
from datetime import datetime, timezone
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    entities = []
    for index in range(entry.data["probe_count"]):
        entities.append(BFourSensor(entry.runtime_data, index, entry.options.get("temperature_unit")))
        entities.append(LastValidTemperature(entry.runtime_data, index))
    async_add_entities(entities)


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


class LastValidTemperature(CoordinatorEntity, SensorEntity):
    """Time of actual valid data, not of a repeated/cached state publication."""
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, index):
        super().__init__(coordinator)
        self.index = index
        self._attr_name = f"Probe {index + 1} Last valid temperature"
        self._attr_unique_id = f"{coordinator.address}_probe_{index + 1}_last_valid_temperature"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, coordinator.address)})

    @property
    def available(self):
        return True

    @property
    def native_value(self):
        stamp = self.coordinator.alerts.probes[self.index].last_valid_at
        return datetime.fromtimestamp(stamp, timezone.utc) if stamp is not None else None
