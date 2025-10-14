import json
import time
import random
import paho.mqtt.client as mqtt

MQTT_BROKER = "192.168.0.101"
MQTT_PORT = 1883
MQTT_CLIENT_ID = "hem_simulator"

# 模式控制变量
# 0: 自发自用模式 (Self-consumption)
# 1: 电池优先模式 (Battery Priority)
current_mode = 0

# 模式名称映射
MODE_NAMES = {
    0: "自发自用模式",
    1: "电池优先模式"
}

client = mqtt.Client(client_id=MQTT_CLIENT_ID, callback_api_version=mqtt.CallbackAPIVersion.VERSION2)

# MQTT 连接回调
def on_connect(client, userdata, flags, rc, properties):
    print("Connected to MQTT broker with result code " + str(rc))
    publish_discovery_configs()
    # 订阅模式控制命令主题
    client.subscribe("homeassistant/select/mode_control/set")
    print("Subscribed to mode control command topic")

# MQTT 消息接收回调
def on_message(client, userdata, msg):
    global current_mode
    if msg.topic == "homeassistant/select/mode_control/set":
        try:
            payload = msg.payload.decode()
            # 支持数字或模式名称
            if payload.isdigit():
                new_mode = int(payload)
            elif payload == "自发自用模式":
                new_mode = 0
            elif payload == "电池优先模式":
                new_mode = 1
            else:
                print(f"Invalid mode payload: {payload}")
                return
            
            if new_mode in [0, 1]:
                current_mode = new_mode
                # 发布新的状态（使用模式名称）
                client.publish("homeassistant/select/mode_control/state", MODE_NAMES[current_mode])
                print(f"模式已切换到: {MODE_NAMES[current_mode]} ({current_mode})")
            else:
                print(f"Invalid mode value: {new_mode}")
        except ValueError:
            print(f"Invalid mode payload: {msg.payload.decode()}")

client.on_connect = on_connect
client.on_message = on_message


def publish_discovery_configs():
    """发布 Home Assistant MQTT Discovery 配置"""
    sensors = {
        "solar_power": {
            "name": "Solar Power",
            "unit": "W",
            "icon": "mdi:solar-power",
            "device_class": "power",
        },
        "home_power": {
            "name": "Home Power",
            "unit": "W",
            "icon": "mdi:home-lightning-bolt",
            "device_class": "power",
        },
        # 电网 - 分为购买和出售
        "grid_import": {
            "name": "Grid Import",
            "unit": "W",
            "icon": "mdi:transmission-tower-import",
            "device_class": "power",
        },
        "grid_export": {
            "name": "Grid Export",
            "unit": "W",
            "icon": "mdi:transmission-tower-export",
            "device_class": "power",
        },
        # 电池 - 分为充电和放电
        "battery_charge": {
            "name": "Battery Charge",
            "unit": "W",
            "icon": "mdi:battery-charging",
            "device_class": "power",
        },
        "battery_discharge": {
            "name": "Battery Discharge",
            "unit": "W",
            "icon": "mdi:battery-minus",
            "device_class": "power",
        },
        "battery_soc": {
            "name": "Battery State of Charge",
            "unit": "%",
            "icon": "mdi:battery-70",
            "device_class": "battery",
        },
    }

    for sensor_id, props in sensors.items():
        topic = f"homeassistant/sensor/{sensor_id}/config"
        payload = {
            "name": props["name"],
            "state_topic": f"homeassistant/sensor/{sensor_id}/state",
            "unit_of_measurement": props["unit"],
            "device_class": props["device_class"],
            "icon": props["icon"],
            "unique_id": sensor_id,
        }
        client.publish(topic, json.dumps(payload), retain=True)
        print(f"Published discovery config for {sensor_id}")
    
    # 发布模式控制的 discovery 配置
    mode_topic = "homeassistant/select/mode_control/config"
    mode_payload = {
        "name": "运行模式",
        "state_topic": "homeassistant/select/mode_control/state",
        "command_topic": "homeassistant/select/mode_control/set",
        "options": ["自发自用模式", "电池优先模式"],
        "icon": "mdi:cog-outline",
        "unique_id": "mode_control",
    }
    client.publish(mode_topic, json.dumps(mode_payload), retain=True)
    print("Published discovery config for mode_control")
    
    # 发布初始模式状态（使用模式名称）
    client.publish("homeassistant/select/mode_control/state", MODE_NAMES[current_mode])
    print(f"Published initial mode state: {MODE_NAMES[current_mode]} ({current_mode})")


def publish_sensor_data():
    """定期发布模拟功率数据"""
    battery_soc = random.uniform(20, 100)  # 初始电池电量
    
    while True:
        solar = random.uniform(200, 3000)       # 太阳能发电
        home = random.uniform(500, 3500)        # 家庭负载
        grid = home - solar                     # 电网供电（可能为负）
        battery = random.uniform(-1000, 1000)   # 电池充/放电
        
        # 将电网功率分离为购买（import）和出售（export）
        grid_import = max(0, grid)   # 从电网购买（正值）
        grid_export = max(0, -grid)  # 向电网出售（转为正值）
        
        # 将电池功率分离为充电和放电
        battery_charge = max(0, -battery)   # 充电（转为正值）
        battery_discharge = max(0, battery)  # 放电（正值）
        
        # 根据电池充放电模拟电量变化
        if battery < 0:  # 充电
            battery_soc = min(100, battery_soc + 0.5)
        elif battery > 0:  # 放电
            battery_soc = max(0, battery_soc - 0.3)

        data = {
            "solar_power": round(solar, 2),
            "home_power": round(home, 2),
            "grid_import": round(grid_import, 2),
            "grid_export": round(grid_export, 2),
            "battery_charge": round(battery_charge, 2),
            "battery_discharge": round(battery_discharge, 2),
            "battery_soc": round(battery_soc, 1),
        }

        for key, value in data.items():
            topic = f"homeassistant/sensor/{key}/state"
            client.publish(topic, value)
        
        # 发布当前模式状态
        client.publish("homeassistant/select/mode_control/state", MODE_NAMES[current_mode])
        
        print("Published:", data, f"| 运行模式: {MODE_NAMES[current_mode]}")

        time.sleep(5)


if __name__ == "__main__":
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()
    publish_sensor_data()
