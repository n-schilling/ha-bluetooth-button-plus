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

# Connection attempts before a press fails
MAX_CONNECT_ATTEMPTS: Final = 3
