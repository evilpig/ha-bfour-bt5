"""Persistence and event-loop updates for local alert controls."""
from datetime import timedelta
from time import time, monotonic
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from .alert_state import ProbeAlerts
from .const import DOMAIN


class AlertManager:
    def __init__(self, hass, entry):
        self.hass = hass
        self.entry = entry
        self.signal = f"{DOMAIN}_{entry.entry_id}_alerts"
        self.stale_seconds = entry.options.get("stale_minutes", 5) * 60
        self.probes = [ProbeAlerts() for _ in range(entry.data["probe_count"])]
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.alerts")
        self._last_save = 0.0

    async def async_load(self):
        saved = await self.store.async_load() or {}
        for index, data in enumerate(saved.get("probes", [])):
            if index < len(self.probes) and isinstance(data, dict):
                self.probes[index] = ProbeAlerts.restore(data)
        self.tick()

    def start(self):
        self.entry.async_on_unload(async_track_time_interval(
            self.hass, self.tick, timedelta(seconds=15)
        ))

    def serialize(self):
        return {"probes": [probe.serialize() for probe in self.probes]}

    def save(self):
        self._last_save = monotonic()
        self.store.async_delay_save(self.serialize, 1)

    def changed(self):
        async_dispatcher_send(self.hass, self.signal)

    def tick(self, _now=None):
        before = [(x.target_reached, x.stale) for x in self.probes]
        for probe in self.probes:
            probe.evaluate(time(), self.stale_seconds)
        if before != [(x.target_reached, x.stale) for x in self.probes]:
            self.changed()
            self.save()

    def record(self, values):
        before = [(x.target_reached, x.stale) for x in self.probes]
        now = time()
        for probe, value in zip(self.probes, values, strict=True):
            probe.record(value, now, self.stale_seconds)
        after = [(x.target_reached, x.stale) for x in self.probes]
        if before != after:
            self.changed()
        # Coalesce timestamp persistence; never write storage for every BLE packet.
        if before != after or monotonic() - self._last_save >= 30:
            self.save()

    def mark_disconnected(self):
        for probe in self.probes:
            probe.current_c = None
        self.changed()

    def set_target(self, index, value):
        self.probes[index].set_target(value, time(), self.stale_seconds)
        self.changed()
        self.save()

    def set_armed(self, index, armed):
        self.probes[index].set_armed(armed, time(), self.stale_seconds)
        self.changed()
        self.save()
