#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// LCD1602 (16 символов, 2 строки) - адрес обычно 0x27 или 0x3F
LiquidCrystal_I2C lcd(0x27, 16, 2); // Если не работает, попробуйте 0x3F

// Переменные для данных
float cpuTemp = 0.0;
float cpuLoad = 0.0;
unsigned long lastUpdate = 0;
char serialBuffer[64];
int bufferIndex = 0;
bool connected = false;

void setup() {
  Serial.begin(115200);
  
  // Инициализация LCD
  lcd.init();
  lcd.backlight();
  lcd.clear();
  
  // Отображение стартового экрана
  showStartupScreen();
  
  Serial.println("ESP32 PC Monitor v1.1");
  Serial.println("Waiting for Linux PC data...");
  Serial.println("Format: TEMP:XX.X|LOAD:XX.X");

  // Предотвращаем фрагментацию String
  serialBuffer.reserve(256);
}

void loop() {
  // Чтение данных из Serial
  while (Serial.available() > 0) {
    char c = Serial.read();
    
    if (c == '\n') {
      serialBuffer[bufferIndex] = '\0';
      processData(serialBuffer);
      bufferIndex = 0;
      memset(serialBuffer, 0, sizeof(serialBuffer));
    } else if (bufferIndex < (int)sizeof(serialBuffer) - 1) {
      serialBuffer[bufferIndex++] = c;
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
}

void processData(char* data) {
  char* tempPtr = strstr(data, "TEMP:");
  char* loadPtr = strstr(data, "LOAD:");
  
  if (tempPtr) {
    cpuTemp = atof(tempPtr + 5);
    Serial.print("OK:TEMP:");
    Serial.println(cpuTemp, 1);
  }
  
  if (loadPtr) {
    cpuLoad = atof(loadPtr + 5);
  }
  
  if (tempPtr || loadPtr) {
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
