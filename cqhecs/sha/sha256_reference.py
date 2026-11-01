"""Readable SHA-256 per NIST FIPS 180-4 (pure Python, no hashlib).

All word arithmetic is explicit modulo 2**32. ``compress`` supports a reduced
round count and an explicit IV for research; the defaults give standard SHA-256.
"""
from __future__ import annotations

from typing import Sequence

MASK = 0xFFFFFFFF

# FIPS 180-4 section 4.2.2 (first 32 bits of the fractional parts of cube roots of the first 64 primes).
K = (
    0x428A2F98, 0x71374491, 0xB5C0FBCF, 0xE9B5DBA5, 0x3956C25B, 0x59F111F1, 0x923F82A4, 0xAB1C5ED5,
    0xD807AA98, 0x12835B01, 0x243185BE, 0x550C7DC3, 0x72BE5D74, 0x80DEB1FE, 0x9BDC06A7, 0xC19BF174,
    0xE49B69C1, 0xEFBE4786, 0x0FC19DC6, 0x240CA1CC, 0x2DE92C6F, 0x4A7484AA, 0x5CB0A9DC, 0x76F988DA,
    0x983E5152, 0xA831C66D, 0xB00327C8, 0xBF597FC7, 0xC6E00BF3, 0xD5A79147, 0x06CA6351, 0x14292967,
    0x27B70A85, 0x2E1B2138, 0x4D2C6DFC, 0x53380D13, 0x650A7354, 0x766A0ABB, 0x81C2C92E, 0x92722C85,
    0xA2BFE8A1, 0xA81A664B, 0xC24B8B70, 0xC76C51A3, 0xD192E819, 0xD6990624, 0xF40E3585, 0x106AA070,
    0x19A4C116, 0x1E376C08, 0x2748774C, 0x34B0BCB5, 0x391C0CB3, 0x4ED8AA4A, 0x5B9CCA4F, 0x682E6FF3,
    0x748F82EE, 0x78A5636F, 0x84C87814, 0x8CC70208, 0x90BEFFFA, 0xA4506CEB, 0xBEF9A3F7, 0xC67178F2,
)

# FIPS 180-4 section 5.3.3 (square roots of the first 8 primes).
IV = (
    0x6A09E667, 0xBB67AE85, 0x3C6EF372, 0xA54FF53A,
    0x510E527F, 0x9B05688C, 0x1F83D9AB, 0x5BE0CD19,
)

State = tuple  # eight 32-bit words (a..h)


def rotr(x: int, n: int) -> int:
    n &= 31
    return ((x >> n) | (x << (32 - n))) & MASK


def shr(x: int, n: int) -> int:
    return (x & MASK) >> n


def ch(x: int, y: int, z: int) -> int:
    return ((x & y) ^ (~x & MASK & z)) & MASK


def maj(x: int, y: int, z: int) -> int:
    return (x & y) ^ (x & z) ^ (y & z)


def big_sigma0(x: int) -> int:
    return rotr(x, 2) ^ rotr(x, 13) ^ rotr(x, 22)


def big_sigma1(x: int) -> int:
    return rotr(x, 6) ^ rotr(x, 11) ^ rotr(x, 25)


def small_sigma0(x: int) -> int:
    return rotr(x, 7) ^ rotr(x, 18) ^ shr(x, 3)


def small_sigma1(x: int) -> int:
    return rotr(x, 17) ^ rotr(x, 19) ^ shr(x, 10)


def pad(message: bytes) -> bytes:
    """Append 0x80, zeros, and the 64-bit big-endian bit length (multiple of 64 bytes)."""
    bit_len = len(message) * 8
    padded = bytes(message) + b"\x80"
    padded += b"\x00" * ((56 - len(padded)) % 64)
    return padded + bit_len.to_bytes(8, "big")


def block_words(block: bytes) -> tuple:
    """Parse one 64-byte block into sixteen big-endian 32-bit words."""
    if len(block) != 64:
        raise ValueError(f"a SHA-256 block is 64 bytes, got {len(block)}")
    return tuple(int.from_bytes(block[i : i + 4], "big") for i in range(0, 64, 4))


def schedule(words: Sequence[int]) -> tuple:
    """Expand 16 words into the 64-word message schedule W[0..63]."""
    if len(words) != 16:
        raise ValueError("schedule needs exactly 16 input words")
    w = [x & MASK for x in words]
    for t in range(16, 64):
        w.append((small_sigma1(w[t - 2]) + w[t - 7] + small_sigma0(w[t - 15]) + w[t - 16]) & MASK)
    return tuple(w)


def round_step(state: Sequence[int], k_t: int, w_t: int) -> tuple:
    """One compression round; returns (new_state, T1, T2)."""
    a, b, c, d, e, f, g, h = state
    t1 = (h + big_sigma1(e) + ch(e, f, g) + k_t + w_t) & MASK
    t2 = (big_sigma0(a) + maj(a, b, c)) & MASK
    new = ((t1 + t2) & MASK, a, b, c, (d + t1) & MASK, e, f, g)
    return new, t1, t2


def compress(
    state: Sequence[int],
    words: Sequence[int],
    rounds: int = 64,
    feed_forward: bool = True,
    k: Sequence[int] = K,
) -> tuple:
    """SHA-256 compression function over one block (optionally reduced-round)."""
    if not 0 <= rounds <= 64:
        raise ValueError("rounds must be between 0 and 64")
    if len(state) != 8:
        raise ValueError("state must have eight words")
    w = schedule(words)
    work = tuple(x & MASK for x in state)
    for t in range(rounds):
        work, _, _ = round_step(work, k[t], w[t])
    if not feed_forward:
        return work
    return tuple((s + x) & MASK for s, x in zip(state, work))


def state_bytes(state: Sequence[int]) -> bytes:
    return b"".join(x.to_bytes(4, "big") for x in state)


def sha256(message: bytes, iv: Sequence[int] = IV) -> bytes:
    state = tuple(iv)
    padded = pad(message)
    for i in range(0, len(padded), 64):
        state = compress(state, block_words(padded[i : i + 64]))
    return state_bytes(state)


def sha256d(data: bytes) -> bytes:
    """Bitcoin-style double SHA-256: SHA256(SHA256(data))."""
    return sha256(sha256(data))
