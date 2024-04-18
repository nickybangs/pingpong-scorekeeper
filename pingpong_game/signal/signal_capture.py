import logging
import numpy as np
from scipy import signal

from pingpong_game.signal.signal_tools import load_signal, get_rms

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

    def get_last_capture(self):
        capture = self.caps.pop()
        if len(self.caps) == 0:
            self.capture_ready = False
        return capture

    def process(self, lsig, rsig, frame_offset=0):
        block_len = len(lsig)
        lb, ub = self.w_idx, self.w_idx+block_len

        lsig = np.array(lsig).astype(np.int32)
        rsig = np.array(rsig).astype(np.int32)

        self.l_sig_buffer[lb:ub] = lsig
        self.r_sig_buffer[lb:ub] = rsig

        for i in range(int(block_len/self.window_len)):
            block_lb, block_ub = i*self.window_len, (i+1)*self.window_len
            lblock = lsig[block_lb:block_ub]
            rblock = rsig[block_lb:block_ub]
            stop_cap = False

            lrms = get_rms(lblock)
            rrms = get_rms(rblock)

            min_rms = self.energy_thresh

            if (lrms > min_rms) or (rrms > min_rms):
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
                self.caps.append(
                    [
                        l_signal.copy(),
                        r_signal.copy(),
                        (self.signal_start_idx, self.signal_stop_idx),
                    ]
                )
                self.capturing_signal = False
                self.capture_ready = True
                self.min_idx = 0
                self.max_idx = 0
                self.signal_start_idx = 0
                self.signal_stop_idx = 0
        self.w_idx = (self.w_idx + block_len) % self.max_capture_len


def preprocess_signal(fname, energy=50, window_len=.01):
    [lch, rch, Fs] = load_signal(fname)

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
    sig_cap.Fs = Fs
    block_len = 5*Fs
    for i in range(int(len(lch)/block_len)):
        frame_offset = i*block_len
        sig_cap.process(
            lch[i*block_len : (i+1)*block_len],
            rch[i*block_len : (i+1)*block_len],
            frame_offset=frame_offset,
        )
    return sig_cap


if __name__ == "__main__":
    from matplotlib import pyplot
    fname = 'media_files/ping_pong_002.wav'
    sig_cap = preprocess_signal(fname)
    Fs = sig_cap.Fs
    start_lines = []
    end_lines = []
    for cap in sig_cap.caps:
        start_lines.append(cap[-1][0])
        end_lines.append(cap[-1][1])
        #print(cap[-1][0], cap[-1][1])
        print(cap[-1][0]/(Fs), cap[-1][1]/(Fs))
        print(30*cap[-1][0]/(Fs), 30*cap[-1][1]/(Fs))
        print()
    # pyplot.vlines(start_lines, ymin=-1_000, ymax=1_000, color='r')
    # pyplot.vlines(end_lines, ymin=-1_000, ymax=1_000, color='g')
    # pyplot.plot(lch)
    # pyplot.plot(rch+100)
    # pyplot.show()
