# Jackery - Home Assistant 自定义集成

这是一个 Home Assistant 自定义集成，用于通过 MQTT 接收 Jackery 储能设备的监控数据并创建传感器实体。

## 功能特性

该集成采用**协调器模式**（Coordinator Pattern），每台 DIY3 主机对应一个独立的 `JackeryDataCoordinator` 实例，统一管理该主机的 MQTT 订阅和数据请求，各主机任务相互隔离、互不影响。

> **多主机支持**：集成不限制实例数量，可重复执行配置流程添加多台 DIY3 主机。每台主机在 HA 中作为独立 Device，其下挂载的 Smart CT / Smart Plug 作为子设备展示。

### 传感器列表

集成提供以下丰富的传感器数据：

#### 📊 设备状态
- **Status** (运行状态：normal / waiting / alarm / fault / standby / low_power，对应 `stat` 0-5)

#### 🌐 并网系统状态（type=106 全量属性）
- **OnGrid Status** (并网状态 `ongridStat`：on_grid / off_grid)
- **CT Status** (CT 工作状态 `ctStat`：online / offline)
- **Grid Meter Link** (智能 CT / 读表器连接 `gridSate`：normal / abnormal)
- **Other Load Power** (默认负载功率 `otherLoadPw`) - 单位：W
- **Max Feed-in Grid Power** (最大馈网功率 `maxFeedGrid`，只读) - 单位：W
- **Function Enable** (功能使能位 `funcEnable`，属性 `func_enable_flags` 含 bit0~bit11 解码)
- **Work Mode** (系统工作模式 `workModel`/`workMode` 0-7)

#### 🔋 电池信息
- **Battery SOC** (电池电量) - 单位：%
- **Battery Charge Power / Energy** (电池充/放电功率与能量) - W / kWh
- **Battery Temperature** (电池温度) - 单位：°C
- **Battery Count** (加电包数量)
- **Battery to AC / Grid Energy** (电池到 AC 口 / 并网口能量) - kWh

#### ☀️ 太阳能 (PV)
- **Solar Power / Energy** (太阳能总功率与发电量) - W / kWh
- **Solar Power PV1 - PV4** (各路 PV 功率) - 单位：W
- **Solar Energy PV1 - PV4** (各路 PV 发电量 `pv1Egy`~`pv4Egy`) - 单位：kWh
- **PV to Battery / AC / Grid Energy** (光伏到电池 / AC 口 / 并网口能量) - kWh

#### ⚡ 电网 / 并网口 (Grid)
- **Grid Import / Export Power** (并网口输入 / 输出功率) - 单位：W
- **Grid Import / Export Energy** (并网口输入 / 输出能量) - 单位：kWh
- **Grid to AC Load / Battery Energy** (电网到 AC 负载 / 电池能量) - kWh
- **AC to Battery / Grid Energy** (AC 微逆到电池 / 并网口能量) - kWh
- **Max Output Power** (最大并网输出功率) - 单位：W

#### 🔌 EPS (离网输出)
- **EPS Output / Input Power** (EPS 输出 / 输入功率) - 单位：W
- **EPS State** (交流插座通讯状态 `swEpsState`)
- **EPS Switch Status** (EPS 开关状态)

#### ⚙️ 设置与状态（只读传感器）
- **SOC Charge / Discharge Limit** (充 / 放电 SOC 限制) - 单位：%

### 控制实体

| 类型 | 实体 | 说明 |
| :--- | :--- | :--- |
| Switch | **EPS Switch** (`swEps`) | 交流插座（离网）开关 |
| Switch | **Auto Standby Allowed** (`isAutoStandby`) | 是否允许自动待机 |
| Select | **Auto Standby Mode** (`autoStandby`) | 待机模式：invalid / standby / on（0/1/2） |
| Number | **SOC Charge / Discharge Limit** | 充电上限 / 放电下限 |
| Number | **Max Output Power (OnGrid)** | 并网口最大输出功率 |
| Button | **Reboot** | 重启主机（下发 `reboot=1`） |
| Switch | **Plug Switch** | 智能插座开 / 关（子设备，`type=103`；仅 `commMode=1` 本地连接可 MQTT 控制） |

### 子设备（Smart CT / Smart Plug）

- **Smart Plug**：负载功率、累计用电量、开 / 关开关（每台主机最多 10 个）。`commMode=1`（本地）时可通过 MQTT 控制；`commMode=2`（云平台）时 HA 会拒绝下发并提示使用 App。
- **Smart CT**：实时功率、累计正向（购电）电量 `Forward Energy`、累计反向（馈网）电量 `Reverse Energy`（每台主机最多 1 台）。
- 子设备数据从主机 MQTT 消息中消失时，对应实体标记为 `Unavailable`，重新出现时自动恢复。

## 前置要求

⚠️ **重要：本集成依赖 Home Assistant 的 MQTT 集成**

