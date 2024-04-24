import cv2
import json
import logging
from math import asin, ceil, degrees, floor
from matplotlib import pyplot
import numpy as np
from pyaudio import PyAudio, paContinue
from scipy import signal
import sys
import time
import wave

from pingpong_game.sig.helper import get_capture_fname
from pingpong_game.sig.signal_capture import preprocess_signal
from pingpong_game.sig.signal_tools import load_signal, estimate_delay_cross_corr


media_dir = "pingpong_game/devtools/media_files"
media_fname = "pp_003"

video_fname = f"{media_dir}/{media_fname}.mp4"
audio_fname = f"{media_dir}/{media_fname}.wav"
cap_fname = f"pingpong_game/devtools/captures/{media_fname}_caps_001.json"

indices = list(map(int, sys.argv[1].split(',')))

with open(cap_fname) as f:
    video_segments = json.load(f)

cap = cv2.VideoCapture(video_fname)
video_fps = cap.get(cv2.CAP_PROP_FPS)

idx = 0
while idx < len(indices):
    index = indices[idx]
    video_start, video_end, _ = video_segments[index]
    cap.set(cv2.CAP_PROP_POS_FRAMES, video_start)
    done = False
    print(video_start, video_end)

    while not done:
        curr_frame = cap.get(cv2.CAP_PROP_POS_FRAMES)
        if curr_frame >= video_end:
            done = True
        ret, frame = cap.read()
        if ret == True:
            cv2.imshow('Frame', frame)
            key_ = cv2.waitKey(25)
            if (key_ & 0xFF) == ord('q'):
                done = True
    comm = input('command: [N/r/q]').lower()
    if comm == "r":
        pass
    elif comm == "n":
        idx += 1
    else:
        break


cap.release()
cv2.destroyAllWindows()

