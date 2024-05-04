"""
Game class - used to store main mechanisms used for the pingpong game
"""
import time

from pingpong_game.config import config
from pingpong_game.player import Player
from pingpong_game.state_machine import Event
from pingpong_game.sig.signal_tools import (
    get_angle_from_sound,
    get_rms,
    get_polarity,
)

# config values explained in config.py and at relevant parts of code
DELAY_MAX = config["delay_max"]
MEAN_SIGNAL_ENERGY_MIN = config["mean_signal_energy_min"]


class Game:
    def __init__(self, sig_cap, scoreboard):
        '''
        initialize a new game with new player objects
        requires a signal capture object which can send events whenever a new signal is captured
        as well as a scoreboard object which is used to communicate with players
        '''
        self.p1 = Player(id=1)
        self.p2 = Player(id=2)
        self.scoreboard = scoreboard
        scoreboard.p1 = self.p1
        scoreboard.p2 = self.p2
        self.sig_cap = sig_cap

    def wait_for_sound(self, timeout=None):
        '''
        wait for a new signal detected event to occur.
        the process is notified by the sig_cap.condition semaphore which is acquired here
        and waited on until the sig_cap object sends a notification, at which point the captured
        sound is parsed to get the relevant game information
        '''
        # 1 hour timeout to simulate never timing out
        if timeout is None:
            timeout = 60*60

        sound_detected = False
        timed_out = False
        self.sig_cap.condition.acquire()

        while (not sound_detected) and (not timed_out) and (self.scoreboard.quit.value != 1):
            # if the sig_cap already has a capture ready, don't need to wait for a notification
            if self.sig_cap.capture_ready:
                s = e = time.time()
                capture_ready = True
            else:
                s = time.time()
                # aside from the sig_cap object, the game processing loop can send a notification
                # if for example the quit or pause buttons have been pressed. that will cause this
                # code to stop waiting and ultimately return control to the main thread
                capture_ready = self.sig_cap.condition.wait(timeout)
                e = time.time()

            # check if captured signal meets criteria for a valid capture. right now this just means
            # checking if it has high enough mean energy between the channels, but future improvements
            # could change this to classify the signal as a table/paddle strike vs a floor bounce, etc
            if capture_ready and (self.scoreboard.quit.value != 1) and (self.scoreboard.pause != 1):
                signal_cap = self.sig_cap.get_next_capture()
                self.sig_cap.condition.notify() # let producer know the capture has been consumed
                mean_rms = (get_rms(signal_cap[0])+ get_rms(signal_cap[1]))/2
                if (mean_rms > MEAN_SIGNAL_ENERGY_MIN):
                    sound_detected = True
                else:
                    # print that the capture was rejected (for debugging) and update the timeout
                    # to reflect how much time remains before the timeout expires
                    print(f"capture rejected: {signal_cap[-1]}, {mean_rms=}")
                    timeout = timeout - (e-s)
            else:
                # if timed out, set the captured signal to None and indicate that a time out occurred
                signal_cap = None
                timed_out = True

        # release the semaphore while no longer waiting for a sound
        self.sig_cap.condition.release()
        return signal_cap

    def wait_for_game_event(self, timeout=None):
        '''
        wait for a captured sound or timeout. if a sound is detected,
        estimate the angle and use the angle to determine which side the sound came from
        return a contact event according to the side, i.e. the side the player is on
        '''
        signal_cap = self.wait_for_sound(timeout)
        if signal_cap is None:
            player = self.current_state.player
            return Event(player, "timeout")

        # get signal info from the signal capture received
        # signal captures are of the form (left_ch_signal, right_ch_signal, signal_indices)
        lch, rch = signal_cap[0], signal_cap[1]
        indces = signal_cap[-1]
        angle = get_angle_from_sound(lch, rch, DELAY_MAX, "beamforming")
        pos = self.get_position_from_angle(angle)
        # print sound detection info to console for debugging
        print(pos, angle, round((get_rms(lch)+get_rms(rch))/2,2))
        if pos == self.p1.position:
            return Event(self.p1, "contact_event")
        else:
            return Event(self.p2, "contact_event")

    def get_position_from_angle(self, angle):
        '''
        determine side of table from angle
        0 to 90 degrees -> left side
        -0 to -90 degrees -> right side
        '''
        if angle > 0:
            return "Left"
        else:
            return "Right"

    def get_player_name(self, player, default):
        """
        use the scoreboard object to get the current player's name
        """
        if self.scoreboard.confirm(f"enter a name for {default}?"):
            name = self.scoreboard.input("enter player's name")
        else:
            name = default
        return name

    def identify_players(self):
        """
        get the name for each player, get the position for each player by having
        them bounce the ball on their paddles.
        update the polarity of the signals if necessary (i.e. change the sign difference between
        them if they don't seem to have opposite signs)
        """
        self.scoreboard.pause.value = 1
        self.p1.name = self.get_player_name(self.p1, "Player One")
        self.p2.name = self.get_player_name(self.p2, "Player Two")
        self.scoreboard.pause.value = 0
        self.scoreboard.p1_str_var.set(self.p1.name)
        self.scoreboard.p2_str_var.set(self.p2.name)

        done = False
        current_player = self.p1
        while not done:
            self.scoreboard.message(f"{current_player.name}: bounce the ball on your paddle")
            self.scoreboard.root.update()
            self.scoreboard.pause.value = 0
            signal_cap = self.wait_for_sound()
            lch, rch = signal_cap[0], signal_cap[1]
            angle = get_angle_from_sound(lch, rch, DELAY_MAX, "beamforming")
            pos = self.get_position_from_angle(angle)
            player_pos_msg = (
                f"it seems that {current_player.name} is on the {pos} side of the table, is this correct?"
            )
            angle_correct = self.scoreboard.confirm(player_pos_msg)
            if angle_correct:
                current_player.position = pos
                if (current_player == self.p2):
                    done = True
                else:
                    current_player = self.p2
            else:
                # if angle wasn't correct, it is possible the default polarity
                # is wrong, in which case this will estimate it and update
                polarity = get_polarity(lch, rch)
                if polarity == config["polarity"]:
                    print('estimated polarity matches config value, no update needed')
                else:
                    print('estimated polarity is different from config value, updating')
                    config["polarity"] = polarity
