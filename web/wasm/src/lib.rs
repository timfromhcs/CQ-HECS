//! Exact f64 state-vector core for the CQ-HECS web emulator.
//!
//! The state is 2^n complex amplitudes stored interleaved (re, im) in f64.
//! Nothing is truncated or compressed: every amplitude is kept, and the only
//! deviation from exact arithmetic is IEEE-754 double rounding (~1e-16 per op).
//! Allocation failures are reported to JavaScript instead of aborting.
//!
//! Bit order: qubit q is bit q of the basis index (qubit 0 least significant),
//! matching Qiskit and the CQ-HECS Python package.

#![allow(clippy::missing_safety_doc)]

use std::alloc::{alloc, dealloc, Layout};

static mut STATE: Vec<f64> = Vec::new();
static mut NUM_QUBITS: u32 = 0;

#[allow(static_mut_refs)]
fn state() -> &'static mut Vec<f64> {
    unsafe { &mut STATE }
}

/// Allocate |0...0> on `n` qubits. Returns 0 on success, -1 if the memory
/// could not be reserved, -2 if `n` is outside 1..=30.
#[no_mangle]
pub extern "C" fn sv_init(n: u32) -> i32 {
    if n == 0 || n > 30 {
        return -2;
    }
    let len = 2usize << n; // 2^n complex = 2^(n+1) f64
    let s = state();
    *s = Vec::new(); // release the previous state before reserving
    if s.try_reserve_exact(len).is_err() {
        return -1;
    }
    s.resize(len, 0.0);
    s[0] = 1.0;
    unsafe { NUM_QUBITS = n };
    0
}

#[no_mangle]
pub extern "C" fn sv_free() {
    *state() = Vec::new();
    unsafe { NUM_QUBITS = 0 };
}

#[no_mangle]
pub extern "C" fn sv_ptr() -> *const f64 {
    state().as_ptr()
}

#[no_mangle]
pub extern "C" fn sv_num_qubits() -> u32 {
    unsafe { NUM_QUBITS }
}

/// Reset to |0...0> without reallocating.
#[no_mangle]
pub extern "C" fn sv_reset() {
    let s = state();
    s.iter_mut().for_each(|v| *v = 0.0);
    if !s.is_empty() {
        s[0] = 1.0;
    }
}

/// Scratch buffers for JavaScript (probabilities, shots). Returns null on failure.
#[no_mangle]
pub extern "C" fn buf_alloc(bytes: usize) -> *mut u8 {
    if bytes == 0 {
        return std::ptr::null_mut();
    }
    match Layout::from_size_align(bytes, 8) {
        Ok(layout) => unsafe { alloc(layout) },
        Err(_) => std::ptr::null_mut(),
    }
}

#[no_mangle]
pub unsafe extern "C" fn buf_free(ptr: *mut u8, bytes: usize) {
    if !ptr.is_null() && bytes > 0 {
        dealloc(ptr, Layout::from_size_align_unchecked(bytes, 8));
    }
}

/// Apply the 2x2 matrix [[a, b], [c, d]] to `target`, on the basis states whose
/// `ctrl_mask` bits are all 1. `ctrl_mask = 0` is an uncontrolled gate.
#[no_mangle]
#[allow(clippy::too_many_arguments)]
pub extern "C" fn apply_u(
    target: u32,
    ctrl_mask: u32,
    ar: f64, ai: f64, br: f64, bi: f64,
    cr: f64, ci: f64, dr: f64, di: f64,
) {
    let n = unsafe { NUM_QUBITS };
    if target >= n || ctrl_mask & (1 << target) != 0 {
        return;
    }
    let s = state();
    let dim = 1usize << n;
    let tbit = 1usize << target;
    let ctrl = ctrl_mask as usize;
    let mut base = 0usize;
    while base < dim {
        // Walk the half-blocks where the target bit is 0.
        for i in base..base + tbit {
            if i & ctrl != ctrl {
                continue;
            }
            let j = i | tbit;
            let (xr, xi) = (s[2 * i], s[2 * i + 1]);
            let (yr, yi) = (s[2 * j], s[2 * j + 1]);
            s[2 * i] = ar * xr - ai * xi + br * yr - bi * yi;
            s[2 * i + 1] = ar * xi + ai * xr + br * yi + bi * yr;
            s[2 * j] = cr * xr - ci * xi + dr * yr - di * yi;
            s[2 * j + 1] = cr * xi + ci * xr + dr * yi + di * yr;
        }
        base += tbit << 1;
    }
}

