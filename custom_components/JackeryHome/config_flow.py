"""Config flow for Energy Monitor integration."""
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.components import mqtt

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

# 配置数据模式
DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(
            "topic_prefix",
            default="homeassistant/sensor"
        ): str,
    }
)


class JackeryHomeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for JackeryHome."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        
        errors = {}

        if user_input is not None:
            # 检查 MQTT 集成是否已配置
            if not await mqtt.async_wait_for_mqtt_client(self.hass):
                errors["base"] = "mqtt_not_configured"
            else:
                _LOGGER.info(
                    f"Creating JackeryHome config entry with topic_prefix: "
                    f"{user_input.get('topic_prefix', 'homeassistant/sensor')}"
                )
                
                return self.async_create_entry(
                    title="JackeryHome",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "topic_prefix": "MQTT topic prefix (e.g., homeassistant/sensor)",
            },
        )

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)

