#!/bin/bash
# Безопасный запуск демона pc_temp_monitor
# Проверяет/запускает systemd, создаёт сервис при необходимости

PYTHON3=$(which python3)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MONITOR_SCRIPT="$SCRIPT_DIR/pc_temp_monitor.py"

# --- Проверка Python3 ---
if [ -z "$PYTHON3" ] || "$PYTHON3" --version 2>/dev/null | grep -qi 'python 2'; then
    echo "Ошибка: python3 не найден или это Python 2"
    exit 1
fi

# --- Проверка наличия скрипта ---
if [ ! -f "$MONITOR_SCRIPT" ]; then
    echo "Ошибка: pc_temp_monitor.py не найден в $SCRIPT_DIR"
    exit 1
fi

# --- Проверка/установка зависимостей ---
for module in serial psutil; do
    if ! "$PYTHON3" -c "import $module" 2>/dev/null; then
        echo "Устанавливаю $module..."
        "$PYTHON3" -m pip install $module 2>/dev/null || pip install $module
    fi
done

# --- Проверяем наличие сервиса systemd ---
SERVICE_EXISTS=false
for svc in pc-temp-monitor-*.service pc_temp_monitor.service pc-temp-monitor.service; do
    if [ -f "/etc/systemd/system/$svc" ]; then
        SERVICE_EXISTS=true
        break
    fi
done

if [ "$SERVICE_EXISTS" = true ]; then
    echo "Перезапускаю systemd сервис..."
    sudo systemctl daemon-reload
    sudo systemctl restart pc-temp-monitor* || true
    sudo systemctl status pc-temp-monitor* --no-pager | head -20
    echo "Логи: sudo journalctl -u pc-temp-monitor* -f --no-pager"
else
    echo "Сервис systemd не найден. Запускаю в ручном режиме с проверкой порта."

    # --- Ищем порт ---
    PORT=""
    for dev in /dev/ttyUSB0 /dev/ttyUSB1 /dev/ttyACM0 /dev/ttyACM1; do
        if [ -e "$dev" ]; then
            PORT="$dev"
            break
        fi
    done

    if [ -z "$PORT" ]; then
        echo "ОШИБКА: USB-порт ESP32 не найден!"
        echo "Проверьте:"
        echo "  1. Подключение ESP32 к USB"
        echo "  2. ls -l /dev/ttyUSB* /dev/ttyACM*"
        echo "  3. dmesg | grep tty"
        echo "Создаю /tmp/PORT_NEEDED.flag — исправьте и запустите снова."
        echo "ESP32_PORT > /tmp/PORT_NEEDED.flag"
        exit 1
    fi

    echo "Использую порт: $PORT"
    echo "Запускаю мониторинг..."
    echo "Ctrl+C для остановки"

    # Запуск с автоматическим рестартом при сбое
    while true; do
        sudo "$PYTHON3" "$MONITOR_SCRIPT" --port "$PORT" "$@"
        EXIT_CODE=$?
        
        if [ $EXIT_CODE -eq 130 ] || [ $EXIT_CODE -eq 0 ]; then
            echo "Мониторинг остановлен (exit $EXIT_CODE)"
            break
        fi
        
        echo "⚠️ Сбой (exit $EXIT_CODE). Перезапуск через 5 секунд..."
        sleep 5
    done
fi
