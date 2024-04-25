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

LCH_WAIT_BUFFER = []
RCH_WAIT_BUFFER = []

src_dir = "/Users/nickybangs/home/gh/ece_6183_project"


def audio_thread_func(audio_sync_idx, stream, sig, sig_cap, quit_, pause):
    global lch_states, rch_states
    while quit_.value == 0:
        while pause.value == 1:
            # wait for signal instead
            time.sleep(.1)
        audio_idx = audio_sync_idx.value
        lb, ub = audio_idx, audio_idx + 2*BLOCK_LEN # nframes * nchannels * nbytes
        data = sig[lb:ub]
        audio_idx += 2*BLOCK_LEN
        lch = data[::2]
        rch = data[1::2]*-1
        [lch, lch_states] = signal.lfilter(b,a,lch,zi=lch_states)
        [rch, rch_states] = signal.lfilter(b,a,rch,zi=rch_states)

        sig_cap.condition.acquire()
        sig_cap.process(lch, rch, frame_offset=lb/2)
        sig_cap.condition.release()

        audio_sync_idx.value = audio_idx
        stream.write(data.tobytes())


def _stream_cb(in_data, frame_count, time_info, status):
    global audio_sync_idx, sig, sig_cap
    global LCH_WAIT_BUFFER, RCH_WAIT_BUFFER
    audio_idx = audio_sync_idx.value
    lb, ub = audio_idx, audio_idx + 2*frame_count # nframes * nchannels * nbytes
    data = sig[lb:ub]
    audio_idx += 2*frame_count
    lch = data[::2]
    rch = data[1::2]*-1
    lch = signal.lfilter(b,a,lch)
    rch = signal.lfilter(b,a,rch)
    audio_sync_idx.value = audio_idx

    if len(lch) < SIG_CAP_WINDOW_LEN:
        LCH_WAIT_BUFFER += list(lch)
        RCH_WAIT_BUFFER += list(rch)

    while len(LCH_WAIT_BUFFER) > SIG_CAP_WINDOW_LEN:
        sig_cap.condition.acquire()
        l_segment = LCH_WAIT_BUFFER[:SIG_CAP_WINDOW_LEN]
        r_segment = RCH_WAIT_BUFFER[:SIG_CAP_WINDOW_LEN]
        sig_cap.process(l_segment, r_segment)
        LCH_WAIT_BUFFER = LCH_WAIT_BUFFER[SIG_CAP_WINDOW_LEN:]
        RCH_WAIT_BUFFER = RCH_WAIT_BUFFER[SIG_CAP_WINDOW_LEN:]
        sig_cap.condition.release()
    return (data.tobytes(), paContinue)


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
            # game.do_capture = False
            # game.sig_cap.clear_captures()
            # time.sleep(POST_SCORING_TIMEOUT)
            # game.do_capture = True
            event = game.wait_for_game_event(SERVE_TIMEOUT)
        else:
            event = game.wait_for_game_event(GAME_EVENT_TIMEOUT)
        game.current_state = game.game_state.transition(game.current_state, event)


def game_engine_thread(game):
    global done#,sig_cap

    game.identify_players()
    # game.p1.name = 'emily'
    # game.p2.name = 'nicky'
    # game.p1.position = 'Left'
    # game.p2.position = 'Right'
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
    global audio_sync_idx
    pa = PyAudio()
    pause = Value('i', 1)
    quit_ = Value('i', 0)
    audio_sync_idx = Value('i', 0)

    audio_fname = f"{src_dir}/pingpong_game/devtools/media_files/pp_003.wav"
    video_fname = f"{src_dir}/pingpong_game/devtools/media_files/pp_003.mp4"

    global sig, sig_cap, done
    done = False
    [sig, Fs] = load_signal(audio_fname, split_channels=False)
    sig_cap = SignalCapture(SIG_CAP_WINDOW_LEN, SIG_CAP_ENERGY, MAX_SIG_BUFFER_LEN)
    DELAY_MAX = config["delay_max"]
    print(DELAY_MAX)

    stream = pa.open(
        format=pa.get_format_from_width(2),
        rate=Fs,
        channels=2,
        input=False,
        output=True,
        # stream_callback=_stream_cb,
    )
    #stream.stop_stream()
    sb = Scoreboard()
    sb.init_tk(pause, quit_, stream)
    game = Game(sig_cap, sb)
    # vid_thread = threading.Thread(target=game_engine_thread, args=(game,))
    # vid_thread.daemon = True
    # vid_thread.start()
    # play_video_thread(video_fname, stream)
    # done = True
    # vid_thread.join()

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
    game_engine_thread(game)
    # sb.root.mainloop()
    # done = True
    vid_thread.join()
    audio_thread.join()
    # fname = get_capture_fname('pp_003_realtime_caps')
    # sig_cap.save(fname)

    stream.close()
    pa.terminate()


if __name__ == "__main__":
    main()
