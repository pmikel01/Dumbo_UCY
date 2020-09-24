from collections import defaultdict



def reliablebroadcast(sid, pid, N, f, PK, SK, leader, input, receive, send):

    cbc_values = defaultdict(lambda: None)
    cbc_sshares = defaultdict(dict)
    cbc_sigs = defaultdict(lambda: None)

    fromLeader = None
    readyCounter = defaultdict(lambda: 0)
    readySenders = set()  # Peers that have sent us ECHO messages
    ready = defaultdict(set)
    readySent = False
    readySenders = set()  # Peers that have sent us READY messages

    def broadcast(o):
        for i in range(N):
            send(i, o)

    if pid == leader:
        m = input()
        #assert isinstance(m, (str, bytes))
        broadcast(('VCBC_SEND', pid, m))

    while True:
        (sender, msg) = receive()

        if msg[0] == 'CBC_SEND' and fromLeader is None:
            _, leader, vs = msg
            if sender != leader:
                print("CBC_SEND message from other than leader:", sender)
                continue
            cbc_values[j] = vs
            h = PK.hash_message(str((sid, 'CBC_SEND', sender, vs)))
            send(j, ('CBC_READY', sender, h, SK.sign(h)))
            if cbc_sigs[j] != None:
                sig = cbc_sigs[j]
                try:
                    assert PK.verify_signature(sig, h)
                    if sum(vs) >= N - f:
                        is_cbcdelivered[sender] = 1
                except AssertionError:
                    print("Signature failed!", (sid, pid, j, msg))
                    continue
                    #raise JustContinueException()

        elif msg[0] == 'CBC_READY':
            # CBC_READY message
            _, sender, h, s = msg
            if cbc_values[sender] == None:
                print("CBC value not broadcasted yet", (sid, pid, j, msg))
                #raise JustContinueException()
                continue
            if j in cbc_sshares[sender]:
                print("redundant partial sig received", (sid, pid, j, msg))
                continue
                #raise JustContinueException()
            if sender != pid or h != PK.hash_message(str((sid, 'CBC_SEND', sender, cbc_values[sender]))):
                print("Inconsistent cbc ready msg!", (sid, pid, j, msg))
                continue
                #raise JustContinueException()
            try:
                assert PK.verify_share(s, j, h)
            except AssertionError:
                print("Signature share failed!", (sid, pid, j, msg))
                continue
                #raise JustContinueException()
            cbc_sshares[sender][j] = s
            if len(cbc_sshares[sender]) == f + 1:
                sigs = dict(list(cbc_sshares[sender].items())[:f + 1])
                sig = PK.combine_shares(sigs)
                assert PK.verify_signature(sig, h)
                broadcast(('CBC_FINAL', sender, h, sig))

        elif msg[0] == 'CBC_FINAL':
            # CBC_FINAL message
            _, sender, h, sig = msg
            if cbc_sigs[j] != None:
                print("redundant full sig received", (sid, pid, j, msg))
                continue
                #raise JustContinueException()
            if j != sender:
                print("Inconsistent cbc final msg!", (sid, pid, j, msg))
                continue
                #raise JustContinueException()
            if cbc_values[sender] == None:
                continue
                #raise JustContinueException()
            try:
                vs = cbc_values[sender]
                h = PK.hash_message(str((sid, 'CBC_SEND', sender, vs)))
                assert PK.verify_signature(sig, h)
                cbc_sigs[sender] = sig
                if sum(vs) >= N - f:
                    is_cbcdelivered[sender] = 1
            except AssertionError:
                print("Signature failed!", (sid, pid, j, msg))
                continue
                #raise JustContinueException()