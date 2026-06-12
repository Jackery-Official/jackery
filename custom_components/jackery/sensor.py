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
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Constants
REQUEST_INTERVAL = 5  # Data request interval (seconds), Phase 2 requires 5s
OFFLINE_TIMEOUT = 60  # Offline timeout (seconds), mark as Unavailable if no report received
# Prompt for re-auth if no response received within this duration after setup
REAUTH_HINT_TIMEOUT = 120

# Host operation status mapping (stat field)
DEVICE_STATUS_MAP = {
    0: "normal",       # Normal
    1: "waiting",      # Waiting
    2: "alarm",        # Alarm
    3: "fault",        # Fault
    4: "standby",      # Standby
    5: "low_power",    # Low Power
}

# Grid-tied system status mapping (type=106 full attributes)
ONGRID_STATUS_MAP = {0: "off_grid", 1: "on_grid"}        # ongridStat: 1=On-grid, 0=Off-grid
CT_STATUS_MAP = {0: "offline", 1: "online"}              # ctStat: 1=Online, 0=Offline
GRID_METER_LINK_MAP = {0: "abnormal", 1: "normal"}       # gridSate: 1=Normal, 0=Abnormal

# funcEnable bits (bit -> name), 1=Enabled, 0=Disabled
FUNC_ENABLE_BITS = {
    0: "aerosol",            # bit0 aerosol
    1: "soc_calibration",    # bit1 SOC calibration
    2: "low_power",          # bit2 low power
    3: "soh_calibration",    # bit3 SOH calibration
    4: "pcs_comm_diag",      # bit4 PCS communication diagnosis
    5: "shutdown_2h",        # bit5 2H shutdown
    6: "fault_shutdown",     # bit6 fault shutdown
    7: "epo",                # bit7 EPO function
    8: "func_48v",           # bit8 48V function
    9: "ethernet_debug",     # bit9 Ethernet debug function
    10: "energy_flow_fill",  # bit10 energy flow data backfill
    11: "smart_plug_first",  # bit11 smart plug priority
}

# deviceType -> Model name mapping (for device details), fallback to "Energy Monitor"
DEVICE_TYPE_MODEL_MAP = {
    1: "Battery Pack",
    2: "CT/Meter Collector/Meter",
    3: "CT",
    4: "Meter Collector",
}
DEFAULT_MODEL = "Energy Monitor"

# Flat status message recognition fields (without type/body wrapper)
_FLAT_PAYLOAD_KEYS = frozenset(
    {
        "batSoc",
        "soc",
        "pvPw",
        "stat",
        "workMode",
        "inOngridPw",
        "outOngridPw",
        "gridInPw",
        "gridOutPw",
        "inGridSidePw",
        "outGridSidePw",
        "swEpsInPw",
        "swEpsOutPw",
        "batInPw",
        "batOutPw",
        "otherLoadPw",
    }
)


def _field_present(data: dict[str, Any], key: str) -> bool:
    """Check if field exists in cache (0 is valid, None means not reported)."""
    return key in data and data[key] is not None


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert MQTT field to float."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _pick_best_power_net(candidates: list[float]) -> float:
    """Pick non-zero value with max absolute magnitude from candidates; fallback to last candidate if all are 0."""
    if not candidates:
        return 0.0
    non_zero = [v for v in candidates if abs(v) > 0]
    if non_zero:
        return max(non_zero, key=abs)
    return candidates[-1]


def _extract_ct_grid_power(ct_data: dict[str, Any]) -> tuple[float, float, bool]:
    """Extract buy/sell power from CT sub-device; returns (grid_buy, grid_sell, has_power_fields)."""
    t_phase_pw = ct_data.get("TphasePw") or ct_data.get("tPhasePw")
    tn_phase_pw = ct_data.get("TnphasePw") or ct_data.get("tnPhasePw")
    has_power_fields = t_phase_pw is not None or tn_phase_pw is not None

    if t_phase_pw is None:
        a_pw = ct_data.get("AphasePw") or ct_data.get("aPhasePw")
        b_pw = ct_data.get("BphasePw") or ct_data.get("bPhasePw")
        c_pw = ct_data.get("CphasePw") or ct_data.get("cPhasePw")
        if any(v is not None for v in (a_pw, b_pw, c_pw)):
            t_phase_pw = _safe_float(a_pw) + _safe_float(b_pw) + _safe_float(c_pw)
            has_power_fields = True

    if tn_phase_pw is None:
        an_pw = ct_data.get("AnphasePw") or ct_data.get("anPhasePw")
        bn_pw = ct_data.get("BnphasePw") or ct_data.get("bnPhasePw")
        cn_pw = ct_data.get("CnphasePw") or ct_data.get("cnPhasePw")
        if any(v is not None for v in (an_pw, bn_pw, cn_pw)):
            tn_phase_pw = _safe_float(an_pw) + _safe_float(bn_pw) + _safe_float(cn_pw)
            has_power_fields = True

    if not has_power_fields:
        return 0.0, 0.0, False

    return _safe_float(t_phase_pw), _safe_float(tn_phase_pw), True


def _ct_has_usable_power(
    ct_data: dict[str, Any], grid_buy: float, grid_sell: float, has_power_fields: bool
) -> bool:
    """Check if CT power is reliable: non-zero reading, or online and has reported phase power (type=102)."""
    if abs(grid_buy) > 0 or abs(grid_sell) > 0:
        return True
    if not has_power_fields:
        return False
    comm = ct_data.get("commState")
    return comm in (1, "1", True)


def _effective_ongrid_net(
    data: dict[str, Any],
    grid_in: float,
    grid_out: float,
    ongrid_charge: float,
    ongrid_supply: float,
    in_grid_side: float,
    out_grid_side: float,
) -> float:
    """Net power at grid-tied port: prioritized non-zero max magnitude (prevents type=106 zero from blocking type=25 fallback)."""
    candidates: list[float] = []
    if _field_present(data, "gridInPw") or _field_present(data, "gridOutPw"):
        candidates.append(grid_in - grid_out)
    if _field_present(data, "inOngridPw") or _field_present(data, "outOngridPw"):
        candidates.append(ongrid_charge - ongrid_supply)
    if _field_present(data, "inGridSidePw") or _field_present(data, "outGridSidePw"):
        candidates.append(in_grid_side - out_grid_side)
    return _pick_best_power_net(candidates)


