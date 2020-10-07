import copy
import traceback
import logging
import gevent
import numpy as np

from collections import namedtuple
from gevent import time
from gevent.event import Event
from enum import Enum
from collections import defaultdict
from gevent.queue import Queue
from honeybadgerbft.core.commoncoin import shared_coin
from honeybadgerbft.core.binaryagreement import binaryagreement
from honeybadgerbft.core.consistentbroadcast import consistentbroadcast
from honeybadgerbft.exceptions import UnknownTagError
from gevent.monkey import patch_all
patch_all()


class MessageTag(Enum):
    VABA_COIN = 'VABA_COIN'             # Queue()
    VABA_COMMIT = 'VABA_COMMIT'         # Queue()
    VABA_VOTE = 'VABA_VOTE'             # [Queue()] * Number_of_ABA_Iterations
    VABA_ABA_COIN = 'VABA_ABA_COIN'     # [Queue()] * Number_of_ABA_Iterations
    VABA_CBC = 'VABA_CBC'               # [Queue()] * N
    VABA_ABA = 'VABA_ABA'               # [Queue()] * Number_of_ABA_Iterations


MessageReceiverQueues = namedtuple(
    'MessageReceiverQueues', ('VABA_COIN', 'VABA_COMMIT', 'VABA_VOTE', 'VABA_ABA_COIN', 'VABA_CBC', 'VABA_ABA'))


def msg_send_receiver(recv_func, recv_queues):
    sender, (tag, j, msg) = recv_func()
    print(sender, (tag, j, msg))
    if tag not in MessageTag.__members__:
        # TODO Post python 3 port: Add exception chaining.
        # See https://www.python.org/dev/peps/pep-3134/
        raise UnknownTagError('Unknown tag: {}! Must be one of {}.'.format(
            tag, MessageTag.__members__.keys()))
    recv_queue = recv_queues._asdict()[tag]

    if tag not in {MessageTag.VABA_COIN.value}:
        recv_queue = recv_queue[j]

    #if (tag == MessageTag.VABA_COIN.value)
    try:
        recv_queue.put_nowait((sender, msg))
    except AttributeError as e:
        print((sender, msg))
        traceback.print_exc(e)


def msg_send_receiver_loop(recv_func, recv_queues):
    while True:
        msg_send_receiver(recv_func, recv_queues)


logger = logging.getLogger(__name__)


