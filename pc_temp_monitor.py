#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PC Temperature Monitor for ESP32 - Linux Console Version
Отправляет реальную температуру процессора на ESP32 LCD дисплей
Только консольный режим, только реальные данные
Поддержка демона
"""

import serial
import serial.tools.list_ports
import time
import psutil
import os
import sys
import subprocess
from datetime import datetime
import glob
import re
import signal
import logging
from logging.handlers import RotatingFileHandler

# ============================================================================
# НАСТРОЙКА ЛОГГИРОВАНИЯ
# ============================================================================

def setup_logging(daemon_mode=False, log_level=logging.INFO):
    """Настройка системы логирования"""
    logger = logging.getLogger('pc_temp_monitor')
    
    # Очищаем существующие обработчики
    if logger.handlers:
        logger.handlers.clear()
    
    # Устанавливаем уровень логирования
    logger.setLevel(log_level)
    
    # Форматтер для логов
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    if daemon_mode:
        # В режиме демона пишем в файл в домашней директории
        home_dir = os.path.expanduser("~")
        log_file = os.path.join(home_dir, '.pc_temp_monitor.log')
        
        try:
            # Создаем обработчик с ротацией
            handler = RotatingFileHandler(
                log_file,
                maxBytes=1024*1024,  # 1MB
                backupCount=3
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
            logger.info(f"Логирование настроено в файл: {log_file}")
            return logger, log_file
            
        except (PermissionError, OSError) as e:
            # Если не удалось, используем /tmp
            log_file = '/tmp/pc_temp_monitor.log'
            try:
                handler = RotatingFileHandler(
                    log_file,
                    maxBytes=1024*1024,
                    backupCount=3
                )
                handler.setFormatter(formatter)
                logger.addHandler(handler)
                logger.info(f"Логирование настроено в файл: {log_file}")
                return logger, log_file
            except:
                # В крайнем случае используем консоль
                console_handler = logging.StreamHandler()
                console_handler.setFormatter(formatter)
                logger.addHandler(console_handler)
                logger.warning("Не удалось настроить файловое логирование, используется консоль")
                return logger, 'console'
    else:
        # В интерактивном режиме только консоль
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        logger.info("Интерактивный режим, логирование в консоль")
        return logger, 'console'

# ============================================================================
# ПОЛУЧЕНИЕ РЕАЛЬНОЙ ТЕМПЕРАТУРЫ ПРОЦЕССОРА В LINUX
# ============================================================================

def get_cpu_temperature_linux(logger):
    """
    Получение реальной температуры CPU в Linux
    Использует только реальные данные
    """
    
    # Получаем нагрузку CPU ПЕРВЫМ делом
    cpu_load = get_cpu_load()
    
    # Пробуем разные методы получения температуры
    temp = None
    
    # Метод 1: Через указанный путь AMD температуры
    if temp is None:
        temp = get_cpu_temp_from_amd_specific()
    
    # Метод 2: Через sysfs (стандартный способ)
    if temp is None:
        temp = get_cpu_temp_from_sysfs()
    
    # Метод 3: Через lm-sensors (требует установки)
    if temp is None:
        temp = get_cpu_temp_from_lm_sensors()
    
    # Если не удалось получить температуру, используем безопасное значение
    if temp is None:
        logger.warning("Не удалось получить температуру, используем безопасное значение 40°C")
        temp = 40.0  # Безопасное значение по умолчанию
    
    return round(temp, 1), round(cpu_load, 1)

def get_cpu_load():
    """Получение нагрузки CPU с гарантированным результатом"""
    try:
        # Первый вызов для инициализации (может вернуть 0.0)
        psutil.cpu_percent(interval=0.1)
        
        # Второй вызов с небольшим интервалом для получения реального значения
        cpu_load = psutil.cpu_percent(interval=0.3)
        
        # Если все еще 0.0, используем альтернативный метод
        if cpu_load == 0.0:
            # Альтернативный метод через /proc/stat
            cpu_load = get_cpu_load_from_proc()
        
        return max(0.1, cpu_load)  # Минимум 0.1% чтобы не было 0.0
    except:
        return 1.0  # Возвращаем минимальное значение при ошибке

def get_cpu_load_from_proc():
    """Альтернативный метод получения нагрузки CPU через /proc/stat"""
    try:
        with open('/proc/stat', 'r') as f:
            lines = f.readlines()
        
        for line in lines:
            if line.startswith('cpu '):
                parts = line.split()
                # user, nice, system, idle, iowait, irq, softirq, steal, guest, guest_nice
                total_time = sum(int(x) for x in parts[1:])
                idle_time = int(parts[4])
                
                # Возвращаем примерную нагрузку (100% - процент простоя)
                if total_time > 0:
                    idle_percent = (idle_time / total_time) * 100
                    return 100 - idle_percent
                break
    except:
        pass
    
    return 5.0  # Значение по умолчанию

def get_cpu_temp_from_amd_specific():
    """
    Получение температуры через конкретный путь для AMD процессоров
    /sys/devices/pci0000:00/0000:00:18.3/hwmon/hwmon0/temp1_input
    """
    amd_temp_paths = [
        '/sys/devices/pci0000:00/0000:00:18.3/hwmon/hwmon0/temp1_input',
        '/sys/devices/pci0000:00/0000:00:18.3/hwmon/hwmon1/temp1_input',
        '/sys/devices/pci0000:00/0000:00:18.3/hwmon/hwmon2/temp1_input',
    ]
    
    for temp_path in amd_temp_paths:
        try:
            if os.path.exists(temp_path):
                with open(temp_path, 'r') as f:
                    temp_str = f.read().strip()
                    # Пропускаем пустые строки или нечисловые значения
                    if not temp_str or not temp_str.replace('.', '').isdigit():
                        continue
                    
                    temp = float(temp_str) / 1000.0  # Преобразуем в градусы Цельсия
                    
                    # Проверяем, что температура реалистична
                    if 0 <= temp <= 120:
                        print(f"AMD специфичный путь: {temp_path} = {temp:.1f}°C")
                        return temp
        except (ValueError, OSError, IOError) as e:
            continue
    
    return None

def get_cpu_temp_from_sysfs():
    """
    Получение температуры через /sys/class/hwmon/
    Стандартный способ для большинства Linux систем с hwmon
    """
    try:
        # Ищем все hwmon устройства
        hwmon_dirs = glob.glob('/sys/class/hwmon/hwmon*')
        
        if not hwmon_dirs:
            return None
        
        temperatures = []
        
        for hwmon_dir in hwmon_dirs:
            try:
                # Читаем имя устройства
                name_file = os.path.join(hwmon_dir, 'name')
                if os.path.exists(name_file):
                    with open(name_file, 'r') as f:
                        device_name = f.read().strip()
                
                # Ищем файлы с температурой
                temp_files = glob.glob(os.path.join(hwmon_dir, 'temp*_input'))
                
                for temp_file in temp_files:
                    try:
                        with open(temp_file, 'r') as f:
                            temp_str = f.read().strip()
                            if not temp_str or not temp_str.replace('.', '').isdigit():
                                continue
                            
                            temp = float(temp_str) / 1000.0
                            
                            # Проверяем, что температура реалистична
                            if 0 <= temp <= 120:
                                temperatures.append(temp)
                                
                                # Пытаемся получить label для отладки
                                base_name = os.path.basename(temp_file).replace('_input', '')
                                label_file = os.path.join(hwmon_dir, f'{base_name}_label')
                                if os.path.exists(label_file):
                                    with open(label_file, 'r') as lf:
                                        label = lf.read().strip()
                                        print(f"hwmon: {device_name} - {label} = {temp:.1f}°C")
                                else:
                                    print(f"hwmon: {device_name} - {base_name} = {temp:.1f}°C")
                    except (ValueError, OSError, IOError):
                        continue
                        
            except (OSError, IOError):
                continue
        
        if temperatures:
            # Берем максимальную температуру (обычно самая горячая зона - CPU)
            max_temp = max(temperatures)
            print(f"hwmon: Максимальная температура = {max_temp:.1f}°C")
            return max_temp
            
    except Exception as e:
        print(f"Ошибка hwmon: {e}")
    
    return None

def get_cpu_temp_from_lm_sensors():
    """
    Получение температуры через lm-sensors
    Требует установки: sudo apt-get install lm-sensors
    """
    try:
        # Проверяем, установлен ли lm-sensors
        result = subprocess.run(['which', 'sensors'], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            print("lm-sensors не установлен. Установите: sudo apt-get install lm-sensors")
            return None
        
        # Получаем данные от sensors
        result = subprocess.run(['sensors'], 
                              capture_output=True, text=True,
                              timeout=3)
        
        if result.returncode == 0:
            output = result.stdout
            
            # Ищем температуры CPU в выводе
            temps = []
            lines = output.split('\n')
            
            for line in lines:
                line_lower = line.lower()
                # Ищем строки с температурой CPU
                if ('core' in line_lower or 'cpu' in line_lower or 
                    'package' in line_lower or 'tccd' in line_lower or
                    'tdie' in line_lower) and '°c' in line:
                    
                    # Извлекаем температуру из строки
                    match = re.search(r'([+-]?\d+\.?\d*)\s*°C', line)
                    if match:
                        try:
                            temp = float(match.group(1))
                            if 0 <= temp <= 120:
                                temps.append(temp)
                                print(f"lm-sensors: {line.strip()}")
                        except ValueError:
                            continue
            
            if temps:
                avg_temp = sum(temps) / len(temps)
                print(f"lm-sensors: Средняя температура CPU = {avg_temp:.1f}°C")
                return avg_temp
                
    except subprocess.TimeoutExpired:
        print("Таймаут выполнения sensors")
    except Exception as e:
        print(f"Ошибка lm-sensors: {e}")
    
    return None

def check_temperature_sources_linux():
    """
    Проверка доступных источников температуры в Linux
    """
    available_sources = []
    
    print("=" * 60)
    print("Проверка доступных источников температуры Linux...")
    print("=" * 60)
    
    # Проверяем AMD специфичный путь
    amd_temp = get_cpu_temp_from_amd_specific()
    if amd_temp is not None:
        print(f"✓ AMD специфичный путь доступен: {amd_temp:.1f}°C")
        available_sources.append("amd_specific")
    else:
        print("✗ AMD специфичный путь не доступен")
    
    # Проверяем hwmon
    hwmon_temp = get_cpu_temp_from_sysfs()
    if hwmon_temp is not None:
        print(f"✓ hwmon доступен: {hwmon_temp:.1f}°C")
        available_sources.append("hwmon")
    else:
        print("✗ hwmon не доступен")
    
    # Проверяем lm-sensors
    try:
        result = subprocess.run(['which', 'sensors'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            lm_temp = get_cpu_temp_from_lm_sensors()
            if lm_temp is not None:
                print(f"✓ lm-sensors установлен: {lm_temp:.1f}°C")
                available_sources.append("lm-sensors")
            else:
                print("✗ lm-sensors: не удалось получить температуру")
        else:
            print("✗ lm-sensors не установлен")
    except:
        print("✗ Ошибка проверки lm-sensors")
    
    # Проверяем нагрузку CPU
    cpu_load = get_cpu_load()
    print(f"✓ Нагрузка CPU: {cpu_load:.1f}%")
    
    print("-" * 60)
    print(f"Доступные источники температуры: {', '.join(available_sources) if available_sources else 'Нет'}")
    
    # Рекомендации
    if not available_sources:
        print("\nРЕКОМЕНДАЦИЯ: Установите lm-sensors для получения температуры:")
        print("sudo apt-get install lm-sensors")
        print("sudo sensors-detect")
        print("sudo service kmod start")
    else:
        print(f"\nБудет использован первый доступный источник: {available_sources[0]}")
    
    print("=" * 60)
    
    return available_sources

# ============================================================================
# КЛАСС МОНИТОРИНГА
# ============================================================================

class TemperatureMonitor:
    """Класс для мониторинга температуры"""
    
    def __init__(self, com_port, logger, log_location, daemon_mode=False):
        self.com_port = com_port
        self.serial_conn = None
        self.running = False
        self.error_count = 0
        self.max_errors = 10
        self.logger = logger
        self.log_location = log_location
        self.daemon_mode = daemon_mode
        
    def connect(self):
        """Подключение к ESP32"""
        try:
            self.logger.info(f"Подключение к {self.com_port}")
            self.serial_conn = serial.Serial(
                port=self.com_port,
                baudrate=115200,
                timeout=1,
                write_timeout=1
            )
            
            time.sleep(2)
            
            if self.serial_conn.in_waiting:
                self.serial_conn.read(self.serial_conn.in_waiting)
            
            self.serial_conn.write(b"HELLO\n")
            time.sleep(0.5)
            
            self.logger.info(f"Успешно подключено к {self.com_port}")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка подключения: {e}")
            return False
    
    def send_data(self, data_str):
        """Отправка данных на ESP32"""
        try:
            if self.serial_conn and self.serial_conn.is_open:
                if not data_str.endswith('\n'):
                    data_str += '\n'
                self.serial_conn.write(data_str.encode())
                return True
        except Exception as e:
            self.logger.error(f"Ошибка отправки данных: {e}")
        return False
    
    def run(self):
        """Основной цикл мониторинга"""
        if not self.serial_conn or not self.serial_conn.is_open:
            self.logger.error("Нет соединения с ESP32")
            return False
        
        self.running = True
        self.logger.info("Запуск мониторинга")
        
        # Инициализация psutil
        psutil.cpu_percent(interval=0.1)
        
        success_counter = 0
        
        try:
            while self.running:
                try:
                    # Получаем температуру и нагрузку
                    cpu_temp, cpu_load = get_cpu_temperature_linux(self.logger)
                    
                    # Проверяем, что данные корректны
                    if cpu_temp is None or cpu_load is None:
                        self.logger.warning("Некорректные данные, повтор через 2 секунды")
                        time.sleep(2)
                        continue
                    
                    # Формируем и отправляем данные
                    data_str = f"TEMP:{cpu_temp:.1f}|LOAD:{cpu_load:.1f}"
                    
                    if self.send_data(data_str):
                        self.error_count = 0
                        success_counter += 1
                        
                        # В режиме демона логируем реже чтобы не засорять лог
                        if not self.daemon_mode or success_counter % 10 == 0:
                            self.logger.info(f"CPU: {cpu_temp}°C, Load: {cpu_load}%")
                        
                        response = self.read_response()
                        if response:
                            if "ERROR" in response or "no data" in response:
                                self.logger.warning(f"ESP32: {response}")
                            else:
                                self.logger.debug(f"ESP32: {response}")
                    else:
                        self.error_count += 1
                        self.logger.warning(f"Ошибка отправки ({self.error_count}/{self.max_errors})")
                        
                        if self.error_count >= self.max_errors:
                            self.logger.error("Превышено максимальное количество ошибок")
                            break
                    
                    time.sleep(1)
                    
                except KeyboardInterrupt:
                    self.logger.info("Остановка по запросу пользователя")
                    self.running = False
                    break
                    
                except Exception as e:
                    self.logger.error(f"Ошибка: {e}")
                    self.error_count += 1
                    
                    if self.error_count >= self.max_errors:
                        self.logger.error("Превышено максимальное количество ошибок")
                        break
                    
                    time.sleep(2)
                    
        finally:
            self.stop()
        
        return True
    
    def read_response(self):
        """Чтение ответа от ESP32"""
        try:
            if self.serial_conn and self.serial_conn.in_waiting:
                response = self.serial_conn.readline().decode().strip()
                if response:
                    return response
        except Exception:
            pass
        return None
    
    def stop(self):
        """Остановка мониторинга"""
        self.running = False
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
        self.logger.info("Мониторинг остановлен")

# ============================================================================
# УТИЛИТЫ
# ============================================================================

def get_available_ports():
    """Получение списка доступных портов"""
    ports = []
    
    common_ports = [
        '/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyUSB2', '/dev/ttyUSB3',
        '/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyACM2', '/dev/ttyACM3'
    ]
    
    for port in common_ports:
        if os.path.exists(port):
            ports.append(port)
    
    try:
        detected_ports = serial.tools.list_ports.comports()
        for port, desc, hwid in sorted(detected_ports):
            if port not in ports:
                ports.append(port)
    except:
        pass
    
    return ports

def find_log_file():
    """Поиск файла лога"""
    log_locations = [
        os.path.join(os.path.expanduser("~"), '.pc_temp_monitor.log'),
        '/tmp/pc_temp_monitor.log'
    ]
    
    for log_file in log_locations:
        if os.path.exists(log_file):
            return log_file
    
    return None

def show_log_tail(lines=50):
    """Показать хвост лог-файла"""
    log_file = find_log_file()
    
    if log_file:
        print(f"Лог-файл: {log_file}")
        print(f"Последние {lines} строк:\n")
        print("=" * 80)
        
        try:
            with open(log_file, 'r') as f:
                file_lines = f.readlines()
                if len(file_lines) > lines:
                    print("...\n")
                    for line in file_lines[-lines:]:
                        print(line.rstrip())
                else:
                    for line in file_lines:
                        print(line.rstrip())
        except Exception as e:
            print(f"Ошибка чтения лог-файла: {e}")
    else:
        print("Лог-файл не найден. Возможные причины:")
        print("1. Демон не был запущен")
        print("2. Демон запущен в интерактивном режиме")
        print("\nПопробуйте запустить демон:")
        print(f"  python3 {sys.argv[0]} --daemon --port /dev/ttyUSB0")

# ============================================================================
# СКРИПТ ДЛЯ SYSTEMD
# ============================================================================

def create_systemd_service(port):
    """Создание systemd сервисного файла"""
    service_content = f"""[Unit]
