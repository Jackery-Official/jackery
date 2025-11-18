# JackeryHome - Home Assistant 自定义集成

这是一个 Home Assistant 自定义集成，用于通过 MQTT 接收能源监控数据并创建传感器实体。

## 功能特性

该集成会自动创建以下传感器：

- **Solar Power** (太阳能发电功率) - 单位：W
- **Home Power** (家庭负载功率) - 单位：W
- **Grid Import** (电网购买功率) - 单位：W
- **Grid Export** (电网出售功率) - 单位：W
- **Battery Charge** (电池充电功率) - 单位：W
- **Battery Discharge** (电池放电功率) - 单位：W
- **Battery State of Charge** (电池电量) - 单位：%

## 前置要求

⚠️ **重要：本集成依赖 Home Assistant 的 MQTT 集成**

在安装 JackeryHome 之前，您必须先配置 MQTT 集成：

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
5. 搜索 "JackeryHome" 并安装
6. 重启 Home Assistant

### 方式 B：手动安装

将 `custom_components/JackeryHome` 文件夹复制到 Home Assistant 的 `config/custom_components/` 目录下：

```
config/
  custom_components/
    JackeryHome/
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
3. 搜索 "JackeryHome"
4. 输入 MQTT 主题前缀（可选，默认：`homeassistant/sensor`）
5. 点击提交完成配置

如果 MQTT 集成未配置或不可用，将显示错误提示。

## MQTT 主题格式

集成会订阅以下 MQTT 主题来接收设备数据：

- **LWT 主题**: `v1/iot_gw/gw_lwt` - 接收设备上线/离线状态和序列号
- **数据主题**: `v1/iot_gw/gw/data` - 接收设备响应的传感器数据

集成会定期向以下主题发送数据请求：

- **请求主题**: `v1/iot_gw/cloud/data` - 发送 `data_get` 命令请求传感器数据

消息格式遵循 Jackery 设备的标准协议（JSON 格式），包含设备序列号、meter 列表等信息。

## 与模拟器配合使用

本集成与 `main.py` 模拟器完美配合：

1. 确保 Home Assistant 已配置好 MQTT 集成并连接到同一个 MQTT broker
2. 运行 `main.py` 模拟器：
   ```bash
   python main.py
   ```
3. 模拟器会自动发布传感器数据到 MQTT
4. Home Assistant 的 JackeryHome 集成会自动接收并显示数据

## 查看传感器

配置完成后，你可以在以下位置查看传感器：

- **开发者工具** → **状态** → 搜索 "energy_monitor"
- 传感器实体 ID 格式：`sensor.solar_power`、`sensor.home_power` 等

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

### 启用调试日志

在 `configuration.yaml` 中添加：

```yaml
logger:
  default: info
  logs:
    custom_components.jackery_home: debug
    homeassistant.components.mqtt: debug
```

## 技术细节

- **依赖**: Home Assistant MQTT 集成
- **协议**: MQTT
- **更新方式**: Push（实时推送）
- **传感器类型**: 功率传感器、电池传感器
- **状态类**: Measurement（测量值）

## 许可证

MIT License

