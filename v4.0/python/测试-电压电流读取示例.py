from pymodbus.client import ModbusTcpClient

# ===================== 配置项 =====================
# 通过直接访问 LOAR-EHT模块-B 模块，读取数据采集器modbus数据
MODULE_IP = "192.168.3.13"  # LOAR-EHT模块-B地址
MODULE_PORT = 502  # 模块转发端口
SLAVE_ID = 1  # 从站地址
START_ADDR = 0  # 起始地址 00 00
COUNT = 4  # 寄存器数量 00 02
# ==================================================

# 连接模块
client = ModbusTcpClient(MODULE_IP, port=MODULE_PORT)
client.connect()

try:
    # 读取保持寄存器（对应功能码03）
    response = client.read_holding_registers(
        address=START_ADDR, count=2, device_id=SLAVE_ID
    )
    val = client.convert_from_registers(response.registers, client.DATATYPE.UINT32)
    
    if not response.isError():
        print("读取成功！")
        print(f"寄存器数据: {response.registers}, 值: {val}")
    else:
        print(f"读取失败: {response}")

except Exception as e:
    print(f"异常: {e}")

finally:
    client.close()
