import time

import gevent
from gevent import Greenlet
from gevent import socket, monkey
from gevent.queue import Queue
from honeybadgerbft.core.honeybadger import HoneyBadgerBFT
import logging
import traceback

from myexperiements.mysockettest.load_key_files import *
from myexperiements.mysockettest.make_random_tx import *

monkey.patch_all()


def set_logger_of_node(id: int):
    logger = logging.getLogger("node-"+str(id))
    logger.setLevel(logging.DEBUG)
    # logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)s %(filename)s [line:%(lineno)d] %(funcName)s %(levelname)s %(message)s ')
    if 'log' not in os.listdir(os.getcwd()):
        os.mkdir(os.getcwd() + '/log')
    full_path = os.path.realpath(os.getcwd()) + '/log/' + "node-"+str(id) + ".log"
    file_handler = logging.FileHandler(full_path)
    file_handler.setFormatter(formatter)  # 可以通过setFormatter指定输出格式
    logger.addHandler(file_handler)
    return logger


# Network node class: deal with socket communications
class Node(Greenlet):

    SEP = '\r\nSEP\r\n'

    def __init__(self, port: int, ip: str, id: int, addresses_list: list, logger=None):
        self.queue = Queue()
        self.ip = ip
        self.port = port
        self.id = id
        self.addresses_list = addresses_list
        self.socks = [None for _ in self.addresses_list]
        if logger is None:
            self.logger = set_logger_of_node(self.id)
        else:
            self.logger = logger
        Greenlet.__init__(self)

    def _run(self):
        self.logger.info("node %d starts to run..." % self.id)
        self._serve_forever()

    def _handle_request(self, sock, address):

        def _finish(e: Exception):
            self.logger.error("node %d's server is closing..." % self.id)
            self.logger.error(str(e))
            print(e)
            print("node %d's server is closing..." % self.id)
            pass

        buf = b''
        try:
            while True:
                gevent.sleep(0)
                buf += sock.recv(4096)
                tmp = buf.split(self.SEP.encode('utf-8'), 1)
                while len(tmp) == 2:
                    buf = tmp[1]
                    data = tmp[0]
                    if data != '' and data:
                        if data == 'ping'.encode('utf-8'):
                            sock.sendall('pong'.encode('utf-8'))
                            self.logger.info("node {} is pinging node {}...".format(self._address_to_id(address), self.id))
                        else:
                            (j, o) = (self._address_to_id(address), pickle.loads(data))
                            assert j in range(len(self.addresses_list))
                            gevent.spawn(self.queue.put_nowait((j, o)))
                    else:
                        self.logger.error('syntax error messages')
                        raise ValueError
                    tmp = buf.split(self.SEP.encode('utf-8'), 1)
        except Exception as e:
            self.logger.error(str((e, traceback.print_exc())))
            _finish(e)

    def _serve_forever(self):
        self.server_sock = socket.socket()
        self.server_sock.bind((self.ip, self.port))
        self.server_sock.listen(5)
        while True:
            sock, address = self.server_sock.accept()
            gevent.spawn(self._handle_request, sock, address)
            self.logger.info('node id %d accepts a new socket from node %d' % (self.id, self._address_to_id(address)))
            gevent.sleep(0)

    def _watchdog_deamon(self):
        pass

    def connect_all(self):
        self.logger.info("node %d is fully meshing the network" % self.id)
        is_sock_connected = [False] * len(self.addresses_list)
        while True:
            try:
                for j in range(len(self.addresses_list)):
                    if not is_sock_connected[j]:
                        is_sock_connected[j] = self._connect(j)
                if all(is_sock_connected):
                    break
                time.sleep(1)
            except Exception as e:
                self.logger.info(str((e, traceback.print_exc())))

    def _connect(self, j: int):
        sock = socket.socket()
        sock.bind((self.ip, self.port + j + 1))
        try:
            sock.connect(self.addresses_list[j])
            sock.sendall(('ping' + self.SEP).encode('utf-8'))
            pong = sock.recv(4096)
        except Exception as e1:
            return False
            #print(e1)
            #traceback.print_exc()
        if pong.decode('utf-8') == 'pong':
            self.logger.info("node {} is ponging node {}...".format(j, self.id))
            self.socks[j] = sock
            return True
        else:
            self.logger.info("fails to build connect from {} to {}".format(self.id, j))
            return False

    def _send(self, j: int, o: bytes):
        msg = b''.join([o, self.SEP.encode('utf-8')])
        try:
            self.socks[j].sendall(msg)
        except Exception as e1:
            self.logger.error("fail to send msg")
            #print("fail to send msg")
            try:
                self._connect(j)
                self.socks[j].connect(self.addresses_list[j])
                self.socks[j].sendall(msg)
            except Exception as e2:
                self.logger.error(str((e1, e2, traceback.print_exc())))

    def send(self, j: int, o: object):
        try:
            self._send(j, pickle.dumps(o))
        except Exception as e:
            self.logger.error(str(("problem objective when sending", o)))
            traceback.print_exc(e)

    def _recv(self):
        #time.sleep(0.001)
        #try:
        (i, o) = self.queue.get()
        #print("node %d is receving: " % self.id, (i, o))
        return (i, o)
        #except Exception as e:
        #   print(e)
        #   pass

    def recv(self):
        return self._recv()

    def _address_to_id(self, address: tuple):
        # print(address)
        # print(self.addresses_list)
        # assert address in self.addresses_list
        for i in range(len(self.addresses_list)):
            if address[0] != '127.0.0.1' and address[0] == self.addresses_list[i][0]:
                return i
        return int((address[1] - 10007) / 200)


# Well defined node class to encapsulate almost everything
class HoneyBadgerBFTNode (HoneyBadgerBFT):

    def __init__(self, sid, id, B, N, f, addresses_list: list, K=3, mode='debug', tx_buffer=None):
        self.sPK, self.ePK, self.sSK, self.eSK = load_key(id)
        HoneyBadgerBFT.__init__(self, sid, id, B, N, f, self.sPK, self.sSK, self.ePK, self.eSK, send=None, recv=None, K=K, logger=set_logger_of_node(id))
        self.server = Node(id=id, ip=addresses_list[id][0], port=addresses_list[id][1], addresses_list=addresses_list, logger=self.logger)
        self.mode = mode
        self._prepare_bootstrap()

    def _prepare_bootstrap(self):
        if self.mode == 'test' or 'debug':
            for r in range(self.K * self.B):
                tx = tx_generator(250) # Set each dummy TX to be 250 Byte
                HoneyBadgerBFT.submit_tx(self, tx)
        else:
            pass
            # TODO: submit transactions through tx_buffer

    def start_socket_server(self):
        pid = os.getpid()
        #print('pid: ', pid)
        self.logger.info('node id %d is running on pid %d' % (self.id, pid))
        self.server.start()

    def connect_socket_servers(self):
        self.server.connect_all()
        self._send = self.server.send
        self._recv = self.server.recv

    def run_hbbft_instance(self):
        self.start_socket_server()
        time.sleep(3)
        gevent.sleep(3)
        self.connect_socket_servers()
        time.sleep(3)
        gevent.sleep(3)
        self.run()


def main(sid, i, B, N, f, addresses, K):
    badger = HoneyBadgerBFTNode(sid, i, B, N, f, addresses, K)
    badger.run_hbbft_instance()


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
