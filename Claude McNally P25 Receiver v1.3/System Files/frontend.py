"""OP25-faithful C4FM front end (from p25_demodulator.py + op25_c4fm_mod.py).
discriminator float -> RMS-AGC -> C4FM RX de-emphasis symbol filter -> ready for
fsk4_demod. This is the piece that was missing; with it the PDU data blocks
decode to the real NMEA. NO invented pre-filter.

OP25 chain (p25_demodulator, demod_type fsk4):
  baseband -> rmsagc_ff(alpha=0.01,k=1.0) -> fir_filter_fff(c4fm_taps RX, span=9)
            -> fsk4_demod_ff
"""
import numpy as np

def _transfer_function_rx(symbol_rate=4800, rate_mult=1.0):
    # op25_c4fm_mod.transfer_function_rx: P25 C4FM de-emphasis D(f)=sinc
    rate = symbol_rate * rate_mult; xfer = []
    for f in range(int(rate)):
        t = np.pi * f / rate
        xfer.append(1.0 if t < 1e-6 else np.sin(t) / t)
    return xfer

def c4fm_rx_taps(sample_rate, symbol_rate=4800, span=9, filter_gain=1.0):
    # op25_c4fm_mod.c4fm_taps(generator=transfer_function_rx).generate()
    sps = int(sample_rate / symbol_rate); ntaps = (sps * span) | 1
    ir = np.fft.fftshift(np.fft.irfft(_transfer_function_rx(symbol_rate), sample_rate))
    start = np.argmax(ir) - (ntaps - 1) // 2
    c = ir[start:start + ntaps]
    return c * (filter_gain / np.sum(c))

def rmsagc(x, alpha=0.01, k=1.0):
    # op25_repeater.rmsagc_ff
    out = np.empty_like(x, dtype=float); rms = 1.0
    for i, v in enumerate(x):
        rms = (1 - alpha) * rms + alpha * (v * v)
        out[i] = v * (k / np.sqrt(rms) if rms > 1e-12 else 1.0)
    return out

def front_end(x, sample_rate):
    """discriminator samples -> C4FM baseband ready for fsk4_demod."""
    a = x - np.mean(x)                                   # static DC only
    a = rmsagc(a)
    a = np.convolve(a, c4fm_rx_taps(sample_rate), mode='same')
    return a
