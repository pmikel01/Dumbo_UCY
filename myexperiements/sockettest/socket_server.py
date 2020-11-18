import time
import pickle
import gevent
import os

from multiprocessing.queues import Queue as mpQueue

from gevent import Greenlet
from gevent import socket, monkey, lock
from gevent.queue import Queue
import logging
import traceback

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

    SEP = '\r\nSEP\r\nSEP\r\nSEP\r\n'

    def __init__(self, port: int, ip: str, id: int, addresses_list: list, logger=None):

        self.SOCK_NUM = 2

        self.recv_queue = Queue()
        self.send_queue = Queue()

        self.ip = ip
        self.port = port
        self.id = id
        self.addresses_list = addresses_list
        self.socks = [ [None] * self.SOCK_NUM for _ in self.addresses_list]
        if logger is None:
            self.logger = set_logger_of_node(self.id)
        else:
            self.logger = logger
        self.is_out_sock_connected = [False] * len(self.addresses_list)
        self.is_in_sock_connected = [False] * len(self.addresses_list)
        self.stop = False
        self.s_locks = [lock.BoundedSemaphore(self.SOCK_NUM) for _ in range(len(self.addresses_list))]

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
            while not self.stop:
                gevent.sleep(0)
                buf += sock.recv(5000)
                tmp = buf.split(self.SEP.encode('utf-8'), 1)
                while len(tmp) == 2:
                    buf = tmp[1]
                    data = tmp[0]
                    if data != '' and data:
                        if data == 'ping'.encode('utf-8'):
                            sock.sendall('pong'.encode('utf-8'))
                            self.logger.info("node {} is pinging node {}...".format(self._address_to_id(address), self.id))
                            self.is_in_sock_connected[self._address_to_id(address)] = True
                        else:
                            (j, o) = (self._address_to_id(address), pickle.loads(data))
                            assert j in range(len(self.addresses_list))
                            gevent.spawn(self.recv_queue.put_nowait((j, o)))
                    else:
                        self.logger.error('syntax error messages')
                        raise ValueError
                    tmp = buf.split(self.SEP.encode('utf-8'), 1)
        except Exception as e:
            self.logger.error(str((e, traceback.print_exc())))
            #_finish(e)

    def _serve_forever(self):
        print("my IP is " + self.ip)
        self.server_sock = socket.socket()
        self.server_sock.bind((self.ip, self.port))
        self.server_sock.listen(5)
        while not self.stop:
            sock, address = self.server_sock.accept()
            gevent.spawn(self._handle_request, sock, address)
            self.logger.info('node id %d accepts a new socket from node %d' % (self.id, self._address_to_id(address)))
            gevent.sleep(0)

    def _watchdog_deamon(self):
        pass

    def connect_all(self):
        self.logger.info("node %d is establishing outgoing connections to the network" % self.id)
        while not self.stop:
            gevent.sleep(0)
            time.sleep(0)
            try:
                for j in range(len(self.addresses_list)):
                    if not self.is_out_sock_connected[j]:
                        self.is_out_sock_connected[j] = self._connect(j)
                if all(self.is_out_sock_connected) and all(self.is_in_sock_connected):
                    break
            except Exception as e:
                self.logger.info(str((e, traceback.print_exc())))
        #send_thread = gevent.spawn(self.send_loop)
        #return send_thread

    def _connect(self, j: int):
        for k in range(self.SOCK_NUM):
            sock = socket.socket()
            sock.bind((self.ip, self.port + self.SOCK_NUM * j + 1 + k))
            try:
                sock.connect(self.addresses_list[j])
                sock.sendall(('ping' + self.SEP).encode('utf-8'))
                pong = sock.recv(5000)
            except Exception as e1:
                return False
            #print(e1)
            #traceback.print_exc()
            if pong.decode('utf-8') == 'pong':
                self.logger.info("node {} is ponging node {}...".format(j, self.id))
                self.socks[j][k] = sock
            else:
                self.logger.info("fails to build connect from {} to {}".format(self.id, j))
                return False
        return True

    def _send(self, j: int, o: bytes, select: int):
        msg = b''.join([o, self.SEP.encode('utf-8')])
        #with self.s_lock:
        for _ in range(3):
            try:
                self.socks[j][select].sendall(msg)
                break
            except Exception as e1:
                self.logger.error("fail to send msg")
                self.logger.error(str((e1, traceback.print_exc())))
                continue

            #print("fail to send msg")
            #try:
            #    self._connect(j)
            #    self.socks[j].connect(self.addresses_list[j])
            #    self.socks[j].sendall(msg)
            #except Exception as e2:
            #    self.logger.error(str((e1, e2, traceback.print_exc())))

    # def send(self, j: int, o: object):
    #     try:
    #         self._send(j, pickle.dumps(o))
    #     except Exception as e:
    #         self.logger.error(str(("problem objective when sending", o)))
    #         traceback.print_exc(e)

    def send(self, j: int, o: object):
        with self.s_locks[j]:
            try:
                self._send(j, pickle.dumps(o), self.s_locks[j].counter)
            except Exception as e:
                self.logger.error(str(("problem objective when sending", o)))
                traceback.print_exc()

    # def send(self, j: int, o: object):
    #     self.send_queue.put((j, o))
    #     print("send msg to " + str(j))
    #     gevent.sleep(0)
    #     time.sleep(0)

    # def send_loop(self):
    #     selectors = [0] * len(self.addresses_list)
    #     while True:
    #         gevent.sleep(0)
    #         time.sleep(0)
    #         try:
    #             (j, o) = self.send_queue.get_nowait()
    #             selectors[j] = (selectors[j] + 1) % self.SOCK_NUM
    #             try:
    #                 self._send(j, pickle.dumps(o), selectors[j])
    #             except Exception as e:
    #                 self.logger.error(str(("problem objective when sending", o)))
    #                 traceback.print_exc(e)
    #         except:
    #             continue

    def _recv(self):
        (i, o) = self.recv_queue.get()
        #print("recv msg from " + str(i))
        gevent.sleep(0)
        time.sleep(0)
        return (i, o)


    def recv(self):
        return self._recv()

    def stop_service(self):
        self.stop = True

    def _address_to_id(self, address: tuple):
        # print(address)
        # print(self.addresses_list)
        # assert address in self.addresses_list
        for i in range(len(self.addresses_list)):
            if address[0] != '127.0.0.1' and address[0] == self.addresses_list[i][0]:
                return i
        return int((address[1] - 10000) / 200)


