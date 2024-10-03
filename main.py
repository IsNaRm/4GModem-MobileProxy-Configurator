import sys
import time
import json
import wmi
from loguru import logger
import subprocess
import os
import utils
import config
from threading import Thread

import web_module


class Modem():
    def __init__(self, adapter=None):
        if adapter:
            self.name = adapter.Description
            self.MAC_Address = adapter.MACAddress
            self.IP_Address = adapter.IPAddress[0]
            self.IP_Subnet = adapter.IPSubnet[0]
            self.Default_Gateway = adapter.DefaultIPGateway[0]
            self.DNS_Servers = adapter.DNSServerSearchOrder[0]
            self.adapter = adapter
            self.proxy_port = None
            self.proxy_login = None
            self.proxy_pass = None
            self.device = None
            self.url = None

internet_adapter:Modem = None
def get_network_adapters():
    # Подключаемся к WMI
    c = wmi.WMI()

    # Получаем все сетевые адаптеры
    adapters = c.Win32_NetworkAdapterConfiguration()

    modems = []

    internet_adapters = []
    for adapter in adapters:
        if adapter.IPAddress:
            if 'Remote NDIS based' in adapter.Description:
                try:
                    modem = Modem(adapter)
                    modems.append(modem)
                except:
                    logger.error(f'Ошибка получения данных о модеме {adapter.Description}')
                    pass
            else:
                modem = Modem(adapter)
                internet_adapters.append(modem)
    return modems, internet_adapters


def generate_config():
    try:
        settings = utils.load_settings()
        proxy_config = ''
        try:
            proxy_config = open('Default_proxy_settings.txt', 'r', encoding='utf-8').read()
        except:
            pass

        users = {}
        for mac_address in settings:
            adapter = settings[mac_address]
            if adapter['proxy_login'] and adapter['proxy_pass']:
                users[mac_address] = {'proxy_login':adapter['proxy_login'], 'proxy_pass':adapter['proxy_pass']}
            if adapter['proxy_port'] is None:
                logger.warning(f'Модем - {mac_address} - не задан порт для прокси, он не будет использован')

        if len(users) > 0:
            proxy_config += f'users '
            for mac_address in users:
                data = users[mac_address]
                proxy_config += f"{data['proxy_login']}:CL:{data['proxy_pass']} "
        proxy_config += '\n'
        for adapter in adapters:
            proxy_config += '\n'
            mac_address = adapter.MAC_Address
            if adapter.proxy_port:
                if mac_address in users:
                    proxy_config += f"auth strong\nallow {users[mac_address]['proxy_login']}\n"
                else:
                    proxy_config += f"auth none\n"
                proxy_config += f"proxy -p{adapter.proxy_port} -i{internet_adapter.IP_Address} -e{adapter.IP_Address}\n"
        with open('3proxy/bin64/3proxy.cfg', 'w+') as f:
            f.write(proxy_config)
        return True
    except Exception as ex:
        logger.error(f'Не удается создать конфиг файл для прокси {ex}')
    return False

def start_proxy():
    config = generate_config()
    if config:
        proxy3_path = os.path.join(os.getcwd(), '3proxy', 'bin64')
        command = f'{proxy3_path}\\3proxy.exe {proxy3_path}\\3proxy.cfg'
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        logger.success(f'Запустил прокси')
        # Чтение и вывод stdout и stderr
        while True:
            try:
                # Чтение stdout
                stdout_line = process.stdout.readline()
                if stdout_line:
                    print(f"STDOUT: {stdout_line.strip()}")

                # Проверка завершения процесса
                if process.poll() is not None:
                    break
            except Exception as ex:
                logger.error(ex)


