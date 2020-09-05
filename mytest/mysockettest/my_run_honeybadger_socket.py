import random
import pickle
import gevent
from gevent import monkey
from gevent.queue import Queue
import io

import honeybadgerbft.core.honeybadger
#reload(honeybadgerbft.core.honeybadger)
from honeybadgerbft.core.honeybadger import HoneyBadgerBFT
from honeybadgerbft.crypto.threshsig.boldyreva import dealer, deserialize2, serialize
from honeybadgerbft.crypto.threshenc import tpke
from honeybadgerbft.core.honeybadger import BroadcastTag

import time, logging, os
import multiprocessing
from multiprocessing import Process, Pool, Lock, Manager
from mytest.mysockettest.socket_node import Node, HoneyBadgerBFTNode
from mytest.mysockettest.trusted_key_gen import *


monkey.patch_all()



def _test_honeybadger_2(N=4, f=1, seed=None):

    def run_hbbft_instance(badger: HoneyBadgerBFTNode, threads: multiprocessing.Queue):

        # lock.acquire()
        # print(pid, "gets lock to start server")
        badger.start_server()
        # lock.release()
        # print(pid, "releases lock after starting server")

        time.sleep(2)
        gevent.sleep(2)

        # lock.acquire()
        # print(pid, "gets lock to fully connect")
        badger.connect_servers()
        # lock.release()
        # print(pid, "releases lock after fully connecting")

        thread = gevent.spawn(badger.run())
        threads.put(thread)
        return thread

    rnd = random.Random(seed)

    sid = 'sidA'
    trusted_key_gen(N)

    # Nodes list
    host = "127.0.0.1"
    port_base = int(rnd.random() * 5 + 1) * 10000
    addresses = [(host, port_base + 200 * i) for i in range(N)]
    print(addresses)

    K = 100
    B = 2
    badgers = [None] * N
    processes = [None] * N
    threads = multiprocessing.Queue()

    for i in range(N):
        badgers[i] = HoneyBadgerBFTNode(sid, i, B, N, f, addresses_list=addresses, K=K)

    for i in range(N):
        processes[i] = Process(target=run_hbbft_instance, args=(badgers[i], threads, ))
        processes[i].start()
        processes[i].join()

    while threads.qsize() != N:
        pass

    print("finished")

    # outs = [None] * N
    # try:
    #     for i in range(N):
    #         outs[i] = threads.get()
    #     print(outs)
    #     # Consistency check
    #     assert len(set(outs)) == 1
    # except KeyboardInterrupt:
    #     gevent.killall(threads)
    #     raise
    #time.sleep(5)
    #print("parent is waiting...", threads.qsize())


# Test by processes
def test_honeybadger_proc():
    _test_honeybadger_2()

if __name__ == '__main__':
    test_honeybadger_proc()
