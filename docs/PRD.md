# Jackery DIY3 系列 Home Assistant 集成插件 (HACS) 产品需求文档

---

## 文档版本历史

| 版本 | 日期 | 作者 | 变更说明 |
|------|------|------|----------|
| 1.0 | 2025-03-04 | 黄国庆 | 初稿：完整功能定义、架构设计、实体清单 |

---

## 1. 项目概述与用户价值

### 1.1 项目背景

Jackery（华宝新能）最新一代户用储能产品 **DIY3** 面向全球市场。为满足极客用户（Geek User）对 **数据主权** 和 **本地化控制** 的强烈诉求，需开发一款基于 Home Assistant Community Store (HACS) 分发的自定义集成插件，将 DIY3 主机及其配套智能配件（Smart CT、Smart Plug）无缝接入 Home Assistant 生态。

### 1.2 目标用户

| 用户画像 | 描述 |
|----------|------|
| 核心用户 | 拥有 Jackery DIY3 储能系统、同时是 Home Assistant 活跃用户的技术爱好者 |
| 典型特征 | 重视数据隐私、偏好本地优先架构、熟悉 HACS 安装流程、有能力自建 HA 实例 |
| 地域分布 | 欧美及亚太市场的独立屋/别墅用户为主 |

### 1.3 用户价值

#### 数据主权 (Data Sovereignty)

- 所有能源数据通过 **局域网 HTTP 直连** 获取，不依赖云端中转。
- 数据在用户自有 HA 实例内存储与处理，完全由用户掌控。
- 即使互联网中断，本地数据采集与展示不受影响。

#### 无缝集成 (Seamless Integration)

- 一键通过 HACS 安装，标准 Config Flow 配置，无需编写 YAML。
- 支持 mDNS 设备自动发现，降低手动输入 IP 的门槛。
- 传感器实体完全适配 HA 原生 **Energy Dashboard**，用户可直接查看太阳能发电、电池充放、电网交互等能源数据。

#### 与云端共存 (Cloud Coexistence)

- 本地集成**不影响**设备与 Jackery Cloud 的连接。
- 用户可同时使用 Jackery APP（云端）和 HA（本地）查看设备数据，两条通道独立并存、互不干扰。

---

## 2. 系统架构

### 2.1 整体架构描述

```
┌──────────────────────────────────────────────────────────────────────┐
│                            用户家庭局域网                             │
│                                                                      │
│  ┌──────────────┐    HTTP/REST (局域网)    ┌─────────────────────┐   │
│  │              │◄──────────────────────────│  Jackery DIY3 主机   │   │
│  │  Home        │    mDNS 设备发现          │  ┌───────────────┐  │   │
│  │  Assistant   │◄─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ │  │ HTTP API      │  │   │
│  │              │                           │  │ (Token Auth)  │  │   │
│  │  ┌────────┐  │                           │  └───────────────┘  │   │
│  │  │Jackery │  │                           │                     │   │
│  │  │HACS    │  │                           │  ┌─────┐  ┌──────┐ │   │
│  │  │集成     │  │                           │  │CT x1│  │Plug  │ │   │
│  │  └────────┘  │                           │  │     │  │ x10  │ │   │
│  └──────────────┘                           │  └─────┘  └──────┘ │   │
│                                             └────────┬────────────┘   │
└──────────────────────────────────────────────────────┼────────────────┘
                                                       │
                                              Cloud (独立通道)
                                                       │
                                                       ▼
                                            ┌─────────────────────┐
                                            │   Jackery Cloud     │
                                            │   ┌─────────────┐   │
                                            │   │ Jackery APP  │   │
                                            │   └─────────────┘   │
                                            └─────────────────────┘
```

### 2.2 架构要点

| 要点 | 说明 |
|------|------|
| **连接方式** | HA 通过局域网 HTTP/REST API 直连 DIY3 主机，Token 鉴权 |
| **设备发现** | 支持 mDNS 自动发现局域网内的 DIY3 设备，同时支持手动输入 IP |
| **数据获取** | HA 定时轮询 DIY3 主机的 HTTP API，获取主机及全部子设备数据 |
| **云端共存** | DIY3 主机同时保持与 Jackery Cloud 的独立连接，APP 功能不受影响 |
| **子设备拓扑** | Smart CT 和 Smart Plug 通过主机内部协议连接，HA 仅与主机通信；主机负责聚合子设备数据，统一通过 HTTP API 返回 |
| **安全策略** | 本版本严格只读，仅提供 Sensor 与 Binary Sensor，不包含任何控制类实体 |