/// Swap qubits `a` and `b` (optionally controlled by `ctrl_mask`).
#[no_mangle]
pub extern "C" fn apply_swap(a: u32, b: u32, ctrl_mask: u32) {
    let n = unsafe { NUM_QUBITS };
    if a >= n || b >= n || a == b {
        return;
    }
    let s = state();
    let (ba, bb) = (1usize << a, 1usize << b);
    let ctrl = ctrl_mask as usize;
    for i in 0..(1usize << n) {
        // Visit each pair once: bit a = 1, bit b = 0.
        if i & ba != 0 && i & bb == 0 && i & ctrl == ctrl {
            let j = (i & !ba) | bb;
            s.swap(2 * i, 2 * j);
            s.swap(2 * i + 1, 2 * j + 1);
        }
    }
}

/// Sum of |amplitude|^2; 1 up to rounding for a unitary circuit.
#[no_mangle]
pub extern "C" fn sv_norm() -> f64 {
    state().chunks_exact(2).map(|c| c[0] * c[0] + c[1] * c[1]).sum()
}

/// Write all 2^n probabilities as f64 into `out`.
#[no_mangle]
pub unsafe extern "C" fn probs_into(out: *mut f64) {
    let s = state();
    let dim = s.len() / 2;
    let out = std::slice::from_raw_parts_mut(out, dim);
    for (k, c) in s.chunks_exact(2).enumerate() {
        out[k] = c[0] * c[0] + c[1] * c[1];
    }
}

/// Bloch vector (x, y, z) of qubit `q` from its reduced density matrix.
#[no_mangle]
pub unsafe extern "C" fn bloch_into(q: u32, out: *mut f64) {
    let n = NUM_QUBITS;
    let out = std::slice::from_raw_parts_mut(out, 3);
    if q >= n {
        out.copy_from_slice(&[0.0, 0.0, 0.0]);
        return;
    }
    let s = state();
    let bit = 1usize << q;
    let (mut p0, mut p1, mut re01, mut im01) = (0.0, 0.0, 0.0, 0.0);
    for i in 0..(1usize << n) {
        if i & bit != 0 {
            continue;
        }
        let j = i | bit;
        let (xr, xi, yr, yi) = (s[2 * i], s[2 * i + 1], s[2 * j], s[2 * j + 1]);
        p0 += xr * xr + xi * xi;
        p1 += yr * yr + yi * yi;
        // rho01 = sum x * conj(y)
        re01 += xr * yr + xi * yi;
        im01 += xi * yr - xr * yi;
    }
    out[0] = 2.0 * re01;
    out[1] = -2.0 * im01;
    out[2] = p0 - p1;
}

/// <Z...Z> on the qubits in `mask`.
#[no_mangle]
pub extern "C" fn expect_z(mask: u32) -> f64 {
    let m = mask as usize;
    state()
        .chunks_exact(2)
        .enumerate()
        .map(|(k, c)| {
            let p = c[0] * c[0] + c[1] * c[1];
            if (k & m).count_ones() % 2 == 0 { p } else { -p }
        })
        .sum()
}

// xoshiro256** seeded by splitmix64: reproducible shots for a given seed.
struct Rng([u64; 4]);

