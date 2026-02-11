#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// Для Arduino Nano: 
// SDA -> A4, SCL -> A5
// LCD2004 (20 символов, 4 строки) - адрес обычно 0x27 или 0x3F
LiquidCrystal_I2C lcd(0x27, 20, 4); // Если не работает, попробуйте 0x3F

// Переменные для данных
float cpuTemp = 0.0;
float cpuLoad = 0.0;
float gpuTemp = 0.0;
float gpuLoad = 0.0;
float ramUsage = 0.0;
unsigned long lastUpdate = 0;
char serialBuffer[128]; // Увеличили буфер для больше данных
byte bufferIndex = 0;
bool connected = false;

// Символы для прогресс-бара
byte fullBar[8] = {
  B11111,
  B11111,
  B11111,
  B11111,
  B11111,
  B11111,
  B11111,
  B11111
};

byte halfBar[8] = {
  B11100,
  B11100,
  B11100,
  B11100,
  B11100,
  B11100,
  B11100,
  B11100
};

void setup() {
  Serial.begin(9600); // Для Nano лучше использовать 9600
  
  // Инициализация LCD
  lcd.init();
  lcd.backlight();
  
  // Создаем символы для прогресс-бара
  lcd.createChar(0, fullBar);   // Полный блок
  lcd.createChar(1, halfBar);   // Полублок
  
  // Отображение стартового экрана
  showStartupScreen();
  
  Serial.println("Arduino PC Monitor v1.0");
  Serial.println("Waiting for Windows data...");
  Serial.println("Format: CPU_TEMP:XX.X|CPU_LOAD:XX|GPU_TEMP:XX.X|GPU_LOAD:XX|RAM:XX");
}

void loop() {
  // Чтение данных из Serial
  while (Serial.available() > 0) {
    char c = Serial.read();
    
    if (c == '\n') {
      serialBuffer[bufferIndex] = '\0'; // Завершаем строку
      processData(serialBuffer);
      bufferIndex = 0;
      memset(serialBuffer, 0, sizeof(serialBuffer)); // Очищаем буфер
    } else if (bufferIndex < sizeof(serialBuffer) - 1) {
      serialBuffer[bufferIndex++] = c;
    }
  }
  
  // Проверка таймаута подключения (5 секунд)
  if (millis() - lastUpdate > 5000) {
    connected = false;
  }
  
  // Обновление дисплея каждые 1000мс
  static unsigned long lastDisplayUpdate = 0;
  if (millis() - lastDisplayUpdate > 1000) {
    updateDisplay();
    lastDisplayUpdate = millis();
  }
}

void processData(char* data) {
  char tempStr[8];
  
  // Ищем температуру CPU
  char* cpuTempPtr = strstr(data, "CPU_TEMP:");
  if (cpuTempPtr != NULL) {
    cpuTempPtr += 9; // Пропускаем "CPU_TEMP:"
    cpuTemp = extractFloatValue(cpuTempPtr);
  }
  
  // Ищем загрузку CPU
  char* cpuLoadPtr = strstr(data, "CPU_LOAD:");
  if (cpuLoadPtr != NULL) {
    cpuLoadPtr += 9; // Пропускаем "CPU_LOAD:"
    cpuLoad = extractFloatValue(cpuLoadPtr);
  }
  
  // Ищем температуру GPU
  char* gpuTempPtr = strstr(data, "GPU_TEMP:");
  if (gpuTempPtr != NULL) {
    gpuTempPtr += 9; // Пропускаем "GPU_TEMP:"
    gpuTemp = extractFloatValue(gpuTempPtr);
  }
  
  // Ищем загрузку GPU
  char* gpuLoadPtr = strstr(data, "GPU_LOAD:");
  if (gpuLoadPtr != NULL) {
    gpuLoadPtr += 9; // Пропускаем "GPU_LOAD:"
    gpuLoad = extractFloatValue(gpuLoadPtr);
  }
  
  // Ищем использование RAM
  char* ramPtr = strstr(data, "RAM:");
  if (ramPtr != NULL) {
    ramPtr += 4; // Пропускаем "RAM:"
    ramUsage = extractFloatValue(ramPtr);
  }
  
  lastUpdate = millis();
  connected = true;
  
  // Отправляем подтверждение
  Serial.print("OK:CPU:");
  Serial.print(cpuTemp, 1);
  Serial.print(" GPU:");
  Serial.println(gpuTemp, 1);
}

