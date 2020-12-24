import hashlib
import json
import logging
import os
import pickle
import traceback
import gevent
import time
import numpy as np
from gevent import monkey, Greenlet
from gevent.event import Event
from gevent.queue import Queue
from collections import namedtuple
from enum import Enum
from mulebft.core.hsfastpath import hsfastpath
from mulebft.core.twovalueagreement import twovalueagreement
from dumbobft.core.validatedcommonsubset import validatedcommonsubset
from dumbobft.core.provablereliablebroadcast import provablereliablebroadcast
from dumbobft.core.dumbocommonsubset import dumbocommonsubset
from honeybadgerbft.core.honeybadger_block import honeybadger_block
from crypto.threshsig.boldyreva import serialize, deserialize1
from crypto.threshsig.boldyreva import TBLSPrivateKey, TBLSPublicKey
from crypto.ecdsa.ecdsa import PrivateKey
from honeybadgerbft.core.commoncoin import shared_coin
from honeybadgerbft.exceptions import UnknownTagError
from crypto.ecdsa.ecdsa import ecdsa_sign, ecdsa_vrfy, PublicKey


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

def hash(x):
    return hashlib.sha256(pickle.dumps(x)).digest()


class BroadcastTag(Enum):
    FAST = 'FAST'

BroadcastReceiverQueues = namedtuple(
    'BroadcastReceiverQueues', ('FAST',))


def broadcast_receiver_loop(recv_func, recv_queues):
    while True:
        gevent.sleep(0)
        sender, (tag, j, msg) = recv_func()
        if tag not in BroadcastTag.__members__:
            raise UnknownTagError('Unknown tag: {}! Must be one of {}.'.format(
                tag, BroadcastTag.__members__.keys()))
        recv_queue = recv_queues._asdict()[tag]
        try:
            recv_queue.put_nowait((sender, msg))
        except AttributeError as e:
            print("error", sender, (tag, j, msg))
            traceback.print_exc()


