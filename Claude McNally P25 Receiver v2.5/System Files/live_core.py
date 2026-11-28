"""
live_core.py  -  streaming P25 GPS burst gate + decode, device-agnostic.

Feed it audio BLOCKS (any size) of mono float samples at a fixed rate with
LiveDecoder.feed(block); it watches a streaming band-ratio (C4FM energy
<2.9 kHz vs 3-10 kHz broadband), and when a transmission keys up it captures
that burst and runs the proven per-burst decode (decode_burst, unchanged),
calling on_report(gga, pp25, t_wall) for each GPS report it recovers.

Nothing here knows about sound cards or WAV files -- the same engine is
driven by a live audio stream in p25_live_decoder.py and by a replayed
recording in the self-test, so the live path is validated against the known
answer key before any hardware is involved.

Measured on Jim's live-radio capture: inter-burst open-squelch noise sits at
band-ratio ~1-2; a keyed P25 GPS burst spikes to ~1600-3500. The gate
thresholds at max(RATIO_ABS_MIN, RATIO_K * running_noise_median) -- a floor
three orders of magnitude below the burst, so detection is not marginal.
"""
import time, numpy as np
from fsk4_demod import fsk4_demod
from framer import decode_frames, pdu_blocks
from frontend import c4fm_rx_taps
from pdu_blocks import count_bits

MAGIC = 0x5575F5FF77FF; MASK = (1 << 48) - 1
LVL2DIBIT = [3, 2, 0, 1]

# --- gate tuning (hops are WIN/HOP at the stream rate) ---
WIN = 1024          # analysis window (samples)
HOP = 512           # hop between windows
RATIO_K = 8.0       # trigger at K * running noise-floor median ...
RATIO_ABS_MIN = 8.0 # ... but never below this absolute ratio
RELEASE_FRAC = 0.25 # burst ends when ratio falls below RELEASE_FRAC * trigger
PREROLL_S = 0.35    # capture this much before the trigger hop
CAP_S = 1.40        # total captured burst length handed to the decoder
REFRACTORY_S = 1.0  # ignore re-triggers within this of a burst onset
NOISE_EWMA = 0.02   # running noise-floor median tracker (idle only)

from scipy.signal import lfilter, spectrogram

def _rmsagc(x, a=0.01, k=1.0):
    r = np.maximum(lfilter([a], [1.0, -(1.0 - a)], x * x), 1e-12); return x * (k / np.sqrt(r))

def detect_in_segment(seg, fr0):
    """Precise burst onset(s) inside a captured window -- the file tool's
    spectrogram band-ratio detector, run on the short buffer the gate handed us
    (exactly one burst), so onset-finding matches the proven path."""
    if len(seg) < WIN + HOP: return []
    f, t, S = spectrogram(seg, fr0, nperseg=WIN, noverlap=HOP)
    low = S[(f >= 100) & (f <= 2900)].sum(0); high = S[(f > 3000) & (f <= 10000)].sum(0) + 1e-12
    r = np.convolve(low / high, np.ones(9) / 9, 'same'); thr = 0.5 * (np.median(r) + r.max())
    starts = []; prev = False
    for i, a in enumerate(r > thr):
        if a and not prev and (not starts or t[i] - starts[-1] > 0.5): starts.append(float(t[i]))
        prev = a
    return starts

def _asc(bs): return "".join(chr(c) if 32 <= c < 127 else "." for c in bs)

def _best_sync(db, region=700):
    acc = 0; best = 99; bi = 0
    for i, d in enumerate(db[:region]):
        acc = ((acc << 2) | (d & 3)) & MASK
        if i >= 23:
            e = count_bits((acc ^ MAGIC) & MASK)
            if e < best: best = e; bi = i
    return bi, best

def _payload_at(db, start):
    fb = []
    for d in db[start:]:
        fb.append((d >> 1) & 1); fb.append(d & 1)
    bv, blocks = pdu_blocks(fb); pay = bytearray()
    for b in blocks:
        if b is None: break
        pay += b
    return _asc(pay)

def _good(p): return ("GGA" in p) and ("$PP25,907" in p)

def decode_at(seg, fr0, tstart, taps, span=0.55):
    """The proven robust acquisition (decode_capture.decode_burst), run on a
    captured window at onset tstart (seconds into seg)."""
    for lead in (0.06, 0.10, 0.03, 0.15, 0.00):
        a = seg[int((tstart - lead) * fr0):int((tstart + span) * fr0)].copy()
        if len(a) < int(0.2 * fr0): continue
        a = a - np.mean(a); a = _rmsagc(a); a = np.convolve(a, taps, 'same')
        a = a / (np.std(a) + 1e-9) * np.sqrt(5.0)
        sym = fsk4_demod(a, fr0, 4800)
        for sgn in (1, -1):
            db = [LVL2DIBIT[b] for b in np.digitize(sgn * sym, [-2., 0., 2.])]
            frames = decode_frames(db, sync_errth=6)        # strict, NID-validated
            if frames:
                p = _payload_at(db, frames[0]['start'])
                if _good(p): return p
            bi, h = _best_sync(db)                           # force-lock, payload-validated
            if bi >= 23:
                p = _payload_at(db, bi - 23)
                if _good(p): return p
    return None

