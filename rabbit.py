# p2p_chat_node.py
import socket
import threading

def receive_messages(client_socket, address):
    while True:
        try:
            message = client_socket.recv(1024).decode('utf-8')
            if not message:
                break
            print(f"Received message from {address}: {message}")
        except ConnectionResetError:
            break

def send_message(destination_ip, destination_port):
    while True:
        message = input("Enter your message: ")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.connect((destination_ip, destination_port))
                s.send(message.encode('utf-8'))
            except Exception as e:
                print(f"Error sending message to {destination_ip}:{destination_port}: {e}")

def p2p_chat_node(ip, port):
    host = ip
    own_port = port

    # Use a separate port for receiving messages
    receive_port = own_port + 1

    server_address = (host, own_port)
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind(server_address)
        server_socket.listen()

        print(f"Node running at {host}:{own_port}")

        while True:
            client_socket, addr = server_socket.accept()
            print(f"Accepted connection from {addr}")

            receive_thread = threading.Thread(target=receive_messages, args=(client_socket, addr))
            receive_thread.start()

if __name__ == "__main__":
    node_ip = '192.168.1.70'  # Replace with the IP address of the current node
    node_port = 5007  # Replace with a unique port for the current node

    peer_ip = '192.168.1.68'  # Replace with the IP address of the peer node
    peer_port = 5008 # Replace with the port of the peer node

    receive_thread = threading.Thread(target=p2p_chat_node, args=(node_ip, node_port))
    send_thread = threading.Thread(target=send_message, args=(peer_ip, peer_port))

    receive_thread.start()
    send_thread.start()
