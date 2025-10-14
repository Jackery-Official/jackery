# 数据传输格式说明

## 概述

Energy Monitor 系统使用 MQTT 协议进行数据传输，包含两个主要的通信方向：

1. **Home Assistant → 设备**: 发送数据获取请求
2. **设备 → Home Assistant**: 返回设备数据

## 数据流图

```
Home Assistant 集成
        │
        ▼
   /data/data-get (请求)
        │
        ▼
    设备端处理
        │
        ▼
   /device/data (响应)
        │
        ▼
   Home Assistant 集成
        │
        ▼
    更新传感器状态
```

## 数据格式

### 1. 数据获取请求

**主题**: `/data/data-get`  
**格式**: 纯文本  
**内容**: `get_data`  
**频率**: 每秒5次（每0.2秒一次）

```bash
主题: /data/data-get
内容: get_data
```

### 2. 设备数据响应

**主题**: `/device/data`  
**格式**: JSON  
**编码**: UTF-8

#### 完整数据格式

```json
{
  "solar_power": 1500.5,
  "home_power": 1200.0,
  "grid_import": 300.0,
  "grid_export": 0.0,
  "battery_charge": 200.0,
  "battery_discharge": 0.0,
  "battery_soc": 85.5
}
```

#### 字段说明

| 字段名 | 类型 | 单位 | 说明 |
|--------|------|------|------|
| `solar_power` | float | W | 太阳能发电功率 |
| `home_power` | float | W | 家庭用电功率 |
| `grid_import` | float | W | 从电网购买功率 |
| `grid_export` | float | W | 向电网出售功率 |
| `battery_charge` | float | W | 电池充电功率 |
| `battery_discharge` | float | W | 电池放电功率 |
| `battery_soc` | float | % | 电池电量百分比 |

## 使用示例

### Python 设备端示例

```python
import json
import paho.mqtt.client as mqtt

def on_message(client, userdata, msg):
    if msg.topic == "/data/data-get":
        # 收到数据请求，发送设备数据
        data = {
            "solar_power": 1500.5,
            "home_power": 1200.0,
            "grid_import": 300.0,
            "grid_export": 0.0,
            "battery_charge": 200.0,
            "battery_discharge": 0.0,
            "battery_soc": 85.5
        }
        
        # 发送到 /device/data 主题
        client.publish("/device/data", json.dumps(data))

# 设置 MQTT 客户端
client = mqtt.Client()
client.on_message = on_message
client.connect("192.168.0.101", 1883, 60)
client.subscribe("/data/data-get")
client.loop_forever()
```

### 测试命令

使用 mosquitto 客户端测试：

```bash
# 监听数据获取请求
mosquitto_sub -h 192.168.0.101 -t "/data/data-get"

# 监听设备数据
mosquitto_sub -h 192.168.0.101 -t "/device/data"

# 手动发送数据请求
mosquitto_pub -h 192.168.0.101 -t "/data/data-get" -m "get_data"

# 手动发送设备数据
mosquitto_pub -h 192.168.0.101 -t "/device/data" -m '{"solar_power": 1500.5, "home_power": 1200.0}'
```

## 注意事项

1. **JSON 格式**: 设备数据必须是有效的 JSON 格式
2. **数值类型**: 所有功率值应为数字类型（int 或 float）
3. **电量范围**: battery_soc 应在 0-100 之间
4. **功率单位**: 所有功率值单位为瓦特 (W)
5. **实时性**: 数据应尽可能实时更新
6. **错误处理**: 设备端应处理数据请求失败的情况

## 数据验证

Home Assistant 集成会验证接收到的数据：

- JSON 格式正确性
- 必需字段存在性
- 数值类型正确性
- 数值范围合理性

如果数据格式不正确，会在日志中记录警告信息。
