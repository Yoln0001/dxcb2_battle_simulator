"""CPython random.Random MT19937 and shuffle compatible numeric primitives."""

import numpy as np
from numba import njit


@njit(cache=True)
def word(state):
    index = int(state[624])
    if index >= 624:
        for i in range(624):
            y = (state[i] & np.uint32(0x80000000)) | (state[(i + 1) % 624] & np.uint32(0x7FFFFFFF))
            state[i] = state[(i + 397) % 624] ^ (y >> np.uint32(1))
            if y & np.uint32(1):
                state[i] ^= np.uint32(0x9908B0DF)
        index = 0
    y = state[index]
    state[624] = index + 1
    y ^= y >> np.uint32(11)
    y ^= (y << np.uint32(7)) & np.uint32(0x9D2C5680)
    y ^= (y << np.uint32(15)) & np.uint32(0xEFC60000)
    y ^= y >> np.uint32(18)
    return y


@njit(cache=True)
def uniform(state):
    a = word(state) >> np.uint32(5)
    b = word(state) >> np.uint32(6)
    return (float(a) * 67108864.0 + float(b)) / 9007199254740992.0


@njit(cache=True)
def below(state, n):
    bits = 0
    v = n
    while v:
        bits += 1
        v >>= 1
    while True:
        value = int(word(state) >> np.uint32(32 - bits))
        if value < n:
            return value


@njit(cache=True)
def shuffle(state, events, count):
    for i in range(count - 1, 0, -1):
        j = below(state, i + 1)
        for k in range(events.shape[1]):
            value = events[i, k]
            events[i, k] = events[j, k]
            events[j, k] = value
