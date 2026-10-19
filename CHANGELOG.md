# Changelog

All notable changes are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versions follow [Semantic Versioning](https://semver.org/).

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
