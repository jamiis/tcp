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

    while True:
        # prompt user for input
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

    # instatiate socket
    sock = TcpSocket(
        remote = [arg.remote_ip, arg.remote_port],
        port   = arg.listening_port,
        log    = arg.log_filename,
    )
    connect(sock)

if __name__ == '__main__':
    main()
