# SolarVault 3 Series HA Entity List

### 1. Main Device

#### 1.1 Core Status & Control (R/W)

| Entity Name | Type | Description |
| :-- | --- | :-- |
| Auto Standby Allowed | `switch` | Allow the device to automatically enter standby mode |
| Auto Standby Mode | `select` | Set standby mode (invalid, standby, on) |
| AC Socket Switch | `switch` | Enable/disable off-grid output (AC Socket) |
| SOC Charge Limit | `number` | Set the upper battery charging limit |
| SOC Discharge Limit | `number` | Set the lower battery discharge limit |
| Max Output Power (OnGrid) | `number` | Set the maximum output power in On-grid mode |
| Reboot | `button` | Reboot the device |

#### 1.2 Battery & Energy Status (Read‑only)

| Entity Name             | Type     | Unit | Description |
| --- | --- | --- | --- |
| Status | `sensor` | - | Device operation status (0:normal, 1:waiting, 2:alarm, 3:fault, 4:standby, 5:low_power) |
| Work Mode | `sensor` | - | System work mode（0:Invalid, 1:Disable Energy Scheduling, 2:Self-Consumption Mode, 3:Battery Priority Mode, 4:User‑Defined， 5:TOU Mode, 6:Feed‑in Priority Mode, 7:Dynamic Pricing Mode） |
| OnGrid Status | `sensor` | - | On-grid status (1:on_grid, 0:off_grid) |
| CT Status | `sensor` | - | CT sensor online status (1:online, 0:offline) |
| Grid Meter Link | `sensor` | - | Grid meter link status (1:normal, 0:abnormal) |
| Battery SOC | `sensor` | % | Current Main Unit SOC |
| Average SOC | `sensor` | % | Current System Average SOC (Main Unit + Expansion Battery Packs) |
| Battery Temperature | `sensor` | °C | Battery internal temperature |
| Battery Count | `sensor` | - | Number of connected battery packs |
| Battery Charge Power | `sensor` | W | Current battery charging power |
| Battery Discharge Power | `sensor` | W | Current battery discharging power |
| AC Socket Status | `sensor` | - | AC Socket status (1: normal, 0: abnormal) |
| AC Socket Switch | `sensor` | - | AC Socket switch status (1:ON, 0: OFF) |

#### 1.3 Real‑time Power Statistics (Read‑only)

| Entity Name            | Type     | Unit | Description                         |
| :-- | --- | --- | --- |
| Solar Power | `sensor` | W | Total PV input power |
| Solar Power PV1 | `sensor` | W | PV1 input power |
| Solar Power PV2 | `sensor` | W | PV2 input power |
| Solar Power PV3 | `sensor` | W | PV3 input power |
| Solar Power PV4 | `sensor` | W | PV4 input power |
| Grid Port Input Power | `sensor` | W | Grid port input power |
| Grid Port Output Power | `sensor` | W | Grid port output power to grid/load |
| Other Load Power | `sensor` | W | Other load power |
| Max Feed-in Grid Power | `sensor` | W | Max feed-in grid power |
| AC Socket Input Power | `sensor` | W | AC socket input power |

#### 1.4 Cumulative Energy Statistics (Energy Dashboard supported)

| Entity Name                   | Type     | Unit | Description                              |
| --- | --- | --- | --- |
| Solar Energy | `sensor` | kWh | Cumulative PV energy generation |
| Solar Energy PV1 | `sensor` | kWh | PV1 cumulative energy |
| Solar Energy PV2 | `sensor` | kWh | PV2 cumulative energy |
| Solar Energy PV3 | `sensor` | kWh | PV3 cumulative energy |
| Solar Energy PV4 | `sensor` | kWh | PV4 cumulative energy |
| Battery Charge Energy | `sensor` | kWh | Cumulative battery charging energy |
| Battery Discharge Energy | `sensor` | kWh | Cumulative battery discharging energy |
| Grid Port Input Energy | `sensor` | kWh | Cumulative Grid Port Input Energy |
| Grid Port Output Energy | `sensor` | kWh | Cumulative Grid Port Output Energy |
| AC Socket Output Energy | `sensor` | kWh | Cumulative AC Socket output energy |
| AC Socket Input Energy | `sensor` | kWh | Cumulative AC Socket input energy |
| AC Socket to Battery Energy | `sensor` | kWh | Cumulative AC Socket to battery energy |
| PV to Battery Energy | `sensor` | kWh | Cumulative PV to battery energy |
| PV to AC Socket Energy | `sensor` | kWh | Cumulative PV to AC Socket energy |
| PV to Grid Port Energy | `sensor` | kWh | Cumulative PV to grid port energy |
| Grid Port to AC Socket Energy | `sensor` | kWh | Cumulative grid port to AC Socket energy |
| Battery to AC Socket Energy | `sensor` | kWh | Cumulative battery to AC Socket energy |
| Battery to Grid Port Energy | `sensor` | kWh | Cumulative battery to grid port energy |
| Grid Port to Battery Energy | `sensor` | kWh | Cumulative grid port to battery energy |
| AC Socket to Grid Port Energy | `sensor` | kWh | Cumulative AC Socket to grid port energy |

### 2. Sub-devices

| Entity Name              | Type     | Unit | Description              |
| --- | --- | --- | --- |
| Plug Switch | `switch` | - | Smart plug switch |
| Plug Power | `sensor` | W | Smart plug power |
| Plug Energy | `sensor` | kWh | Smart plug energy |
| CT Total Forward Power | `sensor` | W | CT Total Forward Power |
| CT Phase A Forward Power | `sensor` | W | CT Phase A Forward Power |
| CT Phase B Forward Power | `sensor` | W | CT Phase B Forward Power |
| CT Phase C Forward Power | `sensor` | W | CT Phase C Forward Power |
| CT Total Reverse Power | `sensor` | W | CT Total Reverse Power |
| CT Phase A Reverse Power | `sensor` | W | CT Phase A Reverse Power |
| CT Phase B Reverse Power | `sensor` | W | CT Phase B Reverse Power |
| CT Phase C Reverse Power | `sensor` | W | CT Phase C Reverse Power |
| CT Forward Energy | `sensor` | kWh | CT forward energy |
| CT Reverse Energy | `sensor` | kWh | CT reverse energy |
