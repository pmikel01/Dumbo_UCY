import gevent
import pickle

from gevent import Greenlet
from gevent import socket, monkey
from gevent.queue import Queue
from crypto.threshsig.boldyreva import serialize as tsig_serialize, deserialize1 as tsig_deserialize
from crypto.threshenc.tpke import serialize as tenc_serialize, deserialize1 as tenc_deserialize

import traceback

monkey.patch_all()


def address_to_id(address: tuple):
    return int(address[1] % 10000 / 200)


class Node (Greenlet):

    SEP = '\r\nS\r\nE\r\nP\r\n'

    def __init__(self, port: int, i: int, nodes_list: list, queue: Queue):
        self.queue = queue
        self.port = port
        self.id = i
        self.nodes_list = nodes_list
        self.socks = [None for _ in self.nodes_list]
        Greenlet.__init__(self)

    def _run(self):
        print("node %d is running..." % self.id)
        gevent.spawn(self._serve_forever())

    def _handle_request(self, sock, address):

        def _finish(e: Exception):
            print(e)
            print("server is closing...")
            pass

        buf = b''
        try:
            while True:
                #gevent.sleep(0)
                buf += sock.recv(256)
                tmp = buf.split(self.SEP.encode('utf-8'), 1)
                while len(tmp) == 2:
                    buf = tmp[1]
                    data = tmp[0]
                    if data != '' and data:
                        if data == 'ping'.encode('utf-8'):
                            sock.sendall('pong'.encode('utf-8'))
                            print("node {} is pinging node {}...".format(address_to_id(address), self.id))
                        else:
                            (j, o) = (address_to_id(address), pickle.loads(data))
                            assert j in range(len(self.nodes_list))
                            try:
                                (a, (h1, r, (h2, b, e))) = o
                                if h1 == 'ACS_COIN' and h2 == 'COIN':
                                    o = (a, (h1, r, (h2, b, tsig_deserialize(e))))
                                    #print("pickle loads group element", tsig_deserialize(e))
                                    print(self.id, (j, o))
                                    gevent.spawn(self.queue.put_nowait((j, o)))
                                else:
                                    raise ValueError
                            except ValueError as e1:
                                try:
                                    h2, b, e = o
                                    if h2 == 'COIN':
                                        o = (h2, b, tsig_deserialize(e))
                                        #print("pickle loads group element", tsig_deserialize(e))
                                        #print("pickle loads group element type", type(tsig_deserialize(e)))
                                        print(self.id, (j, o))
                                        gevent.spawn(self.queue.put_nowait((j, o)))
                                    else:
                                        raise ValueError
                                except ValueError as e2:
                                    try:
                                        (a, (h1, b, e)) = o
                                        if h1 == 'TPKE':
                                            #print("resolve problem tpke", o)
                                            e1 = [None] * len(e)
                                            for i in range(len(e)):
                                                e1[i] = tenc_deserialize(e[i])
                                            o = (a, (h1, b, e1))
                                            print(self.id, (j, o))
                                            gevent.spawn(self.queue.put_nowait((j, o)))
                                        else:
                                            raise ValueError
                                    except ValueError as e3:
                                        #print("problem objective", o)
                                        try:
                                            print(self.id, (j, o))
                                            gevent.spawn(self.queue.put_nowait((j, o)))
                                        except Exception as e4:
                                            print("problem objective", o)
                                            print(e1)
                                            print(e2)
                                            print(e3)
                                            print(e4)
                                            traceback.print_exc()
                    else:
                        #print(data)
                        print('syntax error messages')
                        raise Exception
                    tmp = buf.split(self.SEP.encode('utf-8'), 1)

        except Exception as e:
            print(e)
            traceback.print_exc()
            _finish(e)

    def _serve_forever(self):
        self.server_sock = socket.socket()
        self.server_sock.bind(("", self.port))
        self.server_sock.listen(50)
        while True:
            sock, address = self.server_sock.accept()
            gevent.spawn(self._handle_request, sock, address)
            #self._handle_request(sock, address)

    def _watchdog_deamon(self):
        #self.server_sock.
        pass

    def connect_all(self):
        try:
            for j in range(len(self.nodes_list)):
                #if self.socks[j] is None:
                    print('node id %d:' % j)
                    sock = socket.socket()
                    sock.bind(("", self.port + 10 * j + 1))
                    sock.connect(self.nodes_list[j])
                    sock.sendall(('ping' + self.SEP).encode('utf-8'))
                    pong = sock.recv(4096)
                    if pong.decode('utf-8') == 'pong':
                        print("node {} is ponging node {}...".format(j, self.id))
                        self.socks[j] = sock
                        continue
                #else:
                #    print('fails to establish connection')
        except Exception as e:
            print(e)

    def _send(self, j: int, o: bytes):
        msg = b''.join([o, self.SEP.encode('utf-8')])
        #gevent.sleep(0)
        try:
            self.socks[j].sendall(msg)
        except Exception as e1:
            print("fail to send msg")
            try:
                self.socks[j].connect(self.nodes_list[j])
                self.socks[j].sendall(msg)
            except Exception as e2:
                print(e1)
                print(e2)
                traceback.print_exc()

    def send(self, j: int, o: object):
        try:
            self._send(j, pickle.dumps(o))
        except Exception as e:
            try:
                (a, (h1, r, (h2, b, e))) = o
                if h1 == 'ACS_COIN' and h2 == 'COIN':
                    o = (a, (h1, r, (h2, b, tsig_serialize(e))))
                    assert tsig_deserialize(tsig_serialize(e)) == e
                    self._send(j, pickle.dumps(o))
                else:
                    raise Exception
            except Exception as e1:
                try:
                    (h2, b, e) = o
                    if h2 == 'COIN':
                        o = (h2, b, tsig_serialize(e))
                        assert tsig_deserialize(tsig_serialize(e)) == e
                        self._send(j, pickle.dumps(o))
                    else:
                        raise Exception
                except Exception as e2:
                    try:
                        (a, (h1, b, e)) = o
                        e1 = [None] * len(e)
                        if h1 == 'TPKE':
                            for i in range(len(e)):
                                e1[i] = tenc_serialize(e[i])
                                assert tenc_deserialize(e1[i]) == e[i]
                            o = (a, (h1, b, e1))
                            self._send(j, pickle.dumps(o))
                        else:
                            raise Exception
                    except Exception as e3:
                        print("problem objective", o)
                        print(e)
                        print(e1)
                        print(e2)
                        print(e3)
                        traceback.print_exc()

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
