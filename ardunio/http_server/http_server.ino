#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <DHT.h>
#define DHTPIN 5
#define DHTTYPE DHT11
DHT dht(DHTPIN, DHTTYPE);
#include <Arduino.h>
#include <U8g2lib.h>
#ifdef U8X8_HAVE_HW_SPI
#include <SPI.h>
#endif
#ifdef U8X8_HAVE_HW_I2C
#include <Wire.h>
#endif
U8G2_SSD1306_128X64_NONAME_F_SW_I2C u8g2(U8G2_R0, 14, 2, U8X8_PIN_NONE);

// 状态定义
#define STATE_INIT 0
#define STATE_WIFI_CONNECTING 1
#define STATE_SERVER_STARTING 2
#define STATE_WORKING 3
#define STATE_WIFI_ERROR 5

// 参数定义
const char* ssid = "Ai4E-EG8200";  // WiFi 名称
const char* password = "ai4energy";      // WiFi 密码
// 添加设备开关状态变量
bool deviceOn = true;
// Web服务器实例 (默认端口80)
ESP8266WebServer server(80);

// 状态参数
int workstate = STATE_INIT;

// 最近一次传感器读数
float lastTemperature = 0.0;
float lastHumidity = 0.0;
unsigned long lastSensorRead = 0;

// 初始化函数
void setup() {
  // 打开串行通信
  u8g2.begin();
  dht.begin();
  Serial.begin(115200);
  
  // 设置路由处理函数
  server.on("/", HTTP_GET, handleRoot);
  server.on("/data", HTTP_GET, handleData);
  server.on("/temperature", HTTP_GET, handleTemperature);
  server.on("/humidity", HTTP_GET, handleHumidity);
  server.on("/device", HTTP_POST, handleDeviceControl);  // 添加这一行
  server.on("/deviceOn", HTTP_GET, handleDeviceStatus);
  server.onNotFound(handleNotFound);
}
void loop() {
  int ret = 0;

  serial_data_handle();  // 处理串行数据
  showLED();  // 显示 LED 屏内容

  switch (workstate) {
    case STATE_INIT:
      if ((ssid == "") || (password == "")) {
        // WiFi 参数错误
        break;
      }
      workstate = STATE_WIFI_CONNECTING;
      break;
      
    case STATE_WIFI_CONNECTING:
      ret = wifi_connect();
      if (ret == 0) {
        // WiFi 连接成功
        workstate = STATE_SERVER_STARTING;
      } else {
        // WiFi 连接失败
        workstate = STATE_WIFI_ERROR;
      }
      break;
      
    case STATE_SERVER_STARTING:
      server.begin();
      Serial.println("HTTP server started");
      Serial.print("IP address: ");
      Serial.println(WiFi.localIP());
      workstate = STATE_WORKING;
      break;
      
    case STATE_WORKING:
      // 检查WiFi连接状态
      if (WiFi.status() != WL_CONNECTED) {
        workstate = STATE_WIFI_ERROR;
      } else {
        // 处理HTTP请求
        server.handleClient();
        
        // 每2秒更新一次传感器数据
        if (millis() - lastSensorRead > 2000) {
          updateSensorData();
          lastSensorRead = millis();
        }
      }
      break;
      
    case STATE_WIFI_ERROR:
      // WiFi 断开，重新初始化
      workstate = STATE_INIT;
      break;
      
    default:
      workstate = STATE_INIT;
      break;
  }
  
  delay(100); // 短暂延迟以保持系统响应
}

// 连接 WiFi 的函数
int wifi_connect(void) {
  int retry_times = 0;

  WiFi.begin(ssid, password);

  Serial.print("Connecting");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    retry_times++;
    if (retry_times >= 10) {
      Serial.print("Wifi Connect timeout");
      Serial.println();
      return -1;
    }
  }
  Serial.println();

  Serial.print("Connected, IP address: ");
  Serial.println(WiFi.localIP());

  return 0;
}

// 更新传感器数据
void updateSensorData() {
  float temperature = dht.readTemperature();
  float humidity = dht.readHumidity();

  if (!isnan(temperature) && !isnan(humidity)) {
    lastTemperature = temperature;
    lastHumidity = humidity;
    Serial.printf("Updated sensor data: Temperature=%.1f°C, Humidity=%.1f%%, DeviceOn=%d \n", 
                  lastTemperature, lastHumidity, deviceOn);
  } else {
    Serial.println("Failed to read from DHT sensor!");
  }
}

// 处理根路径请求
void handleRoot() {
  String html = "<!DOCTYPE html><html>";
  html += "<head><meta charset='utf-8'><title>ESP8266 Sensor Server</title></head>";
  html += "<body>";
  html += "<h1>ESP8266 温湿度传感器数据</h1>";
  html += "<p>温度: " + String(lastTemperature, 1) + " °C</p>";
  html += "<p>湿度: " + String(lastHumidity, 1) + " %</p>";
  html += "<p><a href='/data'>JSON数据</a> | <a href='/temperature'>仅温度</a> | <a href='/humidity'>仅湿度</a></p>";
  html += "</body></html>";
  
  server.send(200, "text/html", html);
}

// 处理 /data 路径请求，返回JSON格式数据
void handleData() {
  String json = "{";
  json += "\"temperature\":" + String(lastTemperature, 1) + ",";
  json += "\"humidity\":" + String(lastHumidity, 1) + ",";
  json += "\"deviceOn\":" + String(deviceOn ? "true" : "false");
  json += "}";
  
  server.send(200, "application/json", json);
}

// 处理 /temperature 路径请求，仅返回温度数据
void handleTemperature() {
  server.send(200, "text/plain", String(lastTemperature, 1));
}

// 处理 /humidity 路径请求，仅返回湿度数据
void handleHumidity() {
  server.send(200, "text/plain", String(lastHumidity, 1));
}

// 处理 /deviceOn 路径请求，返回设备开关状态
void handleDeviceStatus() {
  server.send(200, "text/plain", deviceOn ? "true" : "false");
}

// 处理未找到的路径
void handleNotFound() {
  String message = "File Not Found\n\n";
  message += "URI: ";
  message += server.uri();
  message += "\nMethod: ";
  message += (server.method() == HTTP_GET) ? "GET" : "POST";
  message += "\nArguments: ";
  message += server.args();
  message += "\n";
  
  for (uint8_t i = 0; i < server.args(); i++) {
    message += " " + server.argName(i) + ": " + server.arg(i) + "\n";
  }
  
  server.send(404, "text/plain", message);
}

// 处理串行数据的函数
void serial_data_handle() {
  // TODO: 读取串行数据并进行配置
  // Serial read
}

// 显示 LED 屏内容的函数
void showLED() {
  u8g2.clearBuffer();                     
  u8g2.setFont(u8g2_font_ncenB08_tr);     
  
  // 第一行：WiFi连接状态 (增加行间距)
  if (WiFi.status() == WL_CONNECTED) {
    u8g2.drawStr(0, 12, "WiFi: Connected");
  } else {
    u8g2.drawStr(0, 12, "WiFi: Offline");
  }
  
  // 第二行：完整IP地址 (增加行间距)
  if (WiFi.status() == WL_CONNECTED) {
    String ipStr = "Local IP:" + WiFi.localIP().toString();
    u8g2.drawStr(0, 26, ipStr.c_str());
  } else {
    u8g2.drawStr(0, 26, "Local IP: No IP");
  }
  
  // 第三行：温湿度数据 (增加行间距)
  u8g2.drawStr(0, 40, "T:");
  u8g2.setCursor(15, 40);
  u8g2.print(lastTemperature, 1);
  u8g2.setCursor(40, 40);
  u8g2.print("C H:");
  u8g2.setCursor(65, 40);
  u8g2.print(lastHumidity, 1);
  u8g2.print("%");
  
  // 第四行：设备开关状态 (增加行间距)
  u8g2.drawStr(0, 54, "Device:");
  if (deviceOn) {
    u8g2.drawStr(45, 54, "ON");
  } else {
    u8g2.drawStr(45, 54, "OFF");
  }
  
  u8g2.sendBuffer();
}// 处理设备开关的POST请求
void handleDeviceControl() {
  if (server.hasArg("plain")) {
    String body = server.arg("plain");
    
    if (body == "on") {
      deviceOn = true;
      server.send(200, "text/plain", "Device turned ON");
    } else if (body == "off") {
      deviceOn = false;
      server.send(200, "text/plain", "Device turned OFF");
    } else {
      server.send(400, "text/plain", "Invalid command. Use 'on' or 'off'");
    }
  } else {
    server.send(400, "text/plain", "Missing command in request body");
  }
}