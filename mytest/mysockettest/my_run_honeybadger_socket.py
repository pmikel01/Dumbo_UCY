import random
import gevent
from gevent import monkey
from gevent.queue import Queue

import honeybadgerbft.core.honeybadger
#reload(honeybadgerbft.core.honeybadger)
from honeybadgerbft.core.honeybadger import HoneyBadgerBFT
from honeybadgerbft.crypto.threshsig.boldyreva import dealer
from honeybadgerbft.crypto.threshenc import tpke
from honeybadgerbft.core.honeybadger import BroadcastTag

import time, logging

from multiprocessing import Process
from mytest.mysockettest.socket_node import Node


monkey.patch_all()


def simple_router(N, maxdelay=0, seed=None):
    """Builds a set of connected channels, with random delay

    :return: (receives, sends)
    """
    rnd = random.Random()

    host = "127.0.0.1"
    port_base = int(rnd.random() * 5 + 1) * 10000
    addresses = [(host, port_base + 200 * i) for i in range(N)]
    queues = [Queue() for _ in range(N)]
    nodes = [Node(port=addresses[i][1], i=i, nodes_list=addresses, queue=queues[i]) for i in range(N)]

    for node in nodes:
        node.start()

    for node in nodes:
        node.connect_all()

    def makeRecv(j):
        def _recv():
            (i, o) = nodes[j].recv()
            return (i, o)
        return _recv

    def makeSend(i):
        def _send(j, o):
            gevent.spawn(nodes[i].send(j, o))
        return _send

    return ([makeSend(i) for i in range(N)],
            [makeRecv(j) for j in range(N)])


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
    sends, recvs = simple_router(N, seed=router_seed)

    badgers = [None] * N
    threads = [None] * N
    
    # This is an experiment parameter to specify the maximum round number 
    K = 2




    for i in range(N):
        badgers[i] = HoneyBadgerBFT(sid, i, 1, N, f,
                                    sPK, sSKs[i], ePK, eSKs[i],
                                    sends[i], recvs[i], K)
        #print(sPK, sSKs[i], ePK, eSKs[i])
        #print(sPK, sSKs[i], ePK, eSKs[i])



    for r in range(K):
        for i in range(N):
            #if i == 1: continue
            badgers[i].submit_tx('<[HBBFT Input %d]>' % (i+10*r))

    for i in range(N):
        threads[i] = gevent.spawn(badgers[i].run)



    print('start the test...')
    time_start=time.time()

    print(logger)

    #gevent.killall(threads[N-f:])
    #gevent.sleep(3)
    #for i in range(N-f, N):
    #    inputs[i].put(0)
    try:
        outs = [threads[i].get() for i in range(N)]
        print(outs)
        # Consistency check
        assert len(set(outs)) == 1
    except KeyboardInterrupt:
        gevent.killall(threads)
        raise

    time_end=time.time()
    print('complete the test...')
    print('time cost: ', time_end-time_start, 's')


def test_honeybadger():
    _test_honeybadger()


if __name__ == '__main__':
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler('debug.log')
    logger.addHandler(fh)

    test_honeybadger()
