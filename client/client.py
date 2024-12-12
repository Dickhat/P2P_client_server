import socket
import sys
import os
import threading
import time

semaphore = threading.Semaphore(1)              # Для получения названий файлов
create_file_sem = threading.Semaphore(1)        # Семафор для создания файлов, отправляющихся по соединениями
log_sem = threading.Semaphore(1)                # Семафор для файла логов

current_file = os.path.realpath(__file__)
current_directory = os.path.dirname(current_file)

chosen_group = ''

# Получение ip:port сервера
def get_conf():
    # Получение данных из файла конфигурации
    with open(current_directory + '/configure.txt', 'r') as conf_file:
        data = conf_file.read().split(':')

        if (len(data) != 2):
            print("\nconfigure file incorrect\n")
            exit 

        if(len(sys.argv) < 2):
            print("\nNo input message\n")
            exit 

        ip = data[0]
        port = int(data[1])

        return ip, port

# Получение файлов на клиенте
def get_files():
    semaphore.acquire()
    files = os.listdir(current_directory + '/myfiles/')
    semaphore.release()

    return files

# Создание файлов типа "Обрабатываемые"
def create_proccesing_files(file_name):
    semaphore.acquire()

    request_files = ''
    my_files = os.listdir(current_directory + '/myfiles/')

    file_name = file_name.replace('\n', '')

    # Если нет файла или передающегося файла, то создать его и добавить в список необходимых
    if (my_files.count(file_name) == 0 and my_files.count(f"recv_{file_name}") == 0 and file_name != ''):
        created_file = open(f'{current_directory}/myfiles/recv_{file_name}', 'wb')
        created_file.close()

    semaphore.release()

# Подключение к серверу, запрос групп, выбор файла из группы и получение клиентов, раздающих этот файл
def server_request_connect(ip, port):
    # Подключение к серверу
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((ip, port))

        send_str = input("Введите Connect для подключения к серверу:")

        s.sendall(send_str.encode('utf-8'))

        # Получение групп с сервера
        full_response = b""
        response, addr = s.recvfrom(4096)
        full_response += response

        while response == 4096:
            full_response += response
            response, addr = s.recvfrom(4096)
        
        full_response = full_response.decode('utf-8').split('\n')
        
        print('Выберите номер группы для присоединения к ней:')
        for i in range(0, len(full_response) - 1):
            print(f'{i + 1}.{full_response[i]}\n')
    

        while True:
            try:
                chosen_group = input()
                chosen_group = full_response[int(chosen_group) - 1]

                if chosen_group == '':
                    print("Неверно выбрана группа\n")
                else:
                    break
            except:
                print("Неверно выбрана группа\n")

        # Отправка выбранной группы
        s.sendall(chosen_group.encode('utf-8'))        

        # Получение информации о доступных файлов в группе
        full_response = b""
        response, addr = s.recvfrom(4096)
        full_response += response

        while response == 4096:
            full_response += response
            response, addr = s.recvfrom(4096)
        
        full_response = full_response.decode('utf-8').split('\n')

        # Отправка информации о выбранном файле и списке своих файлов
        files = get_files()
        request = ''
        file_name = ''

        # Если доступные файлы есть
        if full_response[0] != 'empty':
            print('Выберите номер файла для получения:\n')
            for i in range(0, len(full_response) - 1):
                print(f'{i + 1}.{full_response[i]}')
        
            while True:
                try:
                    chosen_file = input()
                    chosen_file = full_response[int(chosen_file) - 1]
                    break
                except:
                    print("Неверно выбран файл\n")
            
            file_name = chosen_file + '\n'
        else:
            file_name = 'No available files\n'
        
        request = file_name + chosen_group + '\n'

        local_ip = socket.gethostbyname(socket.gethostname())

        sock_for_clients = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
        sock_for_clients.bind((local_ip, 0)) # Получение свободного порта
        address, sfc_port = sock_for_clients.getsockname()
        
        request += f"{address}:{sfc_port}\n"

        # Файлы клиента
        for file in files:
            request += file + '\n'

        # Отправка выбранного файла (если был доступе) и своих файлов
        s.sendall(request.encode('utf-8'))   
    
        # Получение информации о доступных файлов в группе
        full_response = b""
        response, addr = s.recvfrom(4096)
        full_response += response

        while response == 4096:
            full_response += response
            response, addr = s.recvfrom(4096)
        
        # Если файлов нет - нет и клиентов раздающих его
        if full_response.decode('utf-8') == 'empty':
            clients = []
        else:
            clients = full_response.decode('utf-8').split('\n')

        return clients, sock_for_clients, file_name

# Отключение от сервера и уведомление об этом его
def server_request_disconnect(ip_sfc, port_sfc, ip, port):
    # Подключение к серверу с запросом отключения Listen сокета
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((ip, port))

        request = f"Disconnect {ip_sfc}:{port_sfc}"

        s.sendall(request.encode('utf-8'))
    return


