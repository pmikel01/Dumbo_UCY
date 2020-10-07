import math
import zfec
import hashlib
import string
import random
import time

def encode(K, N, m):
    """Erasure encodes string ``m`` into ``N`` blocks, such that any ``K``
    can reconstruct.

    :param int K: K
    :param int N: number of blocks to encode string ``m`` into.
    :param bytes m: bytestring to encode.

    :return list: Erasure codes resulting from encoding ``m`` into
        ``N`` blocks using ``zfec`` lib.

    """
    try:
        m = m.encode()
    except AttributeError:
        pass
    encoder = zfec.Encoder(K, N)
    assert K <= 256  # TODO: Record this assumption!
    # pad m to a multiple of K bytes
    padlen = K - (len(m) % K)
    m += padlen * chr(K-padlen).encode()
    step = len(m)//K
    blocks = [m[i*step: (i+1)*step] for i in range(K)]
    stripes = encoder.encode(blocks)
    return stripes


#####################
#    Merkle tree    #
#####################
def hash(x):
    assert isinstance(x, (str, bytes))
    try:
        x = x.encode()
    except AttributeError:
        pass
    return hashlib.sha256(x).digest()


def ceil(x): return int(math.ceil(x))


def merkleTree(strList):
    """Builds a merkle tree from a list of :math:`N` strings (:math:`N`
    at least 1)

    :return list: Merkle tree, a list of ``2*ceil(N)`` strings. The root
         digest is at ``tree[1]``, ``tree[0]`` is blank.
    """
    N = len(strList)
    assert N >= 1
    bottomrow = 2 ** ceil(math.log(N, 2))
    mt = [b''] * (2 * bottomrow)
    for i in range(N):
        mt[bottomrow + i] = hash(strList[i])
    for i in range(bottomrow - 1, 0, -1):
        mt[i] = hash(mt[i*2] + mt[i*2+1])
    return mt


def getMerkleBranch(index, mt):
    """Computes a merkle tree from a list of leaves.
    """
    res = []
    t = index + (len(mt) >> 1)
    while t > 1:
        res.append(mt[t ^ 1])  # we are picking up the sibling
        t //= 2
    return res


def merkleVerify(N, val, roothash, branch, index):
    """Verify a merkle tree branch proof
    """
    assert 0 <= index < N
    # XXX Python 3 related issue, for now let's tolerate both bytes and
    # strings
    assert isinstance(val, (str, bytes))
    assert len(branch) == ceil(math.log(N, 2))
    # Index has information on whether we are facing a left sibling or a right sibling
    tmp = hash(val)
    tindex = index
    for br in branch:
        tmp = hash((tindex & 1) and br + tmp or tmp + br)
        tindex >>= 1
    if tmp != roothash:
        print("Verification failed with", hash(val), roothash, branch, tmp == roothash)
        return False
    return True


def test_encoding(B):

    for K in range(1, 50):

        m = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(256 * B))

        start = time.time()

        stripes = encode(K, 3 * K + 1, m)
        middle = time.time()
        print((middle - start) * 1000)

        mt = merkleTree(stripes)
        getMerkleBranch(1, mt)
        end = time.time()
        print((end - middle) * 1000)
        print()


if __name__ == "__main__":
    test_encoding(400)
