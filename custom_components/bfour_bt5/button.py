"""Manual reconnect using the same proxy-aware reader as automatic updates."""
from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([BFourReconnectButton(entry.runtime_data)])


class BFourReconnectButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_name = "Reconnect"
    _attr_icon = "mdi:bluetooth-connect"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._attr_unique_id = f"{coordinator.address}_reconnect"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
            connections={(CONNECTION_BLUETOOTH, coordinator.address)},
        )

    async def async_press(self):
        await self.coordinator.async_request_refresh()
