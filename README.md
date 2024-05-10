# Ping Pong Score Keeping

Finals project for NYU ECE 6183 - real time DSP.


## Running the code

There are three main programs that can be run: the realtime game, the signal capture demo, and the video playback scoreboard. Note that for the first two you need two microphones and an audio interface that can capture two channels at once. No packages outside of those used in class were used so requirements should be met already.

To run the main game (`pingpong_game/__main__.py`), make sure the audio interface with two channels is the default input and from the code repo (or wherever pingpong_game is stored) run:

`python -m pingpong_game`

To run the signal capture demo, make sure the audio interface with two channels is the default input and run:

`python -m pingpong_game.signal_capture_demo`

Both of these programs will produce a wave file output which can be used for post-processing and analysis.

To run the video playback version, make sure you have set the fields indicating the audio and video files in `pingpong_game/config.py` and then run:

`python -m pingpong_game.devtools.play_video`

Note that for this last program the results may vary as a side effect of the audio-video synchronization, see the notes in `pingpong_game/devtools/play_video.py` for more details.

In addition to these main programs, you might also want to run just the signal capture code on an audio file to see how it performs. This can be achieved by updating the input file at the bottom of `pingpong_game/sig/signal_capture.py` and then running:

`python -m pingpong_game.sig.signal_capture`

This will by default output the first 15 captures detected in the file, but the code can be taken and made into a full script if desired.


### Documentation

For more info, read the documentation at docs/doc.pdf
