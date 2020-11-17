import random
import gevent
import os
import pickle

from gevent import time
from mulebft.core.mule import Mule
from myexperiements.sockettest.make_random_tx import tx_generator
from myexperiements.sockettest.socket_server import Node, set_logger_of_node
from coincurve import PrivateKey, PublicKey


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


class MuleBFTNode (Mule):

    def __init__(self, sid, id, S, T, Bfast, Bacs, N, f, my_address: str, addresses_list: list, K=3, mode='debug', mute=False, tx_buffer=None):
        self.sPK, self.sPK1, self.sPK2s, self.ePK, self.sSK, self.sSK1, self.sSK2, self.eSK = load_key(id, N)
        Mule.__init__(self, sid, id, S, T, Bfast, Bacs, N, f, self.sPK, self.sSK, self.sPK1, self.sSK1, self.sPK2s, self.sSK2, self.ePK, self.eSK, send=None, recv=None, K=K, logger=set_logger_of_node(id), mute=mute)
        self.server = Node(id=id, ip=my_address, port=addresses_list[id][1], addresses_list=addresses_list, logger=self.logger)
        self.mode = mode

    def prepare_bootstrap(self):
        self.logger.info('node id %d is inserting dummy payload TXs' % (self.id))
        tx = tx_generator(250)  # Set each dummy TX to be 250 Byte
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


    def start_socket_server(self):
        pid = os.getpid()
        #print('pid: ', pid)
        self.logger.info('node id %d is running on pid %d' % (self.id, pid))
        self.server.start()

    def connect_socket_servers(self):
        self.server.connect_all()
        self._send = self.server.send
        self._recv = self.server.recv

    def run_mule_instance(self):

        gevent.spawn(self.prepare_bootstrap).join()

        self.start_socket_server()
        time.sleep(3)
        gevent.sleep(3)

        self.connect_socket_servers()
        time.sleep(4)
        gevent.sleep(4)

        self.run()
        time.sleep(3)
        gevent.sleep(3)

        self.server.stop_service()
        time.sleep(3)
        gevent.sleep(3)

def main(sid, i, S, T, B, N, f, addresses, K):
    mule = MuleBFTNode(sid, i, S, T, B, N, f, addresses, K)
    mule.run_mule_instance()


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
