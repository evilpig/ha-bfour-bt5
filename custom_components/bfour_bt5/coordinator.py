"""Bounded notification reads via HA's proxy-aware BLE device lookup."""
import asyncio
from datetime import timedelta
import logging
from time import monotonic

from bleak import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from homeassistant.components import bluetooth
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, NOTIFY_UUID, SERVICE_UUID
from .protocol import parse_temperatures

_LOGGER = logging.getLogger(__name__)


class BFourCoordinator(DataUpdateCoordinator):
    """Subscribe until one valid packet arrives, then release the proxy slot."""

    def __init__(self, hass, entry):
        super().__init__(hass, _LOGGER, name=DOMAIN, config_entry=entry,
                         update_interval=timedelta(seconds=30))
        self.address = entry.data["address"]
        self.probe_count = entry.data["probe_count"]
        self.last_packet = None
        self._last_wake_attempt = 0.0
        self._wake_task = None

    def handle_advertisement(self, service_info, change):
        """Wake on a fresh advertisement when unavailable, with bounded retries."""
        if self.last_update_success or monotonic() - service_info.time > 90:
            return
        if monotonic() - self._last_wake_attempt < 30:
            return
        if self._wake_task is not None and not self._wake_task.done():
            return
        self._last_wake_attempt = monotonic()
        self._wake_task = self.config_entry.async_create_background_task(
            self.hass, self.async_request_refresh(), "BFOUR reconnect"
        )

    async def _async_update_data(self):
        info = bluetooth.async_last_service_info(self.hass, self.address, connectable=True)
        if info is None or monotonic() - info.time > 90:
            raise UpdateFailed("Thermometer is idle or not advertising; waiting for it to return")
        self.last_packet = None
        device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if device is None:
            raise UpdateFailed("Thermometer is not reachable through a connectable Bluetooth proxy")
        packet_received = asyncio.Event()
        result = None

        def receive(_characteristic, payload):
            nonlocal result
            self.last_packet = bytes(payload).hex()
            _LOGGER.debug("BT5 notification: %s", self.last_packet)
            try:
                result = parse_temperatures(bytes(payload), self.probe_count)
            except ValueError:
                return
            packet_received.set()

        client = None
        try:
            async with asyncio.timeout(55):
                client = await establish_connection(
                    BleakClientWithServiceCache, device, self.address, max_attempts=2,
                    ble_device_callback=lambda: bluetooth.async_ble_device_from_address(
                        self.hass, self.address, connectable=True
                    ),
                )
                service = client.services.get_service(SERVICE_UUID)
                if service is None or service.get_characteristic(NOTIFY_UUID) is None:
                    raise UpdateFailed("Device does not expose the expected FFB0/FFB2 service")
                await client.start_notify(NOTIFY_UUID, receive)
                await packet_received.wait()
            return result
        except (BleakError, TimeoutError, OSError) as err:
            raise UpdateFailed(
                f"Could not read temperatures. Disconnect BF Home and check proxy connections. "
                f"Last notification: {self.last_packet or 'none'}. {err}"
            ) from err
        finally:
            if client is not None:
                try:
                    async with asyncio.timeout(10):
                        await client.disconnect()
                except (BleakError, TimeoutError, OSError):
                    _LOGGER.debug("Disconnect cleanup failed", exc_info=True)
