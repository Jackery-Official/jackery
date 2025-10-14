#!/usr/bin/env python3
"""
测试 MQTT 数据发送脚本
用于测试 JackeryHome 集成是否能正确接收数据
"""
import json
import time
import paho.mqtt.client as mqtt
import random

# MQTT 配置
MQTT_BROKER = "192.168.0.101"  # 修改为你的 MQTT Broker 地址
MQTT_PORT = 1883
TOPIC_PREFIX = "homeassistant/sensor"

def on_connect(client, userdata, flags, rc):
    """连接回调"""
    if rc == 0:
        print("✅ 成功连接到 MQTT Broker")
    else:
        print(f"❌ 连接失败，错误代码: {rc}")

def on_publish(client, userdata, mid):
    """发布回调"""
    print(f"📤 消息已发布，ID: {mid}")

def main():
    """主函数"""
    print("🚀 启动 JackeryHome MQTT 测试脚本")
    print(f"📡 MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"📂 Topic Prefix: {TOPIC_PREFIX}")
    print("-" * 50)
    
    # 创建 MQTT 客户端
    client = mqtt.Client(client_id="jackery_home_test", callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_publish = on_publish
    
    try:
        # 连接到 MQTT Broker
        print("🔗 正在连接到 MQTT Broker...")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        
        # 等待连接
        time.sleep(2)
        
        # 模拟数据
        sensors = {
            "solar_power": {"min": 200, "max": 3000, "unit": "W"},
            "home_power": {"min": 500, "max": 3500, "unit": "W"},
            "grid_import": {"min": 0, "max": 2000, "unit": "W"},
            "grid_export": {"min": 0, "max": 1500, "unit": "W"},
            "battery_charge": {"min": 0, "max": 1000, "unit": "W"},
            "battery_discharge": {"min": 0, "max": 1000, "unit": "W"},
            "battery_soc": {"min": 20, "max": 100, "unit": "%"},
        }
        
        print("📊 开始发送测试数据...")
        print("按 Ctrl+C 停止")
        print("-" * 50)
        
        count = 0
        while True:
            count += 1
            print(f"\n🔄 第 {count} 轮数据发送:")
            
            for sensor_id, config in sensors.items():
                # 生成随机值
                value = random.randint(config["min"], config["max"])
                
                # 构建主题
                topic = f"{TOPIC_PREFIX}/{sensor_id}/state"
                
                # 发送数据
                result = client.publish(topic, str(value))
                
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    print(f"  ✅ {sensor_id}: {value} {config['unit']} -> {topic}")
                else:
                    print(f"  ❌ {sensor_id}: 发送失败")
            
            # 等待 5 秒
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  用户中断，正在停止...")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
    finally:
        # 清理资源
        client.loop_stop()
        client.disconnect()
        print("🔚 测试脚本已停止")

if __name__ == "__main__":
    main()
