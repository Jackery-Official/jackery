"""Jackery Select Platform."""
import logging
from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN

if TYPE_CHECKING:
    from .sensor import JackeryDataCoordinator

_LOGGER = logging.getLogger(__name__)

# autoStandby: 0=Invalid, 1=Standby, 2=On
AUTO_STANDBY_OPTIONS = {
    "invalid": 0,
    "standby": 1,
    "on": 2,
}
AUTO_STANDBY_VALUE_TO_OPTION = {v: k for k, v in AUTO_STANDBY_OPTIONS.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Jackery select entities."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    if coordinator is None:
        _LOGGER.warning("Coordinator not ready for selects")
        return

    async_add_entities(
        [
            JackeryAutoStandbySelect(
                coordinator=coordinator,
                config_entry_id=config_entry.entry_id,
            )
        ]
    )


class JackeryAutoStandbySelect(SelectEntity):
    """Auto Standby mode select (autoStandby, cmd=5)."""

    def __init__(
        self,
        coordinator: "JackeryDataCoordinator",
        config_entry_id: str,
    ) -> None:
        self._key = "autoStandby"
        self._coordinator = coordinator
        self._attr_name = "Auto Standby Mode"
        self._attr_icon = "mdi:power-sleep"
        self._attr_options = list(AUTO_STANDBY_OPTIONS.keys())

        device_sn = getattr(coordinator, "_device_sn", None)
        self._attr_unique_id = (
            f"jackery_{device_sn}_main_{self._key}" if device_sn else f"jackery_main_{self._key}"
        )
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
        self._coordinator.register_sensor(f"main_select_{self._key}", self)

    async def async_will_remove_from_hass(self) -> None:
        self._coordinator.unregister_sensor(f"main_select_{self._key}")
        await super().async_will_remove_from_hass()

    def _update_from_coordinator(self, data: dict) -> None:
        if self._key not in data:
            return
        val = data.get(self._key)
        if val is None:
            return
        try:
            self._attr_current_option = AUTO_STANDBY_VALUE_TO_OPTION.get(int(val))
            self._attr_available = True
            self.async_write_ha_state()
        except (TypeError, ValueError):
            pass

    async def async_select_option(self, option: str) -> None:
        value = AUTO_STANDBY_OPTIONS.get(option)
        if value is None:
            return
        await self._coordinator.async_control_main_device({self._key: value})
