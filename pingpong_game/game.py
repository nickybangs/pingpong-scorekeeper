import numpy as np
import random
import scipy
import time

from pingpong_game.player import Player
from pingpong_game.scoreboard import Scoreboard
from pingpong_game.state_machine import Event, GameState, StartState

from pingpong_game.signal.signal_capture import SignalCapture
from pingpong_game.signal.signal_tools import get_angle_from_sound, get_pingpong_filter

SERVE_TIMEOUT = 30
GAME_EVENT_TIMEOUT = 2
Fs = 48_000
SIG_CAP_WINDOW_LEN = int(.01*Fs)
SIG_CAP_ENERGY = 30
MAX_SIG_BUFFER_LEN = 5*Fs

mic_diameter_inches = 5
mic_diameter_m = (5/12)*.3048
DELAY_MAX = int((mic_diameter_m / 340)*Fs)


class Game:
    def __init__(self, signal):
        self.p1 = Player()
        self.p2 = Player()
        self.scoreboard = Scoreboard(self.p1, self.p2)
        self.signal = signal
        Fs = self.signal.rate
        [b,a] = get_pingpong_filter(low=8000, high=10000, Fs=Fs)
        self.filter = [b,a]
        self.sig_cap = SignalCapture(SIG_CAP_WINDOW_LEN, SIG_CAP_ENERGY, MAX_SIG_BUFFER_LEN)

    def play_test(self):
        self.game_state = GameState(self.p1, self.p2)
        self.current_state = StartState(self.p1)
        for i in range(10):
            event = self.wait_for_game_event(SERVE_TIMEOUT)
            print(event)

    def play(self):
        self.identify_players()
        self.game_state = GameState(self.p1, self.p2)
        self.scoreboard.message(f"begin game when ready, {self.p1} serves")
        self.current_state = StartState(self.p1)
        event = self.wait_for_game_event(SERVE_TIMEOUT)
        self.current_state = self.game_state.transition(self.current_state, event)
        while self.current_state.state_name not in ["ErrorState", "EndState"]:
            if self.current_state.state_name == "ScoreState":
                post_scoring_state = self.scoreboard.update_score(self.current_state)
                event = self.wait_for_game_event(SERVE_TIMEOUT)
            else:
                event = self.wait_for_game_event(GAME_EVENT_TIMEOUT)
            self.current_state = self.game_state.transition(self.current_state, event)
        if self.current_state.state_name == "ErrorState":
            err_msg = self.current_state.msg
            self.scoreboard.message(f"something went wrong, error message: {err_msg}")
            return
        if self.current_state.state_name != "EndState":
            self.scoreboard.message(f"unexpected end state: {self.current_state.state_name}")
            return
        winning_player = self.current_state.player
        if winning_player == self.p1:
            w_score, l_score = self.scoreboard.score
        else:
            l_score, w_score = self.scoreboard.score
        self.scoreboard.message(f"{winning_player} wins {w_score} to {l_score}")

    def wait_for_sound(self, timeout=None):
        # 1 hour timeout to simulate never timing out
        if timeout is None:
            timeout = 60*60

        done = False
        [b,a] = self.filter
        start = time.time()
        while not done:
            elapsed = time.time()
            x = self.signal.read(SIG_CAP_WINDOW_LEN)
            lch = x[::2]
            rch = x[1::2]
            # lch = x
            # rch = x
            lch = scipy.signal.lfilter(b,a,lch)
            rch = scipy.signal.lfilter(b,a,rch)
            self.sig_cap.process(lch, rch)
            if self.sig_cap.capture_ready:
                done = True
                signal_cap = self.sig_cap.get_last_capture()
            if (elapsed - start) > timeout:
                done = True
                signal_cap = None
        return signal_cap

    def wait_for_game_event(self, timeout=None):
        signal_cap = self.wait_for_sound(timeout)
        if signal_cap is None:
            player = self.current_state.player
            return Event(player, "timeout")
        lch, rch = signal_cap[0], signal_cap[1]
        angle = get_angle_from_sound(lch, rch, DELAY_MAX)
        pos = self.get_position_from_angle(angle)
        print(pos)
        if pos == self.p1.position:
            return Event(self.p1, "contact_event")
        else:
            return Event(self.p2, "contact_event")

    def get_position_from_angle(self, angle):
        if angle < 0:
            return "Left"
        else:
            return "Right"

    def get_player_name(self, player, default):
        if self.scoreboard.confirm(f"enter a name for {default}?"):
            name = self.scoreboard.input("name: ")
        else:
            name = default
        return name

    def identify_players(self):
        done = False
        self.p1.name = self.get_player_name(self.p1, "Player One")
        self.p2.name = self.get_player_name(self.p2, "Player Two")

        current_player = self.p1
        while not done:
            self.scoreboard.message(f"{current_player}: bounce the ball on your paddle")
            signal_cap = self.wait_for_sound()
            lch, rch = signal_cap[0], signal_cap[1]
            angle = get_angle_from_sound(lch, rch, DELAY_MAX)
            pos = self.get_position_from_angle(angle)
            player_pos_msg = (
                f"it seems that {current_player} is on the {pos} side of the table, is this correct?"
            )
            angle_correct = self.scoreboard.confirm(player_pos_msg)
            if angle_correct:
                current_player.position = pos
                if (current_player == self.p2):
                    done = True
                else:
                    current_player = self.p2


if __name__ == "__main__":
    game = Game()
    game.start()
