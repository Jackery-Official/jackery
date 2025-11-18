"""JackeryHome Sensor Platform."""
import asyncio
import json
import logging
import time
import random
from typing import Any, Callable

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


class JackeryDataCoordinator:
    """协调器：管理MQTT订阅和数据获取，供所有传感器实体共享使用."""

    def __init__(self, hass: HomeAssistant, topic_prefix: str) -> None:
        """初始化协调器."""
        self.hass = hass
        self._topic_prefix = topic_prefix
        self._data_topic = "v1/iot_gw/gw/data"  # 接收设备响应数据的主题
        self._data_get_topic = "v1/iot_gw/cloud/data"  # 发送数据请求的主题
        self._gw_lwt_topic = "v1/iot_gw/gw_lwt"  # LWT 主题
        self._device_sn = "26392658575364"  # 默认设备序列号
        self._sensors = {}  # 存储所有传感器实体的引用 {sensor_id: entity}
        self._data_task = None  # 定时数据请求任务
        self._subscribed = False  # 标记是否已订阅

    def register_sensor(self, sensor_id: str, entity: "JackeryHomeSensor") -> None:
        """注册传感器实体到协调器."""
        self._sensors[sensor_id] = entity
        _LOGGER.debug(f"Registered sensor {sensor_id} to coordinator")

    def unregister_sensor(self, sensor_id: str) -> None:
        """从协调器注销传感器实体."""
        if sensor_id in self._sensors:
            del self._sensors[sensor_id]
            _LOGGER.debug(f"Unregistered sensor {sensor_id} from coordinator")

    async def async_start(self) -> None:
        """启动协调器：订阅MQTT主题并开始定期请求数据."""
        if self._subscribed:
            return
        
        try:
            # 订阅 LWT topic
            @callback
            def lwt_message_received(msg):
                """处理 LWT 消息."""
                self._handle_lwt_message(msg)
            
            await ha_mqtt.async_subscribe(
                self.hass,
                self._gw_lwt_topic,
                lwt_message_received,
                1
            )
            _LOGGER.info(f"Coordinator subscribed to LWT topic: {self._gw_lwt_topic}")
            
            # 订阅数据响应 topic
            @callback
            def data_message_received(msg):
                """处理数据响应消息."""
                self._handle_data_message(msg)
            
            await ha_mqtt.async_subscribe(
                self.hass,
                self._data_topic,
                data_message_received,
                1
            )
            _LOGGER.info(f"Coordinator subscribed to data topic: {self._data_topic}")
            
            self._subscribed = True
            
            # 启动定时请求任务
            self._data_task = asyncio.create_task(self._periodic_data_request())
            
        except Exception as e:
            _LOGGER.error(
                f"Failed to start coordinator. MQTT may not be connected: {e}. "
                "Please check your MQTT integration settings."
            )

    async def async_stop(self) -> None:
        """停止协调器：取消定时任务."""
        if self._data_task and not self._data_task.done():
            self._data_task.cancel()
            try:
                await self._data_task
            except asyncio.CancelledError:
                pass
        _LOGGER.info("Coordinator stopped")

    def _handle_lwt_message(self, msg) -> None:
        """处理 LWT 消息，获取设备序列号."""
        try:
            payload = msg.payload
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8")
            
            _LOGGER.debug(f"Coordinator received LWT message: {payload}")
            
            data = json.loads(payload)
            if isinstance(data, dict) and "gw_sn" in data:
                self._device_sn = data["gw_sn"]
                _LOGGER.info(f"Device serial number updated: {self._device_sn}")
                
        except Exception as e:
            _LOGGER.error(f"Error processing LWT message: {e}")

    def _handle_data_message(self, msg) -> None:
        """处理数据响应消息，解析后分发给所有传感器."""
        try:
            payload = msg.payload
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8")

            _LOGGER.debug(f"Coordinator received data message: {payload}")

            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                _LOGGER.warning(f"Failed to parse data message: {payload}")
                return

            # 处理 data_get 响应格式
            if isinstance(data, dict) and data.get("cmd") == "data_get":
                self._parse_and_distribute_data(data)
                
        except Exception as e:
            _LOGGER.error(f"Error processing data message: {e}")

    def _parse_and_distribute_data(self, data: dict) -> None:
        """解析 data_get 响应并分发给对应的传感器."""
        try:
            info = data.get("info", {})
            dev_list = info.get("dev_list", [])
            
            # 遍历所有设备和meter
            for dev in dev_list:
                meter_list = dev.get("meter_list", [])
                for meter in meter_list:
                    # 响应格式：meter 是 [meter_sn, meter_value]
                    if not isinstance(meter, (list, tuple)) or len(meter) < 2:
                        continue
                    
                    meter_sn = str(meter[0])
                    try:
                        meter_value_float = float(meter[1])
                        # 如果小数部分为 0，转换为 int
                        meter_value = (
                            int(meter_value_float) 
                            if meter_value_float == int(meter_value_float) 
                            else meter_value_float
                        )
                    except (ValueError, TypeError):
                        _LOGGER.debug(f"Invalid meter value: {meter[1]}")
                        continue
                    
                    # 根据 meter_sn 找到对应的传感器并更新
                    self._update_sensors_by_meter_sn(meter_sn, meter_value)
                    
        except Exception as e:
            _LOGGER.error(f"Error parsing and distributing data: {e}")

    def _update_sensors_by_meter_sn(self, meter_sn: str, meter_value: float) -> None:
        """根据 meter_sn 更新对应的传感器."""
        # 遍历所有传感器，找到匹配的 meter_sn
        for sensor_id, entity in self._sensors.items():
            if str(entity._meter_sn) == meter_sn:
                # 处理特殊传感器的值（如正负分离）
                processed_value = entity._process_meter_value(meter_value)
                entity._update_sensor_value(processed_value)

    def _construct_data_get_request(self) -> dict:
        """构造 data_get 请求，包含所有传感器的 meter_sn."""
        # 收集所有唯一的 meter_sn
        meter_sns = set()
        for entity in self._sensors.values():
            if entity._meter_sn:
                meter_sns.add(entity._meter_sn)
        
        return {
            "cmd": "data_get",
            "gw_sn": self._device_sn or "",
            "timestamp": str(int(time.time() * 1000)),
            "token": str(random.randint(1000, 9999)),
            "info": {
                "dev_list": [
                    {
                        "dev_sn": f"ems_{self._device_sn}" if self._device_sn else "ems_",
                        "meter_list": list(meter_sns),  # 一次性请求所有 meter_sn
                    }
                ]
            }
        }

    async def _periodic_data_request(self) -> None:
        """定期发送数据请求（所有传感器共用一个请求）."""
        _LOGGER.info("Coordinator starting periodic data request...")
        await asyncio.sleep(2)  # 等待 MQTT 连接建立
        
        while True:
            try:
                if not self._device_sn:
                    _LOGGER.debug("Device serial number not available, waiting...")
                    await asyncio.sleep(REQUEST_INTERVAL)
                    continue
                
                if not self._sensors:
                    _LOGGER.debug("No sensors registered yet, waiting...")
                    await asyncio.sleep(REQUEST_INTERVAL)
                    continue
                
                try:
                    # 构造并发送包含所有 meter_sn 的请求
                    request_data = self._construct_data_get_request()
                    await ha_mqtt.async_publish(
                        self.hass,
                        self._data_get_topic,
                        json.dumps(request_data, ensure_ascii=False),
                        1,
                        False
                    )
                    _LOGGER.debug(
                        f"Coordinator sent data_get request for {len(self._sensors)} sensors "
                        f"to {self._data_get_topic}"
                    )
                except Exception as mqtt_error:
                    _LOGGER.warning(
                        f"MQTT publish failed: {mqtt_error}. "
                        f"Please check MQTT broker connection. "
                        f"Will retry in {REQUEST_INTERVAL} seconds..."
                    )
                
                await asyncio.sleep(REQUEST_INTERVAL)
                
            except asyncio.CancelledError:
                _LOGGER.info("Coordinator periodic data request task cancelled")
                raise
            except Exception as e:
                _LOGGER.error(f"Unexpected error in coordinator periodic data request: {e}")
                await asyncio.sleep(REQUEST_INTERVAL)


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
    
    # 创建协调器（全局唯一，所有传感器共享）
    coordinator = JackeryDataCoordinator(hass, topic_prefix)
    
    # 将协调器存储到 hass.data 中，供其他地方使用
    hass.data[DOMAIN][config_entry.entry_id]["coordinator"] = coordinator
    
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
            coordinator=coordinator,  # 传入协调器
        )
        entities.append(entity)
    
    # 添加实体
    async_add_entities(entities)
    
    # 启动协调器（在所有传感器添加后）
    await coordinator.async_start()
    
    _LOGGER.info(f"Added {len(entities)} JackeryHome sensors with shared coordinator")


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
        coordinator: JackeryDataCoordinator,
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
        self._attr_native_value = None
        self._attr_available = False
        self._attr_should_poll = False
        self._attr_has_entity_name =False 
        self._coordinator = coordinator  # 协调器引用
        
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
        elif self._sensor_id == "battery_soc":
            # Battery SOC 需要乘以 0.1 转换为百分比
            return meter_value * 0.1
        else:
            return meter_value

    def _update_sensor_value(self, value: Any) -> None:
        """更新传感器值并通知 Home Assistant（由协调器调用）."""
        self._attr_native_value = value
        self._attr_available = True
        self.async_write_ha_state()
        _LOGGER.debug(f"Updated {self._sensor_id} with value: {value}")

    async def async_added_to_hass(self) -> None:
        """传感器添加到 Home Assistant 时，注册到协调器."""
        await super().async_added_to_hass()
        
        # 注册到协调器
        self._coordinator.register_sensor(self._sensor_id, self)
        _LOGGER.info(f"JackeryHome sensor {self._sensor_id} registered to coordinator")

    async def async_will_remove_from_hass(self) -> None:
        """传感器从 Home Assistant 移除时，从协调器注销."""
        # 从协调器注销
        self._coordinator.unregister_sensor(self._sensor_id)
        _LOGGER.info(f"JackeryHome sensor {self._sensor_id} unregistered from coordinator")
        
        await super().async_will_remove_from_hass()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {
            "sensor_id": self._sensor_id,
            "meter_sn": self._meter_sn,
            "device_sn": self._coordinator._device_sn,
        }