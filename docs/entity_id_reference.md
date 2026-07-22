# Jackery Entity ID Reference



When `has_entity_name = True` in Home Assistant, the **entity_id is generated from "Device Name + Entity Display Name"**, rather than directly copying the `unique_id` from the code.



Rule: `{domain}.jackery_{sn_lowercase}_{entity_name_slug}`



Example Device SN: `HS2C12600262HH4` → Prefix `jackery_hs2c12600262hh4`



You can search for `jackery_hs2c12600262hh4` in **Developer Tools → States** to verify the actual IDs.



## Recommended Entities for Energy Flow Dashboard

> **entity_id is generated from the display name slug**, not the `sensor_id` in the code. For example, `sensor_id=calc_battery_charge_power` corresponds to the display name "Battery Charge Power (Calc)", so the actual entity_id is `battery_charge_power_calc`, **not** `calc_battery_charge_power`.

### Power Flow Card Plus Recommended Bindings (Data Verified)

| Energy Flow Node | entity_id (Grid Import/Export or Single Entity) | Source |
|-----------|----------------------------------|------|
| Solar | `sensor.jackery_{sn}_solar_power` | `pvPw` |
| Grid (Two-way) | `grid_import_power` + `grid_export_power` | `inOngridPw` / `outOngridPw` |
| Battery Charge/Discharge (Two-way) | `battery_charge_power` + `battery_discharge_power` | `batInPw` / `batOutPw` |
| Battery SOC | `sensor.jackery_{sn}_battery_soc` | `batSoc` |
| Household Load | `sensor.jackery_{sn}_home_power` | `calc_home_power` (`grid - ong`) |
| EPS | `sensor.jackery_{sn}_ac_socket_power` | `calc_ac_socket_power` |

### Calculated Entities (Optional, for Monitoring/App Formula Alignment)

| Display Name | entity_id | Description |
|--------|-----------|------|
| Grid Net Power | `sensor.jackery_{sn}_grid_net_power` | `calc_grid_net_power`; prioritizes CT when reliable, otherwise falls back to multiple sources |
| Battery Charge Power (Calc) | `sensor.jackery_{sn}_battery_charge_power_calc` | `calc_battery_charge_power` |
| Battery Discharge Power (Calc) | `sensor.jackery_{sn}_battery_discharge_power_calc` | `calc_battery_discharge_power` |
| Battery Net Power | `sensor.jackery_{sn}_battery_net_power` | `calc_batt_net_power` |
| Grid Import Power | `sensor.jackery_{sn}_grid_import_power` | `inOngridPw` (Device level type=25, recommended for topology grid import) |

For `ong`, the integration takes the maximum non-zero magnitude among `gridInPw-gridOutPw`, `inOngridPw-outOngridPw`, and `inGridSidePw-outGridSidePw` (to prevent type=106 zero values from overwriting type=25).



## Sensors (Verified Formats)



| Display Name | entity_id |
|--------|-----------|
| Battery SOC | sensor.jackery_{sn}_battery_soc |
| Battery Net Power | sensor.jackery_{sn}_battery_net_power |
| Battery Temperature | sensor.jackery_{sn}_battery_temperature |
| Home Power | sensor.jackery_{sn}_home_power |
| Grid Net Power | sensor.jackery_{sn}_grid_net_power |
| Solar Power | sensor.jackery_{sn}_solar_power |
| Device Status | sensor.jackery_{sn}_status (Display name Status, not device_status) |
| Work Mode | sensor.jackery_{sn}_work_mode |
| AC Socket Power | sensor.jackery_{sn}_ac_socket_power |
| AC Socket Power (Calc) | sensor.jackery_{sn}_ac_socket_power_calc |
| Battery Charge Power (Calc) | sensor.jackery_{sn}_battery_charge_power_calc |
| Battery Discharge Power (Calc) | sensor.jackery_{sn}_battery_discharge_power_calc |
| Grid Import Power | sensor.jackery_{sn}_grid_import_power |
| Grid Export Power | sensor.jackery_{sn}_grid_export_power |
| OnGrid Status | sensor.jackery_{sn}_ongrid_status |
| CT Status | sensor.jackery_{sn}_ct_status |
| Grid Meter Link | sensor.jackery_{sn}_grid_meter_link |
| Other Load Power | sensor.jackery_{sn}_other_load_power |
| Max Feed-in Grid Power | sensor.jackery_{sn}_max_feed_in_grid_power |
| Function Enable | sensor.jackery_{sn}_function_enable |



For the full list of sensor_ids, see the keys in the `SENSORS` dictionary in `custom_components/jackery/sensor.py` (e.g., `grid_import_power` → `sensor.jackery_{sn}_grid_import_power`).



## Control Entities



