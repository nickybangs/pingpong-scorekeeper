"""
    NOTE: this code is not part of the final project. this was used to varying degrees in order to evaluate the performance of
    different parts of the signal capture and angle detection code.
"""

'''
plot a signal with a scrolling vertical bar tracking current location in the file
applies a bandpass filter with passband 8khz to 10khz in order to only show ping pong
events
'''

from matplotlib import pyplot, animation
import matplotlib.patches as patches
import numpy as np
from pyaudio import PyAudio, paInt16
from scipy import signal

from signal_tools import load_signal

pa = PyAudio()
[sig, Fs] = load_signal('media_files/pp_003.wav', False)

block_time = .1
block_len = int(block_time*Fs)
idx=0

stream = pa.open(
    format=paInt16,
    rate=Fs,
    channels=2,
    input=False,
    output=True,
    frames_per_buffer=block_len,
)

lch = sig[::2]
rch = sig[1::2]

fcl = 2 * (8_000/Fs) # was 100
fch = 2 * (10_000/Fs)
fc = [fcl, fch]
K = 6
[b,a] = signal.cheby1(K, .5, fc, 'bandpass')
lch = signal.lfilter(b,a,lch)
rch = signal.lfilter(b,a,rch)

y_lim = max(
    np.mean(np.abs(lch[np.where(lch > 500)])),
    np.mean(np.abs(rch[np.where(rch > 500)])),
)
ts = np.arange(len(lch))/Fs

fig, ax = pyplot.subplots(1)
fig.set_size_inches(15,8)
print(len(lch))

[g1] = ax.plot(ts, lch-100)
[g2] = ax.plot(ts, rch+200)

ax.set_ylim(-y_lim, y_lim)
rect = patches.Rectangle(
    (-block_time, -y_lim), block_time, 2*y_lim, linewidth=1, facecolor='grey', alpha=.5,
)

ax.add_patch(rect)

def my_update(i):
    global idx
    lb, ub = idx*block_len*2, (idx+1)*block_len*2
    rect.set_xy([(idx-2)*block_time, -y_lim])
    idx += 1
    stream.write(sig[lb:ub].tobytes())
    return rect,

anim = animation.FuncAnimation(
    fig,
    my_update,
    interval = block_time*1000,
    blit = True,
    cache_frame_data = False,
    repeat=True,
)


fig.tight_layout()
pyplot.show()
stream.close()
