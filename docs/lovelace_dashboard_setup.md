# Jackery Lovelace 可视化看板安装指南

本指南帮助你将 Jackery 设备从默认「实体网格」升级为分区化能源看板（能量流图 + 关键指标 + 控制区）。

## 1. 安装 HACS 前端卡片

在 Home Assistant 中：

1. 打开 **HACS** → **前端**
2. 搜索并安装：
   - **[Mushroom Cards](https://github.com/piitaya/lovelace-mushroom)** — 顶部芯片、实体卡片
   - **[Power Flow Card Plus](https://github.com/flixlix/power-flow-card-plus)** — 能量流向图
3. （可选）**mini-graph-card** — 历史迷你曲线；**card-mod** — 样式微调
4. 安装后 **清除浏览器缓存** 或重启 HA，确保卡片加载

> **子设备区说明**：看板底部「子设备与智能配件」使用 HA 原生 `entities` 卡片，**不需要**安装 `auto-entities`。若使用 `custom:auto-entities` 却未安装该 HACS 插件，会显示红色 **「配置错误」**。

## 2. 核对实体 ID

1. 进入 **开发者工具** → **状态**
2. 搜索 `jackery_` + 你的设备 SN（小写）
3. 对照 [entity_id_reference.md](entity_id_reference.md) 确认 ID
4. 若 SN 不是 `HS2C12600262HH4`，在配置文件中全局替换 `hs2c12600262hh4`

## 3. 创建仪表盘

1. **概览** → 右上角 ⋮ → **添加仪表盘**
2. 名称：`Jackery 能源`（可自定义）
3. 进入新仪表盘 → **编辑** → 右上角 ⋮ → **原始配置编辑器**
4. 粘贴 [lovelace_dashboard_jackery.yaml](lovelace_dashboard_jackery.yaml) 的全部内容
5. 保存并退出编辑模式

## 4. 仅使用能量流卡片

若只需能量流图，可单独添加一张卡片，配置见项目根目录 [energy_flow_card_config.yaml](../energy_flow_card_config.yaml)。使用前同样需将实体 ID 中的 SN 替换为实际值。

## 5. 多主机

每台 DIY3 主机有独立 SN 前缀。可：

- 为每台设备复制一份 section，并替换对应 entity_id；或
- 为每台主机创建独立仪表盘

## 6. 常见问题

| 现象 | 处理 |
|------|------|
| 卡片显示「Custom element doesn't exist」 | 确认 HACS 卡片已安装并刷新页面 |
| 实体显示 unavailable | 检查 MQTT 与 Jackery 集成连接 |
| 能量流图某路无数据 | 在开发者工具确认对应 sensor 有数值 |
| 控制按钮无效 | 核对 switch/select/number/button 的 entity_id 是否为 `main_*` 格式 |
| 子设备区显示「配置错误」 | 多为未安装 `auto-entities`；请使用最新版 `lovelace_dashboard_jackery.yaml`（已改为原生 entities） |
| 新增 CT/插座后看板无实体 | 在开发者工具复制新 entity_id，追加到看板「子设备」区的 `entities` 列表 |
