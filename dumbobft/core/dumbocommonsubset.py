import gevent
from gevent import time, monkey

monkey.patch_all()

def dumbocommonsubset(pid, N, f, prbc_out, vacs_in, vacs_out):
    """The BKR93 algorithm for asynchronous common subset.

    :param pid: my identifier
    :param N: number of nodes
    :param f: fault tolerance
    :param rbc_out: an array of :math:`N` (blocking) output functions,
        returning a string
    :param aba_in: an array of :math:`N` (non-blocking) functions that
        accept an input bit
    :param aba_out: an array of :math:`N` (blocking) output functions,
        returning a bit
    :return: an :math:`N`-element array, each element either ``None`` or a
        string
    """
    gevent.sleep(0)

    #assert len(prbc_out) == N
    #assert len(vacs_in) == 1
    #assert len(vacs_out) == 1

    prbc_values = [None] * N
    prbc_proofs = [None] * N
    is_prbc_delivered = [0] * N

    def wait_for_prbc_to_continue(leader):
        gevent.sleep(0)
        # Receive output from reliable broadcast
        msg, (prbc_sid, roothash, Sigma) = prbc_out[leader]()
        prbc_values[leader] = msg
        prbc_proofs[leader] = (prbc_sid, roothash, Sigma)
        is_prbc_delivered[leader] = 1
        if leader == pid:
            vacs_in(prbc_proofs[leader])

    r_threads = [gevent.spawn(wait_for_prbc_to_continue, j) for j in range(N)]

    prbc_proofs_vector = vacs_out()

    if prbc_proofs_vector is not None:
        assert prbc_proofs_vector is list and len(prbc_proofs_vector) == N
        for j in range(N):
            if prbc_proofs_vector[j] is not None:
                r_threads[j].join()
                assert prbc_values[j] is not None
            else:
                r_threads[j].kill()
                prbc_values = None
            gevent.sleep()

    return tuple(prbc_values)

    #
    # def _recv_aba(j):
    #     # Receive output from binary agreement
    #     aba_values[j] = aba_out[j]()  # May block
    #     # print (pid, j, 'ENTERING CRITICAL', sum(aba_values))
    #     if sum(aba_values) >= N - f:
    #         # Provide 0 to all other aba
    #         for k in range(N):
    #             if not aba_inputted[k]:
    #                 aba_inputted[k] = True
    #                 aba_in[k](0)
    #                 print(pid, 'ABA[%d] input -> %d' % (k, 0))
    #     # print (pid, j, 'EXITING CRITICAL')
    #
    # # Wait for all binary agreements
    # a_threads = [gevent.spawn(_recv_aba, j) for j in range(N)]
    # gevent.joinall(a_threads)
    # # print ("aba values of node %d" % pid, aba_values)
    #
    # assert sum(aba_values) >= N - f  # Must have at least N-f committed
    #
    # # Wait for the corresponding broadcasts
    # for j in range(N):
    #     if aba_values[j]:
    #         r_threads[j].join()
    #         assert rbc_values[j] is not None
    #     else:
    #         r_threads[j].kill()
    #         rbc_values[j] = None
    #
    # # print('rbc values', rbc_values)
    # return tuple(rbc_values)
