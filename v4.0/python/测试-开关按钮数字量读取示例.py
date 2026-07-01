# 安装依赖：pip install pymodbus
from pymodbus.client import ModbusTcpClient

# ===================== 模块参数=====================
MODULE_IP = "192.168.3.13"  # 模块默认IP
MODULE_PORT = 502           # MODBUS TCP 端口
SLAVE_ID = 2                # 模块默认站号
# =====================================================================

# 连接模块
client = ModbusTcpClient(MODULE_IP, port=MODULE_PORT)
client.connect()

try:
    # 读取数字量输入 DI1~DI2（功能码 0x02，起始地址0，长度2）
    result = client.read_discrete_inputs(address=0, count=2, device_id=SLAVE_ID)

    if not result.isError():
        di1 = result.bits[0]  # DI1 状态  
        di2 = result.bits[1]  # DI2 状态

        print("===== 数字量输入状态 =====")
        print(f"DI1（通道1）：{'导通' if di1 else '断开'}")
        print(f"DI2（通道2）：{'导通' if di2 else '断开'}")
    else:
        print("读取失败：", result)

except Exception as e:
    print("异常：", e)

finally:
    client.close()