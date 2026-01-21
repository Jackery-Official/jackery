"""Energy Monitor MQTT Integration for Home Assistant."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform
from homeassistant.components import mqtt

_LOGGER = logging.getLogger(__name__)

DOMAIN = "jackery"
PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Jackery from a config entry."""
    _LOGGER.info("Setting up Jackery integration")
    
    # 检查 MQTT 集成是否已配置和可用
    if not await mqtt.async_wait_for_mqtt_client(hass):
        _LOGGER.error(
            "MQTT integration is not available or not configured. "
            "Please set up the MQTT integration first: "
            "Settings -> Devices & Services -> Add Integration -> MQTT"
        )
        return False
    
    _LOGGER.info("MQTT integration is available and ready")
    
    # 初始化存储结构
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "config": entry.data,
        "coordinator": None,  # 将在 sensor.py 中设置
    }
    
    # 加载传感器平台
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Jackery integration")
    
    # 停止协调器
    entry_data = hass.data[DOMAIN].get(entry.entry_id, {})
    coordinator = entry_data.get("coordinator")
    if coordinator:
        await coordinator.async_stop()
        _LOGGER.info("Coordinator stopped")
    
    # 卸载传感器平台
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok

