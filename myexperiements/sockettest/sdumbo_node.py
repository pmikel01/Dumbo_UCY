from gevent import monkey; monkey.patch_all(thread=False)

import random
from typing import  Callable
import os
import pickle
from gevent import time, Greenlet
from speedydumbobft.core.speedydumbo import SpeedyDumbo
from myexperiements.sockettest.make_random_tx import tx_generator
from multiprocessing import Value as mpValue
from coincurve import PrivateKey, PublicKey
from ctypes import c_bool

def load_key(id, N):

    with open(os.getcwd() + '/keys-' + str(N) + '/' + 'sPK.key', 'rb') as fp:
        sPK = pickle.load(fp)

    with open(os.getcwd() + '/keys-' + str(N) + '/' + 'sPK1.key', 'rb') as fp:
        sPK1 = pickle.load(fp)

    sPK2s = []
    for i in range(N):
        with open(os.getcwd() + '/keys-' + str(N) + '/' + 'sPK2-' + str(i) + '.key', 'rb') as fp:
            sPK2s.append(PublicKey(pickle.load(fp)))

    with open(os.getcwd() + '/keys-' + str(N) + '/' + 'ePK.key', 'rb') as fp:
        ePK = pickle.load(fp)

    with open(os.getcwd() + '/keys-' + str(N) + '/' + 'sSK-' + str(id) + '.key', 'rb') as fp:
        sSK = pickle.load(fp)

    with open(os.getcwd() + '/keys-' + str(N) + '/' + 'sSK1-' + str(id) + '.key', 'rb') as fp:
        sSK1 = pickle.load(fp)

    with open(os.getcwd() + '/keys-' + str(N) + '/' + 'sSK2-' + str(id) + '.key', 'rb') as fp:
        sSK2 = PrivateKey(pickle.load(fp))

    with open(os.getcwd() + '/keys-' + str(N) + '/' + 'eSK-' + str(id) + '.key', 'rb') as fp:
        eSK = pickle.load(fp)

    return sPK, sPK1, sPK2s, ePK, sSK, sSK1, sSK2, eSK

class SDumboBFTNode (SpeedyDumbo):

    def __init__(self, sid, id, B, N, f, bft_from_server: Callable, bft_to_client: Callable, ready: mpValue, stop: mpValue, K=3, mode='debug', mute=False, debug=False, network: mpValue=mpValue(c_bool, True), tx_buffer=None):
        self.sPK, self.sPK1, self.sPK2s, self.ePK, self.sSK, self.sSK1, self.sSK2, self.eSK = load_key(id, N)
        self.bft_from_server = bft_from_server
        self.bft_to_client = bft_to_client
        self.send = lambda j, o: self.bft_to_client((j, o))
        self.recv = lambda: self.bft_from_server()
        self.ready = ready
        self.stop = stop
        self.mode = mode
        self.network = network
        self.tpt = 15000 #transactions per time
        SpeedyDumbo.__init__(self, sid, id, max(int(B/N), 1), N, f, self.sPK, self.sSK, self.sPK1, self.sSK1, self.sPK2s, self.sSK2, self.ePK, self.eSK, self.send, self.recv, K=K, mute=mute, debug=debug)

    # def prepare_bootstrap(self):
    #     self.logger.info('node id %d is inserting dummy payload TXs' % (self.id))
    #     if self.mode == 'test' or 'debug': #K * max(Bfast * S, Bacs)
    #         tx = tx_generator(250)  # Set each dummy TX to be 250 Byte
    #         k = 0
    #         for _ in range(self.K):
    #             for r in range(self.B):
    #                 SpeedyDumbo.submit_tx(self, tx.replace(">", hex(r) + ">"))
    #                 k += 1
    #                 if r % 50000 == 0:
    #                     self.logger.info('node id %d just inserts 50000 TXs' % (self.id))
    #     else:
    #         pass
    #         # TODO: submit transactions through tx_buffer
    #     self.logger.info('node id %d completed the loading of dummy TXs' % (self.id))

    def prepare_bootstrap2(self):
        self.logger.info('node id %d started inserting dummy payload TXs' % (self.id))
        k = 0
        while not self.stop.value:
            if self.mode == 'test' or 'debug': #K * max(Bfast * S, Bacs)
                # 100 tx`s each time`
                for r in range(self.tpt):
                    id = str(self.id) + "-" + str(k)
                    tx = tx_generator(id)
                    SpeedyDumbo.submit_tx(self, tx)
                    k += 1
                    if (r % 50000 == 0) and (r != 0):
                        self.logger.info('node id %d just inserts 50000 TXs' % (self.id))
            else:
                pass
                # TODO: submit transactions through tx_buffer
            self.logger.info('node id %d completed the loading of %d dummy TXs' % (self.id, k))
            time.sleep(1)
# prepare_bootstrap_without_infinite_loop
    def prepare_bootstrap(self):
        self.logger.info('node id %d started inserting dummy payload TXs' % (self.id))
        k = 0
        if self.mode == 'test' or 'debug': #K * max(Bfast * S, Bacs)
            # 100 tx`s each time`

            for r in range(self.tpt):
                id = str(self.id) + "-" + str(k)
                tx = tx_generator(id)  # Set each dummy TX to be 250 Byte
                SpeedyDumbo.submit_tx(self, tx)
                k += 1
                if (r % 50000 == 0) and (r != 0):
                    self.logger.info('node id %d just inserts 50000 TXs' % (self.id))
        else:
            pass
            # TODO: submit transactions through tx_buffer
        self.logger.info('node id %d completed the loading of %d dummy TXs' % (self.id, k))

    def run(self):

        pid = os.getpid()
        self.logger.info('node %d\'s starts to run consensus on process id %d' % (self.id, pid))


        self.prepare_bootstrap()

        while not self.ready.value:
            time.sleep(1)
            #gevent.sleep(1)

        def _change_network():
            seconds = 0
            while True:
                time.sleep(1)
                seconds += 1
                if seconds % 30 == 0:
                    if seconds % 30 % 2 == 1:
                        self.network.value = False
                        print("change to bad network....")
                    else:
                        self.network.value = True
                        print("change to good network....")

        Greenlet(_change_network).start()

        self.run_bft()
        self.stop.value = True

def main(sid, i, B, N, f, addresses, K):
    badger = SDumboBFTNode(sid, i, B, N, f, addresses, K)
    badger.run_bft()


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

    # Random generator
    rnd = random.Random(sid)

    # Nodes list
    host = "127.0.0.1"
    port_base = int(rnd.random() * 5 + 1) * 10000
    addresses = [(host, port_base + 200 * i) for i in range(N)]
    print(addresses)

    main(sid, i, B, N, f, addresses, K)
