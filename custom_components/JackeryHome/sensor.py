"""Energy Monitor Sensor Platform."""
import asyncio
import json
import logging
from typing import Any

import paho.mqtt.client as mqtt

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

# 全局 MQTT 客户端和数据处理
class MQTTDataManager:
    """MQTT 数据管理器，负责订阅设备数据并发送请求"""
    
    def __init__(self, hass: HomeAssistant, topic_prefix: str, mqtt_broker: str = "192.168.0.101", mqtt_port: int = 1883):
        self.hass = hass
        self.topic_prefix = topic_prefix
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.client = None
        self.data_task = None
        self.sensors = {}
        
    async def start(self):
        """启动 MQTT 客户端和数据获取任务"""
        try:
            # 创建 MQTT 客户端
            self.client = mqtt.Client(client_id="energy_monitor_sensor", callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message
            
            # 连接到 MQTT 代理
            await self._connect_mqtt()
            
            # 启动数据获取任务
            self.data_task = asyncio.create_task(self._data_fetch_loop())
            
            _LOGGER.info("MQTT Data Manager started successfully")
            
        except Exception as e:
            _LOGGER.error(f"Failed to start MQTT Data Manager: {e}")
    
    async def _connect_mqtt(self):
        """连接到 MQTT 代理"""
        def _connect():
            self.client.connect(self.mqtt_broker, self.mqtt_port, 60)
            self.client.loop_start()
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _connect)
        
    def _on_connect(self, client, userdata, flags, rc, properties):
        """MQTT 连接回调"""
        if rc == 0:
            _LOGGER.info("Connected to MQTT broker")
            # 订阅设备数据主题
            client.subscribe("/device/data")
            _LOGGER.info("Subscribed to /device/data topic")
        else:
            _LOGGER.error(f"Failed to connect to MQTT broker with result code {rc}")
    
    def _on_message(self, client, userdata, msg):
        """MQTT 消息接收回调"""
        try:
            topic = msg.topic
            payload = msg.payload.decode()
            
            if topic == "/device/data":
                _LOGGER.debug(f"Received data from /device/data: {payload}")
                # 处理接收到的数据
                self._process_device_data(payload)
                
        except Exception as e:
            _LOGGER.error(f"Error processing MQTT message: {e}")
    
    def _process_device_data(self, payload: str):
        """处理设备数据"""
        try:
            data = json.loads(payload)
            _LOGGER.debug(f"Processed device data: {data}")
            
            # 将处理后的数据发送到相应的传感器
            for sensor_id, sensor_entity in self.sensors.items():
                if sensor_id in data:
                    # 在 Home Assistant 主线程中更新传感器状态
                    self.hass.create_task(sensor_entity._update_state(data[sensor_id]))
                    
        except json.JSONDecodeError as e:
            _LOGGER.error(f"Invalid JSON data received: {payload}, error: {e}")
        except Exception as e:
            _LOGGER.error(f"Error processing device data: {e}")
    
    async def _data_fetch_loop(self):
        """数据获取循环，每秒5次发送请求"""
        while True:
            try:
                # 发送数据获取请求
                if self.client:
                    self.client.publish("/data/data-get", "get_data")
                    _LOGGER.debug("Sent data request to /data/data-get")
                
                # 等待 0.2 秒（每秒5次）
                await asyncio.sleep(0.2)
                
            except Exception as e:
                _LOGGER.error(f"Error in data fetch loop: {e}")
                await asyncio.sleep(1)  # 出错时等待更长时间
    
    def register_sensor(self, sensor_id: str, sensor_entity):
        """注册传感器实体"""
        self.sensors[sensor_id] = sensor_entity
        _LOGGER.info(f"Registered sensor: {sensor_id}")
    
    async def stop(self):
        """停止 MQTT 客户端和数据获取任务"""
        if self.data_task:
            self.data_task.cancel()
            try:
                await self.data_task
            except asyncio.CancelledError:
                pass
        
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
        
        _LOGGER.info("MQTT Data Manager stopped")

