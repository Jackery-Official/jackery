# Jackery SolarVault3 系列本地 MQTT 通信协议 (全量技术手册)

本手册详细描述了 Jackery SolarVault3 系列储能系统与本地控制系统（如 Home Assistant）之间的 MQTT 通信协议。本手册旨在实现 100% 的字段与指令覆盖。

---

## 1. 通信基础与架构

### 1.1 通信参数
- **协议**: MQTT v3.1.1
- **格式**: JSON
- **心跳/超时**: 默认建议轮询间隔 5 秒，离线判定超时 60 秒。

### 1.2 Topic 路由表
Topic 结构为 `{prefix}/device/{SN}/{topic_type}`。

| Topic 类型 | 模式 | 描述 | 消息方向 |
| :--- | :--- | :--- | :--- |
| **Status** | `hb/device/{SN}/status` | 主机状态上报、轮询响应、能量流数据 | 设备 -> 系统 |
| **Event** | `hb/device/{SN}/event` | 子设备全量报告、实时变动事件 | 设备 -> 系统 |
| **Action** | `hb/device/{SN}/action` | 发送控制指令、下发轮询请求 | 系统 -> 设备 |

### 1.3 消息包装结构 (Envelope)
所有上报或下发的消息均包装在以下 JSON 结构中：

```json
{
  "type": 106,
  "eventId": 0,
  "messageId": 4567,
  "ts": 1695347700,
  "token": "YOUR_TOKEN",
  "body": { ... },
  "deviceType": 3,
  "softver": 1001
}
```

- **`type`**: 指令类型码 (见第 2 节)。
- **`token`**: 身份识别码，本地控制指令必填。
- **`body`**: 具体的业务数据载荷。
- **`deviceType`**: 主机设备类型（1: Battery Pack, 2: CT/Meter, 3: DIY3, 4: Meter Collector）。
- **`softver`**: 固件包版本号。

---

## 2. 指令类型码 (Type Codes) 总览

| 类型码 | 含义 | 用途 |
| :--- | :--- | :--- |
| **1** | 主机控制 (Action) | 下发设置变更（如 EPS 开关、自动待机） |
| **2** | 全量设置读取 (Status) | 返回主机所有配置参数与状态 |
| **23** | 统计数据 (Status/Event) | 上报能量统计（累计充发电量） |
| **25** | 设备基础状态 (Status) | 上报当前功率、SOC、运行模式 |
| **100** | 子设备查询 (Action) | 系统下发，请求查询 CT 或智能插座列表 |
| **101** | 子设备全量列表 (Event) | 设备返回，包含所有已连接子设备的详情 |
| **102** | 子设备增量更新 (Event) | 子设备状态变动（如插座开关、功率变化）时实时上报 |
| **103** | 子设备控制 (Action) | 下发子设备动作（如智能插座开关） |
| **105** | 系统全量查询 (Action) | 请求系统完整运行参数 |
| **106** | 系统全量响应 (Status) | 返回并网状态、CT 状态、网侧详细功率等 |
| **107** | 系统增量更新 (Status) | 上报 SOC、工作模式等关键变化 |
| **123** | 异常通知 (Status) | 鉴权失败或系统报错（errorCode 401: Token 错误） |

---

## 3. 监控字段手册 (Monitoring Fields)

