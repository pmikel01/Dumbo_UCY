from honeybadgerbft.crypto.threshsig.boldyreva import dealer
from honeybadgerbft.crypto.threshenc import tpke
import pickle
import os


def trusted_key_gen(N=4, f=1, seed=None):

    # Generate threshold enc keys
    ePK, eSKs = tpke.dealer(N, f+1)

    # Generate threshold sig keys for coin (thld f+1)
    sPK, sSKs = dealer(N, f+1, seed=seed)

    # Generate threshold sig keys for cbc (thld n-f)
    sPK1, sSK1s = dealer(N, N-f, seed=seed)

    # Save all keys to files
    if 'keys' not in os.listdir(os.getcwd()):
        os.mkdir(os.getcwd() + '/keys')

    with open(os.getcwd() + '/keys/' + 'sPK.key', 'wb') as fp:
        pickle.dump(sPK, fp)

    with open(os.getcwd() + '/keys/' + 'sPK1.key', 'wb') as fp:
        pickle.dump(sPK1, fp)

    with open(os.getcwd() + '/keys/' + 'ePK.key', 'wb') as fp:
        pickle.dump(ePK, fp)

    for i in range(N):
        with open(os.getcwd() + '/keys/' + 'sSK-' + str(i) + '.key', 'wb') as fp:
            pickle.dump(sSKs[i], fp)

    for i in range(N):
        with open(os.getcwd() + '/keys/' + 'sSK1-' + str(i) + '.key', 'wb') as fp:
            pickle.dump(sSK1s[i], fp)

    for i in range(N):
        with open(os.getcwd() + '/keys/' + 'eSK-' + str(i) + '.key', 'wb') as fp:
            pickle.dump(eSKs[i], fp)


if __name__ == '__main__':
    
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--N', metavar='N', required=True,
                        help='number of parties', type=int)
    parser.add_argument('--f', metavar='f', required=True,
                        help='number of faulties', type=int)
    args = parser.parse_args()

    N = args.N
    f = args.f

    assert N >= 3 * f + 1

    trusted_key_gen(N, f)