### 2.3 授权流程

以下描述用户从零开始完成授权的完整流程：

```
┌─────────┐          ┌─────────────┐          ┌──────────────┐
│  用户    │          │ Jackery APP │          │ Home Assistant│
└────┬────┘          └──────┬──────┘          └──────┬───────┘
     │                      │                        │
     │  1. 打开 APP 设备页  │                        │
     │─────────────────────>│                        │
     │                      │                        │
     │  2. 进入"HA 集成"    │                        │
     │     设置页面         │                        │
     │─────────────────────>│                        │
     │                      │                        │
     │  3. 开启 "MQTT/本地  │                        │
     │     访问" 开关       │                        │
     │─────────────────────>│                        │
     │                      │                        │
     │                      │  4. APP 生成一次性     │
     │                      │     Local Access Token │
     │                      │  5. 设备固件启用       │
     │                      │     HTTP API 服务      │
     │                      │──────────────────────> │
     │                      │                (设备端) │
     │  6. APP 展示 Token   │                        │
     │     供用户复制       │                        │
     │<─────────────────────│                        │
     │                      │                        │
     │  7. 打开 HA，添加    │                        │
     │     Jackery 集成     │                        │
     │─────────────────────────────────────────────>│
     │                      │                        │
     │  8. HA 通过 mDNS     │                        │
     │     发现设备（或手   │                        │
     │     动输入 IP）      │                        │
     │─────────────────────────────────────────────>│
     │                      │                        │
     │  9. 输入 Token       │                        │
     │─────────────────────────────────────────────>│
     │                      │                        │
     │                      │       10. HA 以 Token  │
     │                      │       调用设备 HTTP    │
     │                      │       API 验证连通性   │
     │                      │<───────────────────────│
     │                      │                        │
     │  11. 验证成功，自动  │                        │
     │      创建设备与实体  │                        │
     │<─────────────────────────────────────────────│
     │                      │                        │
     │  ✅ 完成配置          │                        │
```

**授权流程分步说明：**

| 步骤 | 执行方 | 动作 |
|------|--------|------|
| 1–3 | 用户 → APP | 在 Jackery APP 中找到目标设备，进入「Home Assistant / 本地访问」设置页，打开本地访问开关 |
| 4–5 | APP → 设备 | APP 向设备下发指令，生成一次性 Local Access Token 并启用设备端 HTTP API 服务 |
| 6 | APP → 用户 | APP 界面展示 Token（支持复制），同时显示设备 IP 地址 |
| 7–9 | 用户 → HA | 在 HA 中添加 Jackery 集成，选择已发现设备（或手动输入 IP），粘贴 Token |
| 10 | HA → 设备 | HA 使用 Token 调用设备 HTTP API 进行连通性与鉴权验证 |
| 11 | HA | 验证通过后自动识别设备型号，创建 Device 及全部 Sensor 实体 |

> **注意**：当前版本 Token 无过期机制，也不支持续期。后续版本将考虑 Token 生命周期管理（见第 9 节路线图）。

---

## 3. 核心约束

以下约束在本版本中 **必须严格遵守**，不可协商。

| 编号 | 约束 | 说明 |
|------|------|------|
| C-1 | **HACS 分发** | 以 Custom Component 形式通过 HACS 安装，不进入 HA 官方核心库 |
| C-2 | **Local First** | 优先局域网 HTTP 直连，确保低延迟与断网可用 |
| C-3 | **云端共存** | 本地连接不影响设备与 Jackery Cloud 的通信，APP 功能完整 |
| C-4 | **严格只读** | 本版本 **禁止任何控制操作**。不得包含 Switch、Number、Button 等可写实体，仅提供 Sensor 与 Binary Sensor |
| C-5 | **不暴露 EMS** | 能源管理策略（充电优先级、市电互补等）由设备端黑盒处理，HA 仅展示最终状态 |
| C-6 | **Token 鉴权** | 使用 Jackery APP 生成的一次性 Token 进行身份验证 |

---

## 4. 设备支持范围

### 4.1 支持设备列表

