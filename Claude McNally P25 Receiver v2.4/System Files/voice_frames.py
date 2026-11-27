"""
voice_frames.py  -  sealed P25 voice + speaker-ID kernel for The Traveler PC.

From a keyed segment of detector audio this pulls, out of the SAME LDU frames
the decoder already locks:
  * the 9 IMBE voice frames per LDU  (imbe_fr[8][23], for the vocoder), and
  * the CURRENT SPEAKER -- the Link Control source unit ID, the join key that
    lights the talking unit on the map by the same ID the GPS plots it with.

Proven engine (P25-GPS-Decode decode/voice_ldu.py + decode/lc_source.py):
  - FIXED-timing demod (no MMSE tracking loop): the NID/LC region sits right
    after each sync and the MMSE loop wobbles there when fs = 10x the symbol
    rate.  Fixed timing keeps it crisp.
  - DSD-style sequential dibit Reader (status symbol every 36 dibits).
  - Annex-H deinterleave (TIA-102.BABA iW/iX/iY/iZ) -> imbe_fr.
  - LDU1 Link Control: the three 20-dibit gaps before IMBE 3/4/5 are the 12
    DATA hex words 11..0 (DSD p25p1_ldu1.c); group-voice LC (LCO 0) -> talkgroup
    = lcinfo bits 16..32 and source = bits 32..56 (p25_lcw.c). The NAC rides in
    every frame's NID (framer), system-constant.

Read-only; reuses the bundle's framer + frontend. No vocoder here -- this
produces imbe_fr frames + the speaker id; the shell vocodes and displays.
"""
import os, sys
import numpy as np
from scipy.signal import lfilter, resample_poly
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from frontend import c4fm_rx_taps
import framer

LVL2DIBIT = np.array([3, 2, 0, 1])
LV = np.array([-3., -1., 1., 3.])

# --- P25 Phase-1 IMBE interleave schedule (DSD p25p1_const.h) ---
iW = [0,2,4,1,3,5, 0,2,4,1,3,6, 0,2,4,1,3,6, 0,2,4,1,3,6,
      0,2,4,1,3,6, 0,2,4,1,3,6, 0,2,5,1,3,6, 0,2,5,1,3,6,
      0,2,5,1,3,7, 0,2,5,1,3,7, 0,2,5,1,4,7, 0,3,5,2,4,7]
iX = [22,20,10,20,18,0, 20,18,8,18,16,13, 18,16,6,16,14,11, 16,14,4,14,12,9,
      14,12,2,12,10,7, 12,10,0,10,8,5, 10,8,13,8,6,3, 8,6,11,6,4,1,
      6,4,9,4,2,6, 4,2,7,2,0,4, 2,0,5,0,13,2, 0,21,3,21,11,0]
iY = [1,3,5,0,2,4, 1,3,6,0,2,4, 1,3,6,0,2,4, 1,3,6,0,2,4,
      1,3,6,0,2,4, 1,3,6,0,2,5, 1,3,6,0,2,5, 1,3,6,0,2,5,
      1,3,6,0,2,5, 1,3,7,0,2,5, 1,4,7,0,3,5, 2,4,7,1,3,5]
iZ = [21,19,1,21,19,9, 19,17,14,19,17,7, 17,15,12,17,15,5, 15,13,10,15,13,3,
      13,11,8,13,11,1, 11,9,6,11,9,14, 9,7,4,9,7,12, 7,5,2,7,5,10,
      5,3,0,5,3,8, 3,1,5,3,1,6, 1,14,3,1,22,4, 22,12,1,22,20,2]

_GAP_HEX = [(11, 10, 9, 8), (7, 6, 5, 4), (3, 2, 1, 0)]   # LC DATA words per gap
_VOICE_GAPS = [0, 0, 20, 20, 20, 20, 20, 20, 16]          # data dibits before IMBE k


