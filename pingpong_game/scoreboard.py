from pingpong_game.state_machine import ErrorState, EndState

class Scoreboard:
    def __init__(self, p1, p2):
        self.p1 = p1
        self.p2 = p2
        self.score = [0,0]
        self.points_to_win = 21
        self.win_by = 2

    def message(self, msg):
        print(msg)

    def confirm(self, msg):
        confirmed = False
        resp = None
        while not confirmed:
            yn = input(f"{msg} y/n ").lower()
            if yn == 'y':
                confirmed = True
                resp = True
            elif yn == 'n':
                confirmed = True
                resp = False
            else:
                confirmed = False
        return resp

    def input(self, prompt):
        resp = input(prompt)
        return resp

    def update_score(self, score_state):
        if score_state.player == self.p1:
            self.score[0] += 1
        elif score_state.player == self.p2:
            self.score[1] += 1
        else:
            return ErrorState(msg="invalid player passed to scoreboard")

        if (self.score[0] >= 21) and (self.score[1] <= 19):
            return EndState(self.p1)
        elif (self.score[1] >= 21) and (self.score[0] <= 19):
            return EndState(self.p2)
        else:
            return score_state
