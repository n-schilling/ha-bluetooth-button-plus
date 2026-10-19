# Changelog

All notable changes are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versions follow [Semantic Versioning](https://semver.org/).

## [0.4.0] - 2026-10-19

### Fixed

- A timed stop that fell due while a new buzz was being written no longer cuts the new buzz short, and a stop pressed during a start wins: every command runs under one lock and a stale timed stop steps aside.
- The setup checks the volume characteristic as well, so a button that passes the setup can always buzz.
- A flow started with data for a button that was not offered aborts cleanly instead of failing with an internal error.
- "Not paired" is recognized from the Bluetooth error itself (the BlueZ error code or the original error's text), no longer from a text that carries the button's name.
- The HACS check in CI is skipped for every event without a repository object, not only for pushes.

### Changed

- The buzzer volume and the buzz duration are kept in the integration's settings (config entry options) instead of the entities' restored state: they survive a restart and a disabled entity.
- The host's own Bluetooth adapter is preferred for the connection, since it holds the bond; a proxy is the last resort.
- Entities use Home Assistant's passive Bluetooth coordinator for their availability: one pair of Bluetooth callbacks per button instead of one per entity. The buzz duration, kept in Home Assistant, no longer follows the button's range.
- The buttons are described by one table; the German translation is checked against strings.json; the privacy test scans the whole repository and the full import paths.
- README: what happens with a press out of range, and why Bluetooth proxies cannot help.

## [0.3.2] - 2026-10-19

### Added

- A brand icon, shown on the integrations page and the device page.

## [0.3.1] - 2026-10-19

### Fixed

- A docstring quoted the end of a real Bluetooth address as its example; it now uses the made-up one of the tests. A privacy test keeps real addresses, e-mail addresses and network libraries out of the repository.

## [0.3.0] - 2026-10-19

### Added

- Button *Buzz*: buzzes for the configured time at the configured volume, for dashboards and the device page.
- Number *Buzz duration* (1–60 s, default 10, kept in Home Assistant) per button.

### Changed

- The action `bluetooth_button_plus.buzz` targets the *Buzz* button (or its device) and, without `duration`, uses the buzz duration of the button.

## [0.2.0] - 2026-10-19

### Added

- Number *Buzzer volume* (0 off, 1 low, 2 medium, 3 high) per button. It is written to the button when set and restored after a restart; every start of the buzzer applies it first.
- Action `bluetooth_button_plus.buzz`: starts the buzzer and stops it after a duration (1–60 s, default 10), optionally at a volume for this one buzz. Targets the *Start buzzer* button or its device.

### Changed

- *Start buzzer* sets the buzzer volume before it starts the buzzer; *Stop buzzer* also drops a pending timed stop.
- Test harness 0.13.373 (Home Assistant 2026.10.2), ruff 0.17.1.

## [0.1.0] - 2026-10-19

### Added

- Shelly BLU buttons (`SBBT-*`) are discovered over Bluetooth and set up with a confirmation; the setup connects once to check that the button is paired with the adapter and has a buzzer.
- Buttons *Start buzzer* and *Stop buzzer* per device. They are available only while an adapter that can connect sees the button; a proxy that only forwards advertisements does not count.
