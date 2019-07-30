import random
import logging

from mytest.mysockettest.socket_node import Node
from honeybadgerbft.core.honeybadger import HoneyBadgerBFT
from honeybadgerbft.crypto.threshsig.boldyreva import dealer
from honeybadgerbft.crypto.threshenc import tpke

import time
import traceback

from multiprocessing import Process, Pool
from gevent import socket, monkey, Greenlet
from gevent.queue import Queue

monkey.patch_all()




class HoneyBadgerInstance (HoneyBadgerBFT, Greenlet):
#class HoneyBadgerInstance (HoneyBadgerBFT, Process):
#class HoneyBadgerInstance (HoneyBadgerBFT):
    def __init__(self, sid, pid, B, N, f, sPK, sSK, ePK, eSK, node, K=3):
        Greenlet.__init__(self)
        #Process.__init__(self)
        self.node = node
        self.node.start()
        HoneyBadgerBFT.__init__(self, sid, pid, B, N, f, sPK, sSK, ePK, eSK, node.send, node.recv, K=3)

    def connect_all(self):
        print('is fully meshing the network...')
        self.node.connect_all()

    def _run(self):
        HoneyBadgerBFT.run(self)


def sockets_router(N):
    """Builds a set of connected channels, with random delay

    :return: (receives, sends)
    """
    rnd = random.Random()

    queues = [Queue() for _ in range(N)]
    #_threads = []

    host = "127.0.0.1"
    port_base = int(rnd.random() * 5 + 1) * 10000
    addresses = [(host, port_base + 200 * i) for i in range(N)]
    nodes = [Node(port=addresses[i][1], i=i, nodes_list=addresses, queue=queues[i]) for i in range(N)]

    return nodes





### Test asynchronous common subset
def _test_honeybadger(N=4, f=1, seed=None):
    sid = 'sidA'
    # Generate threshold sig keys
    sPK, sSKs = dealer(N, f+1, seed=seed)

    # Generate threshold enc keys
    ePK, eSKs = tpke.dealer(N, f+1)

    rnd = random.Random(seed)
    #print 'SEED:', seed
    router_seed = rnd.random()
    nodes = sockets_router(N)

    badgers = [None] * N

    # This is an experiment parameter to specify the maximum round number 
    K = 1

    for i in range(N):
        badgers[i] = HoneyBadgerInstance(sid, i, 1, N, f,
                                    sPK, sSKs[i], ePK, eSKs[i],
                                    nodes[i], K)

    time.sleep(3)

    for i in range(N):
        badgers[i].connect_all()
        for r in range(K):
            badgers[i].submit_tx('<[HBBFT Input %d]>' % (i + 10 * r))

    time.sleep(1)

    print('start the test...')
    time_start = time.time()



    for i in range(N):
        badgers[i].start()

    for i in range(N):
        badgers[i].join()



    time_end = time.time()
    print('complete the test...')
    print('time cost: ', time_end-time_start, 's')


def test_honeybadger():
    FORMAT = "%(asctime)s %(thread)d %(message)s"
    logging.basicConfig(level=logging.WARNING, format=FORMAT, datefmt="[%Y-%m-%d %H:%M:%S]")
    root = logging.getLogger()
    _test_honeybadger()


if __name__ == '__main__':
    test_honeybadger()
