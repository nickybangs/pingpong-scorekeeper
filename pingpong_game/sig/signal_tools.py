from math import asin, acos, degrees
import numpy as np
from pyaudio import PyAudio
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
    # iterate over all possible delays between -max delay and +max delay
    # the estimated delay is that which results in the signal with the highest power
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
    return delay_max


def estimate_delay_cross_corr(sig1, sig2, delay_max):
    '''
    cross correlate the two channels, corr_max is the index of the max correlation,which should be when
    the signals are aligned. if this value is greater than the midpoint that indicates the right
    channel is delayed, otherwise the left the estimated delay time is the delay in samples / sample rate
    '''
    mid_point = int(len(sig1)/2)
    corr = signal.correlate(sig1, sig2, 'same')
    # to get better results we only look at results within +- delay_max of the midpoint
    # this helps ensure we get sensible results
    corr_valid = corr[mid_point-delay_max : mid_point+delay_max]
    corr_max = corr_valid.argmax()
    est_delay = delay_max - corr_max
    return est_delay


technique_funcs = {
    "xcorr": estimate_delay_cross_corr,
    "beamforming": beamformer_time_delay,
}

def get_angle_from_sound(sig1, sig2, delay_max, technique="xcorr"):
    '''
    get the angle of the incoming sound by estimated the delay using the specified technique
    cross correlation is used by default
    '''
    delay = technique_funcs[technique](sig1, sig2, delay_max)
    return delay_to_angle(delay, delay_max)


def delay_to_angle(delay, delay_max):
    '''
    return the estimated angle of arrival based on the delay between the signals and the maximum
    delay possible
    '''
    theta = acos(delay/delay_max)
    # for the ping pong game the angles are assume to be -90 degrees to +90 degrees
    return 90 - degrees(theta)

def get_rms(signal):
    '''
    return the root mean square of the input signal or segment
    '''
    return np.sqrt(np.mean(np.array(signal)**2))


def get_pingpong_filter(low, high, Fs, K=6, filt_type="cheby"):
    '''
    return the desired bandpass filter to be used (8000, 10000) does a good job of only
    passing ping pong sounds
    '''
    fcl = 2 * (low/Fs) # usually 8,000
    fch = 2 * (high/Fs) # usually 10,000
    fc = [fcl, fch]
    # use either a chebyshev1 or butterworth filter
    if filt_type == "cheby":
        [b,a] = signal.cheby1(K, .5, fc, 'bandpass')
    else:
        [b,a] = signal.butter(K, fc, 'bandpass')
    return b,a


def get_polarity(sig1, sig2):
    '''
    determine sign difference between two signals, some microphone set ups
    will have signals with flipped signs, this tells the code if it needs to
    reverse this
    '''
    # see documentation for why this is expected to work in general
    opp_sign_max = signal.correlate(sig1, -1*sig2, 'valid')
    same_sign_max = signal.correlate(sig1, sig2, 'valid')
    if opp_sign_max > same_sign_max:
        return -1
    else:
        return 1


def load_signal(fname, split_channels=True):
    '''
    load a signal from the wave filepath. split into two channels if requested
    return the signal and Fs
    '''
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


class StreamSignal:
    '''
    helper class to read in blocks from a two channel input stream
    '''
    def __init__(self, frames_per_buffer=256):
        self.rate = 48_000
        self.frames_per_buffer = frames_per_buffer

        self.pa = PyAudio()
        self.stream = self.pa.open(
            format=self.pa.get_format_from_width(2),
            channels=2,
            rate=self.rate,
            input=True,
            output=False,
            frames_per_buffer=self.frames_per_buffer,
        )

    def read(self, blocklen):
        frames_raw = self.stream.read(blocklen, exception_on_overflow=False)
        signal = np.frombuffer(frames_raw, dtype=np.int16)
        return signal

    def close(self):
        self.stream.stop_stream()
        self.stream.close()
        self.pa.terminate()