class Hotstuff():
    """Mule object used to run the protocol

    :param str sid: The base name of the common coin that will be used to
        derive a nonce to uniquely identify the coin.
    :param int pid: Node id.
    :param int Bfast: Batch size of transactions.
    :param int Bacs: Batch size of transactions.
    :param int N: Number of nodes in the network.
    :param int f: Number of faulty nodes that can be tolerated.
    :param TBLSPublicKey sPK: Public key of the (f, N) threshold signature.
    :param TBLSPrivateKey sSK: Signing key of the (f, N) threshold signature.
    :param TBLSPublicKey sPK1: Public key of the (N-f, N) threshold signature.
    :param TBLSPrivateKey sSK1: Signing key of the (N-f, N) threshold signature.
    :param list sPK2s: Public key(s) of ECDSA signature for all N parties.
    :param PrivateKey sSK2: Signing key of ECDSA signature.
    :param str ePK: Public key of the threshold encryption.
    :param str eSK: Signing key of the threshold encryption.
    :param send:
    :param recv:
    :param K: a test parameter to specify break out after K epochs
    """

    def __init__(self, sid, pid, S, Bfast, N, f, sPK, sSK, sPK1, sSK1, sPK2s, sSK2, ePK, eSK, send, recv, K=3, mute=False):

        self.SLOTS_NUM = S
        self.TIMEOUT = 10000
        self.FAST_BATCH_SIZE = Bfast

        self.sid = sid
        self.id = pid
        self.N = N
        self.f = f
        self.sPK = sPK
        self.sSK = sSK
        self.sPK1 = sPK1
        self.sSK1 = sSK1
        self.sPK2s = sPK2s
        self.sSK2 = sSK2
        self.ePK = ePK
        self.eSK = eSK
        self._send = send
        self._recv = recv
        self.logger = set_consensus_log(pid)
        self.transaction_buffer = Queue()
        self._per_epoch_recv = {}  # Buffer of incoming messages

        self.K = K

        self.s_time = 0
        self.e_time = 0

        self.txcnt = 0
        self.txdelay = 0

        self.mute = mute

    def submit_tx(self, tx):
        """Appends the given transaction to the transaction buffer.

        :param tx: Transaction to append to the buffer.
        """
        self.transaction_buffer.put_nowait(tx)

    def run_bft(self):
        """Run the Mule protocol."""

        if self.mute:

            def send_blackhole(*args):
                pass

            def recv_blackhole(*args):
                while True:
                    gevent.sleep(1)
                    time.sleep(1)
                    pass

            seed = int.from_bytes(self.sid.encode('utf-8'), 'little')
            if self.id in np.random.RandomState(seed).permutation(self.N)[:int((self.N - 1) / 3)]:
                self._send = send_blackhole
                self._recv = recv_blackhole

        def _recv_loop():
            """Receive messages."""
            while True:
                gevent.sleep(0)
                try:
                    (sender, (r, msg)) = self._recv()
                    # Maintain an *unbounded* recv queue for each epoch
                    if r not in self._per_epoch_recv:
                        self._per_epoch_recv[r] = Queue()
                    # Buffer this message
                    self._per_epoch_recv[r].put_nowait((sender, msg))
                except:
                    continue

        self._recv_thread = Greenlet(_recv_loop)
        self._recv_thread.start()

        self.s_time = time.time()
        if self.logger != None:
            self.logger.info('Node %d starts to run at time:' % self.id + str(self.s_time))


        # For each epoch
        e = 0

        if e not in self._per_epoch_recv:
            self._per_epoch_recv[e] = Queue()

        def make_epoch_send(e):
            def _send(j, o):
                self._send(j, (e, o))
            return _send

        send_e = make_epoch_send(e)
        recv_e = self._per_epoch_recv[e].get

        self._run_epoch(e, send_e, recv_e)

        self.e_time = time.time()

        if self.logger != None:
            self.logger.info("node %d breaks in %f seconds with total delivered Txs %d and average delay %f" %
                             (self.id, self.e_time-self.s_time, self.txcnt, self.txdelay) )
        else:
            print("node %d breaks in %f seconds with total delivered Txs %d and average delay %f" %
                  (self.id, self.e_time-self.s_time, self.txcnt, self.txdelay)
                  )

    #
    def _run_epoch(self, e, send, recv):
        """Run one protocol epoch.

        :param int e: epoch id
        :param send:
        :param recv:
        """

        sid = self.sid
        pid = self.id
        N = self.N
        f = self.f

        epoch_id = sid + 'FAST' + str(e)
        hash_genesis = hash(epoch_id)

        fast_recv = Queue()  # The thread-safe queue to receive the messages sent to fast_path of this epoch

        recv_queues = BroadcastReceiverQueues(
            FAST=fast_recv,
        )
        recv_t = gevent.spawn(broadcast_receiver_loop, recv, recv_queues)

        def _setup_fastpath(leader):

            def fastpath_send(k, o):
                send(k, ('FAST', '', o))

            fast_thread = gevent.spawn(hsfastpath, epoch_id, pid, N, f, leader,
                                   self.transaction_buffer.get_nowait, None,
                                   self.SLOTS_NUM, self.FAST_BATCH_SIZE, self.TIMEOUT,
                                   hash_genesis, self.sPK1, self.sSK1, self.sPK2s, self.sSK2,
                                   fast_recv.get, fastpath_send, self.logger)

            return fast_thread

        # Start the fast path
        leader = e % N
        fast_thread = _setup_fastpath(leader)

        # Block to wait the fast path returns
        fast_thread.join()

        # Get the returned notarization of the fast path, which contains the combined Signature for the tip of chain
        try:
            notarization = fast_thread.get(block=False)
            notarized_block_hash, notarized_block_raw_Sig, (epoch_txcnt, weighted_delay) = notarization
            self.txdelay = (self.txcnt * self.txdelay + epoch_txcnt * weighted_delay) / (self.txcnt + epoch_txcnt)
            self.txcnt += epoch_txcnt
        except:
            pass
