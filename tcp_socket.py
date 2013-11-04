import struct
from socket import *
from hashlib import md5
from collections import defaultdict
from threading import Timer, Thread, Lock
from datetime import datetime

# tcp header format (20 bytes total, 4 bytes per row):
#   srcprt(2), dstprt(2), 
#   seqnum(4), 
#   acknum(4), 
#   headlen(2), checksum(2), 
#   fin(1), eof(1), unused(2)

SEGMENT_FORMAT = 'h h i i h 2s ? ? 2s 556s'
SEGMENT_SIZE = 576
SEGMENT_HEADER_SIZE = 20
SEGMENT_DATA_SIZE = SEGMENT_SIZE - SEGMENT_HEADER_SIZE
TIMEOUT = 1.0
STDOUT = 'stdout'

class TcpSocket(object):
    """
    TCP implemented on top of UDP via selective repeat protocol.
    Congestion and flow control not implemented.
    """

    # segment represents a packet. tcp header + chunk of data.
    segment = struct.Struct(SEGMENT_FORMAT)

    def __init__(self, ack_port, log_filename, window_size=10):
        # not using inheritance bc of python's odd wrapper for socket.socket
        self.window_size = window_size
        self.ack_port = ack_port
        self.s = socket(AF_INET, SOCK_DGRAM)
        self.ack_sock = socket(AF_INET, SOCK_DGRAM)
        self.logger = Logger(log_filename)

    def __getattr__(self,name):
        return getattr(self.s, name)

    """ TODO do I need?
    def accept():
        sock = self.__init__()
        sock.addr = self.addr
        return sock
    """

    def reset(self):
        '''Reset variables before transmitting or receiving a new file'''
        # for sending #
        self.acked = defaultdict(lambda: False)
        self.transmitted = defaultdict(lambda: False)
        # for receiving #
        self.received = defaultdict(lambda: {
            'is_buffered' : False, # has packet been received?
            'is_last'     : False, # is this packet the last packet?
            'buffer'      : '',    # buffered data (if is_buffered)
        })
        # for sending and receiving #
        self.data = '' # entire data file (don't confuse with other data vars below)
        self.base = 0  # selective-repeat window base
        self.is_finished = False # is the file done transmitting?

    def setup_addr(self, addr):
        self.addr = addr
        self.ack_addr = (addr[0], self.ack_port)

    def bind(self, addr):
        '''bind receiver to listen for transmissions'''
        self.setup_addr(addr)
        self.s.bind(self.addr)
        self.logger.log('listening on: {0}'.format(self.addr))

    def connect(self, addr):
        '''bind ack socket to listen for acks'''
        self.setup_addr(addr)
        self.ack_sock.bind(self.ack_addr)

    def recv(self): 
        # TODO ask TA how to handle removing null chars on last packet.
        #      will any data files contain null characters?
        # TODO need to checksum over data *and* header?
        # TODO EOF condition? need to exit the while loop?
        # TODO check if seqnum in_window?
        # TODO properly log corrupt packets instead of just 'bad check'
        # TODO need this? if data[-1] == '\x00': 
        self.reset()
        # loop until the data has finished transmitting
        while not self.is_finished:
            # receive and unpack packet
            r = self.s.recv(SEGMENT_SIZE)
            src, dst, seqnum, acknum, headlen, checksum, fin, eof, unused, data = \
                self.segment.unpack(r)
            # if this is the last packet (aka highest sequence number)
            if eof: 
                # mark buffered packet as last
                self.received[seqnum]['is_last'] = True
                # strip null characters
                data = data.rstrip('\x00')
            # is checksum is bad, drop packet
            if checksum != self.get_checksum([src, dst, seqnum, fin, eof, data]):
                self.logger.log('bad checksum!')
                continue
            self.rcvd(data, seqnum)
        self.logger.log('file received successfully')
        return self.data

    def rcvd(self, data, seqnum):
        self.transmit_ack(seqnum)
        if not self.received[seqnum]['is_buffered']:
            # store packet data, mark as buffered
            self.received[seqnum]['is_buffered'] = True
            self.received[seqnum]['buffer']      = data
            # if the sequence number is the same as the window base
            if seqnum == self.base:
                # deliver buffered packets, in-order, and move base
                while self.received[self.base]['is_buffered']:
                    self.data += self.received[self.base]['buffer']
                    self.base += 1
                    # if delivering last packet, mark transmission as finished
                    if self.received[seqnum]['is_last']:
                        self.is_finished = True

    def get_checksum(self, data):
        st = '';
        for v in data: 
            st += str(v)
        return md5(st).digest()[:2]

    def transmit_ack(self, seqnum):
        packet = struct.pack('i', seqnum)
        self.ack_sock.sendto(packet, self.ack_addr)
        self.logger.log('ack sent: {0}'.format(seqnum))

    def transmit_packet(self, seqnum):
        # TODO need to checksum over data *and* header? yes
        # TODO check if 'pos' goes over end of data
        # TODO adjust timeout value as per tcp standard, see: piazza
        # TODO fix srcport and dstport
        pos = seqnum*SEGMENT_DATA_SIZE
        data = self.data[pos:pos+SEGMENT_DATA_SIZE]
        src = 1111; dst = 2222; fin = False;
        eof = False if seqnum != self.num_packets - 1 else True
        acknum = -1 # -1 means field isn't needed
        checksum = self.get_checksum([src, dst, seqnum, fin, eof, data])

        packet = self.segment.pack(
            src, dst, seqnum, acknum, 
            SEGMENT_HEADER_SIZE, checksum, 
            fin, eof, '', data
        )

        self.s.sendto(packet, self.addr)
        self.transmitted[seqnum] = True
        self.logger.log('sent packet: {0}'.format(seqnum))
        Timer(TIMEOUT, self.retransmit_packet, [seqnum]).start()

    def retransmit_packet(self, seqnum):
        if not self.acked[seqnum]:
            self.transmit_packet(seqnum)

    def send_untransmitted(self):
        '''transmits all packets in the window that have not been transmitted'''
        for p in self.get_window():
            if not self.transmitted[p]:
                self.transmit_packet(p)

    def sendall(self, data):
        self.reset()
        self.data = data

        self.num_packets = len(self.data) / SEGMENT_DATA_SIZE
        if len(self.data) % SEGMENT_DATA_SIZE: 
            self.num_packets += 1

        self.logger.log('total number of packets needed: {0}'.format(self.num_packets))

        self.send_untransmitted()
        self.recv_acks()

    def recv_acks(self):
        # TODO closing connection needs to be done on application layer
        while not self.is_finished:
            ack_data = self.ack_sock.recv(SEGMENT_SIZE)
            seqnum, = struct.unpack('i', ack_data)
            if self.in_window(seqnum):
                self.ack(seqnum)
        self.logger.log('file sent successfully')
        # TODO sending FINs and closing needs to be moved to application layer!
        #self.close_conn()

    def ack(self, seqnum):
        self.acked[seqnum] = True
        self.logger.log('acked: {0}'.format(seqnum))
        if seqnum == self.base:
            #move base until next un-acked packet'''
            while self.acked[self.base]:
                self.base += 1
            # if all packets have been acked, marked transmission as finished
            if self.base == self.num_packets:
                self.is_finished = True
            else:
                self.send_untransmitted()

    def get_upper_window(self):
        upper = self.base + self.window_size
        if upper > self.num_packets:
            upper = self.num_packets
        return upper

    def get_window(self):
        lower = self.base
        upper = self.get_upper_window()
        return range(lower, upper)

    def in_window(self, seqnum):
        lower = self.base
        upper = self.get_upper_window()
        return seqnum >= lower and seqnum < upper

    def send_fin(self):
        # TODO remove?
        if not self.closed:
            fin = struct.pack('i', 1)
            self.ack_sock.sendto(fin, self.ack_addr)
            Timer(TIMEOUT, send_fin)

    def close_conn():
        '''notify receiver that transmission is done via FIN and close connection'''
        # TODO
        send_fin()
        while True:
            ack_data = self.ack_sock.recv(SEGMENT_SIZE)
            fin, = struct.unpack('i', ack_data)
            self.logger.log('fin ack received!: {0}'.format(seqnum))
            if fin: break
        self.logger.close()


class Logger(Thread):
    lock = Lock()

    def __init__(self, filename):
        super(Logger, self).__init__()
        self.is_stdout = filename == STDOUT 
        if not self.is_stdout:
            self.f = open(filename, 'w')

    def log(self, msg):
        with self.lock:
            msg = '{0} {1}'.format(datetime.now(), msg)
            if self.is_stdout:
                print msg
            else:
                self.f.write(msg + '\n')

    def close(self):
        if not self.is_stdout:
            self.f.close()
