"""C4FM symbol recovery from discriminator audio — a faithful Python port of OP25's
fsk4_demod_ff (tracking_loop_mmse). Float samples in -> soft 4-level symbols out
(nominal -3,-1,+1,+3). This is the proven front end for the OTA P25 decode:
an MMSE fractional-interpolation symbol-clock recovery + symbol-spread AGC +
a fine-frequency integrator, so it needs no pre-resampling (it locks at any
sample rate >= ~3 samples/symbol; 44.1 kHz native is fine for 4800 baud).

PROVEN 2026-11-23: on Jim's live-radio DEO capture the loop locks to a clean,
symmetric 4-level eye over the burst body, and the recovered NID BCH-decodes to
NAC 0x455 (Jim's confirmed NAC) on cleanly-synced GPS bursts.

Port notes (don't re-derive): taps = OP25's machine-generated 129x8 MMSE table
(fsk4_taps.npy, extracted from gen_interpolator_taps). Gains and clamps are
OP25's verbatim: K_SYMBOL_SPREAD .01, K_SYMBOL_TIMING .025, K_FINE .125,
K_COARSE .00125, spread nominal 2.0 clamped [1.6,2.4]. Feed the loop a signal
scaled so the four levels sit near +/-1,+/-3 (std ~= sqrt(5)); the fine-frequency
integrator nulls residual DC/carrier offset on its own once decisions lock.
"""
import numpy as np, os
TAPS = np.load(os.path.join(os.path.dirname(__file__), "fsk4_taps.npy"))  # (129,8)
NTAPS, NSTEPS = 8, 128
K_SYMBOL_SPREAD=0.0100; K_SYMBOL_TIMING=0.025
K_FINE_FREQUENCY=0.125; K_COARSE_FREQUENCY=0.00125
SPREAD_MAX=2.4; SPREAD_MIN=1.6

def fsk4_demod(sig, fs=44100.0, symrate=4800.0, init_spread=2.0, init_fine=0.0, return_state=False):
    d_symbol_time=symrate/fs
    d_symbol_clock=0.0; d_symbol_spread=init_spread; fine=init_fine; coarse=init_fine
    hist=[0.0]*NTAPS; last=0; out=[]; symbol_error=0.0
    for x in sig:
        d_symbol_clock+=d_symbol_time
        hist[last]=float(x); last=(last+1)%NTAPS
        if d_symbol_clock>1.0:
            d_symbol_clock-=1.0
            imu=int(np.floor(0.5+NSTEPS*(d_symbol_clock/d_symbol_time)))
            imu_p1=imu+1
            if imu>=NSTEPS: imu=NSTEPS-1; imu_p1=NSTEPS
            interp=0.0; interp_p1=0.0; j=last
            for i in range(NTAPS):
                interp   +=TAPS[imu  ][i]*hist[j]
                interp_p1+=TAPS[imu_p1][i]*hist[j]
                j=(j+1)%NTAPS
            interp-=fine; interp_p1-=fine
            out.append(2.0*interp/d_symbol_spread)
            if interp < -d_symbol_spread:
                symbol_error=interp+1.5*d_symbol_spread; d_symbol_spread-=symbol_error*0.5*K_SYMBOL_SPREAD
            elif interp < 0.0:
                symbol_error=interp+0.5*d_symbol_spread; d_symbol_spread-=symbol_error*K_SYMBOL_SPREAD
            elif interp < d_symbol_spread:
                symbol_error=interp-0.5*d_symbol_spread; d_symbol_spread+=symbol_error*K_SYMBOL_SPREAD
            else:
                symbol_error=interp-1.5*d_symbol_spread; d_symbol_spread+=symbol_error*0.5*K_SYMBOL_SPREAD
            if interp_p1<interp: d_symbol_clock+=symbol_error*K_SYMBOL_TIMING
            else:                d_symbol_clock-=symbol_error*K_SYMBOL_TIMING
            d_symbol_spread=min(max(d_symbol_spread,SPREAD_MIN),SPREAD_MAX)
            coarse+=(fine-coarse)*K_COARSE_FREQUENCY
            fine  +=symbol_error*K_FINE_FREQUENCY
    if return_state:
        return np.array(out), d_symbol_spread, fine
    return np.array(out)
