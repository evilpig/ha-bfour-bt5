"""Discovery and manual setup for Grill BT5.0 thermometers."""
import re

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, SERVICE_UUID


class BFourConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1
    _address = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return BFourOptionsFlow()

    async def async_step_bluetooth(self, discovery_info):
        if SERVICE_UUID not in discovery_info.service_uuids:
            return self.async_abort(reason="unsupported_device")
        self._address = discovery_info.address.upper()
        await self.async_set_unique_id(self._address)
        self._abort_if_unique_id_configured()
        self.context["title_placeholders"] = {"name": "Grill BT5.0"}
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            address = user_input["address"].strip().upper()
            if re.fullmatch(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}", address) is None:
                errors["address"] = "invalid_address"
            else:
                await self.async_set_unique_id(address)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Grill BT5.0 {address[-5:]}",
                    data={"address": address, "probe_count": user_input["probe_count"]},
                    options={"connection_mode": "persistent", "update_interval": 5},
                )
        return self.async_show_form(
            step_id="user", errors=errors,
            data_schema=vol.Schema({
                vol.Required("address", default=self._address or ""): str,
                vol.Required("probe_count", default=1): vol.All(vol.Coerce(int), vol.Range(min=1, max=6)),
            }),
        )


class BFourOptionsFlow(OptionsFlow):
    """Change display units through HA's temperature entity options."""

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            unit = user_input["temperature_unit"]
            registry = er.async_get(self.hass)
            for entity in er.async_entries_for_config_entry(
                registry, self.config_entry.entry_id
            ):
                if entity.domain != "sensor" or entity.platform != DOMAIN:
                    continue
                options = dict(entity.options.get("sensor", {}))
                options["unit_of_measurement"] = unit
                registry.async_update_entity_options(entity.entity_id, "sensor", options)
            return self.async_create_entry(title="", data={
                **self.config_entry.options, "temperature_unit": unit,
                "connection_mode": user_input["connection_mode"],
                "update_interval": user_input["update_interval"],
            })
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("connection_mode", default=self.config_entry.options.get(
                    "connection_mode", "intermittent"
                )): vol.In({"persistent": "Persistent (stay connected)", "intermittent": "Intermittent (connect for each read)"}),
                vol.Required("update_interval", default=self.config_entry.options.get(
                    "update_interval", 30
                )): vol.All(vol.Coerce(int), vol.Range(min=5, max=300)),
                vol.Required("temperature_unit", default=self.config_entry.options.get(
                    "temperature_unit", self.hass.config.units.temperature_unit
                )): vol.In({"°C": "Celsius (°C)", "°F": "Fahrenheit (°F)"}),
            }),
        )
