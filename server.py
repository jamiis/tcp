import argparse, sys, socket, json, thread

BUFFER_SIZE = 1024

def whoelse(cport, request):
    print 'whoelse!!!'

def wholasthr(cport, request):
    print 'wholasthr!!!'

def broadcast(cport, request):
    # notify user if no broadcast msg was included
    if 'args' not in request or request['args'] == "":
        response = { "echo": "please specify a message you would like to broadcast" }
        connection = connections[cport]['conn']
        connection.sendall(json.dumps(response))
    # broadcast message to all connections
    response = { "echo": "<broadcast>: {0}".format(request['args']) }
    for port, sock_info in connections.iteritems():
        print port, sock_info, response
        sock_info['conn'].sendall(json.dumps(response))

commands = {
    'whoelse'  : whoelse,
    'wholasthr': wholasthr,
    'broadcast': broadcast,
}

# keep track of all clients connected
# dict keys will be client port numbers
connections = {}

# the usernames and passwords of those allowed to login
# (*obviously* unsecure)
# TODO must be a file
allowed = {
    'Columbia' : '116bway',
    'SEAS'     : 'summerisover',
    'csee4119' : 'lotsofexams',
    'foobar'   : 'passpass',
    'windows'  : 'withglass',
    'Google'   : 'hasglasses',
    'facebook' : 'wastingtime',
    'wikipedia': 'donation',
    'network'  : 'seemse',
}

def block_machine(conn, addr):
    ''' blocks logins from addr for 60 seconds and closes the connection '''
    print "blocking connections from {0} for 60 seconds".format(addr[0])
    # TODO store machine addr and current time in list of blocked addresses
    close_connection(conn, addr)

def is_blocked(conn, addr):
    # TODO
    return False

def close_connection(conn, addr):
    print 'closing connection with: {0}:{1}'.format(addr[0], addr[1])
    conn.close()

def client_thread(conn, addr):
    # client must gain access before allowed to submit cmds
    access = { 
        'is_granted': False,
        'is_blocked': is_blocked(conn, addr),
    }

    # check right away if client is listed as blocked
    data = conn.recv(BUFFER_SIZE)
    if data != "is_blocked":
        return # the client cheated, so return and close conn
    conn.send(json.dumps(access))

    # await submission of client credentials
    while not access['is_granted']:
        for attempt in [1,2,3]:
            creds = json.loads(conn.recv(BUFFER_SIZE))

            # verify client credentials
            if creds['pwd'] == allowed.get(creds['user'], False):
                # credentials passed, access granted
                print "access granted to client {0}:{1}" \
                    .format(addr[0],addr[1])
                access['is_granted'] = True
                conn.sendall(json.dumps(access))
                break
            else:
                # client gave bad credentials
                if attempt == 3:
                    # block logins from this machine
                    access['is_blocked'] = True
                    conn.sendall(json.dumps(access))
                    block_machine(conn, addr)
                    return
                else:
                    # notify client access was denied
                    print "access denied to client {0}:{1}"\
                        .format(addr[0],addr[1])
                    conn.sendall(json.dumps(access))

    # access granted to client at this point
    # the client port is a unique id for this connection
    cport = addr[1]
    # add conn info to conns dict
    connections[cport] = {
        'conn': conn, 
        'addr': addr,
        'time': 999, # TODO
        # TODO: do we need to store usernames to disallow signing
        #       in multiple times by unser one username?
    }

    while True:
        request = json.loads(conn.recv(BUFFER_SIZE))

        print "received request: {0} from {1}:{2}" \
            .format(request, addr[0], addr[1])

        # extract cmd, validate, call corresponding func
        cmd = request['cmd']
        if cmd == 'exit': 
            break
        if cmd not in commands:
            # notify client that this is not a valid cmd
            response = { "echo": "command '{0}' is not supported".format(cmd) }
            conn.sendall(json.dumps(response))
        else:
            # command is valid, so call into function
            commands[cmd](cport, request)

    if conn:
        close_connection(conn, addr)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'port', 
        help='the port the server will listen on',
        type=int,
    )
    args = parser.parse_args()

    # TODO validate port

    # instatiate socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    print 'socket initialized'

    try:
        host = socket.gethostbyname(socket.gethostname())
        sock.bind((host, args.port))
    except socket.error, msg:
        print "an error occured binding the server socket. \
               error code: {0}, msg:{1}".format(msg[0], msg[1])
        sys.exit()

    sock.listen(100)

    print 'socket listening on {0}:{1}'.format(host, args.port)
    
    while True:
        conn, addr = sock.accept()
        # spawn thread to handle connection
        thread.start_new_thread(client_thread, (conn, addr))

    if sock:
        print 'closing socket'
        sock.close()
