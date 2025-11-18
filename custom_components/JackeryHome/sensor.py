"""JackeryHome Sensor Platform."""
import asyncio
import json
import logging
import time
import random
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

# Meter SN 映射（传感器ID到meter_sn的映射）
METER_SN_MAP = {
    "battery_soc": 21548033,
    "solar_energy": 16961537,
    "home_energy": 16936961,
    "grid_import_energy": 16959489,
    "grid_export_energy": 16960513,
    "battery_charge_energy": 16952321,
    "battery_discharge_energy": 16953345,
    "solar_power": 1026001,
    "home_power": 21171201,
    "grid_import_power": 16930817,
    "grid_export_power": 16930817,
    "battery_charge_power": 16931841,
    "battery_discharge_power": 16931841,
}

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
        self._data_topic = "v1/iot_gw/cloud/data/#"  # 接收设备响应数据的主题
        self._data_get_topic = "v1/iot_gw/cloud/data"  # 发送数据请求的基础主题（需要加上 device_sn）
        self._gw_lwt_topic = "v1/iot_gw/gw_lwt/#"
        self._attr_native_value = None
        self._attr_available = False
        self._data_task = None
        self._device_sn = ""  # 设备序列号（从 LWT 消息中获取）
        # 获取 meter_sn，对于功率传感器，使用对应的 _power 键
        if sensor_id in ["grid_import", "grid_export"]:
            self._meter_sn = METER_SN_MAP.get("grid_import_power", 0)
        elif sensor_id in ["battery_charge", "battery_discharge"]:
            self._meter_sn = METER_SN_MAP.get("battery_charge_power", 0)
        else:
            self._meter_sn = METER_SN_MAP.get(sensor_id, 0)  # 当前传感器的 meter_sn
        
        # 能源传感器标识
        self._is_energy_sensor = device_class == SensorDeviceClass.ENERGY

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    async def async_added_to_hass(self) -> None:
        """Set up the sensor."""
        _LOGGER.info(f"JackeryHome sensor {self._sensor_id} added to Home Assistant")
        
        # 订阅 LWT 主题以获取设备序列号
        @callback
        def lwt_message_received(msg):
            """Handle LWT messages to get device serial number."""
            try:
                payload = msg.payload
                if isinstance(payload, bytes):
                    payload = payload.decode("utf-8")
                
                _LOGGER.debug(f"Received LWT message: {payload}")
                
                try:
                    data = json.loads(payload)
                    if isinstance(data, dict) and "gw_sn" in data:
                        self._device_sn = data["gw_sn"]
                        _LOGGER.info(f"Device serial number updated: {self._device_sn}")
                except json.JSONDecodeError:
                    _LOGGER.warning(f"Failed to parse LWT message: {payload}")
                    
            except Exception as e:
                _LOGGER.error(f"Error processing LWT message: {e}")
        
        # 订阅 device/data topic 处理消息回调
        @callback
        def data_message_received(msg):
            """Handle new MQTT messages from device/data topic."""
            try:
                payload = msg.payload
                if isinstance(payload, bytes):
                    payload = payload.decode("utf-8")
                
                _LOGGER.debug(f"Received data message for {self._sensor_id}: {payload}")
                
                # 尝试解析 data_get 格式的数据
                try:
                    data = json.loads(payload)
                    # 检查是否是 data_get 格式
                    if isinstance(data, dict) and data.get("cmd") == "data_get":
                        value = self._parse_data_get_response(data)
                        if value is not None:
                            self._attr_native_value = value
                            self._attr_available = True
                            self.async_write_ha_state()
                            _LOGGER.debug(f"Updated {self._sensor_id} with value: {value}")
                        else:
                            _LOGGER.debug(f"No matching data found for {self._sensor_id} in data_get response")
                        return
                except json.JSONDecodeError:
                    pass
                
                # 兼容旧格式：尝试解析 JSON
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
                
                # 能源传感器直接使用接收到的累积值，不进行额外计算
                # 设备端已经发送了正确的累积值
                
                # 更新传感器状态
                self._attr_native_value = value
                self._attr_available = True
                self.async_write_ha_state()
                
                _LOGGER.debug(f"Updated {self._sensor_id} with value: {value}")
                
            except Exception as e:
                _LOGGER.error(f"Error processing data message for {self._sensor_id}: {e}")

        # 订阅 LWT topic 以获取设备序列号
        await ha_mqtt.async_subscribe(
            self.hass,
            self._gw_lwt_topic,
            lwt_message_received,
            1
        )
        _LOGGER.info(f"Subscribed to MQTT topic: {self._gw_lwt_topic}")
        
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
        

    def _construct_data_get_request(self) -> dict:
        """构造 data_get 格式的请求数据."""
        data = {
            "cmd": "data_get",
            "gw_sn": self._device_sn if self._device_sn else "",
            "timestamp": str(int(time.time() * 1000)),
            "token": str(random.randint(1000, 9999)),
            "info": {
                "dev_list": [
                    {
                        "dev_sn": "ems_" + self._device_sn if self._device_sn else "ems_",
                        "meter_list": [
                            self._meter_sn,
                        ]
                    }
                ]
            }
        }
        return data
    
    def _parse_data_get_response(self, data: dict) -> Any:
        """解析 data_get 格式的响应数据.
        
        请求格式: meter_list 中只包含 meter_sn (整数)
        响应格式: meter_list 中包含 [meter_sn, meter_value] (列表)
        """
        try:
            cmd = data.get("cmd")
            if cmd != "data_get":
                return None
            
            info = data.get("info", {})
            dev_list = info.get("dev_list", [])
            
            for dev in dev_list:
                meter_list = dev.get("meter_list", [])
                for meter in meter_list:
                    # 响应格式：meter 是 [meter_sn, meter_value] 格式的列表
                    if isinstance(meter, list) and len(meter) >= 2:
                        meter_sn_raw = meter[0]
                        meter_value_raw = meter[1]
                        
                        # 处理 meter_sn：可能是字符串或整数，统一转换为整数进行比较
                        try:
                            meter_sn = int(meter_sn_raw) if isinstance(meter_sn_raw, str) else int(meter_sn_raw)
                        except (ValueError, TypeError):
                            meter_sn = meter_sn_raw
                        
                        # 先转换为 float，然后判断是否可以转换为 int
                        meter_value_float = float(meter_value_raw)
                        # 如果小数部分为 0，则转换为 int，否则保留 float
                        meter_value = int(meter_value_float) if meter_value_float == int(meter_value_float) else meter_value_float
                        
                        # 检查是否匹配当前传感器的 meter_sn（支持字符串和整数比较）
                        if int(meter_sn) == int(self._meter_sn):
                            # 处理特殊逻辑（电网功率和电池功率）
                            if self._sensor_id == "grid_import":
                                # 电网功率：负值为购买，正值为出售
                                if meter_value < 0:
                                    return abs(meter_value)
                                else:
                                    return 0
                            elif self._sensor_id == "grid_export":
                                # 电网功率：负值为购买，正值为出售
                                if meter_value > 0:
                                    return meter_value
                                else:
                                    return 0
                            elif self._sensor_id == "battery_charge":
                                # 电池功率：负值为充电，正值为放电
                                if meter_value < 0:
                                    return abs(meter_value)
                                else:
                                    return 0
                            elif self._sensor_id == "battery_discharge":
                                # 电池功率：负值为充电，正值为放电
                                if meter_value > 0:
                                    return meter_value
                                else:
                                    return 0
                            else:
                                # 其他传感器直接返回值
                                return meter_value
                    # 请求格式：meter 只是 meter_sn (整数)，忽略请求
                    elif isinstance(meter, (int, float)):
                        # 这是请求格式，不是响应，忽略
                        pass
            
            return None
            
        except Exception as e:
            _LOGGER.error(f"Error parsing data_get response: {e}")
            return None
    
    async def _periodic_data_request(self) -> None:
        """Periodically send data request to device/data-get topic."""
        while True:
            try:
                # 如果还没有设备序列号，等待一段时间再重试
                if not self._device_sn:
                    _LOGGER.debug(f"Device serial number not available yet for {self._sensor_id}, waiting...")
                    await asyncio.sleep(5)
                    continue
                
                # 构造 data_get 格式的请求
                request_data = self._construct_data_get_request()
                
                # 发送数据获取请求
                topic = f"{self._data_get_topic}/{self._device_sn}" if self._device_sn else self._data_get_topic
                await ha_mqtt.async_publish(
                    self.hass,
                    topic,
                    json.dumps(request_data, ensure_ascii=False),
                    1,
                    False
                )
                _LOGGER.debug(f"Sent data_get request for {self._sensor_id} (meter_sn: {self._meter_sn}) to {topic}")
                
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
            "meter_sn": self._meter_sn,
            "device_sn": self._device_sn,
        }