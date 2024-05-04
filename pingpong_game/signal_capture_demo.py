from multiprocessing import Value
import numpy as np
from scipy import signal
import sys
import threading
import time
import wave

from pingpong_game.config import config
from pingpong_game.game import Game
from pingpong_game.state_machine import StartState,GameState
from pingpong_game.scoreboard import Scoreboard
from pingpong_game.sig.signal_capture import SignalCapture
from pingpong_game.sig.signal_tools import (
    WaveSignal,
    StreamSignal,
    get_pingpong_filter,
    get_polarity,
)

Fs = config["fs"]
SIG_CAP_WINDOW_LEN = config["sig_cap_window_len"]
BLOCK_LEN = config["signal_block_len"]
SIG_CAP_ENERGY = config["sig_cap_energy"]
MAX_SIG_BUFFER_LEN = config["max_sig_buffer_len"]
filter_low_thresh = config["filter_low_thresh"]
filter_high_thresh = config["filter_high_thresh"]
K = 6
[b,a] = get_pingpong_filter(low=filter_low_thresh, high=filter_high_thresh, Fs=Fs, K=K)
lch_states = np.zeros(K*2)
rch_states = np.zeros(K*2)

SERVE_TIMEOUT = config["serve_timeout"]
GAME_EVENT_TIMEOUT = config["game_event_timeout"]
POST_SCORING_TIMEOUT = config["post_scoring_timeout"]


def audio_thread_func(sig, sig_cap, quit_, pause, output_file):
    '''
    read next audio block and process via the SignalCapture class
    '''
    global lch_states, rch_states

    # keep track of current index in a given channel of the audio stream
    # used for identifying the frame boundaries of a captured sound
    audio_idx = 0
    while quit_.value == 0:
        # if 'pause' is set, no sounds are captured by the signal capture class
        if pause.value == 1:
            sig_cap.do_capture = False
        else:
            sig_cap.do_capture = True
        data = sig.read(2*BLOCK_LEN)
        # split out left and right channels for processing
        lch = data[::2]
        rch = data[1::2] * config["polarity"]
        # filter each channel to only detect relevant frequency band
        [lch, lch_states] = signal.lfilter(b,a,lch,zi=lch_states)
        [rch, rch_states] = signal.lfilter(b,a,rch,zi=rch_states)

        # process segment to check if high energy in signal
        # the signal capture class uses condition.notify to let the game
        # engine know if a ping-pong sound was detected
        sig_cap.condition.acquire()
        sig_cap.process(lch, rch, frame_offset=audio_idx)
        sig_cap.condition.release()
        # we are tracking frame index so just offset by block length
        audio_idx += BLOCK_LEN
        output_file.writeframesraw(data.tobytes())


def signal_waiter(game):
    '''
    simple function to loop continuously until quit button pressed
    captured signals are printed to the console showing the side the sound came from
    the estimated angle and the energy of the signal
    '''
    while (game.scoreboard.quit.value == 0):
        event = game.wait_for_game_event()


def main():
    quit_ = Value('i', 0)
    # pause is used in this case to turn off signal captures, it is used
    # when getting input from the user, in which case we don't want to do anything
    # with incoming signals
    pause = Value('i', 0)

    fname = "sig_cap_demo.wav"
    output_file = wave.open(fname, "wb")
    output_file.setnchannels(2)
    output_file.setsampwidth(2)
    output_file.setframerate(Fs)

    sig = StreamSignal(frames_per_buffer=5*256)
    sig_cap = SignalCapture(SIG_CAP_WINDOW_LEN, SIG_CAP_ENERGY, MAX_SIG_BUFFER_LEN)

    sb = Scoreboard()
    sb.init_tk(pause, quit_)
    game = Game(sig_cap, sb)

    audio_thread = threading.Thread(
        target=audio_thread_func,
        args=(sig, sig_cap, quit_, pause, output_file),
    )
    signal_waiter_thread = threading.Thread(
        target=signal_waiter,
        args=(game,),
    )

    game.current_state = StartState(game.p1)
    audio_thread.start()
    signal_waiter_thread.start()
    while (game.scoreboard.quit.value == 0):
        game.scoreboard.root.update()

    sig_cap.condition.acquire()
    sig_cap.condition.notify()
    sig_cap.condition.release()

    audio_thread.join()
    signal_waiter_thread.join()
    sig.close()
    output_file.close()


if __name__ == "__main__":
    main()
