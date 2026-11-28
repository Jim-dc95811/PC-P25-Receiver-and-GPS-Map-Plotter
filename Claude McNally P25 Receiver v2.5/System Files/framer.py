"""OP25-faithful P25 Phase-1 framer + PDU assembly (ported from
p25_framer.cc + p25p1_fdma.cc::process_blocks). Deterministic streaming sync
(check_frame_sync: popcount(x ^ MAGIC) <= 6 over 48 bits) — no correlation
argmax. For a data PDU (DUID 0xC) the body is collected to the next sync, then
status symbols are stripped (every 36th dibit) and 1/2-rate blocks are read at
bit 48+64+k*196, exactly as OP25 does.

Usage: frames = decode_frames(dibits)  # dibits = list of 0..3 symbol values
"""
import bch_nid
from pdu_blocks import block_deinterleave_12, block_deinterleave_34, viterbi_deinterleave_12, crc16, crc32, count_bits

MAGIC = 0x5575F5FF77FF
MASK  = (1 << 48) - 1
# OP25 max_frame_lengths[duid] in BITS (0 => unknown/undef)
MAXLEN = {0:792, 3:144, 5:1728, 7:720, 0xa:1728, 0xc:31000, 0xf:432}

def _sync_positions(dibits, errth=6):
    """Return indices p where dibits[p] is the LAST (24th) symbol of a frame sync."""
    acc = 0; out = []
    for i, d in enumerate(dibits):
        acc = ((acc << 2) | (d & 3)) & MASK
        if i >= 23 and count_bits((acc ^ MAGIC) & MASK) <= errth:
            out.append(i)
    return out

def _nid_from_body(fb):
    """fb = frame_body bits (sync+NID+...). NID = bits[48:114] skipping 70,71 (status)."""
    if len(fb) < 114: return None
    accum = 0
    for i in range(48, 114):
        if i in (70, 71): continue
        accum = (accum << 1) | fb[i]
    nac, duid, ec = bch_nid.nid_codeword(accum)
    return nac, duid, ec, (accum & 1)    # parity = original LSB (OP25)

def _valid(nac, duid, ec, parity):
    if ec < 0 or ec > 4: return False
    if duid in (0,3,7,12,15) and not parity: return True
    if duid in (5,10) and parity: return True
    return False

def decode_frames(dibits, sync_errth=6):
    syncs = _sync_positions(dibits, sync_errth)
    frames = []
    for si, p in enumerate(syncs):
        start = p - 23                      # first sync symbol
        if start < 0: continue
        # body runs to the next sync's start (PDU length not known a priori), else end
        nxt = next((q-23 for q in syncs if q-23 > start), len(dibits))
        syms = dibits[start:nxt]
        fb = []
        for d in syms:
            fb.append((d >> 1) & 1); fb.append(d & 1)
        r = _nid_from_body(fb)
        if r is None: continue
        nac, duid, ec, parity = r
        if not _valid(nac, duid, ec, parity): continue
        frames.append(dict(start=start, nsyms=len(syms), nac=nac, duid=duid, ec=ec, fb=fb))
    return frames

def pdu_blocks(fb):
    """OP25 process_blocks: strip every 36th dibit, read 1/2-rate blocks at 112+k*196."""
    ndib = len(fb) // 2
    bv = []
    for d in range(ndib):
        if (d + 1) % 36 == 0: continue
        bv.append(fb[2*d]); bv.append(fb[2*d+1])
    nblk = (len(bv) - 112) // 196 if len(bv) > (48+64) else 1
    nblk = max(1, nblk)
    blocks = []
    for k in range(nblk):
        blocks.append(viterbi_deinterleave_12(bv, 48 + 64 + k*196))
    return bv, blocks