| Display Name | Type | entity_id |
|--------|------|-----------|
| EPS Switch | switch | switch.jackery_{sn}_eps_switch |
| Auto Standby Allowed | switch | switch.jackery_{sn}_auto_standby_allowed |
| Auto Standby Mode | select | select.jackery_{sn}_auto_standby_mode |
| SOC Charge Limit | number | number.jackery_{sn}_soc_charge_limit |
| SOC Discharge Limit | number | number.jackery_{sn}_soc_discharge_limit |
| Max Output Power (OnGrid) | number | number.jackery_{sn}_max_output_power_ongrid |
| Reboot | button | button.jackery_{sn}_reboot |



> **Note**: In the code, `unique_id` might follow a format like `jackery_{sn}_main_swEps`, but the **entity_id in the HA interface is typically as shown in the table above**. Do not search for `main_sweps`.



## MQTT System-level Data type=105 / 106

A grid-connected system consists of a "Main Device + Child Devices". System-level attributes need to be retrieved using system types (distinct from single-device queries using `type=25`, both coexist).

- **Query (type=105)**: The integration sends `type=105`, `body: null` to `hb/device/{sn}/action`, polling every 5 seconds.
- **Full Response (type=106)**: The device reports `type=106` via `hb/device/{sn}/event`, with the body containing all system attributes.
- **Incremental (type=107)**: See the next section.

| Protocol Field | Meaning | HA Entity / Processing |
|----------|------|----------------|
| `stat` | Overall device status 0-5 | `sensor.jackery_{sn}_status` |
| `ongridStat` | 1=Grid-connected, 0=Off-grid | `sensor.jackery_{sn}_ongrid_status` |
| `ctStat` | CT status 1=Online, 0=Offline | `sensor.jackery_{sn}_ct_status` |
| `gridSate` | CT/Reader status 1=Normal, 0=Abnormal | `sensor.jackery_{sn}_grid_meter_link` |
| `otherLoadPw` | Default load power | `sensor.jackery_{sn}_other_load_power` |
| `soc` | System SOC | Normalized to `batSoc` → `battery_soc` |
| `batNum` | Number of battery packs | `battery_count` |
| `batInPw` / `batOutPw` | Charge/Discharge power | `battery_charge_power` / `battery_discharge_power` |
| `gridInPw` / `gridOutPw` / `inGridSidePw` / `outGridSidePw` | Grid/Grid-side power | Energy flow calculation |
| `workModel` | System work mode 0-7 | Normalized to `workMode` → `work_mode` |
| `maxFeedGrid` | Max feed-in grid power (Read-only) | `sensor.jackery_{sn}_max_feed_in_grid_power` |
| `funcEnable` | Function enable bitmask | `sensor.jackery_{sn}_function_enable` (Attributes include `func_enable_flags` bit decoding) |

> Note: `workModel` (type=106) and `workMode` (type=107) have different spellings; the integration has normalized them to `workMode`.
> Control writes (`workModel` / `maxFeedGrid` / `funcEnable`) will be implemented after system setting command packets are confirmed; currently read-only.

## MQTT type=107 Incremental Reports



- **Topic**: `hb/device/{sn}/event`
- **Type**: `107`
- **Body Fields**: `soc`, `workMode`
- **Processing**: `soc` is automatically mapped to `batSoc`; `workMode` updates the `work_mode` sensor.



## Child Devices (Accessories)

Child devices are dynamically discovered via `type:101`. **Classification is based on `item.devType` in array elements**, not `body.devType`.

| item.devType | Type | entity_id Example |
|--------------|------|----------------|
| 6 | Smart Plug | `switch.jackery_plug_{sn}_switch`, `sensor.jackery_plug_{sn}_power` |
| 2/3/4 | CT/Meter | `sensor.jackery_ct_{sn}_power`, `sensor.jackery_ct_{sn}_forward_energy` |

`type:100` Polling: `body.devType: 2` (CT family), `body.devType: 6` (Smart Plug); the device responds with individual type=101 messages. Plug real-time data can also be incrementally reported via type=102 (`switchSta` / `outPw`).

### Smart Plug Control (type=103)

- **Topic**: `hb/device/{host_sn}/action`
- **Body**: `deviceSn` (Plug SN), `devType` (6), `switchSta` (`1`=ON, `0`=OFF)
- **HA Entity**: `switch.jackery_plug_{sn}_switch`
- **commMode Restrictions**:
  - `commMode=1` (Local connection) → Allows MQTT `type=103` commands.
  - `commMode=2` (Cloud platform integration) → Refuses control; HA displays a prompt: Operation required in Jackery App.
  - Switch entity attributes `mqtt_controllable` / `mqtt_control_block_reason` can be used to determine and display the reason.



## Quick Find



1. **Developer Tools → States** → Search for `jackery_hs2c12600262hh4`
2. Or **Settings → Devices & Services → Jackery → Device HS2C12600262HH4** → View the entity list; click an entity to copy the entity_id.
