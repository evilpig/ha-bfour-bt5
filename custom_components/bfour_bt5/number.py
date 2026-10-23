"""Local target-temperature sliders; no commands are written to the base."""
from homeassistant.components.number import NumberEntity, NumberDeviceClass, NumberMode
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers import entity_registry as er
from .alert_entity import AlertEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(TargetTemperature(entry.runtime_data.alerts, index)
                       for index in range(entry.data["probe_count"]))


class TargetTemperature(AlertEntity, NumberEntity):
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = 0.0
    _attr_native_max_value = 300.0
    _attr_native_step = 0.1
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:thermometer-chevron-up"

    def __init__(self, manager, index):
        self._setup_alert(manager, index, "target_temperature", "Target temperature")

    @property
    def native_value(self):
        return self.probe.target_c

    async def async_set_native_value(self, value):
        self.manager.set_target(self.index, float(value))

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        unit = self.manager.entry.options.get("temperature_unit")
        registry = er.async_get(self.hass)
        entity = registry.async_get(self.entity_id)
        if unit and entity and not entity.options.get("number", {}).get("unit_of_measurement"):
            registry.async_update_entity_options(self.entity_id, "number", {
                **entity.options.get("number", {}), "unit_of_measurement": unit,
            })
