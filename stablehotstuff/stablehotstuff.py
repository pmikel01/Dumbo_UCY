import traceback
import time
from collections import defaultdict
from gevent.event import Event
from gevent.queue import Queue
from gevent import Timeout, monkey
from crypto.ecdsa.ecdsa import ecdsa_sign, ecdsa_vrfy, PublicKey
from crypto.threshsig.boldyreva import serialize, deserialize1
from crypto.threshsig.boldyreva import TBLSPrivateKey, TBLSPublicKey
import os
import json
import gevent
import hashlib, pickle



def hash(x):
    return hashlib.sha256(pickle.dumps(x)).digest()

def stablehotstuff(sid, pid, N, f, leader, get_input, put_output, Bsize, hash_genesis, PK1, SK1, PK2s, SK2, recv, send, logger=None):
    """Fast path, Byzantine Safe Broadcast
    :param str sid: ``the string of identifier``
    :param int pid: ``0 <= pid < N``
    :param int N:  at least 3
    :param int f: fault tolerance, ``N >= 3f + 1``
    :param int leader: the pid of leading node
    :param get_input: a function to get input TXs, e.g., input() to get a transaction
    :param put_output: a function to deliver output blocks, e.g., output(block)
    :param TBLSPublicKey PK1: ``boldyreva.TBLSPublicKey`` with threshold N-f
    :param TBLSPrivateKey SK1: ``boldyreva.TBLSPrivateKey`` with threshold N-f
    :param list PK2s: an array of ``coincurve.PublicKey'', i.e., N public keys of ECDSA for all parties
    :param PublicKey SK2: ``coincurve.PrivateKey'', i.e., secret key of ECDSA
    :param int Bsize: batch size, i.e., the number of TXs in a batch
    :param hash_genesis: the hash of genesis block
    :param recv: function to receive incoming messages
    :param send: function to send outgoing messages
    :return tuple: False to represent timeout, and True to represent success
    """

    slot = 0

