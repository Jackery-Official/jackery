"""Jackery Number Platform."""
import logging
from typing import Any, TYPE_CHECKING

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN

if TYPE_CHECKING:
    from .sensor import JackeryDataCoordinator

_LOGGER = logging.getLogger(__name__)


NUMBERS = {
    "socChgLimit": {"name": "SOC Charge Limit", "min": 0, "max": 100, "step": 1},
    "socDischgLimit": {"name": "SOC Discharge Limit", "min": 0, "max": 100, "step": 1},
    "maxOutPw": {"name": "Max Output Power (OnGrid)", "min": 0, "max": 10000, "step": 10},
    "autoStandby": {"name": "Auto Standby Mode", "min": 0, "max": 2, "step": 1},
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Jackery number entities."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    if coordinator is None:
        _LOGGER.warning("Coordinator not ready for numbers")
        return

    entities = []
    for key, cfg in NUMBERS.items():
        entities.append(
            JackeryMainNumber(
                key=key,
                name=cfg["name"],
                min_value=cfg["min"],
                max_value=cfg["max"],
                step=cfg["step"],
                coordinator=coordinator,
                config_entry_id=config_entry.entry_id,
            )
        )

    if entities:
        async_add_entities(entities)


class JackeryMainNumber(NumberEntity):
    """Main device number (cmd=5)."""

    def __init__(
        self,
        key: str,
        name: str,
        min_value: float,
        max_value: float,
        step: float,
        coordinator: "JackeryDataCoordinator",
        config_entry_id: str,
    ) -> None:
        self._key = key
        self._coordinator = coordinator
        self._attr_name = name
        self._attr_unique_id = f"jackery_main_{key}"
        self._attr_has_entity_name = True
        self._attr_mode = NumberMode.SLIDER
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step
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
        self._coordinator.register_sensor(f"main_number_{self._key}", self)

    async def async_will_remove_from_hass(self) -> None:
        self._coordinator.unregister_sensor(f"main_number_{self._key}")
        await super().async_will_remove_from_hass()

    def _update_from_coordinator(self, data: dict) -> None:
        if self._key not in data:
            return
        val = data.get(self._key)
        if val is None:
            return
        try:
            self._attr_native_value = float(val)
            self._attr_available = True
            self.async_write_ha_state()
        except (TypeError, ValueError):
            pass

    async def async_set_native_value(self, value: float) -> None:
        await self._coordinator.async_control_main_device({self._key: int(value)})
