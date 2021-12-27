from gevent import monkey; monkey.patch_all(thread=False)

import traceback
import time
from collections import defaultdict
from gevent.event import Event
from gevent.queue import Queue
from crypto.ecdsa.ecdsa import ecdsa_sign, ecdsa_vrfy, PublicKey
from crypto.threshsig.boldyreva import TBLSPrivateKey, TBLSPublicKey
import json
import gevent
import hashlib, pickle
from gevent import Timeout


def hash(x):
    return hashlib.sha256(pickle.dumps(x)).digest()


def two_chain_hotstuff(sid, pid, N, f, leader, get_input, put_output, Snum, Bsize, Tout, hash_genesis, PK2s, SK2, recv, send, logger=None):
    """Fast path, Byzantine Safe Broadcast
    :param str sid: ``the string of identifier``
    :param int pid: ``0 <= pid < N``
    :param int N:  at least 3
    :param int f: fault tolerance, ``N >= 3f + 1``
    :param int leader: the pid of leading node
    :param get_input: a function to get input TXs, e.g., input() to get a transaction
    :param put_output: a function to deliver output blocks, e.g., output(block)
    :param list PK2s: an array of ``coincurve.PublicKey'', i.e., N public keys of ECDSA for all parties
    :param PublicKey SK2: ``coincurve.PrivateKey'', i.e., secret key of ECDSA
    :param int Snum: number of slots in a epoch
    :param int Bsize: batch size, i.e., the number of TXs in a batch
    :param hash_genesis: the hash of genesis block
    :param recv: function to receive incoming messages
    :param send: function to send outgoing messages
    :param bcast: function to broadcast a message
    :return tuple: False to represent timeout, and True to represent success
    """

    #if logger is not None: logger.info("Entering fast path of epoch %d" % pid)

    SLOTS_NUM = Snum
    BATCH_SIZE = Bsize
    TIMEOUT = Tout

    assert leader in range(N)
    slot_cur = 1

    hash_prev = hash_genesis
    pending_block = None
    notraized_block = None
    pending_block_header = None

    # Leader's temp variables
    voters = defaultdict(lambda: set())
    votes = defaultdict(lambda: dict())
    decides = defaultdict(lambda: Queue(1))

    timeout_voters = defaultdict(lambda: set())
    timeout_votes = defaultdict(lambda: dict())


    decide_sent = [False] * (SLOTS_NUM + 3)  # The first item of the list is not used

    msg_noncritical_signal = Event()
    msg_noncritical_signal.set()

    slot_noncritical_signal = Event()
    slot_noncritical_signal.set()

    s_times = [0] * (SLOTS_NUM + 3)
    e_times = [0] * (SLOTS_NUM + 3)
    txcnt =  [0] * (SLOTS_NUM + 3)
    delay =  [0] * (SLOTS_NUM + 3)

    epoch_txcnt = 0
    weighted_delay = 0

    not_timeouted = Event()
    not_timeouted.set()
    timeouted = Event()
    timeouted.clear()


    def handle_messages():
        nonlocal leader, hash_prev, pending_block, pending_block_header, notraized_block, voters, votes, slot_cur

        while True:

            #gevent.sleep(0)

            (sender, msg) = recv()
            #logger.info("receving a fast path msg " + str((sender, msg)))

            assert sender in range(N)

            ########################
            # Enter critical block #
            ########################

            msg_noncritical_signal.clear()

            if msg[0] == 'VOTE' and pid == leader and len(voters[slot_cur]) < N - f:

                _, slot, hash_p, sig_p = msg
                #_, slot, hash_p, raw_sig_p, tx_batch, tx_sig = msg
                #sig_p = deserialize1(raw_sig_p)

                if sender not in voters[slot]:

                    try:
                        assert slot == slot_cur
                    except AssertionError:
                        #print("vote out of sync...")
                        #if slot < slot_cur:
                        #    if logger is not None: logger.info("Late vote from node %d! Not needed anymore..." % sender)
                        #else:
                        #    if logger is not None: logger.info("Too early vote from node %d! I do not decide earlier block yet..." % sender)
                        msg_noncritical_signal.set()
                        continue

                    try:
                        assert hash_p == hash_prev
                    except AssertionError:
                        if logger is not None:
                            logger.info("False vote from node %d though within the same slot!" % sender)
                        msg_noncritical_signal.set()
                        continue

                    try:
                        assert ecdsa_vrfy(PK2s[sender], hash_p, sig_p)
                    except AssertionError:
                        if logger is not None:
                            logger.info("Vote signature failed!")
                        msg_noncritical_signal.set()
                        continue


                    voters[slot_cur].add(sender)
                    votes[slot_cur][sender] = sig_p

                    if len(voters[slot_cur]) == N - f and not decide_sent[slot_cur]:
                        #print(slot_cur)
                        Sigma = tuple(votes[slot_cur].items())
                        if slot_cur == SLOTS_NUM + 1 or slot_cur == SLOTS_NUM + 2:
                            tx_batch = 'Dummy'
                        else:
                            try:
                                tx_batch = json.dumps([get_input() for _ in range(BATCH_SIZE)])
                            except Exception as e:
                                tx_batch = json.dumps(['Dummy' for _ in range(BATCH_SIZE)])

                        send(-2, ('DECIDE', slot_cur, hash_prev, Sigma, tx_batch))
                        #if logger is not None: logger.info("Decide made and sent")
                        decide_sent[slot_cur] = True
                        decides[slot_cur].put_nowait((hash_p, Sigma, tx_batch))

            if msg[0] == "DECIDE" and pid != leader:

                _, slot, hash_p, Sigma_p, batches = msg

                try:
                    assert slot == slot_cur
                except AssertionError:
                    if logger is not None: logger.info("Out of synchronization")
                    msg_noncritical_signal.set()
                    continue

                try:
                    assert len(Sigma_p) >= N - f
                except AssertionError:
                    if logger is not None: logger.info("No enough ecdsa signatures!")
                    msg_noncritical_signal.set()
                    continue

                try:
                    for item in Sigma_p:
                        #print(Sigma_p)
                        (sender, sig_p) = item
                        assert ecdsa_vrfy(PK2s[sender], hash_p, sig_p)
                except AssertionError:
                    if logger is not None: logger.info("ecdsa signature failed!")
                    msg_noncritical_signal.set()
                    continue

                decides[slot_cur].put_nowait((hash_p, Sigma_p, batches))

            if msg[0] == "TIMEOUT" and pid == leader and len(timeout_voters[slot_cur]) < N - f and timeouted.is_set():
                _, slot, timeout_sig, pending_block_header = msg
                (_, slot_p, h_pp, digest) = pending_block_header

                timeout_voters[slot_cur].add(sender)
                timeout_votes[slot_cur][sender] = timeout_sig

                msg_noncritical_signal.set()
                send(-1, ("TIMEOUT_ECHO"))
                continue

            if msg[0] == "TIMEOUT_ECHO" and pid != leader and timeouted.is_set():
                _, slot, hash_p, sig_p = msg
                not_timeouted.set()
                msg_noncritical_signal.set()
                continue

            msg_noncritical_signal.set()

            ########################
            # Leave critical block #
            ########################

    """
    One slot
    """

    def one_slot():
        nonlocal pending_block, notraized_block, hash_prev, slot_cur, epoch_txcnt, delay, e_times, s_times, txcnt, weighted_delay

        #print('3')

        #if logger is not None:
        #    logger.info("Entering slot %d" % slot_cur)

        s_times[slot_cur] = time.time()

        try:
            sig_prev = ecdsa_sign(SK2, hash_prev)
            send(leader, ('VOTE', slot_cur, hash_prev, sig_prev))
        except AttributeError as e:
            if logger is not None:
                logger.info(traceback.print_exc())

        #print('4')

        (h_p, Sigma_p, batches) = decides[slot_cur].get()  # Block to wait for the voted block


        ########################
        # Enter critical block #
        ########################

        slot_noncritical_signal.clear()
        msg_noncritical_signal.wait()

        if pending_block is not None:

            notraized_block = (pending_block[0], pending_block[1], pending_block[2], pending_block[4])
            if put_output is not None: put_output(notraized_block)
            txcnt[pending_block[1]] = str(notraized_block).count("Dummy TX")

            if pending_block[1] >= 2:
                e_times[pending_block[1]-1] = time.time()
                delay[pending_block[1]-1] = e_times[pending_block[1]-1] - s_times[pending_block[1]-1]
                weighted_delay = (epoch_txcnt * weighted_delay + txcnt[pending_block[1]-1] * delay[pending_block[1]-1]) / (epoch_txcnt + txcnt[pending_block[1]-1])
                epoch_txcnt += txcnt[pending_block[1]-1]

                #if logger is not None:
                #    logger.info('Fast block Delay at Node %d for Epoch %s and Slot %d: ' % (pid, sid, pending_block[1]-1) + str(delay))

        pending_block = (sid, slot_cur, h_p, Sigma_p, batches)
        pending_block_header = (sid, slot_cur, h_p, hash(batches))
        hash_prev = hash(pending_block_header)

        slot_cur = slot_cur + 1

        slot_noncritical_signal.set()

        ########################
        # Leave critical block #
        ########################

    """
    Execute the slots
    """

    recv_thread = gevent.spawn(handle_messages)


    def pace_maker():
        nonlocal slot_cur, hash_prev, TIMEOUT

        while True:
            timeouted.wait()

            timeout_sig = ecdsa_sign(SK2, hash(slot_cur, pending_block_header))
            send(leader, ('TIMEOUT', slot_cur, timeout_sig, pending_block_header))
            print(('TIMEOUT-2', slot_cur, pending_block_header))

            try:
                with Timeout(TIMEOUT):
                    not_timeouted.wait()
                    slot_cur = slot_cur + 1
            except Timeout as err:
                print(err)
                # TIMEOUT = TIMEOUT * 2
                slot_cur = slot_cur + 1




    gevent.spawn(pace_maker)


    while slot_cur <= SLOTS_NUM + 2:

        #.sleep(0)

        #if logger is not None:
        #    logger.info("entering fastpath slot %d ..." % slot_cur)


        #print('1')

        not_timeouted.wait()

        msg_noncritical_signal.wait()
        slot_noncritical_signal.wait()

        #print('2')

        try:
            with Timeout(TIMEOUT):
                one_slot()
        except Timeout as e:
            msg_noncritical_signal.wait()
            slot_noncritical_signal.wait()
            print("node " + str(pid) + " error: " + str(e))
            if logger is not None:
                logger.info("HotStuff Timeout at round %d!", slot_cur)
                print(('TIMEOUT-1', slot_cur, pending_block_header))
            not_timeouted.clear()
            timeouted.set()





    if notraized_block != None:
        return pending_block[2], pending_block[3], (epoch_txcnt, weighted_delay)  # represents fast_path successes
    else:
        return None