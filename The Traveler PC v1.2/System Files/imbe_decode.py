#!/usr/bin/env python3
"""
imbe_decode.py  -  a pure-Python IMBE 7200x4400 (P25 Phase-1) voice decoder.

No C extension, no binary, no compiler, no DVstick -- just Python + numpy, so it
runs anywhere Python does (a PC, the box, offline). This is a faithful port of
mbelib's imbe7200x4400 path (ISC), the exact reference we ear-confirmed; the
glibc rand() used by the unvoiced synthesis is replicated so the output matches
the C decoder, not just resembles it.

Input : imbe_fr[8][23] (the 144-bit over-air IMBE frame, as voice_frames emits).
Output: 160 int16 PCM samples at 8 kHz per frame (20 ms).

Port map:  ecc.c -> golay2312/hamming1511 ;  imbe7200x4400.c -> ecc wrappers,
demodulate (PN descramble), decode_imbe4400_parms ;  mbelib.c -> spectral-amp
enhance + synthesize_speech + floattoshort.  Tables auto-extracted from the
mbelib headers into imbe_tables.py.
"""
import os, sys, math
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import imbe_tables as T

M_PI = math.pi
M_E = math.e
RAND_MAX = 2147483647


# ----------------------------------------------------------------------------
# glibc rand() replica (TYPE_3, deg=31 sep=3, default seed 1) -- verified to
# reproduce C rand() exactly, so the unvoiced noise realization matches mbelib.
# ----------------------------------------------------------------------------
class _GlibcRand:
    def __init__(self, seed=1):
        st = [0] * 31
        st[0] = seed
        for i in range(1, 31):
            st[i] = (16807 * st[i - 1]) % 2147483647
            if st[i] < 0:
                st[i] += 2147483647
        self.st = st; self.f = 3; self.r = 0
        for _ in range(310):
            self._step()
    def _step(self):
        self.st[self.f] = (self.st[self.f] + self.st[self.r]) & 0xffffffff
        res = (self.st[self.f] >> 1) & 0x7fffffff
        self.f = (self.f + 1) % 31; self.r = (self.r + 1) % 31
        return res
    def rand(self):
        return self._step()
    def randf(self):                       # mbe_rand(): [0,1]
        return float(self._step()) / float(RAND_MAX)
    def phase(self):                       # mbe_rand_phase(): [-pi,pi]
        return self.randf() * (M_PI * 2.0) - M_PI


# ----------------------------------------------------------------------------
# ECC  (ecc.c)
# ----------------------------------------------------------------------------
def _check_golay_block(block):
    mask = 0x400000
    ecc = 0
    for i in range(12):
        if block & mask:
            ecc ^= T.golayGenerator[i]
        mask >>= 1
    eccbits = block & 0x7ff
    syndrome = ecc ^ eccbits
    databits = (block >> 11) ^ T.golayMatrix[syndrome]
    return databits

def golay2312(inb):
    block = 0
    for i in range(22, -1, -1):
        block = (block << 1) + inb[i]
    block = _check_golay_block(block)
    out = [0] * 23
    for i in range(22, 10, -1):
        out[i] = (block & 2048) >> 11
        block <<= 1
    for i in range(10, -1, -1):
        out[i] = inb[i]
    errs = sum(1 for i in range(22, 10, -1) if out[i] != inb[i])
    return out, errs

def hamming1511(inb):
    block = 0
    for i in range(14, -1, -1):
        block = (block << 1) | inb[i]
    syndrome = 0
    for i in range(4):
        syndrome <<= 1
        stmp = block & T.hammingGenerator[i]
        stmp2 = stmp % 2
        for _ in range(14):
            stmp >>= 1; stmp2 ^= stmp % 2
        syndrome |= stmp2
    errs = 0
    if syndrome > 0:
        errs = 1
        block ^= T.hammingMatrix[syndrome]
    out = [0] * 15
    for i in range(14, -1, -1):
        out[i] = (block & 0x4000) >> 14
        block <<= 1
    return out, errs