| 设备 | 类型 | 数量限制 | 连接方式 |
|------|------|----------|----------|
| **DIY3 主机** | 储能主机 | 每条集成配置对应 1 台主机；同一 HA 支持添加多台 | 局域网 HTTP 直连 |
| **Smart CT** | 智能互感器 | 每台主机最多 1 台 | 通过主机内部协议连接，数据由主机聚合上报 |
| **Smart Plug** | 智能插座 | 每台主机最多 10 个 | 通过主机内部协议连接，数据由主机聚合上报 |

### 4.2 Smart CT 规格

| 特性 | 说明 |
|------|------|
| 电气类型 | 支持单相与三相 |
| 上报数据 | 各相电压 (V)、电流 (A)、有功功率 (W)；总有功功率 (W)；能量 (kWh) |
| 典型用途 | 安装于家庭电表侧，监测家庭总负载与电网交互 |

### 4.3 Smart Plug 规格

| 特性 | 说明 |
|------|------|
| 上报数据 | 实时功率 (W)、累计能量 (kWh)、开关状态（只读展示） |
| 数量 | 单台主机最多配对 10 个 |
| 注意 | HA 中 **不可控制** 插座开关，遵循只读原则 |

---

## 5. 详细功能清单

### 5.1 配置流程 (Config Flow)

