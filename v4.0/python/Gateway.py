import threading
import time
import requests
import json
from pymodbus.client import ModbusTcpClient
from paho.mqtt import client as mqtt_client

# ===================== 配置 =====================
# 1. 真实硬件模块 (数据源 - Master 读取它)
SRC_MODBUS_HOST = "192.168.3.13"
SRC_MODBUS_PORT = 502

# 2. 本机 Modbus TCP Server (数据池 - Slave 写入它)
DST_MODBUS_HOST = "127.0.0.1"
DST_MODBUS_PORT = 502

# 1. 连接数据源 (192.168.3.13)
src_client = ModbusTcpClient(host=SRC_MODBUS_HOST, port=SRC_MODBUS_PORT)
src_client.connect()

# 2. 连接本地数据池 (127.0.0.1)
dst_client = ModbusTcpClient(host=DST_MODBUS_HOST, port=DST_MODBUS_PORT)
dst_client.connect()

SLAVE_ID = 1
ESP8266_IP = "192.168.3.15"  # 改成你的8266 IP

# ThingsBoard MQTT 配置
TB_HOST = "47.106.20.36"
TB_PORT = 1883
TB_TOKEN = "h153V5gddcVcXlxZJtQj"
TB_TOPIC_TELEMETRY = "v1/devices/me/telemetry"
TB_TOPIC_RPC_REQUEST = "v1/devices/me/rpc/request/+"
TB_TOPIC_RPC_RESPONSE = "v1/devices/me/rpc/response/"

# 寄存器映射 (在本地数据池 DST 中的地址)
REG_VOLTAGE = 0  # 电压 (Float, 2 regs)
REG_CURRENT = 2  # 电流 (Float, 2 regs)
REG_POWER = 4  # 功率 (Float, 2 regs)
REG_PWM = 6  # PWM 设定值 (Float, 2 regs)
REG_SWITCH_1 = 8  # 开关量 1 (Int, 1 reg, 0 or 1)
REG_SWITCH_2 = 9  # 开关量 2 (Int, 1 reg, 0 or 1)

# 全局变量
voltage = 0.0
current = 0.0
power = 0.0
pwm = 255  # 当前实际下发的 PWM 值
switch_1 = 0
switch_2 = 0


# ===================== Modbus 工具函数 =====================
def read_data_from_modbus(
    client: ModbusTcpClient,
    addr,
    word_order="little",
    datatype=ModbusTcpClient.DATATYPE.FLOAT32,
):
    """
    读取浮点数
    :param client: Modbus客户端
    :param addr: 寄存器地址
    :param word_order: 字序 "little" 或 "big"
    """
    try:
        result = client.read_holding_registers(
            address=addr, count=2, device_id=SLAVE_ID
        )
        if result.isError():
            return 0.0
        else:
            value = client.convert_from_registers(
                result.registers[0:2], datatype, word_order=word_order
            )
            return value
    except Exception as e:
        print(f"读浮点数异常: {e}")
        return 0.0


def write_float(client: ModbusTcpClient, addr, value, word_order="little"):
    """
    写入浮点数
    :param client: Modbus客户端
    :param addr: 寄存器地址
    :param value: 浮点数值
    :param word_order: 字序 "little" 或 "big"
    """
    try:
        regs = client.convert_to_registers(
            value, client.DATATYPE.FLOAT32, word_order=word_order
        )
        client.write_registers(address=addr, values=regs, device_id=SLAVE_ID)
    except Exception as e:
        print(f"写浮点数异常: {e}")


def read_int(client: ModbusTcpClient, addr):
    """读取单个寄存器作为整数"""
    try:
        result = client.read_holding_registers(
            address=addr, count=1, device_id=SLAVE_ID
        )
        if result.isError():
            return 0
        else:
            return result.registers[0]
    except Exception as e:
        print(f"读整数异常: {e}")
        return 0


def write_int(client: ModbusTcpClient, addr, value):
    """写入单个寄存器作为整数"""
    try:
        client.write_registers(address=addr, values=[int(value)], device_id=SLAVE_ID)
    except Exception as e:
        print(f"写整数异常: {e}")


