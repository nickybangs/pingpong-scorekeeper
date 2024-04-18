from multiprocessing import Process
import numpy as np
from scipy import signal
import sys
from threading import Thread
import time

from pingpong_game.game import Game
from pingpong_game.signal.signal_tools import WaveSignal, StreamSignal


FROM_FILE = True
fname = "pingpong_game/devtools/media_files/pp_003.wav"
NUM_CHANNELS = 1
Fs = 48_000
SIG_CAP_WINDOW_LEN = .01*Fs

if FROM_FILE:
    sig = WaveSignal(fname)
else:
    sig = StreamSignal(NUM_CHANNELS, frames_per_buffer=2*256)#int(5*Fs))

# x = sig.read(100)
# print(x)
g = Game(sig)

#g.play_test()
g.play()
sig.close()
