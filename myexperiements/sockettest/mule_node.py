import logging
import random
from typing import List

import gevent
import os
import pickle

from gevent import time, monkey
from mulebft.core.mule import Mule
from myexperiements.sockettest.make_random_tx import tx_generator
from coincurve import PrivateKey, PublicKey
from multiprocessing import Value as mpValue, Queue as mpQueue, Process

#monkey.patch_all(thread=False, socket=False)
monkey.patch_all(thread=False)


def load_key(id, N):

    with open(os.getcwd() + '/keys/' + 'sPK.key', 'rb') as fp:
        sPK = pickle.load(fp)

    with open(os.getcwd() + '/keys/' + 'sPK1.key', 'rb') as fp:
        sPK1 = pickle.load(fp)

    sPK2s = []
    for i in range(N):
        with open(os.getcwd() + '/keys/' + 'sPK2-' + str(i) + '.key', 'rb') as fp:
            sPK2s.append(PublicKey(pickle.load(fp)))

    with open(os.getcwd() + '/keys/' + 'ePK.key', 'rb') as fp:
        ePK = pickle.load(fp)

    with open(os.getcwd() + '/keys/' + 'sSK-' + str(id) + '.key', 'rb') as fp:
        sSK = pickle.load(fp)

    with open(os.getcwd() + '/keys/' + 'sSK1-' + str(id) + '.key', 'rb') as fp:
        sSK1 = pickle.load(fp)

    with open(os.getcwd() + '/keys/' + 'sSK2-' + str(id) + '.key', 'rb') as fp:
        sSK2 = PrivateKey(pickle.load(fp))

    with open(os.getcwd() + '/keys/' + 'eSK-' + str(id) + '.key', 'rb') as fp:
        eSK = pickle.load(fp)

    return sPK, sPK1, sPK2s, ePK, sSK, sSK1, sSK2, eSK


class MuleBFTNode (Mule, Process):

    def __init__(self, sid, id, S, T, Bfast, Bacs, N, f, recv_q: mpQueue, send_q: List[mpQueue], ready: mpValue, stop: mpValue, K=3, mode='debug', mute=False, tx_buffer=None):
        self.sPK, self.sPK1, self.sPK2s, self.ePK, self.sSK, self.sSK1, self.sSK2, self.eSK = load_key(id, N)
        self.recv_queue = recv_q
        self.send_queues = send_q
        self.ready = ready
        self.stop = stop
        self.mode = mode
        Mule.__init__(self, sid, id, S, T, max(int(Bfast/N), 1), max(int(Bacs/N), 1), N, f, self.sPK, self.sSK, self.sPK1, self.sSK1, self.sPK2s, self.sSK2, self.ePK, self.eSK, send=None, recv=None, K=K, mute=mute)
        Process.__init__(self)

    def prepare_bootstrap(self):
        self.logger.info('node id %d is inserting dummy payload TXs' % (self.id))

        # tx = tx_generator(250)  # Set each dummy TX to be 250 Byte
 
        # ran1 = random.randint(100,250)
        # ran2 = random.randint(100,250)
        # tx = tx_generator(ran1)
        # tx2 = tx_generator(ran2)
        # self.logger.info('node id %d and size %d' % (self.id, ran1))
        # self.logger.info('node id %d and size2 %d' % (self.id, ran2))
        # count1 = 0
        # count2 = 0

        # if self.mode == 'test' or 'debug': #K * max(Bfast * S, Bacs)
        #     k = 0
        #     for _ in range(self.K + 1):
        #         for r in range(max(self.FAST_BATCH_SIZE * self.SLOTS_NUM, self.FALLBACK_BATCH_SIZE)):
        #             suffix = hex(self.id) + hex(r) + ">"
        #             choose = random.choice([1,2])
        #             if (choose == 1) :
        #                 Mule.submit_tx(self, tx[:-len(suffix)] + suffix)
        #                 count1 = count1 + 1
        #             else :
        #                 Mule.submit_tx(self, tx2[:-len(suffix)] + suffix)
        #                 count2 = count2 + 1
        #             k += 1
        #             if r % 50000 == 0:
        #                 self.logger.info('node id %d just inserts 50000 TXs' % (self.id))
        # else:
        #     pass
        #     # TODO: submit transactions through tx_buffer
        # self.logger.info('node id %d completed the loading of dummy TXs' % (self.id))
        # self.logger.info('node id %d and count %d' % (self.id, count1))
        # self.logger.info('node id %d and count2 %d' % (self.id, count2))
        tx = tx_generator(250)

        if self.mode == 'test' or 'debug': #K * max(Bfast * S, Bacs)
            k = 0
            for _ in range(self.K + 1):
                for r in range(max(self.FAST_BATCH_SIZE * self.SLOTS_NUM, self.FALLBACK_BATCH_SIZE)):
                    suffix = hex(self.id) + hex(r) + ">"
                    Mule.submit_tx(self, tx[:-len(suffix)] + suffix)
                    k += 1
                    if r % 50000 == 0:
                        self.logger.info('node id %d just inserts 50000 TXs' % (self.id))
        else:
            pass
            # TODO: submit transactions through tx_buffer
        self.logger.info('node id %d completed the loading of dummy TXs' % (self.id))

    def run(self):

        pid = os.getpid()
        self.logger.info('node %d\'s starts to run consensus on process id %d' % (self.id, pid))

        self._send = lambda j, o: self.send_queues[j].put_nowait(o)
        self._recv = lambda: self.recv_queue.get_nowait()

        self.prepare_bootstrap()

        while not self.ready.value:
            time.sleep(1)
            pass

        time.sleep(4)
        print(self.ready.value)

        self.run_bft()
        self.stop.value = True


def main(sid, i, S, T, B, N, f, addresses, K):
    mule = MuleBFTNode(sid, i, S, T, B, N, f, addresses, K)
    mule.run_bft()


if __name__ == '__main__':

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--sid', metavar='sid', required=True,
                        help='identifier of node', type=str)
    parser.add_argument('--id', metavar='id', required=True,
                        help='identifier of node', type=int)
    parser.add_argument('--N', metavar='N', required=True,
                        help='number of parties', type=int)
    parser.add_argument('--f', metavar='f', required=True,
                        help='number of faulties', type=int)
    parser.add_argument('--B', metavar='B', required=True,
                        help='size of batch', type=int)
    parser.add_argument('--K', metavar='K', required=True,
                        help='rounds to execute', type=int)
    args = parser.parse_args()

    # Some parameters
    sid = args.sid
    i = args.id
    N = args.N
    f = args.f
    B = args.B
    K = args.K

    # Epoch Setup
    S = 50
    T = 0.05  # Timeout

    # Random generator
    rnd = random.Random(sid)

    # Nodes list
    host = "127.0.0.1"
    port_base = int(rnd.random() * 5 + 1) * 10000
    addresses = [(host, port_base + 200 * i) for i in range(N)]
    print(addresses)

    main(sid, i, S, T, B, N, f, addresses, K)
