# JackeryHome 故障排除指南

## MQTT 连接问题

### 问题：Host is unreachable 错误

如果您在 Home Assistant 日志中看到以下错误：

```
ERROR (MainThread) [homeassistant.components.mqtt.client] Error re-connecting to MQTT server due to exception: [Errno 113] Host is unreachable
WARNING (MainThread) [custom_components.jackery_home.sensor] MQTT not ready: Error talking
```

**原因：**
JackeryHome 集成依赖于 Home Assistant 的内置 MQTT 集成。该错误表明 Home Assistant 无法连接到配置的 MQTT broker。

**解决方案：**

#### 1. 确认已安装并配置 MQTT 集成

1. 进入 Home Assistant：**设置** → **设备与服务**
2. 检查是否已添加 **MQTT** 集成
3. 如果没有，点击 **添加集成**，搜索并添加 **MQTT**

#### 2. 配置正确的 MQTT Broker 地址

在 MQTT 集成配置中，确保：

- **Broker 地址**：填写您的 MQTT broker 的 IP 地址或主机名
  - 如果使用 Mosquitto Add-on：通常是 `localhost` 或 `core-mosquitto`
  - 如果使用独立 MQTT broker：填写其 IP 地址（例如 `192.168.1.100`）
- **端口**：默认为 `1883`（或 TLS 加密使用 `8883`）
- **用户名/密码**：如果 broker 需要认证，请填写

#### 3. 检查网络连接

确保 Home Assistant 可以访问 MQTT broker：

```bash
# 在 Home Assistant 容器/主机中测试连接
ping <mqtt_broker_ip>
telnet <mqtt_broker_ip> 1883
```

#### 4. 检查 MQTT Broker 是否运行

如果使用 Mosquitto Add-on：
1. 进入 **设置** → **加载项**
2. 找到 **Mosquitto broker**
3. 确认状态为 **已启动**
4. 查看日志确认没有错误

#### 5. 重新配置 JackeryHome 集成

在 MQTT 集成正确配置后：
1. 进入 **设置** → **设备与服务**
2. 找到 **JackeryHome** 集成
3. 如果仍有问题，尝试删除并重新添加该集成

### 问题：MQTT publish failed

如果看到 "MQTT publish failed" 错误，但 MQTT 集成已配置：

1. **重启 MQTT broker**
2. **重启 Home Assistant**
3. 检查 MQTT broker 日志中是否有连接错误
4. 确认 MQTT broker 没有达到连接限制

### 问题：数据未更新

如果传感器显示"不可用"或数据不更新：

1. **检查 MQTT 主题**：确认设备正在向正确的主题发布数据
   - LWT 主题：`v1/iot_gw/gw_lwt`
   - 数据主题：`v1/iot_gw/gw/data`
   
2. **使用 MQTT Explorer 监控**：
   - 安装 MQTT Explorer（桌面应用）
   - 连接到您的 broker
   - 订阅 `v1/iot_gw/#` 查看是否有数据

3. **检查设备序列号**：
   - 查看传感器的属性，确认 `device_sn` 是否正确
   - 确认设备已上线并发送了 LWT 消息

## 常见配置问题

### 使用 Mosquitto Add-on

推荐配置：
- **Broker**: `core-mosquitto` 或 `localhost`
- **Port**: `1883`

### 使用外部 MQTT Broker

1. 确保防火墙允许 1883 端口
2. 如果使用 Docker，确保网络配置正确
3. 考虑使用 TLS 加密连接（端口 8883）

## 调试步骤

### 启用详细日志

在 `configuration.yaml` 中添加：

```yaml
logger:
  default: info
  logs:
    custom_components.jackery_home: debug
    homeassistant.components.mqtt: debug
```

重启 Home Assistant 后，日志将显示更详细的 MQTT 交互信息。

### 手动测试 MQTT 连接

使用 `mosquitto_pub` 和 `mosquitto_sub` 工具测试：

```bash
# 订阅主题
mosquitto_sub -h <broker_ip> -t "v1/iot_gw/#" -v

# 发布测试消息
mosquitto_pub -h <broker_ip> -t "v1/iot_gw/test" -m "test message"
```

## 获取帮助

如果问题仍未解决，请在 GitHub 上提交 issue，并提供：

1. Home Assistant 版本
2. JackeryHome 集成版本
3. MQTT broker 类型和版本
4. 完整的错误日志（启用调试日志后）
5. MQTT 集成配置（隐藏敏感信息）

GitHub 仓库：https://github.com/your-repo/jackery_home

