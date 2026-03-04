# Role
你现在的身份是 Jackery (华宝新能) 的资深 IoT 产品经理。请根据以下项目背景和技术约束，撰写一份详细的《Jackery DIY3 系列 Home Assistant 集成插件 (HACS) 产品需求文档 (PRD)》。

# Project Background
为了满足极客用户（Geek User）对数据隐私和本地化控制的需求，我们需要开发一款基于 Home Assistant Community Store (HACS) 分发的集成插件。
核心对象是 Jackery 最新一代储能产品 "DIY3" 及其配套智能配件（自研 Smart CT、Smart Plug）。

# Core Constraints (必须严格遵守)
1. **集成方式**：采用 HACS 自定义组件 (Custom Component) 形式分发。
2. **连接架构**：
   - **Local First**：优先通过局域网直接连接设备（IP直连），确保低延迟和断网可用性。
   - **Coexistence**：必须确保“本地连接”与“原生 App 云端连接”互不干扰，设备需支持双通道并发上报数据。
3. **安全策略 (Critical)**：
   - **Read-Only (只读)**：鉴于储能设备的安全性和现有 EMS 逻辑的复杂性，本版本 **严禁开放任何控制（Write）权限**。不得包含 Switch（开关）、Slider（滑块）等控制类实体，仅提供 Sensor（传感器）与 Binary Sensor（二元传感器）。
   - **鉴权机制**：采用简单的 Token 认证机制（用户需在配置流中输入 IP 和 Token）。
4. **不开放 EMS**：所有能源管理策略（如充电优先级、市电互补逻辑）均由设备端黑盒处理，HA 仅负责展示最终状态。
. **App 端与固件端的配合**：App 端生成Token需要用户在HA里填写授权，App也会设计MQTT Enable开关，也需要设置HA的域名及端口、证书。（需要你把整个授权流程写清楚）

# Functional Requirements (详细需求)

## 1. 配置流程 (Configuration Flow)
- 设计标准的 HA Config Flow UI。
- 用户输入：Device IP Address, Local Access Token。
- 验证逻辑：尝试连接设备，验证 Token 有效性，成功后自动识别设备型号（DIY3/CT/Plug）并创建对应 Device。

## 2. 设备实体映射 (Entity Mapping)
请列出具体的传感器列表，需包含：
- **DIY3 储能主机**：
  - 实时功率（光伏输入、AC/DC 输出、市电充电）。
  - 电池状态（SOC 百分比、剩余时间、SOH）。
  - 能源统计（累计充电量 kWh、累计放电量 kWh）—— **重点：需适配 HA 自带的 "Energy Dashboard" (需定义 `state_class: total_increasing` 和 `device_class: energy`)**。
  - 运行状态（在线/离线、错误码）。
- **Smart CT (互感器)**：
  - 家庭负载实时功率。
  - 电网取电/馈电功率。
- **Smart Plug (插座)**：
  - 负载实时功率。
  - **注意：插座也必须遵循只读原则，HA 中不可控制插座开关。**

## 3. 非功能性需求 (NFR)
- **数据刷新频率**：本地轮询 (Polling) 建议在 5s - 10s 级别，或支持 WebSocket 推送（如有）。
- **异常处理**：当设备断电或离线时，实体状态需即时标记为 `Unavailable`，避免误导用户。
- **多设备支持**：单一 HA 实例需支持添加多台 DIY3 设备和多个配件。

# Deliverables (输出要求)
请按以下结构输出 PRD：
1. **文档版本历史**。
2. **项目概述与用户价值**（强调“数据主权”和“无缝集成”）。
3. **系统架构图描述**（描述 HA、设备、App 云端三者的关系）。
4. **详细功能清单 (Feature List)**，包含具体的 Entity ID 命名规范建议,以及支持的设备范围。
5. **UI/UX 交互说明**（侧重于数据展示卡片的设计建议）。
6. **风险与限制声明**（明确解释为何暂不开放 Write 权限）。

请确保文档语气专业、逻辑严密，并考虑到 Home Assistant 资深玩家的使用习惯。