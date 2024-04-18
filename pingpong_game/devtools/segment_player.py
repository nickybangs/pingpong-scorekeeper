'''
given a media filename loads the video and audio and plays each detected segment
for each segment the corresponding video label is shown if there is any overlap
'''
import cv2
import json
import logging
from math import asin, ceil, degrees, floor
from matplotlib import pyplot
import numpy as np
from pyaudio import PyAudio, paContinue
from scipy import signal
import time
import wave

from pingpong_game.signal.helper import get_capture_fname
from pingpong_game.signal.signal_capture import preprocess_signal
from pingpong_game.signal.signal_tools import load_signal, estimate_delay_cross_corr


media_dir = "pingpong_game/devtools/media_files"
media_fname = "pp_003"

video_fname = f"{media_dir}/{media_fname}.mp4"
audio_fname = f"{media_dir}/{media_fname}.wav"
cap_fname = f"pingpong_game/devtools/captures/{media_fname}_caps_001.json"

[sig, Fs] = load_signal(audio_fname, split_channels=False)
audio_segments = preprocess_signal(audio_fname, 100)

mic_diameter_inches = 5
mic_diameter_m = (5/12)*.3048
delay_max = int((mic_diameter_m / 330)*Fs)

def get_overlap(segment, all_segments):
    s,e = segment
    idx = 0
    overlaps = []
    next_s, next_e, _= all_segments[idx]
    while (s > next_e) and (idx < len(all_segments)):
        idx += 1
        next_s, next_e, _= all_segments[idx]

    while (next_s < e) and (idx < len(all_segments)):
        overlaps.append(all_segments[idx])
        idx += 1
        next_s, next_e, _= all_segments[idx]
    return overlaps


with open(cap_fname) as f:
    video_segments = json.load(f)

pa = PyAudio()

audio_idx = 0

def _stream_cb(in_data, frame_count, time_info, status):
    global audio_idx
    lb, ub = audio_idx, audio_idx + 2*frame_count # nframes * nchannels * nbytes
    data = sig[lb:ub]
    # if time slice overlaps with preprocessed data, print results
    audio_idx += 2*frame_count
    return (data.tobytes(), paContinue)

stream = pa.open(
    format=pa.get_format_from_width(2),
    rate=Fs,
    channels=2,
    input=False,
    output=True,
    stream_callback=_stream_cb,
)

cap = cv2.VideoCapture(video_fname)
video_fps = cap.get(cv2.CAP_PROP_FPS)
print(f"{video_fps=}")

if (cap.isOpened()== False):
    print("Error opening video file")

cap_idx = 0
while cap_idx < len(audio_segments.caps):
    sig_cap = audio_segments.caps[cap_idx]
    audio_start, audio_end = sig_cap[-1][0], sig_cap[-1][1]
    video_start = floor(video_fps*(audio_start/Fs))
    video_end = ceil(video_fps*(audio_end/Fs))
    overlap = get_overlap(
        (video_start, video_end),
        video_segments,
    )
    if len(overlap) > 0:
        for o in overlap:
            print(o[0], o[1], o[2])

    cap.set(cv2.CAP_PROP_POS_FRAMES, video_start)

    done = False

    audio_idx = int((video_start/video_fps)*Fs)*2
    stream.start_stream()
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
    stream.stop_stream()
    print(estimate_delay_cross_corr(sig_cap[0], sig_cap[1], delay_max))
    comm = input('command: [N/r/q]').lower()
    if comm == "r":
        pass
    elif comm == "n":
        cap_idx += 1
    else:
        break


cap.release()
cv2.destroyAllWindows()

stream.stop_stream()
stream.close()
pa.terminate()
