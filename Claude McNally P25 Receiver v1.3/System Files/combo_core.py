"""
combo_core.py  -  THE COMBO PLATTER engine: one keyed stream, two layers.

Feed it audio blocks (ComboDecoder.feed); it watches the same band-ratio gate as
the GPS decoder, but captures a WHOLE keyed transmission (onset -> de-key) and
routes it:

  * a short GPS data burst  -> on_report(gga, pp25, t)          [position layer]
  * a voice transmission    -> on_speaker(unit_id, t)           [CURRENT SPEAKER]
                            -> on_voice(imbe_frames, spk, t)    [the heard voice]

The two layers are fused by the unit ID: the voice Link Control source is the
same ID the GPS plots, so the talking unit lights up on the map where it is.

Sealed engines bolted in, clean plumbing:
  - GPS decode  = live_core.decode_at (the proven robust acquisition), unchanged.
  - Voice + speaker = voice_frames.decode_voice_segment (the proven kernel).
Nothing here knows about sound cards, audio output, or the GUI -- the same
engine runs live and in a replay self-test, validated before any hardware.
"""
import time, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from frontend import c4fm_rx_taps
from live_core import decode_at, detect_in_segment, split_nmea
from voice_frames import decode_voice_segment

# gate tuning (aligned with live_core; a transmission is captured onset->de-key)
WIN = 1024
HOP = 512
RATIO_K = 8.0
RATIO_ABS_MIN = 8.0
RELEASE_FRAC = 0.25        # de-keyed when ratio falls below this * trigger ...
DEKEY_HOPS = 10            # ... for this many consecutive hops (~0.1 s)
PREROLL_S = 0.35
MAXTX_S = 40.0            # safety cap on one captured transmission
MINTX_S = 0.3
NOISE_EWMA = 0.02


