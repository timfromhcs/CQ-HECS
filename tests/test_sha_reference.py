"""SHA-256 reference: FIPS 180-4 known answers, boundaries, primitives, negatives."""
import hashlib
import random

import pytest

from cqhecs.sha import sha256_reference as ref
from cqhecs.sha import vectors


def _first_primes(count):
    primes = []
    n = 2
    while len(primes) < count:
        if all(n % p for p in primes):
            primes.append(n)
        n += 1
    return primes


def _frac_root(p, k):
    """floor(frac(p**(1/k)) * 2**32) via exact integer k-th root."""
    x = p << (32 * k)
    lo, hi = 0, 1 << 40
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if mid**k <= x:
            lo = mid
        else:
            hi = mid - 1
    return lo & 0xFFFFFFFF


def test_constants_derive_from_primes():
    primes = _first_primes(64)
    assert [_frac_root(p, 3) for p in primes] == list(ref.K)
    assert [_frac_root(p, 2) for p in primes[:8]] == list(ref.IV)


# The known-answer vectors include a one-million-byte message. With the default
# id generation pytest builds the test id from repr(message), i.e. a megabyte-long
# string, and on Windows that id travels through an environment variable that is
# limited to 32767 characters - the test then fails to run with an OSError before
# the assertion is ever reached. Explicit, short, still unique ids fix that
# without changing what is asserted.
_KAT_IDS = [("empty" if not message else f"{len(message)}-byte-message") for message, _ in vectors.SHA256_KAT]


@pytest.mark.parametrize("message,digest", vectors.SHA256_KAT, ids=_KAT_IDS)
def test_known_answers(message, digest):
    assert ref.sha256(message).hex() == digest


@pytest.mark.parametrize("n", [0, 1, 54, 55, 56, 57, 63, 64, 65, 119, 120, 127, 128, 129, 1000])
def test_length_boundaries_match_hashlib(n):
    msg = bytes((i * 7 + 3) & 0xFF for i in range(n))
    assert ref.sha256(msg) == hashlib.sha256(msg).digest()


def test_randomized_cross_check():
    rng = random.Random(0xC0FFEE)
    for _ in range(300):
        msg = rng.randbytes(rng.randrange(0, 300))
        assert ref.sha256(msg) == hashlib.sha256(msg).digest()


def test_padding_layout():
    padded = ref.pad(b"abc")
    assert len(padded) == 64
    assert padded[:3] == b"abc" and padded[3] == 0x80
    assert int.from_bytes(padded[-8:], "big") == 24
    assert len(ref.pad(b"a" * 55)) == 64
    assert len(ref.pad(b"a" * 56)) == 128


def test_primitive_functions():
    assert ref.rotr(0x80000001, 1) == 0xC0000000
    assert ref.rotr(0x12345678, 0) == 0x12345678
    assert ref.shr(0x80000000, 31) == 1
    for x, y, z in [(0xFFFFFFFF, 0, 0xAAAAAAAA), (0x0F0F0F0F, 0x33333333, 0x55555555)]:
        assert ref.ch(x, y, z) == (x & y) | (~x & 0xFFFFFFFF & z)
        for bit in range(32):
            bits = ((x >> bit) & 1) + ((y >> bit) & 1) + ((z >> bit) & 1)
            assert ((ref.maj(x, y, z) >> bit) & 1) == (1 if bits >= 2 else 0)
    rng = random.Random(1)
    for _ in range(200):
        x = rng.getrandbits(32)
        assert ref.big_sigma0(x) == ref.rotr(x, 2) ^ ref.rotr(x, 13) ^ ref.rotr(x, 22)
        assert ref.big_sigma1(x) == ref.rotr(x, 6) ^ ref.rotr(x, 11) ^ ref.rotr(x, 25)
        assert ref.small_sigma0(x) == ref.rotr(x, 7) ^ ref.rotr(x, 18) ^ ref.shr(x, 3)
        assert ref.small_sigma1(x) == ref.rotr(x, 17) ^ ref.rotr(x, 19) ^ ref.shr(x, 10)


def test_schedule_length_and_recurrence():
    words = ref.block_words(ref.pad(b"abc"))
    w = ref.schedule(words)
    assert len(w) == 64 and list(w[:16]) == list(words)
    assert w[16] == (ref.small_sigma1(w[14]) + w[9] + ref.small_sigma0(w[1]) + w[0]) & 0xFFFFFFFF


def test_block_words_rejects_bad_size():
    with pytest.raises(ValueError):
        ref.block_words(b"\x00" * 63)


def test_sha256d_and_genesis_header():
    assert ref.sha256d(b"hello").hex() == hashlib.sha256(hashlib.sha256(b"hello").digest()).hexdigest()
    header = bytes.fromhex(vectors.GENESIS_HEADER_HEX)
    assert len(header) == 80
    assert ref.sha256d(header)[::-1].hex() == vectors.GENESIS_BLOCK_HASH


def test_reduced_rounds():
    block = ref.block_words(ref.pad(b"abc"))
    full = ref.compress(ref.IV, block)
    assert full == ref.compress(ref.IV, block, rounds=64)
    assert ref.compress(ref.IV, block, rounds=63) != full
    assert ref.compress(ref.IV, block, rounds=0) == tuple((v + v) & 0xFFFFFFFF for v in ref.IV)
    with pytest.raises(ValueError):
        ref.compress(ref.IV, block, rounds=65)
    with pytest.raises(ValueError):
        ref.compress(ref.IV, block, rounds=-1)


def test_negative_controls_detect_corruption():
    block = ref.block_words(ref.pad(b"abc"))
    good = ref.compress(ref.IV, block)
    assert ref.compress(ref.IV, block, feed_forward=False) != good
    bad_iv = (ref.IV[0] ^ 1,) + tuple(ref.IV[1:])
    assert ref.compress(bad_iv, block) != good
    swapped = tuple(int.from_bytes(w.to_bytes(4, "big"), "little") for w in block)
    assert ref.compress(ref.IV, swapped) != good
    mutated_k = list(ref.K)
    mutated_k[10] ^= 1
    assert ref.compress(ref.IV, block, k=tuple(mutated_k)) != good
