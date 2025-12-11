
# mask.py
# Beaver-style helper operations (Python ints)

import secrets
from typing import List

def rand_vector(n: int, bitlen: int = 32) -> List[int]:
    # returns list of random ints (0 .. 2^bitlen-1)
    return [secrets.randbits(bitlen) for _ in range(n)]

def dot(a: List[int], b: List[int]) -> int:
    s = 0
    for x, y in zip(a, b):
        s += x * y
    return s

def add_vec(a: List[int], b: List[int]) -> List[int]:
    return [x + y for x, y in zip(a, b)]

def sub_vec(a: List[int], b: List[int]) -> List[int]:
    return [x - y for x, y in zip(a, b)]
