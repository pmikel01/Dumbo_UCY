import gevent,sys
from gevent.event import Event
from collections import defaultdict
import numpy as np
from gevent.queue import Queue
from honeybadgerbft.exceptions import RedundantMessageError, AbandonedNodeError
from honeybadgerbft.core.commoncoin import shared_coin

import logging

class JustContinueException(Exception):
    pass

logger = logging.getLogger(__name__)


def validatedagreement(sid, pid, N, f, coin, aba, PK, SK, input, decide, receive, send, predicate=None):
    """Multi-valued Byzantine consensus. It takes an input ``vi`` and will
    finally writes the decided value into ``decide`` channel.

    :param sid: session identifier
    :param pid: my id number
    :param N: the number of parties
    :param f: the number of byzantine parties
    :param coin: a ``common coin(r)`` is called to block until receiving a bit
    :param aba: a ``b_out <- aba(b_in)`` is called to block until receiving a bit
    :param PK: ``boldyreva.TBLSPublicKey``
    :param SK: ``boldyreva.TBLSPrivateKey``
    :param input: ``input()`` is called to receive an input
    :param decide: ``decide()`` is eventually called
    :param receive: receive channel
    :param send: send channel
    :param predicate: ``predicate()`` represents the externally validated condition
    """

    assert PK.k == f+1
    assert PK.l == N

    vcbc_values = defaultdict(lambda: None)
    vcbc_sshares = defaultdict(dict)
    vcbc_sigs = defaultdict(lambda: None)
    is_vcbcdelivered = [0] * N

    cbc_values = defaultdict(lambda: None)
    cbc_sshares = defaultdict(dict)
    cbc_sigs = defaultdict(lambda: None)
    is_cbcdelivered = [0] * N

    def broadcast(o):
        for i in range(N):
            send(i, o)

    def _handle_vcbc_messages(j, msg):

        if msg[0] == 'VCBC_SEND':
            _, sender, vs = msg
            if j != sender or vcbc_values[sender] != None:
                print("Inconsistent or redundant VCBC_SEND received", (sid, pid, j, msg))
                raise JustContinueException()
            vcbc_values[j] = vs
            h = PK.hash_message(str((sid, 'VCBC_SEND', sender, vs)))
            send(j, ('VCBC_READY', sender, h, SK.sign(h)))
            if vcbc_sigs[j] != None:
                sig = vcbc_sigs[j]
                try:
                    assert PK.verify_signature(sig, h)
                    if predicate == None or predicate(vs):
                        is_vcbcdelivered[sender] = 1
                except AssertionError:
                    print("Signature failed!", (sid, pid, j, msg))
                    # continue
                    raise JustContinueException()

        elif msg[0] == 'VCBC_READY':
            # VCBC_READY message
            _, sender, h, s = msg
            if vcbc_values[sender] == None:
                print("VCBC value not broadcasted yet", (sid, pid, j, msg))
                raise JustContinueException()
            if j in vcbc_sshares[sender]:
                print("redundant partial sig received", (sid, pid, j, msg))
                #continue
                raise JustContinueException()
            if sender != pid or h != PK.hash_message(str((sid, 'VCBC_SEND', sender, vcbc_values[sender]))):
                print("Inconsistent vcbc ready msg!", (sid, pid, j, msg))
                #continue
                raise JustContinueException()
            try:
                assert PK.verify_share(s, j, h)
            except AssertionError:
                print("Signature share failed!", (sid, pid, j, msg))
                #continue
                raise JustContinueException()
            vcbc_sshares[sender][j] = s
            if len(vcbc_sshares[sender]) == f + 1:
                sigs = dict(list(vcbc_sshares[sender].items())[:f + 1])
                sig = PK.combine_shares(sigs)
                assert PK.verify_signature(sig, h)
                # vcbcs_values[sender] = sig
                broadcast(('VCBC_FINAL', sender, h, sig))


        elif msg[0] == 'VCBC_FINAL':
            # VCBC_FINAL message
            _, sender, h, sig = msg
            if vcbc_sigs[j] != None:
                print("redundant full sig received", (sid, pid, j, msg))
                #continue
                raise JustContinueException()
            if j != sender:
                print("Inconsistent vcbc final msg!", (sid, pid, j, msg))
                #continue
                raise JustContinueException()
            if vcbc_values[sender] == None:
                #continue
                raise JustContinueException()
            try:
                h = PK.hash_message(str((sid, 'VCBC_SEND', sender, vcbc_values[sender])))
                assert PK.verify_signature(sig, h)
                vcbc_sigs[sender] = sig
                if predicate == None or predicate(vcbc_values[sender]):
                    is_vcbcdelivered[sender] = 1
            except AssertionError:
                print("Signature failed!", (sid, pid, j, msg))
                #continue
                raise JustContinueException()

        elif msg[0] == 'VCBC_REQUEST':
            # VCBC_REQUEST message
            _, sender = msg
            if vcbc_values[sender] != None and vcbc_sigs[sender] != None:
                send(j, ('VCBC_ANSWER', sender, vcbc_values[sender], vcbc_sigs[sender]))

        elif msg[0] == 'VCBC_ANSWER':
            # VCBC_REQUEST message
            _, sender, vs, sig = msg
            try:
                h = PK.hash_message(str((sid, 'VCBC_SEND', sender, vs)))
                assert PK.verify_signature(sig, h)
                vcbc_sigs[sender] = sig
                vcbc_values[sender] = vs
                if predicate == None or predicate(vs):
                    is_vcbcdelivered[sender] = 1
            except AssertionError:
                print("Signature failed!", (sid, pid, j, msg))
                #continue
                raise JustContinueException()



    def _handle_cbc_messages(j, msg):

        if msg[0] == 'CBC_SEND':
            _, sender, vs = msg
            if j != sender or cbc_values[sender] != None:
                print("Inconsistent or redundant CBC_SEND received", (sid, pid, j, msg))
                raise JustContinueException()
            cbc_values[j] = vs
            h = PK.hash_message(str((sid, 'CBC_SEND', sender, vs)))
            send(j, ('CBC_READY', sender, h, SK.sign(h)))
            if cbc_sigs[j] != None:
                sig = cbc_sigs[j]
                try:
                    assert PK.verify_signature(sig, h)
                    if sum(vs) >= N - f:
                        is_cbcdelivered[sender] = 1
                except AssertionError:
                    print("Signature failed!", (sid, pid, j, msg))
                    # continue
                    raise JustContinueException()

        elif msg[0] == 'CBC_READY':
            # CBC_READY message
            _, sender, h, s = msg
            if cbc_values[sender] == None:
                print("CBC value not broadcasted yet", (sid, pid, j, msg))
                raise JustContinueException()
            if j in cbc_sshares[sender]:
                print("redundant partial sig received", (sid, pid, j, msg))
                # continue
                raise JustContinueException()
            if sender != pid or h != PK.hash_message(str((sid, 'CBC_SEND', sender, cbc_values[sender]))):
                print("Inconsistent cbc ready msg!", (sid, pid, j, msg))
                # continue
                raise JustContinueException()
            try:
                assert PK.verify_share(s, j, h)
            except AssertionError:
                print("Signature share failed!", (sid, pid, j, msg))
                # continue
                raise JustContinueException()
            cbc_sshares[sender][j] = s
            if len(cbc_sshares[sender]) == f + 1:
                sigs = dict(list(cbc_sshares[sender].items())[:f + 1])
                sig = PK.combine_shares(sigs)
                assert PK.verify_signature(sig, h)
                broadcast(('CBC_FINAL', sender, h, sig))

        elif msg[0] == 'CBC_FINAL':
            # CBC_FINAL message
            _, sender, h, sig = msg
            if cbc_sigs[j] != None:
                print("redundant full sig received", (sid, pid, j, msg))
                # continue
                raise JustContinueException()
            if j != sender:
                print("Inconsistent cbc final msg!", (sid, pid, j, msg))
                # continue
                raise JustContinueException()
            if cbc_values[sender] == None:
                # continue
                raise JustContinueException()
            try:
                vs = cbc_values[sender]
                h = PK.hash_message(str((sid, 'CBC_SEND', sender, vs)))
                assert PK.verify_signature(sig, h)
                cbc_sigs[sender] = sig
                if sum(vs) >= N - f:
                    is_cbcdelivered[sender] = 1
            except AssertionError:
                print("Signature failed!", (sid, pid, j, msg))
                # continue
                raise JustContinueException()

    def _recv():
        while True:  # not finished[pid]:
            (j, msg) = receive()
            logger.debug(f'receive {msg} from node {j}',
                         extra={'nodeid': pid, 'epoch': msg[1]})
            assert j in range(N)
            try:
                if msg[0] in {'VCBC_SEND', 'VCBC_READY', 'VCBC_FINAL', 'VCBC_REQUEST', 'VCBC_ANSWER'}:
                    _handle_vcbc_messages(j, msg)
                elif msg[0] in {'CBC_SEND', 'CBC_READY', 'CBC_FINAL'}:
                    _handle_cbc_messages(j, msg)
                elif msg[0] in {'BIASED_ABA_BALL'}:
                    _, sender, vs = msg
                    #TODO:
                    continue
            except JustContinueException:
                continue

    _thread_recv = gevent.spawn(_recv)

    vi = input()
    assert None == predicate or predicate(vi)

    # c-broadcast value
    broadcast(('VCBC_SEND', pid, vi))

    # wait for N - f vcbc-delivered valid values
    while True:
        if sum(is_vcbcdelivered) >= N - f:
            commit = is_vcbcdelivered
            break

    # c-broadcast commit vector
    broadcast(('CBC_SEND', pid, commit))

    # wait for N - f cbc-delivered commit vectors
    while True:
        if sum(is_cbcdelivered) >= N - f:
            commits = cbc_values
            break

    # get a coin and then generate a random permutation
    #coin = shared_coin(sid + 'COIN' + str(j), pid, N, f,
    #       self.sPK, self.sSK,
    #       coin_bcast, coin_recvs[j].get)
    s = coin(0)
    np.random.seed(s)
    pi = np.random.permutation(N)


    r = 0
    while True:
        if
        r += 1
