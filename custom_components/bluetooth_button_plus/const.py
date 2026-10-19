"""Constants for Bluetooth Button Plus."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "bluetooth_button_plus"

# Shelly BLU buttons announce themselves as "SBBT-<model>", for example
# SBBT-002C (BLU Button1) or SBBT-102C (BLU Button Tough 1 ZB).
BUTTON_NAME_PREFIX: Final = "SBBT-"

# The "Find my device" characteristic of Shelly BLU buttons: writing 1 starts
# the buzzer, 0 stops it; the button stops it by itself after a minute. It is
# readable and writable only over a bonded connection, so the button has to be
# paired with Home Assistant's Bluetooth adapter once (see the README).
BUZZER_CHARACTERISTIC: Final = "5b026510-4088-c297-46d8-be6c736a087b"
BUZZER_ON: Final = b"\x01"
BUZZER_OFF: Final = b"\x00"

# The buzzer volume: 0 off, 1 low, 2 medium, 3 high. Bonded as well.
VOLUME_CHARACTERISTIC: Final = "dd78bf35-7680-484e-ad86-1bc1e7738e14"
VOLUME_MIN: Final = 0
VOLUME_MAX: Final = 3
# The button's factory setting
DEFAULT_VOLUME: Final = 1

# Action "buzz": start the buzzer and stop it after a time
SERVICE_BUZZ: Final = "buzz"
ATTR_DURATION: Final = "duration"
ATTR_VOLUME: Final = "volume"

# The configured volume and buzz duration live in the config entry's options,
# so they survive restarts and disabled number entities alike
OPTION_VOLUME: Final = "volume"
OPTION_DURATION: Final = "duration"
DEFAULT_BUZZ_SECONDS: Final = 10
MIN_BUZZ_SECONDS: Final = 1
# The button stops the buzzer by itself after a minute
MAX_BUZZ_SECONDS: Final = 60

# Connection attempts before a press fails
MAX_CONNECT_ATTEMPTS: Final = 3
