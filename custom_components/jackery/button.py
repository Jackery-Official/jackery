"""Jackery Button Platform."""
import logging
from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
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
    """Set up Jackery button entities."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    if coordinator is None:
        _LOGGER.warning("Coordinator not ready for buttons")
        return

    async_add_entities(
        [
            JackeryRebootButton(
                coordinator=coordinator,
                config_entry_id=config_entry.entry_id,
            )
        ]
    )


class JackeryRebootButton(ButtonEntity):
    """Reboot the main device (type=1, reboot=1)."""

    def __init__(
        self,
        coordinator: "JackeryDataCoordinator",
        config_entry_id: str,
    ) -> None:
        self._coordinator = coordinator
        self._attr_name = "Reboot"
        self._attr_icon = "mdi:restart"
        self._attr_device_class = ButtonDeviceClass.RESTART

        device_sn = getattr(coordinator, "_device_sn", None)
        self._attr_unique_id = (
            f"jackery_{device_sn}_main_reboot" if device_sn else "jackery_main_reboot"
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

    async def async_press(self) -> None:
        """Send reboot command (reboot=1)."""
        await self._coordinator.async_control_main_device({"reboot": 1})
