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

    # 太阳能
    "solar_power": {
        "json_key": "pvPw",
        "name": "Solar Power",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:solar-power",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "solar_power_pv1": {
        "json_key": "pv1",
        "name": "Solar Power PV1",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:solar-panel",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "solar_power_pv2": {
        "json_key": "pv2",
        "name": "Solar Power PV2",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:solar-panel",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "solar_power_pv3": {
        "json_key": "pv3",
        "name": "Solar Power PV3",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:solar-panel",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "solar_power_pv4": {
        "json_key": "pv4",
        "name": "Solar Power PV4",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:solar-panel",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
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
    "grid_export_power": { # System -> Grid/Home (inOngirdPw)
        "json_key": "outOngridPw",
        "name": "Grid Export Power",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:transmission-tower-export",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
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
    "eps_input_power": {
        "json_key": "swEpsInPw",
        "name": "EPS Input Power",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:power-plug",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
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
    }
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

        # Topic patterns
        self._topic_status_wildcard = f"{self._topic_root}/device/+/status"

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
        try:
            topic = msg.topic
            payload = msg.payload
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8")

            # Extract device SN from topic: {prefix}/device/{sn}/status
            match = re.search(rf"{self._topic_root}/device/([^/]+)/status", topic)
            if match:
                sn = match.group(1)
                if not self._device_sn:
                    self._device_sn = sn
                    _LOGGER.info(f"Discovered device SN: {self._device_sn}")
                elif self._device_sn != sn:
                    _LOGGER.debug(f"Received data from another device: {sn}")

            # Parse Payload
            try:
                data = json.loads(payload)
                # 如果数据在 body 字段中，则提取 body
                if "body" in data and isinstance(data["body"], dict):
                    data = data["body"]
            except json.JSONDecodeError:
                _LOGGER.warning(f"Invalid JSON payload on {topic}")
                return

            # Enrich data with calculations
            data = self._calculate_energy_flow(data)
            self._distribute_data(data)

        except Exception as e:
            _LOGGER.error(f"Error handling message: {e}")

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
                t_phase_pw = ct_data.get("TphasePw")
                tn_phase_pw = ct_data.get("TnphasePw")
                
                if t_phase_pw is not None and tn_phase_pw is not None:
                    grid_buy = float(t_phase_pw)
                    grid_sell = float(tn_phase_pw)
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
            data["calc_grid_net_power"] = p_grid if p_grid is not None else 0 # Return 0 if None for sensor safety? 
            # Note: If p_grid is None, the sensor might show 0 or unavailable. 
            # Ideally "Grid Net Power" sensor should be unavailable if no CT.
            # But let's set it to 0 for now or handle in sensor.

            # Additional: We might want to pass 'grid_available' to data for sensor state?
            if p_grid is None:
                # If we return None, the sensor logic below might error or show Unknown.
                # Let's leave it as None in data, and handle in sensor update.
                 data["calc_grid_net_power"] = None

        except Exception as e:
            _LOGGER.error(f"Error calculating energy flow: {e}")
            
        return data

    def _distribute_data(self, data: dict) -> None:
        """分发数据给传感器."""
        for sensor_id, entity in self._sensors.items():
            entity._update_from_coordinator(data)

    async def _periodic_data_request(self) -> None:
        """定期发送 'type: 25' 和 'type: 100' 指令."""
        _LOGGER.info(f"Starting periodic data polling for {self._device_sn} via {self._mqtt_host}...")
        await asyncio.sleep(2)

        while True:
            try:
                if not self._device_sn:
                    _LOGGER.debug("Waiting for device SN discovery...")
                    await asyncio.sleep(5)
                    continue

                # Construct Action Topic
                action_topic = f"{self._topic_root}/device/{self._device_sn}/action"
                ts = int(time.time())
                
                # 1. Poll Device Status (Type 25)
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
                
                # 2. Poll Sub-devices (Type 100) - specifically for CTs (devType: 2)
                # type=100 通知设备上报特定类型子设备全量数据
                # devType: 2 (同时获取CT&电表采集头&电表)
                payload_100 = {
                    "type": 100,
                    "eventId": 0,
                    "messageId": random.randint(1000, 9999),
                    "ts": ts,
                    "token": self._token,
                    "body": {
                        "devType": 2
                    }
                }
                
                await ha_mqtt.async_publish(
                    self.hass,
                    action_topic,
                    json.dumps(payload_100),
                    0,
                    False
                )
                
                _LOGGER.debug(f"Sent poll requests (25 & 100) to {action_topic}")

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
             self._attr_native_value = value

        self._attr_available = True
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "device_sn": self._coordinator._device_sn,
            "raw_key": self._config.get("json_key")
        }
