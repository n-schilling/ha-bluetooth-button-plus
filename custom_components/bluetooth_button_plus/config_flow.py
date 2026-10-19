"""Config flow for Bluetooth Button Plus."""

from __future__ import annotations

from typing import Any

import probatio

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_MODEL

from .const import BUTTON_NAME_PREFIX, DOMAIN
from .device import CannotConnect, NotPaired, NotSupported, async_check_button


def is_button(info: BluetoothServiceInfoBleak) -> bool:
    """Return whether the advertisement comes from a Shelly BLU button."""
    return info.connectable and info.name.startswith(BUTTON_NAME_PREFIX)


def title_of(info: BluetoothServiceInfoBleak) -> str:
    """Return a title: the model and the end of the address, "SBBT-102C EE01"."""
    return f"{info.name} {info.address.replace(':', '')[-4:].upper()}"


class BluetoothButtonPlusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a Shelly BLU button."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Offer a button that an adapter discovered."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        if not is_button(discovery_info):
            return self.async_abort(reason="not_supported")
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {"name": title_of(discovery_info)}
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered button; connects once to check it is paired."""
        assert self._discovery_info is not None
        errors: dict[str, str] = {}
        if (
            user_input is not None
            and (result := await self._async_finish(self._discovery_info, errors)) is not None
        ):
            return result
        return self.async_show_form(
            step_id="confirm",
            errors=errors,
            description_placeholders={
                "name": title_of(self._discovery_info),
                "address": self._discovery_info.address,
            },
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Pick one of the buttons an adapter sees."""
        errors: dict[str, str] = {}
        if user_input is not None:
            info = self._discovered[user_input[CONF_ADDRESS]]
            await self.async_set_unique_id(info.address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            if (result := await self._async_finish(info, errors)) is not None:
                return result
        else:
            configured = self._async_current_ids(include_ignore=False)
            for info in async_discovered_service_info(self.hass, connectable=True):
                if info.address not in configured and is_button(info):
                    self._discovered[info.address] = info
            if not self._discovered:
                return self.async_abort(reason="no_devices_found")
        schema = probatio.Schema(
            {
                probatio.Required(CONF_ADDRESS): probatio.In(
                    {
                        address: f"{title_of(info)} ({address})"
                        for address, info in self._discovered.items()
                    }
                )
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def _async_finish(
        self, info: BluetoothServiceInfoBleak, errors: dict[str, str]
    ) -> ConfigFlowResult | None:
        """Check the button and create the entry; on an error fill errors and return None."""
        try:
            await async_check_button(self.hass, info.device, title_of(info))
        except NotSupported:
            return self.async_abort(reason="not_supported")
        except NotPaired:
            errors["base"] = "not_paired"
        except CannotConnect:
            errors["base"] = "cannot_connect"
        else:
            return self.async_create_entry(
                title=title_of(info), data={CONF_ADDRESS: info.address, CONF_MODEL: info.name}
            )
        return None
