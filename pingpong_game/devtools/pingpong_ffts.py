"""
    NOTE: this code is not part of the final project. this was used to varying degrees in order to evaluate the performance of
    different parts of the signal capture and angle detection code.
"""
from matplotlib import pyplot
import numpy as np

from signal_tools import load_signal
from signal_capture import preprocess_signal

media_dir = "media_files"
media_fname = "ping_pong_002"

audio_fname = f"{media_dir}/{media_fname}.wav"
[lch, rch, Fs] = load_signal(audio_fname, True)
Fs = 48_000

audio_segments = preprocess_signal(audio_fname, 30)

for segment in audio_segments.caps:
    lb,ub = segment[-1]
    x = lch[lb:ub]
    Nfft = int(2**(np.ceil(np.log2(len(x)))))
    freq = Fs*(np.arange(0, Nfft/2 + 1)/Nfft)
    X = np.fft.rfft(x, Nfft)
    pyplot.plot(freq, np.abs(X))
    pyplot.show()