# Отправка файлов 
def send_files(ip, port, connection):
    # Получение запроса на файл
    request_file, temp = connection.recvfrom(4096)

    # Полученные названия файла
    request_file = request_file.decode('utf-8').split('\n')
    
    current_client = int(request_file[0])
    total_clients = int(request_file[1])
    file_name = request_file[2]

    log_file = open(f'{current_directory}/log_file.txt', 'a')

    # Передача файлов кусками по 4096 байт
    with open(f'{current_directory}/myfiles/{file_name}', 'rb') as opened_file:
        ip_src, port_src = connection.getsockname()

        file_size = os.path.getsize(f'{current_directory}/myfiles/{file_name}')

        send_by_client = file_size//total_clients

        # Устанавливаем указатель на начальную позицию считывания в зависимости от номера передающего клиента
        opened_file.seek(current_client*send_by_client)

        remaining_bytes = send_by_client

        if(current_client == total_clients):
            remaining_bytes = send_by_client + 1

        # Читаем и отправляем данные порциями
        while remaining_bytes > 0:
            # Считываем максимум 4096 байт за раз
            chunk_size = min(4096, remaining_bytes)
            file_data = opened_file.read(chunk_size)
            
            connection.sendall(file_data)  # Отправка данных
            remaining_bytes -= len(file_data)

        # Запись логов
        log_sem.acquire()
        log_file.write(f"От {ip_src}:{port_src} к {ip}:{port} были отправлены {send_by_client} Байт файла {file_name}\n")
        log_sem.release()
 
    log_file.close()
    return
   
# Получение файлов
def recv_files(ip, port, connection, file_name, current_client, total_clients):
    request = f'{current_client}\n{total_clients}\n{file_name}'
    
    file_name = file_name.replace('\n', '')

    # Отправление запроса на получение файла
    connection.sendall(request.encode('utf-8'))

    request = ''

    # Получение части файла
    bytes, temp = connection.recvfrom(4096)
    request = bytes

    bytes = len(bytes)

    # Считать всю информацию
    while bytes == 4096:
        bytes, temp = connection.recvfrom(4096)
        request+= bytes
        bytes = len(bytes)

    log_file = open(f'{current_directory}/log_file.txt', 'a')

    # ПРОВЕРИТЬ ДОЗАПИСЬ В БАЙТАХ
    with open(f'{current_directory}/myfiles/recv_{file_name}', 'ab') as opened_file:
        ip_src, port_src = connection.getsockname()

        # Запись логов
        log_sem.acquire()
        bytes = len(request)
        log_file.write(f"{ip_src}:{port_src} получил от {ip}:{port} {bytes} байт файла {file_name}\n")
        log_sem.release()

        file_data = opened_file.write(request)
        
    log_file.close()
    return

# Обмен файлами среди клиентов (ОТПРАВКА ФАЙЛОВ)
def clients_exchange_send_request(clients, sock_for_clients, file_name):
    ip, port = sock_for_clients.getsockname()
    addr = f'{ip}:{port}'

    file_name = file_name.replace('\n', '')

    current_client = 0

    # Отправка сообщения о запросе частей файла всем клиентам, полученным от сервера
    for client in clients:
        if addr == client or client == '':
            continue

        # Работа с клиентом по списку
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
            ip, port = client.split(':')
            connection.connect((ip, int(port)))

            create_proccesing_files(file_name)
            recv_files(ip, port, connection, file_name, current_client, len(clients) - 1)

            connection.close()
        
        current_client += 1
   
    try:
        os.rename(f'{current_directory}/myfiles/recv_{file_name}', f'{current_directory}/myfiles/{file_name}')
    except:
        os.remove(f'{current_directory}/myfiles/{file_name}')
        os.rename(f'{current_directory}/myfiles/recv_{file_name}', f'{current_directory}/myfiles/{file_name}')

    exit()            

def main():
    ip, port = get_conf()
    clients, sock_for_clients, file_name = server_request_connect(ip, port)
    sock_for_clients.listen(10)
    threads_list = [] # Список запущенных потоков на получение файлов

    try:
        # Клиенты с необходимым файлом есть
        if len(clients) != 0:
            threadsend = threading.Thread(target=clients_exchange_send_request, args=[clients, sock_for_clients, file_name])
            threads_list.append(threadsend)
            threadsend.start()

        while True:
            sock_for_clients.settimeout(200)  # Ожидание подключения 40 секунд
            connection, addr = sock_for_clients.accept()

            # Удаление отработавших потоков
            for thrd in threads_list:
                if thrd.is_alive() == False:
                    threads_list.remove(thrd)

            if connection != 0:
                thread = threading.Thread(target=send_files, args=[addr[0], addr[1], connection])
                threads_list.append(thread)
                thread.start()
    except:
        ip_sfc, port_sfc = sock_for_clients.getsockname()   # Получение ip:port для Listen сокета
        sock_for_clients.close()
        server_request_disconnect(ip_sfc, port_sfc, ip, port)
    finally:
        # Удаление отработавших потоков
        for thrd in threads_list:
            if thrd.is_alive() == False:
                thrd.join()
                threads_list.remove(thrd)


if __name__ == "__main__":
    main()
