"""Config flow for Energy Monitor integration."""
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Config data schema
DATA_SCHEMA = vol.Schema(
    {

        vol.Required("device_sn"): str,
        vol.Required("token"): str,
        vol.Optional(
            "topic_prefix",
            default="hb"
        ): str,
    }
)


class JackeryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Jackery."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Check if MQTT integration is configured
            if not await mqtt.async_wait_for_mqtt_client(self.hass):
                errors["base"] = "mqtt_not_configured"
            else:
                device_sn = user_input["device_sn"]

                # Support adding multiple DIY3 hosts, each with independent config.
                # Use device_sn as unique key to prevent duplicate hosts.
                await self.async_set_unique_id(device_sn)
                self._abort_if_unique_id_configured()

                _LOGGER.info(
                    f"Creating Jackery config entry with "
                    f"device_sn: {device_sn}, "
                    f"topic_prefix: {user_input.get('topic_prefix', 'hb')}"
                )

                return self.async_create_entry(
                    title=f"Jackery {device_sn}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "topic_prefix": "Protocol root topic (default: hb)",
            },
        )

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> FlowResult:
        """Handle re-authentication when the device rejects the Token."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm re-authentication by letting the user re-enter the Token."""
        errors: dict[str, str] = {}
        entry = getattr(self, "_reauth_entry", None)

        if user_input is not None and entry is not None:
            new_data = {**entry.data, "token": user_input["token"]}
            self.hass.config_entries.async_update_entry(entry, data=new_data)
            await self.hass.config_entries.async_reload(entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required("token"): str}),
            errors=errors,
            description_placeholders={
                "device_sn": entry.data.get("device_sn") if entry else "",
            },
        )
