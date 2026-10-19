# Changelog

All notable changes are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versions follow [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-10-19

### Added

- Shelly BLU buttons (`SBBT-*`) are discovered over Bluetooth and set up with a confirmation; the setup connects once to check that the button is paired with the adapter and has a buzzer.
- Buttons *Start buzzer* and *Stop buzzer* per device. They are available only while an adapter that can connect sees the button; a proxy that only forwards advertisements does not count.
