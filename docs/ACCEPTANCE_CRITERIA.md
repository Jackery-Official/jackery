# Jackery DIY3 Home Assistant 集成插件 — 产品验收标准

---

## 文档版本历史

| 版本 | 日期 | 作者 | 变更说明 |
|------|------|------|----------|
| 1.0 | 2025-03-04 | Jackery IoT PM | 初稿：基于 PRD V1.0 生成全量验收标准 |

> 本文档为 PRD V1.0 的配套验收标准，所有验收项均可追溯到 PRD 中对应章节。

---

## 1. 验收总则

### 1.1 验收范围

本文档覆盖 Jackery DIY3 Home Assistant 集成插件 V1.0 的全部产品需求验收，包括：

- 安装与分发
- 配置流程（Config Flow）
- 设备发现与多设备支持
- 实体映射与数据准确性
- 只读安全约束
- 离线与异常处理
- 性能与兼容性
- UI/UX 展示
- 云端共存

### 1.2 验收环境要求

| 项目 | 要求 |
|------|------|
| Home Assistant 版本 | ≥ 2024.6.0 |
| HACS 版本 | ≥ 2.0 |
| Jackery APP 版本 | ≥ 2.10.18 |
| 设备固件 | 支持本地 MQTT 功能 |
| MQTT Broker | 本地 MQTT Broker（如 Mosquitto）已运行，HA 内置 MQTT 集成已连接 |
| 网络环境 | HA 与 DIY3 主机处于同一局域网 |
| 测试设备 | DIY3 主机 ×1（最少）、Smart CT ×1、Smart Plug ×2（最少） |

### 1.3 验收结论标准

| 结论 | 条件 |
|------|------|
| **通过** | 全部「必须 (MUST)」项通过，「应当 (SHOULD)」项通过率 ≥ 90% |
| **有条件通过** | 全部「必须」项通过，「应当」项通过率 ≥ 70%，未通过项有明确修复计划 |
| **不通过** | 任一「必须」项未通过 |

---

## 2. 安装与分发

| 编号 | 级别 | 验收项 | 预期结果 | 对应 PRD |
|------|------|--------|----------|----------|
| INS-01 | MUST | 通过 HACS 添加自定义仓库并安装 Jackery 集成 | 可在 HACS 中搜索到 "Jackery"，点击安装后提示重启 HA | §3 C-1 |
| INS-02 | MUST | 重启 HA 后集成可用 | 在「设置 → 设备与服务 → 添加集成」中可搜索到 "Jackery" | §3 C-1 |
| INS-03 | MUST | HACS 验证与 Hassfest 验证通过 | CI 中 `hacs/action` 与 `hassfest` 均为绿色 | §3 C-1 |
| INS-04 | SHOULD | 卸载集成后清理完全 | 删除集成后，所有关联的 Device、Entity 被移除，无残留数据 | — |

---

## 3. 配置流程 (Config Flow)

### 3.1 设备发现

| 编号 | 级别 | 验收项 | 预期结果 | 对应 PRD |
|------|------|--------|----------|----------|
| CFG-01 | MUST | mDNS 自动发现局域网内 DIY3 设备 | 添加集成时，设备列表中展示已开启本地访问的 DIY3 设备（显示设备名称 + SN） | §5.1.2 Step 1 |
| CFG-02 | MUST | 支持手动输入设备 SN | 设备列表中提供「手动输入」选项，用户可直接键入设备 SN | §5.1.2 Step 1 |
| CFG-03 | SHOULD | 未开启本地访问的设备不出现在发现列表中 | 仅已启用 MQTT 功能的设备可被发现 | §2.3 |

### 3.2 Token 验证