import re
_GGA = re.compile(r"\$..GGA,[^*]*\*[0-9A-Fa-f]{2}")
_PP25 = re.compile(r"\$PP25,[0-9]+,?\*?[0-9A-Fa-f]{0,2}")
def split_nmea(pay):
    g = _GGA.search(pay); p = _PP25.search(pay)
    return (g.group(0) if g else None), (p.group(0) if p else None)


class LiveDecoder:
    """Streaming burst gate + decoder. feed() blocks of mono float samples;
    on_report(gga, pp25, t_wall) fires per recovered GPS report."""
    def __init__(self, fr0, on_report, on_status=None):
        self.fr0 = int(fr0)
        self.on_report = on_report
        self.on_status = on_status or (lambda *a, **k: None)
        self.taps = c4fm_rx_taps(self.fr0)
        self.f = np.fft.rfftfreq(WIN, 1.0 / self.fr0)
        self.lo = (self.f >= 100) & (self.f <= 2900)
        self.hi = (self.f > 3000) & (self.f <= 10000)
        self.wnd = np.hanning(WIN)
        # contiguous rolling buffer of the most recent samples; buf[0] is at
        # absolute index buf0_abs. Keep enough for pre-roll + capture + slack.
        self.keep = int((PREROLL_S + CAP_S + 1.0) * self.fr0) + WIN
        self.buf = np.zeros(0, dtype=np.float64)
        self.buf0_abs = 0          # absolute index of buf[0]
        self.filled = 0            # total samples ever fed (monotonic)
        self.hoppos = 0            # next absolute index to analyze (hop grid)
        self.noise = 1.0           # running noise-floor median estimate
        self.state = 'IDLE'
        self.trig = RATIO_ABS_MIN
        self.onset_abs = 0
        self.last_onset_abs = -10 ** 12
        self.reports = 0; self.bursts = 0

    def _ratio(self, win):
        P = np.abs(np.fft.rfft(win * self.wnd)) ** 2
        return P[self.lo].sum() / (P[self.hi].sum() + 1e-12)

    def feed(self, block):
        block = np.asarray(block, dtype=np.float64).ravel()
        self.buf = np.concatenate([self.buf, block]); self.filled += len(block)
        # analyze every HOP samples where a full WIN is available
        while self.hoppos + WIN <= self.filled:
            a = self.hoppos - self.buf0_abs
            win = self.buf[a:a + WIN]
            r = self._ratio(win)
            self._gate(r, self.hoppos + WIN)      # pos = end-of-window abs index
            self.hoppos += HOP
        # trim the buffer front, but never past what a pending capture needs
        need_from = self.filled - self.keep
        if self.state == 'BURST':
            need_from = min(need_from, self.onset_abs - int(PREROLL_S * self.fr0))
        if need_from > self.buf0_abs:
            cut = need_from - self.buf0_abs
            self.buf = self.buf[cut:]; self.buf0_abs += cut

    def _seg_from_abs(self, start_abs, length):
        """Pull `length` samples starting at absolute index start_abs. Indices
        into the contiguous buffer are exact (no wraparound)."""
        a = start_abs - self.buf0_abs
        if a < 0: a = 0
        return self.buf[a:a + length].copy()

    def _gate(self, r, pos_abs):
        if self.state == 'IDLE':
            self.trig = max(RATIO_ABS_MIN, RATIO_K * self.noise)
            if r > self.trig and (pos_abs - self.last_onset_abs) > REFRACTORY_S * self.fr0:
                # onset ~= start of the window that first crossed, minus the window
                self.state = 'BURST'; self.onset_abs = pos_abs - WIN
                self.last_onset_abs = self.onset_abs
            else:
                # track the noise floor only while idle
                self.noise = (1 - NOISE_EWMA) * self.noise + NOISE_EWMA * min(r, 5.0)
        else:  # BURST: capture a FIXED-length window once enough samples past
               # the onset have arrived (not when the ratio falls -- the decode
               # needs the full span after the onset).
            if pos_abs - self.onset_abs >= int((CAP_S - PREROLL_S) * self.fr0):
                start_abs = self.onset_abs - int(PREROLL_S * self.fr0)
                seg = self._seg_from_abs(start_abs, int(CAP_S * self.fr0))
                self.state = 'IDLE'
                self.bursts += 1
                self._decode(seg)

    def _decode(self, seg):
        if len(seg) < int(0.3 * self.fr0): return
        onsets = detect_in_segment(seg, self.fr0)      # precise onset via proven detector
        if not onsets: onsets = [PREROLL_S]            # fallback: trust the gate's pre-roll
        pay = None
        for ts in onsets:
            pay = decode_at(seg, self.fr0, ts, self.taps)
            if pay: break
        t = time.time()
        if not pay:
            self.on_status('burst %d: no lock (weak)' % self.bursts); return
        gga, pp = split_nmea(pay)
        if gga:
            self.reports += 1
            self.on_report(gga, pp, t)
        else:
            self.on_status('burst %d: partial  %s' % (self.bursts, pay[:50]))

    def flush(self):
        """Call at end of a finite stream (self-test) to close a burst in progress."""
        if self.state == 'BURST':
            start_abs = self.onset_abs - int(PREROLL_S * self.fr0)
            seg = self._seg_from_abs(start_abs, int(CAP_S * self.fr0))
            self.state = 'IDLE'; self.bursts += 1; self._decode(seg)
