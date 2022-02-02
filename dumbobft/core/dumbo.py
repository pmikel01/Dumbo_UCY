import json
import logging
import os
import traceback, time
import gevent
import numpy as np
from collections import namedtuple
from enum import Enum
from gevent import monkey
from gevent.queue import Queue
from dumbobft.core.dumbocommonsubset import dumbocommonsubset
from dumbobft.core.provablereliablebroadcast import provablereliablebroadcast
from dumbobft.core.validatedcommonsubset import validatedcommonsubset
from honeybadgerbft.crypto.threshsig.boldyreva import serialize, deserialize1
from honeybadgerbft.crypto.threshsig.boldyreva import TBLSPrivateKey, TBLSPublicKey
from honeybadgerbft.core.honeybadger_block import honeybadger_block
from honeybadgerbft.exceptions import UnknownTagError

#monkey.patch_all(thread=False, socket=False)

def set_consensus_log(id: int):
    logger = logging.getLogger("consensus-node-"+str(id))
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '%(asctime)s %(filename)s [line:%(lineno)d] %(funcName)s %(levelname)s %(message)s ')
    if 'log' not in os.listdir(os.getcwd()):
        os.mkdir(os.getcwd() + '/log')
    full_path = os.path.realpath(os.getcwd()) + '/log/' + "consensus-node-"+str(id) + ".log"
    file_handler = logging.FileHandler(full_path)
    file_handler.setFormatter(formatter)  # 可以通过setFormatter指定输出格式
    logger.addHandler(file_handler)
    return logger


class BroadcastTag(Enum):
    ACS_PRBC = 'ACS_PRBC'
    ACS_VACS = 'ACS_VACS'
    TPKE = 'TPKE'


BroadcastReceiverQueues = namedtuple(
    'BroadcastReceiverQueues', ('ACS_PRBC', 'ACS_VACS', 'TPKE'))


def broadcast_receiver(recv_func, recv_queues):
    sender, (tag, j, msg) = recv_func()
    if tag not in BroadcastTag.__members__:
        # TODO Post python 3 port: Add exception chaining.
        # See https://www.python.org/dev/peps/pep-3134/
        raise UnknownTagError('Unknown tag: {}! Must be one of {}.'.format(
            tag, BroadcastTag.__members__.keys()))
    recv_queue = recv_queues._asdict()[tag]

    if tag == BroadcastTag.ACS_PRBC.value:
        recv_queue = recv_queue[j]
    try:
        recv_queue.put_nowait((sender, msg))
    except AttributeError as e:
        print("error", sender, (tag, j, msg))
        traceback.print_exc(e)


def broadcast_receiver_loop(recv_func, recv_queues):
    while True:
        broadcast_receiver(recv_func, recv_queues)


