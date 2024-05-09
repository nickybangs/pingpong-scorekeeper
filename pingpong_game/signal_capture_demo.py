'''
    demo program to display the real-time signal capture and angle detection mechanism
    this code just listed for incoming siginals and outputs their angle and position
    execution stops when the scoreboard quit button is pressed. two microphones are required.
'''
from multiprocessing import Value
import numpy as np
from scipy import signal
import threading
import wave

from pingpong_game.config import config
from pingpong_game.game import Game
from pingpong_game.state_machine import StartState,GameState
from pingpong_game.scoreboard import Scoreboard
from pingpong_game.sig.signal_capture import SignalCapture
from pingpong_game.sig.signal_tools import (
    StreamSignal,
    get_pingpong_filter,
)

Fs = config["fs"]
SIG_CAP_WINDOW_LEN = config["sig_cap_window_len"]
BLOCK_LEN = config["signal_block_len"]
SIG_CAP_POWER = config["sig_cap_power"]
MAX_SIG_BUFFER_LEN = config["max_sig_buffer_len"]
filter_low_thresh = config["filter_low_thresh"]
filter_high_thresh = config["filter_high_thresh"]
K = 6
[b,a] = get_pingpong_filter(low=filter_low_thresh, high=filter_high_thresh, Fs=Fs, K=K)
lch_states = np.zeros(K*2)
rch_states = np.zeros(K*2)


def audio_thread_func(sig, sig_cap, quit_, pause, output_file):
    '''
    read next audio block and process via the SignalCapture class
    '''
    global lch_states, rch_states

    # keep track of current index in a given channel of the audio stream
    # used for identifying the frame boundaries of a captured sound
    audio_idx = 0
    while quit_.value == 0:
        data = sig.read(2*BLOCK_LEN)
        # split out left and right channels for processing
        lch = data[::2]
        rch = data[1::2] * config["polarity"]
        # filter each channel to only detect relevant frequency band
        [lch, lch_states] = signal.lfilter(b,a,lch,zi=lch_states)
        [rch, rch_states] = signal.lfilter(b,a,rch,zi=rch_states)

        # process segment to check if high power in signal
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
    the estimated angle and the power of the signal
    '''
    while (game.scoreboard.quit.value == 0):
        event = game.wait_for_game_event()


def main():
    quit_ = Value('i', 0)
    # NOTE: for this simple demo, the pause functionality is not implemented
    # it is included only because certain other parts of the code expect it
    pause = Value('i', 0)

    # save the captures to a wave file for post processing
    fname = "sig_cap_demo.wav"
    output_file = wave.open(fname, "wb")
    output_file.setnchannels(2)
    output_file.setsampwidth(2)
    output_file.setframerate(Fs)

    # set up an incoming stream and signal capture object
    sig = StreamSignal(frames_per_buffer=5*256)
    sig_cap = SignalCapture(SIG_CAP_WINDOW_LEN, SIG_CAP_POWER, MAX_SIG_BUFFER_LEN)

    # set up a scoreboard and game object - these are required for the event waiting logic
    # and the quit function
    sb = Scoreboard()
    sb.init_tk(pause, quit_)
    game = Game(sig_cap, sb)

    # start the audio processing thread
    audio_thread = threading.Thread(
        target=audio_thread_func,
        args=(sig, sig_cap, quit_, pause, output_file),
    )
    # start the signal waiter
    signal_waiter_thread = threading.Thread(
        target=signal_waiter,
        args=(game,),
    )

    # start a "game" - just need enough state to get the event waiter to work
    game.current_state = StartState(game.p1)
    audio_thread.start()
    signal_waiter_thread.start()
    while (game.scoreboard.quit.value == 0):
        game.scoreboard.root.update()

    # if the quit button is pressed - tell the waiter to stop waiting then wait for threads
    sig_cap.condition.acquire()
    sig_cap.condition.notify()
    sig_cap.condition.release()

    audio_thread.join()
    signal_waiter_thread.join()
    sig.close()
    output_file.close()


if __name__ == "__main__":
    main()
