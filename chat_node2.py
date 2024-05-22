from flask import Flask, render_template, request, redirect, url_for, session
import pika
import threading
import uuid
from datetime import datetime
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider

app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'

class ChatApp:
    # RabbitMQ connection parameters
    RABBITMQ_HOST = '192.168.1.70'
    RABBITMQ_PORT = 5672
    RABBITMQ_USERNAME = 'guest'
    RABBITMQ_PASSWORD = 'guest'

    def __init__(self, user_queue, partner_queue):
        self.user_queue = user_queue
        self.partner_queue = partner_queue
        self.credentials = pika.PlainCredentials(ChatApp.RABBITMQ_USERNAME, ChatApp.RABBITMQ_PASSWORD)
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=ChatApp.RABBITMQ_HOST, port=ChatApp.RABBITMQ_PORT, credentials=self.credentials))
        self.receiver_thread = threading.Thread(target=self.start_receiver, args=(user_queue, partner_queue))
        self.receiver_thread.start()
        
        cassandra_host = ['192.168.1.66', '192.168.1.70', '192.168.1.72']
        cassandra_port = 9042
        cassandra_username = 'AllowAllAuthenticator'
        cassandra_password = 'AllowAllAuthenticator'
        keyspace = 'chat_app'
        
        auth_provider = PlainTextAuthProvider(username=cassandra_username, password=cassandra_password)
        self.cluster = Cluster(contact_points=cassandra_host, port=cassandra_port, auth_provider=auth_provider)
        self.session = self.cluster.connect(keyspace)
        
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
        print(f"Received message: {body.decode()}")
        channel.basic_ack(delivery_tag=method.delivery_tag)

    def start_receiver(self, user_queue, partner_queue):
        def callback(ch, method, properties, body):
            self.clear_message(ch, method, properties, body)

            message = body.decode()
            if user_queue == 'group_chat':
                receiver = 'group_chat'
            else:
                receiver = partner_queue
            
            message_id = uuid.uuid4()
            timestamp = datetime.now()
            self.session.execute("""
                INSERT INTO messages (message_id, sender, receiver, message, timestamp)
                VALUES (%s, %s, %s, %s, %s)
            """, (message_id, user_queue, receiver, message, timestamp))

        connection = pika.BlockingConnection(pika.ConnectionParameters(host=ChatApp.RABBITMQ_HOST, port=ChatApp.RABBITMQ_PORT, credentials=self.credentials))
        self.channel = connection.channel()
        self.channel.queue_declare(queue=user_queue, durable=True)
        self.channel.queue_declare(queue='group_chat', durable=True)

        self.channel.basic_consume(queue=user_queue, on_message_callback=callback)
        self.channel.basic_consume(queue='group_chat', on_message_callback=callback)

        print(f" [*] Waiting for messages in {user_queue} and group_chat. To exit press CTRL+C")
        self.channel.start_consuming()

    def send_message(self, queue_name, message):
        channel = self.connection.channel()
        channel.queue_declare(queue=queue_name, durable=True)
        if queue_name == 'group_chat':
            channel.basic_publish(exchange='', routing_key='group_chat', body=message)
        else:
            channel.basic_publish(exchange='', routing_key=queue_name, body=message)
        
        print(f" [x] Sent '{message}'")

        message_id = uuid.uuid4()
        timestamp = datetime.now()
        self.session.execute("""
            INSERT INTO messages (message_id, sender, receiver, message, timestamp)
            VALUES (%s, %s, %s, %s, %s)
        """, (message_id, self.user_queue, queue_name, message, timestamp))

@app.route('/')
def nodes():
    return render_template('nodes.html')

@app.route('/message')
def message():
    node_id = request.args.get('node')
    partner_queue = ''  # Default value
    if node_id == 'node2':
        partner_queue = 'Alexis Mac'
    elif node_id == 'node3':
        partner_queue = 'Alvaro Asus'
    elif node_id == 'node4':
        partner_queue = 'Ulises VivoBook'
    elif node_id == 'group_chat':
        partner_queue = 'group_chat'

    if 'chat_app' not in session:
        session['chat_app'] = {}

    session['chat_app']['partner_queue'] = partner_queue

    return redirect(url_for('index', partner_queue=partner_queue))

@app.route('/index')
def index():
    messages = []
    partner_queue = request.args.get('partner_queue')
    if not partner_queue:
        partner_queue = session.get('partner_queue')

    if not partner_queue:
        return redirect(url_for('nodes'))

    chat_app_info = {
        'user_queue': "German Thinkpad",
        'partner_queue': partner_queue
    }

    chat_app = ChatApp(chat_app_info['user_queue'], chat_app_info['partner_queue'])

    session['chat_app'] = chat_app_info

    if partner_queue == 'group_chat':
        query = "SELECT * FROM messages WHERE receiver = 'group_chat' ALLOW FILTERING"
        rows = chat_app.session.execute(query)

        for row in rows:
            is_sender = (row.sender == chat_app_info['user_queue'])
            messages.append({'sender': row.sender, 'receiver': row.receiver, 'message': row.message, 'timestamp': row.timestamp, 'is_sender': is_sender})
    else:
        query_sent = "SELECT * FROM messages WHERE sender = %s AND receiver = %s ALLOW FILTERING"
        rows_sent = chat_app.session.execute(query_sent, (chat_app_info['user_queue'], chat_app_info['partner_queue']))

        query_received = "SELECT * FROM messages WHERE sender = %s AND receiver = %s ALLOW FILTERING"
        rows_received = chat_app.session.execute(query_received, (chat_app_info['partner_queue'], chat_app_info['user_queue']))

        for row in rows_sent:
            messages.append({'sender': row.sender, 'receiver': row.receiver, 'message': row.message, 'timestamp': row.timestamp, 'is_sender': True})

        for row in rows_received:
            messages.append({'sender': row.sender, 'receiver': row.receiver, 'message': row.message, 'timestamp': row.timestamp, 'is_sender': False})

    messages.sort(key=lambda x: x['timestamp'])

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
    messages = []

    query_sent = "SELECT * FROM messages WHERE sender = %s AND receiver = %s ALLOW FILTERING"
    rows_sent = chat_app.session.execute(query_sent, (sender, receiver))

    query_received = "SELECT * FROM messages WHERE sender = %s AND receiver = %s ALLOW FILTERING"
    rows_received = chat_app.session.execute(query_received, (receiver, sender))

    for row in rows_sent:
        messages.append({'sender': row.sender, 'receiver': row.receiver, 'message': row.message, 'timestamp': row.timestamp, 'is_sender': True})

    for row in rows_received:
        messages.append({'sender': row.sender, 'receiver': row.receiver, 'message': row.message, 'timestamp': row.timestamp, 'is_sender': False})

    messages.sort(key=lambda x: x['timestamp'])

    return render_template('messages.html', messages=messages, current_user=chat_app.user_queue)

def run_web_interface():
    app.run(host='0.0.0.0', port=5000, threaded=False)

if __name__ == '__main__':
    web_thread = threading.Thread(target=run_web_interface)
    web_thread.start()

    while True:
        message = input('Enter message: ')
