import time
import pickle
from typing import List

import gevent
import os

from multiprocessing import Value as mpValue, Queue as mpQueue, Process, Semaphore as mpSemaphore
from gevent import socket, monkey, lock
from multiprocessing.connection import Connection

import logging
import traceback

monkey.patch_all()



# Network node class: deal with socket communications
class NetworkClient (Process):

    SEP = '\r\nSEP\r\nSEP\r\nSEP\r\n'

    def __init__(self, port: int, my_ip: str, id: int, addresses_list: list, client_from_bft: Connection, client_ready: mpValue, stop: mpValue):

        self.client_from_bft = client_from_bft
        self.ready = client_ready
        self.stop = stop

        self.ip = my_ip
        self.port = port
        self.id = id
        self.addresses_list = addresses_list
        self.N = len(self.addresses_list)


        self.is_out_sock_connected = [False] * self.N

        self.socks = [None for _ in self.addresses_list]
        self.sock_locks = [lock.Semaphore() for _ in self.addresses_list]

        super().__init__()


    def _connect_and_send_forever(self):
        pid = os.getpid()
        self.logger.info('node %d\'s socket client starts to make outgoing connections on process id %d' % (self.id, pid))
        while not self.stop.value:

            try:
                for j in range(self.N):
                    if not self.is_out_sock_connected[j]:
                        self.is_out_sock_connected[j] = self._connect(j)
                if all(self.is_out_sock_connected):
                    with self.ready.get_lock():
                        self.ready.value = True
                    break
            except Exception as e:
                self.logger.info(str((e, traceback.print_exc())))

        #send_thread = [gevent.spawn(self._send_loop, j) for j in range(self.N)]
        #gevent.joinall(send_threads)
        self._send_loop()

    def _connect(self, j: int):
        sock = socket.socket()
        if self.ip == '127.0.0.1':
            sock.bind((self.ip, self.port + j + 1))
        try:
            sock.connect(self.addresses_list[j])
            sock.sendall(('ping' + self.SEP).encode('utf-8'))
            pong = sock.recv(5000)
        except Exception as e1:
            return False
        if pong.decode('utf-8') == 'pong':
            self.logger.info("node {} is ponging node {}...".format(j, self.id))
            self.socks[j] = sock
        else:
            self.logger.info("fails to build connect from {} to {}".format(self.id, j))
            return False
        return True

    def _send(self, j: int, o: bytes):
        msg = b''.join([o, self.SEP.encode('utf-8')])
        self.sock_locks[j].acquire()
        for _ in range(3):
            try:
                self.socks[j].sendall(msg)
                break
            except Exception as e1:
                self.logger.error("fail to send msg")
                self.logger.error(str((e1, traceback.print_exc())))
                continue
        self.sock_locks[j].release()

    ##
    ##
    def _send_loop(self):

        while not self.stop.value:
            try:
                j, o = self.client_from_bft.recv()
                #o = self.send_queue[j].get_nowait()
                #print('send' + str((j, o)))
                #self.logger.info('send' + str((j, o)))
                try:
                    self._send(j, pickle.dumps(o))
                except Exception as e:
                    self.logger.error(str(("problem objective when sending", o)))
                    traceback.print_exc()
            except:
                pass

        #print("sending loop quits ...")

    def run(self):
        self.logger = self._set_client_logger(self.id)

        pid = os.getpid()
        self.logger.info('node id %d is running on pid %d' % (self.id, pid))
        with self.ready.get_lock():
            self.ready.value = False

        self._connect_and_send_forever()


    def stop_service(self):
        with self.stop.get_lock():
            self.stop.value = True


    def _set_client_logger(self, id: int):
        logger = logging.getLogger("node-" + str(id))
        logger.setLevel(logging.DEBUG)
        # logger.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s %(filename)s [line:%(lineno)d] %(funcName)s %(levelname)s %(message)s ')
        if 'log' not in os.listdir(os.getcwd()):
            os.mkdir(os.getcwd() + '/log')
        full_path = os.path.realpath(os.getcwd()) + '/log/' + "node-net-client-" + str(id) + ".log"
        file_handler = logging.FileHandler(full_path)
        file_handler.setFormatter(formatter)  # 可以通过setFormatter指定输出格式
        logger.addHandler(file_handler)
        return logger
