import string
import random


def tx_generator(size=250, chars=string.ascii_uppercase + string.digits):
    return '<HBBFT Input: ' + ''.join(random.choice(chars) for _ in range(size - 15)) + '>'
