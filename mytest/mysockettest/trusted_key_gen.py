from honeybadgerbft.crypto.threshsig.boldyreva import dealer, deserialize2, serialize
from honeybadgerbft.crypto.threshenc import tpke
import random
import pickle
import os

def trusted_key_gen(N=4, f=1, seed=None):

    # Generate threshold sig keys
    sPK, sSKs = dealer(N, f+1, seed=seed)

    # Generate threshold enc keys
    ePK, eSKs = tpke.dealer(N, f+1)

    with open(os.getcwd() + '/keys/' + 'sPK.key', 'wb') as fp:
        pickle.dump(sPK, fp)

    with open(os.getcwd() + '/keys/' + 'ePK.key', 'wb') as fp:
        pickle.dump(ePK, fp)

    for i in range(N):
        with open(os.getcwd() + '/keys/' + 'sSK-' + str(i) + '.key', 'wb') as fp:
            pickle.dump(sSKs[i], fp)

    for i in range(N):
        with open(os.getcwd() + '/keys/' + 'eSK-' + str(i) + '.key', 'wb') as fp:
            pickle.dump(eSKs[i], fp)

#    with open(os.getcwd() + '/keys/' + 'sPK.key', 'rb') as fp:
#        sPK = pickle.load(fp)

#    with open(os.getcwd() + '/keys/' + 'ePK.key', 'rb') as fp:
#        ePK = pickle.load(fp)

#    for i in range(N):
#        with open(os.getcwd() + '/keys/' + 'sSK-' + str(i) + '.key', 'rb') as fp:
#            sSKs[i] = pickle.load(fp)

#    for i in range(N):
#        with open(os.getcwd() + '/keys/' + 'eSK-' + str(i) + '.key', 'rb') as fp:
#            eSKs[i] = pickle.load(fp)