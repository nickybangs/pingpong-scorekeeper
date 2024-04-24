class Event:
    # valid_events = ["contact_event","timeout"]
    def __init__(self, player, etype):
        self.player = player
        self.etype = etype

    def __str__(self):
        return "Event("+str(self.player)+", "+self.etype+")"

class GameEventState:
    def __init__(self, event):
        self.player = event.player
        self.event = event
        self.state_name = "GameEventState"

class ScoreState:
    def __init__(self, player):
        self.player = player
        self.state_name = "ScoreState"

class StartState:
    def __init__(self, player_one):
        self.player = player_one
        self.state_name = "StartState"

class EndState:
    def __init__(self):
        self.state_name = "EndState"

class ErrorState:
    def __init__(self, msg):
        self.state_name = "ErrorState"
        self.msg = msg

class GameState:
    def __init__(self, p1, p2):
        self.current_player = p1
        self.other_player = p2
        self.num_consecutive_events = 0

    def transition(self, current_state, event):
        if event.player.id != self.current_player.id:
            self.other_player = self.current_player
            self.current_player = event.player
            self.num_consecutive_events = 0

        if (
            current_state.state_name in ["StartState", "ScoreState"] and
            event.etype == "timeout"
        ):
            return ErrorState(msg="timed out waiting for serve")

        event_type = event.etype
        if event_type == "contact_event":
            self.num_consecutive_events += 1
            if self.num_consecutive_events > 2:
                return ScoreState(self.other_player)
            else:
                return GameEventState(event)
        elif event_type == "timeout":
            return ScoreState(self.other_player)