#### 5.1.1 流程设计

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────────┐     ┌──────────────┐
│  添加集成    │────>│  设备发现        │────>│  输入 Token     │────>│  验证与创建  │
│              │     │  (mDNS 列表     │     │                 │     │  设备/实体   │
│              │     │   或手动输入 IP) │     │                 │     │              │
└──────────────┘     └──────────────────┘     └─────────────────┘     └──────────────┘
```

#### 5.1.2 Config Flow 步骤

| 步骤 | 名称 | 说明 |
|------|------|------|
| Step 1 | 设备选择 | 展示通过 mDNS 发现的 DIY3 设备列表（显示设备名称 + IP），同时提供「手动输入 IP」选项 |
| Step 2 | Token 输入 | 用户粘贴从 Jackery APP 获取的 Local Access Token |
| Step 3 | 连接验证 | 集成以 Token 调用设备 HTTP API 验证连通性与鉴权；失败时显示明确错误信息（见 5.1.3） |
| Step 4 | 设备创建 | 验证成功后自动识别设备型号及已连接的子设备（CT、Plug），创建 Device 与全部 Sensor 实体 |

#### 5.1.3 错误处理

| 错误场景 | 错误码 | 用户提示文案 |
|----------|--------|-------------|
| 设备 IP 不可达 | `cannot_connect` | "无法连接到设备，请检查设备是否在线且与 Home Assistant 在同一局域网内" |
| Token 无效 | `invalid_auth` | "Token 验证失败，请检查 Token 是否正确。可在 Jackery APP 中重新生成" |
| 设备已被添加 | `already_configured` | "该设备已添加到 Home Assistant" |
| 设备不支持 | `unsupported_device` | "该设备型号暂不支持，请确认固件已更新至最新版本" |
| 设备未启用本地访问 | `local_access_disabled` | "设备的本地访问功能未开启，请在 Jackery APP 中开启" |

#### 5.1.4 多设备支持

- **不限制实例数量**：用户可重复执行配置流程添加多台 DIY3 主机。
- 每台主机为独立的 HA Device，其下挂载的 CT 和 Plug 为子设备。
- 各主机使用独立的 HTTP 连接与轮询任务，互不影响。

### 5.2 实体映射 (Entity Mapping)

#### 5.2.1 Entity ID 命名规范

```
sensor.jackery_{device_sn}_{entity_key}
binary_sensor.jackery_{device_sn}_{entity_key}
```

- `device_sn`：设备序列号，自动从设备 API 获取，全小写，特殊字符替换为下划线。
- `entity_key`：实体标识，采用 `snake_case`，与下方表格中的 Key 列对应。
- 子设备 Entity ID 格式：`sensor.jackery_{sub_device_sn}_{entity_key}`

**示例**：

```
sensor.jackery_diy3a12345_battery_soc
sensor.jackery_diy3a12345_solar_power
sensor.jackery_ct00001_grid_import_power
sensor.jackery_plug00001_load_power
binary_sensor.jackery_diy3a12345_online
```

#### 5.2.2 DIY3 主机实体

**功率传感器 (实时功率)**

| Key | 名称 | 单位 | device_class | state_class | 图标 | 说明 |
|-----|------|------|-------------|-------------|------|------|
| `solar_power` | Solar Power | W | `power` | `measurement` | `mdi:solar-power` | 光伏总输入功率 |
| `solar_power_pv1` | Solar Power PV1 | W | `power` | `measurement` | `mdi:solar-panel` | PV1 通道输入功率 |
| `solar_power_pv2` | Solar Power PV2 | W | `power` | `measurement` | `mdi:solar-panel` | PV2 通道输入功率 |
| `battery_charge_power` | Battery Charge Power | W | `power` | `measurement` | `mdi:battery-charging` | 电池充电功率 |
| `battery_discharge_power` | Battery Discharge Power | W | `power` | `measurement` | `mdi:battery-minus` | 电池放电功率 |
| `grid_import_power` | Grid Import Power | W | `power` | `measurement` | `mdi:transmission-tower-import` | 市电输入（购电）功率 |
| `grid_export_power` | Grid Export Power | W | `power` | `measurement` | `mdi:transmission-tower-export` | 馈网输出（售电）功率 |
| `eps_output_power` | EPS Output Power | W | `power` | `measurement` | `mdi:power-plug` | EPS 离网输出功率 |
| `home_power` | Home Power | W | `power` | `measurement` | `mdi:home-lightning-bolt` | 家庭用电功率（计算值） |

**电池状态**

| Key | 名称 | 单位 | device_class | state_class | 图标 | 说明 |
|-----|------|------|-------------|-------------|------|------|
| `battery_soc` | Battery SOC | % | `battery` | `measurement` | `mdi:battery` | 电池剩余电量百分比 |
| `battery_soh` | Battery SOH | % | — | `measurement` | `mdi:battery-heart-variant` | 电池健康度 |
| `battery_temperature` | Battery Temperature | °C | `temperature` | `measurement` | `mdi:thermometer` | 电池温度 |
| `battery_count` | Battery Count | — | — | `measurement` | `mdi:battery-multiple` | 已连接电池包数量 |

**能量统计 (Energy Dashboard 适配)**

| Key | 名称 | 单位 | device_class | state_class | 图标 | 说明 |
|-----|------|------|-------------|-------------|------|------|
| `solar_energy` | Solar Energy | kWh | `energy` | `total_increasing` | `mdi:solar-power` | 光伏累计发电量 |
| `battery_charge_energy` | Battery Charge Energy | kWh | `energy` | `total_increasing` | `mdi:battery-plus` | 电池累计充电量 |
| `battery_discharge_energy` | Battery Discharge Energy | kWh | `energy` | `total_increasing` | `mdi:battery-minus` | 电池累计放电量 |
| `grid_import_energy` | Grid Import Energy | kWh | `energy` | `total_increasing` | `mdi:transmission-tower-import` | 累计购电量 |
| `grid_export_energy` | Grid Export Energy | kWh | `energy` | `total_increasing` | `mdi:transmission-tower-export` | 累计馈网电量 |
| `eps_output_energy` | EPS Output Energy | kWh | `energy` | `total_increasing` | `mdi:power-plug` | EPS 累计输出电量 |

**运行状态**

| Key | 名称 | 类型 | device_class | 图标 | 说明 |
|-----|------|------|-------------|------|------|
| `online` | Online | `binary_sensor` | `connectivity` | `mdi:lan-connect` | 设备在线状态（基于 HTTP 响应） |
| `error_code` | Error Code | `sensor` | — | `mdi:alert-circle` | 当前错误码，无错误时为 0 |
| `error_message` | Error Message | `sensor` | — | `mdi:alert-circle-outline` | 错误码对应的可读描述（见 5.2.6） |

#### 5.2.3 Smart CT 实体

| Key | 名称 | 单位 | device_class | state_class | 图标 | 说明 |
|-----|------|------|-------------|-------------|------|------|
| `grid_power` | Grid Power | W | `power` | `measurement` | `mdi:current-ac` | 电网总有功功率（正=购电，负=馈电） |
| `phase_a_power` | Phase A Power | W | `power` | `measurement` | `mdi:current-ac` | A 相有功功率 |
| `phase_b_power` | Phase B Power | W | `power` | `measurement` | `mdi:current-ac` | B 相有功功率（三相时） |
| `phase_c_power` | Phase C Power | W | `power` | `measurement` | `mdi:current-ac` | C 相有功功率（三相时） |
| `phase_a_voltage` | Phase A Voltage | V | `voltage` | `measurement` | `mdi:flash` | A 相电压 |
| `phase_b_voltage` | Phase B Voltage | V | `voltage` | `measurement` | `mdi:flash` | B 相电压（三相时） |
| `phase_c_voltage` | Phase C Voltage | V | `voltage` | `measurement` | `mdi:flash` | C 相电压（三相时） |
| `phase_a_current` | Phase A Current | A | `current` | `measurement` | `mdi:current-ac` | A 相电流 |
| `phase_b_current` | Phase B Current | A | `current` | `measurement` | `mdi:current-ac` | B 相电流（三相时） |
| `phase_c_current` | Phase C Current | A | `current` | `measurement` | `mdi:current-ac` | C 相电流（三相时） |
| `grid_import_energy` | Grid Import Energy | kWh | `energy` | `total_increasing` | `mdi:transmission-tower-import` | 累计正向（购电）电量 |
| `grid_export_energy` | Grid Export Energy | kWh | `energy` | `total_increasing` | `mdi:transmission-tower-export` | 累计反向（馈网）电量 |

> **注意**：单相配置时，B/C 相实体将不被创建；集成根据设备 API 返回的 CT 类型自动判断。

#### 5.2.4 Smart Plug 实体

| Key | 名称 | 单位 | device_class | state_class | 图标 | 说明 |
|-----|------|------|-------------|-------------|------|------|
| `load_power` | Load Power | W | `power` | `measurement` | `mdi:power-socket-eu` | 插座负载实时功率 |
| `load_energy` | Load Energy | kWh | `energy` | `total_increasing` | `mdi:lightning-bolt` | 插座累计用电量 |
| `switch_state` | Switch State | — | `binary_sensor` / `power` | — | `mdi:toggle-switch` | 插座开关状态（只读展示，1=开/0=关） |

> **注意**：`switch_state` 为 **Binary Sensor**，仅展示当前开关状态，用户 **不可** 在 HA 中操控。

#### 5.2.5 HA Device 信息

每个设备在 HA 中注册的 Device 信息如下：

| 字段 | DIY3 主机 | Smart CT | Smart Plug |
|------|-----------|----------|------------|
| `name` | Jackery DIY3 {SN 后 4 位} | Jackery Smart CT {SN 后 4 位} | Jackery Smart Plug {SN 后 4 位} |
| `manufacturer` | Jackery | Jackery | Jackery |
| `model` | DIY3 | Smart CT | Smart Plug |
| `identifiers` | `(DOMAIN, device_sn)` | `(DOMAIN, ct_sn)` | `(DOMAIN, plug_sn)` |
| `via_device` | — | 所属 DIY3 主机 | 所属 DIY3 主机 |

#### 5.2.6 错误码定义

| 错误码 | 级别 | 描述 (error_message) | 说明 |
|--------|------|---------------------|------|
| 0 | — | "Normal" | 正常运行 |
| 1001 | Warning | "Battery Over Temperature" | 电池温度过高 |
| 1002 | Warning | "Battery Under Temperature" | 电池温度过低 |
| 1003 | Error | "Battery Over Voltage" | 电池过压保护 |
| 1004 | Error | "Battery Under Voltage" | 电池欠压保护 |
| 1005 | Error | "Battery Communication Error" | 电池通讯异常 |
| 2001 | Warning | "PV Over Voltage" | 光伏过压 |
| 2002 | Warning | "PV Reverse Connection" | 光伏反接 |
| 3001 | Error | "Grid Frequency Abnormal" | 电网频率异常 |
| 3002 | Error | "Grid Voltage Abnormal" | 电网电压异常 |
| 4001 | Error | "Inverter Over Temperature" | 逆变器过温 |
| 4002 | Error | "Inverter Overload" | 逆变器过载 |
| 5001 | Warning | "CT Communication Lost" | CT 通讯丢失 |
| 5002 | Warning | "Plug Communication Lost" | 插座通讯丢失 |
| 9999 | Error | "Unknown Error" | 未知错误 |

> 以上错误码为建议定义，实际以设备固件返回的错误码为准。集成内置映射表负责翻译为可读文案；未映射码统一展示为 `Unknown Error ({code})`。

---

## 6. UI/UX 交互说明

### 6.1 设备页面

添加成功后，在 HA **设置 → 设备与服务 → Jackery** 下可看到：

- **设备列表**：每台 DIY3 主机为一个独立设备，其下关联的 CT 和 Plug 以子设备形式展示。
- **设备详情**：显示设备型号、SN、固件版本（如有）、在线状态。
- **实体列表**：该设备下的全部 Sensor 与 Binary Sensor。

### 6.2 Energy Dashboard 适配

以下实体可直接配置到 HA 原生 **Energy Dashboard**：

| Dashboard 栏位 | 对应实体 |
|----------------|----------|
| Solar Production | `sensor.jackery_{sn}_solar_energy` |
| Battery Systems — Energy going in | `sensor.jackery_{sn}_battery_charge_energy` |
| Battery Systems — Energy coming out | `sensor.jackery_{sn}_battery_discharge_energy` |
| Grid — Consumption | `sensor.jackery_{sn}_grid_import_energy` 或 CT 的 `grid_import_energy` |
| Grid — Return to grid | `sensor.jackery_{sn}_grid_export_energy` 或 CT 的 `grid_export_energy` |

---

## 7. 非功能性需求

### 7.1 数据刷新

| 参数 | 值 | 说明 |
|------|-----|------|
| 轮询间隔 | **5 秒** | 通过 HTTP GET 定时拉取设备 API，兼顾实时性与资源占用 |
| 协议 | HTTP/REST | 局域网直连，请求-响应模式 |
| 超时设置 | 单次请求超时 **5 秒** | 超时后标记本次请求失败，等待下次轮询 |

### 7.2 离线与异常处理

| 场景 | 处理策略 |
|------|----------|
| 设备网络不可达 | 连续 **3 次** 轮询失败（约 15 秒）后将该设备及其子设备全部实体标记为 `Unavailable` |
| 设备恢复在线 | 下一次轮询成功后自动恢复所有实体状态为 `Available` |
| 子设备离线 | CT 或 Plug 从设备 API 返回中消失时，对应实体标记为 `Unavailable`；重新出现时恢复 |
| Token 失效 | API 返回 401/403 时，记录日志并在 HA 集成页面显示 **"Reauthentication Required"** 提示 |
| API 格式异常 | 解析失败时保持上一次有效数据，记录 warning 日志 |

### 7.3 性能要求

| 指标 | 目标值 |
|------|--------|
| 单次 API 请求耗时 | < 500ms（局域网环境） |
| 内存占用 | < 50MB（10 台设备场景） |
| CPU 影响 | 单台设备轮询对 HA 主进程 CPU 增量 < 1% |

### 7.4 兼容性

| 项目 | 要求 |
|------|------|
| Home Assistant 最低版本 | **2024.6.0**（需 mDNS 发现与最新 ConfigFlow API 支持） |
| Python 版本 | ≥ 3.12（随 HA 版本要求） |
| HACS 版本 | ≥ 2.0 |
| 设备固件 | 需设备端固件支持本地 HTTP API（由 Jackery APP ≥ 2.10.18 触发启用） |

---

## 8. 风险与限制声明

### 8.1 为何暂不开放 Write 权限

| 维度 | 说明 |
|------|------|
| **安全性** | 储能设备涉及大功率电池充放电，错误的控制指令可能引发电气安全风险。设备端 EMS（能源管理系统）包含复杂的保护逻辑（温度限流、SOC 保护、并离网切换等），在 HA 侧开放控制需确保 **完全复现** 这些保护逻辑，否则存在安全隐患 |
| **可靠性** | HA 作为第三方平台，其自动化脚本、网络延迟等因素可能导致指令时序异常。储能设备对指令时序有严格要求（如并网/离网切换），不当操作可能导致设备保护性停机 |
| **责任边界** | 开放控制权限后，因第三方自动化引发的设备异常难以界定责任。从产品合规与用户安全角度，需待本地 API 的安全校验机制成熟后再逐步开放 |
| **EMS 复杂性** | 能源管理策略涉及电价时段、天气预测、电池寿命优化等多维度决策，当前由设备端黑盒实现。在 HA 侧暴露控制接口需要定义清晰的 API 语义与状态机，这需要更长的设计与测试周期 |

### 8.2 已知限制

| 限制 | 说明 | 影响 |
|------|------|------|
| Token 无续期 | 当前 Token 一次性生成，无过期与续期机制 | 若 Token 泄露，需用户在 APP 重新生成 |
| 无 TLS 加密 | 当前本地 HTTP 通信为明文 | 局域网内风险可控，但不适用于跨网段访问 |
| 不支持固件升级 | HA 集成不提供 OTA 功能 | 固件升级需通过 Jackery APP 完成 |
| 无历史数据回填 | 集成仅采集实时与累计数据 | 集成首次安装前的历史数据不可追溯 |
| 仅支持 DIY3 | 当前版本仅适配 DIY3 系列 | 其他型号需后续版本支持 |

---

## 9. 后期规划路线图

以下为基于当前版本的能力演进规划，按优先级排列：

| 优先级 | 阶段 | 功能 | 说明 |
|--------|------|------|------|
| P0 | V1.0 | **本版本交付内容** | 只读集成、mDNS 发现、HTTP 轮询、全量 Sensor |
| P1 | V1.1 | **Token 生命周期管理** | Token 过期提醒、APP 端续期/吊销、HA 侧 Reauthentication Flow |
| P1 | V1.1 | **WebSocket 推送** | 将 HTTP 轮询升级为 WebSocket 长连接，降低延迟与资源消耗 |
| P1 | V1.1 | **TLS 加密** | 设备端启用 HTTPS（自签证书或 Jackery CA 签发），保护局域网通信 |
| P2 | V1.2 | **诊断与日志** | 在 HA 集成页面提供「诊断」按钮，导出连接日志与设备状态快照 |
| P2 | V1.2 | **可配置刷新间隔** | 在集成 Options Flow 中允许用户调整轮询频率（1s–30s） |
| P2 | V1.2 | **设备友好命名** | 支持在配置流或 Options 中自定义设备显示名称 |
| P3 | V2.0 | **有限控制权限** | 开放低风险操作（如设置 SOC 上/下限），需设备端 API 支持指令校验 |
| P3 | V2.0 | **多型号支持** | 扩展至其他 Jackery 储能产品线 |
| P3 | V2.0 | **OAuth 2.0 授权** | 替换一次性 Token，实现标准化的 OAuth 2.0 Device Flow 授权 |
| P4 | V2.x | **EMS 策略透传** | 在 HA 中展示/切换设备端预定义的 EMS 策略（如「自用优先」「馈网优先」），但策略执行仍由设备端负责 |
| P4 | V2.x | **HA 官方核心集成** | 代码质量与覆盖率达标后，提交至 HA 核心仓库，成为官方内置集成 |
| P4 | V2.x | **固件版本展示** | 在 HA Device 信息中展示当前固件版本，并提示是否有新版本可用（不执行 OTA） |

---

## 附录 A：术语表

| 术语 | 说明 |
|------|------|
| DIY3 | Jackery 最新一代户用储能产品项目代号/型号 |
| Smart CT | 智能互感器，安装于电表侧，监测电网交互数据 |
| Smart Plug | 智能插座，监测单一负载的功率与用电量 |
| EMS | Energy Management System，能源管理系统 |
| SOC | State of Charge，电池剩余电量百分比 |
| SOH | State of Health，电池健康度百分比 |
| EPS | Emergency Power Supply，应急电源/离网输出 |
| HACS | Home Assistant Community Store，社区插件商店 |
| mDNS | Multicast DNS，局域网设备自动发现协议 |
| Config Flow | HA 标准配置向导 UI 框架 |
| Energy Dashboard | HA 内置能源仪表盘 |

---

## 附录 B：参考资料

| 资源 | 链接 |
|------|------|
| Home Assistant 开发文档 | https://developers.home-assistant.io/ |
| HACS 开发指南 | https://hacs.xyz/docs/developer/start |
| HA Energy Dashboard 文档 | https://www.home-assistant.io/docs/energy/ |
| HA Config Flow 文档 | https://developers.home-assistant.io/docs/config_entries_config_flow_handler |
| HA Sensor Entity 文档 | https://developers.home-assistant.io/docs/core/entity/sensor |
| Power Flow Card Plus | https://github.com/flixlix/power-flow-card-plus |

---

*文档结束*
