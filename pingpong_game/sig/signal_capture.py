'''
    code implementing the signal capture logic. this code receives incoming audio data from two channels
    for each channel it reads the signal a block at a time according to the window_length passed to the
    constructor. if the incoming signal on either channel has high enough power (higher than the
    power_thresh argument) that block is added to the current capture. the current capture is built up
    additively for each block with enough power. once a block is reach without enough power the current
    capture is stopped, the whole captured signal is added to the list of captures, a flag is set indicating
    a new capture is ready, and if requested a notification is sent to any waiting semaphores
'''
import json
import logging
import numpy as np
from scipy import signal
from threading import Condition

from pingpong_game.config import config
from pingpong_game.sig.signal_tools import (
    get_angle_from_sound,
    get_pingpong_filter,
    get_rms,
    load_signal,
)


log = logging.getLogger()


class SignalCapture:
    def __init__(self, window_len, power_thresh, max_capture_len, padding=50, use_lock=True):
        # smallest window length for each block - typically .01 seconds
        self.window_len = int(window_len)
        # max capture length - used as the size of the circular buffer used to record the incoming signal
        self.max_capture_len = max_capture_len
        # power threshold that each block must pass in order to be added to the current capture
        self.power_thresh = power_thresh
        # buffers for each channel
        self.l_sig_buffer = np.zeros(max_capture_len)
        self.r_sig_buffer = np.zeros(max_capture_len)
        # current write index for the buffers
        self.w_idx = 0
        # the max index of the buffer for the current capture
        self.max_idx = 0
        # the min index of the buffer for the current capture
        self.min_idx = 0
        # the signal-specific index for the capture boundaries
        # only relevant if an offset is passed in by the caller
        # used to help locate the capture in the original signal
        self.signal_start_idx = 0
        self.signal_stop_idx = 0
        # padding added to either side of the capture set to a little more than the max delay in samples
        # used to make sure both signals have all the relevant data to determine the delay
        self.padding = padding
        # flag indicating whether the object is currently capturing a signal or not
        # this will be True as long as incoming blocks continue to have power higher than power_thresh
        self.capturing_signal = False
        # flag set whenever a capture is ready to be consumed
        self.capture_ready = False
        # list of captures that are ready and have not yet been consumed
        self.caps = []
        # list of consumed captures - useful for saving the captures after processing
        self.consumed_caps = []
        # flag indicating if the lock/semaphore mechanism is being used by the consumer
        self.use_lock = use_lock
        if use_lock:
            # condition variable that can be waited on by any consumers
            # which the sig_cap will notify after a new capture isr ead
            self.condition = Condition()
        # flag to control whether the processing function should actually
        # perform a capture on incoming signal. sometimes will be set to False by consumer
        # when audio data should be ignored
        self.do_capture = True

    def clear_captures(self):
        '''
        function to clear all current captures. this is useful if the game is paused and
        we want to make sure any captures after the pause aren't stale
        '''
        self.caps = []
        self.capture_ready = False
        self.capturing_signal = False

    def get_next_capture(self):
        '''
        code to return the next capture in the capture list
        if the captured list is empty the capture ready flag is set to false
        '''
        capture = self.caps.pop(0)
        self.consumed_caps.append(capture)
        if len(self.caps) == 0:
            self.capture_ready = False
        return capture

    def save(self, fname):
        '''
        saves the captures in both the capture list and the consumed capture list to json
        '''
        all_caps = list(self.consumed_caps) + list(self.caps)
        for cap in all_caps:
            cap[0] = list(cap[0])
            cap[1] = list(cap[1])
        with open(fname, 'w') as f:
            f.write(json.dumps(all_caps, indent=4))

    def process(self, lsig, rsig, frame_offset=0):
        '''
        iterates over both incoming signals checking if each block has high enough power
        updates the captures and the currently-capturing state as processing occurs
        '''
        # get input block length from signal
        # NOTE this is assumed to be an integer multiple of the window length and shouldn't be too large
        # in order for processing to work as expected
        block_len = len(lsig)
        # get buffer boundaries based on current write index and block length
        lb, ub = self.w_idx, self.w_idx+block_len

        # make sure input signals are np arrays of the correct type
        lsig = np.array(lsig).astype(np.int32)
        rsig = np.array(rsig).astype(np.int32)

        # copy input signals to respective circular buffers
        self.l_sig_buffer[lb:ub] = lsig.copy()
        self.r_sig_buffer[lb:ub] = rsig.copy()

        # iterate through blocks of size window_len, checking if each block has enough power
        for i in range(int(block_len/self.window_len)):
            block_lb, block_ub = i*self.window_len, (i+1)*self.window_len
            lblock = lsig[block_lb:block_ub]
            rblock = rsig[block_lb:block_ub]
            # initialize variable to False, it is set to True if signals have low power
            # or if signal length threshold is met (unexpected behavior)
            stop_cap = False

            # get the rms of each block
            lrms = get_rms(lblock)
            rrms = get_rms(rblock)

            # get the minimum rms allowable
            min_rms = self.power_thresh

            # if either rms is above the min, we will consider it a valid candidate capture
            if (lrms > min_rms) or (rrms > min_rms):
                # if we are already capturing a signal
                # add this block's index to the upper bound of the capture
                if self.capturing_signal:
                    self.max_idx = self.w_idx + block_ub
                    self.signal_stop_idx = frame_offset + block_ub
                    cap_len = self.max_idx - self.min_idx
                    # if we have exceeded the max length, stop capturing and log a warning
                    if cap_len >= self.max_capture_len:
                        log.warning(
                            f"captured signal length exceeded max allowable signal: {cap_len=}"
                        )
                        stop_cap = True
                # else if we arent already capturing, set up a new capture
                else:
                    # initialize capture boundaries
                    self.min_idx = self.w_idx + block_lb
                    self.max_idx = self.w_idx + block_ub
                    self.signal_start_idx = frame_offset + block_lb
                    self.signal_stop_idx = frame_offset + block_ub
                    # set the currently capturing flag to True
                    self.capturing_signal = True
                    log.debug(f"starting signal capture at index {self.signal_start_idx}")
            # else if neither rms is high enough, stop capturing
            else:
                stop_cap = True

            # if we reached a stop capture condition *and* we were in fact doing a capture
            # then finalize the capture and add it to the list of captures
            if stop_cap and self.capturing_signal:
                # get correct indices for circular buffer
                lb_idx = (self.min_idx - self.padding) % self.max_capture_len
                ub_idx = (self.max_idx + self.padding) % self.max_capture_len
                # get correct signal depending on if we wrapped around the circular buffer
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
                # if we the consumer has indicated that we should do a capture, add the capture
                # to the list of captures and set the capture ready flag
                if self.do_capture:
                    self.caps.append(
                        [
                            l_signal.copy(),
                            r_signal.copy(),
                            (self.signal_start_idx, self.signal_stop_idx),
                        ]
                    )
                    self.capture_ready = True
                    # if the consumer is using the semaphore mechanism, notify
                    if self.use_lock:
                        self.condition.notify()
                # reset any capture state
                self.capturing_signal = False
                self.min_idx = 0
                self.max_idx = 0
                self.signal_start_idx = 0
                self.signal_stop_idx = 0
        # update circular buffer index
        self.w_idx = (self.w_idx + block_len) % self.max_capture_len


