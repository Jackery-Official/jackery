"""JackeryHome Sensor Platform."""
import json
import logging
from typing import Any

from homeassistant.components import mqtt as ha_mqtt
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import UnitOfPower, PERCENTAGE

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

# 传感器配置
SENSORS = {
    "solar_power": {
        "name": "太阳能发电",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:solar-power",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "home_power": {
        "name": "家庭用电",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:home-lightning-bolt",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "grid_import": {
        "name": "电网输入",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:transmission-tower-import",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "grid_export": {
        "name": "电网输出",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:transmission-tower-export",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "battery_charge": {
        "name": "电池充电",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:battery-charging",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "battery_discharge": {
        "name": "电池放电",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:battery-minus",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "battery_soc": {
        "name": "电池电量",
        "unit": PERCENTAGE,
        "icon": "mdi:battery-70",
        "device_class": SensorDeviceClass.BATTERY,
        "state_class": SensorStateClass.MEASUREMENT,
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up JackeryHome sensors from a config entry."""
    _LOGGER.info("Setting up JackeryHome sensors")
    
    # 获取配置数据
    config = config_entry.data
    topic_prefix = config.get("topic_prefix", "homeassistant/sensor")
    
    _LOGGER.info(f"Topic prefix: {topic_prefix}")
    
    # 创建所有传感器实体
    entities = []
    for sensor_id, sensor_config in SENSORS.items():
        entity = JackeryHomeSensor(
            sensor_id=sensor_id,
            name=sensor_config["name"],
            unit=sensor_config["unit"],
            icon=sensor_config["icon"],
            device_class=sensor_config["device_class"],
            state_class=sensor_config["state_class"],
            topic_prefix=topic_prefix,
            config_entry_id=config_entry.entry_id,
        )
        entities.append(entity)
    
    async_add_entities(entities)
    _LOGGER.info(f"Added {len(entities)} JackeryHome sensors")


class JackeryHomeSensor(SensorEntity):
    """Representation of a JackeryHome Sensor."""

    def __init__(
        self,
        sensor_id: str,
        name: str,
        unit: str,
        icon: str,
        device_class: SensorDeviceClass,
        state_class: SensorStateClass,
        topic_prefix: str,
        config_entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        self._sensor_id = sensor_id
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_unique_id = f"jackery_home_{sensor_id}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry_id)},
            "name": "JackeryHome",
            "manufacturer": "Jackery",
            "model": "Energy Monitor",
            "sw_version": "1.0.3",
        }
        self._topic = f"{topic_prefix}/{sensor_id}/state"
        self._attr_native_value = None
        self._attr_available = False

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    async def async_added_to_hass(self) -> None:
        """Set up the sensor."""
        _LOGGER.info(f"JackeryHome sensor {self._sensor_id} added to Home Assistant")
        
        # 订阅 MQTT 主题
        @callback
        def message_received(msg):
            """Handle new MQTT messages."""
            try:
                payload = msg.payload
                if isinstance(payload, bytes):
                    payload = payload.decode("utf-8")
                
                _LOGGER.debug(f"Received MQTT message for {self._sensor_id}: {payload}")
                
                # 尝试解析 JSON
                try:
                    data = json.loads(payload)
                    if isinstance(data, dict) and "value" in data:
                        value = data["value"]
                    else:
                        value = data
                except json.JSONDecodeError:
                    # 如果不是 JSON，直接使用原始值
                    try:
                        value = float(payload)
                    except ValueError:
                        # 如果无法转换为数字，保持原值但设置不可用
                        value = payload
                        self._attr_available = False
                        self.async_write_ha_state()
                        return
                
                # 更新传感器状态
                self._attr_native_value = value
                self._attr_available = True
                self.async_write_ha_state()
                
                _LOGGER.debug(f"Updated {self._sensor_id} with value: {value}")
                
            except Exception as e:
                _LOGGER.error(f"Error processing MQTT message for {self._sensor_id}: {e}")

        # 订阅 MQTT 主题
        await ha_mqtt.async_subscribe(
            self.hass, 
            self._topic, 
            message_received, 
            1
        )
        
        _LOGGER.info(f"Subscribed to MQTT topic: {self._topic}")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {
            "sensor_id": self._sensor_id,
            "mqtt_topic": self._topic,
        }