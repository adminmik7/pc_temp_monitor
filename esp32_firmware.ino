#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// LCD1602 (16 символов, 2 строки) - адрес обычно 0x27 или 0x3F
LiquidCrystal_I2C lcd(0x27, 16, 2); // Если не работает, попробуйте 0x3F

// Переменные для данных
float cpuTemp = 0.0;
float cpuLoad = 0.0;
unsigned long lastUpdate = 0;
String serialBuffer = "";
bool connected = false;

void setup() {
  Serial.begin(115200);
  
  // Инициализация LCD
  lcd.init();
  lcd.backlight();
  lcd.clear();
  
  // Отображение стартового экрана
  showStartupScreen();
  
  Serial.println("ESP32 PC Monitor v1.0");
  Serial.println("Waiting for Windows data...");
  Serial.println("Format: TEMP:XX.X|LOAD:XX");
}

void loop() {
  // Чтение данных из Serial
  while (Serial.available() > 0) {
    char c = Serial.read();
    
    if (c == '\n') {
      processData(serialBuffer);
      serialBuffer = "";
    } else {
      serialBuffer += c;
    }
  }
  
  // Проверка таймаута подключения (5 секунд)
  if (millis() - lastUpdate > 5000) {
    connected = false;
  }
  
  // Обновление дисплея каждые 500мс
  static unsigned long lastDisplayUpdate = 0;
  if (millis() - lastDisplayUpdate > 500) {
    updateDisplay();
    lastDisplayUpdate = millis();
  }
  
  delay(10);
}

void processData(String data) {
  data.trim();
  
  if (data.length() > 0) {
    // Ищем температуру и загрузку CPU
    int tempIndex = data.indexOf("TEMP:");
    int loadIndex = data.indexOf("LOAD:");
    
    if (tempIndex != -1) {
      // Извлекаем температуру
      int endIndex = data.indexOf('|', tempIndex);
      if (endIndex == -1) endIndex = data.length();
      
      String tempStr = data.substring(tempIndex + 5, endIndex);
      cpuTemp = tempStr.toFloat();
      
      // Отправляем подтверждение
      Serial.print("OK:");
      Serial.println(cpuTemp, 1);
    }
    
    if (loadIndex != -1) {
      // Извлекаем загрузку CPU
      int endIndex = data.indexOf('|', loadIndex);
      if (endIndex == -1) endIndex = data.length();
      
      String loadStr = data.substring(loadIndex + 5, endIndex);
      cpuLoad = loadStr.toFloat();
    }
    
    lastUpdate = millis();
    connected = true;
  }
}

void showStartupScreen() {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("PC Temp Monitor");
  lcd.setCursor(0, 1);
  lcd.print("Connect USB...");
  delay(2000);
}

void updateDisplay() {
  lcd.clear();
  
  if (!connected) {
    // Режим ожидания подключения
    lcd.setCursor(0, 0);
    lcd.print("Waiting for PC");
    
    lcd.setCursor(0, 1);
    // Анимация ожидания
    static int waitAnim = 0;
    String dots = "";
    for (int i = 0; i < (waitAnim % 4); i++) {
      dots += ".";
    }
    lcd.print("Connecting" + dots);
    waitAnim++;
    return;
  }
  
  // Первая строка: Температура CPU
  lcd.setCursor(0, 0);
  lcd.print("CPU:");
  
  if (cpuTemp > 0) {
    lcd.print(cpuTemp, 1);  // 1 знак после запятой
    lcd.write(223);         // Символ градуса
    lcd.print("C");
    
    // Визуальный индикатор температуры
    lcd.setCursor(12, 0);
    if (cpuTemp < 50) {
      lcd.print("[--]");
    } else if (cpuTemp < 70) {
      lcd.print("[++]");
    } else if (cpuTemp < 85) {
      lcd.print("[!!]");
    } else {
      lcd.print("[XX]");
    }
  } else {
    lcd.print("N/A  ");
  }
  
// Вторая строка: Загрузка CPU и статус
lcd.setCursor(0, 1);

if (cpuLoad > 0) {
  // Форматируем: "CPU:XX%[████    ]"
  lcd.print("LOAD:");
  if (cpuLoad < 10) lcd.print(" ");
  lcd.print((int)cpuLoad);
  lcd.print("% [");
  
  // Прогресс-бар из 8 символов
  int bars = map((int)cpuLoad, 0, 90, 0, 5);
  for (int i = 0; i < 5; i++) {
    if (i < bars) {
      lcd.write(255);  // Заполненный символ
    } else {
      lcd.print(" ");
    }
  }
  lcd.print("]");
} else {
  lcd.print("No data       ");
  // Отображение времени без данных
    lcd.setCursor(8, 1);
    unsigned long sec = (millis() - lastUpdate) / 1000;
    lcd.print("T:");
    lcd.print(sec);
    lcd.print("s");
  }
}
