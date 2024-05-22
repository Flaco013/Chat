

# chat_app.py
import re
import threading
from flask import Flask, render_template, request
import pika
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
# from cassandra.io.libevreactor import LibevConnection
# from cassandra.cluster import Cluster
from datetime import datetime
from flask import jsonify  
from flask import redirect, url_for
from flask import request
from flask import session


# cluster = Cluster()
# cluster.connection_class = LibevConnection
# session = cluster.connect()
import uuid

app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'

class ChatApp:
    # RabbitMQ connection parameters
    RABBITMQ_HOST = '192.168.1.70'
    RABBITMQ_PORT = 5672
    RABBITMQ_USERNAME = 'test'
    RABBITMQ_PASSWORD = 'test'



    def __init__(self, user_queue, partner_queue):
        self.user_queue = user_queue
        self.partner_queue = partner_queue

        self.credentials = pika.PlainCredentials(ChatApp.RABBITMQ_USERNAME, ChatApp.RABBITMQ_PASSWORD)
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=ChatApp.RABBITMQ_HOST, port=ChatApp.RABBITMQ_PORT, credentials=self.credentials))
        self.receiver_thread = threading.Thread(target=self.start_receiver, args=(user_queue, )) # Create a thread for the receiver

        self.receiver_thread.start() # Start the thread

                   # Cassandra connection parameters
        cassandra_host = ['192.168.1.68', '192.168.1.70','192.168.1.67']  # Replace with IP addresses or hostnames
        cassandra_port = 9042  # Cassandra default port
        cassandra_username = 'AllowAllAuthenticator'
        cassandra_password = 'AllowAllAuthenticator'
        keyspace = 'chat_app'
        
        # Connect to Cassandra
        auth_provider = PlainTextAuthProvider(username=cassandra_username, password=cassandra_password)
        self.cluster = Cluster(contact_points=cassandra_host, port=cassandra_port, auth_provider=auth_provider)
        self.session = self.cluster.connect(keyspace)
        
        # Create Cassandra tables if they don't exist
        self.create_cassandra_tables()
        
    def create_cassandra_tables(self):
        self.session.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            message_id UUID,
            sender TEXT,
            receiver TEXT,
            message TEXT,
            timestamp TIMESTAMP,
            PRIMARY KEY ((sender, receiver), timestamp, message_id)
        )
    """)


    def clear_message(self, channel, method, properties, body):
        '''
        This function is called when a message is received by the consumer.
        It prints the message to the console and acknowledges the message to the broker.
        The broker will delete the message from the queue.
        :param channel:
        :param method:
        :param properties:
        :param body:
        :return:
        '''
        print(f"Received message: {body.decode()}")
        channel.basic_ack(delivery_tag=method.delivery_tag)


    def start_receiver(self, queue_name):
        print('start_receiver')
        '''
        This function starts a consumer that listens to the queue and calls the on_message function when a message is received.
        It blocks the main thread, so it should be run in a separate thread.
        :param queue_name:
        :return:
        '''
        def callback(ch, method, properties, body):
            print('callback')
            '''
            This function is called when a message is received by the consumer.
            The parameters are passed by the Pika library, not from the code.
            :param ch:
            :param method:
            :param properties:
            :param body:
            :return:
            '''
            self.clear_message(ch, method, properties, body)

        # set credentials
        credentials = self.credentials

        # set connection for
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=ChatApp.RABBITMQ_HOST, port=ChatApp.RABBITMQ_PORT, credentials=credentials))

        self.channel = connection.channel()

        self.channel.queue_declare(queue=queue_name, durable=True)
        self.channel.basic_consume(queue=queue_name, on_message_callback=callback)

        print(f" [*] Waiting for messages in {queue_name}. To exit press CTRL+C")
        self.channel.start_consuming()

    def send_message(self, queue_name, message):
        print('send_message')
        channel = self.connection.channel()

        channel.queue_declare(queue=queue_name, durable=True)
        channel.basic_publish(exchange='', routing_key=queue_name, body=message)
        print(f" [x] Sent '{message}'")

            # Insert message into Cassandra
        message_id = uuid.uuid4()
        timestamp = datetime.now()
        self.session.execute("""
            INSERT INTO messages (message_id, sender, receiver, message, timestamp)
            VALUES (%s, %s, %s, %s, %s)
    """, (message_id, self.user_queue, self.partner_queue, message, timestamp))

@app.route('/')
def nodes():
    return render_template('nodes.html')

# Route to handle node selection and redirect to messaging page
@app.route('/message')
def message():
    node_id = request.args.get('node')
    partner_queue = ''  # Default value
    if node_id == 'node2':
        partner_queue = 'Mac'
    elif node_id == 'node3':
        partner_queue = 'Uly'

    if 'chat_app' not in session:
        session['chat_app'] = {}    

    session['chat_app']['partner_queue'] = partner_queue

    return redirect(url_for('index', partner_queue=partner_queue))  # Pass partner_queue as a URL parameter


@app.route('/index')
def index():
    # Fetch messages from Cassandra
    messages = []
    
    # Retrieve partner_queue from URL parameter or session
    partner_queue = request.args.get('partner_queue')
    if not partner_queue:
        partner_queue = session.get('partner_queue')
    
    # If partner_queue is not set, redirect to node selection page
    if not partner_queue:
        return redirect(url_for('nodes'))

    # Initialize chat_app_info dictionary with user_queue and partner_queue
    chat_app_info = {
        'user_queue': "Thinkpad",  # Set default user_queue value
        'partner_queue': partner_queue
    }
    
    # Instantiate ChatApp object using user_queue and partner_queue
    chat_app = ChatApp(chat_app_info['user_queue'], chat_app_info['partner_queue'])

    # Set chat_app_info in session
    session['chat_app'] = chat_app_info
    
    # Query for messages sent from the current user to the partner
    query_sent = "SELECT * FROM messages WHERE sender = %s AND receiver = %s ALLOW FILTERING"
    rows_sent = chat_app.session.execute(query_sent, (chat_app_info['user_queue'], chat_app_info['partner_queue']))
    
    # Query for messages sent from the partner to the current user
    query_received = "SELECT * FROM messages WHERE sender = %s AND receiver = %s ALLOW FILTERING"
    rows_received = chat_app.session.execute(query_received, (chat_app_info['partner_queue'], chat_app_info['user_queue']))

    # Add messages sent from the current user to the partner
    for row in rows_sent:
        messages.append({'sender': row.sender, 'receiver': row.receiver, 'message': row.message, 'timestamp': row.timestamp, 'is_sender': True})

    # Add messages sent from the partner to the current user
    for row in rows_received:
        messages.append({'sender': row.sender, 'receiver': row.receiver, 'message': row.message, 'timestamp': row.timestamp, 'is_sender': False})

    # Sort messages by timestamp
    messages.sort(key=lambda x: x['timestamp'])

    # Render template with retrieved messages and current user information
    return render_template('index.html', messages=messages, current_user=chat_app_info['user_queue'])

@app.route('/send_message', methods=['POST'])
def send_message_web():
    message = request.form['message']
    chat_app_info = session['chat_app']
    chat_app = ChatApp(chat_app_info['user_queue'], chat_app_info['partner_queue'])
    chat_app.send_message(chat_app_info['partner_queue'], message)
    return '', 204

@app.route('/load_chat_history', methods=['POST'])
def load_chat_history():
    data = request.json
    sender = data.get('sender')
    receiver = data.get('receiver')

    if 'chat_app' not in session:
      partner_queue = request.args.get('partner_queue')
      session['chat_app'] = ChatApp("Thinkpad", partner_queue)
    
    chat_app = session['chat_app']
    # Fetch chat history from Cassandra
    messages = []

    # Query for messages sent from the current user to the partner
    query_sent = "SELECT * FROM messages WHERE sender = %s AND receiver = %s ALLOW FILTERING"
    rows_sent = chat_app.session.execute(query_sent, (sender, receiver))

    # Query for messages sent from the partner to the current user
    query_received = "SELECT * FROM messages WHERE sender = %s AND receiver = %s ALLOW FILTERING"
    rows_received = chat_app.session.execute(query_received, (receiver, sender))

    # Add messages sent from the current user to the partner
    for row in rows_sent:
        messages.append({'sender': row.sender, 'receiver': row.receiver, 'message': row.message, 'timestamp': row.timestamp, 'is_sender': True})

    # Add messages sent from the partner to the current user
    for row in rows_received:
        messages.append({'sender': row.sender, 'receiver': row.receiver, 'message': row.message, 'timestamp': row.timestamp, 'is_sender': False})

    # Sort messages by timestamp
    messages.sort(key=lambda x: x['timestamp'])

    # Render messages as HTML and return
    return render_template('messages.html', messages=messages, current_user=chat_app.user_queue)
    #return jsonify(html=rendered_messages)


def run_web_interface():
    app.run(host='0.0.0.0', port=5000, threaded=False)

if __name__ == '__main__':
    # queue_name = input('Enter queue name: ')
   # partner_queue = input('Enter partner queue name: ')

    #chat_app = ChatApp("Thinkpad", partner_queue)
    #chat_app = ChatApp("a","b")
    web_thread = threading.Thread(target=run_web_interface)
    web_thread.start()

    while True:
        message = input('Enter message: ')
        #chat_app.send_message(partner_queue, message)

