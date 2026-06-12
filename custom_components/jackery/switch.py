"""Jackery Switch Platform."""
import logging
from typing import Any, TYPE_CHECKING

from homeassistant.components import persistent_notification
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN
from .sensor import (
    COMM_MODE_LABELS,
    plug_comm_mode,
    plug_mqtt_control_allowed,
    should_create_plug_switch,
)

if TYPE_CHECKING:
    from .sensor import JackeryDataCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Jackery switches."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    if coordinator is None:
        _LOGGER.warning("Coordinator not ready for switches")
        return

    # Register callback for dynamic switch entities
    def add_switch_entities_callback(new_entities):
        async_add_entities(new_entities)
    coordinator.add_switch_entities_callback = add_switch_entities_callback

    entities = []

    # Main device switches
    entities.extend(
        [
            JackeryMainSwitch(
                key="isAutoStandby",
                name="Auto Standby Allowed",
                coordinator=coordinator,
                config_entry_id=config_entry.entry_id,
            ),
            JackeryMainSwitch(
                key="swEps",
                name="EPS Switch",
                coordinator=coordinator,
                config_entry_id=config_entry.entry_id,
            ),
        ]
    )

    # Add any existing sub-devices as switches (smart plugs only)
    for item in coordinator.get_subdevices():
        sn = item.get("deviceSn") or item.get("sn")
        dev_type = item.get("devType")
        if sn and should_create_plug_switch(item):
            entities.append(
                JackeryPlugSwitch(
                    plug_sn=sn,
                    dev_type=dev_type,
                    coordinator=coordinator,
                    config_entry_id=config_entry.entry_id,
                )
            )

    if entities:
        async_add_entities(entities)


