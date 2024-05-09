'''
    Classes needed for the game state machine.
    See the documentation for the general flow of the states.
'''

# game event - expected to have a player and event type associated with it
class Event:
    def __init__(self, player, etype):
        self.player = player
        self.etype = etype

    def __str__(self):
        return "Event("+str(self.player)+", "+self.etype+")"

# state used when the event that occurs is a ping pong in-game event
# e.g. a paddle strike or a table strike
class GameEventState:
    def __init__(self, event):
        self.player = event.player
        self.event = event
        self.state_name = "GameEventState"

# state used when the previous event either resulted in a timeout
# or when multiple in game events occur on the same side of the table
# e.g. the ball bounces twice on the table and then gets hit by the player
class ScoreState:
    def __init__(self, player):
        self.player = player
        self.state_name = "ScoreState"

# state used at the beginning of the game or after the pause button has been pressed
class StartState:
    def __init__(self, player_one):
        self.player = player_one
        self.state_name = "StartState"

# state used when the scoreboard detects that one player has won
class EndState:
    def __init__(self):
        self.state_name = "EndState"

# state used whenever an error occurs, this includes a timeout that happens
# while waiting for the server or other unexpected events
class ErrorState:
    def __init__(self, msg):
        self.state_name = "ErrorState"
        self.msg = msg

# state machine logic used to transition from one state to the next
# based on the input event. see documenation for details
class GameState:
    def __init__(self, p1, p2):
        self.current_player = p1
        self.other_player = p2
        self.num_consecutive_events = 0

    def transition(self, current_state, event):
        # if the new state is a different player from the previous state
        # change relevant player info and reset consecutive event counter
        if event.player.id != self.current_player.id:
            self.other_player = self.current_player
            self.current_player = event.player
            self.num_consecutive_events = 0

        # if the event is a timeout while waiting for the server,
        # this is considered to be an error
        if (
            current_state.state_name in ["StartState", "ScoreState"] and
            event.etype == "timeout"
        ):
            return ErrorState(msg="timed out waiting for serve")

        # if the event type is a ping-pong game event, increment the number
        # of consecutive events. check if scorestate conditions are met
        # if a timeout occurs, award a point to the other player
        event_type = event.etype
        if event_type == "contact_event":
            self.num_consecutive_events += 1
            if self.num_consecutive_events > 2:
                # reset event counter
                self.num_consecutive_events = 0
                return ScoreState(self.other_player)
            else:
                return GameEventState(event)
        elif event_type == "timeout":
            return ScoreState(self.other_player)

