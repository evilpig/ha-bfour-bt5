"""Local target and stale-data alert signals; notification routing is optional."""
from datetime import datetime, timezone
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from .alert_entity import AlertEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(AlertSignal(entry.runtime_data.alerts, index, stale)
                       for index in range(entry.data["probe_count"]) for stale in (False, True))


class AlertSignal(AlertEntity, BinarySensorEntity):
    def __init__(self, manager, index, stale):
        self._stale = stale
        suffix, label = ("reading_stale", "Reading stale") if stale else ("target_reached", "Target reached")
        self._setup_alert(manager, index, suffix, label)
        self._attr_icon = "mdi:timer-alert" if stale else "mdi:thermometer-check"
        if stale:
            self._attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self):
        return self.probe.stale if self._stale else self.probe.target_reached

    @property
    def extra_state_attributes(self):
        unit = self.manager.entry.options.get("temperature_unit", self.hass.config.units.temperature_unit)
        def display(value):
            if value is None:
                return None
            return round(value * 9 / 5 + 32 if unit == "°F" else value, 1)
        return {
            "probe": self.index + 1, "armed": self.probe.armed,
            "temperature": display(self.probe.current_c),
            "target_temperature": display(self.probe.target_c), "temperature_unit": unit,
            "stale_minutes": self.manager.stale_seconds / 60,
            "last_valid_at": datetime.fromtimestamp(self.probe.last_valid_at, timezone.utc).isoformat()
                if self.probe.last_valid_at else None,
        }