# ===================== 线程 1：采集 + PWM控制 =====================
def thread_collect_and_control():
    global voltage, current, power, switch_1, switch_2, pwm, dst_client, src_client

    # 【初始化】确保本地 PWM 寄存器有默认值 255，避免首次读取为 0
    print("⚙️ 初始化本地 PWM 寄存器为 255...")
    write_float(dst_client, REG_PWM, 255.0)

    last_pwm_val = -1.0  # 记录上一次的 PWM 值，用于检测变化

    print("✅ 采集与控制合并线程启动")

    while True:
        try:
            # --- 部分 A: 数据采集与同步 (.13 -> 127.0.0.1) ---

            # 1. 从源读取模拟量
            v_raw = read_data_from_modbus(
                src_client, REG_VOLTAGE, "big", ModbusTcpClient.DATATYPE.INT32
            )
            c_raw = read_data_from_modbus(
                src_client, REG_CURRENT, "big", ModbusTcpClient.DATATYPE.INT32
            )

            # 单位转换
            voltage = v_raw / 1000.0
            current = c_raw / 10000.0
            power = voltage * current

            # 2. 从源读取开关量
            s1 = read_int(src_client, REG_SWITCH_1)
            s2 = read_int(src_client, REG_SWITCH_2)

            # 更新全局变量供 MQTT 使用
            switch_1 = s1
            switch_2 = s2

            # 3. 写入本地数据池 (遥测数据)
            write_float(dst_client, REG_VOLTAGE, voltage)
            write_float(dst_client, REG_CURRENT, current)
            write_float(dst_client, REG_POWER, power)
            write_int(dst_client, REG_SWITCH_1, s1)
            write_int(dst_client, REG_SWITCH_2, s2)

            # --- 部分 B: PWM 监控与下发 (127.0.0.1 -> ESP8266) ---

            # 1. 从本地数据池读取当前 PWM 设定值
            # 注意：这里读取的是可能被 RPC 线程修改过的值
            target_pwm_float = read_data_from_modbus(dst_client, REG_PWM)

            # 2. 限制范围并取整
            final_pwm = max(0, min(255, round(target_pwm_float, 0)))

            # 3. 检测数值是否发生变化
            if final_pwm != last_pwm_val:
                print(f"📢 检测到 PWM 变化: {last_pwm_val} -> {final_pwm}")

                # 4. 下发给 ESP8266
                try:
                    url = f"http://{ESP8266_IP}/pwm?value={int(final_pwm)}"
                    requests.get(url, timeout=5)
                    print(f"✅ ESP8266 下发成功: {int(final_pwm)}")

                    # 更新全局变量和最后一次记录的值
                    pwm = final_pwm
                    last_pwm_val = final_pwm

                except Exception as e:
                    print(f"❌ ESP8266 下发失败: {e}")
            else:
                # 值未变化，更新全局变量以保持最新状态
                pwm = final_pwm

        except Exception as e:
            print(f"❌ 合并线程执行错误: {e}")
            # 尝试重连
            try:
                src_client.close()
                dst_client.close()
                time.sleep(2)
                src_client.connect()
                dst_client.connect()
                # 重连后重新初始化 PWM 默认值以防万一
                write_float(dst_client, REG_PWM, 255.0)
                last_pwm_val = -1.0
            except Exception as reconnect_err:
                print(f"❌ 重连失败: {reconnect_err}")

        time.sleep(1)  # 统一轮询频率


# ===================== 线程2：统一 MQTT线程 (遥测 + RPC) =====================
def thread_mqtt_unified():
    # 需要访问全局变量进行遥测上报
    global voltage, current, power, pwm, switch_1, switch_2, dst_client

    def on_connect(c, u, f, rc, props=None):
        if rc == 0:
            print("✅ MQTT 统一连接成功")
            # 订阅 RPC 请求主题
            c.subscribe(TB_TOPIC_RPC_REQUEST)
        else:
            print(f"❌ MQTT 连接失败: {rc}")

    def on_message(c, u, msg):
        try:
            data = json.loads(msg.payload.decode())
            method = data.get("method")
            params = data.get("params")
            topic_parts = msg.topic.split("/")
            request_id = topic_parts[-1]

            if method == "setPWM":
                if isinstance(params, dict):
                    val = params.get("value", params.get("pwm", 0))
                else:
                    val = params

                val_int = max(0, min(255, int(float(val))))

                # 直接写入本地 Modbus 寄存器
                # 注意：这里写入后，合并线程会在下一个周期读取并下发
                write_float(dst_client, REG_PWM, float(val_int))
                print(f"📩 RPC 收到指令，已写入本地寄存器 PWM: {val_int}")

                response_payload = json.dumps({"result": "success", "pwm": val_int})
                response_topic = f"v1/devices/me/rpc/response/{request_id}"
                c.publish(response_topic, response_payload)

            else:
                print(f"⚠️ 未知的 RPC 方法: {method}")

        except Exception as e:
            print(f"❌ RPC 处理错误: {e}")

    # 初始化 MQTT 客户端
    client = mqtt_client.Client(
        mqtt_client.CallbackAPIVersion.VERSION2, client_id="tb_unified_client"
    )
    client.username_pw_set(TB_TOKEN)
    client.on_connect = on_connect
    client.on_message = on_message

    # 连接 MQTT
    client.connect(TB_HOST, TB_PORT, 60)

    # 启动网络循环后台线程，这样我们可以同时在主循环中发布消息
    client.loop_start()

    print("✅ 统一 MQTT 线程启动 (遥测+RPC)")

    try:
        while True:
            # 构建遥测数据
            payload = {
                "voltage": round(voltage, 2),
                "current": round(current, 2),
                "power": round(power, 2),
                "pwm": pwm,
                "switch_1": bool(switch_1),
                "switch_2": bool(switch_2),
                "running": True,
            }
            # 发布遥测数据
            client.publish(TB_TOPIC_TELEMETRY, json.dumps(payload))

            # 等待下一次上报
            time.sleep(2)
    except Exception as e:
        print(f"❌ MQTT 统一线程异常: {e}")
    finally:
        client.loop_stop()
        client.disconnect()
        dst_client.close()


# ===================== 启动 =====================
if __name__ == "__main__":
    print("🚀 智能网关启动 (优化版: 2线程)")
    print(f"📡 数据源: {SRC_MODBUS_HOST}:{SRC_MODBUS_PORT}")
    print(f"💾 数据池: {DST_MODBUS_HOST}:{DST_MODBUS_PORT}")
    print(f"💡 执行器: {ESP8266_IP}")

    # 启动合并后的采集与控制线程
    t1 = threading.Thread(target=thread_collect_and_control, daemon=True)

    # 启动 MQTT 线程
    t2 = threading.Thread(target=thread_mqtt_unified, daemon=True)

    t1.start()
    t2.start()

    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        print("🛑 程序退出")