def _grid_net_from_system(
    data: dict[str, Any],
    grid_in: float,
    grid_out: float,
    ongrid_charge: float,
    ongrid_supply: float,
    in_grid_side: float,
    out_grid_side: float,
) -> tuple[float, bool]:
    """Calculate net grid power based on App priority when CT is missing, including device-level fallback."""
    candidates: list[float] = []
    if _field_present(data, "inGridSidePw") or _field_present(data, "outGridSidePw"):
        candidates.append(in_grid_side - out_grid_side)
    if _field_present(data, "gridInPw") or _field_present(data, "gridOutPw"):
        gi_go = grid_in - grid_out
        if abs(gi_go) > 0 or grid_in != 0 or grid_out != 0:
            candidates.append(gi_go)
    if _field_present(data, "inOngridPw") or _field_present(data, "outOngridPw"):
        candidates.append(ongrid_charge - ongrid_supply)
    if not candidates:
        return 0.0, False
    return _pick_best_power_net(candidates), True


def _normalize_payload_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize MQTT field aliases for cache merging and energy flow calculation."""
    result = dict(payload)

    if "soc" in result and result.get("batSoc") is None:
        result["batSoc"] = result["soc"]

    if result.get("gridInPw") is None and result.get("gridBuyPw") is not None:
        result["gridInPw"] = result["gridBuyPw"]
    if result.get("gridOutPw") is None and result.get("gridSellPw") is not None:
        result["gridOutPw"] = result["gridSellPw"]

    # Normalize workModel (type=106) and workMode (type=107) to workMode
    if result.get("workMode") is None and result.get("workModel") is not None:
        result["workMode"] = result["workModel"]

    return result


def _extract_flat_body(raw_data: dict[str, Any]) -> dict[str, Any]:
    """Extract body fields from flat status message."""
    meta_keys = {
        "type",
        "eventId",
        "messageId",
        "ts",
        "deviceType",
        "token",
        "softver",
        "body",
    }
    if not any(key in raw_data for key in _FLAT_PAYLOAD_KEYS):
        return {}
    return {key: value for key, value in raw_data.items() if key not in meta_keys}


# Sub-device array element devType (different scope from body.devType in type=100/101)
CT_ITEM_DEV_TYPES = frozenset({2, 3, 4})
PLUG_ITEM_DEV_TYPES = frozenset({6})

# Smart plug communication mode (commMode)
COMM_MODE_LOCAL = 1
COMM_MODE_CLOUD = 2
COMM_MODE_LABELS = {
    COMM_MODE_LOCAL: "local",
    COMM_MODE_CLOUD: "cloud",
}


def plug_comm_mode(item: dict[str, Any]) -> int | None:
    """Read plug commMode (1=local, 2=cloud)."""
    val = item.get("commMode")
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def plug_mqtt_control_allowed(item: dict[str, Any]) -> tuple[bool, str]:
    """Check if MQTT control is allowed for plug; returns (allowed, reason)."""
    mode = plug_comm_mode(item)
    if mode == COMM_MODE_LOCAL:
        return True, ""
    if mode == COMM_MODE_CLOUD:
        return (
            False,
            "Smart plug is cloud-connected (commMode=2) and cannot be controlled via MQTT. Please use the Jackery App.",
        )
    if mode is None:
        return (
            False,
            "Unknown commMode. MQTT control is only supported when commMode=1 (local).",
        )
    return (
        False,
        f"Smart plug commMode={mode} does not support MQTT control. Only commMode=1 (local) is supported.",
    )


def _subdevice_sn(item: dict[str, Any]) -> str | None:
    """Extract sub-device SN."""
    return item.get("deviceSn") or item.get("sn")


def is_ct_item_dev_type(dev_type: int | None) -> bool:
    """Check if devType belongs to CT/Meter family."""
    return dev_type in CT_ITEM_DEV_TYPES


def subdevice_sensor_group(item: dict[str, Any], *, from_cts_array: bool = False) -> str:
    """Determine sensor group based on devType and cts source, ignoring body.devType."""
    if from_cts_array or is_ct_item_dev_type(item.get("devType")):
        return "ct"
    return "plug"


def should_create_plug_switch(item: dict[str, Any]) -> bool:
    """Only create switch entities for smart plugs."""
    return item.get("devType") in PLUG_ITEM_DEV_TYPES


def _merge_subdevice_list(
    existing: list[dict[str, Any]] | None,
    new_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge sub-devices by deviceSn to prevent type=101 messages from overwriting each other."""
    merged: dict[str, dict[str, Any]] = {}
    for item in (existing or []) + new_items:
        if not isinstance(item, dict):
            continue
        sn = _subdevice_sn(item)
        if not sn:
            continue
        merged[sn] = {**merged.get(sn, {}), **item}
    return list(merged.values())


