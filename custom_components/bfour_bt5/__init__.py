"""Read BFOUR Grill BT5.0 devices through Home Assistant Bluetooth proxies."""
from homeassistant.const import Platform
from homeassistant.components import bluetooth

from .coordinator import BFourCoordinator


async def async_setup_entry(hass, entry):
    coordinator = BFourCoordinator(hass, entry)
    # Keep entities and the reconnect button available even when the device is off.
    await coordinator.async_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR, Platform.BUTTON])
    entry.async_on_unload(bluetooth.async_register_callback(
        hass, coordinator.handle_advertisement,
        {"address": coordinator.address, "connectable": True},
        bluetooth.BluetoothScanningMode.PASSIVE,
    ))
    entry.async_on_unload(entry.add_update_listener(async_options_updated))
    return True


async def async_unload_entry(hass, entry):
    unloaded = await hass.config_entries.async_unload_platforms(entry, [Platform.SENSOR, Platform.BUTTON])
    if unloaded:
        await entry.runtime_data.async_shutdown()
    return unloaded


async def async_options_updated(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)
