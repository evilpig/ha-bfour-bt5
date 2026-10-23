"""Dependency-free protocol and mocked transport tests.

Transport tests exercise our control flow, not HA or Android interoperability.
Run: python3 -m unittest discover -s tests -v
"""
import asyncio
import importlib.util
from time import monotonic
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock

BASE = Path(__file__).resolve().parents[1] / "custom_components/bfour_bt5"
package = types.ModuleType("bt5_test")
package.__path__ = [str(BASE)]
sys.modules["bt5_test"] = package
from bt5_test.protocol import parse_temperatures


class ProtocolTests(unittest.TestCase):
    def test_decimal_and_byte_order(self):
        self.assertEqual(parse_temperatures(bytes.fromhex("550000f00190"), 2), (24.0, 40.0))
        self.assertEqual(parse_temperatures(bytes.fromhex("55000101"), 1), (25.7,))

    def test_missing_probe_and_zero(self):
        self.assertEqual(parse_temperatures(bytes.fromhex("5500ffff0000"), 2), (None, 0.0))

    def test_six_channels(self):
        packet = b"\x55\x00" + b"\x01\x01" * 6
        self.assertEqual(parse_temperatures(packet, 6), (25.7,) * 6)

    def test_rejects_truncated_wrong_type_and_impossible_values(self):
        for packet in (b"", bytes.fromhex("550000"), bytes.fromhex("55010101"), bytes.fromhex("5500fffe")):
            with self.subTest(packet=packet), self.assertRaises(ValueError):
                parse_temperatures(packet, 1)

    def test_ignores_trailing_fields(self):
        self.assertEqual(parse_temperatures(bytes.fromhex("550000f00a0000"), 1), (24.0,))

    def test_captured_bf30_frame(self):
        self.assertEqual(parse_temperatures(bytes.fromhex("5500010dffffffffffffffffffffff"), 6),
                         (26.9, None, None, None, None, None))

    def test_invalid_channel_counts(self):
        for count in (0, 7):
            with self.assertRaises(ValueError):
                parse_temperatures(bytes.fromhex("55000101"), count)


def stub_module(name, **values):
    module = types.ModuleType(name)
    module.__dict__.update(values)
    sys.modules[name] = module
    return module


class BleakError(Exception):
    pass


class UpdateFailed(Exception):
    pass


class CoordinatorStub:
    def __init__(self, hass, *args, **kwargs):
        self.hass = hass
        self.config_entry = kwargs.get("config_entry")
        self.last_update_success = True

    def async_set_update_error(self, error):
        self.last_update_success = False

    async def async_shutdown(self):
        pass


stub_module("bleak", BleakError=BleakError)
connector = stub_module("bleak_retry_connector", BleakClientWithServiceCache=object,
                        establish_connection=AsyncMock())
stub_module("homeassistant")
stub_module("homeassistant.components")
bt = stub_module("homeassistant.components.bluetooth",
                 async_ble_device_from_address=lambda *a, **kw: object())
stub_module("homeassistant.helpers")
stub_module("homeassistant.helpers.update_coordinator",
            DataUpdateCoordinator=CoordinatorStub, UpdateFailed=UpdateFailed)
from bt5_test.coordinator import BFourCoordinator


class TransportTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.reader = BFourCoordinator(object(), types.SimpleNamespace(options={}, data={
            "address": "AA:BB:CC:DD:EE:FF", "probe_count": 1}))
        bt.async_ble_device_from_address = lambda *a, **kw: object()
        bt.async_last_service_info = lambda *a, **kw: types.SimpleNamespace(time=monotonic())
        service = types.SimpleNamespace(get_characteristic=lambda uuid: object())
        self.client = types.SimpleNamespace(
            services=types.SimpleNamespace(get_service=lambda uuid: service),
            start_notify=AsyncMock(), disconnect=AsyncMock(), is_connected=True)
        connector.establish_connection.reset_mock(side_effect=True)
        connector.establish_connection.return_value = self.client

    async def test_reads_valid_packet_after_ignoring_config_reply(self):
        async def notify(uuid, callback):
            callback(None, bytes.fromhex("55010101"))
            callback(None, bytes.fromhex("55000101"))
        self.client.start_notify.side_effect = notify
        self.assertEqual(await self.reader._async_update_data(), (25.7,))
        self.client.disconnect.assert_awaited_once()

    async def test_missing_proxy_fails_without_connecting(self):
        bt.async_ble_device_from_address = lambda *a, **kw: None
        with self.assertRaises(UpdateFailed):
            await self.reader._async_update_data()
        connector.establish_connection.assert_not_awaited()

    async def test_missing_service_disconnects(self):
        self.client.services.get_service = lambda uuid: None
        with self.assertRaises(UpdateFailed):
            await self.reader._async_update_data()
        self.client.disconnect.assert_awaited_once()

    async def test_notification_error_disconnects(self):
        self.client.start_notify.side_effect = BleakError("test failure")
        with self.assertRaises(UpdateFailed):
            await self.reader._async_update_data()
        self.client.disconnect.assert_awaited_once()

    async def test_cancellation_disconnects(self):
        subscribed = asyncio.Event()
        async def notify(*args):
            subscribed.set()
        self.client.start_notify.side_effect = notify
        task = asyncio.create_task(self.reader._async_update_data())
        await subscribed.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.client.disconnect.assert_awaited_once()

    async def test_idle_skips_connection_then_recovers(self):
        bt.async_last_service_info = lambda *a, **kw: types.SimpleNamespace(time=monotonic() - 91)
        with self.assertRaises(UpdateFailed):
            await self.reader._async_update_data()
        connector.establish_connection.assert_not_awaited()
        bt.async_last_service_info = lambda *a, **kw: types.SimpleNamespace(time=monotonic())
        async def notify(uuid, callback):
            callback(None, bytes.fromhex("5500010d"))
        self.client.start_notify.side_effect = notify
        self.assertEqual(await self.reader._async_update_data(), (26.9,))

    async def test_never_seen_device_skips_connection(self):
        bt.async_last_service_info = lambda *a, **kw: None
        with self.assertRaises(UpdateFailed):
            await self.reader._async_update_data()
        connector.establish_connection.assert_not_awaited()

    async def test_advertisements_debounce_wake_requests(self):
        self.reader.last_update_success = False
        refresh = AsyncMock()
        self.reader.async_request_refresh = refresh
        tasks = []
        def create_task(hass, coro, name):
            task = asyncio.create_task(coro)
            tasks.append(task)
            return task
        self.reader.config_entry.async_create_background_task = create_task
        info = types.SimpleNamespace(time=monotonic())
        self.reader.handle_advertisement(info, None)
        self.reader.handle_advertisement(info, None)
        await asyncio.gather(*tasks)
        refresh.assert_awaited_once()

    async def test_persistent_reuses_link_and_publishes_latest_frame(self):
        self.reader.mode = "persistent"
        callbacks = []
        async def notify(uuid, callback):
            callbacks.append(callback)
            callback(None, bytes.fromhex("5500010d"))
        self.client.start_notify.side_effect = notify
        self.assertEqual(await self.reader._async_update_data(), (26.9,))
        self.client.disconnect.assert_not_awaited()
        callbacks[0](None, bytes.fromhex("5500010e"))
        self.assertEqual(await self.reader._async_update_data(), (27.0,))
        self.assertEqual(connector.establish_connection.await_count, 1)
        self.assertEqual(self.client.start_notify.await_count, 1)
        await self.reader.async_shutdown()
        self.client.disconnect.assert_awaited_once()

    async def test_persistent_disconnect_invalidates_immediately(self):
        self.reader.mode = "persistent"
        async def notify(uuid, callback):
            callback(None, bytes.fromhex("5500010d"))
        self.client.start_notify.side_effect = notify
        await self.reader._async_update_data()
        callback = connector.establish_connection.call_args.kwargs["disconnected_callback"]
        self.client.is_connected = False
        callback(self.client)
        self.assertIsNone(self.reader._client)
        self.assertIsNone(self.reader._latest_temperatures)
        self.assertFalse(self.reader.last_update_success)

    async def test_persistent_stale_notifications_release_slot(self):
        self.reader.mode = "persistent"
        self.reader._client = self.client
        self.reader._latest_temperatures = (26.9,)
        self.reader._last_notification_at = monotonic() - 31
        bt.async_last_service_info = lambda *a, **kw: None
        with self.assertRaises(UpdateFailed):
            await self.reader._async_update_data()
        self.client.disconnect.assert_awaited_once()
        self.assertIsNone(self.reader._latest_temperatures)

    async def test_persistent_failed_subscription_releases_slot(self):
        self.reader.mode = "persistent"
        self.client.start_notify.side_effect = BleakError("test failure")
        with self.assertRaises(UpdateFailed):
            await self.reader._async_update_data()
        self.client.disconnect.assert_awaited_once()
        self.assertIsNone(self.reader._client)

    async def test_persistent_cancellation_releases_slot(self):
        self.reader.mode = "persistent"
        subscribed = asyncio.Event()
        async def notify(*args):
            subscribed.set()
        self.client.start_notify.side_effect = notify
        task = asyncio.create_task(self.reader._async_update_data())
        await subscribed.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.client.disconnect.assert_awaited_once()
        self.assertIsNone(self.reader._client)

    async def test_configured_interval(self):
        reader = BFourCoordinator(object(), types.SimpleNamespace(options={
            "connection_mode": "persistent", "update_interval": 12,
        }, data={"address": "AA:BB:CC:DD:EE:FF", "probe_count": 1}))
        self.assertEqual(reader.mode, "persistent")
        self.assertEqual(reader.interval, 12)

    async def test_connect_failure(self):
        connector.establish_connection.side_effect = BleakError("unreachable")
        with self.assertRaises(UpdateFailed):
            await self.reader._async_update_data()
        self.client.disconnect.assert_not_awaited()


