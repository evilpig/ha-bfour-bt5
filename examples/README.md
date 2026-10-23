# Target selector and notification examples

These are optional Home Assistant examples. The integration only reads temperatures; it never writes an alarm or target to the base.

## 1. Create the helpers

Recommended: Settings → Devices & services → Helpers → Create helper.

- **Number**: name `BFOUR target temperature`, entity ID `input_number.bfour_target_temperature`, mode **Input field**, step 1. For Fahrenheit use 32–212 and unit °F; for Celsius use 0–100 and unit °C (BF-30 range).
- **Toggle**: name `BFOUR alert armed`, entity ID `input_boolean.bfour_alert_armed`. Leave it off until ready to start a cook.

The optional [helpers.yaml](helpers.yaml) shows the equivalent YAML. If you use it, merge its sections with your existing configuration rather than duplicating top-level keys, then check configuration and restart/reload as appropriate. Do not also create the same helpers in the UI.

**Keep the helper and probe in the same unit.** Number helpers do not automatically convert their values when you switch the probe from °F to °C. Adjust the helper's value, range, and unit yourself before re-arming.

## 2. Create the alert automation

Create one new automation, open **Edit in YAML**, and paste [target_alert.yaml](target_alert.yaml). Replace `notify.mobile_app_your_phone` with the actual notification action from your Home Assistant Companion app. Replace the sensor ID if your installation chose a different one. Save with the alert toggle off.

It uses state changes plus a native numeric condition because it must respond both to new readings and to changes to the target/arming helpers. No polling automation or temperature comparison template is needed.

The alert fires when the current temperature is **strictly above** the target. Equality alone does not fire it. It also checks immediately when you arm the alert or change the target. A currently unavailable/non-numeric sensor cannot satisfy the numeric condition. If the sensor reconnects above the target while the alert is still armed, it will notify; this is intentional so an armed cooking alert is not missed during a short disconnection.

After the notification action succeeds, the automation switches **Alert armed** off. This is a one-shot latch: it avoids repeated alerts when readings fluctuate or the sensor reconnects. Turn it back on for the next cook. If you leave it armed while the thermometer is off, it remains armed for its return. Home Assistant restores the toggle across restarts. Turn it off manually to cancel.

For a destination-independent test, replace the phone action with `persistent_notification.create` and keep the same title/message fields. The examples send no notification until you install and arm them; they have not been installed in your account by publishing this repository.

## 3. Add the dashboard controls

Add a **Manual** dashboard card and paste [dashboard.yaml](dashboard.yaml). Set the target, check the selected unit, then turn on **Alert armed**. This example does not cause the page to open automatically on a kiosk; it updates the sensor card on an already-open dashboard.

## Validation

Automation behavior depends on the actual helper IDs, selected units, and notification action in your installation. Test with a harmless target above the current room-temperature reading, then lower the target to confirm one notification and automatic disarming. Notifications depend on Home Assistant and the destination being available.
