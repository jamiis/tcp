from argz import parse
import socket, thread
from tcp_socket import TcpSocket

arg = parse(is_receiver=True)

sock = TcpSocket(
    ack_port=arg.remote_port,
    log_filename = arg.log_filename,
)
# TODO pull remote ip
host = socket.gethostbyname(socket.gethostname())
sock.bind((host, arg.listening_port))

# TODO after recv data, write it to filename
while True:
    data = sock.recv()
    open(arg.filename, 'w').write(data)
