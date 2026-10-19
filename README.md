# Bluetooth Button Plus for Home Assistant

[![CI](https://github.com/n-schilling/ha-bluetooth-button-plus/actions/workflows/ci.yaml/badge.svg?branch=main)](https://github.com/n-schilling/ha-bluetooth-button-plus/actions/workflows/ci.yaml)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![HACS: custom](https://img.shields.io/badge/HACS-custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories)

A custom integration that puts the buzzer of a Shelly BLU button into Home Assistant: two buttons, *Start buzzer* and *Stop buzzer*. Useful to find a button that is attached to something that wanders, such as a dog's harness or a key ring.

It complements the integrations that already read the button: [BTHome](https://www.home-assistant.io/integrations/bthome/) for the presses and the battery, [Bermuda](https://github.com/agittins/bermuda) for the room and the distance. Neither of them writes to the button; this one does nothing else. This project is not affiliated with or endorsed by Shelly.

## How it works

Shelly BLU buttons have a Bluetooth characteristic *Find my device*. Writing a 1 to it starts the buzzer, a 0 stops it, and the button stops it by itself after a minute. The characteristic is writable only over a **bonded** connection, so the button has to be paired with the Bluetooth adapter of Home Assistant once, see [Pairing](#pairing).

A press of *Start buzzer* connects to the button, writes the 1 and disconnects right away; the button is a battery device and advertises only while nothing is connected. *Stop buzzer* does the same with a 0.

## Supported devices

| Device | Status |
|---|---|
| Shelly BLU Button Tough 1 ZB (SBBT-102C) | Tested |
| Other Shelly BLU buttons (`SBBT-*`) with a buzzer | Offered, not tested |

The buzzer characteristic is documented for the BLU Button1 and the BLU Button Tough 1 as well. During setup the integration connects once and refuses a device without the characteristic. If a button works for you that is not listed as tested, please open an [issue](https://github.com/n-schilling/ha-bluetooth-button-plus/issues).

## Requirements

- Home Assistant 2026.10 or newer.
- A Bluetooth adapter that can **connect**: the adapter of the Home Assistant machine, or an [ESPHome Bluetooth proxy](https://esphome.io/components/bluetooth_proxy.html) with active connections. Shelly devices as Bluetooth proxies only forward advertisements, they cannot connect, so a button seen only through a Shelly proxy stays *unavailable* here.
- The button paired with that adapter, see below.

The buttons are available only while an adapter that can connect sees the button. Out of range, they are *unavailable*; a press then fails with a message that says so.

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
| Start buzzer (`button`) | Connects, starts the buzzer and disconnects. The button stops the buzzer by itself after a minute. |
| Stop buzzer (`button`) | Stops the buzzer before that. |

Both are *unavailable* while no adapter that can connect sees the button.

## Example

A script that makes the button buzz for ten seconds:

```yaml
sequence:
  - action: button.press
    target:
      entity_id: button.sbbt_102c_ee01_start_buzzer
  - delay:
      seconds: 10
  - action: button.press
    target:
      entity_id: button.sbbt_102c_ee01_stop_buzzer
```

## Limitations

- Range: only the adapter that is bonded with the button can trigger the buzzer, and only while it sees the button. Bluetooth proxies that merely forward advertisements do not help.
- The bond lives in BlueZ on the host. A new Bluetooth adapter, or a reinstalled host, needs a new pairing.
- Nothing is read from the button; its presses and its battery come from BTHome, its position from Bermuda.

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
