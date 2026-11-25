"""P25 PDU data-block FEC — ported VERBATIM from OP25
(sndcp-fork op25/gr-op25_repeater/lib/p25p1_fdma.cc). Do not re-derive these;
they are the regulated P25 primitives. Input is a bit_vector `bv` (list of 0/1,
two bits per received dibit, status symbols already stripped). Each block is
196 bits (98 dibits) starting at a bit offset.

  block_deinterleave_12(bv, start) -> 12 bytes  (rate-1/2 trellis; unconfirmed
                                      data blocks AND the PDU header block)
  block_deinterleave_34(bv, start) -> 18 bytes  (rate-3/4 Viterbi; confirmed
                                      data blocks: 2-byte serial/CRC + 16 data)
  crc16(buf,12)==0  validates a header/unconfirmed block
  crc32(bits,nbits) packet CRC (P25 / p25craft)
"""

# ---- rate-1/2 deinterleave + trellis (p25p1_fdma.cc block_deinterleave) ----
_DEINT = [
 0,1,2,3,52,53,54,55,100,101,102,103,148,149,150,151,
 4,5,6,7,56,57,58,59,104,105,106,107,152,153,154,155,
 8,9,10,11,60,61,62,63,108,109,110,111,156,157,158,159,
 12,13,14,15,64,65,66,67,112,113,114,115,160,161,162,163,
 16,17,18,19,68,69,70,71,116,117,118,119,164,165,166,167,
 20,21,22,23,72,73,74,75,120,121,122,123,168,169,170,171,
 24,25,26,27,76,77,78,79,124,125,126,127,172,173,174,175,
 28,29,30,31,80,81,82,83,128,129,130,131,176,177,178,179,
 32,33,34,35,84,85,86,87,132,133,134,135,180,181,182,183,
 36,37,38,39,88,89,90,91,136,137,138,139,184,185,186,187,
 40,41,42,43,92,93,94,95,140,141,142,143,188,189,190,191,
 44,45,46,47,96,97,98,99,144,145,146,147,192,193,194,195,
 48,49,50,51]
_NEXT = [[0x2,0xC,0x1,0xF],[0xE,0x0,0xD,0x3],[0x9,0x7,0xA,0x4],[0x5,0xB,0x6,0x8]]

def count_bits(n):
    i = 0
    while n:
        n &= n - 1; i += 1
    return i

def find_min(lst):
    mn = min(lst)
    return lst.index(mn) if lst.count(mn) == 1 else -1

def block_deinterleave_12(bv, start):
    if start + 195 >= len(bv):
        return None
    buf = bytearray(12); state = 0
    for b in range(0, 98*2, 4):
        cw = (bv[start+_DEINT[b]] << 3) | (bv[start+_DEINT[b+1]] << 2) | \
             (bv[start+_DEINT[b+2]] << 1) | bv[start+_DEINT[b+3]]
        hd = [count_bits(cw ^ _NEXT[state][j]) for j in range(4)]
        state = find_min(hd)
        if state == -1:
            return None
        d = b >> 2
        if d < 48:
            buf[d >> 2] |= state << (6 - ((d % 4) * 2))
    return bytes(buf)

# ---- rate-3/4 confirmed-data Viterbi (p25p1_fdma.cc block_deinterleave_34) ----
_PAIRS = [[0,2],[2,2],[1,3],[3,3],[3,2],[1,2],[2,3],[0,3],
          [3,1],[1,1],[2,0],[0,0],[0,1],[2,1],[1,0],[3,0]]
_STMAP = [[0,8,4,12,2,10,6,14],[4,12,2,10,6,14,0,8],[1,9,5,13,3,11,7,15],
          [5,13,3,11,7,15,1,9],[3,11,7,15,1,9,5,13],[7,15,1,9,5,13,3,11],
          [2,10,6,14,0,8,4,12],[6,14,0,8,4,12,2,10]]

