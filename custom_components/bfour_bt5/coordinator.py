"""Proxy-aware reads with persistent and intermittent connection modes."""
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
STALE_NOTIFICATION_SECONDS = 30


class BFourCoordinator(DataUpdateCoordinator):
    """Publish at the configured cadence; optionally retain the BLE connection."""

    def __init__(self, hass, entry):
        # Existing entries retain their original intermittent/30-second behavior.
        self.mode = entry.options.get("connection_mode", "intermittent")
        default_interval = 5 if self.mode == "persistent" else 30
        self.interval = entry.options.get("update_interval", default_interval)
        super().__init__(hass, _LOGGER, name=DOMAIN, config_entry=entry,
                         update_interval=timedelta(seconds=self.interval))
        self.address = entry.data["address"]
        self.probe_count = entry.data["probe_count"]
        self.last_packet = None
        self._last_wake_attempt = 0.0
        self._wake_task = None
        self._client = None
        self._latest_temperatures = None
        self._last_notification_at = 0.0
        self._read_lock = asyncio.Lock()
        self._closing = False

    def handle_advertisement(self, service_info, change):
        """Wake when unavailable, without starting a connection for every packet."""
        if self._closing or self.last_update_success or monotonic() - service_info.time > 90:
            return
        if monotonic() - self._last_wake_attempt < 30:
            return
        if self._wake_task is not None and not self._wake_task.done():
            return
        self._last_wake_attempt = monotonic()
        self._wake_task = self.config_entry.async_create_background_task(
            self.hass, self.async_request_refresh(), "BFOUR reconnect"
        )

    async def _disconnect(self, client):
        """Release retained state before disconnecting to ignore intentional closure."""
        if client is self._client:
            self._client = None
            self._latest_temperatures = None
            self._last_notification_at = 0.0
        try:
            async with asyncio.timeout(10):
                await client.disconnect()
        except (BleakError, TimeoutError, OSError):
            _LOGGER.debug("Disconnect cleanup failed", exc_info=True)

    async def async_shutdown(self):
        """Release the connection on reload, removal, or Home Assistant shutdown."""
        self._closing = True
        await super().async_shutdown()
        async with self._read_lock:
            if self._client is not None:
                await self._disconnect(self._client)

    async def _async_update_data(self):
        async with self._read_lock:
            if self._closing:
                raise UpdateFailed("Thermometer integration is stopping")
            return await self._read()

    async def _read(self):
        persistent = self.mode == "persistent"
        if persistent and self._client is not None:
            if (self._client.is_connected and self._latest_temperatures is not None
                    and monotonic() - self._last_notification_at <= STALE_NOTIFICATION_SECONDS):
                return self._latest_temperatures
            # A live link with no recent valid temperature frame must not retain old values.
            await self._disconnect(self._client)

        info = bluetooth.async_last_service_info(self.hass, self.address, connectable=True)
        if info is None or monotonic() - info.time > 90:
            raise UpdateFailed("Thermometer is idle or not advertising; waiting for it to return")
        device = bluetooth.async_ble_device_from_address(self.hass, self.address, connectable=True)
        if device is None:
            raise UpdateFailed("Thermometer is not reachable through a connectable Bluetooth proxy")
        self.last_packet = None
        packet_received = asyncio.Event()
        result = None
        client = None
        keep_connection = False

        def receive(_characteristic, payload):
            nonlocal result
            # Ignore a late notification belonging to a disconnected persistent session.
            if persistent and self._client is not client:
                return
            self.last_packet = bytes(payload).hex()
            _LOGGER.debug("BT5 notification: %s", self.last_packet)
            try:
                result = parse_temperatures(bytes(payload), self.probe_count)
            except ValueError:
                return
            if persistent:
                self._latest_temperatures = result
                self._last_notification_at = monotonic()
            packet_received.set()

        def disconnected(disconnected_client):
            if persistent and disconnected_client is self._client:
                self._client = None
                self._latest_temperatures = None
                self._last_notification_at = 0.0
                packet_received.set()
                if not self._closing:
                    self.async_set_update_error(UpdateFailed("Thermometer disconnected; waiting to reconnect"))

        try:
            async with asyncio.timeout(55):
                client = await establish_connection(
                    BleakClientWithServiceCache, device, self.address,
                    disconnected_callback=disconnected, max_attempts=2,
                    ble_device_callback=lambda: bluetooth.async_ble_device_from_address(
                        self.hass, self.address, connectable=True
                    ),
                )
                if persistent:
                    self._client = client
                service = client.services.get_service(SERVICE_UUID)
                if service is None or service.get_characteristic(NOTIFY_UUID) is None:
                    raise UpdateFailed("Device does not expose the expected FFB0/FFB2 service")
                await client.start_notify(NOTIFY_UUID, receive)
                await packet_received.wait()
                if result is None or (persistent and (not client.is_connected or self._client is not client)):
                    raise UpdateFailed("Thermometer disconnected before a valid temperature arrived")
                keep_connection = persistent and not self._closing
            return result
        except (BleakError, TimeoutError, OSError) as err:
            raise UpdateFailed(
                f"Could not read temperatures. Disconnect BF Home and check proxy connections. "
                f"Last notification: {self.last_packet or 'none'}. {err}"
            ) from err
        finally:
            if client is not None and not keep_connection:
                await self._disconnect(client)