# 全局数据管理器实例
_data_manager = None

# 传感器配置（对应 main.py 中的传感器定义）
SENSORS = {
    "solar_power": {
        "name": "Solar Power",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:solar-power",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "home_power": {
        "name": "Home Power",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:home-lightning-bolt",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "grid_import": {
        "name": "Grid Import",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:transmission-tower-import",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "grid_export": {
        "name": "Grid Export",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:transmission-tower-export",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "battery_charge": {
        "name": "Battery Charge",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:battery-charging",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "battery_discharge": {
        "name": "Battery Discharge",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:battery-minus",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "battery_soc": {
        "name": "Battery State of Charge",
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
    """Set up Energy Monitor sensors from a config entry."""
    global _data_manager
    
    _LOGGER.info("Setting up Energy Monitor sensors")
    
    # 获取配置数据
    config = hass.data[DOMAIN][config_entry.entry_id]
    topic_prefix = config.get("topic_prefix", "homeassistant/sensor")
    mqtt_broker = config.get("mqtt_broker", "192.168.0.101")
    mqtt_port = config.get("mqtt_port", 1883)
    
    # 创建全局数据管理器（如果还没有创建）
    if _data_manager is None:
        _data_manager = MQTTDataManager(hass, topic_prefix, mqtt_broker, mqtt_port)
        await _data_manager.start()
    
    # 创建所有传感器实体
    entities = []
    for sensor_id, sensor_config in SENSORS.items():
        entity = EnergyMonitorSensor(
            sensor_id=sensor_id,
            name=sensor_config["name"],
            unit=sensor_config["unit"],
            icon=sensor_config["icon"],
            device_class=sensor_config["device_class"],
            state_class=sensor_config["state_class"],
            topic_prefix=topic_prefix,
        )
        entities.append(entity)
        
        # 将传感器注册到数据管理器
        _data_manager.register_sensor(sensor_id, entity)
    
    async_add_entities(entities, True)
    _LOGGER.info(f"Added {len(entities)} Energy Monitor sensors")


class EnergyMonitorSensor(SensorEntity):
    """Representation of an Energy Monitor Sensor."""

    def __init__(
        self,
        sensor_id: str,
        name: str,
        unit: str,
        icon: str,
        device_class: SensorDeviceClass,
        state_class: SensorStateClass,
        topic_prefix: str,
    ) -> None:
        """Initialize the sensor."""
        self._sensor_id = sensor_id
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_unique_id = f"energy_monitor_{sensor_id}"
        self._topic = f"{topic_prefix}/{sensor_id}/state"
        self._attr_native_value = None
        self._attr_available = False

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    async def async_added_to_hass(self) -> None:
        """Set up the sensor."""
        _LOGGER.info(f"Energy Monitor sensor {self._sensor_id} added to Home Assistant")
        # 注意：现在数据通过 MQTTDataManager 处理，不再直接订阅 MQTT topic
    
    async def _update_state(self, value: Any) -> None:
        """更新传感器状态（由 MQTTDataManager 调用）"""
        try:
            # 确保值是数字类型
            if isinstance(value, (int, float)):
                self._attr_native_value = value
                self._attr_available = True
                self.async_write_ha_state()
                _LOGGER.debug(f"Updated {self._sensor_id} with value: {value}")
            else:
                _LOGGER.warning(f"Invalid value type for {self._sensor_id}: {type(value)} - {value}")
        except Exception as e:
            _LOGGER.error(f"Error updating sensor {self._sensor_id}: {e}")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {
            "sensor_id": self._sensor_id,
            "mqtt_topic": self._topic,
        }


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload the sensor platform."""
    global _data_manager
    
    _LOGGER.info("Unloading Energy Monitor sensors")
    
    # 停止数据管理器
    if _data_manager is not None:
        await _data_manager.stop()
        _data_manager = None
    
    return True

