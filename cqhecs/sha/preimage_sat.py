"""CNF encoding of reduced-round SHA-256 compression (FIPS 180-4 §5.1.2, §5.3).

This module turns the wording of ``sha256_reference`` -- additions, the six
logical functions and the message schedule -- into clauses, so that
:mod:`cqhecs.sat` can decide statements about them. It is the bridge between the
SHA research track and the exact SAT/#SAT track.

What is encoded
---------------
Everything is a *bit* wire. A bit is a DIMACS literal (``int``); a single
allocated variable pinned to true by a unit clause is used both as the constant
``TRUE`` and -- negated -- as the constant ``FALSE``. Every gate therefore takes
literals and returns a literal, and constants need no special case:

* ``AND``/``XOR``/``OR``: Tseitin definitions, two-wire gates only
  (FIPS 180-4 §4.1.2 logical functions);
* ``ADD``: a ripple-carry chain of hand-written full adders (FIPS 180-4 §4.1.3
  word addition modulo 2**W). ``add`` returns the sum bits and the carry out;
  the caller drops the carry to obtain addition modulo 2**W;
* ``ROTR``/``SHR``: free re-wiring, no clauses (FIPS 180-4 §3.2);
* ``Ch``, ``Maj``, ``Sigma0/1``, ``sigma0/1``: built only from the gates above,
  using the round constants ``K`` and initial value ``IV`` of
  :mod:`cqhecs.sha.sha256_reference` (FIPS 180-4 §4.2.2, §5.3.3).

The encoder is deliberately dumb: no symmetry breaking, no "the answer is
already known" propagation, no algebraic shortcut. Adders are adders. A model
that the solver returns is therefore evidence about the clauses, not about the
encoder's cleverness.

Word widths
-----------
``width`` is the word size W. W = 32 is SHA-256 and is checked against
:func:`cqhecs.sha.sha256_reference.compress` in the tests. Other widths are
**toys**: they use the same algorithm with every rotation amount reduced modulo W
and shifts of W bits or more contributing zero. A W = 8 instance is not SHA-256
and proves nothing about SHA-256; it exists so that an exhaustive Python search
can be the oracle for the CNF, and so that UNSAT can be certified cheaply.

Honesty
-------
These instances are small and bounded. Nothing here says anything about the
complexity of inverting SHA-256, about ``P`` versus ``NP``, or about the
security of 64-round SHA-256. Round counts above the reduced sizes tested in
``tests/test_sha_preimage_sat.py`` do not finish and are reported as UNRESOLVED
in ``research/sha_forge/SAT_SHA.md``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from cqhecs.sat import CNF, parse_dimacs
from cqhecs.sha import sha256_reference as ref

#: SHA-256 width; the only width for which the reference module is the oracle.
DEFAULT_WIDTH = 32
#: FIPS 180-4 §5.2.1: the sixteen 32-bit words of a message block.
MESSAGE_WORDS = 16
#: FIPS 180-4 §5.3.3: the eight-word chaining value.
STATE_WORDS = 8
#: FIPS 180-4 §5.3.3: 64 rounds.
MAX_ROUNDS = 64


def width_mask(width: int) -> int:
    """The modulus-2**W mask."""
    return (1 << width) - 1


def rounded_constants(width: int = DEFAULT_WIDTH) -> Tuple[Tuple[int, ...], Tuple[int, ...]]:
    """``(K, IV)`` truncated to ``width`` bits, in the reference order."""
    mask = width_mask(width)
    return tuple(k & mask for k in ref.K), tuple(v & mask for v in ref.IV)


# ---------------------------------------------------------------------------
# The wide Python model used as the oracle for widths other than 32
# ---------------------------------------------------------------------------
def toy_compress(
    state: Sequence[int],
    words: Sequence[int],
    rounds: int = MAX_ROUNDS,
    width: int = DEFAULT_WIDTH,
    feed_forward: bool = True,
) -> Tuple[int, ...]:
    """The same algorithm as ``compress`` with the word width as a parameter.

    At ``width == 32`` this is checked (in the tests) to produce exactly
    ``sha256_reference.compress``. At any other width it is a **toy**: the
    rotation amounts of FIPS 180-4 §4.1.2 are reduced modulo W, and a shift of W
    bits or more contributes zero. It is an independent integer implementation
    of the same wiring, used only as an oracle for the clauses.

    The schedule is expanded up to ``max(MESSAGE_WORDS, rounds)`` words, which is
    all that the requested rounds can consume.
    """
    if not 0 <= rounds <= MAX_ROUNDS:
        raise ValueError("rounds must be between 0 and 64")
    if len(state) != STATE_WORDS:
        raise ValueError("state must have eight words")
    if len(words) != MESSAGE_WORDS:
        raise ValueError("schedule needs exactly 16 input words")
    if not 4 <= width <= 32:
        raise ValueError("width must be between 4 and 32")
    mask = width_mask(width)
    k, _ = rounded_constants(width)

    def rotr(x: int, n: int) -> int:
        n %= width
        x &= mask
        if n == 0:
            return x
        return ((x >> n) | (x << (width - n))) & mask

    def shr(x: int, n: int) -> int:
        return 0 if n >= width else (x & mask) >> n

    def ch(x: int, y: int, z: int) -> int:
        return ((x & y) ^ (~x & mask & z)) & mask

    def maj(x: int, y: int, z: int) -> int:
        return ((x & y) ^ (x & z) ^ (y & z)) & mask

    def big_sigma0(x: int) -> int:
        return rotr(x, 2) ^ rotr(x, 13) ^ rotr(x, 22)

    def big_sigma1(x: int) -> int:
        return rotr(x, 6) ^ rotr(x, 11) ^ rotr(x, 25)

    def small_sigma0(x: int) -> int:
        return rotr(x, 7) ^ rotr(x, 18) ^ shr(x, 3)

    def small_sigma1(x: int) -> int:
        return rotr(x, 17) ^ rotr(x, 19) ^ shr(x, 10)

    w = [x & mask for x in words]
    needed = max(MESSAGE_WORDS, rounds)
    for t in range(MESSAGE_WORDS, needed):
        w.append((small_sigma1(w[t - 2]) + w[t - 7] + small_sigma0(w[t - 15]) + w[t - 16]) & mask)

    work = [x & mask for x in state]
    for t in range(rounds):
        a, b, c, d, e, f, g, h = work
        t1 = (h + big_sigma1(e) + ch(e, f, g) + k[t] + w[t]) & mask
        t2 = (big_sigma0(a) + maj(a, b, c)) & mask
        work = [(t1 + t2) & mask, a, b, c, (d + t1) & mask, e, f, g]
    if not feed_forward:
        return tuple(work)
    return tuple((s + x) & mask for s, x in zip(state, work))


def width_compress(
    state: Sequence[int],
    words: Sequence[int],
    rounds: int = MAX_ROUNDS,
    width: int = DEFAULT_WIDTH,
    feed_forward: bool = True,
) -> Tuple[int, ...]:
    """``compress`` at W = 32, else :func:`toy_compress`.

    At W = 32 this delegates to :func:`cqhecs.sha.sha256_reference.compress`, so a
    differential test at that width compares the CNF against the shipped
    reference rather than against this module.
    """
    if width == DEFAULT_WIDTH:
        return tuple(ref.compress(state, words, rounds=rounds, feed_forward=feed_forward))
    return toy_compress(state, words, rounds=rounds, width=width, feed_forward=feed_forward)


def block_words(block: bytes, width: int = DEFAULT_WIDTH) -> Tuple[int, ...]:
    """The sixteen schedule inputs of one 64-byte block, truncated to ``width`` bits.

    At W = 32 this is exactly :func:`cqhecs.sha.sha256_reference.block_words`. At a
    toy width the low W bits of each big-endian 32-bit word are kept, which is the
    documented way to feed a real block to a narrow instance.
    """
    words = ref.block_words(block)
    mask = width_mask(width)
    return tuple(word & mask for word in words)


def masked_iv(width: int = DEFAULT_WIDTH) -> Tuple[int, ...]:
    """The FIPS 180-4 §5.3.3 initial value truncated to ``width`` bits."""
    _, iv = rounded_constants(width)
    return iv


# ---------------------------------------------------------------------------
# The encoder
# ---------------------------------------------------------------------------
class WordEncoder:
    """Tseitin CNF for W-bit word arithmetic over DIMACS literals.

    A bit is a literal, so ``-lit`` is its complement and no negation gate is
    ever allocated. One variable is allocated first and pinned true; its literal
    is ``TRUE`` and its negation is ``FALSE``, which lets constants flow through
    the same gate code as variables.
    """

    def __init__(self, width: int = DEFAULT_WIDTH) -> None:
        if not 4 <= width <= 32:
            raise ValueError(f"width must be between 4 and 32, got {width}")
        self.width = width
        self._num_vars = 0
        self._clauses: List[Tuple[int, ...]] = []
        self.true_lit = self.new_var()
        self._clauses.append((self.true_lit,))

    # -- plumbing --------------------------------------------------------
    def new_var(self) -> int:
        self._num_vars += 1
        return self._num_vars

    @property
    def num_vars(self) -> int:
        return self._num_vars

    @property
    def clauses(self) -> Tuple[Tuple[int, ...], ...]:
        return tuple(self._clauses)

    @property
    def false_lit(self) -> int:
        return -self.true_lit

    def const(self, value: bool) -> int:
        """A literal fixed by a unit clause (the constant TRUE or FALSE)."""
        return self.true_lit if value else -self.true_lit

    def const_bits(self, value: int, width: Optional[int] = None) -> List[int]:
        """Little-endian bits of ``value`` as constant literals."""
        w = self.width if width is None else width
        return [self.const(bool((value >> b) & 1)) for b in range(w)]

    def clause(self, *literals: int) -> None:
        """Add a clause; duplicate literals are folded and tautologies dropped."""
        seen: List[int] = []
        present = set()
        for literal in literals:
            if -literal in present:
                return  # tautology: always true, carries no information
            if literal in present:
                continue
            present.add(literal)
            seen.append(literal)
        self._clauses.append(tuple(seen))

    # -- single-bit gates (FIPS 180-4 §4.1.2) ----------------------------
    def and2(self, x: int, y: int) -> int:
        """Tseitin ``z = x AND y``: three clauses, one fresh variable."""
        z = self.new_var()
        self.clause(-x, -y, z)
        self.clause(x, -z)
        self.clause(y, -z)
        return z

    def or2(self, x: int, y: int) -> int:
        """``x OR y`` as the negated AND of the complements; no extra variable."""
        return -self.and2(-x, -y)

    def xor2(self, x: int, y: int) -> int:
        """Tseitin ``z = x XOR y``: four clauses, one fresh variable."""
        z = self.new_var()
        self.clause(x, y, -z)
        self.clause(-x, -y, -z)
        self.clause(x, -y, z)
        self.clause(-x, y, z)
        return z

    def xnor2(self, x: int, y: int) -> int:
        """``x == y``."""
        return -self.xor2(x, y)

    # -- word operations (FIPS 180-4 §3.2, §4.1.2) -----------------------
    def xor_word(self, a: Sequence[int], b: Sequence[int]) -> List[int]:
        return [self.xor2(x, y) for x, y in zip(a, b)]

    def not_word(self, a: Sequence[int]) -> List[int]:
        return [-x for x in a]

    def and_word(self, a: Sequence[int], b: Sequence[int]) -> List[int]:
        return [self.and2(x, y) for x, y in zip(a, b)]

    def rotr(self, bits: Sequence[int], n: int) -> List[int]:
        """Right rotation; bit i of the result is bit (i+n) mod W of the input."""
        shift = n % self.width
        if shift == 0:
            return list(bits)
        return list(bits[shift:]) + list(bits[:shift])

    def shr(self, bits: Sequence[int], n: int) -> List[int]:
        """Logical right shift; vacated high bits are the constant FALSE."""
        return [bits[i + n] if i + n < self.width else self.false_lit for i in range(self.width)]

    def ch(self, x: Sequence[int], y: Sequence[int], z: Sequence[int]) -> List[int]:
        """``Ch(x, y, z) = (x AND y) XOR (NOT x AND z)``, bitwise (§4.1.2)."""
        out = []
        for xt, yt, zt in zip(x, y, z):
            out.append(self.xor2(self.and2(xt, yt), self.and2(-xt, zt)))
        return out

    def maj(self, x: Sequence[int], y: Sequence[int], z: Sequence[int]) -> List[int]:
        """``Maj(x, y, z) = (x AND y) XOR (x AND z) XOR (y AND z)`` (§4.1.2)."""
        out = []
        for xt, yt, zt in zip(x, y, z):
            out.append(self.xor2(self.xor2(self.and2(xt, yt), self.and2(xt, zt)), self.and2(yt, zt)))
        return out

    def big_sigma0(self, x: Sequence[int]) -> List[int]:
        """``ROTR^2 XOR ROTR^13 XOR ROTR^22`` (§4.1.2)."""
        return self.xor_word(self.xor_word(self.rotr(x, 2), self.rotr(x, 13)), self.rotr(x, 22))

    def big_sigma1(self, x: Sequence[int]) -> List[int]:
        """``ROTR^6 XOR ROTR^11 XOR ROTR^25`` (§4.1.2)."""
        return self.xor_word(self.xor_word(self.rotr(x, 6), self.rotr(x, 11)), self.rotr(x, 25))

    def small_sigma0(self, x: Sequence[int]) -> List[int]:
        """``ROTR^7 XOR ROTR^18 XOR SHR^3`` (§4.1.2)."""
        return self.xor_word(self.xor_word(self.rotr(x, 7), self.rotr(x, 18)), self.shr(x, 3))

    def small_sigma1(self, x: Sequence[int]) -> List[int]:
        """``ROTR^17 XOR ROTR^19 XOR SHR^10`` (§4.1.2)."""
        return self.xor_word(self.xor_word(self.rotr(x, 17), self.rotr(x, 19)), self.shr(x, 10))

    # -- addition (FIPS 180-4 §4.1.3) -------------------------------------
    def full_adder(self, a: int, b: int, carry: int) -> Tuple[int, int]:
        """One bit slice: ``(sum, carry_out)`` from five fresh variables."""
        propagate = self.xor2(a, b)
        total = self.xor2(propagate, carry)
        generate = self.and2(a, b)
        absorb = self.and2(propagate, carry)
        return total, self.or2(generate, absorb)

    def add(
        self,
        a_bits: Sequence[int],
        b_bits: Sequence[int],
        carry_in: Optional[int] = None,
        W: Optional[int] = None,
    ) -> Tuple[List[int], int]:
        """Ripple-carry ``a + b + carry_in`` over W bits.

        ``carry_in`` is a literal; ``None`` means the constant FALSE. ``W``
        defaults to the encoder width and must match it when given. The result is
        ``(sum_bits, carry_out)``; dropping ``carry_out`` gives addition modulo
        2**W, which is what a SHA-256 round uses.
        """
        width = self.width if W is None else W
        if width != self.width:
            raise ValueError(f"W={width} does not match the encoder width {self.width}")
        if len(a_bits) != width or len(b_bits) != width:
            raise ValueError("both operands must have W bits")
        carry = self.false_lit if carry_in is None else carry_in
        total: List[int] = []
        for i in range(width):
            bit, carry = self.full_adder(a_bits[i], b_bits[i], carry)
            total.append(bit)
        return total, carry

    def add_word(
        self,
        a_bits: Sequence[int],
        b_bits: Sequence[int],
        carry_in: Optional[int] = None,
    ) -> List[int]:
        """``a + b + carry_in`` modulo 2**W; the carry out is dropped."""
        total, _ = self.add(a_bits, b_bits, carry_in)
        return total

    def add_many(self, operands: Sequence[Sequence[int]]) -> List[int]:
        """Sum of two or more words modulo 2**W, left to right."""
        if len(operands) < 2:
            raise ValueError("add_many needs at least two operands")
        total = list(operands[0])
        for operand in operands[1:]:
            total = self.add_word(total, operand)
        return total

    # -- serialization ----------------------------------------------------
    def to_cnf(self) -> CNF:
        """The accumulated formula, validated by :class:`cqhecs.sat.CNF`."""
        return CNF(num_vars=self._num_vars, clauses=tuple(self._clauses), source="sha256-round-cnf")


# ---------------------------------------------------------------------------
# Round construction (FIPS 180-4 §5.3.3 steps 1-3)
# ---------------------------------------------------------------------------
def _check_rounds(rounds: int) -> None:
    if not 0 <= rounds <= MAX_ROUNDS:
        raise ValueError(f"rounds must be between 0 and {MAX_ROUNDS}, got {rounds}")


def _check_state(state: Sequence[int], width: int) -> None:
    if len(state) != STATE_WORDS:
        raise ValueError("state must have eight words")
    mask = width_mask(width)
    for word in state:
        if not 0 <= word <= mask:
            raise ValueError(f"state word {word} does not fit in {width} bits")


def _check_words(words: Sequence[int], width: int) -> None:
    if len(words) != MESSAGE_WORDS:
        raise ValueError("schedule needs exactly 16 input words")
    mask = width_mask(width)
    for word in words:
        if not 0 <= word <= mask:
            raise ValueError(f"message word {word} does not fit in {width} bits")


@dataclass(frozen=True)
class SatInstance:
    """A CNF instance plus the wiring needed to replay a model.

    ``dimacs`` is the complete formula; ``to_cnf()`` parses it back with the
    strict DIMACS parser of :mod:`cqhecs.sat`, so a solver sees exactly the text
    recorded here. ``input_bits``/``output_bits`` are the literals of the sixteen
    schedule inputs and the eight output words, little-endian, so a model can be
    decoded into words and compared with the Python reference.
    """

    width: int
    rounds: int
    feed_forward: bool
    num_vars: int
    num_clauses: int
    dimacs: str
    input_state: Tuple[int, ...]
    input_bits: Tuple[Tuple[int, ...], ...]
    output_bits: Tuple[Tuple[int, ...], ...]
    free_words: Tuple[int, ...]
    asserted_state: Optional[Tuple[int, ...]]

    # -- decoding ---------------------------------------------------------
    @staticmethod
    def decode_word(bits: Sequence[int], assignment: Dict[int, bool]) -> int:
        """The integer value of one word under a model, little-endian."""
        value = 0
        for index, literal in enumerate(bits):
            bit = assignment.get(abs(literal))
            if bit is None:
                raise ValueError(f"the assignment does not assign variable {abs(literal)}")
            if bit == (literal > 0):
                value |= 1 << index
        return value

    def decode_input_words(self, assignment: Dict[int, bool]) -> Tuple[int, ...]:
        """The sixteen schedule inputs under a model."""
        return tuple(self.decode_word(bits, assignment) for bits in self.input_bits)

    def decode_output(self, assignment: Dict[int, bool]) -> Tuple[int, ...]:
        """The eight output-state words under a model."""
        return tuple(self.decode_word(bits, assignment) for bits in self.output_bits)

    # -- solver handoff ---------------------------------------------------
    def to_cnf(self) -> CNF:
        """Parse the recorded DIMACS text with the strict parser."""
        return parse_dimacs(self.dimacs, source=f"sha256:W={self.width}:rounds={self.rounds}")

    @property
    def free_bits(self) -> int:
        """Number of unconstrained schedule-input bits the solver may choose."""
        return len(self.free_words) * self.width


def sha256_round_cnf(
    input_state: Sequence[int],
    words: Sequence[int],
    rounds: int,
    *,
    width: int = DEFAULT_WIDTH,
    free_words: Sequence[int] = (),
    asserted_state: Optional[Sequence[int]] = None,
    asserted_words: Optional[Sequence[int]] = None,
    feed_forward: bool = True,
) -> SatInstance:
    """Build the CNF of ``rounds`` compression rounds from an explicit state.

    ``words`` are the sixteen schedule inputs. Indices listed in ``free_words``
    are replaced by fresh variables (the remaining words stay fixed constants),
    so a model chooses them. ``asserted_state``, when given, asserts the eight
    output words bit by bit (or only the indices in ``asserted_words``).

    The schedule is expanded in CNF for rounds above 16 (FIPS 180-4 §5.2.2,
    step 1). Nothing else is assumed: no round is skipped and no shortcut is
    applied.
    """
    _check_rounds(rounds)
    _check_state(input_state, width)
    _check_words(words, width)
    free = tuple(sorted({int(i) for i in free_words}))
    for index in free:
        if not 0 <= index < MESSAGE_WORDS:
            raise ValueError(f"free word index {index} is outside 0..15")
    assert_words: Tuple[int, ...]
    if asserted_state is None:
        assert_words = ()
    else:
        _check_state(asserted_state, width)
        assert_words = tuple(range(STATE_WORDS)) if asserted_words is None else tuple(sorted(asserted_words))
        for index in assert_words:
            if not 0 <= index < STATE_WORDS:
                raise ValueError(f"asserted word index {index} is outside 0..7")

    encoder = WordEncoder(width)
    k, _ = rounded_constants(width)

    # Message schedule: sixteen inputs, then the CNF expansion of §5.2.2.
    schedule: List[List[int]] = []
    for index in range(MESSAGE_WORDS):
        if index in free:
            schedule.append([encoder.new_var() for _ in range(width)])
        else:
            schedule.append(encoder.const_bits(words[index]))
    for t in range(MESSAGE_WORDS, rounds):
        expanded = encoder.add_many(
            [
                encoder.small_sigma1(schedule[t - 2]),
                schedule[t - 7],
                encoder.small_sigma0(schedule[t - 15]),
                schedule[t - 16],
            ]
        )
        schedule.append(expanded)

    state = [encoder.const_bits(word) for word in input_state]
    work = state
    for t in range(rounds):
        a, b, c, d, e, f, g, h = work
        t1 = encoder.add_many([h, encoder.big_sigma1(e), encoder.ch(e, f, g), encoder.const_bits(k[t]), schedule[t]])
        t2 = encoder.add_word(encoder.big_sigma0(a), encoder.maj(a, b, c))
        work = [encoder.add_word(t1, t2), a, b, c, encoder.add_word(d, t1), e, f, g]

    if feed_forward:
        output = [encoder.add_word(work[i], state[i]) for i in range(STATE_WORDS)]
    else:
        output = list(work)

    if asserted_state is not None:
        for index in assert_words:
            for bit in range(width):
                literal = output[index][bit]
                encoder.clause(literal if (asserted_state[index] >> bit) & 1 else -literal)

    cnf = encoder.to_cnf()
    return SatInstance(
        width=width,
        rounds=rounds,
        feed_forward=feed_forward,
        num_vars=cnf.num_vars,
        num_clauses=cnf.num_clauses,
        dimacs=cnf.to_dimacs(),
        input_state=tuple(input_state),
        input_bits=tuple(tuple(bits) for bits in schedule[:MESSAGE_WORDS]),
        output_bits=tuple(tuple(bits) for bits in output),
        free_words=free,
        asserted_state=None if asserted_state is None else (tuple(asserted_state) if assert_words else None),
    )


# ---------------------------------------------------------------------------
# The two entry points
# ---------------------------------------------------------------------------
def build_verification_instance(
    block: bytes,
    rounds: int,
    *,
    width: int = DEFAULT_WIDTH,
    expected_state: Optional[Sequence[int]] = None,
    feed_forward: bool = True,
) -> SatInstance:
    """Encode "this block compresses to this state in ``rounds`` rounds".

    The sixteen message words are constants taken from ``block``
    (FIPS 180-4 §5.2.1) and every output word is asserted. With the default
    ``expected_state`` -- the output of :func:`width_compress` -- the instance is
    satisfiable exactly when the clauses and the Python model agree, which is the
    differential test. Passing a different ``expected_state`` asks a real
    question instead: the flipped-bit test passes a state one bit away and
    expects UNSAT.

    ``expected_state`` is never derived from the solver's own answer; it defaults
    to the independent reference, and a caller may supply any claim.
    """
    words = block_words(block, width)
    state = masked_iv(width)
    if expected_state is None:
        expected_state = width_compress(state, words, rounds=rounds, width=width, feed_forward=feed_forward)
    return sha256_round_cnf(
        state,
        words,
        rounds,
        width=width,
        asserted_state=expected_state,
        feed_forward=feed_forward,
    )


def build_partial_preimage_instance(
    block: bytes,
    rounds: int,
    free_words: Sequence[int],
    *,
    width: int = DEFAULT_WIDTH,
    target_state: Optional[Sequence[int]] = None,
    asserted_words: Optional[Sequence[int]] = None,
    feed_forward: bool = True,
) -> SatInstance:
    """Encode "some value of the free schedule words reaches ``target_state``".

    The words in ``free_words`` are fresh variables; the other schedule inputs
    keep the values of ``block``. All eight output words are asserted by default
    (``asserted_words`` selects a subset). ``target_state`` defaults to the
    reference output of ``block``, so the block's own words are one witness and
    the instance is satisfiable by construction -- the question is how many other
    witnesses exist, which is what :func:`cqhecs.sat.count_models` answers.

    This is a genuine preimage question at the encoded size. It is not a claim
    about inverting SHA-256: at the tested sizes an exhaustive Python search is
    the oracle, and larger sizes are reported as UNRESOLVED.
    """
    words = block_words(block, width)
    state = masked_iv(width)
    if target_state is None:
        target_state = width_compress(state, words, rounds=rounds, width=width, feed_forward=feed_forward)
    return sha256_round_cnf(
        state,
        words,
        rounds,
        width=width,
        free_words=free_words,
        asserted_state=target_state,
        asserted_words=asserted_words,
        feed_forward=feed_forward,
    )


# ---------------------------------------------------------------------------
# Model verification against the Python reference
# ---------------------------------------------------------------------------
def verify_model(
    instance: SatInstance,
    assignment: Dict[int, bool],
    *,
    expected_state: Optional[Sequence[int]] = None,
) -> Dict[str, object]:
    """Replay a solver model against the Python reference, independently of the CNF.

    The decoded schedule inputs are compressed with :func:`width_compress`
    (``sha256_reference.compress`` at W = 32) and compared with the state decoded
    from the model's output wires. ``agrees`` is True only if they match *and*,
    when ``expected_state`` is given, that state is reached as well.

    ``formula_satisfied`` reports the separate question of whether the model
    actually satisfies the recorded clauses.
    """
    words = instance.decode_input_words(assignment)
    decoded = instance.decode_output(assignment)
    recomputed = width_compress(
        instance.input_state,
        words,
        rounds=instance.rounds,
        width=instance.width,
        feed_forward=instance.feed_forward,
    )
    target = tuple(expected_state) if expected_state is not None else instance.asserted_state
    agrees = decoded == recomputed and (target is None or decoded == tuple(target))
    return {
        "agrees": bool(agrees),
        "width": instance.width,
        "rounds": instance.rounds,
        "free_words": instance.free_words,
        "reference": (
            "cqhecs.sha.sha256_reference.compress"
            if instance.width == DEFAULT_WIDTH
            else f"toy_compress (W={instance.width}; NOT SHA-256)"
        ),
        "input_state": instance.input_state,
        "input_words": words,
        "decoded_state": decoded,
        "recomputed_state": recomputed,
        "asserted_state": target,
        "formula_satisfied": instance.to_cnf().is_satisfied(assignment),
    }
