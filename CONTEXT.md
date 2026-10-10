# Domain Glossary

## Action Topic
系统向设备下发轮询/控制的 MQTT 主题：`{prefix}/device/{SN}/action`。出现流量只表示系统在发令，不表示设备已鉴权或已上报数据。

## Status Topic / Event Topic
设备向系统上报的 MQTT 主题：`{prefix}/device/{SN}/status` 与 `.../event`。主机电池与功率等监控字段只从此路上行；集成只订阅这两类主题。

## Token
设备本地控制身份识别码（静态字符串，由 App 下发到设备）。指令 envelope 中携带；与设备内部存储不一致时设备拒答。

## Token Rejection Silence
设备在 Token 不匹配时不返回任何 MQTT 消息的行为。因此无法从「单条失败回包」直接判定鉴权失败（除非偶发 `type=123` / `errorCode=401`）。

## Reauth Hint
集成在配置或 reload 后持续轮询，若长时间从未收到该主机任何 `status`/`event` 上行，则在 Home Assistant 集成页提示需要重新认证。这是「无上行响应」启发式，不是 Token 运行中过期或会话丢失。

## Battery SOC
主机电池电量监控量，对应上报字段 `batSoc`（及系统平均电量 `soc`）。仅在 Status/Event 上行载荷中出现；不会出现在 Action Topic 的轮询请求体里。
