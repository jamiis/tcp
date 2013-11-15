from argz import parse
import socket
from tcp_socket import TcpSocket

# parse command line arguments
arg = parse(is_receiver=True)

# create a new tcp socket
sock = TcpSocket(
    remote = [arg.remote_ip, arg.remote_port],
    port   = arg.listening_port,
    log    = arg.log_filename,
)

# receive data on socket
data = sock.recv()
# once data is done trasferring, write it to a file
open(arg.filename, 'w').write(data)
