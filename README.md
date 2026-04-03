# 🌡️ PC Temperature Monitor

# 🌡️ pc_temp_monitor — Linux PC Monitor

**Latest Release:** [v1.2.0](https://github.com/adminmik7/pc_temp_monitor/releases/tag/v1.2.0) 🚀

Мониторинг реальной температуры и нагрузки CPU с выводом на LCD (1602/2004) через ESP32 или Arduino Nano. Работает в Linux, использует данные `hwmon` и `lm-sensors`.

---

## 📁 Структура

| Файл | Назначение |
|---|---|
| `pc_temp_monitor.py` | Python-скрипт отправки данных на MCU |
| `esp32_firmware.ino` | Прошивка ESP32 (LCD 1602 I2C) |
| `arduino_nano_fw.ino` | Прошивка Arduino Nano (LCD 2004 I2C) |
| `daemon_start.sh` | Скрипт безопасного запуска с авто-рестартом |

---

## 🚀 Быстрый старт

```bash
# Проверить датчики температуры
python3 pc_temp_monitor.py --check-sensors

# Запустить (интерактив)
python3 pc_temp_monitor.py --port /dev/ttyUSB0

# Запустить как демон (фон)
python3 pc_temp_monitor.py --daemon --port /dev/ttyUSB0

# Безопасный запуск (авто-порт + рестарт при сбое)
chmod +x daemon_start.sh
./daemon_start.sh
```

## 📋 Все команды

```bash
python3 pc_temp_monitor.py --check-sensors     # Проверить датчики
python3 pc_temp_monitor.py --port /dev/ttyUSB0  # Интерактивный режим
python3 pc_temp_monitor.py --daemon --port ...  # Демон (фон)
python3 pc_temp_monitor.py --log                # Показать логи
python3 pc_temp_monitor.py --list-ports         # Список портов
python3 pc_temp_monitor.py --create-service --port /dev/ttyUSB0  # systemd сервис
```

## ✅ Ключевые возможности

- Реальная температура CPU (AMD/Intel, sysfs + lm-sensors)
- Реальная нагрузка CPU (psutil + /proc/stat fallback)
- Поддержка демона с логированием
- Автоматический выбор порта
- systemd сервис для автозапуска

---

## 📝 Changelog

### 2026-04-02 — Code review & fixes

**esp32_firmware.ino v1.1:**
- ❌→✅ "Waiting for Windows data" → "Waiting for Linux PC data"
- ✅ `serialBuffer.reserve(256)` — предотвращение фрагментации памяти

**arduino_nano_fw.ino v1.1:**
- ❌→✅ "Waiting for Windows data" → "Waiting for Linux PC data"
- 🐛 **Критический баг:** Прогресс-бары CPU/GPU/RAM конфликтовали на строках 2-3 (overlap). Строка 4 (RAM) перезаписывала строку 3 (GPU). → ✅ Исправлено: RAM на строке 2 справа, GPU на строке 3

**pc_temp_monitor.py:**
- 🔧 autopep8 — автоформатирование (119 строк trailing whitespace, 4 отступа)
- ❌ Удалён неиспользуемый `from datetime import datetime`
- ❌ Удалён дублирующий `import psutil` в `__main__`
- 🔧 `except:` → `except Exception:` (6 мест)
- 🔧 Исправлен unused exception variable `e` (×2)
- 🔧 Исправлен f-string без плейсхолдеров

**Новые файлы:**
- ✅ `daemon_start.sh` — безопасный запуск с проверкой Python, зависимостей, USB-порта и авто-рестартом при сбое

### Ранее
- Удалён графический интерфейс — только консольный режим
- Убрана эмуляция температуры — только реальные данные
- Исправлена проблема с Load: 0.0%
- Добавлена поддержка демона
- Оптимизирован путь AMD: `/sys/devices/pci0000:00/0000:00:18.3/hwmon/hwmon0/temp1_input`
- Автовыбор порта при единственном ESP32

---

## 🏠 Связанные проекты

- **[openclaw-backup](https://github.com/adminmik7/openclaw-backup)** — бэкап конфигурации OpenClaw
