from pymodbus.client import ModbusTcpClient
import threading
import time

# 你的 diagslave 配置
HOST = "127.0.0.1"
PORT = 502
SLAVE_ID = 1

# 测试函数：每个线程独立连接、读取、关闭
def test_client(id):
    try:
        print(f"线程 {id} → 尝试连接...")

        # 创建客户端
        client = ModbusTcpClient(HOST, port=PORT)
        client.connect()

        # 读保持寄存器 0-1（电压）
        result = client.read_holding_registers(
            address=0,
            count=2,
            device_id=SLAVE_ID
        )

        if not result.isError():
            print(f"✅ 线程 {id} 读取成功: {result.registers}")
        else:
            print(f"❌ 线程 {id} 读取失败")

        client.close()

    except Exception as e:
        print(f"⚠️  线程 {id} 异常: {e}")

# ----------------------
# 同时启动 5 个客户端
# ----------------------
print("="*50)
print("开始并发测试 diagslave 多客户端连接")
print("="*50)

for i in range(5):
    t = threading.Thread(target=test_client, args=(i,))
    t.start()
    time.sleep(0.1)