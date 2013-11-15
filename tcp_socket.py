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
INITIAL_RTT = 1.0
INITIAL_TIMEOUT = 1.0
MIN_TIMEOUT = .1
STDOUT = 'stdout'

class TcpSocket(object):
    """
    TCP implemented on top of UDP via selective repeat protocol.
    Congestion and flow control not implemented.
    """

    # round trip time will be set every time ACK received
    rtt = INITIAL_RTT

    # segment represents a packet. tcp header + chunk of data.
    segment = struct.Struct(SEGMENT_FORMAT)

    # for sending #
    base = 0  # selective-repeat window base
    acked = defaultdict(lambda: False)
    transmitted = defaultdict(lambda: {
        'has_transmitted' : False,
        'timeout'         : INITIAL_TIMEOUT,
        'time'            : 0,
    })
    # for receiving #
    received = defaultdict(lambda: {
        'is_buffered' : False, # has packet been received?
        'is_last'     : False, # is this packet the last packet?
        'buffer'      : '',    # buffered data (if is_buffered)
    })

    def __init__(self, remote, port, log, window=10):
        # get that logger setup so we can start using it pronto!
        self.logger = Logger(log)
        # not using inheritance bc of python's odd wrapper for socket.socket
        self.s = socket(AF_INET, SOCK_DGRAM)
        # listen at this address
        host = gethostbyname(gethostname())
        self.s.bind((host, port))
        self.logger.log('listening on: {0}:{1}'.format(host, port))
        # set address being transmitted to
        if remote[0].lower() == 'localhost':
            remote[0] = gethostbyname(gethostname())
        self.remote = tuple(remote)
        # set window size for SR protocol
        self.window_size = window

    def __getattr__(self,name):
        return getattr(self.s, name)

    """ TODO do I need?
    def accept():
        sock = self.__init__()
        sock.addr = self.addr
        return sock
    """

    ''' TODO remove
    def set_remote_addr(self, addr):
        # TODO
        self.addr = addr
        self.ack_addr = (addr[0], self.ack_port)

    TODO fix this?
    def bind(self, addr):
        # TODO self.setup_addr(addr)
        self.s.bind(self.addr)
        self.logger.log('listening on: {0}'.format(self.addr))
    def connect(self, addr):
        self.setup_addr(addr)
        self.ack_sock.bind(self.ack_addr)
    '''

    def recv(self): 
        # TODO ask TA how to handle removing null chars on last packet.
        #      will any data files contain null characters?
        # TODO need to checksum over data *and* header?
        # TODO EOF condition? need to exit the while loop?
        # TODO check if seqnum in_window?
        # TODO properly log corrupt packets instead of just 'bad check'
        # TODO need this? if data[-1] == '\x00': 

        self.data = ''
        self.is_finished = False

        # loop until the data has finished transmitting
        while not self.is_finished:
            # receive and unpack packet
            r, addr = self.s.recvfrom(SEGMENT_SIZE)
            src, dst, seqnum, acknum, headlen, checksum, fin, eof, unused, data = \
                self.segment.unpack(r)
            # make sure packet isn't an ack packet
            if acknum == -1:
                self.logger.log('received packet {0} from: {1}'.format(seqnum, addr))
                # if this is the last packet (aka highest sequence number)
                if eof: 
                    # mark buffered packet as last
                    self.received[seqnum]['is_last'] = True
                    # strip null characters
                    data = data.rstrip('\x00')
                # is checksum is bad, drop packet
                if checksum != self.get_checksum([seqnum, acknum, fin, eof, data]):
                    import pdb; pdb.set_trace();
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
                    # if delivering last packet, mark transmission as finished
                    if self.received[self.base]['is_last']:
                        self.is_finished = True
                    # append buffered data
                    self.data += self.received[self.base]['buffer']
                    self.base += 1

    def get_checksum(self, data):
        st = '';
        for v in data: 
            st += str(v)
        return md5(st).digest()[:2]

    def transmit_ack(self, acknum):
        # TODO change src and dst
        # TODO need checksum?
        src = 0; dst = 0; seqnum = -1;
        fin = False; eof = False; data = '';
        packet = self.segment.pack(
            src, dst, seqnum, acknum, 
            SEGMENT_HEADER_SIZE, '', 
            fin, eof, '', data
        )
        self.s.sendto(packet, self.remote)
        self.logger.log('ack {0} sent to: {1}'.format(acknum, self.remote))

    def transmit_packet(self, seqnum):
        # TODO need to checksum over data *and* header? yes
        # TODO check if 'pos' goes over end of data
        # TODO adjust timeout value as per tcp standard, see: piazza
        # TODO fix srcport and dstport
        pos = (seqnum-self.start_base)
        pos_bytes = pos*SEGMENT_DATA_SIZE
        data = self.data[pos_bytes : pos_bytes + SEGMENT_DATA_SIZE]
        # TODO change src and dst
        src = 1111; dst = 2222; fin = False;
        eof = False if pos != self.num_packets - 1 else True
        acknum = -1 # -1 means field isn't needed
        checksum = self.get_checksum([seqnum, acknum, fin, eof, data])

        packet = self.segment.pack(
            src, dst, seqnum, acknum, 
            SEGMENT_HEADER_SIZE, checksum, 
            fin, eof, '', data
        )

        self.s.sendto(packet, self.remote)
        # mark packet as having been transmitted
        p = self.transmitted[seqnum]
        p['has_transmitted'] = True
        p['time'] = datetime.now()
        # calculate and set new timeout
        p['timeout'] = self.get_timeout(p['timeout'])
        Timer(p['timeout'], self.retransmit_packet, [seqnum]).start()

        self.logger.log('sent packet {0} to {1}'.format(seqnum, self.remote))

    def get_timeout(self, t_old):
        t_new = 0.25 * t_old + 0.75 * self.rtt
        if t_new < MIN_TIMEOUT:
            t_new = MIN_TIMEOUT
        self.logger.log('timeout: {0}'.format(t_new))
        return t_new

    def retransmit_packet(self, seqnum):
        if not self.acked[seqnum]:
            self.transmit_packet(seqnum)

    def send_untransmitted(self):
        '''transmits all packets in the window that have not been transmitted'''
        for p in self.get_window():
            if not self.transmitted[p]['has_transmitted']:
                self.transmit_packet(p)

    def sendall(self, data):
        self.data = data
        self.is_finished = False
        self.num_packets = len(self.data) / SEGMENT_DATA_SIZE
        if len(self.data) % SEGMENT_DATA_SIZE: 
            self.num_packets += 1
        # these are used for easing certain calculations later
        self.start_base = self.base
        self.last_base = self.base + self.num_packets

        self.logger.log('total number of packets needed: {0}'.format(self.num_packets))

        self.send_untransmitted()
        self.recv_acks()

    def recv_acks(self):
        # TODO closing connection needs to be done on application layer
        while not self.is_finished:
            ack_data, addr = self.s.recvfrom(SEGMENT_SIZE)
            src, dst, seqnum, acknum, headlen, checksum, fin, eof, unused, data = \
                self.segment.unpack(ack_data)
            # check if ack packet
            if acknum >= 0:
                # update round trip time
                self.rtt = (datetime.now() - self.transmitted[acknum]['time']).total_seconds()
                self.logger.log('new RTT: {0}'.format(self.rtt))
                self.logger.log('received ack {0} from: {1}'.format(acknum, addr))
                self.ack(acknum)
        self.logger.log('file sent successfully')
        # TODO sending FINs and closing needs to be moved to application layer!
        #self.close_conn()

    def ack(self, acknum):
        self.acked[acknum] = True
        self.logger.log('acked: {0}'.format(acknum))
        if acknum == self.base:
            #move base until next un-acked packet'''
            while self.acked[self.base]:
                # if all packets have been acked, marked transmission as finished
                if self.base == self.last_base -1:
                    self.is_finished = True
                self.base += 1
            # if transmission isn't finished, retransmit packets
            if not self.is_finished:
                self.send_untransmitted()

    def get_upper_window(self):
        upper = self.base + self.window_size
        if upper > self.last_base:
            upper =  self.last_base
        return upper

    def get_window(self):
        lower = self.base
        upper = self.get_upper_window()
        return range(lower, upper)

    # TODO not used:
    def in_window(self, seqnum):
        lower = self.base
        upper = self.get_upper_window()
        return seqnum >= lower and seqnum < upper

    def send_fin(self):
        # TODO remove?
        if not self.closed:
            fin = struct.pack('i', 1)
            self.s.sendto(fin, self.remote)
            Timer(TIMEOUT, send_fin)

    def close_conn():
        '''notify receiver that transmission is done via FIN and close connection'''
        # TODO
        send_fin()
        while True:
            ack_data = self.s.recv(SEGMENT_SIZE)
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
