#!/usr/bin/env python3
"""
数据传输示例
演示如何使用修改后的 Energy Monitor 系统进行数据传输
"""

import json
import time
import random
import paho.mqtt.client as mqtt
battery_soc_point = "21548033"
    ## 能量累计
solar_energy_point = "16961537"
home_energy_point = "16936961"
grid_import_energy_point = "16959489"
grid_export_energy_point = "16960513"
battery_charge_energy_point = "16952321"
battery_discharge_energy_point = "16953345"
    ## 实时功率
solar_power_point = "1026001"
home_power_point = "21171201"
grid_import_power_point = "16930817"
grid_export_power_point = "16930817"
battery_charge_power_point = "16931841"
battery_discharge_power_point = "16931841"
class DataTransmissionExample:
    
    
    def __init__(self, broker="192.168.1.100", port=1883):
        self.broker = broker
        self.port = port
        self.client = None
        self.running = False
        self.device_status = "offline"
        self.device_sn = ""
        self.battery_soc = 0
        self.solar_energy = 0
        self.solar_energy = 0
        self.home_energy = 0
        self.grid_import_energy = 0
        self.grid_export_energy = 0
        self.battery_charge_energy = 0
        self.battery_discharge_energy = 0

        self.energy_data = {
            "solar_energy": 0,
            "home_energy": 0,
            "grid_import_energy": 0,
            "grid_export_energy": 0,
            "battery_charge_energy": 0,
            "battery_discharge_energy": 0,
        }

    ## 构造发送数据
    def construct_send_data(self):
        data = {
        "cmd": "data_get",
        "gw_sn": self.device_sn,
        "timestamp": str(int(time.time() * 1000)),
        ## 随机数是字符串
        "token": str(random.randint(1000, 9999)),
        "info": {
            "dev_list": [
                {
                    "dev_sn": "ems_" + self.device_sn,
                    "meter_list": [
                        battery_soc_point,
                        solar_energy_point,
                       home_energy_point,
                       grid_import_energy_point,
                       grid_export_energy_point,
                       battery_charge_energy_point,
                       battery_discharge_energy_point,
                       solar_power_point,
                       home_power_point,
                       grid_import_power_point,
                       grid_export_power_point,
                       battery_charge_power_point,
                       battery_discharge_power_point,
                    ]
                }
            ]
        }
        }
        return data
    ## 解析数据
    def parse_data(self, payload):
        # payload 已经是字典类型，不需要再次解析
        if isinstance(payload, str):
            data = json.loads(payload)
        else:
            data = payload
        info = data["info"]
        dev_list = info["dev_list"]
        for dev in dev_list:
            dev_sn = dev["dev_sn"]
            meter_list = dev["meter_list"]
            for meter in meter_list:
                meter_sn = meter[0]
                # 先转换为 float，然后判断是否可以转换为 int
                meter_value_float = float(meter[1])
                # 如果小数部分为 0，则转换为 int，否则保留 float
                meter_value = int(meter_value_float) if meter_value_float == int(meter_value_float) else meter_value_float
                print(f"📨 收到设备数据: {dev_sn} {meter_sn} {meter_value}")
                if meter_sn == battery_soc_point:
                    self.battery_soc = meter_value
                    print(f"📨 收到电池电量: {self.battery_soc}")
                if meter_sn == solar_energy_point:
                    self.solar_energy = meter_value
                    print(f"📨 收到太阳能能量: {self.solar_energy}")
                if meter_sn == home_energy_point:
                    self.home_energy = meter_value
                    print(f"📨 收到家庭能量: {self.home_energy}")
                if meter_sn == grid_import_energy_point:
                    self.grid_import_energy = meter_value
                    print(f"📨 收到电网购买能量: {self.grid_import_energy}")
                if meter_sn == grid_export_energy_point:
                    self.grid_export_energy = meter_value
                    print(f"📨 收到电网出售能量: {self.grid_export_energy}")
                if meter_sn == battery_charge_energy_point:
                    self.battery_charge_energy = meter_value
                    print(f"📨 收到电池充电能量: {self.battery_charge_energy}")
                if meter_sn == battery_discharge_energy_point:
                    self.battery_discharge_energy = meter_value
                    print(f"📨 收到电池放电能量: {self.battery_discharge_energy}")
                if meter_sn == solar_power_point:
                    self.solar_power = meter_value
                    print(f"📨 收到太阳能功率: {self.solar_power}")
                if meter_sn == home_power_point:
                    self.home_power = meter_value
                    print(f"📨 收到家庭功率: {self.home_power}")
                ## 电网功率 负值为购买，正值为出售
                if meter_sn == grid_import_power_point:
                    self.grid_import_power = meter_value
                    if meter_value < 0:
                        self.grid_import_power = -meter_value
                        print(f"📨 收到电网购买功率: {self.grid_import_power}")
                    else:
                        self.grid_export_power = meter_value
                        print(f"📨 收到电网出售功率: {self.grid_export_power}")
                ## 电池充放电功率 负值为充电，正值为放电
                if meter_sn == battery_charge_power_point:
                    self.battery_charge_power = meter_value
                    if meter_value < 0:
                        self.battery_charge_power = -meter_value
                        print(f"📨 收到电池充电功率: {self.battery_charge_power}")
                    else:
                        self.battery_discharge_power = meter_value
                        print(f"📨 收到电池放电功率: {self.battery_discharge_power}")
                
    def setup_mqtt(self):
        """设置 MQTT 客户端"""
        self.client = mqtt.Client(client_id="energy_device", callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
    def on_connect(self, client, userdata, flags, rc, properties):
        """MQTT 连接回调"""
        if rc == 0:
            print("✅ 连接到 MQTT 代理成功")
            # 订阅数据获取请求主题
            client.subscribe("v1/iot_gw/gw/data")
            client.subscribe("v1/iot_gw/gw_lwt")
            print("✅ 订阅 v1/iot_gw/gw_data 主题成功")
            print("✅ 订阅 v1/iot_gw/gw_lwt 主题成功")
        else:
            print(f"❌ 连接 MQTT 代理失败，错误码: {rc}")
    
    def on_message(self, client, userdata, msg):
        """MQTT 消息接收回调"""
        if msg.topic == "v1/iot_gw/gw/data":
            print(f"📨 收到数据请求: {msg.payload.decode()}")
            # 解析JSON
            data = json.loads(msg.payload)
            self.parse_data(data)
        if msg.topic == "v1/iot_gw/gw_lwt":
            print(f"📨 收到设备状态: {msg.payload.decode()}")
            # 解析JSON
            data = json.loads(msg.payload)
            self.device_sn = data["gw_sn"]
            info = data["info"]
            print(f"📨 收到设备状态: {self.device_sn} {info}")
            # 更新设备状态
            self.device_status = info
            print(f"📨 设备状态: {self.device_status}")
    
    
    def send_device_data(self):
        data = self.construct_send_data()
        
        # 转换为 JSON 格式
        json_data = json.dumps(data, ensure_ascii=False, indent=2)
        
        # 发布到 device/data 主题
        result = self.client.publish("v1/iot_gw/cloud/data", json_data)
        
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print("📤 发送设备数据:")
            print(f"   主题: v1/iot_gw/cloud/data")
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
            if self.device_sn != "":
                self.send_device_data()
            else:
                print("❌ 设备SN为空，无法发送数据")
                # return
            
            # 运行指定时间
            start_time = time.time()
            while self.running and (time.time() - start_time) < duration:
                time.sleep(1)
                
                # 每5秒发送一次数据（模拟设备主动发送）
                if int(time.time() - start_time) % 5 == 0:
                    print("📤 设备主动发送数据...")
                    if self.device_sn != "":
                        self.send_device_data()
                    else:
                        print("❌ 设备SN为空，无法发送数据")
                        # return
            
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
    print()
    
    # 创建示例实例
    example = DataTransmissionExample()
    example.setup_mqtt()
    
    # 启动模拟（运行60秒）
    example.start_simulation(duration=1000)

if __name__ == "__main__":
    main()
