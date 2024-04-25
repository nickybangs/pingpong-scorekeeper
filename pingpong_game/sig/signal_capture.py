import json
import logging
import numpy as np
from scipy import signal
from threading import Condition

from pingpong_game.sig.signal_tools import load_signal, get_rms, get_angle_from_sound

log = logging.getLogger()


class SignalCapture:
    def __init__(self, window_len, energy_thresh, max_capture_len, padding=50):
        self.window_len = int(window_len)
        self.max_capture_len = max_capture_len
        self.energy_thresh = energy_thresh
        self.l_sig_buffer = np.zeros(max_capture_len)
        self.r_sig_buffer = np.zeros(max_capture_len)
        self.w_idx = 0
        self.max_idx = 0
        self.min_idx = 0
        self.signal_start_idx = 0
        self.signal_stop_idx = 0
        self.padding = padding
        self.capturing_signal = False
        self.capture_ready = False
        self.caps = []
        self.consumed_caps = []
        self.condition = Condition()
        self.do_capture = True

    def clear_captures(self, i=None):
        self.caps = []
        self.capture_ready = False
        self.capturing_signal = False

    def get_next_capture(self):
        capture = self.caps.pop(0)
        self.consumed_caps.append(capture)
        if len(self.caps) == 0:
            self.capture_ready = False
        return capture

    def save(self, fname):
        all_caps = list(self.consumed_caps) + list(self.caps)
        for cap in all_caps:
            cap[0] = list(cap[0])
            cap[1] = list(cap[1])
        with open(fname, 'w') as f:
            f.write(json.dumps(all_caps, indent=4))

    def process(self, lsig, rsig, frame_offset=0):
        block_len = len(lsig)
        lb, ub = self.w_idx, self.w_idx+block_len
        #print(f"block lb: {lb}, block ub: {ub}")

        lsig = np.array(lsig).astype(np.int32)
        rsig = np.array(rsig).astype(np.int32)

        self.l_sig_buffer[lb:ub] = lsig
        self.r_sig_buffer[lb:ub] = rsig

        for i in range(int(block_len/self.window_len)):
            block_lb, block_ub = i*self.window_len, (i+1)*self.window_len
            #print(f"window lb: {block_lb}, window ub: {block_ub}")
            lblock = lsig[block_lb:block_ub]
            rblock = rsig[block_lb:block_ub]
            stop_cap = False

            lrms = get_rms(lblock)
            rrms = get_rms(rblock)

            min_rms = self.energy_thresh

            if (lrms > min_rms) or (rrms > min_rms):
            #if ((lrms + rrms)/2) > min_rms:
                if self.capturing_signal:
                    self.max_idx = self.w_idx + block_ub
                    self.signal_stop_idx = frame_offset + block_ub
                    cap_len = self.max_idx - self.min_idx
                    if cap_len >= self.max_capture_len:
                        log.warning(
                            f"captured signal length exceeded max allowable signal: {cap_len=}"
                        )
                        stop_cap = True
                else:
                    self.min_idx = self.w_idx + block_lb
                    self.max_idx = self.w_idx + block_ub
                    self.signal_start_idx = frame_offset + block_lb
                    self.signal_stop_idx = frame_offset + block_ub
                    self.capturing_signal = True
                    log.debug(f"starting signal capture at index {self.signal_start_idx}")
            else:
                stop_cap = True

            if stop_cap and self.capturing_signal:
                lb_idx = (self.min_idx - self.padding) % self.max_capture_len
                ub_idx = (self.max_idx + self.padding) % self.max_capture_len
                if lb_idx > ub_idx:
                    l_signal = np.concatenate(
                        (
                            self.l_sig_buffer[lb_idx:],
                            self.l_sig_buffer[:ub_idx]
                        )
                    )
                    r_signal = np.concatenate(
                        (
                            self.r_sig_buffer[lb_idx:],
                            self.r_sig_buffer[:ub_idx]
                        )
                    )
                else:
                    l_signal = self.l_sig_buffer[lb_idx:ub_idx]
                    r_signal = self.r_sig_buffer[lb_idx:ub_idx]
                if self.do_capture:
                    self.caps.append(
                        [
                            l_signal.copy(),
                            r_signal.copy(),
                            (self.signal_start_idx, self.signal_stop_idx),
                        ]
                    )
                    self.capture_ready = True
                    self.condition.notify()
                self.capturing_signal = False
                self.min_idx = 0
                self.max_idx = 0
                self.signal_start_idx = 0
                self.signal_stop_idx = 0
        self.w_idx = (self.w_idx + block_len) % self.max_capture_len


def preprocess_signal(fname, energy=50, window_len=.01):
    [lch, rch, Fs] = load_signal(fname)
    rch = rch*-1

    fcl = 2 * (8_000/Fs) # was 100
    fch = 2 * (10_000/Fs)
    fc = [fcl, fch]
    K = 6
    [b,a] = signal.cheby1(K, .5, fc, 'bandpass')
    lch = signal.lfilter(b,a,lch)
    rch = signal.lfilter(b,a,rch)

    sig_cap = SignalCapture(
        window_len=window_len*Fs,
        energy_thresh=energy,
        max_capture_len=5*Fs,
    )

    sig_cap.condition.acquire()
    sig_cap.Fs = Fs
    block_len = int(.5*Fs)
    block_len = int(1*window_len*Fs)
    for i in range(int(len(lch)/block_len)):
        frame_offset = i*block_len
        sig_cap.process(
            lch[i*block_len : (i+1)*block_len],
            rch[i*block_len : (i+1)*block_len],
            frame_offset=frame_offset,
        )
        #_ = input()
    return sig_cap


if __name__ == "__main__":
    from matplotlib import pyplot
    fname = 'pingpong_game/devtools/media_files/pp_003.wav'
    sig_cap = preprocess_signal(fname)
    Fs = sig_cap.Fs
    mic_diameter_inches = 5
    mic_diameter_m = (5/12)*.3048
    delay_max = int((mic_diameter_m / 340)*Fs)
    print(Fs)
    print(delay_max)
    for i,cap in enumerate(sig_cap.caps[:15]):
        lch = cap[0]
        rch = cap[1]
        print(f"{i}: {get_angle_from_sound(lch, rch, delay_max, 'beamforming')} {cap[-1]}, {len(lch)}")
