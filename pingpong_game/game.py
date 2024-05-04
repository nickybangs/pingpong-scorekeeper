import numpy as np
import random
import scipy
import time


from pingpong_game.config import config
from pingpong_game.player import Player
from pingpong_game.scoreboard import Scoreboard
from pingpong_game.state_machine import Event, GameState, StartState, EndState
from pingpong_game.sig.signal_capture import SignalCapture
from pingpong_game.sig.signal_tools import (
    get_angle_from_sound,
    get_rms,
    get_pingpong_filter,
    get_polarity,
)


mic_diameter_m = config["mic_diameter_m"]
DELAY_MAX = config["delay_max"]
MEAN_SIGNAL_ENERGY_MIN = config["mean_signal_energy_min"]


class Game:
    def __init__(self, sig_cap, scoreboard):
        self.p1 = Player(id=1)
        self.p2 = Player(id=2)
        self.scoreboard = scoreboard
        scoreboard.p1 = self.p1
        scoreboard.p2 = self.p2
        self.sig_cap = sig_cap

    def wait_for_sound(self, timeout=None):
        global condition
        # 1 hour timeout to simulate never timing out
        if timeout is None:
            timeout = 60*60

        sound_detected = False
        timed_out = False
        self.sig_cap.condition.acquire()

        while (not sound_detected) and (not timed_out) and (self.scoreboard.quit.value != 1):
            if self.sig_cap.capture_ready:
                s = e = time.time()
                capture_ready = True
            else:
                s = time.time()
                capture_ready = self.sig_cap.condition.wait(timeout)
                e = time.time()

            if capture_ready and (self.scoreboard.quit.value != 1) and (self.scoreboard.pause != 1):
                signal_cap = self.sig_cap.get_next_capture()
                self.sig_cap.condition.notify() # let producer know the capture has been consumed
                mean_rms = (get_rms(signal_cap[0])+ get_rms(signal_cap[1]))/2
                if (mean_rms > MEAN_SIGNAL_ENERGY_MIN):
                    sound_detected = True
                else:
                    print(f"capture rejected: {signal_cap[-1]}, {mean_rms=}")
                    timeout = timeout - (e-s)
            else:
                signal_cap = None
                timed_out = True

        self.sig_cap.condition.release()
        return signal_cap

    def wait_for_game_event(self, timeout=None):
        signal_cap = self.wait_for_sound(timeout)
        if signal_cap is None:
            player = self.current_state.player
            return Event(player, "timeout")

        lch, rch = signal_cap[0], signal_cap[1]
        indces = signal_cap[-1]
        angle = get_angle_from_sound(lch, rch, DELAY_MAX, "beamforming")
        pos = self.get_position_from_angle(angle)
        # print sound detection info to console
        print(pos, angle, round((get_rms(lch)+get_rms(rch))/2,2))
        if pos == self.p1.position:
            return Event(self.p1, "contact_event")
        else:
            return Event(self.p2, "contact_event")

    def get_position_from_angle(self, angle):
        if angle > 0:
            return "Left"
        else:
            return "Right"

    def get_player_name(self, player, default):
        if self.scoreboard.confirm(f"enter a name for {default}?"):
            name = self.scoreboard.input("enter player's name")
        else:
            name = default
        return name

    def identify_players(self):
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


if __name__ == "__main__":
    game = Game()
    game.start()