### 3.1 主机状态 (Host / System) - body 字段
| JSON Key | 描述 | 单位/映射 |
| :--- | :--- | :--- |
| `stat` | 主机运行状态 | 0:正常, 1:等待, 2:告警, 3:故障, 4:待机, 5:低功耗 |
| `workMode` / `workModel` | 系统工作模式 | 整数 (具体含义视型号而定) |
| `batSoc` | 电池电量 (SOC) | % |
| `soc` | 系统平均电量 | % |
| `pvPw` | 总光伏功率 | W |
| `pv1` / `pv2` / `pv3` / `pv4` | 各路光伏输入功率 | W |
| `batInPw` | 电池充电功率 | W |
| `batOutPw` | 电池放电功率 | W |
| `cellTemp` | 电池温度 | 0.1 ℃ (原始值 250 = 25.0℃) |
| `batNum` | 连接的电池包数量 | 个 |
| `gridInPw` / `gridBuyPw` | 网侧输入功率 (买电) | W |
| `gridOutPw` / `gridSellPw` | 网侧输出功率 (卖电) | W |
| `inOngridPw` | 并网口充电功率 | W |
| `outOngridPw` | 并网口放电功率 | W |
| `inGridSidePw` | 电表侧输入功率 | W |
| `outGridSidePw` | 电表侧输出功率 | W |
| `swEpsInPw` | AC 插座输入功率 | W |
| `swEpsOutPw` | AC 插座输出功率 | W |
| `swEpsState` | AC 插座状态 | 1:正常, 0:异常 |
| `swEps` | AC 插座开关状态 | 1:开启, 0:关闭 |
| `ongridStat` | 并网状态 | 1:并网, 0:离网 |
| `ctStat` | CT 状态 | 1:在线, 0:离线 |
| `gridSate` | 电表通讯链路 | 1:正常, 0:异常 |
| `otherLoadPw` | 其他负载功率 | W |
| `maxFeedGrid` | 最大向电网馈送功率 | W |
| `socChgLimit` | SOC 充电限制 | % |
| `socDischgLimit` | SOC 放电限制 | % |
| `funcEnable` | 功能启用位图 | 12位位图 (见 3.3) |

### 3.2 能量统计 (Energy Statistics) - Type 23
| JSON Key | 描述 | 单位 (缩放 0.01) |
| :--- | :--- | :--- |
| `batChgEgy` | 电池累计充电 | kWh |
| `batDisChgEgy` | 电池累计放电 | kWh |
| `pvEgy` | 累计光伏发电总计 | kWh |
| `pv1Egy` / `pv2Egy` / `pv3Egy` / `pv4Egy` | 各路光伏累计发电 | kWh |
| `inOngridEgy` | 并网口累计输入电量 | kWh |
| `outOngridEgy` | 并网口累计输出电量 | kWh |
| `outEpsEgy` | AC 插座累计输出电量 | kWh |
| `inEpsEgy` | AC 插座累计输入电量 | kWh |
| `acOtBatEgy` | AC 充电池累计电量 | kWh |
| `pvOtBatEgy` | PV 充电池累计电量 | kWh |
| `pvOtAcEgy` | PV 供 AC 累计电量 | kWh |
| `pvOtOngridEgy` | PV 供电网累计电量 | kWh |
| `ongridOtAcLoadEgy` | 电网供 AC 累计电量 | kWh |
| `batOtAcEgy` | 电池供 AC 累计电量 | kWh |
| `batOtGridEgy` | 电池供电网累计电量 | kWh |
| `ongridOtBatEgy` | 电网充电池累计电量 | kWh |
| `acOtOngridEgy` | AC 供电网累计电量 | kWh |

### 3.3 功能位图 (`funcEnable` Bit Definition)
位 (Bit) 从 0 开始：
- `0`: 气溶胶 (aerosol)
- `1`: SOC 校准 (soc_calibration)
- `2`: 低功耗模式 (low_power)
- `3`: SOH 校准 (soh_calibration)
- `4`: PCS 通讯诊断 (pcs_comm_diag)
- `5`: 2小时停机 (shutdown_2h)
- `6`: 故障停机 (fault_shutdown)
- `7`: EPO 功能 (epo)
- `8`: 48V 功能 (func_48v)
- `9`: 以太网调试 (ethernet_debug)
- `10`: 能量流数据回填 (energy_flow_fill)
- `11`: 智能插座优先 (smart_plug_first)

---

## 4. 子设备手册 (Sub-devices)

子设备数据通常包含在 `plugs` 或 `cts` 数组中。

### 4.1 智能插座 (Smart Plug)
| Key | 描述 | 备注 |
| :--- | :--- | :--- |
| `deviceSn` / `sn` | 子设备序列号 | 唯一标识 |
| `devType` | 设备类型码 | 智能插座通常为 6 或 1 |
| `outPw` / `power` | 当前功率 | W |
| `inPw` | 输入功率 | W |
| `totalEgy` | 累计用电量 | kWh (缩放 0.01) |
| `switchSta` / `sysSwitch` | 开关状态 | 1:开, 0:关 |
| `commState` | 通讯状态 | 1:在线, 0:离线 |
| `commMode` | 通讯模式 | 1:本地, 2:云端 (见第 5 节) |

