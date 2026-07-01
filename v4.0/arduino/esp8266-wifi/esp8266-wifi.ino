#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>

// WiFi配置
const char* ssid     = "jake484";
const char* password = "yjy522432938";

// ==================== 静态IP（无DNS版）====================
IPAddress localIP(192, 168, 3, 15);     // 你自己固定的IP
IPAddress gateway(192, 168, 3, 1);      // 路由器网关
IPAddress subnet(255, 255, 255, 0);     // 子网掩码
// =======================================================

ESP8266WebServer server(80);
#define LED_PIN 2

// 协议发送：#PWM=xxx\n
void handlePWM()
{
  if (!server.hasArg("value"))
  {
    server.send(400, "text/plain", "Err: No Value");
    return;
  }

  int pwmVal = server.arg("value").toInt();
  pwmVal = constrain(pwmVal, 0, 255);

  // 标准协议下发，防乱码
  Serial.print("#PWM=");
  Serial.println(pwmVal);

  server.send(200, "text/plain", "OK:" + String(pwmVal));
}

void setup()
{
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH);

  // ✅ 没有 DNS，照样正常连接！
  WiFi.config(localIP, gateway, subnet);

  Serial.begin(115200);

  // 连接WiFi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED)
  {
    digitalWrite(LED_PIN, !digitalRead(LED_PIN));
    delay(200);
  }

  digitalWrite(LED_PIN, LOW);

  server.on("/pwm", handlePWM);
  server.begin();
}

void loop()
{
  server.handleClient();

  // WiFi正常 1秒闪烁一次
  static unsigned long lastTime = 0;
  static bool ledFlag = false;
  if (millis() - lastTime >= 1000)
  {
    lastTime = millis();
    ledFlag = !ledFlag;
    digitalWrite(LED_PIN, ledFlag);
  }
}