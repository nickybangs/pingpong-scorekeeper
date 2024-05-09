# set up the config file used at runtime

config = dict()

# assume FS of 48 kHz, this required to get a decent number of samples for the delay between the two mics
Fs = 48_000

config["fs"] = Fs
# the signal capture window length determines the length of the signal used when determining if a sound had
# high enough power to count as an event, i.e. the RMS is found for each window of length .01 seconds, and if
# it is high enough it is added to the captured signal
config["sig_cap_window_len"] = int(.01*Fs)
# block length for the incoming signal, should be close to the signal capture window length,
# and should be an integer multiple if it is larger
config["signal_block_len"] = config["sig_cap_window_len"]*1
# minimum power required for each block to be added to a captured signal
config["sig_cap_power"] = 50
# max buffer size for the signal capture, no sonic events should be longer than a second so this gives plenty of buffer
config["max_sig_buffer_len"] = 5*Fs
# frequency bounds for the bandpass filter used to limit input signal to just ping-pong sounds
config["filter_low_thresh"] = 8_000
config["filter_high_thresh"] = 10_000
# how long the game will wait for the server
# default to a couple of minutes but this can be modified if that is too long
config["serve_timeout"] = 60*2
# how long after the last game event (e.g. a paddle strike) before timing out
# this is used to determine if for example the ball bounced on the table and was missed
# if enough time goes by without hearing a new sound, it was assumed to be a missed ball
# and a point is awarded to the other player
config["game_event_timeout"] = 2
# possible timeout after someone scores, this could allow for bounces to be ignored but currenty not used
config["post_scoring_timeout"] = 0
# distance between microphones in meters - in this case it is 5" / 12" times ft/m conversion
config["mic_diameter_m"] = (5/12)*.3048
# max delay in samples based on the distance between the microphones
config["delay_max"] = int((config["mic_diameter_m"]/340)*Fs)
# minimum mean power required for both channels in order to count as a real signal
# this is separated from the signal capture to allow for more control over what captures are kept
# also this can allow for other means of filtering out captures in the future - e.g. classification on incoming
# signals instead of using the mean power between the signals
config["mean_signal_power_min"] = 80
# pre-configured sign difference between the two mics. in my case the channels had opposite signs
# so i need to multiply one of the channels by -1 before processing. this assumption is checked when
# determing the players position in the calibration stage, and changed if the polarity is estimated to be the same
config["polarity"] = -1

# files used by video playback version

# src dir is the top level directory containing the entire project
src_dir = "/Users/nickybangs/home/gh/ece_6183_project"
config["audio_fname"] = f"{src_dir}/pingpong_game/devtools/media_files/pp_003.wav"
config["video_fname"] = f"{src_dir}/pingpong_game/devtools/media_files/pp_003.mp4"
