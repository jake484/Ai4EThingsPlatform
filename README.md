# Ai4EThingsPlatform

## 整体介绍

### 物联网架构

![图 3](assets/figs/README-20-30-07.png)  

其中：

1. **工控机（主机）：** 采用`Docker`部署`ThingBoard`物联网平台，实现完善的设备管理功能，能够对连接到平台的各类物联网设备进行注册、认证、状态监控以及参数配置等操作；具备通过丰富的图表、图形等形式，将设备采集到的数据直观呈现。
2. **Liunx开发板（显示设备）：** 选用正点原子STM32MP157开发板搭配电容屏，安装Debian桌面系统，通过浏览器访问物联网平台。
3.	**工业路由器：** 作为交换机，连通各设备。
4.	**工业网关：** 有图形化编程功能，支持可视化拖拽式逻辑配置，支持 Modbus、MQTT、HTTP、TCP、UDP 等多种工业常见通信协议，可与各类工业设备、传感器、服务器等进行对接。
5.	**终端设备：** 采用`ESP8266`作为核心模块，搭载显示屏与温湿度传感器，通过相应的接口协议与网关进行通信。

### 运行效果

终端设备采集传感器数据，通过工业网关上传至工控机的物联网平台，再由物联网平台将数据发送至工控机进行处理和存储，显示设备访问工控机服务，展示设备数据，并实现对终端设备控制。

## 工控机（主机）

### 登录密码
root：Ot@13579

### 查看公网IP

1. IPv4: curl icanhazip.com
2. IPv6: curl 6.ipw.cn

### 启动 browservice 
sudo ./browservice.AppImage --vice-opt-http-listen-addr=0.0.0.0:80 --start-page=http://localhost:8080 --vice-opt-navigation-forwarding=yes --show-control-bar=yes --chromium-args=--no-sandbox

### 防火墙开启命令
sudo firewall-cmd --list-ports
sudo firewall-cmd --zone=public --add-port=8080/tcp --permanent
sudo firewall-cmd --reload

### 查看开机自启动的browservice状态
systemctl status browservice.service

## 蒲公英密码

Ai4EBox-2.4G

上网方式：动态IP

SN 526153936967

密码：ai4energy

## Liunx开发板（显示设备）

## 工业路由器

## 工业网关

## 终端设备