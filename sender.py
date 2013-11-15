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
# TODO close socket?
