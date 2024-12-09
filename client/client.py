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
def create_proccesing_files(recv_files):
    semaphore.acquire()

    request_files = ''
    my_files = os.listdir(current_directory + '/myfiles/')

    # Если нет файла или передающегося файла, то создать его и добавить в список необходимых
    for file in recv_files:
        if (my_files.count(file) == 0 and my_files.count(f"recv_{file}") == 0 and file != ''):
            created_file = open(f'{current_directory}/myfiles/recv_{file}', 'wb')
            created_file.close()
            request_files += file + '\n'

    semaphore.release()

    if request_files == '':
        request_files = 'no files available'

    return request_files

# Подключение к серверу и запрос клиентов из группы
def server_request_connect(ip, port):
    # Подключение к серверу
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((ip, port))

        send_str = input("Введите Connect для подключения к серверу:")

        s.sendall(send_str.encode('utf-8'))

        # Получение клиентов, принадлежащих группе
        full_response = b""
        response, addr = s.recvfrom(4096)
        full_response += response

        while response == 4096:
            full_response += response
            response, addr = s.recvfrom(4096)
        
        full_response = full_response.decode('utf-8')

        if full_response == "empty":
            clients = []
        else: 
            clients = full_response.split("\n")

        try:
            clients.remove("")
        finally:
            local_ip = socket.gethostbyname(socket.gethostname())

            sock_for_clients = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
            sock_for_clients.bind((local_ip, 0)) # Получение свободного порта
            address, sfc_port = sock_for_clients.getsockname()

            s.sendall(f"{address}:{sfc_port}".encode('utf-8'))
            return clients, sock_for_clients

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
    response = ""

    files = get_files()

    # Формирование сообщения о всех файлах
    for file in files:
        response += file + "\n"

    connection.sendall(response.encode('utf-8'))   # Сообщение о файлах

    # Получение списка необходимых файлов от другого клиента
    bytes, temp = connection.recvfrom(4096)
    request_files = bytes

    # Считать всю информацию
    while bytes == 4096:
        bytes, temp = connection.recvfrom(4096)
        request_files += bytes
        
    # Полученные названия файлов
    request_files = request_files.decode('utf-8')

    # Клиенту не нужны файлы
    if request_files == 'no files available':
        return

    request_files = request_files.split('\n')

    log_file = open(f'{current_directory}/log_file.txt', 'a')

    # Передача файлов кусками по 4096 байт
    for file in request_files:
        if file != '':
            with open(f'{current_directory}/myfiles/{file}', 'rb') as opened_file:
                ip_src, port_src = connection.getsockname()

                # Запись логов
                log_sem.acquire()
                log_file.write(f"От {ip_src}:{port_src} к {ip}:{port} был отправлен файл {file}\n")
                log_sem.release()

                file_data = opened_file.read(4096)
                while file_data:
                    connection.sendall(file_data)   # Сообщение о файлах
                    file_data = opened_file.read(4096)
 
    log_file.close()
    return
    
# Получение файлов
def recv_files(ip, port, connection):
     # Получение списка файлов от другого клиента
    bytes, temp = connection.recvfrom(4096)
    request = bytes

    # Считать всю информацию
    while bytes == 4096:
        bytes, temp = connection.recvfrom(4096)
        request+= bytes
        
    request = request.decode('utf-8')
    recv_files = request.split('\n')

    # Определение необходимых файлов
    request_files = create_proccesing_files(recv_files)

    # Завершение соединения, если нет необходимых файлов
    if request_files == 'no files available':
        connection.sendall(request_files.encode('utf-8'))
        return

    # Отправка запроса на определенные файлы
    connection.sendall(request_files.encode('utf-8'))

    request_files = request_files.split('\n')

    log_file = open(f'{current_directory}/log_file.txt', 'a')

    # Получение файлов кусками по 4096 байт
    for file in request_files:
        if file != '':
            with open(f'{current_directory}/myfiles/recv_{file}', 'wb') as opened_file:
                ip_src, port_src = connection.getsockname()

                # Запись логов
                log_sem.acquire()
                log_file.write(f"{ip_src}:{port_src} получил от {ip}:{port} файл {file}\n")
                log_sem.release()

                bytes, temp = connection.recvfrom(4096)

                # Запись байтов в файл
                while len(bytes) == 4096:
                    file_data = opened_file.write(bytes)
                    bytes, temp = connection.recvfrom(4096)
                else:
                    file_data = opened_file.write(bytes)
            os.rename(f'{current_directory}/myfiles/recv_{file}', f'{current_directory}/myfiles/{file}')
    
    log_file.close()
    return

# Обмен файлами среди клиентов (ОТПРАВКА ФАЙЛОВ)
def clients_exchange_send(clients, sock_for_clients):
    ip, port = sock_for_clients.getsockname()
    addr = f'{ip}:{port}'
    # Отправка сообщения о текущих файлах всем клиентам
    for client in clients:
        if addr == client:
            continue

        # Работа с клиентом по списку
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
            ip, port = client.split(':')
            connection.connect((ip, int(port)))

            send_files(ip, port, connection)
            recv_files(ip, port, connection)

            connection.close()
    exit()            

# Обмен файлами среди клиентов (ПОЛУЧЕНИЕ ФАЙЛОВ)
def clients_exchange_recv(connection, addr):    
    recv_files(addr[0], addr[1], connection)
    send_files(addr[0], addr[1], connection)
    connection.close()
    exit()

def main():
    ip, port = get_conf()
    clients, sock_for_clients = server_request_connect(ip, port)
    sock_for_clients.listen(10)
    threads_list = [] # Список запущенных потоков на получение файлов

    try:
        # Клиенты есть в группе
        if len(clients) != 0:
            threadsend = threading.Thread(target=clients_exchange_send, args=[clients, sock_for_clients])
            threads_list.append(threadsend)
            threadsend.start()

        while True:
            sock_for_clients.settimeout(40)  # Ожидание подключения 10 секунд
            connection, addr = sock_for_clients.accept()

            # Удаление отработавших потоков
            for thrd in threads_list:
                if thrd.is_alive() == False:
                    threads_list.remove(thrd)

            if connection != 0:
                thread = threading.Thread(target=clients_exchange_recv, args=[connection, addr])
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
