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


# set up global settings using the config file
# all variables are explained in the config file and also in relevant functions where used
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


def core_game_thread(game):
    '''
    thread to wait for game events, receiving notifications from the signal capture
    class whenever a ping pong sound is detected and passing the detected event
    through a state machine
    '''
    # continuously loop processing game events as they come in
    # exit loop if error or end of game states detected or Quit button pressed
    while ((game.current_state.state_name not in ["ErrorState", "EndState"])
           and (game.scoreboard.quit.value == 0) and (game.scoreboard.pause.value == 0)):
        if game.current_state.state_name == "ScoreState":
            post_scoring_state = game.scoreboard.update_score(game.current_state)
            # exit loop if game over
            if post_scoring_state.state_name == "EndState":
                break
            #ignore any sounds for small period of time after a player has scored
            game.scoreboard.pause.value = 1
            game.sig_cap.clear_captures()
            time.sleep(POST_SCORING_TIMEOUT)
            game.scoreboard.pause.value = 0
            # wait for the next serve
            event = game.wait_for_game_event(SERVE_TIMEOUT)
        elif game.current_state.state_name == "StartState":
            event = game.wait_for_game_event(SERVE_TIMEOUT)
        else:
            event = game.wait_for_game_event(GAME_EVENT_TIMEOUT)
        game.current_state = game.game_state.transition(game.current_state, event)


def game_engine_thread(game):
    # do this in thread
    game.identify_players()
    game.game_state = GameState(game.p1, game.p2)
    game.scoreboard.message(f"begin game when ready, {game.p1} serves")
    game.scoreboard.root.update()
    game.current_state = StartState(game.p1)

    game_thread = threading.Thread(target=core_game_thread, args=(game,))
    game_thread.start()
    # while game thread is processing events, the main thread updates the scoreboard
    # and updates the Tkinter root object
    while ((game.current_state.state_name not in ["ErrorState", "EndState"])
           and (game.scoreboard.quit.value != 1)):
        p1_score = game.scoreboard.score[0]
        p2_score = game.scoreboard.score[1]
        game.scoreboard.p1_score_var.set(p1_score)
        game.scoreboard.p2_score_var.set(p2_score)
        game.scoreboard.root.update()
        if game.scoreboard.pause.value == 1:
            # send notification to game even thread which will cause 
            # it to drop out of its loop, then we wait for the resume button to be pressed
            game.sig_cap.condition.acquire()
            game.sig_cap.condition.notify()
            game.sig_cap.condition.release()
            game_thread.join()
            while game.scoreboard.pause.value == 1:
                game.scoreboard.root.update()
            serving = game.scoreboard.serving
            game.current_state = StartState(serving)
            game_thread = threading.Thread(target=core_game_thread, args=(game,))
            game_thread.start()

    # tell the game thread to stop waiting for a game event since quit button
    # has been pressed
    if game.scoreboard.quit.value == 1:
        game.sig_cap.condition.acquire()
        game.sig_cap.condition.notify()
        game.sig_cap.condition.release()
        game_thread.join()
        return

    # wait for event processing thread to finish then handle end game state
    game_thread.join()

    if game.current_state.state_name == "ErrorState":
        err_msg = game.current_state.msg
        game.scoreboard.message(f"something went wrong, error message: {err_msg}")
    elif game.current_state.state_name != "EndState":
        game.scoreboard.message(f"unexpected end state: {game.current_state.state_name}")
    else:
        winning_player = game.current_state.player
        if winning_player == game.p1:
            w_score, l_score = game.scoreboard.score
        else:
            l_score, w_score = game.scoreboard.score
        game.scoreboard.message(f"{winning_player} wins {w_score} to {l_score}")
    game.scoreboard.root.update()


def main(fname):
    quit_ = Value('i', 0)
    # pause is used in this case to turn off signal captures, it is used
    # when getting input from the user, in which case we don't want to do anything
    # with incoming signals
    pause = Value('i', 0)
    # save incoming signal for replaying after game - useful for testing
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
    audio_thread.start()
    game_engine_thread(game)
    audio_thread.join()
    sig.close()
    output_file.close()


if __name__ == "__main__":
    main('test2.wav')