class SetupTests(unittest.IsolatedAsyncioTestCase):
    async def test_offline_start_still_loads_sensor_and_reconnect_button(self):
        from unittest.mock import patch
        stub_module("homeassistant.const", Platform=types.SimpleNamespace(SENSOR="sensor", BUTTON="button"))
        bt.BluetoothScanningMode = types.SimpleNamespace(PASSIVE="passive")
        unsubscribed = []
        bt.async_register_callback = lambda *a, **kw: lambda: unsubscribed.append(True)
        spec = importlib.util.spec_from_file_location("bt5_test.lifecycle", BASE / "__init__.py")
        spec.submodule_search_locations = None
        lifecycle = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lifecycle)
        reader = types.SimpleNamespace(async_refresh=AsyncMock(), address="AA:BB:CC:DD:EE:FF",
                                       handle_advertisement=lambda *a: None)
        forward = AsyncMock()
        hass = types.SimpleNamespace(config_entries=types.SimpleNamespace(async_forward_entry_setups=forward))
        unload_callbacks = []
        entry = types.SimpleNamespace(async_on_unload=unload_callbacks.append,
                                      add_update_listener=lambda callback: lambda: None)
        with patch.object(lifecycle, "BFourCoordinator", return_value=reader):
            self.assertTrue(await lifecycle.async_setup_entry(hass, entry))
        self.assertIs(entry.runtime_data, reader)
        forward.assert_awaited_once_with(entry, ["sensor", "button"])
        self.assertEqual(len(unload_callbacks), 2)
        unload_callbacks[0]()
        self.assertEqual(unsubscribed, [True])


if __name__ == "__main__":
    unittest.main()
