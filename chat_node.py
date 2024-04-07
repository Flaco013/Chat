from flask import Flask, render_template, request
import pika
import threading
import time
import sys
import os

# Set the template folder path relative to the script
template_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=template_folder)

# Configuration
MY_NODE_ID = "Node1"  # Change this for each node
QUEUE_NAME = "chat_queue"
EXCHANGE_NAME = "chat_exchange"
ROUTING_KEY = "chat_routing_key"
OTHER_NODES = ["192.168.1.68"]  # Adjust based on the number of nodes in your network

def connect_to_rabbitmq():
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        channel = connection.channel()

        # Declare exchange
        channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type='direct')

        # Declare queue
        channel.queue_declare(queue=QUEUE_NAME)

        # Bind queue to exchange with routing key
        channel.queue_bind(exchange=EXCHANGE_NAME, queue=QUEUE_NAME, routing_key=ROUTING_KEY)

        return connection, channel

    except Exception as e:
        print(f"Error connecting to RabbitMQ: {e}")
        return None, None

connection, channel = connect_to_rabbitmq()

def send_message(message, destination):
    channel.basic_publish(exchange=EXCHANGE_NAME,
                          routing_key=ROUTING_KEY,
                          body=f'{MY_NODE_ID}({time.time()}): {message}',
                          properties=pika.BasicProperties(
                              delivery_mode=2,  # Make the message persistent
                          ))

    print(f"Message sent to {destination}: {message}")

def receive_message(ch, method, properties, body):
    print(f"Received message: {body}")

def listen_for_messages():
    global connection, channel
    while True:
        try:
            if connection and connection.is_open:
                channel.basic_consume(queue=QUEUE_NAME, on_message_callback=receive_message, auto_ack=True)
                print("Listening for messages...")
                channel.start_consuming()
            else:
                print("Reconnecting to RabbitMQ...")
                connection, channel = connect_to_rabbitmq()

        except Exception as e:
            print(f"Error in message listener: {e}")
            time.sleep(5)  # Wait for 5 seconds before attempting to reconnect


# Start message listener in a separate thread
message_listener_thread = threading.Thread(target=listen_for_messages)
message_listener_thread.start()

@app.route('/')
def index():
    return render_template('chatWeb.html')

@app.route('/send_message', methods=['POST'])
def send_chat_message():
    message = request.form['message']
    destination = request.form['destination']

    if destination in OTHER_NODES:
        send_message(message, destination)
    else:
        print(f"Destination node '{destination}' not found.")

    return '', 204

if __name__ == '__main__':
    app.run(debug=True)
