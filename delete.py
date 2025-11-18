import json
import paho.mqtt.client as mqtt

MQTT_BROKER = "192.168.1.100"
MQTT_PORT = 1883
MQTT_USERNAME = ""
MQTT_PASSWORD = ""
MQTT_CLIENT_ID = "ha_delete_discovery"

SENSOR_IDS = [
    "solar_power",
    "home_power",
    "grid_import",
    "grid_export",
    "battery_charge",
    "battery_discharge",
    "battery_soc",
    "battery_power",
    "grid_power"
]

# ==== 修改后的回调 ====
def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        print("✅ 已连接到 MQTT Broker")
    else:
        print(f"❌ 连接失败，原因码: {reason_code}")

def on_publish(client, userdata, mid, reason_code, properties=None):
    print(f"🧹 已发送删除命令 (mid={mid})")

def delete_discovery_configs():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, MQTT_CLIENT_ID)
    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    client.on_connect = on_connect
    client.on_publish = on_publish

    print("🚀 正在连接 MQTT Broker ...")
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()

    for sensor_id in SENSOR_IDS:
        topic = f"homeassistant/sensor/{sensor_id}/config"
        client.publish(topic, None, retain=True)
        print(f"🗑️ 已发布空配置以删除实体：{sensor_id}")

    client.loop_stop()
    client.disconnect()
    print("✅ 所有 Discovery 配置已删除")

if __name__ == "__main__":
    delete_discovery_configs()
