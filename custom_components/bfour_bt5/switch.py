"""Explicit per-probe cooking-alert arming."""
from homeassistant.components.switch import SwitchEntity
from .alert_entity import AlertEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(ArmAlerts(entry.runtime_data.alerts, index)
                       for index in range(entry.data["probe_count"]))


class ArmAlerts(AlertEntity, SwitchEntity):
    _attr_icon = "mdi:bell-check"

    def __init__(self, manager, index):
        self._setup_alert(manager, index, "arm_alerts", "Arm alerts")

    @property
    def is_on(self):
        return self.probe.armed

    async def async_turn_on(self, **kwargs):
        self.manager.set_armed(self.index, True)

    async def async_turn_off(self, **kwargs):
        self.manager.set_armed(self.index, False)