| 编号 | 级别 | 验收项 | 预期结果 | 对应 PRD |
|------|------|--------|----------|----------|
| CFG-04 | MUST | 正确 Token 可通过验证 | 输入从 APP 获取的有效 Token 后，验证成功并进入设备创建步骤 | §5.1.2 Step 2–3 |
| CFG-05 | MUST | 错误 Token 被拒绝并显示明确提示 | 输入错误 Token 后，提示 "Token 验证失败，请检查 Token 是否正确。可在 Jackery APP 中重新生成" | §5.1.3 `invalid_auth` |
| CFG-06 | MUST | 设备不可达时显示明确提示 | MQTT 不可用或设备未连接 Broker 时，提示 "无法连接到设备，请检查 MQTT 集成与设备是否均已连接到 Broker" | §5.1.3 `cannot_connect` |
| CFG-07 | MUST | 重复添加同一设备被阻止 | 再次添加已配置的设备时，提示 "该设备已添加到 Home Assistant" | §5.1.3 `already_configured` |
| CFG-08 | SHOULD | 不支持的设备型号显示明确提示 | 提示 "该设备型号暂不支持，请确认固件已更新至最新版本" | §5.1.3 `unsupported_device` |
| CFG-09 | SHOULD | 未启用本地访问的设备显示明确提示 | 提示 "设备的本地访问功能未开启，请在 Jackery APP 中开启" | §5.1.3 `local_access_disabled` |

### 3.3 设备创建

| 编号 | 级别 | 验收项 | 预期结果 | 对应 PRD |
|------|------|--------|----------|----------|
| CFG-10 | MUST | 验证成功后自动创建 DIY3 主机 Device | 在「设备与服务」中可看到 Jackery DIY3 设备，显示型号与 SN | §5.1.2 Step 4 |
| CFG-11 | MUST | 自动识别并创建已连接的 Smart CT 子设备 | CT 以子设备形式出现在主机设备下 | §5.1.2 Step 4 |
| CFG-12 | MUST | 自动识别并创建已连接的 Smart Plug 子设备 | 各 Plug 以子设备形式出现在主机设备下 | §5.1.2 Step 4 |
| CFG-13 | MUST | 所有 Sensor 与 Binary Sensor 实体自动创建 | 主机、CT、Plug 下的全部传感器实体按 PRD 定义自动生成 | §5.2 |

### 3.4 多设备支持

| 编号 | 级别 | 验收项 | 预期结果 | 对应 PRD |
|------|------|--------|----------|----------|
| CFG-14 | MUST | 支持添加第二台 DIY3 主机 | 重复配置流程可成功添加第二台主机，两台设备独立运行 | §5.1.4 |
| CFG-15 | MUST | 多台设备的实体互不干扰 | 各设备的传感器数据独立更新，不会混淆 | §5.1.4 |
| CFG-16 | SHOULD | 删除一台设备不影响其他设备 | 删除其中一台主机的集成配置，另一台继续正常工作 | §5.1.4 |

---

## 4. 实体映射与数据准确性

### 4.1 Entity ID 命名

| 编号 | 级别 | 验收项 | 预期结果 | 对应 PRD |
|------|------|--------|----------|----------|
| ENT-01 | MUST | Entity ID 符合命名规范 | 格式为 `sensor.jackery_{device_sn}_{entity_key}`，SN 全小写 | §5.2.1 |
| ENT-02 | MUST | 子设备 Entity ID 使用子设备 SN | CT/Plug 实体使用各自的 SN 而非主机 SN | §5.2.1 |

### 4.2 DIY3 主机传感器

| 编号 | 级别 | 验收项 | 预期结果 | 对应 PRD |
|------|------|--------|----------|----------|
| ENT-03 | MUST | 光伏总功率传感器存在且有数值 | `solar_power` 实体存在，单位 W，数值与设备实际一致 | §5.2.2 |
| ENT-04 | MUST | 光伏分路功率传感器存在 | `solar_power_pv1`、`solar_power_pv2` 实体存在 | §5.2.2 |
| ENT-05 | MUST | 电池充电/放电功率传感器存在 | `battery_charge_power`、`battery_discharge_power` 实体存在且数值正确 | §5.2.2 |
| ENT-06 | MUST | 市电购电/馈网功率传感器存在 | `grid_import_power`、`grid_export_power` 实体存在 | §5.2.2 |
| ENT-07 | MUST | EPS 输出功率传感器存在 | `eps_output_power` 实体存在 | §5.2.2 |
| ENT-08 | MUST | 家庭用电功率传感器存在 | `home_power` 实体存在，数值为计算值 | §5.2.2 |
| ENT-09 | MUST | 电池 SOC 传感器存在 | `battery_soc` 实体存在，单位 %，范围 0–100 | §5.2.2 |
| ENT-10 | SHOULD | 电池 SOH 传感器存在 | `battery_soh` 实体存在 | §5.2.2 |
| ENT-11 | MUST | 电池温度传感器存在 | `battery_temperature` 实体存在，单位 °C | §5.2.2 |
| ENT-12 | MUST | 在线状态 Binary Sensor 存在 | `online` 实体存在，设备在线时为 ON | §5.2.2 |
| ENT-13 | MUST | 错误码传感器存在 | `error_code` 实体存在，正常时为 0 | §5.2.2 |
| ENT-14 | SHOULD | 错误码文案传感器存在 | `error_message` 实体存在，正常时显示 "Normal" | §5.2.6 |

### 4.3 能量统计传感器 (Energy Dashboard)

| 编号 | 级别 | 验收项 | 预期结果 | 对应 PRD |
|------|------|--------|----------|----------|
| ENT-15 | MUST | 所有能量传感器 `device_class` 为 `energy` | `solar_energy`、`battery_charge_energy`、`battery_discharge_energy`、`grid_import_energy`、`grid_export_energy`、`eps_output_energy` 均为 `energy` | §5.2.2 |
| ENT-16 | MUST | 所有能量传感器 `state_class` 为 `total_increasing` | 同上所有能量实体 | §5.2.2 |
| ENT-17 | MUST | 能量传感器单位为 kWh | 同上所有能量实体单位正确 | §5.2.2 |
| ENT-18 | MUST | 能量实体可被添加到 Energy Dashboard | 在 HA Energy Dashboard 配置中可选择上述实体，且数据正确展示 | §6.2 |

### 4.4 Smart CT 传感器

| 编号 | 级别 | 验收项 | 预期结果 | 对应 PRD |
|------|------|--------|----------|----------|
| ENT-19 | MUST | 电网总功率传感器存在 | `grid_power` 实体存在，单位 W | §5.2.3 |
| ENT-20 | MUST | 各相功率传感器存在（按实际相数） | 单相时仅 A 相实体；三相时 A/B/C 相实体均存在 | §5.2.3 |
| ENT-21 | MUST | 各相电压传感器存在（按实际相数） | 电压实体存在，单位 V | §5.2.3 |
| ENT-22 | MUST | 各相电流传感器存在（按实际相数） | 电流实体存在，单位 A | §5.2.3 |
| ENT-23 | MUST | CT 能量统计传感器存在 | `grid_import_energy`、`grid_export_energy` 存在，适配 Energy Dashboard | §5.2.3 |
| ENT-24 | MUST | 单相 CT 不创建 B/C 相实体 | 单相 CT 配置下，仅 A 相相关实体存在 | §5.2.3 |

### 4.5 Smart Plug 传感器

| 编号 | 级别 | 验收项 | 预期结果 | 对应 PRD |
|------|------|--------|----------|----------|
| ENT-25 | MUST | 插座功率传感器存在 | `load_power` 实体存在，单位 W | §5.2.4 |
| ENT-26 | MUST | 插座能量统计传感器存在 | `load_energy` 实体存在，kWh，`total_increasing` | §5.2.4 |
| ENT-27 | MUST | 插座开关状态为只读 Binary Sensor | `switch_state` 为 Binary Sensor 类型，反映实际开/关状态 | §5.2.4 |
| ENT-28 | MUST | 多个 Plug 各自独立 | 每个 Plug 有独立的 Device 与 Entity，数据互不混淆 | §5.2.4 |

### 4.6 Device 信息

| 编号 | 级别 | 验收项 | 预期结果 | 对应 PRD |
|------|------|--------|----------|----------|
| ENT-29 | MUST | Device 名称含 SN 后 4 位 | 格式为 "Jackery DIY3 XXXX"、"Jackery Smart CT XXXX"、"Jackery Smart Plug XXXX" | §5.2.5 |
| ENT-30 | MUST | 制造商显示为 Jackery | Device 信息中 manufacturer = "Jackery" | §5.2.5 |
| ENT-31 | MUST | 子设备通过 `via_device` 关联到主机 | CT 和 Plug 的 Device 详情中显示所属主机 | §5.2.5 |

---

## 5. 只读安全约束

