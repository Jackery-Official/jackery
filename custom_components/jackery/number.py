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
    "socChgLimit": {
        "name": "SOC Charge Limit",
        "min": 50,
        "max": 100,
        "step": 1,
        "min_key": "minSocChg",
        "max_key": "maxSocChg",
    },
    "socDischgLimit": {
        "name": "SOC Discharge Limit",
        "min": 5,
        "max": 49,
        "step": 1,
        "min_key": "minSocDischg",
        "max_key": "maxSocDischg",
    },
    "maxOutPw": {
        "name": "Max Output Power (OnGrid)",
        "min": 0,
        "max": 2500,
        "step": 10,
    },
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
        device_sn = getattr(coordinator, "_device_sn", None)
        self._attr_unique_id = f"jackery_{device_sn}_main_{key}" if device_sn else f"jackery_main_{key}"
        self._attr_has_entity_name = True
        self._attr_mode = NumberMode.SLIDER
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_sn), (DOMAIN, config_entry_id)} if device_sn else {(DOMAIN, config_entry_id)},
            "name": f"Jackery {device_sn}" if device_sn else "Jackery",
            "manufacturer": "Jackery",
            "model": "Energy Monitor",
        }
        if device_sn:
            self._attr_device_info["serial_number"] = device_sn

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
        """Update the entity when new data is received."""
        changed = False
        cfg = NUMBERS.get(self._key, {})

        # 1. Update dynamic limits (Min/Max)
        min_key = cfg.get("min_key")
        if min_key and min_key in data:
            new_min = float(data[min_key])
            if new_min != self._attr_native_min_value:
                self._attr_native_min_value = new_min
                changed = True

        max_key = cfg.get("max_key")
        if max_key and max_key in data:
            new_max = float(data[max_key])
            if new_max != self._attr_native_max_value:
                self._attr_native_max_value = new_max
                changed = True

        # 2. Update current value
        if self._key in data:
            val = data.get(self._key)
            if val is not None:
                try:
                    new_val = float(val)
                    if new_val != self._attr_native_value:
                        self._attr_native_value = new_val
                        self._attr_available = True
                        changed = True
                except (TypeError, ValueError):
                    pass
        
        # 3. Force UI update if anything changed
        if changed:
            self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        self._attr_native_value = value
        self.async_write_ha_state()
        await self._coordinator.async_control_main_device({self._key: int(value)})
