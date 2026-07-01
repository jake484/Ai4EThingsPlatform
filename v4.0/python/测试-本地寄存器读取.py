from pymodbus.client import ModbusTcpClient

# ===================== 配置区 =====================
# 本机 Modbus TCP 从站（diagslave）
HOST = "127.0.0.1"
PORT = 502
SLAVE_ID = 1  # 你启动 diagslave 时的 -a 1

# 测试用的寄存器地址
TEST_REG_ADDR = 0  # 保持寄存器起始地址
TEST_REG_COUNT = 10  # 一次读 5 个
# ====================================================


def modbus_test():
    print("=" * 60)
    print("  Modbus TCP 本机测试脚本（测试 diagslave）")
    print("=" * 60)

    # 1. 创建客户端
    client = ModbusTcpClient(HOST, port=PORT)
    print(f"🔌 正在连接 {HOST}:{PORT} ...")

    # 2. 连接
    connected = client.connect()
    if not connected:
        print("❌ 连接失败！请检查：")
        print("   1. diagslave 是否正在运行")
        print("   2. 端口是否 502")
        print("   3. 防火墙是否放行")
        return

    print("✅ 连接成功！")
    print(f"🎯 从站地址 Slave ID: {SLAVE_ID}")

    try:
        # --------------------------------------------------------------------
        # 第一步：读保持寄存器（Read Holding Registers）
        # --------------------------------------------------------------------
        print("\n" + "-" * 50)
        print(f"📖 读取 保持寄存器 地址={TEST_REG_ADDR}, 数量={TEST_REG_COUNT}")

        result = client.read_holding_registers(
            address=TEST_REG_ADDR, count=TEST_REG_COUNT, device_id=SLAVE_ID
        )

        if result.isError():
            print(f"❌ 读失败: {result}")
        else:
            print(f"✅ 读取成功: {result.registers}")

        res = client.convert_from_registers(result.registers
            [0:6], client.DATATYPE.FLOAT32, word_order="little"
        )

        print(res)

    except Exception as e:
        print(f"\n❌ 发生异常: {e}")

    finally:
        # 关闭连接
        client.close()
        print("\n" + "=" * 60)
        print("✅ 测试完成，连接已关闭")
        print("=" * 60)


if __name__ == "__main__":
    modbus_test()