if __name__ == "__main__":
    settings = utils.load_settings()
    adapters, internet_adapters = get_network_adapters()
    if len(adapters) > 0:
        logger.success(f'Найдено {len(adapters)} модемов')
    else:
        logger.error(f'Модемы не найдены')
        exit()

    for adapter in adapters:
        if adapter.MAC_Address not in settings:
            adapter_data = {'proxy_port': adapter.proxy_port,
                            'proxy_login': adapter.proxy_login,
                            'proxy_pass': adapter.proxy_pass,
                            'device':adapter.device,
                            'url':adapter.Default_Gateway
                            }
            settings[adapter.MAC_Address] = adapter_data
        else:
            adapter_data = settings[adapter.MAC_Address]
            adapter.proxy_login = adapter_data['proxy_login']
            adapter.proxy_pass = adapter_data['proxy_pass']
            adapter.proxy_port = adapter_data['proxy_port']
            adapter.device = adapter_data['device']

    with open('Settings.json', 'w+') as f:
        json.dump(settings, f, indent=5)

    if len(internet_adapters) > 1:
        while True:
            try:
                logger.info(f'найдено {len(internet_adapters)} сетевых карт с доступом в инетернет')
                for i in range(len(internet_adapters)):
                    print(f'{i+1} - {internet_adapters[i].name}')
                data = input('Выберите необходимый:')
                internet_adapter = internet_adapters[int(data)]
                break
            except:
                logger.error(f'неверно введен номер, попробуйте еще раз')
    elif len(internet_adapters) == 1:
        internet_adapter = internet_adapters[0]
    else:
        internet_adapter = Modem()
        internet_adapter.IP_Address = '127.0.0.1'
    config.local_ip = internet_adapter.IP_Address
    if config.local_port is None:
        while True:
            logger.warning(f'Введите порт по которому будет доступ к смене айпи на модемах')
            try:
                port = int(input())
            except:
                logger.error(f'Не верный порт, введите еще раз')
    time.sleep(0.1)
    logger.success(f'адресс для смены ip: http://{config.local_ip}:{config.local_port}/change_ip/--device--')
    logger.info(f'Режим настройки прокси, введите номер модема для его настройки')
    time.sleep(0.1)

    while True:
        print('0 - Запуск прокси')
        for i in range(len(adapters)):
            adapter = adapters[i]
            msg = f'{i+1} - http://{adapter.Default_Gateway}, {adapter.name}, {adapter.MAC_Address}\t'
            if adapter.proxy_port:
                proxy_data = f'http://{internet_adapter.IP_Address}:{adapter.proxy_port}'
                if adapter.proxy_login and adapter.proxy_pass:
                    proxy_data += f':{adapter.proxy_login}:{adapter.proxy_pass}'
                proxy_data += f'[http://{config.local_ip}:{config.local_port}/change_ip/{adapter.MAC_Address.replace(":", "")}]'
                msg += f"Данные для доступа к прокси {proxy_data}"
            else:
                msg += f'Нужно указать как минимум порт'
            print(msg)
        try:
            choose = int(input())
            if choose < 0 and choose >= len(adapters):
                logger.error(f'Неверно введен номер, введите еще раз')
                choose = -1
        except:
            logger.error(f'Неверно введен номер, введите еще раз')
            choose = -1
        if choose == 0:
            Thread(target=web_module.start_server).start()
            start_proxy()
            break
        if choose != -1:
            adapter = adapters[choose-1]
            while True:
                print(f'Настройка прокси на модеме - {adapter.IP_Address}, {adapter.name}\n')
                if adapter.proxy_port:
                    proxy_data = f'http://{internet_adapter.IP_Address}:{adapter.proxy_port}'
                    if adapter.proxy_login and adapter.proxy_pass:
                        proxy_data += f':{adapter.proxy_login}:{adapter.proxy_pass}'
                    proxy_data += f'[http://{config.local_ip}:{config.local_port}/change_ip/{adapter.MAC_Address.replace(":", "")}]'
                    print(f"Данные для доступа к прокси {proxy_data}")

                print(f'0 - Назад')
                print(f'1 - Порт. Текущий - {adapter.proxy_port}')
                print(f'2 - Логин. Текущий - {adapter.proxy_login}')
                print(f'3 - Пароль. Текущий - {adapter.proxy_pass}')
                print(f'4 - Модель модема. Текущий - {adapter.device}')
                choose = input()
                if choose == '0':
                    break
                elif choose == '1':
                    while True:
                        data = input('Введите порт (любой от 1025 до 65535), 0 - назад:')
                        if data == '0':
                            break
                        try:
                            port = int(data)
                            adapter.proxy_port = port
                            break
                        except:
                            logger.error(f'неверно введен порт, попробуйте еще раз')
                elif choose == '2':
                    while True:
                        data = input('Введите логин, 0 - назад:')
                        if data == '0':
                            break
                        adapter.proxy_login = data
                        break
                elif choose == '3':
                    while True:
                        data = input('Введите пароль, 0 - назад:')
                        if data == '0':
                            break
                        adapter.proxy_pass = data
                        break
                elif choose == '4':
                    while True:
                        devices = json.load(open('Devices.json'))
                        logger.info(f'Выберите модель:')
                        i = 1
                        for device in devices:
                            print(f'{i} - {device}')
                            i += 1
                        try:
                            choose = int(input('Введите номер, 0 для выхода:'))
                            adapter.device = list(devices.keys())[choose-1]
                            break
                        except:
                            logger.error(f'Неверный номер, введите еще раз')

                adapter_data = {'proxy_port': adapter.proxy_port,
                                'proxy_login': adapter.proxy_login,
                                'proxy_pass': adapter.proxy_pass,
                                'device':adapter.device,
                                'url':adapter.Default_Gateway}
                settings[adapter.MAC_Address] = adapter_data
                with open('Settings.json', 'w+') as f:
                    json.dump(settings, f, indent=5)