def validatedagreement(sid, pid, N, f, PK, SK, PK1, SK1, input, decide, receive, send, predicate = lambda x: True):
    """Multi-valued Byzantine consensus. It takes an input ``vi`` and will
    finally writes the decided value into ``decide`` channel.

    :param sid: session identifier
    :param pid: my id number
    :param N: the number of parties
    :param f: the number of byzantine parties
    :param PK: ``boldyreva.TBLSPublicKey`` with threshold f+1
    :param SK: ``boldyreva.TBLSPrivateKey`` with threshold f+1
    :param PK1: ``boldyreva.TBLSPublicKey`` with threshold n-f
    :param SK1: ``boldyreva.TBLSPrivateKey`` with threshold n-f
    :param input: ``input()`` is called to receive an input
    :param decide: ``decide()`` is eventually called
    :param receive: receive channel
    :param send: send channel
    :param predicate: ``predicate()`` represents the externally validated condition
    """

    assert PK.k == f+1
    assert PK.l == N
    assert PK1.k == N-f
    assert PK1.l == N

    Number_of_ABA_Iterations = min(15, N)

    """ 
    """
    """ 
    Some instantiations
    """
    """ 
    """

    my_cbc_input = Queue(1)
    my_commit_input  = Queue(1)
    aba_inputs = [Queue(1) for _ in range(Number_of_ABA_Iterations)]  # noqa: E221

    aba_recvs = [Queue() for _ in range(Number_of_ABA_Iterations)]
    aba_coin_recvs = [Queue() for _ in range(Number_of_ABA_Iterations)]
    vote_recvs = [Queue() for _ in range(Number_of_ABA_Iterations)]
    cbc_recvs = [Queue() for _ in range(N)]
    coin_recv = Queue()
    commit_recvs = [Queue() for _ in range(N)]

    cbc_outputs = [Queue(1) for _ in range(N)]
    commit_outputs = [Queue(1) for _ in range(N)]
    aba_outputs = [Queue(1) for _ in range(Number_of_ABA_Iterations)]

    is_cbc_delivered = [0] * N
    is_commit_delivered = [0] * N

    recv_queues = MessageReceiverQueues(
        VABA_COIN=coin_recv,
        VABA_COMMIT=commit_recvs,
        VABA_VOTE=vote_recvs,
        VABA_ABA_COIN=aba_coin_recvs,
        VABA_CBC=cbc_recvs,
        VABA_ABA=aba_recvs,
    )
    gevent.spawn(msg_send_receiver_loop, receive, recv_queues)

    """ 
    Setup the sub protocols Input Broadcast CBCs"""

    for j in range(N):

        def make_cbc_send(j): # this make will automatically deep copy the enclosed send func
            def cbc_send(k, o):
                """CBC send operation.
                :param k: Node to send.
                :param o: Value to send.
                """
                #print("node", pid, "is sending", o, "to node", k, "with the leader", j)
                send(k, ('VABA_CBC', j, o))
            return cbc_send

        # Only leader gets input
        cbc_input = my_cbc_input.get if j == pid else None
        cbc = gevent.spawn(consistentbroadcast, sid + 'CBC' + str(j), pid, N, f, PK1, SK1, j,
                           cbc_input, cbc_recvs[j].get, make_cbc_send(j))
        # cbc.get is a blocking function to get cbc output
        cbc_outputs[j] = cbc.get

    """ 
    Setup the sub protocols Commit CBCs"""

    for j in range(N):

        def make_commit_send(j): # this make will automatically deep copy the enclosed send func
            def commit_send(k, o):
                """COMMIT-CBC send operation.
                :param k: Node to send.
                :param o: Value to send.
                """
                #print("node", pid, "is sending", o, "to node", k, "with the leader", j)
                send(k, ('VABA_COMMIT', j, o))
            return commit_send

        # Only leader gets input
        commit_input = my_commit_input.get if j == pid else None
        commit = gevent.spawn(consistentbroadcast, sid + 'COMMIT-CBC' + str(j), pid, N, f, PK1, SK1, j,
                           commit_input, commit_recvs[j].get, make_commit_send(j))
        # commit.get is a blocking function to get commit-cbc output
        commit_outputs[j] = commit.get

    """ 
    Setup the sub protocols permutation coins"""

    def coin_bcast(o):
        """Common coin multicast operation.
        :param o: Value to multicast.
        """
        for k in range(N):
            send(k, ('VABA_COIN', 'leader_election', o))

    permutation_coin = shared_coin(sid + 'COIN', pid, N, f,
                               PK, SK, coin_bcast, coin_recv.get)

    """ 
    """
    """ 
    Start to run consensus
    """
    """ 
    """

    """ 
    Run n CBC instance to consistently broadcast input values
    """

    cbc_values = [None] * N

    v = input()
    assert predicate(v)
    my_cbc_input.put_nowait(v)

    def wait_for_cbc_to_continue(leader):
        # Receive output from CBC broadcast for input values
        vl = cbc_outputs[leader]()
        if predicate(vl):
            cbc_values[leader] = vl # May block
            is_cbc_delivered[leader] = 1
            #print("Leader %d finishes CBC for node %d" % (leader, pid) )
            #print(is_cbc_delivered)

    cbc_out_threads = [gevent.spawn(wait_for_cbc_to_continue, node) for node in range(N)]

    while sum(is_cbc_delivered) < N - f:
        time.sleep(0)
        pass

    # print(is_cbc_delivered)
    # print(cbc_values)

    """
    Run n CBC instance to commit finished CBC IDs
    """

    commit_values = [None] * N

    assert len(is_cbc_delivered) == N
    assert sum(is_cbc_delivered) >= N - f
    assert all(item == 0 or 1 for item in is_cbc_delivered)

    my_commit_input.put_nowait(copy.deepcopy(is_cbc_delivered))  # Deepcopy prevents input changing while executing

    def wait_for_commit_to_continue(leader):
        # Receive output from CBC broadcast for commitment
        cl = commit_outputs[leader]()
        if (sum(cl[0]) >= N - f) and all(item == 0 or 1 for item in cl[0]): #
            commit_values[leader] = cl # May block
            is_commit_delivered[leader] = 1
            #print("Leader %d finishes COMMIT_CBC for node %d" % (leader, pid) )

    commit_out_threads = [gevent.spawn(wait_for_commit_to_continue, node) for node in range(N)]

    while sum(is_commit_delivered) < N - f:
        time.sleep(0)
        pass

    # print(is_commit_delivered)
    # print(commit_values)

    """
    Run a Coin instance to permute the nodes' IDs to sequentially elect the leaders
    """
    seed = permutation_coin('permutation')  # Block to get a random seed to permute nodes
    np.random.seed(seed)
    pi = np.random.permutation(N)

    # print(pi)

    """
    Repeatedly run biased ABA instances until 1 is output 
    """

    votes = defaultdict(set)
    msg_stop_signal = Event()
    msg_stop_signal.clear()

    def handle_vote_messages():
        while not msg_stop_signal.ready():
            time.sleep(0)
            for r in range(Number_of_ABA_Iterations):
                if not vote_recvs[r].empty():
                    sender, msg = vote_recvs[r].get()
                    a, flag_bit, o = msg
                    if (pi[r] == a) and (flag_bit == 0 or flag_bit == 1):
                        if flag_bit == 1:
                            (m, Sig) = o
                            digestFromLeader = PK1.hash_message(str((sid + 'CBC' + str(a), a, m)))
                            PK1.verify_signature(Sig, digestFromLeader)
                            votes[r].add((sender, msg))
                        else:
                            if commit_values[sender] is not None and commit_values[sender][a] == 0:
                                votes[r].add((sender, msg))
                if len(votes[r]) >= N - f:
                    break

    vote_msg_thread = gevent.spawn(handle_vote_messages)

    a = None
    for r in range(Number_of_ABA_Iterations):

        a = pi[r]
        if is_cbc_delivered[a] == 1:
            vote = (a, 1, cbc_values[a])
        else:
            vote = (a, 0, "Bottom")

        for j in range(N):
            send(j, ('VABA_VOTE', r, vote))

        while len(votes[r]) < N - f:
            time.sleep(0)
            pass

        print(votes[r])
        aba_r_input = 0
        for vote in votes[r]:
            _, (_, bit, cbc_value) = vote
            if bit == 1:
                aba_r_input = 1
                cbc_values[a] = cbc_value

        def make_coin_bcast():
            def coin_bcast(o):
                """Common coin multicast operation.
                :param o: Value to multicast.
                """
                for k in range(N):
                    send(k, ('VABA_ABA_COIN', r, o))
            return coin_bcast

        coin = shared_coin(sid + 'COIN' + str(r), pid, N, f,
                           PK, SK,
                           make_coin_bcast(), aba_coin_recvs[r].get)

        def make_aba_send(rnd): # this make will automatically deep copy the enclosed send func
            def aba_send(k, o):
                """CBC send operation.
                :param k: Node to send.
                :param o: Value to send.
                """
                #print("node", pid, "is sending", o, "to node", k, "with the leader", j)
                send(k, ('VABA_ABA', rnd, o))
            return aba_send

        # Only leader gets input
        aba = gevent.spawn(binaryagreement, sid + 'ABA' + str(r), pid, N, f, coin,
                     aba_inputs[r].get, aba_outputs[r].put_nowait,
                     aba_recvs[r].get, make_aba_send(r))
        # aba.get is a blocking function to get aba output
        aba_inputs[r].put_nowait(aba_r_input)
        aba_r = aba_outputs[r].get()
        print("Round", r, "ABA outputs", aba_r)

        if aba_r == 1:
            msg_stop_signal.set()
            print(msg_stop_signal.is_set())
            break
        else:
            continue
    assert a is not None
    decide(cbc_values[a][0])  # In rare cases, there could return None. We let higher level caller of VABA to deal that