class JackeryPlugSwitch(SwitchEntity):
    """Jackery Smart Plug Switch."""

    def __init__(
        self,
        plug_sn: str,
        dev_type: int,
        coordinator: "JackeryDataCoordinator",
        config_entry_id: str,
    ) -> None:
        """Initialize."""
        self._plug_sn = plug_sn
        self._dev_type = dev_type
        self._coordinator = coordinator
        self._raw_data = {}

        device_sn = getattr(coordinator, "_device_sn", "")
        self._attr_name = "Switch"
        self._attr_unique_id = f"jackery_{device_sn}_plug_{plug_sn}_switch"
        self._attr_has_entity_name = True

        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"sub_{device_sn}_{plug_sn}")},
            "via_device": (DOMAIN, config_entry_id),
            "name": f"Jackery Plug {plug_sn}",
            "manufacturer": "Jackery",
            "model": f"Sub-device Type {dev_type}",
        }

    @property
    def should_poll(self) -> bool:
        return False

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._coordinator.register_sensor(self._attr_unique_id, self)

    async def async_will_remove_from_hass(self) -> None:
        self._coordinator.unregister_sensor(self._attr_unique_id)
        await super().async_will_remove_from_hass()

    def _plug_item(self) -> dict[str, Any]:
        """合并协调器缓存与实体快照，优先使用缓存中的 commMode 等字段。"""
        cached = self._coordinator.get_plug_item(self._plug_sn)
        if cached:
            return {**self._raw_data, **cached}
        return dict(self._raw_data)

    def _update_from_coordinator(self, data: dict) -> None:
        my_plug = self._coordinator.get_plug_item(self._plug_sn)
        if not my_plug:
            plugs = data.get("plugs") or data.get("plug")
            if plugs and isinstance(plugs, list):
                my_plug = next(
                    (
                        p
                        for p in plugs
                        if isinstance(p, dict)
                        and (p.get("sn") == self._plug_sn or p.get("deviceSn") == self._plug_sn)
                    ),
                    None,
                )
        if not my_plug:
            return

        self._raw_data = dict(my_plug)
        self._attr_available = True

        val = my_plug.get("switchSta")
        if val is None:
            val = my_plug.get("sysSwitch")
        if val is not None:
            self._attr_is_on = bool(int(val))

        self.async_write_ha_state()

    async def _ensure_mqtt_controllable(self) -> None:
        """仅 commMode=1（本地连接）时允许 MQTT 控制；不可控时弹出持久通知。"""
        allowed, reason = plug_mqtt_control_allowed(self._plug_item())
        if not allowed:
            persistent_notification.async_create(
                self.hass,
                message=reason,
                title="Jackery 智能插座",
                notification_id=f"jackery_plug_{self._plug_sn}_mqtt_blocked",
            )
            raise HomeAssistantError(reason)

    async def async_toggle(self, **kwargs: Any) -> None:
        """看板标题开关/卡片 toggle 均走此入口，云云对接时开/关统一拦截。"""
        await self._ensure_mqtt_controllable()
        if self.is_on:
            await self._coordinator.async_control_subdevice_switch(
                plug_sn=self._plug_sn,
                dev_type=self._dev_type,
                is_on=False,
            )
        else:
            await self._coordinator.async_control_subdevice_switch(
                plug_sn=self._plug_sn,
                dev_type=self._dev_type,
                is_on=True,
            )

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._ensure_mqtt_controllable()
        await self._coordinator.async_control_subdevice_switch(
            plug_sn=self._plug_sn,
            dev_type=self._dev_type,
            is_on=True,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._ensure_mqtt_controllable()
        await self._coordinator.async_control_subdevice_switch(
            plug_sn=self._plug_sn,
            dev_type=self._dev_type,
            is_on=False,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        raw = self._plug_item()
        mode = plug_comm_mode(raw)
        mqtt_ok, mqtt_block_reason = plug_mqtt_control_allowed(raw)
        return {
            "plug_sn": self._plug_sn,
            "dev_type": self._dev_type,
            "commState": raw.get("commState"),
            "commMode": mode,
            "commMode_label": COMM_MODE_LABELS.get(mode) if mode is not None else None,
            "mqtt_controllable": mqtt_ok,
            "mqtt_control_block_reason": mqtt_block_reason or None,
            "scanName": raw.get("scanName") or raw.get("name"),
            "switchSta": raw.get("switchSta") if raw.get("switchSta") is not None else raw.get("sysSwitch"),
            "outPw": raw.get("outPw"),
            "inPw": raw.get("inPw"),
            "raw_data": raw,
        }


class JackeryMainSwitch(SwitchEntity):
    """Main device switch (cmd=5)."""

    def __init__(
        self,
        key: str,
        name: str,
        coordinator: "JackeryDataCoordinator",
        config_entry_id: str,
    ) -> None:
        self._key = key
        self._coordinator = coordinator
        self._attr_name = name
        device_sn = getattr(coordinator, "_device_sn", None)
        self._attr_unique_id = f"jackery_{device_sn}_main_{key}" if device_sn else f"jackery_main_{key}"
        self._attr_has_entity_name = True
        device_info = {
            "identifiers": {(DOMAIN, config_entry_id)},
            "name": f"Jackery {device_sn}" if device_sn else "Jackery",
            "manufacturer": "Jackery",
            "model": "Energy Monitor",
        }
        if device_sn:
            device_info["serial_number"] = device_sn
        self._attr_device_info = device_info

    @property
    def should_poll(self) -> bool:
        return False

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._coordinator.register_sensor(f"main_switch_{self._key}", self)

    async def async_will_remove_from_hass(self) -> None:
        self._coordinator.unregister_sensor(f"main_switch_{self._key}")
        await super().async_will_remove_from_hass()

    def _update_from_coordinator(self, data: dict) -> None:
        if self._key not in data:
            return
        val = data.get(self._key)
        if val is None:
            return
        self._attr_is_on = bool(int(val))
        self._attr_available = True
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._coordinator.async_control_main_device({self._key: 1})

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._coordinator.async_control_main_device({self._key: 0})
