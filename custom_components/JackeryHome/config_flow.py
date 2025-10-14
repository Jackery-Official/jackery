"""Config flow for Energy Monitor integration."""
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

# 配置数据模式
DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(
            "topic_prefix",
            default="homeassistant/sensor"
        ): str,
        vol.Required(
            "mqtt_broker",
            default="192.168.0.101"
        ): str,
        vol.Optional(
            "mqtt_port",
            default=1883
        ): int,
    }
)


class JackeryHomeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for JackeryHome."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # 验证 MQTT broker 地址
            mqtt_broker = user_input.get("mqtt_broker", "").strip()
            if not mqtt_broker:
                errors["base"] = "mqtt_broker_required"
            
            # 验证端口范围
            try:
                mqtt_port = int(user_input.get("mqtt_port", 1883))
                if mqtt_port < 1 or mqtt_port > 65535:
                    errors["base"] = "invalid_port"
            except (ValueError, TypeError):
                errors["base"] = "invalid_port"
            
            if not errors:
                # 检查是否已经配置
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                
                _LOGGER.info(f"Creating JackeryHome config entry with topic_prefix: {user_input.get('topic_prefix', 'homeassistant/sensor')}")
                
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

