from tcp_socket import TcpSocket
import argparse, socket, sys, json
from threading import Thread

def blocked():
    print "you have been blocked from logging in for 60 seconds"

def connect(sock):
    # first check if machine is blocked 
    sock.sendall("is_blocked")
    access = json.loads(sock.recv())
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
        access = json.loads(sock.recv())
        if access['is_blocked']:
            blocked()
            return
        elif not access['is_granted']:
            print "access denied. bad username or password"
            continue

    print "access granted. welcome."

    def proc_kill():
        sys.exit()

    # spawn thread to handle receiving all server communication
    # thread required bc server can broadcast to client w/out client talking to server
    # TODO thread.start_new_thread(send_thread, (sock,))
    # Thread(target=send_thread, args=(sock,)).run()
    send_thread(sock)

    while True:
        # when socket is closed, destroy thread
        if not sock: return
        # await comm. from server
        response = json.loads(sock.recv())
        if 'closing' in response:
            proc_kill()
        if 'echo' in response:
            print response['echo']

def send_thread(sock):
    while True:
        # prompt user for input
        # TODO try and do custom recv so that we can have '>' at the prompt
        prompt = raw_input('> ').strip()
        if not prompt:
            continue # there wasn't any cmd input

        # extract command and args from user input
        split = prompt.split(' ',1)
        request = { 'cmd': split[0] }
        if split[0] == 'kill':
            sys.exit()
        if len(split) > 1:
            request['args'] = split[1]

        # send command + args to server
        sock.sendall(json.dumps(request))

        response = json.loads(sock.recv())
        if 'closing' in response:
            sys.exit()
        if 'echo' in response:
            print response['echo']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('server_ip',  help='remote host')
    parser.add_argument('server_port', help='remote port ', type=int)
    parser.add_argument('filename',  help='name of file being transferred')
    parser.add_argument('listening_port', help='the port the server will listen on', type=int)
    parser.add_argument('remote_ip',  help='remote host')
    parser.add_argument('remote_port', help='remote port ', type=int)
    parser.add_argument('log_filename',   help='name of log file being transferred')
    arg = parser.parse_args()

    ''' TODO
    # conditionally resolve localhost
    if args.host == "localhost":
        host = socket.gethostbyname(args.host) 
    else:
        host = args.host 
    '''

    # instatiate socket
    sock = TcpSocket(
        remote = [arg.remote_ip, arg.remote_port],
        port   = arg.listening_port,
        log    = arg.log_filename,
    )
    # TODO print "attempting to connect on {0}:{1}".format(host, arg.port)
    connect(sock)

    # when connect returns, close socket
    # TODO sock.close()

if __name__ == '__main__':
    main()
