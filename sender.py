import socket
from argz import parse
from tcp_socket import TcpSocket

# parse command line arguments
arg = parse(is_receiver=False)

# load data from file into python
try:
    data = open(arg.filename).read()
except IOError as err:
    print("I/O error: {0}".format(err))
    raise

# create a new tcp socket
sock = TcpSocket(
    remote = [arg.remote_ip, arg.remote_port],
    port   = arg.ack_port,
    log    = arg.log_filename,
    window = arg.window_size,
)
# send data over tcp socket
sock.sendall(data)