def block_deinterleave_34(bv, start):
    if start + 195 >= len(bv):
        return None
    coded = [bv[start+_DEINT[i]] for i in range(196)]  # same 196-bit interleave
    N = 49; INF = 100000
    cost = [[INF]*8 for _ in range(N+1)]; prev = [[-1]*8 for _ in range(N+1)]
    cost[0][0] = 0
    for t in range(N):
        obs = (coded[4*t] << 3) | (coded[4*t+1] << 2) | (coded[4*t+2] << 1) | coded[4*t+3]
        for s in range(8):
            if cost[t][s] >= INF:
                continue
            for nx in range(8):
                p = _STMAP[s][nx]; exp = (_PAIRS[p][0] << 2) | _PAIRS[p][1]
                nc = cost[t][s] + count_bits(obs ^ exp)
                if nc < cost[t+1][nx]:
                    cost[t+1][nx] = nc; prev[t+1][nx] = s
    end = min(range(8), key=lambda s: cost[N][s])
    path = [0]*N; s = end
    for t in range(N, 0, -1):
        path[t-1] = s; s = prev[t][s]
        if s < 0:
            return None
    buf = bytearray(18); acc = 0; nb = 0; o = 0
    for i in range(N):
        if o >= 18:
            break
        acc = (acc << 3) | (path[i] & 7); nb += 3
        while nb >= 8 and o < 18:
            nb -= 8; buf[o] = (acc >> nb) & 0xff; o += 1; acc &= (1 << nb) - 1
    return bytes(buf)

# ---- CRCs (p25p1_fdma.cc) ----
def crc16(buf, ln=12):
    poly = (1<<12)+(1<<5)+(1<<0); crc = 0
    for i in range(ln):
        bits = buf[i]
        for j in range(8):
            bit = (bits >> (7-j)) & 1
            crc = ((crc << 1) | bit) & 0x1ffff
            if crc & 0x10000:
                crc = (crc & 0xffff) ^ poly
    return (crc ^ 0xffff) & 0xffff

def crc32(bits):  # bits = list of 0/1; P25 packet CRC-32
    g = 0x04c11db7; crc = 0
    for b in bits:
        crc <<= 1
        if ((crc >> 32) ^ b) & 1:
            crc ^= g
    return (crc & 0xffffffff) ^ 0xffffffff

# ---- proper VITERBI decode of the 1/2-rate P25 data block (optimal; replaces the
#      greedy per-symbol block_deinterleave_12 when symbols carry residual errors).
#      Same code/tables; 49 trellis steps, state transitions to the input dibit,
#      output codeword = _NEXT[prev_state][input]. Recovers blocks the greedy
#      decoder hard-fails on. ----
def viterbi_deinterleave_12(bv, start):
    if start + 195 >= len(bv):
        return None
    INF = 1 << 30; N = 49
    cost = [[INF]*4 for _ in range(N+1)]
    prev = [[-1]*4 for _ in range(N+1)]
    inp  = [[-1]*4 for _ in range(N+1)]
    cost[0][0] = 0
    for t in range(N):
        b = t*4
        obs = (bv[start+_DEINT[b]] << 3) | (bv[start+_DEINT[b+1]] << 2) | \
              (bv[start+_DEINT[b+2]] << 1) | bv[start+_DEINT[b+3]]
        for ps in range(4):
            if cost[t][ps] >= INF:
                continue
            base = cost[t][ps]
            for d in range(4):
                c = base + count_bits(obs ^ _NEXT[ps][d])
                if c < cost[t+1][d]:
                    cost[t+1][d] = c; prev[t+1][d] = ps; inp[t+1][d] = d
    end = min(range(4), key=lambda s: cost[N][s])
    dibits = [0]*N; s = end
    for t in range(N, 0, -1):
        dibits[t-1] = inp[t][s]; s = prev[t][s]
        if s < 0:
            return None
    buf = bytearray(12)
    for d in range(48):
        buf[d >> 2] |= dibits[d] << (6 - ((d % 4) * 2))
    return bytes(buf)
