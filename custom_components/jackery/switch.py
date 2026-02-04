"""Jackery Switch Platform."""
import logging
from typing import Any, TYPE_CHECKING

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN

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

    # Add any existing sub-devices as switches (non-CT)
    for item in coordinator.get_subdevices():
        sn = item.get("deviceSn") or item.get("sn")
        dev_type = item.get("devType")
        if dev_type is None and item.get("subType") == 2:
            dev_type = 2
        if sn and dev_type != 2:
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

        self._attr_name = "Switch"
        self._attr_unique_id = f"jackery_plug_{plug_sn}_switch"
        self._attr_has_entity_name = True

        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"sub_{plug_sn}")},
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
        self._coordinator.register_sensor(f"plug_switch_{self._plug_sn}", self)

    async def async_will_remove_from_hass(self) -> None:
        self._coordinator.unregister_sensor(f"plug_switch_{self._plug_sn}")
        await super().async_will_remove_from_hass()

    def _update_from_coordinator(self, data: dict) -> None:
        plugs = data.get("plugs") or data.get("plug")
        if not plugs or not isinstance(plugs, list):
            return

        my_plug = next((p for p in plugs if (p.get("sn") == self._plug_sn or p.get("deviceSn") == self._plug_sn)), None)
        if not my_plug:
            return

        self._raw_data = dict(my_plug)
        val = my_plug.get("sysSwitch")
        if val is None:
            val = my_plug.get("switchSta")
        if val is None:
            return

        self._attr_is_on = bool(int(val))
        self._attr_available = True
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._coordinator.async_control_subdevice_switch(
            plug_sn=self._plug_sn,
            dev_type=self._dev_type,
            is_on=True,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._coordinator.async_control_subdevice_switch(
            plug_sn=self._plug_sn,
            dev_type=self._dev_type,
            is_on=False,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "plug_sn": self._plug_sn,
            "dev_type": self._dev_type,
            "raw_data": self._raw_data,
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
        self._attr_unique_id = f"jackery_main_{key}"
        self._attr_has_entity_name = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry_id)},
            "name": "Jackery",
            "manufacturer": "Jackery",
            "model": "Energy Monitor",
        }

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
