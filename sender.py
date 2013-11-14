import socket
from argz import parse
from tcp_socket import TcpSocket

arg = parse(is_receiver=False)
data = open(arg.filename).read()
sock = TcpSocket(
    remote = [arg.remote_ip, arg.remote_port],
    port   = arg.ack_port,
    log    = arg.log_filename,
    window = arg.window_size,
)
sock.sendall(data)
# TODO host = arg.remote_ip if arg.remote_ip != 'localhost' else socket.gethostbyname(arg.remote_ip)
# TODO sock.connect((host, arg.remote_port))
# TODO close socket?
