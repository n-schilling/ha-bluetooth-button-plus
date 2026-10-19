# Bluetooth Button Plus for Home Assistant

[![CI](https://github.com/n-schilling/ha-bluetooth-button-plus/actions/workflows/ci.yaml/badge.svg?branch=main)](https://github.com/n-schilling/ha-bluetooth-button-plus/actions/workflows/ci.yaml)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![HACS: custom](https://img.shields.io/badge/HACS-custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories)

A custom integration that puts the buzzer of a Shelly BLU button into Home Assistant: the button *Buzz* that buzzes for a number of seconds, *Start buzzer* and *Stop buzzer*, the numbers *Buzzer volume* and *Buzz duration*, and the action `buzz`. Useful to find a button that is attached to something that wanders, such as a dog's harness or a key ring.

It complements the integrations that already read the button: [BTHome](https://www.home-assistant.io/integrations/bthome/) for the presses and the battery, [Bermuda](https://github.com/agittins/bermuda) for the room and the distance. Neither of them writes to the button; this one does nothing else. This project is not affiliated with or endorsed by Shelly.

## How it works

Shelly BLU buttons have a Bluetooth characteristic *Find my device*. Writing a 1 to it starts the buzzer, a 0 stops it, and the button stops it by itself after a minute. The characteristic is writable only over a **bonded** connection, so the button has to be paired with the Bluetooth adapter of Home Assistant once, see [Pairing](#pairing).

A press of *Start buzzer* connects to the button, writes the volume and the 1 and disconnects right away; the button is a battery device and advertises only while nothing is connected. *Stop buzzer* does the same with a 0. The action `buzz` starts the buzzer the same way and stops it after the duration, in the background.

## Supported devices

| Device | Status |
|---|---|
| Shelly BLU Button Tough 1 ZB (SBBT-102C) | Tested |
| Other Shelly BLU buttons (`SBBT-*`) with a buzzer | Offered, not tested |

The buzzer characteristic is documented for the BLU Button1 and the BLU Button Tough 1 as well. During setup the integration connects once and refuses a device without the characteristic. If a button works for you that is not listed as tested, please open an [issue](https://github.com/n-schilling/ha-bluetooth-button-plus/issues).

## Requirements

- Home Assistant 2026.10 or newer.
- The Bluetooth adapter of the Home Assistant machine, in range of the button. The bond lives in the Bluetooth stack of that machine, so only its own adapter can write to the button; the integration prefers it whenever several adapters see the button. Bluetooth proxies do not help: Shelly devices as proxies only forward advertisements and cannot connect, and an [ESPHome proxy](https://esphome.io/components/bluetooth_proxy.html) has no way to pair with the button, so a connection through it is refused.
- The button paired with that adapter, see below.

The buttons and the volume are available only while an adapter that can connect sees the button. Out of range, they are *unavailable*, and Home Assistant skips a press or the action for an unavailable entity: an automation goes on, and the log notes that the entity is unavailable. Only in the short gap between the last advertisement and the moment Home Assistant marks the button unavailable does a press fail with a message of its own.

## Pairing

Home Assistant itself cannot pair Bluetooth devices. On a Linux host (Home Assistant OS, Supervised, Container) pair once with `bluetoothctl`; the bond is stored by BlueZ and survives restarts. On Home Assistant OS, `bluetoothctl` runs on the host, reachable through the [SSH access to the host](https://developers.home-assistant.io/docs/operating-system/debugging/) on port 22222.

1. Put the button into pairing mode: four quick presses, or hold it for ten seconds, until it plays a short tone. Pairing mode lasts one minute.
2. On the host, within that minute:

    ```
    bluetoothctl
    agent off
    agent NoInputNoOutput
    default-agent
    pair AA:BB:CC:DD:EE:FF
    ```

    `Pairing successful` is the answer you want. With the button's *Security* (passkey) off, no code is asked for. If the first attempt answers `ConnectionAttemptFailed`, the button was not in pairing mode yet; try again.
3. `info AA:BB:CC:DD:EE:FF` shows `Paired: yes` and `Bonded: yes`.

A Shelly BLU button remembers four paired devices; a fifth replaces the one used least. The Shelly app on your phone is one of them.

The buzzer has to be enabled in the Shelly app (*Buzzer* in the device settings), and *Beacon mode* keeps the button advertising often enough to be found.

## Installation

1. In HACS: **⋮ → Custom repositories**, add `https://github.com/n-schilling/ha-bluetooth-button-plus` as type **Integration**.
2. Install **Bluetooth Button Plus** and restart Home Assistant.
3. A paired button in range is discovered and shown under **Settings → Devices & services**; confirm it. Or add one by hand: **Add integration → Bluetooth Button Plus** and pick the button from the list of buttons an adapter currently sees.

During setup the integration connects once to the button. That checks the pairing: a button that is not paired refuses the connection, and the setup says so.

## Entities

| Entity | Description |
|---|---|
| Buzz (`button`) | Buzzes for the *Buzz duration* at the *Buzzer volume*: connects, writes the volume and the 1, disconnects, and stops the buzzer after the time in the background. |
| Start buzzer (`button`) | Connects, writes the buzzer volume, starts the buzzer and disconnects. The button stops the buzzer by itself after a minute. |
| Stop buzzer (`button`) | Stops the buzzer before that, and drops a pending stop of the action `buzz`. |
| Buzz duration (`number`, configuration) | Seconds the *Buzz* button and the action without `duration` buzz, 1–60 (default 10). Kept in Home Assistant, the button has no such setting, so it can be set while the button is away. |
| Buzzer volume (`number`, configuration) | 0 off, 1 low, 2 medium, 3 high. Written to the button when set and applied before every start of the buzzer. The button cannot be asked for its volume without a connection, so a volume changed in the Shelly app is not shown here; it is overwritten at the next start. |

Both settings are kept in the integration's configuration, so they survive a restart and a disabled entity. All entities but *Buzz duration* are *unavailable* while no adapter that can connect sees the button.

## Action

`bluetooth_button_plus.buzz` starts the buzzer and stops it after a time. The call returns once the buzzer started; the stop runs in the background. A new buzz replaces a pending stop, *Stop buzzer* ends it early.

| Field | Default | Description |
|---|---|---|
| `duration` | the buzz duration | Seconds until the buzzer is stopped, 1–60, for this one buzz only. |
| `volume` | the buzzer volume | 0–3 for this one buzz only. |

Target: the *Buzz* button, or its device.

## Example

A script that makes the button buzz loudly for five seconds:

```yaml
sequence:
  - action: bluetooth_button_plus.buzz
    target:
      entity_id: button.sbbt_102c_ee01_buzz
    data:
      duration: 5
      volume: 3
```

## Limitations

- Range: only the adapter that is bonded with the button can trigger the buzzer, and only while it sees the button. Bluetooth proxies do not help, see [Requirements](#requirements).
- The bond lives in BlueZ on the host. A new Bluetooth adapter, or a reinstalled host, needs a new pairing.
- Nothing is read from the button; its presses and its battery come from BTHome, its position from Bermuda. The volume is the value Home Assistant set last, not the button's.

## Privacy

The integration stores the Bluetooth address and the model name of each button in its config entry. It sends nothing anywhere else.

## Development

```
python -m venv .venv && .venv/bin/pip install -r requirements_test.txt
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/mypy custom_components
.venv/bin/pytest --cov=custom_components.bluetooth_button_plus --cov-report=term-missing
```

## License

Apache License 2.0, see [LICENSE](LICENSE).
