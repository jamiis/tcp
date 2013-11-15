from argz import parse
import socket
from tcp_socket import TcpSocket

arg = parse(is_receiver=True)

sock = TcpSocket(
    remote = [arg.remote_ip, arg.remote_port],
    port   = arg.listening_port,
    log    = arg.log_filename,
)

data = sock.recv()
open(arg.filename, 'w').write(data)
