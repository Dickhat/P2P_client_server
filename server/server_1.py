import socket
import time
import datetime
import sys
import threading
import os

semaphore = threading.Semaphore(1)
ip = '192.168.0.130' 
port = 8765

groups = [] # Список активных сокетов

# Проверка текущих групп
def groups_check():
    current_file = os.path.realpath(__file__)
    current_directory = os.path.dirname(current_file)

    semaphore.acquire()

    # Просмотр активных подключений
    with open(f'{current_directory}/online clients.txt', "r") as file:
        for line in file:
            groups.append(line.replace("\n", ''))
    
    semaphore.release()

# Обновление клиентов в группе
def groups_update(request):
    current_file = os.path.realpath(__file__)
    current_directory = os.path.dirname(current_file)

    semaphore.acquire()

    # Удаление клиента из группы
    if request.find('Disconnect') != -1:
        request = request.split(" ")
        groups.remove(request[1])
     # Добавление клиента в группу
    else:
        groups.append(request)

    with open(f'{current_directory}/online clients.txt', "w") as file:
        for client in groups:
            file.write(client + "\n")
    
    semaphore.release()

# Обработка запросов клиента
def works(connection, addr):
    # Получение запроса от клиента 
    bytes, temp = connection.recvfrom(4096)

    request = bytes.decode('utf-8')

    # Клиент решил отключиться от группы (group_name disconnect)
    if request.find("Disconnect") != -1:
        groups_update(request)
        # groups_check()

        # # Удаление из группы
        # try:
        #     groups[request[0]].remove(addr[0] + ":" + f"{addr[1]}")
        #     groups_update(request[0])
        # except:
        #     error = "Вас нет в данной группе"
        #     connection.sendall(error.encode('utf-8'))
        # finally:
        #     connection.close()
        #     exit()

    if request.find("Connect") != -1:
        response = ""

        if len(groups) != 0:
            for client in groups:
                response += client + "\n"
        else:
            response = "empty"
        
        connection.sendall(response.encode('utf-8'))

        # Получение согласия присоединения к группе
        bytes, addr = connection.recvfrom(4096)
        request = bytes.decode('utf-8')

        # Добавление активного клиента к группе (ip:port)
        groups_update(request)

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
                thread = threading.Thread(target=works, args=[connection, addr])
                thread.start()

if __name__ == "__main__":
    main()