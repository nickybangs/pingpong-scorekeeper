"""
    NOTE: this code is not part of the final project. this was used to varying degrees in order to evaluate the performance of
    different parts of the signal capture and angle detection code.
"""
import cv2
import json
import logging
from math import asin, ceil, degrees, floor
from matplotlib import pyplot
import numpy as np
from scipy import signal
import time
import wave

from helper import get_capture_fname, get_overlap
from signal_capture import preprocess_signal
from signal_tools import load_signal, estimate_delay


media_dir = "media_files"
media_fname = "pp_003"

video_fname = f"{media_dir}/{media_fname}.mp4"
audio_fname = f"{media_dir}/{media_fname}.wav"
cap_fname = f"captures/{media_fname}_caps_001.json"

wf_temp = wave.open(audio_fname)
Fs = wf_temp.getframerate()
wf_temp.close()

power_thresh = 50

mic_diameter_inches = 5
mic_diameter_m = (5/12)*.3048
delay_max = (mic_diameter_m / 330)*Fs

audio_segments = preprocess_signal(audio_fname, power_thresh, window_len=.01)

with open(cap_fname) as f:
    video_segments = json.load(f)

cap = cv2.VideoCapture(video_fname)
video_fps = cap.get(cv2.CAP_PROP_FPS)
cap.release()
cv2.destroyAllWindows()

audio_detected_1plus = np.zeros(len(audio_segments.caps))
audio_detected_2plus = np.zeros(len(audio_segments.caps))
audio_detected_2plus = np.zeros(len(audio_segments.caps))

audio_indices = np.zeros(len(audio_segments.caps))
video_indices = np.zeros(len(video_segments))

# audio detected with no corresponding video
# audio detected once with corresponding video
# audio detected 2+ with corresponding video
# audio detected and not rejected once with corr. video
# audio detected and not rejected 2+ with corr. video
# audio detected and correctly labeled



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
            video_idx = video_segments.index(o)
            angle  = estimate_delay(sig_cap[0], sig_cap[1], delay_max)
            if angle is not None:
                audio_indices[cap_idx] += 1
                video_indices[video_idx] += 1

    cap_idx += 1

print(audio_indices)
print(video_indices)
