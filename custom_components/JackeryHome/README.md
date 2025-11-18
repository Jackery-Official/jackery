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

## 安装步骤

### 1. 复制文件到 Home Assistant

将 `custom_components/energy_monitor` 文件夹复制到 Home Assistant 的 `config/custom_components/` 目录下：

```
config/
  custom_components/
    energy_monitor/
      __init__.py
      manifest.json
      sensor.py
      config_flow.py
      README.md
```

### 2. 重启 Home Assistant

复制文件后，重启 Home Assistant 以加载新的集成。

### 3. 配置集成

有两种配置方式：

#### 方式 A：通过 UI 配置（推荐）

1. 进入 Home Assistant 的 **设置** → **设备与服务**
2. 点击右下角的 **添加集成** 按钮
3. 搜索 "JackeryHome"
4. 输入 MQTT 主题前缀（默认：`homeassistant/sensor`）
5. 点击提交完成配置

#### 方式 B：通过 configuration.yaml 配置

在 `configuration.yaml` 中添加：

```yaml
energy_monitor:
  topic_prefix: "homeassistant/sensor"
```

然后重启 Home Assistant。

## MQTT 主题格式

集成会订阅以下 MQTT 主题（假设 topic_prefix 为 `homeassistant/sensor`）：

- `homeassistant/sensor/solar_power/state`
- `homeassistant/sensor/home_power/state`
- `homeassistant/sensor/grid_import/state`
- `homeassistant/sensor/grid_export/state`
- `homeassistant/sensor/battery_charge/state`
- `homeassistant/sensor/battery_discharge/state`
- `homeassistant/sensor/battery_soc/state`

每个主题接收的消息格式为纯数字，例如：`1234.56`

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

### 传感器不显示数据

1. 检查 MQTT broker 是否正常运行
2. 检查 Home Assistant 的 MQTT 集成是否已配置
3. 检查 `main.py` 中的 MQTT broker 地址是否正确
4. 查看 Home Assistant 日志：**设置** → **系统** → **日志**

### 查看 MQTT 消息

使用 MQTT 客户端工具（如 MQTT Explorer）监听 `homeassistant/sensor/#` 主题，确认消息是否正常发布。

## 技术细节

- **依赖**: Home Assistant MQTT 集成
- **协议**: MQTT
- **更新方式**: Push（实时推送）
- **传感器类型**: 功率传感器、电池传感器
- **状态类**: Measurement（测量值）

## 许可证

MIT License

