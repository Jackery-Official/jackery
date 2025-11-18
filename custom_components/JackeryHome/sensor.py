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

# 常量定义
REQUEST_INTERVAL = 5  # 数据请求间隔（秒）

# Meter SN 映射（传感器ID到meter_sn的映射）
METER_SN_MAP = {
    "battery_soc": "21548033",
    "solar_energy": "16961537",
    "home_energy": "16936961",
    "grid_import_energy": "16959489",
    "grid_export_energy": "16960513",
    "battery_charge_energy": "16952321",
    "battery_discharge_energy": "16953345",
    "solar_power": "1026001",
    "home_power": "21171201",
    "grid_import_power": "16930817",
    "grid_export_power": "16930817",
    "battery_charge_power": "16931841",
    "battery_discharge_power": "16931841",
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
        self._data_topic = "v1/iot_gw/gw/data"  # 接收设备响应数据的主题
        self._data_get_topic = "v1/iot_gw/cloud/data"  # 发送数据请求的基础主题（需要加上 device_sn）
        self._gw_lwt_topic = "v1/iot_gw/gw_lwt"
        self._attr_native_value = None
        self._attr_available = False
        self._data_task = None
        ###TODO: 从 LWT 消息中获取设备序列号
        self._device_sn = "26392658575364"  # 设备序列号（从 LWT 消息中获取）
        self._attr_should_poll = False
        self._attr_has_entity_name = True 
        # 获取 meter_sn，对于功率传感器，使用对应的 _power 键
        meter_sn_key_map = {
            "grid_import": "grid_import_power",
            "grid_export": "grid_export_power",
            "battery_charge": "battery_charge_power",
            "battery_discharge": "battery_discharge_power",
        }
        meter_sn_key = meter_sn_key_map.get(sensor_id, sensor_id)
        self._meter_sn = METER_SN_MAP.get(meter_sn_key, 0)
        
        # 能源传感器标识
        self._is_energy_sensor = device_class == SensorDeviceClass.ENERGY

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    def _handle_lwt_message(self, msg) -> None:
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

    def _process_meter_value(self, meter_value: float) -> float:
        """根据传感器类型处理 meter 值."""
        if self._sensor_id == "grid_import":
            return abs(meter_value) if meter_value < 0 else 0
        elif self._sensor_id == "grid_export":
            return meter_value if meter_value > 0 else 0
        elif self._sensor_id == "battery_charge":
            return abs(meter_value) if meter_value < 0 else 0
        elif self._sensor_id == "battery_discharge":
            return meter_value if meter_value > 0 else 0
        else:
            return meter_value

    def _handle_data_message(self, msg) -> None:
        """Handle new MQTT messages from device/data topic."""
        try:
            payload = msg.payload
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8")

            _LOGGER.debug(f"Received data message for {self._sensor_id}: {payload}")

            data = None
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                data = None

            # 处理 data_get 响应
            if isinstance(data, dict) and data.get("cmd") == "data_get":
                value = self._parse_data_get_response(data)
                if value is not None:
                    self._update_sensor_value(value)
                return

            # 兼容旧格式的数据
            if isinstance(data, dict):
                if self._sensor_id in data:
                    value = data[self._sensor_id]
                elif "value" in data:
                    value = data["value"]
                else:
                    value = data
            else:
                try:
                    value = float(payload)
                except ValueError:
                    self._attr_available = False
                    self.async_write_ha_state()
                    return

            if value is not None:
                self._update_sensor_value(value)

        except Exception as e:
            _LOGGER.error(f"Error processing data message for {self._sensor_id}: {e}")

    def _update_sensor_value(self, value: Any) -> None:
        """更新传感器值并通知 Home Assistant."""
        self._attr_native_value = value
        self._attr_available = True
        self.async_write_ha_state()
        _LOGGER.debug(f"Updated {self._sensor_id} with value: {value}")

    async def async_added_to_hass(self) -> None:
        """Set up the sensor."""
        await super().async_added_to_hass()
        
        _LOGGER.info(f"JackeryHome sensor {self._sensor_id} added to Home Assistant")
        
        # 创建 LWT 消息处理回调
        @callback
        def lwt_message_received(msg):
            """Callback wrapper for LWT messages."""
            self._handle_lwt_message(msg)
        
        # 创建数据消息处理回调
        @callback
        def data_message_received(msg):
            """Callback wrapper for data messages."""
            self._handle_data_message(msg)
        
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
        return {
            "cmd": "data_get",
            "gw_sn": self._device_sn or "",
            "timestamp": str(int(time.time() * 1000)),
            "token": str(random.randint(1000, 9999)),
            "info": {
                "dev_list": [
                    {
                        "dev_sn": f"ems_{self._device_sn}" if self._device_sn else "ems_",
                        "meter_list": [self._meter_sn],
                    }
                ]
            }
        }
    
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
            target_meter_sn = str(self._meter_sn)
            
            for dev in dev_list:
                meter_list = dev.get("meter_list", [])
                for meter in meter_list:
                    # 响应格式：meter 是 [meter_sn, meter_value] 格式的列表
                    if not isinstance(meter, (list, tuple)) or len(meter) < 2:
                        continue
                    
                    meter_sn = str(meter[0])
                    if meter_sn != target_meter_sn:
                        continue
                    
                    try:
                        meter_value_float = float(meter[1])
                    except (ValueError, TypeError):
                        _LOGGER.debug(f"Invalid meter value for {self._sensor_id}: {meter[1]}")
                        continue
                    
                    # 如果小数部分为 0，则转换为 int，否则保留 float
                    meter_value = int(meter_value_float) if meter_value_float == int(meter_value_float) else meter_value_float
                    
                    # 使用统一的方法处理 meter 值
                    return self._process_meter_value(meter_value)
            
            _LOGGER.debug(f"No matching data found for {self._sensor_id} in data_get payload")
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
                    _LOGGER.debug(
                        f"Device serial number not available yet for {self._sensor_id}, waiting..."
                    )
                    await asyncio.sleep(REQUEST_INTERVAL)
                    continue
                
                # 构造并发送 data_get 格式的请求
                request_data = self._construct_data_get_request()
                await ha_mqtt.async_publish(
                    self.hass,
                    self._data_get_topic,
                    json.dumps(request_data, ensure_ascii=False),
                    1,
                    False
                )
                _LOGGER.debug(
                    f"Sent data_get request for {self._sensor_id} "
                    f"(meter_sn: {self._meter_sn}) to {self._data_get_topic}"
                )
                
                await asyncio.sleep(REQUEST_INTERVAL)
                
            except Exception as e:
                _LOGGER.error(f"Error in periodic data request for {self._sensor_id}: {e}")
                await asyncio.sleep(REQUEST_INTERVAL)

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when sensor is removed."""
        if self._data_task and not self._data_task.done():
            self._data_task.cancel()
            try:
                await self._data_task
            except asyncio.CancelledError:
                pass
        _LOGGER.info(f"JackeryHome sensor {self._sensor_id} removed from Home Assistant")
        
        await super().async_will_remove_from_hass()

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