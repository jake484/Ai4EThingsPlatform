import json
import time
import threading
from pymodbus.client import ModbusTcpClient, ModbusSerialClient
import paho.mqtt.client as mqtt
from struct import unpack, pack
from pymodbus.exceptions import ModbusException

# -------------------------- 配置参数 --------------------------
# Modbus TCP 设备配置
MODBUS_TCP_IP = "192.168.3.13"  # Modbus TCP设备IP
MODBUS_TCP_PORT = 502  # Modbus TCP设备端口

# Modbus RTU 设备配置
MODBUS_RTU_PORT = '/dev/ttyUSB0'      # Windows为串口设备名 例如COM3，Linux为设备路径
MODBUS_RTU_BAUDRATE = 9600    # 波特率
MODBUS_RTU_PARITY = 'N'       # 校验位
MODBUS_RTU_STOPBITS = 1       # 停止位
MODBUS_RTU_BYTESIZE = 8       # 数据位
MODBUS_RTU_TIMEOUT = 1        # 超时时间
MODBUS_RTU_SLAVE_ID = 2       # 从站ID

# MQTT 服务器配置
MQTT_BROKER_IP = "192.168.3.14" # 182.92.0.11
MQTT_BROKER_PORT = 1883
MQTT_TOPIC_STATUS = "ai4energy/tcpData"  # TCP数据上传话题
MQTT_TOPIC_RTU_STATUS = "ai4energy/rtuData"  # RTU数据上传话题

# 采集间隔（秒）
COLLECT_INTERVAL = 3


