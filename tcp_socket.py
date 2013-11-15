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
MIN_TIMEOUT = .05
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
        self.source = port
        self.logger.log('bound to: {0}:{1}'.format(host, port))
        # set address being transmitted to
        if remote[0].lower() == 'localhost':
            remote[0] = gethostbyname(gethostname())
        self.remote = tuple(remote)
        # set window size for SR protocol
        self.window_size = window

    def __getattr__(self,name):
        return getattr(self.s, name)

    def recv(self): 
        # reset a few variables before receiving
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
                self.logger.log(
                    'source: {0}, destination: {1}, seqnum: {2}, acknum: {3}, eof: {4}'.format(
                    src, dst, seqnum, acknum, eof)
                )
                # if this is the last packet (aka highest sequence number)
                if eof: 
                    # mark buffered packet as last
                    self.received[seqnum]['is_last'] = True
                    # strip null characters from end of last packet
                    if data[-1] == '\x00': 
                        data = data.rstrip('\x00')
                # is checksum is bad, drop packet
                if checksum != self.get_checksum([seqnum, acknum, fin, eof, data]):
                    # NOTE: I have decided *not* log bad checksums. the assignment didn't
                    #       specify what to do. I could have if I wanted to with the code below:
                    # self.logger.log('bad checksum!')
                    continue
                self.rcvd(data, seqnum)
        self.logger.log('file received successfully')
        # pass data up from transport layer to application layer
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
        # set source and destination ports
        src = self.source
        dst = self.remote[1]
        # this is an ack packet so these flags and data can be arbitrary
        seqnum = -1; fin = False; eof = False; data = '';
        # pack into struct
        packet = self.segment.pack(
            src, dst, seqnum, acknum, 
            SEGMENT_HEADER_SIZE, '', 
            fin, eof, '', data
        )
        # send ack across the wire
        self.s.sendto(packet, self.remote)

    def transmit_packet(self, seqnum):
        # set all tcp header and data values
        pos = (seqnum-self.start_base)
        pos_bytes = pos*SEGMENT_DATA_SIZE
        data = self.data[pos_bytes : pos_bytes + SEGMENT_DATA_SIZE]
        src = self.source
        dst = self.remote[1]
        fin = False
        eof = False if pos != self.num_packets - 1 else True
        # not an ack packet so set acknum to -1
        acknum = -1 
        checksum = self.get_checksum([seqnum, acknum, fin, eof, data])
        # pack tcp header and data into struct
        packet = self.segment.pack(
            src, dst, seqnum, acknum, 
            SEGMENT_HEADER_SIZE, checksum, 
            fin, eof, '', data
        )
        # send binary data across the wire
        self.s.sendto(packet, self.remote)
        # mark packet as having been transmitted
        p = self.transmitted[seqnum]
        p['has_transmitted'] = True
        p['time'] = datetime.now()
        # calculate and set new timeout
        p['timeout'] = self.get_timeout(p['timeout'])
        # start timeout timer for retransmitting packet
        Timer(p['timeout'], self.retransmit_packet, [seqnum]).start()

    def get_timeout(self, t_old):
        '''calculates timeout for a packet based on previous timeout and most recent rtt'''
        t_new = 0.25 * t_old + 0.75 * self.rtt
        if t_new < MIN_TIMEOUT:
            t_new = MIN_TIMEOUT
        return t_new

    def retransmit_packet(self, seqnum):
        '''retransmit packet unless the packet has been acked'''
        if not self.acked[seqnum]:
            self.transmit_packet(seqnum)

    def send_untransmitted(self):
        '''transmits all packets in the window that have not been transmitted. 
        packets that have not been acked but have already been transmitted will 
        be retransmitted when their timer runs out.'''
        for p in self.get_window():
            if not self.transmitted[p]['has_transmitted']:
                self.transmit_packet(p)

    def sendall(self, data):
        '''send data across the wire to self.remote over tcp'''
        # set/reset some variables before beginning transmission
        self.data = data
        self.is_finished = False
        self.num_packets = len(self.data) / SEGMENT_DATA_SIZE
        if len(self.data) % SEGMENT_DATA_SIZE: 
            self.num_packets += 1
        # these are used for easing certain calculations later
        self.start_base = self.base
        self.last_base = self.base + self.num_packets
        # self.logger.log('total number of packets needed: {0}'.format(self.num_packets))

        # sending the untransmitted will send the packets in the window and start 
        # timer threads which will handle sending all future packets not yet in the window
        self.send_untransmitted()

        # start looking for incoming acks
        while not self.is_finished:
            # receive data struct and unpack into variables
            ack_data, addr = self.s.recvfrom(SEGMENT_SIZE)
            src, dst, seqnum, acknum, headlen, checksum, fin, eof, unused, data = \
                self.segment.unpack(ack_data)
            # make sure packet is an ack
            if acknum >= 0:
                # update round trip time
                self.rtt = (datetime.now() - self.transmitted[acknum]['time']).total_seconds()
                # log received ack
                self.logger.log(
                    'source: {0}, destination: {1}, seqnum: {2}, acknum: {3}, eof: {4}, rtt: {5}'.format(
                    src, dst, seqnum, acknum, eof, self.rtt)
                )
                # mark packet as acked
                self.ack(acknum)

        # at this point, the file has been transmitted successfully
        self.logger.log('file sent successfully')

    def ack(self, acknum):
        self.acked[acknum] = True
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

    def get_window(self):
        lower = self.base
        upper = self.base + self.window_size
        # make sure upper doesn't exceed the last base sequence number
        if upper > self.last_base:
            upper =  self.last_base
        return range(lower, upper)


class Logger(Thread):
    '''specialized logger that will log to a filename or, if filename is 'stdout'
    will print to stdout. also, uses locks to ensure there aren't race conditions'''
    lock = Lock()

    def __init__(self, filename):
        super(Logger, self).__init__()
        self.is_stdout = filename == STDOUT 
        if not self.is_stdout:
            # will erase contents of filename if filename exists
            self.f = open(filename, 'w')

    def log(self, msg):
        with self.lock:
            msg = '{0}, {1}'.format(datetime.now(), msg)
            # if stdout, print to console
            if self.is_stdout:
                print msg
            else:
                self.f.write(msg + '\n')

    def close(self):
        if not self.is_stdout:
            self.f.close()
