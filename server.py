import argparse, socket, sys, pprint
from thread import start_new_thread

commands = {
    'whoelse'  : whoelse,
    'wholasthr': wholasthr,
    'broadcast': broadcast,
}

def client_thread(c_socket, addr):
    while True:
        received = c_socket.recv(1024).strip()

        # extract cmd & args, validate, call corresponding fcn in commands
        parsed = received.split(' ',1)
        cmd = parsed[0]
        args = ''
        if len(parsed) > 1:
            args = parsed[1] 

        if cmd not in commands:
            c_socket.sendall("The command '{0}' is not supported".format(cmd))
        else:
            commands[cmd]

        # close connection
        print data
        if not data:
            break

        c_socket.sendall('Ok...' + data)

    print 'closing connection with: {0}:{1}'.format(addr[0], addr[1])
    c_socket.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'port', 
        help='the port the server will listen on',
        type=int,
    )
    args = parser.parse_args()

    # TODO validate port

    # establish listening socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print 'socket initialized'

    try:
        s.bind(('localhost', args.port))
    except socket.error, msg:
        print "an error occured binding the server socket. \
               error code: {0}, msg:{1}".format(msg[0], msg[1])
        sys.exit()

    s.listen(100)
    print 'socket listening'
    
    while 1:
        c_socket, addr = s.accept()
        print 'connected with: {0}:{1}'.format(addr[0], addr[1])

        start_new_thread(client_thread, (c_socket, addr))

    s.close()
