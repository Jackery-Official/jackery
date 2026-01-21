# Jackery - Home Assistant 自定义集成

这是一个 Home Assistant 自定义集成，用于通过 MQTT 接收能源监控数据并创建传感器实体。

## 功能特性

该集成采用**协调器模式**（Coordinator Pattern），所有传感器共享一个 `JackeryDataCoordinator` 实例，统一管理 MQTT 订阅和数据请求，提高效率并减少资源占用。

### 功率传感器（实时监测）

- **Solar Power** (太阳能发电功率) - 单位：W
- **Home Power** (家庭负载功率) - 单位：W
- **Grid Import** (电网购买功率) - 单位：W
- **Grid Export** (电网出售功率) - 单位：W
- **Battery Charge** (电池充电功率) - 单位：W
- **Battery Discharge** (电池放电功率) - 单位：W
- **Battery State of Charge** (电池电量) - 单位：%

### 能源传感器（用于能源仪表板）

- **Solar Energy** (太阳能发电总量) - 单位：kWh
- **Home Energy** (家庭用电总量) - 单位：kWh
- **Grid Import Energy** (电网购买总量) - 单位：kWh
- **Grid Export Energy** (电网出售总量) - 单位：kWh
- **Battery Charge Energy** (电池充电总量) - 单位：kWh
- **Battery Discharge Energy** (电池放电总量) - 单位：kWh

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

将 `custom_components/Jackery` 文件夹复制到 Home Assistant 的 `config/custom_components/` 目录下：

```
config/
  custom_components/
    Jackery/
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
4. 输入 MQTT 主题前缀（可选，默认：`homeassistant/sensor`）
5. 点击提交完成配置

如果 MQTT 集成未配置或不可用，将显示错误提示。

## 架构设计

### 协调器模式

集成使用 `JackeryDataCoordinator` 类统一管理所有传感器的数据获取：

- **单一协调器实例**：所有传感器共享一个协调器，避免重复订阅和请求
- **统一数据请求**：每 5 秒发送一次 `data_get` 请求，包含所有传感器的 `meter_sn`
- **自动分发数据**：协调器接收响应后，根据 `meter_sn` 自动分发给对应的传感器
- **设备序列号管理**：通过 LWT 消息自动获取和更新设备序列号

### 数据流程

1. **启动阶段**：
   - 协调器订阅 LWT 主题 (`v1/iot_gw/gw_lwt`) 获取设备序列号
   - 协调器订阅数据响应主题 (`v1/iot_gw/gw/data`)
   - 启动定时任务，每 5 秒发送一次数据请求

2. **数据请求**：
   - 协调器收集所有传感器的 `meter_sn`
   - 构造包含所有 `meter_sn` 的 `data_get` 请求
   - 发送到 `v1/iot_gw/cloud/data` 主题

3. **数据处理**：
   - 接收设备响应（JSON 格式）
   - 解析 `meter_list` 中的 `[meter_sn, meter_value]` 数据
   - 根据 `meter_sn` 匹配对应的传感器实体
   - 调用传感器的 `_process_meter_value()` 处理特殊值（如正负分离）
   - 更新传感器状态并通知 Home Assistant

## MQTT 主题格式

集成会订阅以下 MQTT 主题来接收设备数据：

- **LWT 主题**: `v1/iot_gw/gw_lwt` - 接收设备上线/离线状态和序列号
  ```json
  {
    "gw_sn": "26392658575364"
  }
  ```

- **数据响应主题**: `v1/iot_gw/gw/data` - 接收设备响应的传感器数据
  ```json
  {
    "cmd": "data_get",
    "info": {
      "dev_list": [
        {
          "dev_sn": "ems_26392658575364",
          "meter_list": [
            ["1026001", 2500.0],
            ["21171201", 1800.0],
            ...
          ]
        }
      ]
    }
  }
  ```

集成会定期向以下主题发送数据请求：

- **请求主题**: `v1/iot_gw/cloud/data` - 发送 `data_get` 命令请求传感器数据
  ```json
  {
    "cmd": "data_get",
    "gw_sn": "26392658575364",
    "timestamp": "1234567890123",
    "token": "5678",
    "info": {
      "dev_list": [
        {
          "dev_sn": "ems_26392658575364",
          "meter_list": ["1026001", "21171201", "16930817", ...]
        }
      ]
    }
  }
  ```

### 数据请求间隔

- **默认间隔**：5 秒（`REQUEST_INTERVAL = 5`）
- 所有传感器共享同一个请求，减少 MQTT 消息数量

## 与模拟器配合使用

本集成与 `main.py` 模拟器完美配合：

1. 确保 Home Assistant 已配置好 MQTT 集成并连接到同一个 MQTT broker
2. 运行 `main.py` 模拟器：
   ```bash
   python main.py
   ```
3. 模拟器会自动发布传感器数据到 MQTT
4. Home Assistant 的 Jackery 集成会自动接收并显示数据

## 查看传感器

配置完成后，你可以在以下位置查看传感器：

- **开发者工具** → **状态** → 搜索 "jackery" 或传感器名称
- 传感器实体 ID 格式：`sensor.solar_power`、`sensor.home_power`、`sensor.solar_energy` 等
- 每个传感器包含以下属性：
  - `sensor_id`: 传感器内部标识
  - `meter_sn`: 对应的 meter 序列号
  - `device_sn`: 设备序列号（从 LWT 消息获取）

## 在 Lovelace 中使用

你可以使用这些传感器创建能源流图表。例如使用 Energy Flow Card：

```yaml
type: custom:energy-flow-card-plus
entities:
  solar:
    entity: sensor.solar_power
  grid:
    entity:
      consumption: sensor.grid_import
      production: sensor.grid_export
  battery:
    entity:
      consumption: sensor.battery_charge
      production: sensor.battery_discharge
    state_of_charge: sensor.battery_soc
  home:
    entity: sensor.home_power
```

## 故障排除

### MQTT 连接错误

如果看到 "Host is unreachable" 或 "MQTT not ready" 错误：

1. **检查 MQTT 集成**：确保 MQTT 集成已配置且连接正常
2. **验证 Broker 地址**：确认 MQTT broker 地址和端口正确
3. **测试连接**：在终端使用 `mosquitto_sub` 测试 MQTT 连接
4. **查看详细日志**：启用调试日志查看更多信息

详细的故障排除指南请参考：[TROUBLESHOOTING.md](../../../TROUBLESHOOTING.md)

### 传感器不显示数据

1. 检查 MQTT broker 是否正常运行
2. 确认设备已连接并发送 LWT 消息到 `v1/iot_gw/gw_lwt`
3. 使用 MQTT Explorer 监听 `v1/iot_gw/#` 主题查看消息
4. 查看 Home Assistant 日志：**设置** → **系统** → **日志**
5. 确认传感器属性中的 `device_sn` 是否正确
6. 检查协调器是否已启动：日志中应看到 "Coordinator subscribed to LWT topic" 和 "Coordinator subscribed to data topic"
7. 确认数据请求是否发送：日志中应看到 "Coordinator sent data_get request"
8. 验证设备响应格式：响应应包含 `cmd: "data_get"` 和正确的 `meter_list` 结构

### 启用调试日志

在 `configuration.yaml` 中添加：

```yaml
logger:
  default: info
  logs:
    custom_components.jackery: debug
    homeassistant.components.mqtt: debug
```

## 传感器值处理逻辑

集成会根据传感器类型对原始 `meter_value` 进行特殊处理：

- **Grid Import**：仅显示负值（取绝对值），正值显示为 0
- **Grid Export**：仅显示正值，负值显示为 0
- **Battery Charge**：仅显示负值（取绝对值），正值显示为 0
- **Battery Discharge**：仅显示正值，负值显示为 0
- **Battery SOC**：原始值乘以 0.1 转换为百分比
- **其他传感器**：直接使用原始值

## Meter SN 映射

每个传感器对应一个唯一的 `meter_sn`，用于在设备响应中识别数据：

| 传感器 ID | Meter SN |
|----------|----------|
| `solar_power` | 1026001 |
| `home_power` | 21171201 |
| `grid_import_power` / `grid_export_power` | 16930817 |
| `battery_charge_power` / `battery_discharge_power` | 16931841 |
| `battery_soc` | 21548033 |
| `solar_energy` | 16961537 |
| `home_energy` | 16936961 |
| `grid_import_energy` | 16959489 |
| `grid_export_energy` | 16960513 |
| `battery_charge_energy` | 16952321 |
| `battery_discharge_energy` | 16953345 |

## 技术细节

- **架构模式**: 协调器模式（Coordinator Pattern）
- **依赖**: Home Assistant MQTT 集成
- **协议**: MQTT (QoS 1)
- **更新方式**: 主动请求 + 推送响应（每 5 秒）
- **传感器类型**: 功率传感器、能源传感器、电池传感器
- **状态类**: 
  - 功率传感器：`MEASUREMENT`（测量值）
  - 能源传感器：`TOTAL_INCREASING`（累计递增）
  - 电池传感器：`MEASUREMENT`（测量值）
- **设备类**: `POWER`、`ENERGY`、`BATTERY`

## 许可证

MIT License

