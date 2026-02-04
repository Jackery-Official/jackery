"""Jackery Sensor Platform."""
import asyncio
import json
import logging
import random
import re
import time
from typing import Any, Callable

from homeassistant.components import mqtt as ha_mqtt
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

# 常量定义
REQUEST_INTERVAL = 10  # 数据请求间隔（秒）

# 传感器配置
SENSORS = {
    # 电池相关
    "battery_soc": {
        "json_key": "batSoc",
        "name": "Battery SOC",
        "unit": PERCENTAGE,
        "icon": "mdi:battery-50",
        "device_class": SensorDeviceClass.BATTERY,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "battery_charge_power": {
        "json_key": "batInPw",
        "name": "Battery Charge Power",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:battery-charging",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "battery_discharge_power": {
        "json_key": "batOutPw",
        "name": "Battery Discharge Power",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:battery-minus",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "battery_temperature": {
        "json_key": "cellTemp",
        "name": "Battery Temperature",
        "unit": UnitOfTemperature.CELSIUS,
        "icon": "mdi:thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "battery_count": {
        "json_key": "batNum",
        "name": "Battery Count",
        "unit": None,
        "icon": "mdi:battery-multiple",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    # 电池能量统计
    "battery_charge_energy": {
        "json_key": "batChgEgy",
        "name": "Battery Charge Energy",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "icon": "mdi:battery-plus",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "scale": 0.01,
    },
    "battery_discharge_energy": {
        "json_key": "batDisChgEgy",
        "name": "Battery Discharge Energy",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "icon": "mdi:battery-minus",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "scale": 0.01,
    },

    # 太阳能
    "solar_power": {
        "json_key": "pvPw",
        "name": "Solar Power",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:solar-power",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "solar_energy": {
        "json_key": "pvEgy",
        "name": "Solar Energy",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "icon": "mdi:solar-power",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "scale": 0.01,
    },
    "solar_power_pv1": {
        "json_key": "pv1",
        "name": "Solar Power PV1",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:solar-panel",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "solar_energy_pv1": {
        "json_key": "pv1Egy",
        "name": "Solar Energy PV1",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "icon": "mdi:solar-panel",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "scale": 0.01,
    },
    "solar_power_pv2": {
        "json_key": "pv2",
        "name": "Solar Power PV2",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:solar-panel",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "solar_energy_pv2": {
        "json_key": "pv2Egy",
        "name": "Solar Energy PV2",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "icon": "mdi:solar-panel",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "scale": 0.01,
    },
    "solar_power_pv3": {
        "json_key": "pv3",
        "name": "Solar Power PV3",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:solar-panel",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "solar_energy_pv3": {
        "json_key": "pv3Egy",
        "name": "Solar Energy PV3",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "icon": "mdi:solar-panel",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "scale": 0.01,
    },
    "solar_power_pv4": {
        "json_key": "pv4",
        "name": "Solar Power PV4",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:solar-panel",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "solar_energy_pv4": {
        "json_key": "pv4Egy",
        "name": "Solar Energy PV4",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "icon": "mdi:solar-panel",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "scale": 0.01,
    },

    # 电网相关
    "grid_import_power": { # Grid -> System (outOngridPw)
        "json_key": "inOngridPw",
        "name": "Grid Import Power",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:transmission-tower-import",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "grid_import_energy": {
        "json_key": "inOngridEgy",
        "name": "Grid Import Energy",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "icon": "mdi:transmission-tower-import",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "scale": 0.01,
    },
    "grid_export_power": { # System -> Grid/Home (inOngirdPw)
        "json_key": "outOngridPw",
        "name": "Grid Export Power",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:transmission-tower-export",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "grid_export_energy": {
        "json_key": "outOngridEgy",
        "name": "Grid Export Energy",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "icon": "mdi:transmission-tower-export",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "scale": 0.01,
    },
    "max_output_power": {
        "json_key": "maxOutPw",
        "name": "Max Output Power (OnGrid)",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:speedometer",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },

    # EPS (离网输出)
    "eps_output_power": {
        "json_key": "swEpsOutPw",
        "name": "EPS Output Power",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:power-plug",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "eps_output_energy": {
        "json_key": "outEpsEgy",
        "name": "EPS Output Energy",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "icon": "mdi:power-plug",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "scale": 0.01,
    },
    "eps_input_power": {
        "json_key": "swEpsInPw",
        "name": "EPS Input Power",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:power-plug",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "eps_input_energy": {
        "json_key": "inEpsEgy",
        "name": "EPS Input Energy",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "icon": "mdi:power-plug",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "scale": 0.01,
    },
    "eps_state": {
         "json_key": "swEpsState",
         "name": "EPS State",
         "unit": None,
         "icon": "mdi:power-settings",
         "device_class": None,
         "state_class": None, # 1-Normal, 0-Abnormal
    },
    "eps_switch": {
         "json_key": "swEps",
         "name": "EPS Switch Status",
         "unit": None,
         "icon": "mdi:toggle-switch",
         "device_class": None,
         "state_class": None, # 1-On, 0-Off
    },

    # Limits & Settings & Status
    "soc_charge_limit": {
        "json_key": "socChgLimit",
        "name": "SOC Charge Limit",
        "unit": PERCENTAGE,
        "icon": "mdi:battery-arrow-up",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "soc_discharge_limit": {
        "json_key": "socDischgLimit",
        "name": "SOC Discharge Limit",
        "unit": PERCENTAGE,
        "icon": "mdi:battery-arrow-down",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "is_auto_standby": {
        "json_key": "isAutoStandby",
        "name": "Auto Standby Allowed",
        "unit": None,
        "icon": "mdi:power-sleep",
        "device_class": None,
        "state_class": None, # 1-Allowed, 0-Not Allowed
    },
    "auto_standby_status": {
        "json_key": "autoStandby",
        "name": "Auto Standby Status",
        "unit": None,
        "icon": "mdi:power-sleep",
        "device_class": None,
        "state_class": None, # 0-Invalid, 1-Sleep/Off, 2-On
    },
    
    # Calculated Sensors
    "home_power": {
        "json_key": "calc_home_power",
        "name": "Home Power",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:home-lightning-bolt",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "battery_net_power": {
        "json_key": "calc_batt_net_power",
        "name": "Battery Net Power",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:battery-sync",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "calc_battery_charge_power": {
        "json_key": "calc_battery_charge_power",
        "name": "Battery Charge Power (Calc)",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:battery-charging",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "calc_battery_discharge_power": {
        "json_key": "calc_battery_discharge_power",
        "name": "Battery Discharge Power (Calc)",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:battery-minus",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "grid_net_power": {
        "json_key": "calc_grid_net_power",
        "name": "Grid Net Power",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:transmission-tower",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    # 更多能量流向统计
    "ac_to_battery_energy": {
        "json_key": "acOtBatEgy",
        "name": "AC to Battery Energy",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "icon": "mdi:battery-arrow-up",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "scale": 0.01,
    },
    "pv_to_battery_energy": {
        "json_key": "pvOtBatEgy",
        "name": "PV to Battery Energy",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "icon": "mdi:solar-power-variant",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "scale": 0.01,
    },
    "pv_to_ac_energy": {
        "json_key": "pvOtAcEgy",
        "name": "PV to AC Energy",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "icon": "mdi:solar-panel",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "scale": 0.01,
    },
    "pv_to_grid_energy": {
        "json_key": "pvOtOngridEgy",
        "name": "PV to Grid Energy",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "icon": "mdi:transmission-tower-export",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "scale": 0.01,
    },
    "grid_to_ac_load_energy": {
        "json_key": "ongridOtAcLoadEgy",
        "name": "Grid to AC Load Energy",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "icon": "mdi:home-import-outline",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "scale": 0.01,
    },
    "battery_to_ac_energy": {
        "json_key": "batOtAcEgy",
        "name": "Battery to AC Energy",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "icon": "mdi:battery-arrow-down",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "scale": 0.01,
    },
    "battery_to_grid_energy": {
        "json_key": "batOtGridEgy",
        "name": "Battery to Grid Energy",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "icon": "mdi:transmission-tower-export",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "scale": 0.01,
    },
    "grid_to_battery_energy": {
        "json_key": "ongridOtBatEgy",
        "name": "Grid to Battery Energy",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "icon": "mdi:battery-arrow-up",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "scale": 0.01,
    },
}

# 子设备传感器配置
SUBDEVICE_SENSORS = {
    # 智能插座 (devType=6 or 1)
    "plug": {
        "power": {
            "key": "outPw", # Fallback to 'power'
            "name": "Power",
            "unit": UnitOfPower.WATT,
            "device_class": SensorDeviceClass.POWER,
            "state_class": SensorStateClass.MEASUREMENT,
            "icon": "mdi:power-socket-eu",
        },
        "energy": {
            "key": "totalEgy",
            "name": "Energy",
            "unit": UnitOfEnergy.KILO_WATT_HOUR,
            "device_class": SensorDeviceClass.ENERGY,
            "state_class": SensorStateClass.TOTAL_INCREASING,
            "icon": "mdi:lightning-bolt",
            "scale": 0.01,
        },
    },
    # CT / Smart Meter (devType=2)
    "ct": {
        "power": {
            "key": "TphasePw", # Fallback to sum of phases
            "name": "Power",
            "unit": UnitOfPower.WATT,
            "device_class": SensorDeviceClass.POWER,
            "state_class": SensorStateClass.MEASUREMENT,
            "icon": "mdi:current-ac",
        },
        "energy_import": {
            "key": "TphaseEgy", # Total Forward Active Energy
            "name": "Energy Import",
            "unit": UnitOfEnergy.KILO_WATT_HOUR,
            "device_class": SensorDeviceClass.ENERGY,
            "state_class": SensorStateClass.TOTAL_INCREASING,
            "icon": "mdi:transmission-tower-import",
            "scale": 0.01, # Assumption
        },
        "energy_export": {
            "key": "TnphaseEgy", # Total Reverse Active Energy
            "name": "Energy Export",
            "unit": UnitOfEnergy.KILO_WATT_HOUR,
            "device_class": SensorDeviceClass.ENERGY,
            "state_class": SensorStateClass.TOTAL_INCREASING,
            "icon": "mdi:transmission-tower-export",
            "scale": 0.01, # Assumption
        },
    },
}


class JackeryDataCoordinator:
    """协调器：管理MQTT订阅和数据获取，供所有传感器实体共享使用."""

    def __init__(self, hass: HomeAssistant, topic_prefix: str, token: str, mqtt_host: str, device_sn: str) -> None:
        """初始化协调器."""
        self.hass = hass
        self._topic_prefix = topic_prefix
        self._token = token
        self._mqtt_host = mqtt_host
        self._device_sn = device_sn
        self._topic_root = topic_prefix

        self._sensors = {}  # {sensor_id: entity}
        self._data_task = None
        self._subscribed = False
        self._last_update_time = time.time()

        self._known_plugs = set() # Set of known plug SNs
        self._subdevice_missing_since = {} # {sn: timestamp} for deletion delay
        self.add_entities_callback = None # Callback to add new entities
        self.add_switch_entities_callback = None # Callback to add new switch entities
        self._data_cache = {} # Cache for merged data from status and events

        # Topic patterns
        self._topic_status_wildcard = f"{self._topic_root}/device/+/status"
        self._topic_event_wildcard = f"{self._topic_root}/device/+/event"

    def register_sensor(self, sensor_id: str, entity: "JackerySensor") -> None:
        """注册传感器实体."""
        self._sensors[sensor_id] = entity

    def unregister_sensor(self, sensor_id: str) -> None:
        """注销传感器实体."""
        if sensor_id in self._sensors:
            del self._sensors[sensor_id]

    async def async_start(self) -> None:
        """启动协调器."""
        if self._subscribed:
            return

        try:
            # 订阅状态主题 (Wildcard) 以发现设备和接收数据
            @callback
            def message_received(msg):
                self._handle_message(msg)

            await ha_mqtt.async_subscribe(
                self.hass,
                self._topic_status_wildcard,
                message_received,
                1
            )
            _LOGGER.info(f"Coordinator subscribed to: {self._topic_status_wildcard}")

            # Subscribe to event topic for sub-device data (Type 101)
            await ha_mqtt.async_subscribe(
                self.hass,
                self._topic_event_wildcard,
                message_received,
                1
            )
            _LOGGER.info(f"Coordinator subscribed to: {self._topic_event_wildcard}")

            self._subscribed = True

            # 启动定时轮询
            self._data_task = asyncio.create_task(self._periodic_data_request())

        except Exception as e:
            _LOGGER.error(f"Failed to start coordinator: {e}")

    async def async_stop(self) -> None:
        """停止协调器."""
        if self._data_task and not self._data_task.done():
            self._data_task.cancel()
            try:
                await self._data_task
            except asyncio.CancelledError:
                pass
        _LOGGER.info("Coordinator stopped")

    def _handle_message(self, msg) -> None:
        """处理接收到的 MQTT 消息."""
        self._last_update_time = time.time()
        try:
            topic = msg.topic
            payload = msg.payload
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8")

            # Extract device SN from topic: {prefix}/device/{sn}/status OR .../event
            match = re.search(rf"{self._topic_root}/device/([^/]+)/(status|event)", topic)
            if match:
                sn = match.group(1)
                msg_type = match.group(2) # 'status' or 'event'
                if not self._device_sn:
                    self._device_sn = sn
                    _LOGGER.info(f"Discovered device SN: {self._device_sn}")
                elif self._device_sn != sn:
                    _LOGGER.debug(f"Received data from another device: {sn}")

            # Parse Payload
            try:
                raw_data = json.loads(payload)
                msg_code = raw_data.get("type")
                body = raw_data.get("body")
                
                # If body is missing or None, use empty dict or the raw_data itself if it looks like data
                # But protocol says data is in body.
                if body is None:
                     # Some status messages might be flat? Assuming body per protocol.
                     # If Type 101 and body is None, ignore.
                     if msg_code == 101:
                         return 
                     body = {}
                
                # Merge logic
                # Type 23: Statistical/Energy Data
                if msg_code == 23 and isinstance(body, dict):
                    device_sn_in_body = body.get("deviceSn")
                    if device_sn_in_body == "system":
                        # Merge into main device cache
                        self._data_cache.update(body)
                    else:
                        # Find and update sub-device in cache
                        # Search in plugs and cts
                        for key in ["plugs", "plug", "cts"]:
                            items = self._data_cache.get(key)
                            if isinstance(items, list):
                                for item in items:
                                    if item.get("sn") == device_sn_in_body or item.get("deviceSn") == device_sn_in_body:
                                        item.update(body)
                                        break

                # Type 101: Sub-device full data
                elif msg_code == 101 and isinstance(body, dict):
                    # Normalize sub-device payloads for plugs/sockets/CTs
                    raw_plugs = body.get("plug") or body.get("plugs") or body.get("socket") or body.get("sockets") or []
                    raw_cts = body.get("ct") or body.get("cts") or []

                    current_cts = []
                    current_plugs = []

                    # Combine all sub-devices into a single list for discovery
                    combined = []
                    if isinstance(raw_plugs, list):
                        for item in raw_plugs:
                            if isinstance(item, dict) and item.get("devType") is None:
                                item = {**item, "devType": 6}
                            combined.append(item)
                    if isinstance(raw_cts, list):
                        for item in raw_cts:
                            if isinstance(item, dict):
                                # Some CT payloads report devType=3, subType=2; normalize to devType=2
                                sub_type = item.get("subType")
                                if sub_type == 2:
                                    item = {**item, "devType": 2}
                                elif item.get("devType") is None:
                                    item = {**item, "devType": 2}
                            combined.append(item)

                    for item in combined:
                        if not isinstance(item, dict):
                            continue
                        dt = item.get("devType")
                        if dt == 2:
                            current_cts.append(item)
                        else:
                            current_plugs.append(item)

                    self._data_cache["cts"] = current_cts
                    # Store all in "plugs" for JackeryPlugSensor to find itself by SN
                    self._data_cache["plugs"] = combined
                    self._data_cache["plug"] = combined  # Keep original key too

                # Type 25 or Status: Main device data
                elif isinstance(body, dict):
                    # Merge top-level keys
                    self._data_cache.update(body)

            except json.JSONDecodeError:
                _LOGGER.warning(f"Invalid JSON payload on {topic}")
                return

            # Enrich data with calculations using merged cache
            # operate on copy or direct? Direct is fine.
            self._data_cache = self._calculate_energy_flow(self._data_cache)
            
            # Check for new plugs
            self._check_for_new_plugs(self._data_cache)

            self._distribute_data(self._data_cache)

        except Exception as e:
            _LOGGER.error(f"Error handling message: {e}")

    def _check_for_new_plugs(self, data: dict) -> None:
        """检查并同步插座/CT（添加新设备，移除旧设备）."""
        # Check both keys
        plugs = data.get("plugs") or data.get("plug")
        if not plugs or not isinstance(plugs, list):
            plugs = data.get("cts") if isinstance(data.get("cts"), list) else None
        
        # 如果数据中根本没有 plugs/cts 字段，不做处理
        if plugs is None:
            return

        current_sns = set()
        for plug in plugs:
            sn = plug.get("deviceSn") or plug.get("sn")
            if sn:
                current_sns.add(sn)
        
        now = time.time()

        # 1. 更新 missing 状态
        for sn in current_sns:
            if sn in self._subdevice_missing_since:
                _LOGGER.info(f"Sub-device {sn} reappeared, cancelling deletion.")
                del self._subdevice_missing_since[sn]

        for sn in self._known_plugs:
            if sn not in current_sns:
                if sn not in self._subdevice_missing_since:
                    self._subdevice_missing_since[sn] = now
                    _LOGGER.info(f"Sub-device {sn} missing, starting 60s deletion timer...")

        # 2. 执行真正的移除
        for sn in list(self._subdevice_missing_since.keys()):
            if sn not in self._known_plugs:
                del self._subdevice_missing_since[sn]
                continue
            
            if sn in current_sns:
                del self._subdevice_missing_since[sn]
                continue

            missing_time = self._subdevice_missing_since[sn]
            if now - missing_time > 60:
                _LOGGER.info(f"Sub-device {sn} missing for >60s. Removing.")
                self._known_plugs.remove(sn)
                del self._subdevice_missing_since[sn]
                
                # Remove entities
                for sensor_id, entity in list(self._sensors.items()):
                    # Match unique IDs containing the SN for sub-devices
                    # Format: jackery_plug_{sn}_xxx or jackery_ct_{sn}_xxx or jackery_plug_{sn}_switch
                    if f"_{sn}_" in sensor_id or sensor_id.endswith(f"_{sn}"):
                        self.hass.async_create_task(entity.async_remove(force_remove=True))

        # 3. 处理新增
        new_entities = []
        new_switch_entities = []
        for plug in plugs:
            sn = plug.get("deviceSn") or plug.get("sn")
            dev_type = plug.get("devType")
            if dev_type is None and plug.get("subType") == 2:
                dev_type = 2
            
            if sn and sn not in self._known_plugs:
                _LOGGER.info(f"Discovered new sub-device: {sn} (Type: {dev_type})")
                self._known_plugs.add(sn)
                
                if hasattr(self, "config_entry_id"):
                    # Create Sensors defined in SUBDEVICE_SENSORS
                    sensor_group = "ct" if dev_type == 2 else "plug"
                    group_config = SUBDEVICE_SENSORS.get(sensor_group, {})

                    for sensor_key, sensor_cfg in group_config.items():
                        entity = JackerySubDeviceSensor(
                            plug_sn=sn,
                            dev_type=dev_type,
                            sensor_key=sensor_key,
                            sensor_config=sensor_cfg,
                            coordinator=self,
                            config_entry_id=self.config_entry_id
                        )
                        new_entities.append(entity)

                    if dev_type != 2:
                        from .switch import JackeryPlugSwitch
                        switch_entity = JackeryPlugSwitch(
                            plug_sn=sn,
                            dev_type=dev_type,
                            coordinator=self,
                            config_entry_id=self.config_entry_id
                        )
                        new_switch_entities.append(switch_entity)

        if new_entities and self.add_entities_callback:
            self.add_entities_callback(new_entities)
        if new_switch_entities and self.add_switch_entities_callback:
            self.add_switch_entities_callback(new_switch_entities)

    def get_subdevices(self) -> list[dict[str, Any]]:
        """Return latest sub-device list from cache."""
        plugs = self._data_cache.get("plugs") or self._data_cache.get("plug")
        if isinstance(plugs, list):
            return [p for p in plugs if isinstance(p, dict)]
        cts = self._data_cache.get("cts")
        if isinstance(cts, list):
            return [p for p in cts if isinstance(p, dict)]
        return []

    async def async_control_subdevice_switch(self, plug_sn: str, dev_type: int, is_on: bool) -> None:
        """Control sub-device switch via type 103."""
        if not self._device_sn:
            _LOGGER.warning("Cannot control sub-device: device SN not discovered")
            return

        action_topic = f"{self._topic_root}/device/{self._device_sn}/action"
        ts = int(time.time())
        payload = {
            "type": 103,
            "eventId": 0,
            "messageId": random.randint(1000, 9999),
            "ts": ts,
            "body": {
                "deviceSn": plug_sn,
                "devType": dev_type,
                "sysSwitch": 1 if is_on else 0,
            },
        }
        if self._token:
            payload["token"] = self._token

        await ha_mqtt.async_publish(
            self.hass,
            action_topic,
            json.dumps(payload),
            0,
            False
        )

    async def async_control_main_device(self, params: dict[str, Any]) -> None:
        """Control main device via type 1, cmd 5."""
        if not self._device_sn:
            _LOGGER.warning("Cannot control main device: device SN not discovered")
            return

        action_topic = f"{self._topic_root}/device/{self._device_sn}/action"
        ts = int(time.time())
        body = {"cmd": 5, "rc": 1}
        body.update(params)
        payload = {
            "type": 1,
            "eventId": 3,
            "messageId": random.randint(1000, 9999),
            "ts": ts,
            "body": body,
        }
        if self._token:
            payload["token"] = self._token

        await ha_mqtt.async_publish(
            self.hass,
            action_topic,
            json.dumps(payload),
            0,
            False
        )

    def _calculate_energy_flow(self, data: dict) -> dict:
        """
        根据用户需求计算能量流数据.
        
        Variables Mapping:
        - PV: pvPw
        - OngridCharge: inOngridPw
        - OngridSupply: outOngridPw
        - ACIn: swEpsInPw
        - ACOut: swEpsOutPw
        - GridBuy: (Need Key, assuming 'gridBuyPw' or similar, else None)
        - GridSell: (Need Key, assuming 'gridSellPw', else None)
        """
        try:
            # 1. PV
            # Handle dict for PV if necessary (copied from sensor logic)
            pv_val = data.get("pvPw", 0)
            if isinstance(pv_val, dict):
                pv = float(pv_val.get("pvPw", 0) or pv_val.get("w", 0) or pv_val.get("power", 0))
            else:
                pv = float(pv_val)

            # 2. Ongrid
            ongrid_charge = float(data.get("inOngridPw", 0))
            ongrid_supply = float(data.get("outOngridPw", 0))
            p_ong = ongrid_charge - ongrid_supply # 流入主机为正

            # 3. ACSocket (EPS)
            ac_in = float(data.get("swEpsInPw", 0))
            ac_out = float(data.get("swEpsOutPw", 0))
            p_ac = ac_in - ac_out # 流入主机为正

            # 4. Grid (Meter)
            # 优先从 'cts' 数组中提取 CT 数据 (Smart CT Meter)
            # cts item: { ..., "TphasePw": <Import>, "TnphasePw": <Export>, "commState": 1/0, ... }
            grid_available = False
            grid_buy = 0.0
            grid_sell = 0.0
            
            cts = data.get("cts")
            if cts and isinstance(cts, list) and len(cts) > 0:
                # 尝试获取第一个 CT 数据
                ct_data = cts[0]
                # 检查通讯状态 (如果 commState 存在且为 0 可能表示离线，视具体协议而定，这里暂定只要有数据即可)
                # TphasePw: 总正向有功 (Grid Buy)
                # TnphasePw: 总负向有功 (Grid Sell)
                t_phase_pw = ct_data.get("TphasePw") or ct_data.get("tPhasePw")
                tn_phase_pw = ct_data.get("TnphasePw") or ct_data.get("tnPhasePw")

                # Fallback: if total phase missing, sum A/B/C
                if t_phase_pw is None:
                    a_pw = ct_data.get("AphasePw") or ct_data.get("aPhasePw") or 0
                    b_pw = ct_data.get("BphasePw") or ct_data.get("bPhasePw") or 0
                    c_pw = ct_data.get("CphasePw") or ct_data.get("cPhasePw") or 0
                    if any(v is not None for v in [a_pw, b_pw, c_pw]):
                        t_phase_pw = float(a_pw) + float(b_pw) + float(c_pw)

                if tn_phase_pw is None:
                    an_pw = ct_data.get("AnphasePw") or ct_data.get("anPhasePw") or 0
                    bn_pw = ct_data.get("BnphasePw") or ct_data.get("bnPhasePw") or 0
                    cn_pw = ct_data.get("CnphasePw") or ct_data.get("cnPhasePw") or 0
                    if any(v is not None for v in [an_pw, bn_pw, cn_pw]):
                        tn_phase_pw = float(an_pw) + float(bn_pw) + float(cn_pw)

                if t_phase_pw is not None or tn_phase_pw is not None:
                    grid_buy = float(t_phase_pw or 0)
                    grid_sell = float(tn_phase_pw or 0)
                    grid_available = True
            
            # 兼容旧逻辑或直接字段 (如果 cts 不存在)
            if not grid_available:
                grid_buy_raw = data.get("gridBuyPw") # Hypothetical key
                grid_sell_raw = data.get("gridSellPw") # Hypothetical key
                if grid_buy_raw is not None and grid_sell_raw is not None:
                    grid_available = True
                    grid_buy = float(grid_buy_raw)
                    grid_sell = float(grid_sell_raw)

            # Calculate P_grid
            p_grid = None
            if grid_available:
                p_grid = grid_buy - grid_sell
                
                # 🔴异常流程（仅当电表可用且并网口处于充电态时生效）
                # GridAvailable=true 且 GridBuy < OngridCharge 且 (OngridCharge - GridBuy) <= 50W
                if grid_buy < ongrid_charge and (ongrid_charge - grid_buy) <= 50:
                    p_grid = p_ong

            # 5. Battery (Calculated)
            # P_batt = P_pv + P_ac + P_ong
            p_batt = pv + p_ac + p_ong

            # 6. Home (Calculated)
            p_home = 0.0
            
            if p_grid is not None:
                # 电表可用
                p_home = p_grid - p_ong
                
                # 🔴 异常分支 1
                if grid_buy > 0 and ongrid_charge > 0 and grid_buy < ongrid_charge and (ongrid_charge - grid_buy) <= 50:
                    # p_grid = p_ong # Already handled in p_grid calc above? 
                    # Note: User spec says "P_grid = P_ong (按异常流程先修正); P_home = 0"
                    # My P_grid calc above handled P_grid. Now P_home:
                    p_home = 0.0

                # 🔴 异常分支 2
                elif grid_buy > 0 and ongrid_charge > 0 and grid_buy < ongrid_charge and (ongrid_charge - grid_buy) > 50:
                    p_home = ongrid_charge - grid_buy

                # 🔴 馈网场景分支 A
                elif grid_sell > 0 and ongrid_supply > 0:
                    p_home = grid_sell - ongrid_supply

                # 🔴 馈网场景分支 B
                elif grid_sell > 0 and ongrid_charge > 0:
                    p_home = grid_sell + ongrid_charge
            
            else:
                # 电表不可用 (No CT)
                if ongrid_supply > 0:
                    p_home = ongrid_supply
                else:
                    p_home = 0.0

            # Store calculated values
            data["calc_home_power"] = p_home
            data["calc_batt_net_power"] = p_batt
            data["calc_battery_charge_power"] = max(0.0, p_batt)
            data["calc_battery_discharge_power"] = max(0.0, -p_batt)
            data["grid_available"] = grid_available
            data["calc_grid_net_power"] = p_grid if grid_available else None

        except Exception as e:
            _LOGGER.error(f"Error calculating energy flow: {e}")
            
        return data

    def _distribute_data(self, data: dict) -> None:
        """分发数据给传感器."""
        for sensor_id, entity in self._sensors.items():
            entity._update_from_coordinator(data)

    def _mark_all_offline(self) -> None:
        """Mark all entities as unavailable."""
        for entity in self._sensors.values():
            if entity.available:
                entity._attr_available = False
                entity.async_write_ha_state()

    async def _periodic_data_request(self) -> None:
        """定期发送 'type: 25' 和 'type: 100' 指令."""
        _LOGGER.info(f"Starting periodic data polling for {self._device_sn} via {self._mqtt_host}...")
        await asyncio.sleep(2)

        while True:
            try:
                if time.time() - self._last_update_time > 60:
                    self._mark_all_offline()

                if not self._device_sn:
                    _LOGGER.debug("Waiting for device SN discovery...")
                    await asyncio.sleep(5)
                    continue

                # Construct Action Topic
                action_topic = f"{self._topic_root}/device/{self._device_sn}/action"
                ts = int(time.time())
                
                # 1. Poll Device Status (Type 25)
                try:
                    payload_25 = {
                        "type": 25,
                        "eventId": 0,
                        "messageId": random.randint(1000, 9999),
                        "ts": ts,
                        "token": self._token,
                        "body": None
                    }

                    await ha_mqtt.async_publish(
                        self.hass,
                        action_topic,
                        json.dumps(payload_25),
                        0,
                        False
                    )
                except Exception as e:
                    _LOGGER.warning(f"Error polling device status (Type 25): {e}")

                # 2. Poll Sub-devices (Type 100) - CTs (2) and Plugs (6)
                try:
                    for dev_type in [2, 6]:
                        payload_100 = {
                            "type": 100,
                            "eventId": 0,
                            "messageId": random.randint(1000, 9999),
                            "ts": ts,
                            "token": self._token,
                            "body": {
                                "devType": dev_type
                            }
                        }

                        await ha_mqtt.async_publish(
                            self.hass,
                            action_topic,
                            json.dumps(payload_100),
                            0,
                            False
                        )
                        await asyncio.sleep(0.5) # Avoid spamming too fast
                except Exception as e:
                    _LOGGER.warning(f"Error polling sub-devices (Type 100): {e}")
                
                _LOGGER.debug(f"Sent poll requests (25 & 100 [2,6]) to {action_topic}")

                await asyncio.sleep(REQUEST_INTERVAL)

            except asyncio.CancelledError:
                break
            except Exception as e:
                _LOGGER.error(f"Error in polling task: {e}")
                await asyncio.sleep(REQUEST_INTERVAL)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Jackery sensors."""
    config = config_entry.data
    topic_prefix = config.get("topic_prefix", "hb")
    token = config.get("token")
    mqtt_host = config.get("mqtt_host")
    device_sn = config.get("device_sn")

    coordinator = JackeryDataCoordinator(hass, topic_prefix, token, mqtt_host, device_sn)
    coordinator.config_entry_id = config_entry.entry_id # Assign entry_id
    
    # Register callback for dynamic entities
    def add_entities_callback(new_entities):
        async_add_entities(new_entities)
    coordinator.add_entities_callback = add_entities_callback
    
    hass.data[DOMAIN][config_entry.entry_id]["coordinator"] = coordinator

    entities = []
    for sensor_id, sensor_config in SENSORS.items():
        if sensor_config.get("json_key") is None:
            continue

        entity = JackerySensor(
            sensor_id=sensor_id,
            coordinator=coordinator,
            config_entry_id=config_entry.entry_id,
        )
        entities.append(entity)

    async_add_entities(entities)
    await coordinator.async_start()


class JackerySensor(SensorEntity):
    """Jackery Sensor."""
    # ... (Existing JackerySensor Code) ...
    def __init__(
        self,
        sensor_id: str,
        coordinator: JackeryDataCoordinator,
        config_entry_id: str,
    ) -> None:
        """Initialize."""
        self._sensor_id = sensor_id
        self._coordinator = coordinator
        self._config = SENSORS[sensor_id]

        self._attr_name = self._config["name"]
        self._attr_native_unit_of_measurement = self._config["unit"]
        self._attr_icon = self._config["icon"]
        self._attr_device_class = self._config["device_class"]
        self._attr_state_class = self._config["state_class"]
        self._attr_unique_id = f"jackery_{sensor_id}"
        self._attr_has_entity_name = True

        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry_id)},
            "name": "Jackery",
            "manufacturer": "Jackery",
            "model": "Energy Monitor",
        }

    @property
    def should_poll(self) -> bool:
        return False

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._coordinator.register_sensor(self._sensor_id, self)

    async def async_will_remove_from_hass(self) -> None:
        self._coordinator.unregister_sensor(self._sensor_id)
        await super().async_will_remove_from_hass()

    def _update_from_coordinator(self, data: dict) -> None:
        """Receive data from coordinator."""
        # Special handling for EPS Output Power (Bidirectional)
        if self._sensor_id == "eps_output_power":
            out_p = float(data.get("swEpsOutPw", 0))
            in_p = float(data.get("swEpsInPw", 0))
            self._attr_native_value = out_p - in_p
            self._attr_available = True
            self.async_write_ha_state()
            return

        json_key = self._config.get("json_key")
        if not json_key or json_key not in data:
            return

        value = data[json_key]

        if self._sensor_id == "grid_net_power" and value is None:
            # Keep last value when CT data is temporarily missing
            return

        # Process specific conversions
        if self._sensor_id == "battery_temperature":
            # cellTemp is 0.1 C
            try:
                self._attr_native_value = float(value) * 0.1
            except (TypeError, ValueError):
                pass
        elif self._sensor_id == "battery_soc":
             self._attr_native_value = value
        elif self._sensor_id.startswith("solar_power_pv") and isinstance(value, dict):
            # Handle dictionary for PV if it occurs
            if "pvPw" in value:
                self._attr_native_value = value["pvPw"]
            elif "w" in value:
                self._attr_native_value = value["w"]
            elif "power" in value:
                self._attr_native_value = value["power"]
            else:
                self._attr_native_value = str(value)
        else:
            scale = self._config.get("scale", 1)
            try:
                self._attr_native_value = float(value) * scale
            except (TypeError, ValueError):
                 self._attr_native_value = value

        self._attr_available = True
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "device_sn": self._coordinator._device_sn,
            "raw_key": self._config.get("json_key")
        }


class JackerySubDeviceSensor(SensorEntity):
    """Jackery Smart Plug / CT Sub-device Sensor."""

    def __init__(
        self,
        plug_sn: str,
        dev_type: int,
        sensor_key: str,
        sensor_config: dict,
        coordinator: JackeryDataCoordinator,
        config_entry_id: str,
    ) -> None:
        """Initialize."""
        self._plug_sn = plug_sn
        self._dev_type = dev_type
        self._sensor_key = sensor_key
        self._sensor_config = sensor_config
        self._coordinator = coordinator
        
        # Determine Device Name based on Type
        if self._dev_type == 2:
            device_name = "CT"
        else:
            device_name = "Plug"

        # Entity Name: "Power", "Energy", etc.
        self._attr_name = self._sensor_config["name"]
        
        self._attr_native_unit_of_measurement = self._sensor_config.get("unit")
        self._attr_icon = self._sensor_config.get("icon")
        self._attr_device_class = self._sensor_config.get("device_class")
        self._attr_state_class = self._sensor_config.get("state_class")
        
        # Unique ID: jackery_ct_{sn}_power, jackery_plug_{sn}_energy, etc.
        safe_key = self._sensor_key.replace("_", "") # e.g. energy_import -> energyimport
        self._attr_unique_id = f"jackery_{device_name.lower()}_{plug_sn}_{safe_key}"
        self._attr_has_entity_name = True

        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"sub_{plug_sn}")}, 
            "via_device": (DOMAIN, config_entry_id),
            "name": f"Jackery {device_name} {plug_sn}",
            "manufacturer": "Jackery",
            "model": f"Sub-device Type {dev_type}",
        }

    @property
    def should_poll(self) -> bool:
        return False

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Register with coordinator using a unique ID format
        self._coordinator.register_sensor(self._attr_unique_id, self)

    async def async_will_remove_from_hass(self) -> None:
        self._coordinator.unregister_sensor(self._attr_unique_id)
        await super().async_will_remove_from_hass()

    def _update_from_coordinator(self, data: dict) -> None:
        """Receive data from coordinator."""
        if self._dev_type == 2:
            plugs = data.get("cts")
        else:
            plugs = data.get("plugs") or data.get("plug")
        if not plugs or not isinstance(plugs, list):
            return

        # Find my plug data
        my_plug = next((p for p in plugs if (p.get("sn") == self._plug_sn or p.get("deviceSn") == self._plug_sn)), None)
        if not my_plug:
            return

        # Store full raw data for attributes
        self._raw_data = dict(my_plug)
        
        target_key = self._sensor_config.get("key")
        val = my_plug.get(target_key)
        
        # Fallback logic for specific keys if needed (like Power)
        if val is None:
             if target_key == "outPw":
                 val = my_plug.get("power")
             elif target_key == "TphasePw":
                 # Accept alternate key casing and sum phase powers if needed
                 val = my_plug.get("tPhasePw")
                 if val is None:
                     a_pw = my_plug.get("AphasePw") or my_plug.get("aPhasePw") or 0
                     b_pw = my_plug.get("BphasePw") or my_plug.get("bPhasePw") or 0
                     c_pw = my_plug.get("CphasePw") or my_plug.get("cPhasePw") or 0
                     if any(v is not None for v in [a_pw, b_pw, c_pw]):
                         val = float(a_pw) + float(b_pw) + float(c_pw)
             elif target_key == "TphaseEgy":
                 # Total forward active energy
                 val = my_plug.get("tPhaseEgy")
                 if val is None:
                     a_egy = my_plug.get("AphaseEgy") or my_plug.get("aPhaseEgy") or 0
                     b_egy = my_plug.get("BphaseEgy") or my_plug.get("bPhaseEgy") or 0
                     c_egy = my_plug.get("CphaseEgy") or my_plug.get("cPhaseEgy") or 0
                     if any(v is not None for v in [a_egy, b_egy, c_egy]):
                         val = float(a_egy) + float(b_egy) + float(c_egy)
             elif target_key == "TnphaseEgy":
                 # Total reverse active energy
                 val = my_plug.get("tnPhaseEgy")
                 if val is None:
                     an_egy = my_plug.get("AnphaseEgy") or my_plug.get("anPhaseEgy") or 0
                     bn_egy = my_plug.get("BnphaseEgy") or my_plug.get("bnPhaseEgy") or 0
                     cn_egy = my_plug.get("CnphaseEgy") or my_plug.get("cnPhaseEgy") or 0
                     if any(v is not None for v in [an_egy, bn_egy, cn_egy]):
                         val = float(an_egy) + float(bn_egy) + float(cn_egy)
        
        if val is not None:
            try:
                native_val = float(val)
                scale = self._sensor_config.get("scale", 1)
                self._attr_native_value = native_val * scale
                self._attr_available = True
                self.async_write_ha_state()
            except (TypeError, ValueError):
                pass

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        raw = getattr(self, "_raw_data", None) or {}
        return {
            "plug_sn": self._plug_sn,
            "dev_type": self._dev_type,
            "sensor_type": self._sensor_key,
            # Normalized CT/plug fields (if present)
            "sn": raw.get("sn") or raw.get("deviceSn"),
            "name": raw.get("name") or raw.get("scanName"),
            "commState": raw.get("commState"),
            # Plug fields
            "inPw": raw.get("inPw"),
            "outPw": raw.get("outPw"),
            "sysSwitch": raw.get("sysSwitch") if raw.get("sysSwitch") is not None else raw.get("switchSta"),
            "totalEgy": raw.get("totalEgy"),
            # CT Fields
            "TphasePw": raw.get("TphasePw"),
            "TphaseEgy": raw.get("TphaseEgy"),
            "TnphaseEgy": raw.get("TnphaseEgy"),
            "tPhasePw": raw.get("tPhasePw"),
            "tPhaseEgy": raw.get("tPhaseEgy"),
            "tnPhaseEgy": raw.get("tnPhaseEgy"),
        }