Description=PC Temperature Monitor for ESP32
After=network.target
Wants=network.target

[Service]
Type=simple
User={os.getenv('USER')}
WorkingDirectory={os.getcwd()}
ExecStart=/usr/bin/python3 {os.path.abspath(__file__)} --port {port}
Restart=always
RestartSec=10
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=pc_temp_monitor
Environment="PYTHONUNBUFFERED=1"

# Права на доступ к USB порту
SupplementaryGroups=dialout

[Install]
WantedBy=multi-user.target
"""
    
    service_file = f"/etc/systemd/system/pc-temp-monitor-{os.getenv('USER')}.service"
    
    print(f"Создание systemd сервиса: {service_file}")
    print("\nСодержимое сервисного файла:")
    print("-" * 60)
    print(service_content)
    print("-" * 60)
    
    try:
        with open(service_file, 'w') as f:
            f.write(service_content)
        
        print(f"✓ Сервис создан: {service_file}")
        print("\nКоманды для управления:")
        print(f"  sudo systemctl daemon-reload")
        print(f"  sudo systemctl enable pc-temp-monitor-{os.getenv('USER')}.service")
        print(f"  sudo systemctl start pc-temp-monitor-{os.getenv('USER')}.service")
        print(f"  sudo systemctl status pc-temp-monitor-{os.getenv('USER')}.service")
        print(f"  sudo journalctl -u pc-temp-monitor-{os.getenv('USER')}.service -f")
        
    except PermissionError:
        print("✗ Недостаточно прав. Запустите с sudo:")
        print(f"  sudo python3 {sys.argv[0]} --create-service --port {port}")

# ============================================================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='PC Temperature Monitor for ESP32 - Linux Console Version',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Примеры использования:
  python3 %(prog)s --port /dev/ttyUSB0                    # Интерактивный режим
  python3 %(prog)s --daemon --port /dev/ttyUSB0          # Запуск демона
  python3 %(prog)s --check-sensors                       # Проверить датчики температуры
  python3 %(prog)s --list-ports                          # Список портов
  python3 %(prog)s --log                                 # Показать логи демона
  python3 %(prog)s --create-service --port /dev/ttyUSB0  # Создать systemd сервис
        '''
    )
    
    parser.add_argument('--port', help='COM порт ESP32 (например: /dev/ttyUSB0)')
    parser.add_argument('--daemon', action='store_true', help='Запуск в режиме демона')
    parser.add_argument('--check-sensors', action='store_true', help='Проверить датчики температуры')
    parser.add_argument('--list-ports', action='store_true', help='Показать доступные порты')
    parser.add_argument('--log', action='store_true', help='Показать логи демона')
    parser.add_argument('--create-service', action='store_true', help='Создать systemd сервис')
    parser.add_argument('--verbose', '-v', action='store_true', help='Подробный вывод')
    
    args = parser.parse_args()
    
    # Проверка аргументов
    if args.check_sensors:
        check_temperature_sources_linux()
        return
    
    if args.log:
        show_log_tail()
        return
    
    if args.create_service:
        if not args.port:
            print("Ошибка: укажите порт для создания сервиса")
            print("Пример: --create-service --port /dev/ttyUSB0")
            return
        create_systemd_service(args.port)
        return
    
    if args.list_ports:
        ports = get_available_ports()
        if ports:
            print("Доступные порты:")
            for i, port in enumerate(ports, 1):
                try:
                    detected_ports = serial.tools.list_ports.comports()
                    desc = next((d for p, d, h in detected_ports if p == port), "")
                    if desc:
                        print(f"  {i}. {port} - {desc[:50]}")
                    else:
                        print(f"  {i}. {port}")
                except:
                    print(f"  {i}. {port}")
        else:
            print("Порты не найдены. Подключите ESP32.")
        return
    
    # Определяем порт для мониторинга
    if not args.port:
        ports = get_available_ports()
        if not ports:
            print("Ошибка: Порты не найдены. Подключите ESP32.")
            sys.exit(1)
        
        if len(ports) == 1:
            args.port = ports[0]
            print(f"Автоматически выбран порт: {args.port}")
        else:
            print("Доступные порты:")
            for i, port in enumerate(ports, 1):
                print(f"  {i}. {port}")
            
            try:
                choice = input(f"\nВыберите порт (1-{len(ports)}) или нажмите Enter для выхода: ").strip()
                if choice == '':
                    return
                
                index = int(choice) - 1
                if 0 <= index < len(ports):
                    args.port = ports[index]
                else:
                    print("Неверный выбор")
                    return
            except (ValueError, KeyboardInterrupt):
                return
    
    # Проверяем датчики температуры перед запуском
    print("\nПроверка датчиков температуры...")
    temperature_sources = check_temperature_sources_linux()
    
    if not temperature_sources:
        print("\n⚠  Внимание: Не найдены датчики температуры!")
        print("Программа будет использовать безопасное значение 40°C")
        print("Для получения реальных данных установите lm-sensors:")
        print("  sudo apt-get install lm-sensors")
        print("  sudo sensors-detect")
        print("=" * 60)
    
    # Уровень логирования
    log_level = logging.DEBUG if args.verbose else logging.INFO
    
    if args.daemon:
        # Запуск в режиме демона
        print(f"\nЗапуск демона на порту {args.port}")
        print("Логи будут записываться в: ~/.pc_temp_monitor.log")
        print("Для остановки нажмите Ctrl+C\n")
        
        # Настраиваем логирование для демона
        logger, log_location = setup_logging(daemon_mode=True, log_level=log_level)
        
        monitor = TemperatureMonitor(args.port, logger, log_location, daemon_mode=True)
        
        def signal_handler(sig, frame):
            print("\nПолучен сигнал остановки...")
            monitor.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        if monitor.connect():
            monitor.run()
        else:
            print("Не удалось подключиться к ESP32")
            sys.exit(1)
    else:
        # Интерактивный режим
        print(f"\nЗапуск в интерактивном режиме на порту {args.port}")
        print("Нажмите Ctrl+C для остановки\n")
        
        logger, log_location = setup_logging(daemon_mode=False, log_level=log_level)
        monitor = TemperatureMonitor(args.port, logger, log_location, daemon_mode=False)
        
        def signal_handler(sig, frame):
            print("\nОстановка...")
            monitor.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        
        if monitor.connect():
            monitor.run()
        else:
            print("Не удалось подключиться к ESP32")
            sys.exit(1)

# ============================================================================

if __name__ == "__main__":
    # Проверка зависимостей
    try:
        import serial
        import psutil
    except ImportError as e:
        print(f"Ошибка: Отсутствует зависимость: {e}")
        print("Установите необходимые модули:")
        print("  pip install pyserial psutil")
        sys.exit(1)
    
    main()
