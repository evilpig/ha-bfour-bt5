"""Shared device ownership and local-alert change subscription."""
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.device_registry import DeviceInfo
from .const import DOMAIN


class AlertEntity:
    _attr_has_entity_name = True

    def _setup_alert(self, manager, index, suffix, label):
        self.manager = manager
        self.index = index
        self._attr_name = f"Probe {index + 1} {label}"
        self._attr_unique_id = f"{manager.entry.unique_id}_probe_{index + 1}_{suffix}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, manager.entry.unique_id)})

    @property
    def probe(self):
        return self.manager.probes[self.index]

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(
            self.hass, self.manager.signal, self.async_write_ha_state
        ))
