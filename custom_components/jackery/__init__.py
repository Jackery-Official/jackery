"""Energy Monitor MQTT Integration for Home Assistant."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.const import Platform
from homeassistant.components import mqtt
from homeassistant.helpers import entity_registry as er

_LOGGER = logging.getLogger(__name__)

DOMAIN = "jackery"
PLATFORMS = [Platform.SENSOR, Platform.SWITCH, Platform.NUMBER, Platform.SELECT, Platform.BUTTON]


async def _migrate_unique_ids(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate legacy unique_ids to new format with device_sn to preserve historical data.

    Old format: jackery_{sensor_id} / jackery_main_{key}
    New format: jackery_{sn}_{sensor_id} / jackery_{sn}_main_{key} / jackery_{sn}_plug_{plug_sn}_{key}
    """
    device_sn = entry.data.get("device_sn")
    if not device_sn:
        return

    new_prefix = f"jackery_{device_sn}_"

    @callback
    def _update(registry_entry: er.RegistryEntry) -> dict | None:
        old = registry_entry.unique_id
        # Skip if already migrated
        if old.startswith(new_prefix):
            return None

        if old.startswith("jackery_main_"):
            return {"new_unique_id": old.replace("jackery_main_", f"{new_prefix}main_", 1)}
        if old.startswith("jackery_plug_"):
            return {"new_unique_id": old.replace("jackery_plug_", f"{new_prefix}plug_", 1)}
        if old.startswith("jackery_ct_"):
            return {"new_unique_id": old.replace("jackery_ct_", f"{new_prefix}ct_", 1)}
        if old.startswith("jackery_"):
            return {"new_unique_id": old.replace("jackery_", new_prefix, 1)}
        return None

    await er.async_migrate_entries(hass, entry.entry_id, _update)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Jackery from a config entry."""
    _LOGGER.info("Setting up Jackery integration")
    
    # Check if MQTT integration is configured and available
    if not await mqtt.async_wait_for_mqtt_client(hass):
        _LOGGER.error(
            "MQTT integration is not available or not configured. "
            "Please set up the MQTT integration first: "
            "Settings -> Devices & Services -> Add Integration -> MQTT"
        )
        return False
    
    _LOGGER.info("MQTT integration is available and ready")

    # Migrate legacy unique_ids (multi-instance support: add device_sn prefix while preserving history)
    await _migrate_unique_ids(hass, entry)

    # Initialize storage structure
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "config": entry.data,
        "coordinator": None,  # Will be set in sensor.py
    }
    
    # Load sensor platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Jackery integration")
    
    # Stop the coordinator
    entry_data = hass.data[DOMAIN].get(entry.entry_id, {})
    coordinator = entry_data.get("coordinator")
    if coordinator:
        await coordinator.async_stop()
        _LOGGER.info("Coordinator stopped")
    
    # Unload sensor platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok
