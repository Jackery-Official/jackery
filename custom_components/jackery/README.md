# Jackery - Home Assistant 自定义集成

这是一个 Home Assistant 自定义集成，用于通过 MQTT 接收 Jackery 储能设备的监控数据并创建传感器实体。

## 功能特性

该集成采用**协调器模式**（Coordinator Pattern），所有传感器共享一个 `JackeryDataCoordinator` 实例，统一管理 MQTT 订阅和数据请求，提高效率并减少资源占用。

### 传感器列表

集成提供以下丰富的传感器数据：

#### 🔋 电池信息
- **Battery SOC** (电池电量) - 单位：%
- **Battery Charge Power** (电池充电功率) - 单位：W
- **Battery Discharge Power** (电池放电功率) - 单位：W
- **Battery Temperature** (电池温度) - 单位：°C
- **Battery Count** (电池数量)

#### ☀️ 太阳能 (PV)
- **Solar Power** (太阳能总功率) - 单位：W
- **Solar Power PV1 - PV4** (各路 PV 功率) - 单位：W

#### ⚡ 电网 (Grid)
- **Grid Import Power** (电网取电功率) - 单位：W
- **Grid Export Power** (电网馈电功率) - 单位：W
- **Max Output Power** (最大并网输出功率) - 单位：W

#### 🔌 EPS (离网输出)
- **EPS Output Power** (EPS 输出功率) - 单位：W
- **EPS Input Power** (EPS 输入功率) - 单位：W
- **EPS State** (EPS 状态)
- **EPS Switch Status** (EPS 开关状态)

#### ⚙️ 设置与状态
- **SOC Charge Limit** (充电 SOC 限制) - 单位：%
- **SOC Discharge Limit** (放电 SOC 限制) - 单位：%
- **Auto Standby Allowed** (是否允许自动待机)
- **Auto Standby Status** (自动待机状态)

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
4. **Token**: 输入您的设备 Token（必填，用于认证）
5. **MQTT Topic Prefix**: 输入 MQTT 主题前缀（可选，默认：`hb`）
6. 点击提交完成配置

如果 MQTT 集成未配置或不可用，将显示错误提示。

## 架构设计

### 协调器模式

集成使用 `JackeryDataCoordinator` 类统一管理所有传感器的数据获取：

- **单一协调器实例**：所有传感器共享一个协调器，避免重复订阅和请求
- **统一数据请求**：每 10 秒发送一次查询请求
- **自动分发数据**：协调器接收响应后，根据 JSON 字段自动分发给对应的传感器
- **自动发现设备**：通过监听状态主题自动获取设备序列号 (SN)

### 数据流程

1. **发现阶段**：
   - 协调器订阅通配符主题 (`hb/device/+/status`)
   - 当接收到消息时，从主题中提取设备 SN (`hb/device/{sn}/status`)

2. **轮询阶段**：
   - 获得设备 SN 后，启动定时任务（默认 10秒）
   - 向 `hb/device/{sn}/action` 发送查询指令 (`type: 25`)

3. **数据处理**：
   - 接收设备在 `status` 主题回复的 JSON 数据
   - 解析 JSON 字段（如 `batSoc`, `pvPw` 等）
   - 转换数据单位（如温度除以 10）
   - 更新所有关联的传感器实体状态

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

## 查看传感器

配置完成后，你可以在以下位置查看传感器：

- **开发者工具** → **状态** → 搜索 "jackery" 或传感器名称
- 传感器实体 ID 格式：`sensor.battery_soc`、`sensor.solar_power` 等
- 每个传感器包含以下属性：
  - `device_sn`: 设备序列号
  - `raw_key`: 原始 JSON 字段名

## 在 Lovelace 中使用

你可以使用这些传感器创建能源流图表。例如使用 Energy Flow Card Plus：

```yaml
type: custom:energy-flow-card-plus
entities:
  solar:
    entity: sensor.solar_power
    name: Solar
  grid:
    entity:
      consumption: sensor.grid_import_power
      production: sensor.grid_export_power
    name: Grid
  battery:
    entity:
      consumption: sensor.battery_charge_power
      production: sensor.battery_discharge_power
    state_of_charge: sensor.battery_soc
    name: Battery
  home:
    entity: sensor.eps_output_power  # 或其他代表家庭负载的传感器
    name: Home
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