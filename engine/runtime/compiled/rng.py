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


@njit(cache=True)
def seeded_state(seed):
    """与 random.Random(seed).getstate()[1] 逐位相同的MT19937状态。

    seed为0到2**63-1的整数（批量模拟的每场种子小于2**53）。在内核里按CPython的
    init_by_array播种，省去每场在Python里创建Random对象并导出状态的开销。
    """
    mask = 0xFFFFFFFF
    mt = np.empty(624, np.int64)
    mt[0] = 19650218
    for i in range(1, 624):
        previous = mt[i - 1]
        mt[i] = (1812433253 * (previous ^ (previous >> 30)) + i) & mask
    key = np.empty(2, np.int64)
    key[0] = seed & mask
    key[1] = (seed >> 32) & mask
    length = 2 if key[1] != 0 else 1
    i = 1
    j = 0
    for _ in range(624):
        previous = mt[i - 1]
        mt[i] = ((mt[i] ^ ((previous ^ (previous >> 30)) * 1664525)) + key[j] + j) & mask
        i += 1
        j += 1
        if i >= 624:
            mt[0] = mt[623]
            i = 1
        if j >= length:
            j = 0
    for _ in range(623):
        previous = mt[i - 1]
        mt[i] = ((mt[i] ^ ((previous ^ (previous >> 30)) * 1566083941)) - i) & mask
        i += 1
        if i >= 624:
            mt[0] = mt[623]
            i = 1
    mt[0] = 0x80000000
    state = np.empty(625, np.uint32)
    for i in range(624):
        state[i] = np.uint32(mt[i])
    state[624] = np.uint32(624)
    return state