# ----------------------------------------------------------------------------
# IMBE frame -> imbe_d[88]  (imbe7200x4400.c)
# ----------------------------------------------------------------------------
def _ecc_c0(fr):
    out, errs = golay2312([fr[0][j] for j in range(23)])
    for j in range(23):
        fr[0][j] = out[j]
    return errs

def _demodulate(fr):
    tmp = "".join(str(fr[0][i]) for i in range(22, 10, -1))
    foo = int(tmp, 2)
    pr = [0] * 115
    pr[0] = 16 * foo
    for i in range(1, 115):
        pr[i] = (173 * pr[i - 1] + 13849) & 0xffff
    for i in range(1, 115):
        pr[i] = pr[i] // 32768
    k = 1
    for i in range(1, 4):
        for j in range(22, -1, -1):
            fr[i][j] ^= pr[k]; k += 1
    for i in range(4, 7):
        for j in range(14, -1, -1):
            fr[i][j] ^= pr[k]; k += 1

def _ecc_data(fr):
    imbe = []
    errs = 0
    for i in range(4):
        if i > 0:
            gout, e = golay2312([fr[i][j] for j in range(23)])
            errs += e
            for j in range(22, 10, -1):
                imbe.append(gout[j])
        else:
            for j in range(22, 10, -1):
                imbe.append(fr[i][j])
    for i in range(4, 7):
        hout, e = hamming1511([fr[i][j] for j in range(15)])
        errs += e
        for j in range(14, 3, -1):
            imbe.append(hout[j])
    for j in range(6, -1, -1):
        imbe.append(fr[7][j])
    return imbe, errs                       # len 88


# ----------------------------------------------------------------------------
# mbe_parms
# ----------------------------------------------------------------------------
class MbeParms:
    __slots__ = ("w0", "L", "K", "Vl", "Ml", "log2Ml", "PHIl", "PSIl", "gamma", "repeat")
    def __init__(self):
        # size 58 (0..57): the C reads log2Ml[intkl+1] which can touch index 57
        # when prev.L==56, but always * deltal(=0) there -> a harmless 0.0.
        self.w0 = 0.0; self.L = 0; self.K = 0
        self.Vl = [0] * 58; self.Ml = [0.0] * 58; self.log2Ml = [0.0] * 58
        self.PHIl = [0.0] * 58; self.PSIl = [0.0] * 58
        self.gamma = 0.0; self.repeat = 0

def init_parms():
    cur, prev, penh = MbeParms(), MbeParms(), MbeParms()
    prev.w0 = 0.09378; prev.L = 30; prev.K = 10; prev.gamma = 0.0
    for l in range(57):
        prev.Ml[l] = 0.0; prev.Vl[l] = 0; prev.log2Ml[l] = 0.0
        prev.PHIl[l] = 0.0; prev.PSIl[l] = M_PI / 2.0
    prev.repeat = 0
    _move(prev, cur); _move(prev, penh)
    return cur, prev, penh

def _move(src, dst):
    dst.w0 = src.w0; dst.L = src.L; dst.K = src.K
    dst.gamma = src.gamma; dst.repeat = src.repeat
    for l in range(57):
        dst.Ml[l] = src.Ml[l]; dst.Vl[l] = src.Vl[l]; dst.log2Ml[l] = src.log2Ml[l]
        dst.PHIl[l] = src.PHIl[l]; dst.PSIl[l] = src.PSIl[l]
    dst.Ml[0] = 0.0

def _use_last(cur, prev):
    _move(prev, cur)