### 4.2 CT 电表 (CT / Meter)
| Key | 描述 | 备注 |
| :--- | :--- | :--- |
| `subType` | CT 型号类型码 | 1: Shelly 1P, 2: Shelly 3P, 6: Jackery US, 等 |
| `TphasePw` / `tPhasePw` | 总正向功率 | W (买电) |
| `TnphasePw` / `tnPhasePw` | 总反向功率 | W (卖电) |
| `AphasePw` / `BphasePw` / `CphasePw` | 各相正向功率 | W |
| `anPhasePw` / `bnPhasePw` / `cnPhasePw` | 各相反向功率 | W |
| `TphaseEgy` / `tPhaseEgy` | 总正向电量 | kWh (缩放 0.01) |
| `TnphaseEgy` / `tnPhaseEgy` | 总反向电量 | kWh (缩放 0.01) |

---

## 5. 控制指令集 (Control Commands)

### 5.1 主机设置 (`type 1`)
用于修改系统全局参数。

```json
{
  "type": 1,
  "body": {
    "cmd": 5,      // 固定为 5
    "rc": 1,       // 固定为 1
    "swEps": 1,    // 开启 AC 插座 (0 为关闭)
    "isAutoStandby": 0 // 禁止自动待机 (1 为允许)
  }
}
```

### 5.2 子设备开关 (`type 103`)
用于控制智能插座。

```json
{
  "type": 103,
  "body": {
    "deviceSn": "PLUG_SN_XXXX",
    "devType": 6,
    "sysSwitch": 1 // 1:开, 0:关
  }
}
```
**重要限制条件**: 
仅当插座上报的 `commMode == 1` (本地模式) 时，此指令才会生效。若 `commMode == 2`，必须通过官方 App 控制，本地 MQTT 指令将被忽略。

### 5.3 主动轮询请求 (`type 100`)
用于强制设备刷新子设备列表。

```json
{
  "type": 100,
  "body": {
    "devType": 6 // 6:插座, 2:CT
  }
}
```

---

## 6. 能量流计算逻辑 (Internal Logic)

本地集成通过以下公式实现能量流的精确计算：

### 6.1 网侧净功率 (`p_grid`)
1. **优先级 1 (CT 电表)**: 若 CT 在线且数据可用：
   `p_grid = TphasePw - TnphasePw`
2. **优先级 2 (系统估算)**: 若无 CT，按以下顺序尝试：
   - `inGridSidePw - outGridSidePw`
   - `gridInPw - gridOutPw`
   - `inOngridPw - outOngridPw`

### 6.2 家庭负载功率 (`p_home`)
公式: `p_home = p_grid - p_ong`
- `p_ong` 为并网口净功率 (`gridInPw - gridOutPw`)。
- 当 `p_home` 计算结果为 0 时，回退使用 `otherLoadPw`。

### 6.3 电池净功率 (`p_batt`)
1. **直接读取**: 若 `batInPw` 或 `batOutPw` 存在：
   `p_batt = batInPw - batOutPw`
2. **逻辑推算**: 若无直接上报：
   `p_batt = pvPw + (swEpsInPw - swEpsOutPw) + (gridInPw - gridOutPw)`
   *(即：光伏输入 + AC插座净输入 + 并网口净输入)*

---

## 7. 常见问题与排障

### 7.1 为什么控制指令无效？
- 检查消息是否包含正确的 `token`。
- 检查目标 Topic 是否为 `action`。
- 对于智能插座，检查其 `commMode` 是否为 `1`。

### 7.2 收到鉴权错误 (Type 123)
- `errorCode 401`: 表示 Token 与设备内部存储的不匹配。需重新核对 Token 并确保设备已连接至本地网络。

### 7.3 数据不更新
- 确保持续向 `action` 发送轮询请求（集成默认每 5 秒发送一次 `type 25`, `type 105`, `type 2`, `type 100`）。