| 编号 | 级别 | 验收项 | 预期结果 | 对应 PRD |
|------|------|--------|----------|----------|
| SEC-01 | MUST | 无 Switch 实体 | 集成中不存在任何 `switch.*` 类型实体 | §3 C-4 |
| SEC-02 | MUST | 无 Number 实体 | 集成中不存在任何 `number.*` 类型实体 | §3 C-4 |
| SEC-03 | MUST | 无 Button 实体 | 集成中不存在任何 `button.*` 类型实体 | §3 C-4 |
| SEC-04 | MUST | 无 Select/Input 等可写实体 | 集成中不存在任何可触发设备端动作的实体 | §3 C-4 |
| SEC-05 | MUST | Smart Plug 开关状态不可操控 | `switch_state` 为 Binary Sensor，用户在 HA 界面中无法执行开/关操作 | §5.2.4 |
| SEC-06 | MUST | 集成不向设备发送任何控制指令 | 抓包验证：HA 通过 MQTT 仅发送数据请求（data_get），不发送任何控制类指令 | §3 C-4, C-5 |

---

## 6. 离线与异常处理

| 编号 | 级别 | 验收项 | 预期结果 | 对应 PRD |
|------|------|--------|----------|----------|
| ERR-01 | MUST | 设备断网后 60 秒内标记为 Unavailable | 断开 DIY3 主机网络，超过 60 秒未收到 MQTT 消息后，该设备及子设备全部实体变为 `Unavailable` | §7.2 |
| ERR-02 | MUST | 设备恢复后自动恢复 Available | 恢复网络连接后，收到设备 MQTT 消息时全部实体恢复为 `Available` | §7.2 |
| ERR-03 | MUST | 子设备离线时对应实体标记为 Unavailable | 拔掉某个 Smart Plug，该 Plug 的实体标记为 `Unavailable`，其他设备不受影响 | §7.2 |
| ERR-04 | MUST | 子设备重新上线后自动恢复 | 重新接入 Plug 后，对应实体恢复为 `Available` | §7.2 |
| ERR-05 | MUST | Token 失效时提示重新认证 | 模拟 Token 失效（设备拒绝鉴权），HA 集成页面显示 "Reauthentication Required" | §7.2 |
| ERR-06 | SHOULD | MQTT 消息格式异常时保持上次数据 | 模拟设备发送非法 JSON，传感器保持上次有效值，不显示错误值 | §7.2 |
| ERR-07 | MUST | 设备离线不影响 HA 运行 | DIY3 主机离线时，HA 系统整体无卡顿或报错 | §7.3 |

---

## 7. 数据刷新与性能

| 编号 | 级别 | 验收项 | 预期结果 | 对应 PRD |
|------|------|--------|----------|----------|
| PRF-01 | MUST | 数据请求间隔约 5 秒 | 观察传感器更新频率，相邻两次更新时间差约为 5 秒（±1 秒容差） | §7.1 |
| PRF-02 | MUST | MQTT 消息端到端延迟 < 500ms | 局域网环境下，通过日志或网络抓包验证从发送请求到收到响应的延迟 | §7.3 |
| PRF-03 | SHOULD | 单台设备 CPU 增量 < 1% | 添加一台设备前后对比 HA 主进程 CPU 占用 | §7.3 |
| PRF-04 | SHOULD | 10 台设备场景内存占用 < 50MB | 配置 10 台设备后检查集成内存使用 | §7.3 |
| PRF-05 | MUST | 60 秒无消息标记离线 | 模拟设备断网，验证超过 60 秒无 MQTT 消息后实体变为 Unavailable | §7.1 |

---

## 8. 云端共存

| 编号 | 级别 | 验收项 | 预期结果 | 对应 PRD |
|------|------|--------|----------|----------|
| CLD-01 | MUST | HA 集成运行时 APP 仍可正常查看设备 | HA 持续通过 MQTT 接收数据期间，Jackery APP 可正常显示设备数据 | §3 C-3 |
| CLD-02 | MUST | APP 操作不影响 HA 数据采集 | 通过 APP 执行操作（如调整 EMS 策略），HA 传感器数据不中断 | §3 C-3 |
| CLD-03 | MUST | 断开互联网后 HA 本地数据不中断 | 断开路由器外网，HA 与设备通过本地 MQTT Broker 的通信不受影响 | §1.3 |