# ----------------------------------------------------------------------------
# decode_imbe4400_parms  (imbe7200x4400.c mbe_decodeImbe4400Parms)
# ----------------------------------------------------------------------------
def decode_imbe4400_parms(imbe_d, cur, prev):
    cur.repeat = prev.repeat
    s = "".join(str(imbe_d[i]) for i in (0, 1, 2, 3, 4, 5)) + \
        str(imbe_d[85]) + str(imbe_d[86])
    b0 = int(s, 2)
    if b0 > 207:
        return 1
    cur.w0 = float(np.float32((4.0 * M_PI) / (float(b0) + 39.5)))   # C stores w0 as float32
    L = int(0.9254 * int((M_PI / cur.w0) + 0.25))
    if L > 56 or L < 9:
        return 1
    cur.L = L; L9 = L - 9
    if L < 37:
        K = int((L + 2) / 3)
    else:
        K = 12
    cur.K = K

    bb = [[0] * 12 for _ in range(58)]
    bo = T.bo[L9]
    idx = 0
    for i in range(6, 85):
        b1, b2 = bo[idx][0], bo[idx][1]
        bb[b1][b2] = imbe_d[i]
        idx += 1

    # Vl
    j = 1; k = K - 1
    for i in range(1, L + 1):
        cur.Vl[i] = bb[1][k]
        if j == 3:
            j = 1
            if k > 0: k -= 1
            else: k = 0
        else:
            j += 1

    Gm = [0.0] * 7
    s = "".join(str(bb[2][q]) for q in (5, 4, 3, 2, 1, 0))
    b2v = int(s, 2)
    Gm[1] = T.B2[b2v]

    ba = T.ba[L9]
    for i in range(2, 7):
        a1 = int(ba[i - 2][0]); a2 = ba[i - 2][1]
        bits = "".join(str(bb[i + 1][q]) for q in range(a1 - 1, -1, -1))
        bm = int(bits, 2) if bits else 0
        Gm[i] = a2 * (float(bm) - (2.0 ** (a1 - 1)) + 0.5)

    Ri = [0.0] * 7
    for i in range(1, 7):
        sm = 0.0
        for m in range(1, 7):
            am = 1 if m == 1 else 2
            sm += am * Gm[m] * math.cos((M_PI * (m - 1) * (i - 0.5)) / 6.0)
        Ri[i] = sm

    Cik = [[0.0] * 11 for _ in range(7)]
    ji_tab = T.ImbeJi[L9]
    m = 8
    for i in range(1, 7):
        Cik[i][1] = Ri[i]
        for k in range(2, ji_tab[i - 1] + 1):
            Bm = T.hoba[L9][m - 8]
            if Bm == 0:
                Cik[i][k] = 0.0
            else:
                bits = "".join(str(bb[m][(Bm - b) - 1]) for b in range(Bm))
                bm = int(bits, 2)
                Cik[i][k] = (T.quantstep[Bm - 1] * T.standdev[k - 2]) * (
                    (float(bm) - (2.0 ** (Bm - 1))) + 0.5)
            m += 1

    Tl = [0.0] * 57
    l = 1
    for i in range(1, 7):
        ji = ji_tab[i - 1]
        for j in range(1, ji + 1):
            sm = 0.0
            for k in range(1, ji + 1):
                ak = 1 if k == 1 else 2
                sm += ak * Cik[i][k] * math.cos((M_PI * (k - 1) * (j - 0.5)) / ji)
            Tl[l] = sm; l += 1

    if cur.L <= 15:
        rho = 0.4
    elif cur.L <= 24:
        rho = 0.03 * cur.L - 0.05
    else:
        rho = 0.7

    if cur.L > prev.L:
        for l in range(prev.L + 1, cur.L + 1):
            prev.Ml[l] = prev.Ml[prev.L]; prev.log2Ml[l] = prev.log2Ml[prev.L]

    flokl = [0.0] * 57; intkl = [0] * 57; deltal = [0.0] * 57
    Sum77 = 0.0
    for l in range(1, cur.L + 1):
        flokl[l] = (float(prev.L) / float(cur.L)) * l
        intkl[l] = int(flokl[l])
        deltal[l] = flokl[l] - intkl[l]
        Sum77 += ((1.0 - deltal[l]) * prev.log2Ml[intkl[l]]) + (deltal[l] * prev.log2Ml[intkl[l] + 1])
    Sum77 = (rho / float(cur.L)) * Sum77

    for l in range(1, cur.L + 1):
        c1 = rho * (1.0 - deltal[l]) * prev.log2Ml[intkl[l]]
        c2 = rho * deltal[l] * prev.log2Ml[intkl[l] + 1]
        cur.log2Ml[l] = Tl[l] + c1 + c2 - Sum77
        cur.Ml[l] = 2.0 ** cur.log2Ml[l]
    return 0


