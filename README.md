# JackeryHome - Home Assistant 能源监控集成

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/suyulin/jackery_home.svg)](https://github.com/suyulin/jackery_home/releases)
[![License](https://img.shields.io/github/license/suyulin/jackery_home.svg)](LICENSE)

这是一个 Home Assistant 自定义集成，通过 MQTT 监控太阳能、电网、电池和家庭能源数据。

## 功能

- 模拟太阳能发电、电网供电、家庭用电和电池充放电数据
- 通过 MQTT 自动发现功能将传感器添加到 Home Assistant
- **提供 Home Assistant 自定义集成，用于接收和显示 MQTT 数据**
- 提供 Energy Flow Card Plus 卡片配置示例

## 项目结构

本项目包含两个主要部分：

1. **MQTT 模拟器** (`main.py`) - 模拟发送能源监控数据到 MQTT broker
2. **Home Assistant 自定义集成** (`custom_components/JackeryHome/`) - 接收 MQTT 数据并创建传感器实体

### 集成架构

集成采用**协调器模式**（Coordinator Pattern）：
- 所有传感器共享一个 `JackeryDataCoordinator` 实例
- 统一管理 MQTT 订阅和数据请求
- 每 5 秒发送一次包含所有传感器 `meter_sn` 的数据请求
- 自动解析响应并分发给对应的传感器实体

## 传感器列表

本项目会创建以下传感器：

### 功率传感器（实时监测）

- `sensor.jackeryhome_solar_power`: 太阳能发电功率（W）
- `sensor.jackeryhome_home_power`: 家庭用电功率（W）
- `sensor.jackeryhome_grid_import`: 从电网购买功率（W）
- `sensor.jackeryhome_grid_export`: 向电网出售功率（W）
- `sensor.jackeryhome_battery_charge`: 电池充电功率（W）
- `sensor.jackeryhome_battery_discharge`: 电池放电功率（W）
- `sensor.jackeryhome_battery_state_of_charge`: 电池电量百分比（%）

### 能源传感器（用于能源仪表板）

- `sensor.jackeryhome_solar_energy`: 太阳能发电总量（kWh）
- `sensor.jackeryhome_home_energy`: 家庭用电总量（kWh）
- `sensor.jackeryhome_grid_import_energy`: 电网购买总量（kWh）
- `sensor.jackeryhome_grid_export_energy`: 电网出售总量（kWh）
- `sensor.jackeryhome_battery_charge_energy`: 电池充电总量（kWh）
- `sensor.jackeryhome_battery_discharge_energy`: 电池放电总量（kWh）

## 安装

### 方式一：通过 HACS 安装（推荐）

1. **添加自定义存储库**
   - 打开 HACS
   - 点击右上角三个点 → "自定义存储库"
   - 添加仓库 URL：`https://github.com/suyulin/jackery_home`
   - 类别选择：`Integration`
   - 点击"添加"

2. **安装集成**
   - 在 HACS 中搜索 "JackeryHome"
   - 点击"安装"
   - 重启 Home Assistant

3. **配置集成**
   - 进入 **设置** → **设备与服务** → **添加集成**
   - 搜索 "JackeryHome"
   - 输入 MQTT 主题前缀（默认：`homeassistant/sensor`）
   - 点击提交完成配置

### 方式二：手动安装

1. 下载最新的 [Release](https://github.com/suyulin/jackery_home/releases)
2. 将 `custom_components/JackeryHome` 文件夹复制到你的 Home Assistant 配置目录的 `custom_components/` 文件夹中
3. 重启 Home Assistant
4. 按照上述"配置集成"步骤进行配置

## 快速开始

### 使用 MQTT 模拟器

1. **安装依赖并运行模拟器**
   ```bash
   # 使用 uv（推荐）
   uv sync
   uv run main.py
   
   # 或使用 pip
   pip install paho-mqtt
   python main.py
   ```

2. **配置 MQTT Broker**
   
   编辑 `main.py` 中的地址：
   ```python
   MQTT_BROKER = "192.168.0.101"  # 修改为你的 MQTT Broker 地址
   ```

3. **在 Home Assistant 中查看传感器**
   
   传感器会自动通过 MQTT Discovery 添加

### 配置和使用

1. **确保已安装并配置集成**（参考上面的安装步骤）

2. **运行模拟器**
   ```bash
   # 使用 uv（推荐）
   uv run main.py
   
   # 或使用 python
   python main.py
   ```

3. **查看传感器数据**
   - 进入 **开发者工具** → **状态**
   - 搜索 "jackeryhome" 或传感器名称（如 "Solar Power"、"Home Power" 等）
   - 实体 ID 格式：`sensor.jackeryhome_{sensor_id}`

## Energy Flow Card Plus 配置

### 安装卡片

1. **通过 HACS 安装（推荐）：**
   - 打开 HACS
   - 点击"前端"（Frontend）
   - 搜索 "Energy Flow Card Plus"
   - 点击安装
   - 重启 Home Assistant

2. **手动安装：**
   - 从 [GitHub](https://github.com/flixlix/energy-flow-card-plus) 下载最新版本
   - 将文件放到 `www/community/energy-flow-card-plus/` 目录
   - 在 Home Assistant 中添加资源：
     - 设置 -> 仪表板 -> 右上角三点 -> 资源
     - URL: `/hacsfiles/energy-flow-card-plus/energy-flow-card-plus.js`
     - 类型: JavaScript 模块

### 添加卡片到仪表板

1. 进入仪表板编辑模式
2. 点击"添加卡片"
3. 选择"手动"（Manual）
4. 复制 `energy_flow_card_config.yaml` 中的配置
5. 保存

### 基础配置示例

```yaml
type: custom:energy-flow-card-plus
entities:
  solar:
    entity: sensor.jackeryhome_solar_power
    name: 太阳能
    icon: mdi:solar-power
  grid:
    entity:
      consumption: sensor.jackeryhome_grid_import   # 从电网购买
      production: sensor.jackeryhome_grid_export    # 向电网出售
    name: 电网
    icon: mdi:transmission-tower
  battery:
    entity:
      consumption: sensor.jackeryhome_battery_charge     # 充电
      production: sensor.jackeryhome_battery_discharge   # 放电
    state_of_charge: sensor.jackeryhome_battery_state_of_charge
    name: 电池
    icon: mdi:battery
  home:
    entity: sensor.jackeryhome_home_power
    name: 家庭用电
    icon: mdi:home-lightning-bolt
display_zero_lines:
  mode: show
  transparency: 50
  grey_color:
    - 189
    - 189
    - 189
w_decimals: 0
kw_decimals: 2
color_icons: true
animation_speed: 10
energy_date_selection: false
```

**注意**：实体 ID 格式为 `sensor.jackeryhome_{sensor_id}`，其中 `{sensor_id}` 对应传感器 ID（如 `solar_power`、`grid_import` 等）。

更多配置选项请查看 `energy_flow_card_config.yaml` 文件。

## 项目文件说明

### 核心文件
- `main.py`: MQTT 传感器模拟器主程序
- `custom_components/JackeryHome/`: Home Assistant 自定义集成
  - `__init__.py`: 集成入口
  - `manifest.json`: 集成元数据
  - `sensor.py`: 传感器平台实现（包含协调器模式和所有传感器逻辑）
  - `config_flow.py`: UI 配置流程
  - `strings.json`: 本地化字符串
  - `translations/zh-Hans.json`: 中文翻译
  - `README.md`: 集成技术文档（包含架构设计、MQTT 协议格式等）

### 文档和工具
- `INTEGRATION_GUIDE.md`: 详细的集成使用指南
- `energy_flow_card_config.yaml`: Energy Flow Card Plus 配置示例
- `install.sh`: Linux/macOS 自动安装脚本
- `install.ps1`: Windows PowerShell 自动安装脚本
- `README.md`: 项目主文档（本文件）

## 数据流向逻辑

1. **太阳能发电**：随机生成 200-3000W
2. **家庭用电**：随机生成 500-3500W
3. **电网功率**：
   - grid_import（从电网购买）：当家庭用电 > 太阳能发电时的差值
   - grid_export（向电网出售）：当太阳能发电 > 家庭用电时的差值
4. **电池功率**：
   - battery_charge（充电）：0-1000W
   - battery_discharge（放电）：0-1000W
5. **电池电量**：根据充放电动态变化（20%-100%）

## 注意事项

- 确保 Home Assistant 已配置好 MQTT 集成
- MQTT Broker 需要在运行此脚本之前启动
- 集成会每 5 秒主动请求一次数据（所有传感器共享同一个请求）
- 数据为模拟值，用于演示目的
- 集成会自动从 LWT 消息获取设备序列号，无需手动配置

## 文档

- [**HACS 发布指南**](HACS_PUBLISHING_GUIDE.md) - 如何发布到 HACS
- [自定义集成 README](custom_components/JackeryHome/README.md) - 集成技术文档

## 开发者

### 发布新版本

使用提供的发布脚本：

```bash
./prepare_release.sh
```

或手动发布：

1. 更新 `custom_components/JackeryHome/manifest.json` 中的版本号
2. 提交更改并推送到 GitHub
3. 创建新的 Git tag（如 `v1.0.1`）
4. 在 GitHub 创建 Release

详细说明请查看 [HACS 发布指南](HACS_PUBLISHING_GUIDE.md)

## 相关链接

- [Energy Flow Card Plus GitHub](https://github.com/flixlix/energy-flow-card-plus)
- [Home Assistant MQTT Discovery](https://www.home-assistant.io/integrations/mqtt/#mqtt-discovery)
- [Home Assistant 开发文档](https://developers.home-assistant.io/)
- [Paho MQTT Python Client](https://github.com/eclipse/paho.mqtt.python)

## 许可证

MIT License

