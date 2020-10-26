from collections import defaultdict
from gevent.event import Event
from gevent.queue import Queue
from gevent import Timeout
from honeybadgerbft.crypto.ecdsa.ecdsa import ecdsa_sign, ecdsa_vrfy
from honeybadgerbft.crypto.threshsig.boldyreva import serialize, deserialize1

import json
import gevent
import hashlib, pickle


def hash(x):
    return hashlib.sha256(pickle.dumps(x)).digest()


def fastpath(sid, pid, N, f, leader, get_input, put_output, S, B, T, hash_genesis, PK1, SK1, PK2s, SK2, recv, send):
    """Fast path, Byzantine Safe Broadcast
    :param str sid: ``the string of identifier``
    :param int pid: ``0 <= pid < N``
    :param int N:  at least 3
    :param int f: fault tolerance, ``N >= 3f + 1``
    :param int leader: the pid of leading node
    :param get_input: a function to get input TXs, e.g., input() to get a transaction
    :param put_output: a function to deliver output blocks, e.g., output(block)
    :param PK1: ``boldyreva.TBLSPublicKey`` with threshold N-f
    :param SK1: ``boldyreva.TBLSPrivateKey`` with threshold N-f
    :param PK2s: an array of ``coincurve.PublicKey'', i.e., N public keys of ECDSA for all parties
    :param SK2: ``coincurve.PrivateKey'', i.e., secret key of ECDSA
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

    noncritical_signal = Event()
    noncritical_signal.set()

    def bcast(m):
        for i in range(N):
            send(i, m)

    def handle_messages():
        nonlocal leader, hash_prev, pending_block, notraized_block, batches, voters, votes, slot_cur

        while True:
            (sender, msg) = recv()
            assert sender in range(N)

            ########################
            # Enter critical block #
            ########################

            noncritical_signal.clear()

            if msg[0] == 'VOTE' and pid == leader:
                _, slot, hash_p, raw_sig_p, tx_batch, tx_sig = msg
                sig_p = deserialize1(raw_sig_p)

                if sender not in voters[slot]:

                    try:
                        assert slot == slot_cur
                    except AssertionError:
                        if slot < slot_cur:
                            print("Late vote! Not needed anymore...")
                        else:
                            print("Too early vote! I do not ")
                        continue

                    try:
                        assert hash_p == hash_prev
                    except AssertionError:
                        print("False vote though within the same slot!")
                        continue

                    try:
                        assert PK1.verify_share(sig_p, sender, PK1.hash_message(hash_p))
                        #assert PK1.verify_share(sig_p, sender, hash_p)
                    except AssertionError:
                        print("Vote signature failed!")
                        continue

                    try:
                        assert ecdsa_vrfy(PK2s[sender], tx_batch, tx_sig)
                    except AssertionError:
                        print("Batch signature failed!")
                        continue

                    voters[slot_cur].add(sender)
                    votes[slot_cur][sender] = sig_p
                    batches[slot_cur][sender] = (tx_batch, tx_sig)

                    if len(voters[slot_cur]) == N - f and not decide_sent[slot_cur]:
                        Simga = PK1.combine_shares(votes[slot_cur])
                        signed_batches = tuple(batches[slot_cur].items())
                        bcast(('DECIDE', slot_cur, hash_prev, serialize(Simga), signed_batches))
                        decide_sent[slot_cur] = True

            if msg[0] == "DECIDE":
                _, slot, hash_p, raw_Sig_p, signed_batches = msg
                Sig_p = deserialize1(raw_Sig_p)

                try:
                    assert slot == slot_cur
                except AssertionError:
                    print("Out of synchronization")
                    continue

                try:
                    #digest = PK1.hash_message(str((hash_p, slot-1)))
                    #assert PK1.verify_signature(Sig_p, digest)
                    assert PK1.verify_signature(Sig_p, PK1.hash_message(hash_p))

                except AssertionError:
                    print("Notarization signature failed!")
                    continue

                try:
                    assert len(signed_batches) >= N - f
                except AssertionError:
                    print("Not enough batches!")
                    continue

                for item in signed_batches:
                    proposer, (tx_batch, sig) = item
                    try:
                        ecdsa_vrfy(PK2s[proposer], tx_batch, sig)
                    except AssertionError:
                        print("Batches signatures failed!")
                        continue

                decides[slot].put((hash_p, raw_Sig_p, signed_batches))

            noncritical_signal.set()

            ########################
            # Leave critical block #
            ########################

    """
    One slot
    """

    def one_slot():
        nonlocal pending_block, notraized_block, hash_prev, slot_cur

        #digest = PK1.hash_message(hash_prev)
        #sig_prev = SK1.sign(digest)
        sig_prev = SK1.sign(PK1.hash_message(hash_prev))

        if slot_cur == SLOTS_NUM + 1 or slot_cur == SLOTS_NUM + 2:
            tx_batch = 'Dummy'
        else:
            tx_batch = json.dumps([get_input() for _ in range(BATCH_SIZE)])

        sig_tx = ecdsa_sign(SK2, tx_batch)

        send(leader, ('VOTE', slot_cur, hash_prev, serialize(sig_prev), tx_batch, sig_tx))

        (h_p, raw_Sig, signed_batches) = decides[slot_cur].get()  # Block to wait for the voted block
        # assert h_p == hash_prev

        if pending_block is not None:
            notraized_block = (pending_block[0], pending_block[1], pending_block[2], pending_block[4])
            put_output(notraized_block)
            # print(notraized_block)

        pending_block = (sid, slot_cur, h_p, raw_Sig, signed_batches)
        pending_block_header = (sid, slot_cur, h_p, hash(signed_batches))
        hash_prev = hash(pending_block_header)

    """
    Execute the slots
    """

    recv_thread = gevent.spawn(handle_messages)

    while slot_cur <= SLOTS_NUM + 2:
        print("node " + str(pid) + " starts the slot " + str(slot_cur) + " ...")
        print(noncritical_signal.is_set())

        timeout = Timeout(TIMEOUT, False)
        timeout.start()

        with Timeout(TIMEOUT):

            try:
                slot_thread = gevent.spawn(one_slot)
                slot_thread.join()
                print("node " + str(pid) + " finishes the slot " + str(slot_cur) + " ...")
                slot_cur = slot_cur + 1
            except Timeout:
                try:
                    noncritical_signal.wait()
                    gevent.killall([slot_thread, recv_thread])
                except Timeout as e:
                    print("node " + str(pid) + " error: " + str(e))
                if pending_block is not None:
                    return False, (pending_block[2], pending_block[3])  # represents fast_path fails with timeout, but still delivers some blocks
                else:
                    return False, None  # fast_path fails and delivers nothing useful
            finally:
                timeout.cancel()

    return True, (pending_block[2], pending_block[3])  # represents fast_path successes
