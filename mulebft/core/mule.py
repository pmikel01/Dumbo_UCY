import hashlib
import json
import pickle
import traceback
import gevent
import time
from gevent.queue import Queue
from collections import namedtuple, deque
from enum import Enum

from mulebft.core.fastpath import fastpath
from mulebft.core.twovalueagreement import twovalueagreement
from dumbobft.core.validatedcommonsubset import validatedcommonsubset
from dumbobft.core.provablereliablebroadcast import provablereliablebroadcast
from dumbobft.core.dumbocommonsubset import dumbocommonsubset
from honeybadgerbft.core.honeybadger_block import honeybadger_block
from honeybadgerbft.crypto.threshsig.boldyreva import serialize, deserialize1
from honeybadgerbft.crypto.threshsig.boldyreva import TBLSPrivateKey, TBLSPublicKey
from honeybadgerbft.crypto.ecdsa.ecdsa import PrivateKey
from honeybadgerbft.core.commoncoin import shared_coin
from honeybadgerbft.exceptions import UnknownTagError


def hash(x):
    return hashlib.sha256(pickle.dumps(x)).digest()


class BroadcastTag(Enum):
    TCVBA = 'TCVBA'
    FAST = 'FAST'
    VIEW_CHANGE = 'VIEW_CHANGE'
    VIEW_COIN = 'VIEW_COIN'
    ACS_PRBC = 'ACS_PRBC'
    ACS_VACS = 'ACS_VACS'
    TPKE = 'TPKE'



BroadcastReceiverQueues = namedtuple(
    'BroadcastReceiverQueues', ('TCVBA', 'FAST', 'VIEW_CHANGE', 'VIEW_COIN', 'ACS_PRBC', 'ACS_VACS', 'TPKE'))


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
        traceback.print_exc()


def broadcast_receiver_loop(recv_func, recv_queues):
    while True:
        broadcast_receiver(recv_func, recv_queues)