# ----------------------------------------------------------------------------
# spectral amplitude enhance + synthesis  (mbelib.c)
# ----------------------------------------------------------------------------
def spectral_amp_enhance(mp):
    Rm0 = 0.0; Rm1 = 0.0
    for l in range(1, mp.L + 1):
        Rm0 += mp.Ml[l] * mp.Ml[l]
        Rm1 += (mp.Ml[l] * mp.Ml[l]) * math.cos(mp.w0 * l)
    R2m0 = Rm0 * Rm0; R2m1 = Rm1 * Rm1
    Wl = [0.0] * 57
    for l in range(1, mp.L + 1):
        if mp.Ml[l] != 0:
            Wl[l] = math.sqrt(mp.Ml[l]) * (
                (0.96 * M_PI * ((R2m0 + R2m1) - (2.0 * Rm0 * Rm1 * math.cos(mp.w0 * l))))
                / (mp.w0 * Rm0 * (R2m0 - R2m1))) ** 0.25
            if (8 * l) <= mp.L:
                pass
            elif Wl[l] > 1.2:
                mp.Ml[l] = 1.2 * mp.Ml[l]
            elif Wl[l] < 0.5:
                mp.Ml[l] = 0.5 * mp.Ml[l]
            else:
                mp.Ml[l] = Wl[l] * mp.Ml[l]
    sm = 0.0
    for l in range(1, mp.L + 1):
        M = abs(mp.Ml[l]); sm += M * M
    gamma = 1.0 if sm == 0 else math.sqrt(Rm0 / sm)
    for l in range(1, mp.L + 1):
        mp.Ml[l] = gamma * mp.Ml[l]


def synthesize_speech(cur, prev, uvquality, rng):
    N = 160
    Ws = T.Ws
    aout = [0.0] * N
    f32 = np.float32
    # these feed the `> uvthreshold` tests that decide how many rand() are drawn;
    # C evaluates them in float32, so match that exactly or the noise stream drifts.
    uvthreshold = float(f32(f32(2700.0) * f32(M_PI)) / f32(4000.0))
    uvsine = 1.3591409 * M_E
    uvrand = 2.0
    if uvquality < 1 or uvquality > 64:
        uvquality = 3
    loguvquality = (1.0 / M_E) if uvquality == 1 else (math.log(uvquality) / uvquality)
    uvstep = 1.0 / uvquality
    qfactor = loguvquality
    uvoffset = (uvstep * (uvquality - 1)) / 2.0
    numUv = sum(1 for l in range(1, cur.L + 1) if cur.Vl[l] == 0)
    cw0 = cur.w0; pw0 = prev.w0

    if cur.L > prev.L:
        maxl = cur.L
        for l in range(prev.L + 1, maxl + 1):
            prev.Ml[l] = 0.0; prev.Vl[l] = 1
    else:
        maxl = prev.L
        for l in range(cur.L + 1, maxl + 1):
            cur.Ml[l] = 0.0; cur.Vl[l] = 1

    for l in range(1, 57):
        cur.PSIl[l] = prev.PSIl[l] + ((pw0 + cw0) * ((l * N) / 2.0))
        if l <= int(cur.L / 4):
            cur.PHIl[l] = cur.PSIl[l]
        else:
            cur.PHIl[l] = cur.PSIl[l] + ((numUv * rng.phase()) / cur.L)

    for l in range(1, maxl + 1):
        cw0l = float(f32(f32(cw0) * f32(l))); pw0l = float(f32(f32(pw0) * f32(l)))
        cvl = cur.Vl[l]; pvl = prev.Vl[l]
        cMl = cur.Ml[l]; pMl = prev.Ml[l]
        cPHI = cur.PHIl[l]; pPHI = prev.PHIl[l]
        if cvl == 0 and pvl == 1:
            rphase = [rng.phase() for _ in range(uvquality)]
            for n in range(N):
                C1 = Ws[n + N] * pMl * math.cos((pw0l * n) + pPHI)
                C3 = 0.0
                for i in range(uvquality):
                    C3 += math.cos((cw0 * n * (l + (i * uvstep) - uvoffset)) + rphase[i])
                    if cw0l > uvthreshold:
                        C3 += (cw0l - uvthreshold) * uvrand * rng.randf()
                C3 = C3 * uvsine * Ws[n] * cMl * qfactor
                aout[n] += C1 + C3
        elif cvl == 1 and pvl == 0:
            rphase = [rng.phase() for _ in range(uvquality)]
            for n in range(N):
                C1 = Ws[n] * cMl * math.cos((cw0l * (n - N)) + cPHI)
                C3 = 0.0
                for i in range(uvquality):
                    C3 += math.cos((pw0 * n * (l + (i * uvstep) - uvoffset)) + rphase[i])
                    if pw0l > uvthreshold:
                        C3 += (pw0l - uvthreshold) * uvrand * rng.randf()
                C3 = C3 * uvsine * Ws[n + N] * pMl * qfactor
                aout[n] += C1 + C3
        elif cvl == 1 or pvl == 1:
            for n in range(N):
                C1 = Ws[n + N] * pMl * math.cos((pw0l * n) + pPHI)
                C2 = Ws[n] * cMl * math.cos((cw0l * (n - N)) + cPHI)
                aout[n] += C1 + C2
        else:
            rphase = [rng.phase() for _ in range(uvquality)]
            rphase2 = [rng.phase() for _ in range(uvquality)]
            for n in range(N):
                C3 = 0.0
                for i in range(uvquality):
                    C3 += math.cos((pw0 * n * (l + (i * uvstep) - uvoffset)) + rphase[i])
                    if pw0l > uvthreshold:
                        C3 += (pw0l - uvthreshold) * uvrand * rng.randf()
                C3 = C3 * uvsine * Ws[n + N] * pMl * qfactor
                C4 = 0.0
                for i in range(uvquality):
                    C4 += math.cos((cw0 * n * (l + (i * uvstep) - uvoffset)) + rphase2[i])
                    if cw0l > uvthreshold:
                        C4 += (cw0l - uvthreshold) * uvrand * rng.randf()
                C4 = C4 * uvsine * Ws[n] * cMl * qfactor
                aout[n] += C3 + C4
    return aout


