import gevent.monkey; gevent.monkey.patch_all()

import random
import traceback

from myexperiements.sockettest.hbbft_node import HoneyBadgerBFTNode
from myexperiements.sockettest.dumbo_node import DumboBFTNode
from myexperiements.sockettest.mule_node import MuleBFTNode


def instantiate_bft_node(sid, i, B, N, f, my_address, addresses, K, S, T, protocol="mule", mute=False, factor=1):
    if protocol == 'dumbo':
        dumbo = DumboBFTNode(sid, i, B, N, f, my_address, addresses, K, mute=mute)
        dumbo.run_dumbo_instance()
    elif protocol == "badger":
        badger = HoneyBadgerBFTNode(sid, i, B, N, f, my_address, addresses, K, mute=mute)
        badger.run_hbbft_instance()
    elif protocol == "mule":
        mule = MuleBFTNode(sid, i, S, T, int(factor*B/N), B, N, f, my_address, addresses, K, mute=mute)
        mule.run_mule_instance()
    else:
        print("Only support dumbo or badger or mule")


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
    parser.add_argument('--S', metavar='S', required=False,
                        help='slots to execute', type=int, default=50)
    parser.add_argument('--T', metavar='T', required=False,
                        help='fast path timeout', type=float, default=1)
    parser.add_argument('--P', metavar='P', required=False,
                        help='protocol to execute', type=str, default="mule")
    parser.add_argument('--M', metavar='M', required=False,
                        help='whether to mute a third of nodes', type=bool, default=False)
    parser.add_argument('--F', metavar='F', required=False,
                        help='the parameter to time (B/N) to get the fast path batch size', type=float, default=1)

    args = parser.parse_args()

    # Some parameters
    sid = args.sid
    i = args.id
    N = args.N
    f = args.f
    B = args.B
    K = args.K
    S = args.S
    T = args.T
    P = args.P
    M = args.M
    F = args.F

    # Random generator
    rnd = random.Random(sid)

    # Nodes list
    addresses = [None] * N
    try:
        with open('hosts.config', 'r') as hosts:
            for line in hosts:
                params = line.split()
                pid = int(params[0])
                priv_ip = params[1]
                pub_ip = params[2]
                port = int(params[3])
                # print(pid, ip, port)
                if pid not in range(N):
                    continue
                if pid == i:
                    my_address = priv_ip
                addresses[pid] = (pub_ip, port)
        # print(addresses)
        assert all([node is not None for node in addresses])
        print("hosts.config is correctly read")
        instantiate_bft_node(sid, i, B, N, f, my_address, addresses, K, S, T, P, M, F)
    except FileNotFoundError or AssertionError as e:
        #print(e)
        traceback.print_exc()
        #print("hosts.config is not correctly read... ")
        #host = "127.0.0.1"
        #port_base = int(rnd.random() * 5 + 1) * 10000
        #addresses = [(host, port_base + 200 * i) for i in range(N)]
        #print(addresses)
    #instantiate_hbbft_node(sid, i, B, N, f, addresses, K)
