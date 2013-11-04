import argparse

def parse(is_receiver):
    parser = argparse.ArgumentParser()
    parser.add_argument('filename',  help='name of file being transferred')
    if is_receiver:
        parser.add_argument('listening_port', help='listening port ', type=int)
    parser.add_argument('remote_ip',  help='remote host')
    parser.add_argument('remote_port', help='remote port ', type=int)
    if not is_receiver:
        parser.add_argument('ack_port', help='ack port ', type=int)
        parser.add_argument('window_size', help='window size', type=int)
    parser.add_argument('log_filename',   help='name of log file being transferred')
    return parser.parse_args()
