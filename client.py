import pika

def receive_callback(ch, method, properties, body):
    print(f"Received message: {body.decode()}")

def main():
    connection = pika.BlockingConnection(pika.ConnectionParameters('192.168.1.70'))
    channel = connection.channel()

    channel.queue_declare(queue='chat_queue')

    channel.basic_consume(queue='chat_queue', on_message_callback=receive_callback, auto_ack=True)

    print('Waiting for messages. To exit press CTRL+C')
    channel.start_consuming()

if __name__ == '__main__':
    main()
