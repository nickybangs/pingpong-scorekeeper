import cv2
import logging
import json
from math import asin, degrees
from multiprocessing import Process, Value
import numpy as np
from pyaudio import PyAudio, paContinue
from scipy import signal
import threading
import time
import wave

from pingpong_game.config import config
from pingpong_game.game import Game
from pingpong_game.sig.helper import get_capture_fname
from pingpong_game.state_machine import StartState,GameState
from pingpong_game.scoreboard import Scoreboard
from pingpong_game.sig.signal_capture import preprocess_signal
from pingpong_game.sig.signal_tools import get_pingpong_filter, load_signal


Fs = config["fs"]
SIG_CAP_WINDOW_LEN = config["sig_cap_window_len"]
BLOCK_LEN = config["signal_block_len"]
SIG_CAP_ENERGY = config["sig_cap_energy"]
MAX_SIG_BUFFER_LEN = config["max_sig_buffer_len"]
filter_low_thresh = config["filter_low_thresh"]
filter_high_thresh = config["filter_high_thresh"]

SERVE_TIMEOUT = config["serve_timeout"]
GAME_EVENT_TIMEOUT = config["game_event_timeout"]
POST_SCORING_TIMEOUT = config["post_scoring_timeout"]

src_dir = "/Users/nickybangs/home/gh/ece_6183_project"

def sig_cap_notif_thread(sig_cap, quit_, audio_sync_idx):
    while quit_.value == 0:
        if len(sig_cap.caps) == 0:
            break
        audio_idx = audio_sync_idx.value
        lb, ub = audio_idx, audio_idx + 2*BLOCK_LEN # nframes * nchannels * nbytes
        sig_cap.capture_ready = False

        more_overlap = True
        while more_overlap:
            # get first index, captures are popped by the consumer
            # after notification is sent
            cap_start, cap_end = sig_cap.caps[0][-1]
            # check if the next capture overlaps with current audio segment
            # send notification if so
            if (cap_start < int(ub/2)) and (cap_end > int(lb/2)):
                print('cap detected')
                sig_cap.capture_ready = True
                sig_cap.condition.acquire()
                sig_cap.condition.notify()
                sig_cap.condition.wait()
                sig_cap.condition.release()
                sig_cap.capture_ready = False
            else:
                more_overlap = False
            if (len(sig_cap.caps) == 0):
                more_overlap = False


def audio_thread_func(audio_sync_idx, sig, quit_, pause, sig_cap):
    # output stream for audio playback
    pa = PyAudio()
    stream = pa.open(
        format=pa.get_format_from_width(2),
        rate=Fs,
        channels=2,
        input=False,
        output=True,
    )
    while quit_.value == 0:
        while pause.value == 1:
            # wait for signal instead
            time.sleep(.1)
        audio_idx = audio_sync_idx.value
        lb, ub = audio_idx, audio_idx + 2*BLOCK_LEN # nframes * nchannels * nbytes
        data = sig[lb:ub]
        stream.write(data.tobytes())
        audio_idx += 2*BLOCK_LEN
        audio_sync_idx.value = audio_idx

        more_overlap = True
        while more_overlap:
            cap_start, cap_end = sig_cap.caps[0][-1]
            # check if the next capture overlaps with current audio segment
            # send notification if so
            if (cap_start < int(ub/2)) and (cap_end > int(lb/2)):
                print('cap detected')
                sig_cap.capture_ready = True
                sig_cap.condition.acquire()
                sig_cap.condition.notify()
                sig_cap.condition.wait()
                sig_cap.condition.release()
                sig_cap.capture_ready = False
            else:
                more_overlap = False
            if (len(sig_cap.caps) == 0):
                more_overlap = False

    # close the output audio stream
    stream.close()
    pa.terminate()


def play_video_proc(fname, PAUSE, QUIT, audio_sync_idx):
    cap = cv2.VideoCapture(fname)
    video_fps = cap.get(cv2.CAP_PROP_FPS)
    cv2.namedWindow("output", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("output", 200, 100)
    cv2.moveWindow("output", 50,380)
    while(cap.isOpened()):
        ret, frame = cap.read()
        if ret == True:
            cv2.imshow('output', frame)
            key_ = cv2.waitKey(25)

            if QUIT.value == 1:
                break

            while PAUSE.value == 1:
                key_ = cv2.waitKey(5)
            frame_number = cap.get(cv2.CAP_PROP_POS_FRAMES)
            timestamp = frame_number/video_fps
            audio_sync_idx.value = int(timestamp*Fs)*2
        else:
            break
    cap.release()
    cv2.destroyAllWindows()


def core_game_thread(game):
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
    game.identify_players()
    # game.p1.name = "kyle"
    # game.p1.pos = "Right"
    # game.p2.name = "doug"
    # game.p2.pos = "Left"
    game.scoreboard.p1_str_var.set(game.p1.name)
    game.scoreboard.p2_str_var.set(game.p2.name)
    game.game_state = GameState(game.p1, game.p2)
    game.scoreboard.message(f"begin game when ready, {game.p1} serves")
    game.scoreboard.root.update()
    game.current_state = StartState(game.p1)

    game_thread = threading.Thread(target=core_game_thread, args=(game,))
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
    # multiprocessing.Value variables are used instead of globals
    # this allows the variables to be shared across the different threads
    # and processes. The pause and quit_ variables are used by the tkinter scoreboard
    # the audio_sync_idx variable is used to keep the video and audio in sync
    pause = Value('i', 1)
    quit_ = Value('i', 0)
    audio_sync_idx = Value('i', 0)

    # sample video used for demo, these paths can be changed to score different
    # videos. the mp4 and wav files should be synchronized beforehand in order
    # to get accurate playback
    audio_fname = f"{src_dir}/pingpong_game/devtools/media_files/pp_003.wav"
    video_fname = f"{src_dir}/pingpong_game/devtools/media_files/pp_003.mp4"
    # preprocess the audio file using the real time algorithm this makes sure
    # the results match what is observed in real time and don't get affected by
    # the audio syncing with the video
    sig_cap = preprocess_signal(
        audio_fname,
        SIG_CAP_ENERGY,
        window_len=SIG_CAP_WINDOW_LEN,
    )
    sig_cap.capture_ready = False
    print(sig_cap.caps[0][-1])
    global audio_idx
    audio_idx = 0

    # set up tkinter scoreboard and game object
    sb = Scoreboard()
    sb.init_tk(pause, quit_)
    game = Game(sig_cap, sb)

    # load the signal used for audio playback
    [sig, Fs] = load_signal(audio_fname, split_channels=False)

    # start audio thread, using audio_sync_idx to make sure audio and
    # video are synchronized
    audio_thread = threading.Thread(
        target=audio_thread_func,
        args=(audio_sync_idx, sig, quit_, pause, sig_cap),
    )

    # sigcap_thread = threading.Thread(
    #     target=sig_cap_notif_thread,
    #     args=(sig_cap, quit_, audio_sync_idx),
    # )
    # start video in a separate process, it doesn't work if you try
    # to play it in a thread
    vid_thread = Process(
        target=play_video_proc,
        args=(video_fname, pause, quit_, audio_sync_idx),
    )
    vid_thread.start()
    audio_thread.start()
    #sigcap_thread.start()

    # run game engine as main thread whlie video plays
    # it is required to be the main thread by tkinter
    game_engine_thread(game)

    # wait for the video and audio threads to finish before exiting
    vid_thread.join()
    audio_thread.join()
    #sigcap_thread.join()



if __name__ == "__main__":
    main()
