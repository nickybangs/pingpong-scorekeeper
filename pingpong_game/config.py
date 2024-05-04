config = dict()

Fs = 48_000

config["fs"] = Fs
config["sig_cap_window_len"] = int(.01*Fs)
config["signal_block_len"] = config["sig_cap_window_len"]*1
config["sig_cap_energy"] = 50
config["max_sig_buffer_len"] = 5*Fs
config["filter_low_thresh"] = 8_000
config["filter_high_thresh"] = 10_000
config["serve_timeout"] = 60*60
config["game_event_timeout"] = 2
config["post_scoring_timeout"] = 0
config["mic_diameter_m"] = (5/12)*.3048
config["delay_max"] = int((config["mic_diameter_m"]/340)*Fs)
config["mean_signal_energy_min"] = 80
config["polarity"] = -1