impl Rng {
    fn new(seed: u64) -> Self {
        let mut z = seed;
        let mut next = || {
            z = z.wrapping_add(0x9E37_79B9_7F4A_7C15);
            let mut x = z;
            x = (x ^ (x >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
            x = (x ^ (x >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
            x ^ (x >> 31)
        };
        Rng([next(), next(), next(), next()])
    }
    fn next_u64(&mut self) -> u64 {
        let s = &mut self.0;
        let result = s[1].wrapping_mul(5).rotate_left(7).wrapping_mul(9);
        let t = s[1] << 17;
        s[2] ^= s[0];
        s[3] ^= s[1];
        s[1] ^= s[2];
        s[0] ^= s[3];
        s[2] ^= t;
        s[3] = s[3].rotate_left(45);
        result
    }
    fn uniform(&mut self) -> f64 {
        (self.next_u64() >> 11) as f64 * (1.0 / (1u64 << 53) as f64)
    }
}

/// Draw `shots` basis indices into `out` (u32). `scratch` must hold `shots`
/// f64. One pass over the state after sorting the uniforms, so no 2^n
/// probability buffer is needed.
#[no_mangle]
pub unsafe extern "C" fn sample_into(shots: u32, seed: f64, scratch: *mut f64, out: *mut u32) {
    let shots = shots as usize;
    let u = std::slice::from_raw_parts_mut(scratch, shots);
    let out = std::slice::from_raw_parts_mut(out, shots);
    let mut rng = Rng::new(seed.to_bits());
    let total = sv_norm();
    for v in u.iter_mut() {
        *v = rng.uniform() * total;
    }
    u.sort_unstable_by(|a, b| a.partial_cmp(b).unwrap());
    let s = state();
    let dim = s.len() / 2;
    let mut cumulative = 0.0;
    let mut k = 0usize;
    for (idx, slot) in out.iter_mut().enumerate() {
        let target = u[idx];
        while k + 1 < dim {
            let p = s[2 * k] * s[2 * k] + s[2 * k + 1] * s[2 * k + 1];
            if cumulative + p > target {
                break;
            }
            cumulative += p;
            k += 1;
        }
        *slot = k as u32;
    }
}

/// Projective measurement of qubit `q` with a given uniform draw `r` in [0,1).
/// Collapses and renormalizes the state; returns the outcome 0/1.
#[no_mangle]
pub extern "C" fn measure_qubit(q: u32, r: f64) -> u32 {
    let n = unsafe { NUM_QUBITS };
    if q >= n {
        return 0;
    }
    let s = state();
    let bit = 1usize << q;
    let mut p1 = 0.0;
    for (k, c) in s.chunks_exact(2).enumerate() {
        if k & bit != 0 {
            p1 += c[0] * c[0] + c[1] * c[1];
        }
    }
    let total = sv_norm();
    let outcome = if r * total < p1 { 1usize } else { 0usize };
    let keep = if outcome == 1 { p1 } else { total - p1 };
    let scale = if keep > 0.0 { 1.0 / keep.sqrt() } else { 0.0 };
    for (k, c) in s.chunks_exact_mut(2).enumerate() {
        if ((k & bit) != 0) as usize == outcome {
            c[0] *= scale;
            c[1] *= scale;
        } else {
            c[0] = 0.0;
            c[1] = 0.0;
        }
    }
    outcome as u32
}

// ---------------------------------------------------------------------------
// SHA-256 (FIPS 180-4), scalar.
//
// A third independent implementation next to the Python reference, the
// TypeScript reference and the firmware's C: same test vectors, different
// language and compiler, so a transcription error in any one of them shows up as
// a mismatch instead of agreeing by construction.
//
// Scalar only, on purpose: a SIMD variant would need a second code path and its
// own evidence, and the probe reports the SIMD tier as unavailable rather than
// pretending otherwise.

const K: [u32; 64] = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
];

const IV: [u32; 8] = [
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
];

fn compress(state: &mut [u32; 8], block: &[u8]) {
    let mut w = [0u32; 64];
    for i in 0..16 {
        w[i] = u32::from_be_bytes([block[4 * i], block[4 * i + 1], block[4 * i + 2], block[4 * i + 3]]);
    }
    for i in 16..64 {
        let s0 = w[i - 15].rotate_right(7) ^ w[i - 15].rotate_right(18) ^ (w[i - 15] >> 3);
        let s1 = w[i - 2].rotate_right(17) ^ w[i - 2].rotate_right(19) ^ (w[i - 2] >> 10);
        w[i] = w[i - 16].wrapping_add(s0).wrapping_add(w[i - 7]).wrapping_add(s1);
    }
    let mut a = state[0];
    let mut b = state[1];
    let mut c = state[2];
    let mut d = state[3];
    let mut e = state[4];
    let mut f = state[5];
    let mut g = state[6];
    let mut h = state[7];
    for t in 0..64 {
        let s1 = e.rotate_right(6) ^ e.rotate_right(11) ^ e.rotate_right(25);
        let ch = (e & f) ^ ((!e) & g);
        let t1 = h.wrapping_add(s1).wrapping_add(ch).wrapping_add(K[t]).wrapping_add(w[t]);
        let s0 = a.rotate_right(2) ^ a.rotate_right(13) ^ a.rotate_right(22);
        let maj = (a & b) ^ (a & c) ^ (b & c);
        let t2 = s0.wrapping_add(maj);
        h = g;
        g = f;
        f = e;
        e = d.wrapping_add(t1);
        d = c;
        c = b;
        b = a;
        a = t1.wrapping_add(t2);
    }
    state[0] = state[0].wrapping_add(a);
    state[1] = state[1].wrapping_add(b);
    state[2] = state[2].wrapping_add(c);
    state[3] = state[3].wrapping_add(d);
    state[4] = state[4].wrapping_add(e);
    state[5] = state[5].wrapping_add(f);
    state[6] = state[6].wrapping_add(g);
    state[7] = state[7].wrapping_add(h);
}

fn sha256_into(data: &[u8], out: &mut [u8; 32]) {
    let mut state = IV;
    let mut offset = 0usize;
    while offset + 64 <= data.len() {
        compress(&mut state, &data[offset..offset + 64]);
        offset += 64;
    }
    let rest = data.len() - offset;
    let mut tail = [0u8; 128];
    tail[..rest].copy_from_slice(&data[offset..]);
    tail[rest] = 0x80;
    let tail_len = if rest < 56 { 64 } else { 128 };
    let bits = (data.len() as u64).wrapping_mul(8);
    tail[tail_len - 8..tail_len].copy_from_slice(&bits.to_be_bytes());
    compress(&mut state, &tail[..64]);
    if tail_len == 128 {
        compress(&mut state, &tail[64..]);
    }
    for (i, word) in state.iter().enumerate() {
        out[4 * i..4 * i + 4].copy_from_slice(&word.to_be_bytes());
    }
}

/// SHA-256 of `len` bytes at `data` into 32 bytes at `out`. Returns 0 on success,
/// -1 for a null pointer (a caller bug, reported instead of a trap).
#[no_mangle]
pub extern "C" fn sha256(data: *const u8, len: usize, out: *mut u8) -> i32 {
    if data.is_null() || out.is_null() {
        return -1;
    }
    let input = unsafe { std::slice::from_raw_parts(data, len) };
    let mut digest = [0u8; 32];
    sha256_into(input, &mut digest);
    unsafe { std::ptr::copy_nonoverlapping(digest.as_ptr(), out, 32) };
    0
}

/// Bitcoin-style double SHA-256 of `len` bytes at `data` into 32 bytes at `out`.
#[no_mangle]
pub extern "C" fn sha256d(data: *const u8, len: usize, out: *mut u8) -> i32 {
    if data.is_null() || out.is_null() {
        return -1;
    }
    let input = unsafe { std::slice::from_raw_parts(data, len) };
    let mut inner = [0u8; 32];
    sha256_into(input, &mut inner);
    let mut outer = [0u8; 32];
    sha256_into(&inner, &mut outer);
    unsafe { std::ptr::copy_nonoverlapping(outer.as_ptr(), out, 32) };
    0
}
