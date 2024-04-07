import socket
import threading

def receive_messages(client_socket, address):
    while True:
        try:
            message = client_socket.recv(1024).decode("utf-8")
            if not message:
                break
            print(f"Received message from {address}: {message}")
        except ConnectionResetError:
            break

def send_message(destination_ip, destination_port):
    while True:
        message = input("Enter a message to send:")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.connect((destination_ip, destination_port))
                s.send(message.encode("utf-8"))
            except Exception as e:
                print(f"Error sendding message to node: {destination_ip}:{destination_port}:{e}")        


def p2p_chat_node(ip, port):
    host = ip 
    own_port = port

    receive_port = own_port + 1

    server_address = (host, own_port)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind(server_address)
        server_socket.listen()

        print(f"Node running on {host}:{own_port}")

        while True:
            client_socket, addr = server_socket.accept()
            print(f"Accepted connection from {addr}")

            receive_thread =  threading.Thread(target=receive_messages, args=(client_socket, addr))
            receive_thread.start()

if __name__ == "__main__":
    node_ip = "192.168.1.70"
    node_port = 5000

    peer_ip = "192.168.1.68"
    peer_port = 5004

    receive_thread = threading.Thread(target=p2p_chat_node, args=(node_ip, node_port))
    send_thread = threading.Thread(target=send_message, args=(peer_ip, peer_port))

    receive_thread.start()
    send_thread.start()
