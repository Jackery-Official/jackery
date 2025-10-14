#!/usr/bin/env python3
"""
数据传输示例
演示如何使用修改后的 Energy Monitor 系统进行数据传输
"""

import json
import time
import random
import paho.mqtt.client as mqtt

class DataTransmissionExample:
    """数据传输示例类"""
    
    def __init__(self, broker="192.168.0.101", port=1883):
        self.broker = broker
        self.port = port
        self.client = None
        self.running = False
        
    def setup_mqtt(self):
        """设置 MQTT 客户端"""
        self.client = mqtt.Client(client_id="energy_device_simulator", callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
    def on_connect(self, client, userdata, flags, rc, properties):
        """MQTT 连接回调"""
        if rc == 0:
            print("✅ 连接到 MQTT 代理成功")
            # 订阅数据获取请求主题
            client.subscribe("device/data-get")
            print("✅ 订阅 device/data-get 主题成功")
        else:
            print(f"❌ 连接 MQTT 代理失败，错误码: {rc}")
    
    def on_message(self, client, userdata, msg):
        """MQTT 消息接收回调"""
        if msg.topic == "device/data-get":
            print(f"📨 收到数据请求: {msg.payload.decode()}")
            # 模拟处理时间
            # time.sleep(0.1)
            # 发送模拟数据
            # self.send_device_data()
    
    def generate_sample_data(self):
        """生成模拟的设备数据"""
        # 模拟太阳能发电（白天较高，夜晚较低）
        hour = time.localtime().tm_hour
        if 6 <= hour <= 18:  # 白天
            solar_power = random.uniform(500, 3000)
        else:  # 夜晚
            solar_power = random.uniform(0, 100)
        
        # 模拟家庭用电
        home_power = random.uniform(800, 2500)
        
        # 计算电网功率（家庭用电 - 太阳能发电）
        grid_power = home_power - solar_power
        
        # 分离电网功率为购买和出售
        grid_import = max(0, grid_power)   # 从电网购买
        grid_export = max(0, -grid_power)  # 向电网出售
        
        # 模拟电池充放电
        battery_power = random.uniform(-800, 800)
        battery_charge = max(0, -battery_power)   # 充电
        battery_discharge = max(0, battery_power)  # 放电
        
        # 模拟电池电量（根据充放电状态变化）
        if not hasattr(self, 'battery_soc'):
            self.battery_soc = random.uniform(30, 90)
        
        # 根据充放电更新电量
        if battery_power > 0:  # 放电
            self.battery_soc = max(0, self.battery_soc - 0.5)
        elif battery_power < 0:  # 充电
            self.battery_soc = min(100, self.battery_soc + 0.3)
        
        return {
            "solar_power": round(solar_power, 2),
            "home_power": round(home_power, 2),
            "grid_import": round(grid_import, 2),
            "grid_export": round(grid_export, 2),
            "battery_charge": round(battery_charge, 2),
            "battery_discharge": round(battery_discharge, 2),
            "battery_soc": round(self.battery_soc, 1)
        }
    
    def send_device_data(self):
        """发送设备数据到 /device/data 主题"""
        data = self.generate_sample_data()
        
        # 转换为 JSON 格式
        json_data = json.dumps(data, ensure_ascii=False, indent=2)
        
        # 发布到 device/data 主题
        result = self.client.publish("device/data", json_data)
        
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print("📤 发送设备数据:")
            print(f"   主题: device/data")
            print(f"   数据: {json_data}")
            print()
        else:
            print(f"❌ 发送数据失败，错误码: {result.rc}")
    
    def start_simulation(self, duration=60):
        """启动数据模拟"""
        print("🚀 启动数据传输模拟")
        print(f"📡 MQTT 代理: {self.broker}:{self.port}")
        print(f"⏱️  运行时长: {duration} 秒")
        print("=" * 50)
        
        try:
            # 连接 MQTT 代理
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            self.running = True
            
            # 等待连接建立
            time.sleep(2)
            
            # 发送初始数据
            print("📤 发送初始数据...")
            self.send_device_data()
            
            # 运行指定时间
            start_time = time.time()
            while self.running and (time.time() - start_time) < duration:
                time.sleep(1)
                
                # 每5秒发送一次数据（模拟设备主动发送）
                if int(time.time() - start_time) % 5 == 0:
                    print("📤 设备主动发送数据...")
                    self.send_device_data()
            
        except KeyboardInterrupt:
            print("\n⏹️  用户中断模拟")
        except Exception as e:
            print(f"❌ 模拟出错: {e}")
        finally:
            self.stop_simulation()
    
    def stop_simulation(self):
        """停止模拟"""
        self.running = False
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
        print("✅ 模拟已停止")

def main():
    """主函数"""
    print("🏠 Energy Monitor 数据传输示例")
    print("=" * 50)
    print("这个示例演示了以下功能：")
    print("1. 监听 device/data-get 请求")
    print("2. 响应请求并发送设备数据到 device/data")
    print("3. 模拟真实的能源监控数据")
    print("4. 每秒5次的数据获取频率（由 Home Assistant 集成触发）")
    print()
    
    # 创建示例实例
    example = DataTransmissionExample()
    example.setup_mqtt()
    
    # 启动模拟（运行60秒）
    example.start_simulation(duration=1000)

if __name__ == "__main__":
    main()
