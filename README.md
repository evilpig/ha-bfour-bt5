# BFOUR Grill BT5.0 for Home Assistant

Read temperatures from connection-based BFOUR meat thermometers through Home Assistant Bluetooth adapters and proxies, including Kiosk Satellite. No cloud account or dedicated thermometer ESP32 is needed.

[![Add to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=evilpig&repository=ha-bfour-bt5&category=integration)

## Device compatibility

| Model | Status | Evidence / limitation |
| --- | --- | --- |
| BFOUR BF-30 | Tested | Actual FFB2 captures and live temperature readings through Kiosk Satellite; Celsius/Fahrenheit switching verified. Hardware revisions may differ. |
| BFOUR BF-5 | Candidate; not tested here | Published community work uses the same FFB0 service, FFB2 notification characteristic, and temperature layout. |
| BFOUR BF-60 | Candidate; not tested here | Published ESPHome work uses the same service, characteristic, and temperature layout. |
| BFOUR BF-20 / BF-40 | Unverified | Model names alone do not establish protocol compatibility. Confirm FFB0/FFB2 and matching captures before relying on readings. |
| BFOUR BF-70 / BF-80 | Not supported by this integration | Newer advertisement-based FFA0 protocol; see [danielholm/bfour-ble](https://github.com/danielholm/bfour-ble). |
| Other Grill BT5.0 devices | Unverified | Requires the protocol below, not just a matching name. |

The expected Bluetooth name is `Grill BT5.0`, service `FFB0`, and notification characteristic `FFB2`. Up to six channels can be configured. Their physical meaning depends on the model; do not assume an extra channel is an ambient sensor.

## Features

- Automatic Bluetooth discovery and manual address entry.
- Temperature sensors with 0.1-degree precision and missing-probe handling.
- Configure → Temperature unit: Celsius or Fahrenheit, using Home Assistant's built-in conversion. Existing entity IDs and history are retained.
- Read-only: no target, alarm, preset, or display-unit commands are sent to the thermometer.
- Automatic reconnection after a fresh advertisement, plus a **Reconnect** button on the device page.
- Choose **Persistent** (stay connected) or **Intermittent** (connect/read/disconnect).
- Editable update interval: **5–300 seconds**.

## Requirements

- Home Assistant **2026.10 or newer** (tested on 2026.10.2).
- Home Assistant Bluetooth integration and a working adapter or proxy supporting active device connections.
- For Kiosk Satellite: enable ESPHome, Bluetooth proxy, and **Allow device connections**; grant Android Nearby devices and Location permissions and keep Location enabled.
- Disconnect BF Home and Bluetooth inspection apps before use. They may compete for the thermometer's connection.

## Install with HACS

1. Click **Add to HACS** above. HACS must already be installed.
2. Alternatively, open HACS → Custom repositories, add `https://github.com/evilpig/ha-bfour-bt5`, and select **Integration**.
3. Download **BFOUR Grill BT5.0**, then restart Home Assistant.
4. Power on the base and wake the charged probe. Configure the discovered device, or use Settings → Devices & services → Add integration → **BFOUR Grill BT5.0**.
5. Enter your own Bluetooth address and number of channels (start with one for a single-probe BF-30).
6. Compare the reading with the physical display before relying on it.

This is a HACS **custom repository**, not an inclusion in HACS's default catalog.

### Manual install

Copy `custom_components/bfour_bt5` into `/config/custom_components/bfour_bt5`, then restart Home Assistant. No configuration.yaml changes are needed.

### Existing manual installation

The HACS package uses the same `bfour_bt5` domain and unique IDs. Back up the existing integration folder, add this repository in HACS, and download it over the manual copy. Keep the existing integration entry; do not create a duplicate. Restart Home Assistant after the download.

## Connection mode and update interval

Open Settings → Devices & services → BFOUR Grill BT5.0 → **Configure**:

| Setting | Behavior |
| --- | --- |
| Persistent | Holds a Bluetooth connection while the thermometer is on. Notifications refresh an in-memory latest value; Home Assistant publishes it at the selected interval. Uses one proxy connection slot. |
| Intermittent | Connects, receives a notification, and disconnects for each update. Releases the slot between reads. |
| Update interval | 5–300 seconds. In Persistent mode this controls publishing, not the thermometer's own notification rate. In Intermittent mode it controls the time between completed reads. |

New installations default to Persistent with a 5-second interval. Existing entries without these options keep Intermittent and 30 seconds until you change Configure. Switching mode or interval reloads only this integration and releases its previous connection; Home Assistant itself does not restart.

Persistent mode receives notifications about every 1.8 seconds on the tested BF-30. A detected disconnect marks the sensor unavailable immediately. If the link stays up but stops sending valid temperatures for more than 30 seconds, the next scheduled update drops the link and attempts recovery. With a long publishing interval, that silent-link detection can therefore take up to the interval. Unloading or disabling the integration also disconnects it. A connection uses a proxy slot and may block the vendor phone app. Battery impact has not been measured.

The **Reconnect** button requests an immediate update. In Persistent mode it uses a healthy live connection; it does not unnecessarily disconnect it.

## When the thermometer is normally off

The integration stays loaded while the thermometer is off, including when Home Assistant starts while it is off. Its temperature sensors show **unavailable**, rather than holding a misleading last temperature. There is no separate idle entity.

Home Assistant continues listening through its normal Bluetooth scanners. Once the last advertisement is more than **90 seconds** old (or no advertisement exists), the reader skips active connection attempts. A read in progress or an attempt against a recent cached advertisement may occur during that initial window.

When the thermometer advertises again, an advertisement callback requests a new read. Wake requests are rate-limited to one per **30 seconds**, and the configured update interval provides a fallback. Successful connection and notifications restore the temperature sensors automatically. If Home Assistant has never received a successful reading, they remain unavailable until that first read.

Press **Reconnect** on the device page for an immediate read request. This button uses the existing Bluetooth scanners; it does not restart Android's Bluetooth radio or force a new scan. If there is no recent advertisement it waits for the thermometer to return. No dashboard needs to be reloaded: a normal Home Assistant entity card updates when the sensor recovers.

Automatic recovery depends on the thermometer advertising, the proxy being reachable, available Bluetooth connection slots, and a functioning Android/adapter Bluetooth stack. The software cannot repair a stuck radio.

## Temperature units

Open Settings → Devices & services → BFOUR Grill BT5.0 → **Configure**. Choose Celsius or Fahrenheit. This applies a display unit to all temperature sensors owned by the entry and preserves other sensor options. You can subsequently override an individual sensor in its entity settings. The physical thermometer display is unchanged.

## Troubleshooting

### Android / Kiosk Satellite GATT error 133

This is a generic connection failure before temperature decoding. During testing, the kiosk returned 133 in both the proxy and nRF Connect; a full kiosk reboot restored direct connectivity and proxy reads. This is a diagnostic observation, not a guaranteed fix for all 133 errors.

1. Disconnect BF Home and nRF Connect on other devices.
2. Ensure the kiosk allows device connections and has a free slot.
3. Temporarily disable this integration and the kiosk proxy, then test with nRF Connect **on that kiosk**. Use **Connect**, not Bond; the tested BF-30 did not require bonding.
4. If the kiosk itself cannot connect, restart the kiosk and retest before changing the decoder.
5. Disconnect nRF Connect, restore the proxy, and re-enable the integration.

### Connected, but no temperatures

Enable debug logging on the integration. Share a redacted FFB2 notification packet, the model, and the corresponding display reading. Do not enable or write to DFU services. A notification read has a 55-second connection/read bound and up to 10 seconds of disconnect cleanup; initial recovery can therefore take longer than a poll interval.

## Protocol and limitations

Temperature frames start with `55 00`; consecutive big-endian unsigned 16-bit values start at byte 2, in Celsius tenths. `FFFF` means no probe. Zero is valid. Other reply types, truncated packets, and values above the implementation's broad 600°C protocol sanity bound are rejected. That bound is not a probe operating-temperature rating.

Negative-temperature encoding is not implemented. This integration does not set cooking targets or control the base's alarms. Home Assistant updates follow your configured interval; persistent notifications arrive independently at the device’s rate. Bluetooth behavior and channel layouts can vary across models and firmware.

## Target temperatures and alerts

Use native Home Assistant helpers and automations so you can pick any notification destination. See [the target selector, dashboard, and alert examples](examples/README.md). These examples are optional and are not installed by this integration. They do not write targets to the thermometer.

## Development

```sh
python3 -m unittest discover -s tests -v
```

Tests cover actual BF-30-shaped frames, malformed data, missing probes, idle suppression and recovery, persistent connection reuse and cleanup, advertisement debounce, connection failures, and cleanup. Transport tests use mocks and do not prove compatibility with untested hardware. GitHub Actions runs these tests and HACS validation.

## Credits

This is a new Python reader based on published protocol findings:

- [Community BF-5 work](https://community.home-assistant.io/t/recommendation-for-bbq-thermostat-that-can-work-with-ha/881720/38)
- [YordiDR's ESPHome BT5 component](https://github.com/YordiDR/esphome/tree/dev/esphome/components/bt5_thermometer)
- [wizbowes/BFour-ESPHome BF-60 work](https://github.com/wizbowes/BFour-ESPHome)
- [Kiosk Satellite Bluetooth proxy](https://kiosksatellite.com/docs/esphome/)

Not affiliated with BFOUR, Home Assistant, or Kiosk Satellite. MIT licensed.