float extractFloatValue(char* str) {
  char temp[10];
  int i = 0;
  
  // Копируем число до следующего '|' или конца строки
  while (str[i] != '\0' && str[i] != '|' && i < 9) {
    temp[i] = str[i];
    i++;
  }
  temp[i] = '\0';
  
  return atof(temp);
}

void showStartupScreen() {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("  PC Monitor v2.0");
  lcd.setCursor(0, 1);
  lcd.print("  LCD2004 Display");
  lcd.setCursor(0, 2);
  lcd.print("  Arduino Nano");
  lcd.setCursor(0, 3);
  lcd.print("Connect USB...");
  delay(2000);
}

void updateDisplay() {
  lcd.clear();
  
  if (!connected) {
    // Режим ожидания подключения
    lcd.setCursor(0, 0);
    lcd.print("  Waiting for PC");
    
    lcd.setCursor(0, 1);
    // Анимация ожидания
    static byte waitAnim = 0;
    lcd.print("   Connecting");
    for (byte i = 0; i < (waitAnim % 4); i++) {
      lcd.print(".");
    }
    waitAnim++;
    
    lcd.setCursor(0, 3);
    lcd.print(" Baud: 9600");
    return;
  }
  
  // Строка 1: CPU Температура и загрузка
  lcd.setCursor(0, 0);
  lcd.print("CPU:");
  if (cpuTemp > 0) {
    lcd.print(cpuTemp, 1);
    lcd.write(223);
    lcd.print("C");
    
    lcd.setCursor(11, 0);
    lcd.print("LOAD:");
    if (cpuLoad < 10) lcd.print(" ");
    lcd.print((int)cpuLoad);
    lcd.print("%");
    
    // Индикатор температуры CPU
    lcd.setCursor(19, 0);
    if (cpuTemp < 50) {
      lcd.write('-');
    } else if (cpuTemp < 70) {
      lcd.write('+');
    } else if (cpuTemp < 85) {
      lcd.write('!');
    } else {
      lcd.write('X');
    }
  } else {
    lcd.print("N/A");
  }
  
  // Строка 2: GPU Температура и загрузка
  lcd.setCursor(0, 1);
  lcd.print("GPU:");
  if (gpuTemp > 0) {
    lcd.print(gpuTemp, 1);
    lcd.write(223);
    lcd.print("C");
    
    lcd.setCursor(11, 1);
    lcd.print("LOAD:");
    if (gpuLoad < 10) lcd.print(" ");
    lcd.print((int)gpuLoad);
    lcd.print("%");
    
    // Индикатор температуры GPU
    lcd.setCursor(19, 1);
    if (gpuTemp < 50) {
      lcd.write('-');
    } else if (gpuTemp < 70) {
      lcd.write('+');
    } else if (gpuTemp < 85) {
      lcd.write('!');
    } else {
      lcd.write('X');
    }
  } else {
    lcd.print("N/A");
  }
  
  // Строка 3: Прогресс-бары CPU и GPU
  lcd.setCursor(0, 2);
  lcd.print("CPU[");
  if (cpuLoad > 0) {
    drawProgressBar(4, 2, cpuLoad, 10);
  } else {
    lcd.print("---");
  }
  
  lcd.setCursor(0, 3);
  lcd.print("GPU[");
  if (gpuLoad > 0) {
    drawProgressBar(4, 3, gpuLoad, 10);
  } else {
    lcd.print("---");
  }
  
  // Строка 4: RAM и время
  lcd.setCursor(11, 2);
  lcd.print("RAM:");
  if (ramUsage > 0) {
    if (ramUsage < 10) lcd.print(" ");
    lcd.print((int)ramUsage);
    lcd.print("%");
  } else {
    lcd.print("N/A");
  }
  
  // Прогресс-бар RAM
  lcd.setCursor(11, 3);
  lcd.print("[");
  if (ramUsage > 0) {
    drawProgressBar(12, 3, ramUsage, 8);
  } else {
    lcd.print("---");
  }
}

void drawProgressBar(byte col, byte row, float value, byte length) {
  lcd.setCursor(col, row);
  
  byte fullBlocks = (value * length) / 100;
  byte remainder = ((int)(value * length) % 100) / 10;
  
  for (byte i = 0; i < length; i++) {
    if (i < fullBlocks) {
      lcd.write(0); // Полный блок
    } else if (i == fullBlocks && remainder > 0) {
      lcd.write(1); // Полублок
    } else {
      lcd.print(" ");
    }
  }
  lcd.print("]");
}