# -------------------------- Modbus TCP 操作函数 --------------------------
def modbus_tcp_read_float_data():
    """读取从地址7到39的浮点数数据 (TCP)"""
    try:
        # 连接 Modbus TCP 设备
        client = ModbusTcpClient(MODBUS_TCP_IP, port=MODBUS_TCP_PORT)
        client.connect()

        # 读取从地址7到39的保持寄存器（共33个寄存器，每两个寄存器组成一个浮点数）
        start_address = 1   # 直接从地址7开始
        count = 62          # 31个寄存器
        response = client.read_holding_registers(
            address=start_address, count=count, device_id=1
        )
        
        data = {}
        if not response.isError():
            registers = response.registers
            
            # 将寄存器对转换为浮点数
            for i in range(0, len(registers), 2):
                if i + 1 < len(registers):  # 确保有配对的寄存器
                    addr = start_address + (i // 2)  # 计算实际地址（7, 8, 9, ...）
                    # 将两个16位寄存器合并成32位浮点数
                    float_val = unpack('!f', bytes.fromhex(f"{registers[i]:04x}{registers[i+1]:04x}"))[0]
                    data[addr] = round(float_val, 2)  # 保留两位小数
        
        # 关闭连接
        client.close()
        
        return data

    except Exception as e:
        print(f"Modbus TCP 读取失败：{e}")
        return {}  # 返回空字典


# -------------------------- Modbus RTU 操作函数 --------------------------
def modbus_rtu_read_float_data():
    """读取从地址22到86的浮点数数据 (RTU) - 对应VD44到VD180"""
    try:
        # 创建 Modbus RTU 客户端
        client = ModbusSerialClient(
            port=MODBUS_RTU_PORT,
            baudrate=MODBUS_RTU_BAUDRATE,
            parity=MODBUS_RTU_PARITY,
            stopbits=MODBUS_RTU_STOPBITS,
            bytesize=MODBUS_RTU_BYTESIZE,
            timeout=MODBUS_RTU_TIMEOUT
        )
        
        if not client.connect():
            print("Modbus RTU 串口连接失败！检查串口号/接线/PLC是否RUN")
            return {}

        # 计算需要读取的寄存器数量：从地址22到56，总共34个地址，每个浮点数占2个寄存器
        start_offset = 22
        end_offset = 56
        total_addresses = end_offset - start_offset + 1  # 65个地址
        total_reg = total_addresses * 2  # 每个浮点数占2个寄存器

        response = client.read_holding_registers(
            address=start_offset,
            count=total_reg,
            device_id=MODBUS_RTU_SLAVE_ID
        )

        data = {}
        # 检查Modbus响应异常
        if isinstance(response, ModbusException):
            print(f"Modbus RTU 通信错误：{response}")
            client.close()
            return {}
        if response.isError():
            print(f"Modbus RTU 读取失败（起始偏移{start_offset}），错误码：{response}")
            client.close()
            return {}

        regs = response.registers
        # 每2个寄存器解析1个浮点数
        for i in range(0, total_reg, 2):
            if i + 1 < len(regs):
                current_addr = start_offset + (i // 2)  # 当前地址
                # 核心解析：西门子字节序（高字在前）+ IEEE754单精度浮点数
                int32 = (regs[i] << 16) | regs[i+1]  # 拼接32位整数
                real_value = unpack('!f', pack('!I', int32))[0]  # 解包浮点
                data[current_addr-start_offset+1] = round(real_value, 2)  # 保留两位小数
                # print(f"RTU读取：偏移{current_addr} → 浮点值：{real_value:.4f}")

        client.close()
        return data

    except Exception as e:
        print(f"Modbus RTU 读取异常：{str(e)}")
        return {}
    finally:
        try:
            client.close()
        except:
            pass


# -------------------------- MQTT 操作函数 --------------------------
def on_mqtt_connect(client, userdata, flags, reason_code, properties=None):
    """MQTT 连接成功回调"""
    if reason_code == 0:
        print("MQTT 连接成功")
    else:
        print(f"MQTT 连接失败，错误码：{reason_code}")


def mqtt_client_init():
    """初始化 MQTT 客户端"""
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_mqtt_connect

    # 连接 MQTT 服务器
    try:
        client.connect(MQTT_BROKER_IP, MQTT_BROKER_PORT, 60)
        return client
    except Exception as e:
        print(f"MQTT 客户端初始化失败：{e}")
        return None


# -------------------------- 网关主逻辑 --------------------------
def collect_and_upload_tcp_status(mqtt_client):
    """循环采集 Modbus TCP 浮点数数据并上传到 MQTT"""
    while True:
        try:
            # 读取 Modbus TCP 浮点数数据
            float_data = modbus_tcp_read_float_data()
            
            if float_data:  # 如果有数据才上传
                # 转换为 JSON 字符串
                payload = json.dumps(float_data, ensure_ascii=False)
                # 发布到 MQTT
                mqtt_client.publish(MQTT_TOPIC_STATUS, payload, qos=1)
                print(f"上传 TCP 浮点数数据到 MQTT：{payload}")
            else:
                print("未获取到有效的 TCP 浮点数数据")
                
        except Exception as e:
            print(f"采集并上传 TCP 浮点数数据失败：{e}")

        # 等待采集间隔
        time.sleep(COLLECT_INTERVAL)


def collect_and_upload_rtu_status(mqtt_client):
    """循环采集 Modbus RTU 浮点数数据并上传到 MQTT"""
    while True:
        try:
            # 读取 Modbus RTU 浮点数数据
            float_data = modbus_rtu_read_float_data()
            
            if float_data:  # 如果有数据才上传
                # 转换为 JSON 字符串
                payload = json.dumps(float_data, ensure_ascii=False)
                # 发布到 MQTT
                mqtt_client.publish(MQTT_TOPIC_RTU_STATUS, payload, qos=1)
                print(f"上传 RTU 浮点数数据到 MQTT：{payload}")
            else:
                print("未获取到有效的 RTU 浮点数数据")
                
        except Exception as e:
            print(f"采集并上传 RTU 浮点数数据失败：{e}")

        # 等待采集间隔
        time.sleep(COLLECT_INTERVAL)


if __name__ == "__main__":
    # 初始化 MQTT 客户端，失败时重试
    mqtt_client = None
    while not mqtt_client:
        mqtt_client = mqtt_client_init()
        if not mqtt_client:
            print(f"MQTT 客户端初始化失败，30秒后重试...")
            time.sleep(30)
    
    # 启动 MQTT 网络循环（后台线程）
    mqtt_client.loop_start()

    # 启动 TCP 数据采集上传线程
    tcp_collect_thread = threading.Thread(
        target=collect_and_upload_tcp_status, args=(mqtt_client,)
    )
    tcp_collect_thread.daemon = True
    tcp_collect_thread.start()

    # 启动 RTU 数据采集上传线程
    rtu_collect_thread = threading.Thread(
        target=collect_and_upload_rtu_status, args=(mqtt_client,)
    )
    rtu_collect_thread.daemon = True
    rtu_collect_thread.start()

    # 主线程保持运行
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("网关服务停止")
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
    # 初始化 MQTT 客户端
    mqtt_client = mqtt_client_init()
    if not mqtt_client:
        exit(1)

    # 启动 MQTT 网络循环（后台线程）
    mqtt_client.loop_start()

    # 启动 TCP 数据采集上传线程
    tcp_collect_thread = threading.Thread(
        target=collect_and_upload_tcp_status, args=(mqtt_client,)
    )
    tcp_collect_thread.daemon = True
    tcp_collect_thread.start()

    # 启动 RTU 数据采集上传线程
    rtu_collect_thread = threading.Thread(
        target=collect_and_upload_rtu_status, args=(mqtt_client,)
    )
    rtu_collect_thread.daemon = True
    rtu_collect_thread.start()

    # 主线程保持运行
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("网关服务停止")
        mqtt_client.loop_stop()
        mqtt_client.disconnect()