def fixed_demod(x, fr0):
    """Fixed-timing demod (no MMSE loop) -> symbol stream at the NID-clean phase."""
    a = x - x.mean()
    rms = np.maximum(lfilter([0.01], [1, -0.99], a * a), 1e-12); a = a / np.sqrt(rms)
    taps = c4fm_rx_taps(fr0); a = np.convolve(a, taps, 'same')
    U = 4; a = resample_poly(a, U, 1); sU = (fr0 // 4800) * U
    best = None
    for ph in range(sU):
        sm = a[ph::sU]; sm = sm / (np.mean(np.abs(sm)) / 2.0)
        ok = (np.min(np.abs(sm[:, None] - LV[None, :]), 1) < 0.5).mean()
        if best is None or ok > best[0]: best = (ok, ph)
    sym = a[best[1]::sU]; sym = sym / (np.mean(np.abs(sym)) / 2.0)
    return sym


class _Reader:
    """DSD read_dibit: status symbol every 36 dibits (skipped); data returned."""
    def __init__(self, dibits, pos, status_count=21):
        self.d = dibits; self.pos = pos; self.sc = status_count
    def read(self):
        if self.sc == 35:
            self.pos += 1; self.sc = 1
        else:
            self.sc += 1
        v = int(self.d[self.pos]); self.pos += 1
        return v


def _imbe_frame(rd):
    fr = [[0] * 23 for _ in range(8)]
    for j in range(72):
        dbt = rd.read()
        fr[iW[j]][iX[j]] = (dbt >> 1) & 1
        fr[iY[j]][iZ[j]] = dbt & 1
    return fr


def extract_voice(dibits, start):
    """The 9 IMBE voice frames (imbe_fr[8][23]) of one LDU at frame-dibit start."""
    rd = _Reader(dibits, start + 57, 21)
    frames = []
    for k in range(9):
        for _ in range(_VOICE_GAPS[k]):
            rd.read()
        frames.append(_imbe_frame(rd))
    return frames


def _read_hexword(rd):
    bits = []
    for _ in range(3):
        d = rd.read(); bits += [(d >> 1) & 1, d & 1]
    rd.read(); rd.read()                       # 2 parity dibits
    return bits


def lcw_group(dibits, start):
    """Group-voice (LCO 0) (talkgroup_id, source_unit_id) from one LDU1.

    The 56-bit LC info of a Group Voice Channel User word (TIA-102) lays out as
    service-options[8] reserved[8] group-address[16] source-address[24], so the
    talkgroup is bits 16..32 and the source is bits 32..56 (the proven speaker
    field). Returns (None, None) if the word is not group-voice."""
    rd = _Reader(dibits, start + 57, 21)
    hexd = [None] * 12
    gi = 0
    for k in range(5):
        if k >= 2:
            for idx in _GAP_HEX[gi]:
                hexd[idx] = _read_hexword(rd)
            gi += 1
        for _ in range(72):
            rd.read()
    lcformat = hexd[11] + hexd[10][:2]
    if "".join(map(str, lcformat)) != "00000000":
        return None, None
    lcinfo = hexd[9][4:6]
    for i in (8, 7, 6, 5, 4, 3, 2, 1, 0):
        lcinfo += hexd[i]
    tgid = int("".join(map(str, lcinfo[16:32])), 2)   # group address (16-bit, decimal)
    src  = int("".join(map(str, lcinfo[32:56])), 2)   # source unit id (24-bit)
    return tgid, src


def decode_voice_segment(seg, fr0):
    """From a keyed segment return (speaker_id|None, tgid|None, nac|None,
    [imbe_fr,...], n_ldu).

    speaker_id and tgid = per-segment MAJORITY of the group-voice LC source and
    group address over the LDU1s (neither changes mid-transmission, so the vote
    rides over the odd uncorrected LC bit error). nac = majority of the decoded
    frame NIDs (system-constant). imbe frames are every LDU's 9 voice frames.
    """
    sym = fixed_demod(np.asarray(seg, dtype=float), fr0)
    best = None
    for sg in (1, -1):
        db = LVL2DIBIT[np.digitize(sg * sym, [-2., 0., 2.])]
        fr = framer.decode_frames(db, sync_errth=8)
        vc = sum(1 for q in fr if q['duid'] in (5, 10))
        if best is None or vc > best[0]: best = (vc, db, fr)
    vc, db, fr = best
    if vc == 0:
        return None, None, None, [], 0
    voice, srcs, tgids, n = [], [], [], 0
    for q in fr:
        if q['duid'] in (5, 10) and q['start'] + 875 < len(db):
            voice.extend(extract_voice(db, q['start'])); n += 1
            if q['duid'] == 5:
                tg, s = lcw_group(db, q['start'])
                if s is not None:  srcs.append(s)
                if tg is not None: tgids.append(tg)
    spk  = Counter(srcs).most_common(1)[0][0] if srcs else None
    tgid = Counter(tgids).most_common(1)[0][0] if tgids else None
    nac  = Counter(q['nac'] for q in fr).most_common(1)[0][0] if fr else None
    return spk, tgid, nac, voice, n
