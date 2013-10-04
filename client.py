import argparse, socket, sys, json, thread

BUFFER_SIZE = 1024

def blocked():
    print "You have been blocked from logging in for 60 seconds"

def connect(sock, host, port):
    sock.connect((host, port))

    # first check if machine is blocked 
    sock.send("is_blocked")
    access = json.loads(sock.recv(BUFFER_SIZE))
    if access['is_blocked']:
        blocked()
        return

    # submit credentials for access
    while not access['is_granted']:
        user = raw_input("Username: ")
        pwd  = raw_input("Password: ")
        sock.sendall(json.dumps({
            'user': user,
            'pwd' : pwd,
        }))
        access = json.loads(sock.recv(BUFFER_SIZE))
        if not access['is_granted']:
            print "access denied. bad username or password"
            continue
        if access['is_blocked']:
            blocked()
            return

    print "access granted. welcome."

    # spawn thread to handle receiving all server communication
    # thread required bc server can broadcast to client w/out client talking to server
    thread.start_new_thread(recv_thread, (sock,))

    while True:
        # prompt user for input
        prompt = raw_input().strip()
        if not prompt:
            continue # there wasn't any cmd input

        # extract command and args from user input
        split = prompt.split(' ',1)
        request = { 'cmd': split[0] }
        if len(split) > 1:
            request['args'] = split[1]

        # send command + args to server
        sock.sendall(json.dumps(request))

def recv_thread(sock):
    while True:
        # when socket is closed, destroy thread
        if not sock: return
        # await comm. from server
        response = json.loads(sock.recv(BUFFER_SIZE))
        if 'echo' in response:
            print response['echo']


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'host', 
        help='the host name the client will attempt to connect to',
    )
    parser.add_argument(
        'port', 
        help='the port the server will listen on',
        type=int,
    )
    # TODO validate host and port

    args = parser.parse_args()

    # conditionally resolve localhost
    if args.host == "localhost":
        host = socket.gethostbyname(args.host) 
    else:
        host = args.host 

    # instatiate socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print "attempting to connect on {0}:{1}".format(host, args.port)
    connect(sock, host, args.port)

    # when connect returns, close socket
    sock.close()
