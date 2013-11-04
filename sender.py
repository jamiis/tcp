import socket
from argz import parse
from tcp_socket import TcpSocket

arg = parse(is_receiver=False)
data = open(arg.filename).read()
sock = TcpSocket(
    window_size  = arg.window_size,
    log_filename = arg.log_filename,
    ack_port     = arg.ack_port,
)
host = arg.remote_ip if arg.remote_ip != 'localhost' else socket.gethostbyname(arg.remote_ip)
sock.connect((host, arg.remote_port))
sock.sendall(data)
# TODO close socket?
