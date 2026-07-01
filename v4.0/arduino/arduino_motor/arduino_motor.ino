#define PWM_PIN 9
#define IN1_PIN 8
#define IN2_PIN 7

int curPwm = 255;
bool enableSerial = false;
String rxBuffer = "";  // 接收缓冲区

void setup() {
  Serial.begin(115200);
  
  pinMode(PWM_PIN, OUTPUT);
  pinMode(IN1_PIN, OUTPUT);
  pinMode(IN2_PIN, OUTPUT);
  
  digitalWrite(IN1_PIN, HIGH);
  digitalWrite(IN2_PIN, LOW);
  analogWrite(PWM_PIN, curPwm);

  // 延迟 2.5 秒再开启接收（避开ESP8266开机乱码）
  delay(2500);
  enableSerial = true;
  
  rxBuffer.reserve(32);
}

void loop() {
  // 永远保持 PWM 转速
  analogWrite(PWM_PIN, curPwm);

  if (!enableSerial) return;

  // ==============================================
  // 协议解析：只识别 #PWM=数值\n 格式
  // ==============================================
  while (Serial.available()) {
    char c = Serial.read();
    
    if (c == '#') {
      rxBuffer = "";  // 帧头，清空缓冲区
    }
    
    rxBuffer += c;
    
    if (c == '\n') {  // 帧尾，开始解析
      if (rxBuffer.startsWith("#PWM=")) {
        // 提取数值
        String numStr = rxBuffer.substring(5);
        int p = numStr.toInt();
        
        if (p >= 0 && p <= 255) {
          curPwm = p;
        }
      }
      rxBuffer = "";
    }
  }
}