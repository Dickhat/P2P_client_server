import socket
import time
import datetime
import sys
import threading
import os

semaphore = threading.Semaphore(1)
ip = '192.168.0.130' 
port = 8765

groups = {} # Словарь "Группа": [массив подключений]

# Проверка текущих групп
def groups_check():
    current_file = os.path.realpath(__file__)
    current_directory = os.path.dirname(current_file)
    main_path = current_directory + '/groups/'

    semaphore.acquire()

    # Поиск групп по файлам
    for file_name in os.listdir(main_path):
       with open(main_path + file_name, "r") as file:
            groups.update({f"{file_name}":[]})      # Добавление группы в словарь групп

            for line in file:
                groups[f"{file_name}"].append(line.replace("\n", ''))
    
    semaphore.release()

# Обновление клиентов в группе
def groups_update(group_name):
    current_file = os.path.realpath(__file__)
    current_directory = os.path.dirname(current_file)
    main_path = current_directory + '/groups/'

    semaphore.acquire()

    with open(main_path + group_name, "w") as file:
        for client in groups[f"{group_name}"]:
            file.write(client + "\n")
    
    semaphore.release()

# Обработка запросов клиента
def works(connection, addr):
    # Получение запроса от клиента 
    bytes, temp = connection.recvfrom(4096)

    request = bytes.decode('utf-8')

    # Клиент решил отключиться от группы (group_name disconnect)
    if request.find("Disconnect") != -1:
        request = request.split(" ")
        groups.pop(request[1])
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

    # Проверка, что группа существует
    group_members = groups.get(request, "empty")
    group_name = request 
    response = ""

    if group_members != "empty":
        for client in group_members:
            response += client + "\n"
    else:
        response = "Группа не указана, отказ в запросе"
        connection.sendall(response.encode('utf-8'))
        connection.close()

    # Отправление членов группы
    if response == "":
        response = "no connections"
        connection.sendall(response.encode('utf-8'))
    else:
        connection.sendall(response.encode('utf-8'))

    # Получение согласия присоединения к группе
    bytes, addr = connection.recvfrom(4096)
    request = bytes.decode('utf-8')

    # Добавление активного клиента к группе (ip:port)
    groups[group_name].append(request)
    groups_update(group_name)

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
                thread.run()

if __name__ == "__main__":
    main()