class Mule():
    """Mule object used to run the protocol

    :param str sid: The base name of the common coin that will be used to
        derive a nonce to uniquely identify the coin.
    :param int pid: Node id.
    :param int B: Batch size of transactions.
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

    def __init__(self, sid, pid, S, T, B, N, f, sPK, sSK, sPK1, sSK1, sPK2s, sSK2, ePK, eSK, send, recv, K=3, logger=None):

        self.SLOTS_NUM = S
        self.TIMEOUT = T
        self.FAST_BATCH_SIZE = B

        self.sid = sid
        self.id = pid
        self.B = B
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
        self.logger = logger
        self.epoch = 0  # Current block number
        self.transaction_buffer = deque()
        self._per_epoch_recv = {}  # Buffer of incoming messages

        self.K = K

    def submit_tx(self, tx):
        """Appends the given transaction to the transaction buffer.

        :param tx: Transaction to append to the buffer.
        """
        # print('backlog_tx', self.id, tx)
        #if self.logger != None:
        #    self.logger.info('Backlogged tx at Node %d:' % self.id + str(tx))
        self.transaction_buffer.append(tx)

    def run(self):
        """Run the Mule protocol."""

        def _recv():
            """Receive messages."""
            while True:
                (sender, (r, msg)) = self._recv()

                # Maintain an *unbounded* recv queue for each epoch
                if r not in self._per_epoch_recv:
                    self._per_epoch_recv[r] = Queue()

                # Buffer this message
                self._per_epoch_recv[r].put_nowait((sender, msg))

        self._recv_thread = gevent.spawn(_recv)

        while True:
            # For each epoch
            e = self.epoch
            if e not in self._per_epoch_recv:
                self._per_epoch_recv[e] = Queue()

            def _make_send(e):
                def _send(j, o):
                    self._send(j, (e, o))

                return _send

            send_e = _make_send(e)
            recv_e = self._per_epoch_recv[e].get
            new_tx = self._run_epoch(e, send_e, recv_e)

            # print('new block at %d:' % self.id, new_tx)
            if self.logger != None:
                self.logger.info('Node %d Delivers Block %d: ' % (self.id, self.epoch) + str(new_tx))

            # print('buffer at %d:' % self.id, self.transaction_buffer)
            if self.logger != None:
                self.logger.info('Backlog Buffer at Node %d:' % self.id + str(self.transaction_buffer))

            self.epoch += 1  # Increment the round
            if self.epoch >= self.K:
                break  # Only run one round for now

        if self.logger != None:
            self.logger.info("node %d breaks" % self.id)
        else:
            print("node %d breaks" % self.id)

    def _recovery(self):
        # TODO: here to implement to recover blocks
        pass

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
        S = self.SLOTS_NUM
        T = self.TIMEOUT
        B = self.FAST_BATCH_SIZE

        epoch_id = sid + 'FAST' + str(e)
        hash_genesis = hash(epoch_id)

        fast_recv = Queue()  # The thread-safe queue to receive the messages sent to fast_path of this epoch
        viewchange_recv = Queue()
        tcvba_recv = Queue()
        coin_recv = Queue()

        prbc_recvs = [Queue() for _ in range(N)]
        vacs_recv = Queue()
        tpke_recv = Queue()

        recv_queues = BroadcastReceiverQueues(
            TCVBA=tcvba_recv,
            FAST=fast_recv,
            VIEW_CHANGE=viewchange_recv,
            VIEW_COIN=coin_recv,
            ACS_PRBC=prbc_recvs,
            ACS_VACS=vacs_recv,
            TPKE=tpke_recv,
        )
        gevent.spawn(broadcast_receiver_loop, recv, recv_queues)

        tcvba_input = Queue(1)
        tcvba_output = Queue(1)

        fast_blocks = Queue()  # The blocks that receives

        viewchange_counter = 0
        viewchange_max_slot = 0

        def _setup_fastpath(leader):

            def fastpath_send(k, o):
                send(k, ('FAST', '', o))

            fast_thread = gevent.spawn(fastpath, epoch_id, pid, N, f, leader,
                                       self.transaction_buffer.popleft, fast_blocks.put,
                                       S, B, T, hash_genesis, self.sPK1, self.sSK1, self.sPK2s, self.sSK2,
                                       fast_recv.get, fastpath_send, self.logger)

            return fast_thread

        def _setup_coin():
            def coin_bcast(o):
                """Common coin multicast operation.
                :param o: Value to multicast.
                """
                for k in range(N):
                    send(k, ('VIEW_COIN', '', o))

            coin = shared_coin(epoch_id, pid, N, f,
                               self.sPK, self.sSK,
                               coin_bcast, coin_recv.get)

            return coin

        def _setup_tcvba(coin):

            def tcvba_send(k, o):
                send(k, ('TCVBA', '', o))

            tcvba = gevent.spawn(twovalueagreement, epoch_id, pid, N, f, coin,
                         tcvba_input.get, tcvba_output.put_nowait,
                         tcvba_recv.get, tcvba_send)

            return tcvba

        # Setup VIEW CHANGE
        coin_thread = _setup_coin()
        tcvba_thread = _setup_tcvba(coin_thread)

        # Start the fast path
        leader = e % N
        fast_thread = _setup_fastpath(leader)

        #
        def handle_viewchange_msg():
            nonlocal viewchange_counter, viewchange_max_slot

            while True:
                j, (notarized_block_header_j, notarized_block_raw_Sig_j) = viewchange_recv.get()
                if notarized_block_raw_Sig_j is not None:
                    (_, slot_num, Sig_p, _) = notarized_block_header_j
                    notarized_block_hash_j = hash(notarized_block_header_j)
                    try:
                        notarized_Sig_j = deserialize1(notarized_block_raw_Sig_j)
                        notarized_hash = self.sPK1.hash_message(notarized_block_hash_j)
                        assert self.sPK1.verify_signature(notarized_Sig_j, notarized_hash)
                    except AssertionError:
                        print("False view change with invalid notarization")
                        continue  # go to next iteration without counting ViewChange Counter
                else:
                    assert notarized_block_header_j == None
                    slot_num = 0

                viewchange_counter += 1
                if slot_num > viewchange_max_slot:
                    viewchange_max_slot = slot_num

                if viewchange_counter >= N - f:
                    tcvba_input.put_nowait(viewchange_max_slot)
                    break

        vc_thread = gevent.spawn(handle_viewchange_msg)

        # Block to wait the fast path returns
        fast_thread.join()

        # Get the returned notarization of the fast path, which contains the combined Signature for the tip of chain
        notarization = fast_thread.get()

        print(("Fast chain proof: ", notarization))

        if notarization is not None:

            notarized_block = fast_blocks.queue[fast_blocks.qsize() - 1]
            #notarized_block = fast_blocks.get()

            payload_digest = hash(notarized_block[3])
            notarized_block_header = (notarized_block[0], notarized_block[1], notarized_block[2], payload_digest)

            notarized_block_hash, notarized_block_raw_Sig = notarization

            assert hash(notarized_block_header) == notarized_block_hash

            o = (notarized_block_header, notarized_block_raw_Sig)
            for j in range(N):
                send(j, ('VIEW_CHANGE', '', o))

        else:
            notarized_block_header = None
            o = (notarized_block_header, None)
            for j in range(N):
                send(j, ('VIEW_CHANGE', '', o))

        #
        delivered_slots = tcvba_output.get()  # Block to receive the output
        delivered_slots = max(delivered_slots - 1, 0)
        #

        print(("fast blocks: ", fast_blocks))

        if delivered_slots > 0:

            if self.logger != None:
                self.logger.info('Backlogged tx at Node %d:' % self.id + str(fast_blocks))
            return fast_blocks

        else:

            # Select B transactions (TODO: actual random selection)
            tx_to_send = []

            for _ in range(self.B):
                try:
                    tx_to_send.append(self.transaction_buffer.popleft())
                except IndexError as e:
                    tx_to_send.append("Dummy")

            my_prbc_input = Queue(1)
            vacs_input = Queue(1)
            prbc_outputs = [Queue(1) for _ in range(N)]
            vacs_output = Queue(1)

            # if self.logger != None: self.logger.info('Commit tx at Node %d:' % self.id + str(tx_to_send))
            start = time.time()

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
                prbc = gevent.spawn(provablereliablebroadcast, epoch_id+'PRBC'+str(j), pid, N, f, self.sPK1, self.sSK1, j,
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

                gevent.spawn(validatedcommonsubset, epoch_id+'VACS', pid, N, f, self.sPK, self.sSK, self.sPK1, self.sSK1,
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

            _input = Queue(1)
            _input.put(json.dumps(tx_to_send))

            _output = honeybadger_block(pid, self.N, self.f, self.ePK, self.eSK,
                              _input.get,
                              acs_in=my_prbc_input.put_nowait, acs_out=dumboacs.get,
                              tpke_bcast=tpke_bcast, tpke_recv=tpke_recv.get)

            block = set()
            for batch in _output:
                decoded_batch = json.loads(batch.decode())
                for tx in decoded_batch:
                    block.add(tx)

            # print(("ACS block: ", block))
            end = time.time()

            if self.logger != None:
                self.logger.info('ACS block Delay at Node %d: ' % self.id + str(end - start))

            return list(block)