---

## 9. UI/UX 展示

| 编号 | 级别 | 验收项 | 预期结果 | 对应 PRD |
|------|------|--------|----------|----------|
| UIX-01 | MUST | 设备页面结构正确 | 「设置 → 设备与服务 → Jackery」下显示设备列表，主机与子设备层级清晰 | §6.1 |
| UIX-02 | MUST | 设备详情显示型号与 SN | 点击设备可看到型号、制造商、SN 等信息 | §6.1 |
| UIX-03 | MUST | 实体列表完整 | 设备详情下展示该设备全部 Sensor 与 Binary Sensor 实体 | §6.1 |
| UIX-04 | MUST | Energy Dashboard 可配置 | 在 HA Energy Dashboard 配置页中可找到并选择对应的能量实体 | §6.2 |
| UIX-05 | MUST | Energy Dashboard 数据展示正确 | 配置后 Dashboard 正确显示太阳能、电池、电网的能量流数据 | §6.2 |

---

## 10. 兼容性

| 编号 | 级别 | 验收项 | 预期结果 | 对应 PRD |
|------|------|--------|----------|----------|
| CMP-01 | MUST | HA 2024.6.0 上可正常运行 | 在 HA 2024.6.0 版本上安装并完成全流程 | §7.4 |
| CMP-02 | SHOULD | HA 最新稳定版上可正常运行 | 在当前 HA 最新稳定版上安装并完成全流程 | §7.4 |
| CMP-03 | MUST | HACS ≥ 2.0 可安装 | 通过 HACS 2.0+ 正常安装集成 | §7.4 |
| CMP-04 | MUST | Jackery APP ≥ 2.10.18 可生成 Token | 使用满足版本要求的 APP 成功生成 Token 并完成配置 | §7.4 |

---

## 11. 授权流程端到端验证

| 编号 | 级别 | 验收项 | 预期结果 | 对应 PRD |
|------|------|--------|----------|----------|
| AUTH-01 | MUST | APP 中可开启本地访问开关 | 在 Jackery APP 设备设置中可找到并开启「本地访问 / HA 集成」开关 | §2.3 步骤 1–3 |
| AUTH-02 | MUST | APP 成功生成 Token 并可复制 | 开启开关后 APP 展示 Token 文本，支持一键复制 | §2.3 步骤 4–6 |
| AUTH-03 | MUST | APP 显示设备 SN 与 MQTT Broker 配置 | Token 页面同时显示设备 SN，且可配置 MQTT Broker 地址与端口 | §2.3 步骤 4, 7 |
| AUTH-04 | MUST | HA 中粘贴 Token 后验证成功 | 将 APP 中的 Token 粘贴到 HA Config Flow，验证通过并创建设备 | §2.3 步骤 8–12 |
| AUTH-05 | MUST | 端到端全流程 ≤ 5 分钟完成 | 从打开 APP 到 HA 中看到设备数据，整个过程不超过 5 分钟 | §1.3 |

---

## 12. 验收检查清单汇总

| 类别 | MUST 项 | SHOULD 项 | 合计 |
|------|---------|-----------|------|
| 安装与分发 | 3 | 1 | 4 |
| 配置流程 | 10 | 3 | 13 |
| 实体映射与数据 | 25 | 2 | 27 |
| 只读安全约束 | 6 | 0 | 6 |
| 离线与异常处理 | 5 | 1 | 6 |（ERR-07 已计入）
| 数据刷新与性能 | 3 | 2 | 5 |
| 云端共存 | 3 | 0 | 3 |
| UI/UX 展示 | 5 | 0 | 5 |
| 兼容性 | 3 | 1 | 4 |
| 授权流程 | 5 | 0 | 5 |
| **合计** | **68** | **10** | **78** |

---

## 附录：验收记录模板

| 编号 | 验收项 | 测试人 | 测试日期 | 结果 (Pass/Fail/N/A) | 备注 |
|------|--------|--------|----------|---------------------|------|
| INS-01 | HACS 安装 | | | | |
| INS-02 | 重启后集成可用 | | | | |
| ... | ... | | | | |

> 验收时请逐项填写上表，未通过项需附上问题描述与截图。

---

*文档结束*
