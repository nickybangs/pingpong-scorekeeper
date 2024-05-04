'''
    Video playback version of the scorekeeper. Most of the logic is the same as the realtime version, but slightly
    adjusted to try to handle synchronizing the audio to the video.

    NOTE: due to the synchronization, the signal capture results are not always consistent. This is only reliable as a
    demonstration device where you can re-run the program to get the results that would be observed in real time.
    To simulate realtime results, it is best to use the preprocess_signal function in sig/signal_capture
'''
import cv2
from multiprocessing import Process, Value
import numpy as np
from pyaudio import PyAudio
from scipy import signal
import threading
import time

from pingpong_game.config import config
from pingpong_game.game import Game
from pingpong_game.state_machine import StartState,GameState
from pingpong_game.scoreboard import Scoreboard
from pingpong_game.sig.signal_capture import SignalCapture
from pingpong_game.sig.signal_tools import get_pingpong_filter, load_signal


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


def audio_thread_func(audio_sync_idx, stream, sig, sig_cap, quit_, pause):
    '''
    process audio stream as if it were real time, keeping audio index in sync
    with video frames for better playback
    '''
    global lch_states, rch_states
    while quit_.value == 0:
        # if paused, spin wait until resumed - NOTE: could be improved with signals
        while pause.value == 1:
            time.sleep(.1)
        # update audio index value to sync with video (video processing code sets this every frame)
        audio_idx = audio_sync_idx.value
        lb, ub = audio_idx, audio_idx + 2*BLOCK_LEN
        data = sig[lb:ub]
        audio_idx += 2*BLOCK_LEN
        lch = data[::2]
        rch = data[1::2]*config["polarity"]
        [lch, lch_states] = signal.lfilter(b,a,lch,zi=lch_states)
        [rch, rch_states] = signal.lfilter(b,a,rch,zi=rch_states)

        # run signal through processor. the reason for the inconsistent results can be seen in this thread
        # since the starting index can change at random, it is possible that different signals will be passed to the processor
        # this can have the effect that some captures that would occur in a realtime setting may be missed in the video playback
        # i tried various things to fix this, but in the end nothing ended up working nicely with the audio playback so i returned
        # to this version. the corruption only happens every once and a while though and in general the results in this version
        # resemble the realtime version. as noted above though, to get the actual results as a reference, the preprocess_signal
        # function should be used
        sig_cap.condition.acquire()
        sig_cap.process(lch, rch, frame_offset=lb/2)
        sig_cap.condition.release()

        # update the audio index
        audio_sync_idx.value = audio_idx
        # output to the audio stream
        stream.write(data.tobytes())


def play_video_proc(fname, PAUSE, QUIT, audio_sync_idx):
    '''
    play the video frames in a separate process. updating the audio index each frame to keep audio and video in sync
    NOTE: the PAUSE and QUIT values are shared with the main thread and the audio thread. multiprocessing.Value variables
    are used in all of the code instead of globals since Value variables are needed to share data between processes
    Though they aren't needed in the realtime version, they are used so that more code could be compatible for both versions
    '''
    cap = cv2.VideoCapture(fname)
    video_fps = cap.get(cv2.CAP_PROP_FPS)
    # set window size and location
    cv2.namedWindow("output", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("output", 200, 100)
    cv2.moveWindow("output", 50,380)
    # display video
    while(cap.isOpened()):
        ret, frame = cap.read()
        if ret == True:
            cv2.imshow('output', frame)
            key_ = cv2.waitKey(25)

            # break if quit button pressed
            if QUIT.value == 1:
                break

            # if paused, just wait for resume button
            while PAUSE.value == 1:
                key_ = cv2.waitKey(5)
            frame_number = cap.get(cv2.CAP_PROP_POS_FRAMES)
            timestamp = frame_number/video_fps
            # set the audio index based on the current time in the video
            audio_sync_idx.value = int(timestamp*Fs)*2
        else:
            break
    cap.release()
    cv2.destroyAllWindows()


def game_event_thread(game):
    '''
    similar to the realtime function of the same name, doesn't include funcionality only needed for realtime
    '''
    event = game.wait_for_game_event(SERVE_TIMEOUT)
    game.current_state = game.game_state.transition(game.current_state, event)

    while ((game.current_state.state_name not in ["ErrorState", "EndState"])
           and (game.scoreboard.quit.value != 1)):
        if game.current_state.state_name == "ScoreState":
            post_scoring_state = game.scoreboard.update_score(game.current_state)
            event = game.wait_for_game_event(SERVE_TIMEOUT)
        else:
            event = game.wait_for_game_event(GAME_EVENT_TIMEOUT)
        game.current_state = game.game_state.transition(game.current_state, event)


def game_engine_thread(game):
    '''
    similar to realtime version function of the same name
    '''
    game.identify_players()
    game.game_state = GameState(game.p1, game.p2)
    game.scoreboard.message(f"begin game when ready, {game.p1} serves")
    game.scoreboard.root.update()
    game.current_state = StartState(game.p1)

    game_thread = threading.Thread(target=game_event_thread, args=(game,))
    game_thread.start()
    while ((game.current_state.state_name not in ["ErrorState", "EndState"])
           and (game.scoreboard.quit.value != 1)):
        p1_score = game.scoreboard.score[0]
        p2_score = game.scoreboard.score[1]
        game.scoreboard.p1_score_var.set(p1_score)
        game.scoreboard.p2_score_var.set(p2_score)
        game.scoreboard.root.update()

    if game.scoreboard.quit.value == 1:
        game.sig_cap.condition.acquire()
        game.sig_cap.condition.notify()
        game.sig_cap.condition.release()
        game_thread.join()
        return
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


def main():
    '''
    main function for video playback version. initializes the game, video and audio streams.
    playback is paused at start, and resumed only after player identification takes place
    '''
    pa = PyAudio()
    # multiprocessing.Value variables needed to share memory between processes
    pause = Value('i', 1)
    quit_ = Value('i', 0)
    audio_sync_idx = Value('i', 0)

    audio_fname = config["audio_fname"]
    video_fname = config["video_fname"]

    # load the signal from the audio fname provided in the config
    [sig, Fs] = load_signal(audio_fname, split_channels=False)
    # initialize a signal capture object
    sig_cap = SignalCapture(SIG_CAP_WINDOW_LEN, SIG_CAP_ENERGY, MAX_SIG_BUFFER_LEN)

    # open an output stream for playback
    stream = pa.open(
        format=pa.get_format_from_width(2),
        rate=Fs,
        channels=2,
        input=False,
        output=True,
    )
    # initialize a scoreboard interface and the game object
    sb = Scoreboard()
    sb.init_tk(pause, quit_)
    game = Game(sig_cap, sb)

    # start the audio processing thread and the video Process
    audio_thread = threading.Thread(
        target=audio_thread_func,
        args=(audio_sync_idx, stream, sig, sig_cap, quit_, pause),
    )
    vid_thread = Process(
        target=play_video_proc,
        args=(video_fname, pause, quit_, audio_sync_idx),
    )
    vid_thread.start()
    audio_thread.start()
    # run the main game loop
    game_engine_thread(game)

    # after game, wait for audio and video to finish before closing
    vid_thread.join()
    audio_thread.join()

    stream.close()
    pa.terminate()


if __name__ == "__main__":
    main()