class ComboDecoder:
    def __init__(self, fr0, on_report=None, on_speaker=None, on_voice=None, on_status=None):
        self.fr0 = int(fr0)
        self.on_report = on_report or (lambda *a: None)
        self.on_speaker = on_speaker or (lambda *a: None)
        self.on_voice = on_voice or (lambda *a: None)
        self.on_status = on_status or (lambda *a: None)
        self.taps = c4fm_rx_taps(self.fr0)
        self.wnd = np.hanning(WIN)
        self.f = np.fft.rfftfreq(WIN, 1.0 / self.fr0)
        self.lo = (self.f >= 100) & (self.f <= 2900)
        self.hi = (self.f > 3000) & (self.f <= 10000)
        self.buf = np.zeros(0, dtype=np.float64)
        self.buf0_abs = 0
        self.filled = 0
        self.hoppos = 0
        self.noise = 1.0
        self.state = 'IDLE'
        self.trig = RATIO_ABS_MIN
        self.onset_abs = 0
        self.dekey = 0
        self.last_spk = None
        self.reports = 0
        self.tx = 0

    def _ratio(self, win):
        P = np.abs(np.fft.rfft(win * self.wnd)) ** 2
        return P[self.lo].sum() / (P[self.hi].sum() + 1e-12)

    def feed(self, block):
        block = np.asarray(block, dtype=np.float64).ravel()
        self.buf = np.concatenate([self.buf, block]); self.filled += len(block)
        while self.hoppos + WIN <= self.filled:
            a = self.hoppos - self.buf0_abs
            self._gate(self._ratio(self.buf[a:a + WIN]), self.hoppos + WIN)
            self.hoppos += HOP
        # keep the buffer from the current onset (or recent tail) forward
        if self.state == 'KEYED':
            keep_from = self.onset_abs - int(PREROLL_S * self.fr0)
        else:
            keep_from = self.filled - int((PREROLL_S + 1.0) * self.fr0) - WIN
        if keep_from > self.buf0_abs:
            cut = keep_from - self.buf0_abs
            self.buf = self.buf[cut:]; self.buf0_abs += cut

    def _seg(self, start_abs, end_abs):
        a = max(0, start_abs - self.buf0_abs)
        b = end_abs - self.buf0_abs
        return self.buf[a:b].copy()

    def _gate(self, r, pos_abs):
        if self.state == 'IDLE':
            self.trig = max(RATIO_ABS_MIN, RATIO_K * self.noise)
            if r > self.trig:
                self.state = 'KEYED'; self.onset_abs = pos_abs - WIN; self.dekey = 0
            else:
                self.noise = (1 - NOISE_EWMA) * self.noise + NOISE_EWMA * min(r, 5.0)
        else:  # KEYED: accumulate until de-keyed (release) or the safety cap
            keyed_len = pos_abs - self.onset_abs
            rel = RELEASE_FRAC * self.trig
            self.dekey = self.dekey + 1 if r < rel else 0
            if self.dekey >= DEKEY_HOPS or keyed_len >= int(MAXTX_S * self.fr0):
                end_abs = pos_abs
                seg = self._seg(self.onset_abs - int(PREROLL_S * self.fr0), end_abs)
                self.state = 'IDLE'; self.noise = max(self.noise, 1.0)
                if len(seg) >= int(MINTX_S * self.fr0):
                    self.tx += 1
                    self._process(seg)

    def _process(self, seg):
        """One captured transmission -> GPS report, or voice + current speaker.
        Fully isolated: a decode error on one malformed transmission is reported
        and skipped, never raised -- the gate is already back to IDLE by now, so
        the decoder keeps running on the next key-up untouched."""
        try:
            self._process_inner(seg)
        except Exception as e:
            self.on_status('tx %d: decode error (%s) - skipped' % (self.tx, e))

    def _process_inner(self, seg):
        t = time.time()
        # 1) GPS data burst? (the proven robust acquisition on the burst onset)
        onsets = detect_in_segment(seg, self.fr0) or [PREROLL_S]
        for ts in onsets[:3]:
            pay = decode_at(seg, self.fr0, ts, self.taps)
            if pay:
                gga, pp = split_nmea(pay)
                if gga:
                    self.reports += 1
                    self.on_report(gga, pp, t)
                    return
        # 2) else a voice transmission -> speaker + voice frames
        spk, voice, n = decode_voice_segment(seg, self.fr0)
        if n == 0:
            self.on_status('tx %d: no lock (weak)' % self.tx); return
        if spk is not None:
            self.last_spk = spk
            self.on_speaker(spk, t)
        self.on_voice(voice, spk, t)
        self.on_status('tx %d: voice %d LDU, speaker %s' % (self.tx, n, spk))

    def flush(self):
        if self.state == 'KEYED':
            seg = self._seg(self.onset_abs - int(PREROLL_S * self.fr0), self.filled)
            self.state = 'IDLE'
            if len(seg) >= int(MINTX_S * self.fr0):
                self.tx += 1; self._process(seg)


# --- replay self-test: prove GPS + CURRENT SPEAKER routing on a recording ----
def _replay(wavpath):
    import wave
    w = wave.open(wavpath, 'rb'); fr0 = w.getframerate(); nch = w.getnchannels()
    x = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(float) / 32768.0
    w.close()
    if nch > 1: x = x[::nch]
    def rep(gga, pp, t): print("  GPS      %s   %s" % (gga, pp or ""))
    def spk(uid, t):     print("  SPEAKER  unit %d is talking" % uid)
    def voi(frames, s, t): print("           (voice: %d IMBE frames, %.1fs audio)"
                                 % (len(frames), len(frames) * 0.02))
    def sta(m): pass
    dec = ComboDecoder(fr0, on_report=rep, on_speaker=spk, on_voice=voi, on_status=sta)
    print("COMBO replay: %s  (%d Hz, %.1fs)" % (os.path.basename(wavpath), fr0, len(x) / fr0))
    BLK = 2048
    for s in range(0, len(x), BLK):
        dec.feed(x[s:s + BLK])
    dec.flush()
    print("  -> %d transmissions, %d GPS reports\n" % (dec.tx, dec.reports))


if __name__ == "__main__":
    for p in sys.argv[1:]:
        _replay(p)