def _all_subdevices_from_cache(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Aggregate all sub-devices from cache (plugs + cts deduplicated)."""
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for key in ("plugs", "plug", "cts"):
        items = data.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            sn = _subdevice_sn(item)
            if not sn or sn in seen:
                continue
            seen.add(sn)
            result.append(item)
    return result


def _merge_subdevice_arrays_into_cache(
    cache: dict[str, Any],
    body: dict[str, Any],
) -> bool:
    """Merge plugs/cts arrays from body into cache (type=101/102/25 etc)."""
    updated = False
    raw_plugs = (
        body.get("plug")
        or body.get("plugs")
        or body.get("socket")
        or body.get("sockets")
    )
    if isinstance(raw_plugs, list) and raw_plugs:
        plug_items: list[dict[str, Any]] = []
        for item in raw_plugs:
            if not isinstance(item, dict):
                continue
            entry = dict(item)
            if entry.get("devType") is None:
                entry["devType"] = 6
            plug_items.append(entry)
        existing_plugs = [
            p
            for p in (cache.get("plugs") or [])
            if isinstance(p, dict) and subdevice_sensor_group(p) == "plug"
        ]
        cache["plugs"] = _merge_subdevice_list(existing_plugs, plug_items)
        cache["plug"] = cache["plugs"]
        updated = True

    raw_cts = body.get("ct") or body.get("cts")
    if isinstance(raw_cts, list) and raw_cts:
        ct_items = [dict(item) for item in raw_cts if isinstance(item, dict)]
        cache["cts"] = _merge_subdevice_list(cache.get("cts"), ct_items)
        updated = True
    return updated


def _merge_subdevice_point_update(
    cache: dict[str, Any],
    body: dict[str, Any],
    main_device_sn: str | None,
) -> bool:
    """Merge single sub-device incremental updates (type=102 etc) into cache."""
    device_sn = _subdevice_sn(body)
    if not device_sn or device_sn == main_device_sn or device_sn == "system":
        return False

    for key in ("plugs", "plug", "cts"):
        items = cache.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and _subdevice_sn(item) == device_sn:
                item.update(body)
                return True

    entry = dict(body)
    dev_type = entry.get("devType")
    if dev_type is None:
        if any(k in body for k in ("switchSta", "sysSwitch", "outPw", "inPw", "totalEgy")):
            entry["devType"] = 6
            dev_type = 6
        elif any(k in body for k in ("AphasePw", "aPhasePw", "phasePw", "subType")):
            entry["devType"] = 3
            dev_type = 3

    if dev_type in PLUG_ITEM_DEV_TYPES:
        cache["plugs"] = _merge_subdevice_list(cache.get("plugs"), [entry])
        cache["plug"] = cache["plugs"]
        return True
    if is_ct_item_dev_type(dev_type):
        cache["cts"] = _merge_subdevice_list(cache.get("cts"), [entry])
        return True
    return False


# Sensor configuration
SENSORS = {
    # Device Status
    "device_status": {
        "json_key": "stat",
        "name": "Status",
        "unit": None,
        "icon": "mdi:state-machine",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "options": list(DEVICE_STATUS_MAP.values()),
    },
    "work_mode": {
        "json_key": "workMode",
        "name": "Work Mode",
        "unit": None,
        "icon": "mdi:cog-outline",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    # Grid-tied system status (type=106 full attributes)
    "ongrid_status": {
        "json_key": "ongridStat",
        "name": "OnGrid Status",
        "unit": None,
        "icon": "mdi:transmission-tower",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "options": list(ONGRID_STATUS_MAP.values()),
        "value_map": ONGRID_STATUS_MAP,
    },
    "ct_status": {
        "json_key": "ctStat",
        "name": "CT Status",
        "unit": None,
        "icon": "mdi:current-ac",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "options": list(CT_STATUS_MAP.values()),
        "value_map": CT_STATUS_MAP,
    },
    "grid_meter_link": {
        "json_key": "gridSate",
        "name": "Grid Meter Link",
        "unit": None,
        "icon": "mdi:lan-connect",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "options": list(GRID_METER_LINK_MAP.values()),
        "value_map": GRID_METER_LINK_MAP,
    },
    "other_load_power": {
        "json_key": "otherLoadPw",
        "name": "Other Load Power",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:home-lightning-bolt-outline",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "max_feed_grid_power": {
        "json_key": "maxFeedGrid",
        "name": "Max Feed-in Grid Power",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:transmission-tower-export",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "func_enable": {
        "json_key": "funcEnable",
        "name": "Function Enable",
        "unit": None,
        "icon": "mdi:tune-variant",
        "device_class": None,
        "state_class": None,
    },
    # Battery related
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
    # Battery energy statistics
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

    # Solar
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

    # Grid related
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

    # EPS / AC Socket (App logic: use input if swEpsInPw > 0, else output)
    "eps_output_power": {
        "json_key": "calc_ac_socket_power",
        "name": "AC Socket Power",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:power-plug",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "ac_socket_power": {
        "json_key": "calc_ac_socket_power",
        "name": "AC Socket Power (Calc)",
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
    # "is_auto_standby": {
    #     "json_key": "isAutoStandby",
    #     "name": "Auto Standby Allowed",
    #     "unit": None,
    #     "icon": "mdi:power-sleep",
    #     "device_class": None,
    #     "state_class": None, # 1-Allowed, 0-Not Allowed
    # },
    # "auto_standby_status": {
    #     "json_key": "autoStandby",
    #     "name": "Auto Standby Mode",
    #     "unit": None,
    #     "icon": "mdi:power-sleep",
    #     "device_class": None,
    #     "state_class": None, # 0-Invalid, 1-Sleep/Off, 2-On
    # },
    
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
    # More energy flow statistics
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
    "ac_to_grid_energy": {
        "json_key": "acOtOngridEgy",
        "name": "AC to Grid Energy",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "icon": "mdi:transmission-tower-export",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "scale": 0.01,
    },
}

# Sub-device sensor configuration
SUBDEVICE_SENSORS = {
    # Smart Plug (devType=6 or 1)
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
            "key": "phasePw", # Resolve by subType to A/B/C/Total
            "name": "Power",
            "unit": UnitOfPower.WATT,
            "device_class": SensorDeviceClass.POWER,
            "state_class": SensorStateClass.MEASUREMENT,
            "icon": "mdi:current-ac",
        },
        "energy": {
            "key": "phaseEgy", # Resolve by subType to A/B/C/Total (Forward/Buy Energy)
            "name": "Forward Energy",
            "unit": UnitOfEnergy.KILO_WATT_HOUR,
            "device_class": SensorDeviceClass.ENERGY,
            "state_class": SensorStateClass.TOTAL_INCREASING,
            "icon": "mdi:transmission-tower-import",
            "scale": 0.01, # Assumption
        },
        "energy_reverse": {
            "key": "TnphaseEgy", # Reverse/Sell Energy (Total, compatible with tnPhaseEgy or sum of phases)
            "name": "Reverse Energy",
            "unit": UnitOfEnergy.KILO_WATT_HOUR,
            "device_class": SensorDeviceClass.ENERGY,
            "state_class": SensorStateClass.TOTAL_INCREASING,
            "icon": "mdi:transmission-tower-export",
            "scale": 0.01, # Assumption
        },
    },
}


class JackeryDataCoordinator:
    """Coordinator: Manages MQTT subscriptions and data polling, shared by all entities."""

    def __init__(self, hass: HomeAssistant, topic_prefix: str, token: str, mqtt_host: str, device_sn: str) -> None:
        """Initialize coordinator."""
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
        self._subdevice_missing_since = {} # {sn: timestamp} for offline marking delay
        self._device_type = None  # Host deviceType (for model display)
        self._soft_ver = None     # Firmware bundle version (softver)
        self._reauth_started = False  # Prevent redundant Token re-auth triggers
        self._ever_received = False   # Whether any valid message for this host was received since start
        self._start_time = time.time()
        self.add_entities_callback = None # Callback to add new entities
        self.add_switch_entities_callback = None # Callback to add new switch entities
        self._data_cache = {} # Cache for merged data from status and events

        # Topic patterns
        # Phase 2: Use independent MQTT topics for each host.
        # device_sn is required; subscribe to host-specific topics for task isolation.
        # Fallback to wildcard subscription + auto-discovery if device_sn is missing.
        sn_segment = self._device_sn if self._device_sn else "+"
        self._topic_status_wildcard = f"{self._topic_root}/device/{sn_segment}/status"
        self._topic_event_wildcard = f"{self._topic_root}/device/{sn_segment}/event"

    def _merge_normalized_cache(self, payload: dict[str, Any]) -> None:
        """Normalize aliases and merge into host cache."""
        self._data_cache.update(_normalize_payload_fields(payload))

    def register_sensor(self, sensor_id: str, entity: "JackerySensor") -> None:
        """Register sensor entity."""
        self._sensors[sensor_id] = entity

    def unregister_sensor(self, sensor_id: str) -> None:
        """Unregister sensor entity."""
        if sensor_id in self._sensors:
            del self._sensors[sensor_id]

    async def async_start(self) -> None:
        """Start coordinator."""
        if self._subscribed:
            return

        try:
            # Subscribe to status topic (wildcard) for discovery and data
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

            # Start periodic polling
            self._data_task = asyncio.create_task(self._periodic_data_request())

        except Exception as e:
            _LOGGER.error(f"Failed to start coordinator: {e}")

    async def async_stop(self) -> None:
        """Stop coordinator."""
        if self._data_task and not self._data_task.done():
            self._data_task.cancel()
            try:
                await self._data_task
            except asyncio.CancelledError:
                pass
        _LOGGER.info("Coordinator stopped")

    def _handle_message(self, msg) -> None:
        """Handle received MQTT message."""
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
                    # Task isolation: only handle messages for this host to prevent data contamination.
                    _LOGGER.debug(f"Ignoring data from another device: {sn}")
                    return

            # Only update heartbeat for this host's messages to ensure accurate offline detection.
            self._last_update_time = time.time()
            self._ever_received = True

            # Parse Payload
            try:
                raw_data = json.loads(payload)
                msg_code = raw_data.get("type")
                body = raw_data.get("body")

                body_sn = body.get("deviceSn") if isinstance(body, dict) else None
                is_main_device_msg = (
                        not body_sn
                        or body_sn == self._device_sn
                        or body_sn == "system"
                )
                # Capture host device model (deviceType) and firmware version (softver)
                # Only when confirmed as host's own message to prevent CT/Plug type=23 contamination.
                if is_main_device_msg and msg_code in (2, 23, 25, 106, 107):
                    self._capture_device_meta(raw_data, body)

                
                # If body is missing or None, use empty dict or the raw_data itself if it looks like data
                # But protocol says data is in body.
                if body is None:
                    if msg_code == 101:
                        return
                    flat_body = _extract_flat_body(raw_data)
                    body = flat_body if flat_body else {}

                # Merge logic
                # Type 23: Statistical/Energy Data
                if msg_code == 23 and isinstance(body, dict):
                    device_sn_in_body = body.get("deviceSn")
                    # Host statistics: deviceSn missing, matches host SN, or is "system"
                    # (Bugfix: previously only checked "system", causing host energy data loss).
                    if (
                        not device_sn_in_body
                        or device_sn_in_body == self._device_sn
                        or device_sn_in_body == "system"
                    ):
                        self._merge_normalized_cache(body)
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

                # Type 106: Grid-tied system full attributes (response to type=105)
                elif msg_code == 106 and isinstance(body, dict):
                    _LOGGER.info(
                        "Received type 106 system full data for %s (%d fields)",
                        self._device_sn,
                        len(body),
                    )
                    self._merge_normalized_cache(body)

                # Type 107: Grid-tied system incremental updates (soc, workMode)
                elif msg_code == 107 and isinstance(body, dict):
                    _LOGGER.debug(
                        "Received type 107 incremental update for %s: %s",
                        self._device_sn,
                        body,
                    )
                    self._merge_normalized_cache(body)

                # Type 102: Sub-device real-time updates (plug switchSta/outPw, CT power, etc)
                elif msg_code == 102 and isinstance(body, dict):
                    if not _merge_subdevice_arrays_into_cache(self._data_cache, body):
                        _merge_subdevice_point_update(
                            self._data_cache, body, self._device_sn
                        )

                # Type 101: Sub-device full data
                elif msg_code == 101 and isinstance(body, dict):
                    body_query_devtype = body.get("devType")
                    raw_plugs = (
                        body.get("plug")
                        or body.get("plugs")
                        or body.get("socket")
                        or body.get("sockets")
                        or []
                    )
                    raw_cts = body.get("ct") or body.get("cts") or []

                    plug_items: list[dict[str, Any]] = []
                    if isinstance(raw_plugs, list):
                        for item in raw_plugs:
                            if not isinstance(item, dict):
                                continue
                            entry = dict(item)
                            if entry.get("devType") is None:
                                entry["devType"] = 6
                            plug_items.append(entry)

                    ct_items: list[dict[str, Any]] = []
                    if isinstance(raw_cts, list):
                        for item in raw_cts:
                            if isinstance(item, dict):
                                ct_items.append(dict(item))

                    existing_plugs = [
                        p
                        for p in (self._data_cache.get("plugs") or [])
                        if isinstance(p, dict)
                        and subdevice_sensor_group(p) == "plug"
                    ]
                    existing_cts = [
                        p
                        for p in (self._data_cache.get("cts") or [])
                        if isinstance(p, dict)
                    ]
                    for p in (self._data_cache.get("plugs") or []):
                        if (
                            isinstance(p, dict)
                            and is_ct_item_dev_type(p.get("devType"))
                            and _subdevice_sn(p)
                            and _subdevice_sn(p) not in {_subdevice_sn(c) for c in existing_cts}
                        ):
                            existing_cts.append(p)

                    # Phase 2: Support sub-device removal.
                    # Replace cache list for specific devType when receiving type=101 full report, instead of simple merge.
                    if body_query_devtype == 6:
                        # Replace plug list
                        self._data_cache["plugs"] = plug_items

                        reported_plugs = {_subdevice_sn(p) for p in plug_items if _subdevice_sn(p)}
                        for sn in list(self._known_plugs):
                            # If device was known but missing from full report, it has been unbound.
                            if sn not in reported_plugs and any(
                                    k.startswith(f"jackery_{self._device_sn}_plug_{sn}") for k in self._sensors
                            ):
                                self._remove_subdevice_from_ha(sn)

                    elif body_query_devtype == 2:
                        # Replace CT list
                        self._data_cache["cts"] = ct_items

                        reported_cts = {_subdevice_sn(c) for c in ct_items if _subdevice_sn(c)}
                        for sn in list(self._known_plugs):
                            if sn not in reported_cts and any(
                                    k.startswith(f"jackery_{self._device_sn}_ct_{sn}") for k in self._sensors
                            ):
                                self._remove_subdevice_from_ha(sn)

                    else:
                        # Fallback: merge by SN if devType not specified
                        self._data_cache["plugs"] = _merge_subdevice_list(existing_plugs, plug_items)
                        self._data_cache["cts"] = _merge_subdevice_list(existing_cts, ct_items)

                    self._data_cache["plug"] = self._data_cache["plugs"]

                    _LOGGER.info(
                        "type=101 body.devType=%s (query category): plugs=%d cts=%d",
                        body_query_devtype,
                        len(self._data_cache["plugs"]),
                        len(self._data_cache["cts"]),
                    )
                    for item in plug_items:
                        _LOGGER.debug(
                            "  plug %s item.devType=%s commState=%s",
                            _subdevice_sn(item),
                            item.get("devType"),
                            item.get("commState"),
                        )
                    for item in ct_items:
                        _LOGGER.debug(
                            "  ct %s item.devType=%s subType=%s commState=%s → group=ct",
                            _subdevice_sn(item),
                            item.get("devType"),
                            item.get("subType"),
                            item.get("commState"),
                        )

                # Type 25 or other payloads (host fields + optional sub-device arrays/updates)
                elif isinstance(body, dict) and body:
                    sub_updated = _merge_subdevice_arrays_into_cache(
                        self._data_cache, body
                    )
                    point_updated = _merge_subdevice_point_update(
                        self._data_cache, body, self._device_sn
                    )
                    main_body = {
                        k: v
                        for k, v in body.items()
                        if k
                        not in (
                            "plugs",
                            "plug",
                            "socket",
                            "sockets",
                            "cts",
                            "ct",
                            "deviceSn",
                            "sn",
                        )
                    }
                    if main_body and not (point_updated and not sub_updated):
                        self._merge_normalized_cache(main_body)
                    elif not sub_updated and not point_updated:
                        self._merge_normalized_cache(body)

            except json.JSONDecodeError:
                _LOGGER.warning(f"Invalid JSON payload on {topic}")
                return

            # Enrich data with calculations using merged cache
            # operate on copy or direct? Direct is fine.
            self._data_cache = self._calculate_energy_flow(self._data_cache)
            
            # Sync plugs/CTs (add new devices; mark offline sub-devices as Unavailable)
            self._check_for_new_plugs(self._data_cache)

            self._distribute_data(self._data_cache)

        except Exception as e:
            _LOGGER.error(f"Error handling message: {e}")

    def _check_for_new_plugs(self, data: dict) -> None:
        """Sync plugs/CTs (add new devices; mark offline sub-devices as Unavailable)."""
        subdevices = _all_subdevices_from_cache(data)
        if not subdevices and data.get("plugs") is None and data.get("cts") is None:
            return

        current_sns = set()
        for item in subdevices:
            sn = _subdevice_sn(item)
            if sn:
                current_sns.add(sn)
        
        now = time.time()

        # 1. Update missing status
        for sn in current_sns:
            if sn in self._subdevice_missing_since:
                _LOGGER.info(f"Sub-device {sn} reappeared, cancelling offline timer.")
                del self._subdevice_missing_since[sn]

        for sn in self._known_plugs:
            if sn not in current_sns:
                if sn not in self._subdevice_missing_since:
                    self._subdevice_missing_since[sn] = now
                    _LOGGER.info(f"Sub-device {sn} missing, starting {OFFLINE_TIMEOUT}s offline timer...")

        # 2. Sub-device offline handling: mark as Unavailable if missing for >OFFLINE_TIMEOUT
        #    (Phase 2: mark Unavailable if data disappears, recover automatically; do not delete entity)
        for sn in current_sns:
            self._set_subdevice_available(sn, True)

        for sn in list(self._subdevice_missing_since.keys()):
            if sn not in self._known_plugs or sn in current_sns:
                del self._subdevice_missing_since[sn]
                continue

            missing_time = self._subdevice_missing_since[sn]
            if now - missing_time > OFFLINE_TIMEOUT:
                _LOGGER.info(f"Sub-device {sn} missing for >{OFFLINE_TIMEOUT}s. Marking unavailable.")
                self._set_subdevice_available(sn, False)

        # 3. Handle new devices
        ct_sns = {
            sn
            for item in (data.get("cts") or [])
            if isinstance(item, dict) and (sn := _subdevice_sn(item))
        }
        new_entities = []
        new_switch_entities = []
        for item in subdevices:
            sn = _subdevice_sn(item)
            dev_type = item.get("devType")
            from_cts = sn in ct_sns if sn else False

            if sn and sn not in self._known_plugs:
                sensor_group = subdevice_sensor_group(item, from_cts_array=from_cts)
                _LOGGER.info(
                    "Discovered new sub-device: %s (item.devType=%s, group=%s)",
                    sn,
                    dev_type,
                    sensor_group,
                )
                self._known_plugs.add(sn)

                if hasattr(self, "config_entry_id"):
                    group_config = SUBDEVICE_SENSORS.get(sensor_group, {})

                    for sensor_key, sensor_cfg in group_config.items():
                        entity = JackerySubDeviceSensor(
                            plug_sn=sn,
                            dev_type=dev_type,
                            sensor_key=sensor_key,
                            sensor_config=sensor_cfg,
                            coordinator=self,
                            config_entry_id=self.config_entry_id,
                            sensor_group=sensor_group,
                        )
                        new_entities.append(entity)

                    if should_create_plug_switch(item):
                        from .switch import JackeryPlugSwitch
                        switch_entity = JackeryPlugSwitch(
                            plug_sn=sn,
                            dev_type=dev_type,
                            coordinator=self,
                            config_entry_id=self.config_entry_id,
                        )
                        new_switch_entities.append(switch_entity)

        if new_entities and self.add_entities_callback:
            self.add_entities_callback(new_entities)
        if new_switch_entities and self.add_switch_entities_callback:
            self.add_switch_entities_callback(new_switch_entities)

    def get_subdevices(self) -> list[dict[str, Any]]:
        """Return latest sub-device list from cache."""
        return _all_subdevices_from_cache(self._data_cache)

    def _find_plug_in_cache(self, plug_sn: str) -> dict[str, Any] | None:
        """Find smart plug entry in cache."""
        for key in ("plugs", "plug"):
            items = self._data_cache.get(key)
            if not isinstance(items, list):
                continue
            for item in items:
                if isinstance(item, dict) and _subdevice_sn(item) == plug_sn:
                    return item
        return None

    def get_plug_item(self, plug_sn: str) -> dict[str, Any]:
        """Get latest plug cache (unified source for control validation and UI)."""
        return dict(self._find_plug_in_cache(plug_sn) or {})

    async def async_control_subdevice_switch(self, plug_sn: str, dev_type: int, is_on: bool) -> None:
        """Control sub-device switch via type 103 (local commMode=1 only)."""
        if not self._device_sn:
            _LOGGER.warning("Cannot control sub-device: device SN not discovered")
            raise HomeAssistantError("Host SN not discovered, cannot control plug")

        plug_item = self._find_plug_in_cache(plug_sn) or {}
        allowed, reason = plug_mqtt_control_allowed(plug_item)
        if not allowed:
            _LOGGER.warning("Plug %s control blocked: %s", plug_sn, reason)
            raise HomeAssistantError(reason)

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
                "switchSta": 1 if is_on else 0,
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
        _LOGGER.info(
            "Sent type=103 sub-device control to %s: deviceSn=%s devType=%s switchSta=%s",
            action_topic,
            plug_sn,
            dev_type,
            1 if is_on else 0,
        )
        self._apply_plug_switch_cache(plug_sn, is_on)
        self._distribute_data(self._data_cache)

    def _apply_plug_switch_cache(self, plug_sn: str, is_on: bool) -> None:
        """Optimistically update plug switch cache (switchSta) after control command."""
        switch_val = 1 if is_on else 0
        for key in ("plugs", "plug"):
            items = self._data_cache.get(key)
            if not isinstance(items, list):
                continue
            for item in items:
                if isinstance(item, dict) and _subdevice_sn(item) == plug_sn:
                    item["switchSta"] = switch_val
                    return

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

    def _capture_device_meta(self, raw_data: dict, body) -> None:
        """Capture host deviceType and softver from message, update device details if needed.

        - deviceType: located at top level (see type=25/2 examples).
        - softver: firmware bundle version, can be at top level or in body.
        """
        changed = False

        device_type = raw_data.get("deviceType")
        if device_type is not None and device_type != self._device_type:
            self._device_type = device_type
            changed = True

        soft_ver = raw_data.get("softver")
        if soft_ver is None and isinstance(body, dict):
            soft_ver = body.get("softver")
        if soft_ver is not None and soft_ver != self._soft_ver:
            self._soft_ver = soft_ver
            changed = True

        if changed:
            self._update_device_registry()

    def _update_device_registry(self) -> None:
        """Dynamically update HA device model and firmware version based on deviceType/softver."""
        entry_id = getattr(self, "config_entry_id", None)
        if not entry_id:
            return
        dev_reg = dr.async_get(self.hass)
        device = dev_reg.async_get_device(identifiers={(DOMAIN, entry_id)})
        if device is None:
            return

        updates: dict[str, Any] = {}
        if self._device_type is not None:
            model = DEVICE_TYPE_MODEL_MAP.get(self._device_type, DEFAULT_MODEL)
            if device.model != model:
                updates["model"] = model
        if self._soft_ver is not None:
            sw_version = str(self._soft_ver)
            if device.sw_version != sw_version:
                updates["sw_version"] = sw_version

        if updates:
            dev_reg.async_update_device(device.id, **updates)

    def _trigger_reauth(self, reason: str = "") -> None:
        """Trigger HA integration page "Reauthentication Required".

        Note: Device does not respond when Token is rejected (confirmed by vendor).
        Cannot determine auth failure from a single message. Using heuristic: if no response
        received for a long time after setup, Token is likely invalid (or SN is wrong).
        """
        if self._reauth_started:
            return
        self._reauth_started = True
        _LOGGER.error(
            "Device %s never responded since setup, possible Token rejection. %s",
            self._device_sn,
            reason,
        )
        entry_id = getattr(self, "config_entry_id", None)
        if not entry_id:
            return
        entry = self.hass.config_entries.async_get_entry(entry_id)
        if entry is not None:
            entry.async_start_reauth(self.hass)

    def _calculate_energy_flow(self, data: dict) -> dict:
        """
        Calculate energy flow using App formulas (prioritize type=106 systemBody).

        Grid: inGridSidePw - outGridSidePw, fallback to gridInPw - gridOutPw (matches App)
        Ongrid: gridInPw - gridOutPw (fallback to inOngridPw - outOngridPw)
        AC Socket: swEpsInPw > 0 ? swEpsInPw : swEpsOutPw (device-level type=25)
        Battery: prioritize type=106 batInPw/batOutPw; else pv + ac + ong
        Home: grid - ong; fallback to otherLoadPw if grid data is missing
        """
        try:
            # 1. PV (device-level type=25; system-level type=106 usually lacks pvPw)
            pv_val = data.get("pvPw", 0)
            if isinstance(pv_val, dict):
                pv = _safe_float(
                    pv_val.get("pvPw") or pv_val.get("w") or pv_val.get("power")
                )
            else:
                pv = _safe_float(pv_val)

            # 2. Grid-tied port power ong (multi-source, prevents type=106 zero from blocking type=25 fallback)
            grid_in = _safe_float(data.get("gridInPw"))
            grid_out = _safe_float(data.get("gridOutPw"))
            ongrid_charge = _safe_float(data.get("inOngridPw"))
            ongrid_supply = _safe_float(data.get("outOngridPw"))
            in_grid_side = _safe_float(data.get("inGridSidePw"))
            out_grid_side = _safe_float(data.get("outGridSidePw"))
            p_ong = _effective_ongrid_net(
                data,
                grid_in,
                grid_out,
                ongrid_charge,
                ongrid_supply,
                in_grid_side,
                out_grid_side,
            )

            # 3. AC Socket (device-level swEps*)
            ac_in = _safe_float(data.get("swEpsInPw"))
            ac_out = _safe_float(data.get("swEpsOutPw"))
            p_ac = ac_in - ac_out
            ac_socket = ac_in if ac_in > 0 else ac_out

            # 4. CT Meter (prioritized over system-side estimation if reliable)
            grid_available = False
            grid_buy = 0.0
            grid_sell = 0.0
            ct_available = False

            cts = data.get("cts")
            if cts and isinstance(cts, list) and len(cts) > 0:
                ct_data = cts[0]
                grid_buy, grid_sell, has_ct_fields = _extract_ct_grid_power(ct_data)
                if _ct_has_usable_power(ct_data, grid_buy, grid_sell, has_ct_fields):
                    ct_available = True
                    grid_available = True

            # 5. Net grid power (use CT if reliable, else system/device-level fallback chain)
            p_grid = 0.0
            if ct_available:
                p_grid = grid_buy - grid_sell
                if (
                    ongrid_charge > 0
                    and grid_buy < ongrid_charge
                    and (ongrid_charge - grid_buy) <= 50
                ):
                    p_grid = p_ong
                elif abs(p_grid) < 1 and abs(p_ong) > 1:
                    p_grid = p_ong
            else:
                p_grid, grid_available = _grid_net_from_system(
                    data,
                    grid_in,
                    grid_out,
                    ongrid_charge,
                    ongrid_supply,
                    in_grid_side,
                    out_grid_side,
                )

            # 7. Battery power: prioritize type=106 batInPw/batOutPw, else App formula pv+ac+ong
            bat_in = _safe_float(data.get("batInPw"))
            bat_out = _safe_float(data.get("batOutPw"))
            has_system_bat = (
                _field_present(data, "batInPw") or _field_present(data, "batOutPw")
            )
            if has_system_bat:
                p_batt = bat_in - bat_out
                calc_batt_charge = bat_in
                calc_batt_discharge = bat_out
            else:
                p_batt = pv + p_ac + p_ong
                calc_batt_charge = max(0.0, p_batt)
                calc_batt_discharge = max(0.0, -p_batt)

            # 8. Home load
            p_home = 0.0
            if grid_available:
                p_home = p_grid - p_ong

                if ct_available:
                    if (
                        grid_buy > 0
                        and ongrid_charge > 0
                        and grid_buy < ongrid_charge
                        and (ongrid_charge - grid_buy) <= 50
                    ):
                        p_home = 0.0
                    elif (
                        grid_buy > 0
                        and ongrid_charge > 0
                        and grid_buy < ongrid_charge
                        and (ongrid_charge - grid_buy) > 50
                    ):
                        p_home = ongrid_charge - grid_buy
                    elif grid_sell > 0 and ongrid_supply > 0:
                        p_home = grid_sell - ongrid_supply
                    elif grid_sell > 0 and ongrid_charge > 0:
                        p_home = grid_sell + ongrid_charge
            elif _field_present(data, "outOngridPw") and ongrid_supply > 0:
                p_home = ongrid_supply

            other_load = _safe_float(data.get("otherLoadPw"))
            if p_home == 0.0 and _field_present(data, "otherLoadPw") and other_load > 0:
                p_home = other_load

            if (
                ongrid_charge > 0
                and abs(p_grid - ongrid_charge) > 50
                and not ct_available
            ):
                _LOGGER.debug(
                    "Energy flow grid mismatch: calc_grid_net=%.1f inOngridPw=%.1f p_ong=%.1f",
                    p_grid,
                    ongrid_charge,
                    p_ong,
                )

            data["calc_ac_socket_power"] = ac_socket
            data["calc_home_power"] = p_home
            data["calc_batt_net_power"] = p_batt
            data["calc_battery_charge_power"] = calc_batt_charge
            data["calc_battery_discharge_power"] = calc_batt_discharge
            data["grid_available"] = grid_available
            data["calc_grid_net_power"] = p_grid

        except Exception as e:
            _LOGGER.error(f"Error calculating energy flow: {e}")

        return data

    def _distribute_data(self, data: dict) -> None:
        """Distribute data to sensors."""
        for sensor_id, entity in self._sensors.items():
            entity._update_from_coordinator(data)

    def _mark_all_offline(self) -> None:
        """Mark all entities as unavailable."""
        for entity in self._sensors.values():
            if entity.available:
                entity._attr_available = False
                entity.async_write_ha_state()

    def _entity_keys_for_subdevice(self, sn: str) -> list[str]:
        """Match registered entity keys for a sub-device SN (includes host SN prefix)."""
        keys = []
        prefix_plug = f"jackery_{self._device_sn}_plug_{sn}_"
        prefix_ct = f"jackery_{self._device_sn}_ct_{sn}_"
        switch_id = f"jackery_{self._device_sn}_plug_{sn}_switch"
        
        for sensor_id in self._sensors:
            if (
                sensor_id.startswith(prefix_plug)
                or sensor_id.startswith(prefix_ct)
                or sensor_id == switch_id
            ):
                keys.append(sensor_id)
        return keys

    def _set_subdevice_available(self, sn: str, available: bool) -> None:
        """Set availability for all entities of a sub-device."""
        for sensor_id in self._entity_keys_for_subdevice(sn):
            entity = self._sensors.get(sensor_id)
            if entity is None:
                continue
            if entity.available != available:
                entity._attr_available = available
                entity.async_write_ha_state()

    def _remove_subdevice_from_ha(self, sn: str) -> None:
        """Remove unbound sub-device and its entities from Home Assistant."""
        dev_reg = dr.async_get(self.hass)
        # Identifiers must match JackerySubDeviceSensor definition
        device = dev_reg.async_get_device(identifiers={(DOMAIN, f"sub_{self._device_sn}_{sn}")})

        if device:
            dev_reg.async_remove_device(device.id)
            _LOGGER.info(f"Sub-device {sn} was unbound. Removed from HA device registry.")

        # 清理内存缓存
        if sn in self._known_plugs:
            self._known_plugs.remove(sn)
        if sn in self._subdevice_missing_since:
            del self._subdevice_missing_since[sn]

        # 清除已注册的传感器引用
        keys_to_remove = self._entity_keys_for_subdevice(sn)
        for k in keys_to_remove:
            self.unregister_sensor(k)

    async def _periodic_data_request(self) -> None:
        """Periodically send 'type: 25' and 'type: 100' commands."""
        _LOGGER.info(f"Starting periodic data polling for {self._device_sn} via {self._mqtt_host}...")
        await asyncio.sleep(2)

        while True:
            try:
                if time.time() - self._last_update_time > OFFLINE_TIMEOUT:
                    self._mark_all_offline()

                # 启发式：配置后持续轮询却长时间从未收到任何响应 → 极可能 Token 无效
                if (
                    not self._ever_received
                    and self._device_sn
                    and time.time() - self._start_time > REAUTH_HINT_TIMEOUT
                ):
                    self._trigger_reauth("no response within reauth hint window")

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

                # 1b. Poll System Full Data (Type 105) - Grid-tied system full attributes (device responds with type=106)
                try:
                    payload_105 = {
                        "type": 105,
                        "eventId": 0,
                        "messageId": random.randint(1000, 9999),
                        "ts": ts,
                        "token": self._token,
                        "body": None,
                    }

                    await ha_mqtt.async_publish(
                        self.hass,
                        action_topic,
                        json.dumps(payload_105),
                        0,
                        False,
                    )
                except Exception as e:
                    _LOGGER.warning(f"Error polling system full data (Type 105): {e}")

                # 2. Poll Sub-devices (Type 100) - devType=2 CT family; devType=6 Smart Plug
                for poll_dev_type in (2, 6):
                    try:
                        payload_100 = {
                            "type": 100,
                            "eventId": 0,
                            "messageId": random.randint(1000, 9999),
                            "ts": ts,
                            "token": self._token,
                            "body": {
                                "devType": poll_dev_type,
                            },
                        }
                        await ha_mqtt.async_publish(
                            self.hass,
                            action_topic,
                            json.dumps(payload_100),
                            0,
                            False,
                        )
                    except Exception as e:
                        _LOGGER.warning(
                            "Error polling sub-devices (Type 100 devType=%s): %s",
                            poll_dev_type,
                            e,
                        )

                _LOGGER.debug(
                    "Sent poll requests (25 & 105 & 100 [2,6]) to %s", action_topic
                )

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
        if self._config.get("options") is not None:
            self._attr_options = self._config["options"]

        device_sn = getattr(coordinator, "_device_sn", None)
        self._attr_unique_id = f"jackery_{device_sn}_{sensor_id}" if device_sn else f"jackery_{sensor_id}"
        self._attr_has_entity_name = True

        device_info = {
            "identifiers": {(DOMAIN, config_entry_id)},
            "name": f"Jackery {device_sn}" if device_sn else "Jackery",
            "manufacturer": "Jackery",
            "model": "Energy Monitor",
        }
        if device_sn:
            device_info["serial_number"] = device_sn
        self._attr_device_info = device_info

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
        json_key = self._config.get("json_key")
        if not json_key or json_key not in data:
            return

        value = data[json_key]

        # Process specific conversions
        value_map = self._config.get("value_map")
        if self._sensor_id == "device_status":
            try:
                self._attr_native_value = DEVICE_STATUS_MAP.get(int(value))
            except (TypeError, ValueError):
                self._attr_native_value = None
        elif value_map is not None:
            # Generic enum mapping (e.g. ongridStat/ctStat/gridSate), keep original value if not found
            try:
                self._attr_native_value = value_map.get(int(value), value)
            except (TypeError, ValueError):
                self._attr_native_value = value
        elif self._sensor_id == "battery_temperature":
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
        attrs: dict[str, Any] = {
            "device_sn": self._coordinator._device_sn,
            "raw_key": self._config.get("json_key"),
        }
        # funcEnable bit decoding for troubleshooting
        if self._sensor_id == "func_enable":
            raw = self._coordinator._data_cache.get("funcEnable")
            try:
                bits = int(raw)
                attrs["func_enable_raw"] = bits
                attrs["func_enable_flags"] = {
                    name: bool(bits & (1 << bit))
                    for bit, name in FUNC_ENABLE_BITS.items()
                }
            except (TypeError, ValueError):
                pass
        return attrs


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
        sensor_group: str = "plug",
    ) -> None:
        """Initialize."""
        self._plug_sn = plug_sn
        self._dev_type = dev_type
        self._sensor_key = sensor_key
        self._sensor_config = sensor_config
        self._coordinator = coordinator
        self._sensor_group = sensor_group

        device_name = "CT" if sensor_group == "ct" else "Plug"

        # Entity Name: "Power", "Energy", etc.
        self._attr_name = self._sensor_config["name"]
        
        self._attr_native_unit_of_measurement = self._sensor_config.get("unit")
        self._attr_icon = self._sensor_config.get("icon")
        self._attr_device_class = self._sensor_config.get("device_class")
        self._attr_state_class = self._sensor_config.get("state_class")
        
        # Unique ID: jackery_{device_sn}_ct_{sn}_power, jackery_{device_sn}_plug_{sn}_energy, etc.
        safe_key = self._sensor_key.replace("_", "") # e.g. energy_import -> energyimport
        device_sn = getattr(coordinator, "_device_sn", "")
        self._attr_unique_id = f"jackery_{device_sn}_{device_name.lower()}_{plug_sn}_{safe_key}"
        self._attr_has_entity_name = True

        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"sub_{device_sn}_{plug_sn}")}, 
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
        if self._sensor_group == "ct":
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

        # CT phase mapping by subType (1=A, 2=B, 3=C, 4=Total)
        if self._sensor_group == "ct" and target_key in {"phasePw", "phaseEgy"}:
            sub_type = my_plug.get("subType")
            if target_key == "phasePw":
                if sub_type == 1:
                    val = my_plug.get("AphasePw") or my_plug.get("aPhasePw")
                elif sub_type == 2:
                    val = my_plug.get("BphasePw") or my_plug.get("bPhasePw")
                elif sub_type == 3:
                    # C Phase (Single phase: A+B)
                    val = my_plug.get("CphasePw") or my_plug.get("cPhasePw")
                    if not val:
                        a_pw = my_plug.get("AphasePw") or my_plug.get("aPhasePw") or 0
                        b_pw = my_plug.get("BphasePw") or my_plug.get("bPhasePw") or 0
                        if any(v is not None for v in [a_pw, b_pw]):
                            val = float(a_pw) + float(b_pw)
                else:
                    val = my_plug.get("TphasePw") or my_plug.get("tPhasePw")
            else:
                if sub_type == 1:
                    val = my_plug.get("AphaseEgy") or my_plug.get("aPhaseEgy")
                elif sub_type == 2:
                    val = my_plug.get("BphaseEgy") or my_plug.get("bPhaseEgy")
                elif sub_type == 3:
                    # C Phase (Single phase: A+B)
                    val = my_plug.get("CphaseEgy") or my_plug.get("cPhaseEgy")
                    if not val:
                        a_egy = my_plug.get("AphaseEgy") or my_plug.get("aPhaseEgy") or 0
                        b_egy = my_plug.get("BphaseEgy") or my_plug.get("bPhaseEgy") or 0
                        if any(v is not None for v in [a_egy, b_egy]):
                            val = float(a_egy) + float(b_egy)
                else:
                    val = my_plug.get("TphaseEgy") or my_plug.get("tPhaseEgy")
                # If subtype energy is zero/None but total is non-zero, fall back to the single non-zero phase
                if not val:
                    total_egy = my_plug.get("TphaseEgy") or my_plug.get("tPhaseEgy")
                    if total_egy:
                        a_egy = my_plug.get("AphaseEgy") or my_plug.get("aPhaseEgy") or 0
                        b_egy = my_plug.get("BphaseEgy") or my_plug.get("bPhaseEgy") or 0
                        c_egy = my_plug.get("CphaseEgy") or my_plug.get("cPhaseEgy") or 0
                        non_zero = [v for v in [a_egy, b_egy, c_egy] if v]
                        if len(non_zero) == 1:
                            val = non_zero[0]
        
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
        mode = plug_comm_mode(raw)
        mqtt_ok, _ = plug_mqtt_control_allowed(raw)
        return {
            "plug_sn": self._plug_sn,
            "dev_type": self._dev_type,
            "sensor_type": self._sensor_key,
            "subType": raw.get("subType"),
            # Normalized CT/plug fields (if present)
            "sn": raw.get("sn") or raw.get("deviceSn"),
            "name": raw.get("name") or raw.get("scanName"),
            "commState": raw.get("commState"),
            "commMode": mode,
            "commMode_label": COMM_MODE_LABELS.get(mode) if mode is not None else None,
            "mqtt_controllable": mqtt_ok,
            # Plug fields
            "inPw": raw.get("inPw"),
            "outPw": raw.get("outPw"),
            "switchSta": raw.get("switchSta") if raw.get("switchSta") is not None else raw.get("sysSwitch"),
            "totalEgy": raw.get("totalEgy"),
            # CT Fields
            "TphasePw": raw.get("TphasePw"),
            "TphaseEgy": raw.get("TphaseEgy"),
            "TnphaseEgy": raw.get("TnphaseEgy"),
            "tPhasePw": raw.get("tPhasePw"),
            "tPhaseEgy": raw.get("tPhaseEgy"),
            "tnPhaseEgy": raw.get("tnPhaseEgy"),
        }
