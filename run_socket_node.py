import random
import traceback

from myexperiements.sockettest.hbbft_node import HoneyBadgerBFTNode
from myexperiements.sockettest.dumbo_node import DumboBFTNode
from myexperiements.sockettest.mule_node import MuleBFTNode


def instantiate_bft_node(sid, i, B, N, f, my_address, addresses, K, S, T):
    print(my_address)
    print(addresses)
    #dumbo = DumboBFTNode(sid, i, B, N, f, my_address, addresses, K)
    #dumbo.run_dumbo_instance()
    #badger = HoneyBadgerBFTNode(sid, i, B, N, f, my_address, addresses, K)
    #badger.run_hbbft_instance()
    mule = MuleBFTNode(sid, i, S, T, B, N, f, my_address, addresses, K)
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
    parser.add_argument('--S', metavar='S', required=False,
                        help='slots to execute', type=int, default=50)
    parser.add_argument('--T', metavar='T', required=False,
                        help='fast path timeout', type=int, default=1)
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
        instantiate_bft_node(sid, i, B, N, f, my_address, addresses, K, S, T)
    except FileNotFoundError or AssertionError as e:
        #print(e)
        traceback.print_exc()
        #print("hosts.config is not correctly read... ")
        #host = "127.0.0.1"
        #port_base = int(rnd.random() * 5 + 1) * 10000
        #addresses = [(host, port_base + 200 * i) for i in range(N)]
        #print(addresses)
    #instantiate_hbbft_node(sid, i, B, N, f, addresses, K)
