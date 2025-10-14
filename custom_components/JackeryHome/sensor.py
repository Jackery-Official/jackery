"""JackeryHome Sensor Platform."""
import asyncio
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
from homeassistant.const import UnitOfPower, UnitOfEnergy, PERCENTAGE

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

# 传感器配置
SENSORS = {
    # 功率传感器（实时监测）
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
    # 能源传感器（用于能源仪表板）
    "solar_energy": {
        "name": "Solar Energy",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "icon": "mdi:solar-power",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "home_energy": {
        "name": "Home Energy",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "icon": "mdi:home-lightning-bolt",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "grid_import_energy": {
        "name": "Grid Import Energy",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "icon": "mdi:transmission-tower-import",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "grid_export_energy": {
        "name": "Grid Export Energy",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "icon": "mdi:transmission-tower-export",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "battery_charge_energy": {
        "name": "Battery Charge Energy",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "icon": "mdi:battery-charging",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "battery_discharge_energy": {
        "name": "Battery Discharge Energy",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "icon": "mdi:battery-minus",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
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
            "sw_version": "1.0.5",
        }
        self._topic = f"{topic_prefix}/{sensor_id}/state"
        self._data_topic = "device/data"
        self._data_get_topic = "device/data-get"
        self._attr_native_value = None
        self._attr_available = False
        self._data_task = None
        
        # 能源累积相关属性
        self._is_energy_sensor = device_class == SensorDeviceClass.ENERGY
        self._last_power_value = 0.0
        self._last_update_time = None
        self._total_energy = 0.0

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    async def async_added_to_hass(self) -> None:
        """Set up the sensor."""
        _LOGGER.info(f"JackeryHome sensor {self._sensor_id} added to Home Assistant")
        
        # 订阅 device/data topic 处理消息回调
        @callback
        def data_message_received(msg):
            """Handle new MQTT messages from device/data topic."""
            try:
                payload = msg.payload
                if isinstance(payload, bytes):
                    payload = payload.decode("utf-8")
                
                _LOGGER.debug(f"Received data message for {self._sensor_id}: {payload}")
                
                # 尝试解析 JSON
                try:
                    data = json.loads(payload)
                    # 根据传感器ID从数据中提取对应的值
                    if isinstance(data, dict) and self._sensor_id in data:
                        value = data[self._sensor_id]
                    elif isinstance(data, dict) and "value" in data:
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
                
                # 处理能源传感器累积计算
                if self._is_energy_sensor:
                    value = self._calculate_energy_accumulation(value)
                
                # 更新传感器状态
                self._attr_native_value = value
                self._attr_available = True
                self.async_write_ha_state()
                
                _LOGGER.debug(f"Updated {self._sensor_id} with value: {value}")
                
            except Exception as e:
                _LOGGER.error(f"Error processing data message for {self._sensor_id}: {e}")

        # 订阅 device/data topic
        await ha_mqtt.async_subscribe(
            self.hass, 
            self._data_topic, 
            data_message_received, 
            1
        )
        
        _LOGGER.info(f"Subscribed to MQTT topic: {self._data_topic}")
        
        # 启动定时器，每隔5秒向 device/data-get 发送数据获取请求
        self._data_task = asyncio.create_task(self._periodic_data_request())
        
    def _calculate_energy_accumulation(self, power_value: float) -> float:
        """计算能源累积值（从功率转换为能源）"""
        import time
        
        try:
            current_time = time.time()
            power_watts = float(power_value)
            
            # 如果是第一次更新，只记录时间和功率值
            if self._last_update_time is None:
                self._last_update_time = current_time
                self._last_power_value = power_watts
                return self._total_energy
            
            # 计算时间差（小时）
            time_diff_hours = (current_time - self._last_update_time) / 3600.0
            
            # 计算能源增量（kWh）
            # 使用梯形积分法：平均功率 × 时间
            avg_power = (self._last_power_value + power_watts) / 2.0
            energy_increment = (avg_power * time_diff_hours) / 1000.0  # 转换为kWh
            
            # 累积能源值
            self._total_energy += energy_increment
            
            # 更新记录
            self._last_update_time = current_time
            self._last_power_value = power_watts
            
            _LOGGER.debug(f"Energy accumulation for {self._sensor_id}: "
                         f"power={power_watts}W, time_diff={time_diff_hours:.4f}h, "
                         f"increment={energy_increment:.6f}kWh, total={self._total_energy:.6f}kWh")
            
            return self._total_energy
            
        except (ValueError, TypeError) as e:
            _LOGGER.error(f"Error calculating energy accumulation for {self._sensor_id}: {e}")
            return self._total_energy

    async def _periodic_data_request(self) -> None:
        """Periodically send data request to device/data-get topic."""
        while True:
            try:
                # 发送数据获取请求
                await ha_mqtt.async_publish(
                    self.hass,
                    self._data_get_topic,
                    json.dumps({"request": "data", "sensor": self._sensor_id}),
                    1,
                    False
                )
                _LOGGER.debug(f"Sent data request for {self._sensor_id} to {self._data_get_topic}")
                
                # 等待5秒
                await asyncio.sleep(5)
                
            except Exception as e:
                _LOGGER.error(f"Error in periodic data request for {self._sensor_id}: {e}")
                # 出错时等待5秒再重试
                await asyncio.sleep(5)

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when sensor is removed."""
        if self._data_task and not self._data_task.done():
            self._data_task.cancel()
            try:
                await self._data_task
            except asyncio.CancelledError:
                pass
        _LOGGER.info(f"JackeryHome sensor {self._sensor_id} removed from Home Assistant")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {
            "sensor_id": self._sensor_id,
            "mqtt_topic": self._topic,
            "data_topic": self._data_topic,
            "data_get_topic": self._data_get_topic,
        }