import socket
import sys
import threading
import os

semaphore = threading.Semaphore(1)
ip = '192.168.0.130' 
port = 8765

groups = {} # Список активных сокетов

# Проверка групп
def groups_check():
    current_file = os.path.realpath(__file__)
    current_directory = os.path.dirname(current_file)

    semaphore.acquire()

    # Поиск групп по файлам
    for file_name in os.listdir(current_directory + '/groups/'):
       with open(current_directory + '/groups/' + file_name, "r", encoding='utf-8') as file:
            groups.update({f"{file_name}":[]})      # Добавление группы в словарь групп

            books_clients = {}

            # Получение из группы книг, которые в ней есть, с пользователями, которые эти книги могут предоставить
            for line in file:
                info, clients = line.split('|')
                clients = clients.split(',')
                clients[len(clients) - 1] = clients[len(clients) - 1].replace('\n', '')
                books_clients.update({info:clients})

            groups[f"{file_name}"].append(books_clients)
    
    semaphore.release()

# Проверка групп
def groups_write_in_file():
    current_file = os.path.realpath(__file__)
    current_directory = os.path.dirname(current_file)

    semaphore.acquire()

    # Поиск групп по файлам
    for file_name in os.listdir(current_directory + '/groups/'):
        with open(current_directory + '/groups/' + file_name, "w", encoding='utf-8') as file:
            for book in groups[file_name][0]:
                file.write(f'{book}|')
                for client in groups[file_name][0][book]:
                    file.write(f'{client},')
                file.write('\n')
    
    semaphore.release()

# Обновление групп с книгами и пользователями
def groups_update(request):
    current_file = os.path.realpath(__file__)
    current_directory = os.path.dirname(current_file)

    # Удаление клиента из группы
    if request.find('Disconnect') != -1:
        semaphore.acquire()

        trash, addr = request.split(" ") # Disconnect {group_name} {ip:port}


        for group in groups:
            files = groups[group][0]
            # list для избегания ошибки: dictionary changed size during iteration
            for file, clients in list(files.items()):
                try:
                    clients.remove(addr)

                    # Если клиентов не осталось, то удаляем файл из набора возможных передач
                    if len(clients) == 0:
                        files.pop(file)
                except:
                    error = 'Не является владельцем этой книги'
        
        semaphore.release()
     # Добавление клиента в группу {chosen_file}\n{group_name}\n{ip:port}\nclient_files
    else:
        semaphore.acquire()
        request = request.split('\n')

        group_name = request[1]
        ip_port = request[2]

        group_files = groups[group_name][0]

        # Добавление/Обновление книг доступных в группе
        for index in range(3, len(request) - 1):
            file = request[index]
            if group_files.get(file, 'empty') == 'empty':
                group_files.update({file:[ip_port]})
            else:
                group_files[file].append(ip_port)

        semaphore.release()
    groups_write_in_file()

def get_clients_of_file(group_name, file):
    clients = []

    if file == 'No available files':
        return clients
    
    semaphore.acquire()

    clients = groups[group_name][0][file]
    
    semaphore.release()
    
    return clients

# Обработка запросов клиента
def requests_processing(connection, addr):
    # Получение запроса от клиента 
    bytes, trsh_addr = connection.recvfrom(4096)

    request = bytes.decode('utf-8')

    # Клиент решил отключиться от группы (group_name disconnect)
    if request.find("Disconnect") != -1:
        groups_update(request)

    if request.find("Connect") != -1:
        response = ""

        if len(groups) != 0:
            for group in groups:
                response += group + "\n"
        else:
            response = "empty"
        
        connection.sendall(response.encode('utf-8'))

        # Получение названия группы, к которой клиент подключается
        bytes, trsh_addr = connection.recvfrom(4096)
        group_name = bytes.decode('utf-8')
        
        response = ''

        # Отправка доступных файлов в группе
        for book in groups[group_name][0]:
            response += book + '\n'

        if response == '':
            response = 'empty'

        connection.sendall(response.encode('utf-8'))

        # Прием выбранного файла (если файлы существуют) и файлов, которые клиент может отправить {chosen_file}\n{group_name}\n{ip:port}\nclient_files
        full_response = b""
        bytes, trsh_addr = connection.recvfrom(4096)
        full_response += bytes

        while bytes == 4096:
            full_response += bytes
            bytes, trsh_addr = connection.recvfrom(4096)

        full_response = full_response.decode('utf-8')
        
        chosen_file = full_response.split('\n')[0]
        group_name = full_response.split('\n')[1]

        client_with_file = get_clients_of_file(group_name, chosen_file)

        # Отправка ip:port клиентов с выбранным файлом
        response = ''

        if len(client_with_file) == 0:
            response = 'empty'

        for client in client_with_file:
            response += client + '\n'

        connection.sendall(response.encode('utf-8'))

        # Подключение клиента к группе
        groups_update(full_response)

    connection.close()

def main():
    groups_check()

    # Подключение к серверу
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((ip, port))
        s.listen(10)

        while True:
            connection, addr = s.accept()

            if connection != 0:
                thread = threading.Thread(target=requests_processing, args=[connection, addr])
                thread.start()

if __name__ == "__main__":
    main()