class Dumbo():
    """Dumbo object used to run the protocol.

    :param str sid: The base name of the common coin that will be used to
        derive a nonce to uniquely identify the coin.
    :param int pid: Node id.
    :param int B: Batch size of transactions.
    :param int N: Number of nodes in the network.
    :param int f: Number of faulty nodes that can be tolerated.
    :param TBLSPublicKey sPK: Public key of the (f, N) threshold signature
        (:math:`\mathsf{TSIG}`) scheme.
    :param TBLSPrivateKey sSK: Signing key of the (f, N) threshold signature
        (:math:`\mathsf{TSIG}`) scheme.
    :param TBLSPublicKey sPK1: Public key of the (N-f, N) threshold signature
        (:math:`\mathsf{TSIG}`) scheme.
    :param TBLSPrivateKey sSK1: Signing key of the (N-f, N) threshold signature
        (:math:`\mathsf{TSIG}`) scheme.
    :param str ePK: Public key of the threshold encryption
        (:math:`\mathsf{TPKE}`) scheme.
    :param str eSK: Signing key of the threshold encryption
        (:math:`\mathsf{TPKE}`) scheme.
    :param send:
    :param recv:
    :param K: a test parameter to specify break out after K rounds
    """

    def __init__(self, sid, pid, B, N, f, sPK, sSK, sPK1, sSK1, ePK, eSK, send, recv, K=3, mute=False):
        self.sid = sid
        self.id = pid
        self.B = B
        self.N = N
        self.f = f
        self.sPK = sPK
        self.sSK = sSK
        self.sPK1 = sPK1
        self.sSK1 = sSK1
        self.ePK = ePK
        self.eSK = eSK
        self._send = send
        self._recv = recv
        self.logger = set_consensus_log(pid)
        self.round = 0  # Current block number
        self.transaction_buffer = Queue()
        self._per_round_recv = {}  # Buffer of incoming messages

        self.K = K

        self.s_time = 0
        self.e_time = 0
        self.txcnt = 0

        self.mute = mute

    def submit_tx(self, tx):
        """Appends the given transaction to the transaction buffer.
        :param tx: Transaction to append to the buffer.
        """
        #print('backlog_tx', self.id, tx)
        #if self.logger != None:
        #    self.logger.info('Backlogged tx at Node %d:' % self.id + str(tx))
        # Insert transactions to the end of TX buffer
        self.transaction_buffer.put_nowait(tx)

    def run_bft(self):
        """Run the Dumbo protocol."""

        if self.mute:

            def send_blackhole(*args):
                pass

            def recv_blackhole(*args):
                while True:
                    time.sleep(1)
                    pass

            seed = int.from_bytes(self.sid.encode('utf-8'), 'little')
            if self.id in np.random.RandomState(seed).permutation(self.N)[:int((self.N - 1) / 3)]:
                self._send = send_blackhole
                self._recv = recv_blackhole

        def _recv():
            """Receive messages."""
            while True:
                try:
                    (sender, (r, msg)) = self._recv()

                    # Maintain an *unbounded* recv queue for each epoch
                    if r not in self._per_round_recv:
                        self._per_round_recv[r] = Queue()

                    # Buffer this message
                    self._per_round_recv[r].put_nowait((sender, msg))
                except:
                    continue
                gevent.sleep(0)
                time.sleep(0)

        self._recv_thread = gevent.spawn(_recv)

        self.s_time = time.time()
        if self.logger != None: self.logger.info('Node %d starts to run at time:' % self.id + str(self.s_time))
        
        self.logger.info('BBB: %d ' % self.B)
        while True:
            # For each round...

            start = time.time()

            r = self.round
            if r not in self._per_round_recv:
                self._per_round_recv[r] = Queue()

            # Select B transactions (TODO: actual random selection)
            tx_to_send = []
            for _ in range(self.B):
                tx_to_send.append(self.transaction_buffer.get_nowait())

            self.logger.info('tx_to_send: %d ' % len(tx_to_send))
            

            def _make_send(r):
                def _send(j, o):
                    self._send(j, (r, o))
                return _send

            send_r = _make_send(r)
            recv_r = self._per_round_recv[r].get
            new_tx = self._run_round(r, tx_to_send, send_r, recv_r)
            # for x in new_tx:
                # self.logger.info(x)
            

            # print('new block at %d:' % self.id, new_tx)
            if self.logger != None:
                self.logger.info('new: %d ' % len(new_tx))
                # self.logger.info('Node %d Delivers Block %d: ' % (self.id, self.round) + str(new_tx))
                tx_cnt = str(new_tx).count("Dummy TX")
                self.txcnt += tx_cnt
                self.logger.info(
                'Node %d Delivers ACS Block in Round %d with having %d TXs' % (self.id, r, tx_cnt))

            end = time.time()

            if self.logger != None:
                self.logger.info('ACS Block Delay at Node %d: ' % self.id + str(end - start))

            # Put undelivered but committed TXs back to the backlog buffer
            #for _tx in tx_to_send:
            #    if _tx not in new_tx:
            #        self.transaction_buffer.put_nowait(_tx)

            # print('buffer at %d:' % self.id, self.transaction_buffer)
            #if self.logger != None:
            #    self.logger.info('Backlog Buffer at Node %d:' % self.id + str(self.transaction_buffer))

            self.round += 1     # Increment the round
            if self.round >= self.K:
                break   # Only run one round for now

        if self.logger != None:
            self.e_time = time.time()
            self.logger.info("node %d breaks in %f seconds with total delivered Txs %d" % (self.id, self.e_time-self.s_time, self.txcnt))
        else:
            print("node %d breaks" % self.id)


    #
    def _run_round(self, r, tx_to_send, send, recv):
        """Run one protocol round.

        :param int r: round id
        :param tx_to_send: Transaction(s) to process.
        :param send:
        :param recv:
        """
        # Unique sid for each round
        sid = self.sid + ':' + str(r)
        pid = self.id
        N = self.N
        f = self.f

        prbc_recvs = [Queue() for _ in range(N)]
        vacs_recv = Queue()
        tpke_recv = Queue()

        my_prbc_input = Queue(1)
        vacs_input = Queue(1)

        prbc_outputs = [Queue(1) for _ in range(N)]
        vacs_output = Queue(1)


        #print(pid, r, 'tx_to_send:', tx_to_send)
        #if self.logger != None: self.logger.info('Commit tx at Node %d:' % self.id + str(tx_to_send))

        def _setup_prbc(j):
            """Setup the sub protocols RBC, BA and common coin.

            :param int j: Node index for which the setup is being done.
            """

            def prbc_send(k, o):
                """Reliable send operation.
                :param k: Node to send.
                :param o: Value to send.
                """
                send(k, ('ACS_PRBC', j, o))

            # Only leader gets input
            prbc_input = my_prbc_input.get if j == pid else None
            prbc = gevent.spawn(provablereliablebroadcast, sid+'PRBC'+str(r)+str(j), pid, N, f, self.sPK1, self.sSK1, j,
                               prbc_input, prbc_recvs[j].get, prbc_send)
            prbc_outputs[j] = prbc.get  # block for output from rbc

        def _setup_vacs():

            def vacs_send(k, o):
                """Threshold encryption broadcast."""
                send(k, ('ACS_VACS', '', o))

            def vacs_predicate(j, vj):
                try:
                    sid, roothash, raw_Sig = vj
                    digest = self.sPK1.hash_message(str((sid, j, roothash)))
                    assert self.sPK1.verify_signature(deserialize1(raw_Sig), digest)
                    return True
                except AssertionError:
                    print("Failed to verify proof for RBC")
                    return False

            gevent.spawn(validatedcommonsubset, sid+'VACS'+str(r), pid, N, f, self.sPK, self.sSK, self.sPK1, self.sSK1,
                         vacs_input.get, vacs_output.put_nowait,
                         vacs_recv.get, vacs_send, vacs_predicate)

        # N instances of ABA, RBC
        for j in range(N):
            _setup_prbc(j)

        # One instance of (validated) ACS
        _setup_vacs()

        # One instance of TPKE
        def tpke_bcast(o):
            """Threshold encryption broadcast."""
            def broadcast(o):
                """Multicast the given input ``o``.

                :param o: Input to multicast.
                """
                for j in range(N):
                    send(j, o)
            broadcast(('TPKE', '', o))


        # One instance of ACS pid, N, f, prbc_out, vacs_in, vacs_out
        dumboacs = gevent.spawn(dumbocommonsubset, pid, N, f, prbc_outputs,
                           vacs_input.put_nowait,
                           vacs_output.get)

        recv_queues = BroadcastReceiverQueues(
            ACS_PRBC=prbc_recvs,
            ACS_VACS=vacs_recv,
            TPKE=tpke_recv,
        )
        gevent.spawn(broadcast_receiver_loop, recv, recv_queues)

        _input = Queue(1)
        _input.put(json.dumps(tx_to_send))

        _output = honeybadger_block(pid, self.N, self.f, self.ePK, self.eSK,
                          _input.get,
                          acs_in=my_prbc_input.put_nowait, acs_out=dumboacs.get,
                          tpke_bcast=tpke_bcast, tpke_recv=tpke_recv.get)

        self.logger.info('out: %d ' % len(_output))

        block = set()
        for batch in _output:
            decoded_batch = json.loads(batch.decode())
            self.logger.info('dec: %d ' % len(decoded_batch))
            for tx in decoded_batch:
                # if pid==0: self.logger.debug("tx: %s" % tx)
                block.add(tx)

        return list(block)

    # TODO： make help and callhelp threads to handle the rare cases when vacs (vaba) returns None