在安装 Jackery 之前，您必须先配置 MQTT 集成：

1. 进入 Home Assistant 的 **设置** → **设备与服务**
2. 点击 **添加集成**，搜索 **MQTT**
3. 配置您的 MQTT broker 连接信息：
   - **Broker**: MQTT broker 地址（例如：`localhost`、`core-mosquitto` 或 IP 地址）
   - **Port**: 端口号（默认：`1883`）
   - **Username/Password**: 如需要认证，请填写

## 安装步骤

### 方式 A：通过 HACS 安装（推荐）

1. 确保已安装 [HACS](https://hacs.xyz/)
2. 进入 HACS → 集成
3. 点击右上角菜单 → 自定义仓库
4. 添加此仓库 URL 并选择类别为"集成"
5. 搜索 "Jackery" 并安装
6. 重启 Home Assistant

### 方式 B：手动安装

将 `custom_components/jackery` 文件夹复制到 Home Assistant 的 `config/custom_components/` 目录下：

```
config/
  custom_components/
    jackery/
      __init__.py
      manifest.json
      sensor.py
      config_flow.py
      strings.json
      translations/
```

然后重启 Home Assistant。

### 配置集成

1. 进入 Home Assistant 的 **设置** → **设备与服务**
2. 点击右下角的 **添加集成** 按钮
3. 搜索 "Jackery"
4. **设备 SN**: 输入该台 DIY3 主机的序列号（必填，作为集成实例的唯一标识）
5. **Token**: 输入该设备的 Token（必填，由 Jackery APP 获取并下发给设备；下发指令时携带，设备据此鉴权执行）
6. **MQTT Topic Prefix**: 输入 MQTT 主题前缀（可选，默认：`hb`）
7. 点击提交完成配置

> **多主机**：重复以上步骤即可添加多台 DIY3 主机，每台主机需各自输入对应的 SN 与 Token；相同 SN 不能重复添加。

如果 MQTT 集成未配置或不可用，将显示错误提示。

### Token 重新认证

由于设备拒绝 Token 时不会回复任何报文，集成采用启发式判定：**配置完成后持续 5 秒轮询，若 120 秒内始终未收到任何本机消息**（极可能是 Token 无效或 SN 配错），将自动在集成页面弹出 **“Reauthentication Required”**，重新输入有效 Token 后会自动重新加载生效。

## 架构设计

### 协调器模式

每台主机使用一个 `JackeryDataCoordinator` 实例统一管理该主机的数据获取：

- **每主机一个协调器**：各主机的订阅与轮询任务相互独立，互不影响（任务隔离）
- **统一数据请求**：每 **5 秒** 发送一次查询请求（二期需求）
- **自动分发数据**：协调器接收响应后，根据 JSON 字段自动分发给对应的实体
- **本机消息过滤**：仅处理本协调器所属 `device_sn` 的报文，避免多主机数据串台

### 数据流程

1. **订阅阶段**：
   - 协调器订阅本主机专属主题 `hb/device/{sn}/status` 与 `hb/device/{sn}/event`
   - 非本机的报文会被直接忽略

2. **轮询阶段**（每 5 秒）：
   - 向 `hb/device/{sn}/action` 发送主机状态查询 (`type: 25`，单设备级)
   - 发送并网系统全量查询 (`type: 105`，`body: null`；设备以 `type: 106` 响应系统全量属性)
   - 发送子设备查询 (`type: 100`，`devType=2` 同时获取 CT/电表采集头/电表；设备分条 type=101 上报)

3. **数据处理**：
   - 接收 `status` / `event` 主题的 JSON 数据并合并进缓存
   - 解析字段（如 `batSoc`, `pvPw`、`stat`、`softver`、`deviceType` 等）
   - 显式处理 `type: 106` 系统全量上报（`workModel` → `workMode`，并网/CT/读表器状态等）
   - 显式处理 `type: 107` 增量上报（`soc` → `batSoc`，`workMode` → `work_mode` 传感器）
   - 兼容扁平 `status` 报文（无 `type`/`body` 包装时直接提取功率字段）
   - 按 App 公式计算能量流（电网、家庭负载、AC Socket、电池净功率）
   - 转换数据单位（如温度 ×0.1、能量 ×0.01）
   - 更新所有关联的实体状态，并按需刷新设备型号 / 固件版本

4. **离线与异常处理**：
   - 主机超过 **60 秒** 无消息 → 该主机所有实体标记 `Unavailable`，恢复后自动 `Available`
   - 子设备从消息中消失超过 60 秒 → 对应实体标记 `Unavailable`（不删除），重现自动恢复
   - JSON 解析失败 → 保留上一次有效缓存并记录 warning 日志

## MQTT 主题格式

集成使用以下 MQTT 主题模式（假设前缀为默认的 `hb`）：

- **状态/数据主题**: `hb/device/{sn}/status`
  - 设备在此主题发布实时状态数据
  - Payload 示例：
    ```json
    {
      "batSoc": 85,
      "batInPw": 0,
      "batOutPw": 150,
      "cellTemp": 255,
      "pvPw": 400,
      ...
    }
    ```

- **控制/查询主题**: `hb/device/{sn}/action`
  - 集成向此主题发送查询指令
  - Payload 示例：
    ```json
    {
      "type": 25,
      "eventId": 0,
      "messageId": 1234,
      "ts": 1700000000,
      "token": "YOUR_TOKEN",
      "body": null
    }
    ```

- **增量上报主题**: `hb/device/{sn}/event`（`type: 107`）
  - 设备主动推送 SOC、工作模式等增量属性
  - Payload 示例：
    ```json
    {
      "type": 107,
      "eventId": 0,
      "messageId": 3984,
      "ts": 1713337422,
      "deviceType": 3,
      "body": {
        "soc": 12,
        "workMode": 3
      }
    }
    ```

### 能量流计算公式

| 维度 | 公式 | 主要 MQTT 字段 |
|------|------|----------------|
| 光伏 | `pvPw` | `pvPw` |
| 并网口 | `gridInPw - gridOutPw`（回退 `inOngridPw - outOngridPw`） | `gridInPw`, `gridOutPw`, `inOngridPw`, `outOngridPw` |
| 电网 | CT 优先；无 CT 时 `inGridSidePw - outGridSidePw` | `TphasePw`, `TnphasePw`, `inGridSidePw`, `outGridSidePw` |
| AC Socket | `swEpsInPw > 0 ? swEpsInPw : swEpsOutPw` | `swEpsInPw`, `swEpsOutPw` |
| 电池净功率 | `pv + ac + ong` | 计算字段 `calc_batt_net_power` |
| 家庭负载 | `grid - ong`（含 CT 异常分支） | 计算字段 `calc_home_power` |

## 查看传感器

配置完成后，你可以在以下位置查看传感器：

- **设置 → 设备与服务 → Jackery** → 选择对应主机 Device 查看其全部实体
- **开发者工具** → **状态** → 搜索 "jackery" 或传感器名称
- 多主机下实体 ID 会带上主机标识（如 `sensor.jackery_<sn>_battery_soc`），下方示例请按实际实体 ID 替换
- 每个传感器包含以下属性：
  - `device_sn`: 设备序列号
  - `raw_key`: 原始 JSON 字段名

## 在 Lovelace 中使用

默认设备页会把 40+ 实体平铺展示，信息密度高但缺少层次。推荐使用自定义看板：

### 完整可视化看板（推荐）

1. 在 HACS 安装 **Mushroom Cards** 与 **Power Flow Card Plus**
2. 按 [docs/lovelace_dashboard_setup.md](../../docs/lovelace_dashboard_setup.md) 创建「Jackery 能源」仪表盘
3. 使用 [docs/lovelace_dashboard_jackery.yaml](../../docs/lovelace_dashboard_jackery.yaml) 作为原始配置
4. 实体 ID 命名规则见 [docs/entity_id_reference.md](../../docs/entity_id_reference.md)

看板结构：顶部状态芯片 → 能量流图 → 电池 / 光伏电网指标 → 控制区 → 可折叠详细数据。

### 仅能量流卡片

项目根目录 [energy_flow_card_config.yaml](../../energy_flow_card_config.yaml) 提供单卡片配置。请将实体 ID 中的 SN 替换为实际值，例如 `sensor.jackery_hs2c12600262hh4_solar_power`：

```yaml
type: custom:power-flow-card-plus
entities:
  solar:
    entity: sensor.jackery_{sn}_solar_power
  grid:
    entity: sensor.jackery_{sn}_grid_net_power
    display_state: two_way
  battery:
    entity:
      consumption: sensor.jackery_{sn}_calc_battery_charge_power
      production: sensor.jackery_{sn}_calc_battery_discharge_power
    state_of_charge: sensor.jackery_{sn}_battery_soc
    display_state: two_way
  home:
    entity: sensor.jackery_{sn}_home_power
```

## 故障排除

### 常见问题

1. **无法发现设备**：
   - 确认设备已连接到 MQTT Broker
   - 使用 MQTT 工具（如 MQTT Explorer）监听 `hb/#`，确认设备是否有发送消息
   - 确认配置中的 "Topic Prefix" 与设备实际使用的一致（默认为 `hb`）

2. **有设备 SN 但无数据更新**：
   - 检查 Token 是否正确
   - 检查日志中是否有 "Sent poll request" 记录
   - 确认设备是否响应了 `type: 25` 的请求

### 启用调试日志

在 `configuration.yaml` 中添加：

```yaml
logger:
  default: info
  logs:
    custom_components.jackery: debug
```

## 许可证

MIT License