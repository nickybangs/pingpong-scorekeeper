from math import asin, degrees
import numpy as np
from scipy import signal
import struct
import time
import wave


def beamformer_time_delay(sig1, sig2, max_delay):
    """
    uses a simple time delay beamformer to estimate the delay
    between signal 2 and signal 1. if signal 2 is delayed the
    result will be positive
    """
    rms_max = 0
    delay_max = None
    len_ref = len(sig1)
    for delay in range(-max_delay,max_delay+1):
        if delay > 0:
            ref = sig1[:len_ref-delay]
            shift = sig2[delay:]
        else:
            D = np.abs(delay)
            ref = sig2[:len_ref-D]
            shift = sig1[D:]
        summed = ref + shift
        rms = get_rms(summed)
        if rms > rms_max:
            rms_max = rms
            delay_max = delay
    return rms_max, delay_max


def estimate_delay_cross_corr(sig1, sig2, delay_max):
    '''
    cross correlate the two channels, corr_max is the index of the max
    correlation, which should be when the signals are aligned
    if this value is greater than the midpoint that indicates the right
    channel is delayed, otherwise the left
    the estimated delay time is the delay in samples / sample rate
    '''
    mid_point = int(len(sig1)/2)
    corr = signal.correlate(sig1, sig2, 'same')
    corr_valid = corr[mid_point-delay_max : mid_point+delay_max]
    corr_max = corr_valid.argmax()
    est_delay = delay_max - corr_max
    return est_delay


def delay_to_angle(delay, delay_max):
    theta = asin(delay/delay_max)
    return degrees(theta)


def get_rms(signal):
    return np.sqrt(np.mean(np.array(signal)**2))


def load_signal(fname, split_channels=True):
    wf = wave.open(fname)
    num_channels = wf.getnchannels()
    Fs = wf.getframerate()
    if num_channels == 2:
        frames_raw = wf.readframes(wf.getnframes())
        wf.close()
        frames = np.frombuffer(frames_raw, dtype=np.int16)
        if split_channels:
            lchannel = frames[::2]
            rchannel = frames[1::2]
            return [lchannel, rchannel, Fs]
        else:
            return [frames, Fs]
    else:
        wf.close()
        raise ValueError('not implemented')