def preprocess_signal(fname, power=50, window_len=.01*48_000):
    '''
    preprocess a signal loaded from a wave file. this code runs the signal capture processoer
    as if the signal was being processed in real time. it is used for debugging, testing and validation
    '''
    [lch, rch, Fs] = load_signal(fname)
    rch = rch*config["polarity"]

    # filter each signal before processing
    filter_low_thresh = config["filter_low_thresh"]
    filter_high_thresh = config["filter_high_thresh"]
    K = 6
    [b,a] = get_pingpong_filter(low=filter_low_thresh, high=filter_high_thresh, Fs=Fs, K=K)
    lch = signal.lfilter(b,a,lch)
    rch = signal.lfilter(b,a,rch)

    sig_cap = SignalCapture(
        window_len=window_len,
        power_thresh=power,
        max_capture_len=5*Fs,
        use_lock=False,
    )

    # iterate over blocks of size window_len and process the input
    sig_cap.Fs = Fs
    block_len = int(1*window_len)
    for i in range(int(len(lch)/block_len)):
        frame_offset = i*block_len
        sig_cap.process(
            lch[i*block_len : (i+1)*block_len],
            rch[i*block_len : (i+1)*block_len],
            frame_offset=frame_offset,
        )
    return sig_cap


if __name__ == "__main__":
    '''
    run the signal capture processor on an input wave file using the preprocess function
    print first N=15 captures to console
    '''
    from matplotlib import pyplot
    fname = 'pingpong_game/devtools/media_files/pp_003.wav'
    N = 15
    sig_cap = preprocess_signal(fname)
    Fs = sig_cap.Fs
    mic_diameter_inches = 5
    mic_diameter_m = (5/12)*.3048
    delay_max = int((mic_diameter_m / 340)*Fs)
    for i,cap in enumerate(sig_cap.caps[:N]):
        lch = cap[0]
        rch = cap[1]
        print(f"{i}: {get_angle_from_sound(lch, rch, delay_max, 'beamforming')} {cap[-1]}, {len(lch)}")
