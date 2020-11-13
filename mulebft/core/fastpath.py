import traceback
import time
from collections import defaultdict
from gevent.event import Event
from gevent.queue import Queue
from gevent import Timeout, monkey
from honeybadgerbft.crypto.ecdsa.ecdsa import ecdsa_sign, ecdsa_vrfy, PublicKey
from honeybadgerbft.crypto.threshsig.boldyreva import serialize, deserialize1
from honeybadgerbft.crypto.threshsig.boldyreva import TBLSPrivateKey, TBLSPublicKey

import json
import gevent
import hashlib, pickle

monkey.patch_all()


def hash(x):
    return hashlib.sha256(pickle.dumps(x)).digest()


def fastpath(sid, pid, N, f, leader, get_input, put_output, S, B, T, hash_genesis, PK1, SK1, PK2s, SK2, recv, send, logger=None):
    """Fast path, Byzantine Safe Broadcast
    :param str sid: ``the string of identifier``
    :param int pid: ``0 <= pid < N``
    :param int N:  at least 3
    :param int f: fault tolerance, ``N >= 3f + 1``
    :param int leader: the pid of leading node
    :param get_input: a function to get input TXs, e.g., input() to get a transaction
    :param put_output: a function to deliver output blocks, e.g., output(block)
    :param TBLSPublicKey PK1: ``boldyreva.TBLSPublicKey`` with threshold N-f
    :param TBLSPrivateKey SK1: ``boldyreva.TBLSPrivateKey`` with threshold N-f
    :param list PK2s: an array of ``coincurve.PublicKey'', i.e., N public keys of ECDSA for all parties
    :param PublicKey SK2: ``coincurve.PrivateKey'', i.e., secret key of ECDSA
    :param int T: timeout of a slot
    :param int S: number of slots in a epoch
    :param int B: batch size, i.e., the number of TXs in a batch
    :param hash_genesis: the hash of genesis block
    :param recv: function to receive incoming messages
    :param send: function to send outgoing messages
    :return tuple: False to represent timeout, and True to represent success
    """

    TIMEOUT = T
    SLOTS_NUM = S
    BATCH_SIZE = B

    assert leader in range(N)
    slot_cur = 1

    hash_prev = hash_genesis
    pending_block = None
    notraized_block = None

    # Leader's temp variables
    voters = defaultdict(lambda: set())
    votes = defaultdict(lambda: dict())
    batches = defaultdict(lambda: dict())
    decides = defaultdict(lambda: Queue(1))

    decide_sent = [False] * (SLOTS_NUM + 3)  # The first item of the list is not used

    msg_noncritical_signal = Event()
    msg_noncritical_signal.set()

    slot_noncritical_signal = Event()
    slot_noncritical_signal.set()

    s_times = [0] * (SLOTS_NUM + 3)
    e_times = [0] * (SLOTS_NUM + 3)

    def bcast_to_all_but_not_me(m):
        for i in range(N):
            if i != pid:
                send(i, m)

    def handle_messages():
        nonlocal leader, hash_prev, pending_block, notraized_block, batches, voters, votes, slot_cur

        while True:
            (sender, msg) = recv()
            assert sender in range(N)

            ########################
            # Enter critical block #
            ########################

            msg_noncritical_signal.clear()

            if msg[0] == 'VOTE' and pid == leader and len(voters[slot_cur]) < N - f:

                _, slot, hash_p, raw_sig_p, tx_batch, tx_sig = msg
                sig_p = deserialize1(raw_sig_p)

                if sender not in voters[slot]:

                    try:
                        assert slot == slot_cur
                    except AssertionError:
                        #if slot < slot_cur:
                        #    print("Late vote from node %d! Not needed anymore..." % sender)
                        #else:
                        #    print("Too early vote from node %d! I do not decide earlier block yet..." % sender)
                        continue

                    try:
                        assert hash_p == hash_prev
                    except AssertionError:
                        print("False vote from node %d though within the same slot!" % sender)
                        msg_noncritical_signal.set()
                        continue

                    try:
                        assert PK1.verify_share(sig_p, sender, PK1.hash_message(hash_p))
                    except AssertionError:
                        print("Vote signature failed!")
                        msg_noncritical_signal.set()
                        continue

                    try:
                        assert ecdsa_vrfy(PK2s[sender], tx_batch, tx_sig)
                    except AssertionError:
                        print("Batch signature failed!")
                        msg_noncritical_signal.set()
                        continue

                    voters[slot_cur].add(sender)
                    votes[slot_cur][sender] = sig_p
                    batches[slot_cur][sender] = (tx_batch, tx_sig)

                    if len(voters[slot_cur]) == N - f and not decide_sent[slot_cur]:
                        Simga = PK1.combine_shares(votes[slot_cur])
                        signed_batches = tuple(batches[slot_cur].items())
                        raw_Sig = serialize(Simga)
                        decides[slot_cur].put((hash_p, raw_Sig, signed_batches))
                        bcast_to_all_but_not_me(('DECIDE', slot_cur, hash_prev, raw_Sig, signed_batches))
                        decide_sent[slot_cur] = True

            if msg[0] == "DECIDE" and pid != leader:

                _, slot, hash_p, raw_Sig_p, signed_batches = msg
                Sig_p = deserialize1(raw_Sig_p)

                try:
                    assert slot == slot_cur
                except AssertionError:
                    print("Out of synchronization")
                    msg_noncritical_signal.set()
                    continue

                try:
                    assert PK1.verify_signature(Sig_p, PK1.hash_message(hash_p))
                except AssertionError:
                    print("Notarization signature failed!")
                    msg_noncritical_signal.set()
                    continue

                try:
                    assert len(signed_batches) >= N - f
                except AssertionError:
                    print("Not enough batches!")
                    msg_noncritical_signal.set()
                    continue

                for item in signed_batches:
                    proposer, (tx_batch, sig) = item
                    try:
                        ecdsa_vrfy(PK2s[proposer], tx_batch, sig)
                    except AssertionError:
                        print("Batches signatures failed!")
                        msg_noncritical_signal.set()
                        continue

                decides[slot_cur].put((hash_p, raw_Sig_p, signed_batches))

            msg_noncritical_signal.set()

            ########################
            # Leave critical block #
            ########################

    """
    One slot
    """

    def one_slot():
        nonlocal pending_block, notraized_block, hash_prev, slot_cur

        sig_prev = SK1.sign(PK1.hash_message(hash_prev))

        s_times[slot_cur] = time.time()
        if slot_cur == SLOTS_NUM + 1 or slot_cur == SLOTS_NUM + 2:
            tx_batch = 'Dummy'
        else:
            try:
                tx_batch = json.dumps([get_input() for _ in range(BATCH_SIZE)])
            except IndexError as e:
                tx_batch = json.dumps(['Dummy' for _ in range(BATCH_SIZE)])

        try:
            sig_tx = ecdsa_sign(SK2, tx_batch)
            send(leader, ('VOTE', slot_cur, hash_prev, serialize(sig_prev), tx_batch, sig_tx))
        except AttributeError as e:
            traceback.print_exc(e)

        (h_p, raw_Sig, signed_batches) = decides[slot_cur].get()  # Block to wait for the voted block

        ########################
        # Enter critical block #
        ########################

        slot_noncritical_signal.clear()

        if pending_block is not None:
            notraized_block = (pending_block[0], pending_block[1], pending_block[2], pending_block[4])
            put_output(notraized_block)
            e_times[pending_block[1]] = time.time()
            delay = e_times[pending_block[1]] - s_times[pending_block[1]]
            logger.info('Fast block Delay at Node %d for epoch %s and slot %d: ' % (pid, sid, pending_block[1]) + str(delay))


        pending_block = (sid, slot_cur, h_p, raw_Sig, signed_batches)
        pending_block_header = (sid, slot_cur, h_p, hash(signed_batches))
        hash_prev = hash(pending_block_header)

        slot_noncritical_signal.set()

        ########################
        # Leave critical block #
        ########################

    """
    Execute the slots
    """

    recv_thread = gevent.spawn(handle_messages)

    while slot_cur <= SLOTS_NUM + 2:
        msg_noncritical_signal.wait()
        slot_noncritical_signal.wait()

        timeout = Timeout(TIMEOUT, False)
        timeout.start()

        with Timeout(TIMEOUT):

            try:
                slot_thread = gevent.spawn(one_slot)
                slot_thread.join()
                slot_cur = slot_cur + 1
            except Timeout:
                try:
                    msg_noncritical_signal.wait()
                    slot_noncritical_signal.wait()
                    gevent.killall([slot_thread, recv_thread])
                except Timeout as e:
                    print("node " + str(pid) + " error: " + str(e))
                    break
                #if pending_block is not None:
                #    assert notraized_block is not None
                #    return (pending_block[2], pending_block[3])  # represents fast_path fails with timeout, but still delivers some blocks
                #else:
                #    return None  # fast_path fails and delivers nothing useful
            finally:
                timeout.cancel()

    if notraized_block != None:
        return pending_block[2], pending_block[3]  # represents fast_path successes
    else:
        return None