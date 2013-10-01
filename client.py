import argparse, ipaddress, socket, sys

if __name__ == '__main__':
    print 'creating client socket'
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

