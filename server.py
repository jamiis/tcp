import argparse, sys, socket, json, thread
from tcp_socket import tcp_socket
from datetime import datetime

BUFFER_SIZE = 1024

def whoelse(sock, request):
    """
    echo list of all connected users to requesting client. 
    list will have no repeats even if a user is logged in multiple times.
    """
    users = set()
    for s in connections.values():
        users.add(s['user'])
    response = { "echo": "\n".join(users) }
    sock['conn'].sendall(json.dumps(response))

def wholasthr(sock, request):
    """echo unique list of users that logged-in within in the past hr"""
    users = set()
    for s in history:
        # if connection was made in the last hour
        if time_elapsed_leq(s['time'], datetime.utcnow(), 60*60):
            users.add(s['user'])
    response = { "echo": "\n".join(users) }
    sock['conn'].sendall(json.dumps(response))

def broadcast(sock, request):
    # notify user if no broadcast msg was included
    if 'args' not in request or request['args'] == "":
        response = { "echo": "please specify a message you would like to broadcast" }
        sock['conn'].sendall(json.dumps(response))
    # broadcast message to all connections
    response = { "echo": "<broadcast>: {0}".format(request['args']) }
    for s in connections.values():
        s['conn'].sendall(json.dumps(response))

def block_machine(sock):
    '''block logins attempts from ip for 60 seconds and close the connection'''
    ip = sock['addr'][0]
    print "blocking connections from {0} for 60 seconds".format(ip)
    blocked[ip] = { 'time': datetime.utcnow() }
    close(sock)

def is_blocked(sock):
    ip = sock['addr'][0]
    if ip in blocked:
        if time_elapsed_leq(blocked[ip]['time'], datetime.utcnow(), 60):
            return True
        # unblock ip. 60 seconds has elapsed since ip was blocked.
        del blocked[ip]
    return False

def close(sock):
    """close the socket with client port 'cport' and remove from 'connections'"""
    cport = sock['addr'][1]
    if cport not in connections:
        # socket has already closed
        return
    addr = sock['addr']
    print 'closing connection with: {0}:{1}'.format(addr[0], addr[1])
    sock['conn'].close()
    del connections[cport]

def time_elapsed_leq(start, end, elapsed):
    return (end - start).total_seconds() <= elapsed

def client_thread(sock):
    conn = sock['conn']
    addr = sock['addr']
    
    # client must gain access before allowed to submit cmds
    access = { 
        'is_granted': False,
        'is_blocked': is_blocked(sock),
    }

    # check right away if client is listed as blocked
    data = conn.recv(BUFFER_SIZE)
    if data != "is_blocked":
        return # the client cheated, so return and close conn
    conn.send(json.dumps(access))
    if is_blocked(sock): return

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
                # populate socket with login information
                sock['user'] = creds['user']
                sock['time'] = datetime.utcnow()
                sock['has_access'] = True
                break
            else:
                # client gave bad credentials
                if attempt == 3:
                    # block logins from this machine
                    access['is_blocked'] = True
                    conn.sendall(json.dumps(access))
                    #response = { "closing": True }
                    #sock['conn'].sendall(json.dumps(response))
                    block_machine(sock)
                    return
                else:
                    # notify client access was denied
                    print "access denied to client {0}:{1}"\
                        .format(addr[0],addr[1])
                    conn.sendall(json.dumps(access))

    # access granted to client at this point
    history.append(sock)

    while True:
        request = json.loads(conn.recv(BUFFER_SIZE))

        print "received request: {0} from {1}:{2}" \
            .format(request, addr[0], addr[1])

        # extract cmd, validate, call corresponding func
        cmd = request['cmd']
        if cmd == "exit": 
            response = { "closing": True }
            sock['conn'].sendall(json.dumps(response))
            close(sock)
            return
        if cmd not in commands:
            # notify client that this is not a valid cmd
            response = { "echo": "command '{0}' is not supported".format(cmd) }
            conn.sendall(json.dumps(response))
        else:
            # command is valid, so call into function
            commands[cmd](sock, request)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'port', 
        help='the port the server will listen on',
        type=int,
    )
    args = parser.parse_args()

    # TODO validate port

    # instatiate tcp socket
    sock = tcp_socket()

    print 'socket initialized'

    try:
        host = socket.gethostbyname(socket.gethostname())
        sock.bind((host, args.port))
    except socket.error, msg:
        print "an error occured binding the server socket. \
               error code: {0}, msg:{1}".format(msg[0], msg[1])
        sys.exit()

    # TODO can this be commented out? sock.listen(100)

    print 'socket listening on {0}:{1}'.format(host, args.port)
    
    while True:
        conn, addr = sock.accept()
        # 'sock' dict will replace sock socket. 
        # only adds information, does not delete info.
        s = {
            'conn'      : conn, 
            'addr'      : addr,
            'time'      : None, # filled in when user logs in
            'user'      : None, # ditto
            'has_access': False,
        }
        # the client port is a unique id for this connection
        cport = addr[1]
        # add conn info to conns dict
        connections[cport] = s
        # spawn thread to handle connection
        thread.start_new_thread(client_thread, (s,))

    close(s)
    #sock.close()

commands = {
    'whoelse'  : whoelse,
    'wholasthr': wholasthr,
    'broadcast': broadcast,
}

# keep track of all clients connected
# dict keys will be client port numbers
connections = {}

# keep an historical account of every connection. would have used 'connections' variable
# but client port numbers are eventually recycled which would have caused problems
history = []

# maintain dict of blocked ip addresses
blocked = {}

# the usernames and passwords of those allowed to login
# (*obviously* unsecure)
f = open('allowed', 'r')
allowed = {}
for line in f:
    [user, pwd] = line.strip().split(" ")
    allowed[user] = pwd

if __name__ == '__main__':
    main()
