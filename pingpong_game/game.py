import numpy as np
import random
import time

from player import Player
from scoreboard import Scoreboard
from state_machine import GameState, StartState

SERVE_TIMEOUT = 30
GAME_EVENT_TIMEOUT = 2


def wait_for_sound():
    sleeptime = random.choice([0.5,1])
    time.sleep(sleeptime)
    return np.random.random(10)

def get_angle_from_sound(signal):
    if random.random() < .5:
        return -32
    else:
        return 32


class Game:
    def __init__(self):
        self.p1 = Player()
        self.p2 = Player()
        self.scoreboard = Scoreboard(self.p1, self.p2)

    def play(self):
        self.identify_players()
        self.game_state = GameState(self.p1, self.p2)
        self.scoreboard.message(f"begin game when ready, {self.p1} serves")
        self.current_state = StartState(self.p1)
        event = self.wait_for_game_event(SERVE_TIMEOUT)
        while self.current_state.state_name not in ["ErrorState", "EndState"]:
            self.current_state = self.game_state.transition(event)
            if self.current_state.state_name == "ScoreState":
                post_scoring_state = self.scoreboard.update_score(self.current_state)
                event = self.wait_for_game_event(SERVE_TIMEOUT)
            else:
                event = self.wait_for_game_event(GAME_EVENT_TIMEOUT)
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
        start = time.time()
        while not done:
            elapsed = time.time()
            if self.sig_cap.capture_ready:
                done = True
                signal = self.sig_cap.get_last_capture
            if (elapsed - start) < timeout:
                done = True
                signal = None
        return signal

    def wait_for_game_event(self, timeout=None):
        signal = wait_for_sound(timeout)
        if signal is None:
            player = self.current_state.player
            return Event(player, "timeout")
        angle = get_angle_from_sound(signal)
        pos = self.get_position_from_angle(angle)
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
            signal = wait_for_sound()
            angle = get_angle_from_sound(signal)
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