def _float_to_short(fb):
    out = np.empty(160, dtype=np.int16)
    for i in range(160):
        a = 7.0 * fb[i]
        if a > 32760: a = 32760
        elif a < -32760: a = -32760
        out[i] = int(a)
    return out


# ----------------------------------------------------------------------------
# Driver: imbe_fr frames -> PCM
# ----------------------------------------------------------------------------
class ImbeDecoder:
    """Stateful IMBE decoder: feed imbe_fr frames in order, get 160 int16/frame.
    One decoder per transmission (carries cur/prev/enhanced state)."""
    def __init__(self, uvquality=3, seed=1):
        self.cur, self.prev, self.penh = init_parms()
        self.uvquality = uvquality
        self.rng = _GlibcRand(seed)

    def decode_frame(self, imbe_fr):
        fr = [list(row) for row in imbe_fr]
        errs_c0 = _ecc_c0(fr)
        _demodulate(fr)
        imbe_d, errs_data = _ecc_data(fr)
        errs2 = errs_c0 + errs_data            # C: errs2 = C0 errs + data errs
        bad = decode_imbe4400_parms(imbe_d, self.cur, self.prev)
        if bad == 1 or errs2 > 5:
            _use_last(self.cur, self.prev)
            self.cur.repeat += 1
        else:
            self.cur.repeat = 0
        if self.cur.repeat <= 3:
            _move(self.cur, self.prev)
            spectral_amp_enhance(self.cur)
            fb = synthesize_speech(self.cur, self.penh, self.uvquality, self.rng)
            _move(self.cur, self.penh)
        else:
            fb = [0.0] * 160
            self.cur, self.prev, self.penh = init_parms()
        return _float_to_short(fb)


def decode_frames(frames, uvquality=3, seed=1):
    """Decode a list of imbe_fr frames -> int16 PCM (np.ndarray, 8 kHz)."""
    dec = ImbeDecoder(uvquality, seed)
    out = [dec.decode_frame(f) for f in frames]
    return np.concatenate(out) if out else np.zeros(0, np.int16)
