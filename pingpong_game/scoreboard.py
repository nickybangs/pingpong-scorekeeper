from functools import partial
import sys
import tkinter as Tk
from tkinter import messagebox, simpledialog
from threading import Thread

from pingpong_game.state_machine import ErrorState, EndState


def pause_stream(pause, stream):
    if pause.value == 0:
        pause.value = 1
        stream.stop_stream()
    else:
        pause.value = 0
        stream.start_stream()

def quit_stream(quit_, stream):
    quit_.value = 1
    stream.stop_stream()

class Scoreboard:
    def __init__(self, p1=None, p2=None):
        self.p1 = p1
        self.p2 = p2
        self.score = [0,0]
        self.points_to_win = 21
        self.win_by = 2

    def init_tk(self, pause, quit_, stream):
        root = Tk.Tk()
        root.geometry("300x330+1000+100")
        self.p1_str_var = Tk.StringVar(value="Player One")
        self.p1_score_var = Tk.StringVar(value="0")
        self.p2_str_var = Tk.StringVar(value="Player Two")
        self.p2_score_var = Tk.StringVar(value="0")

        playerone_label = Tk.Label(root, textvariable=self.p1_str_var)
        playerone_score = Tk.Label(root, textvariable=self.p1_score_var)
        playertwo_label = Tk.Label(root, textvariable=self.p2_str_var)
        playertwo_score = Tk.Label(root, textvariable=self.p2_score_var)

        self.quit = quit_
        self.pause = pause
        self.stream = stream
        pause_func = partial(pause_stream, pause, stream)
        quit_func = partial(quit_stream, quit_, stream)
        pause_button = Tk.Button(root, text="Pause/Resume", command=pause_func)
        quit_button = Tk.Button(root, text="Quit", command=quit_func)

        playerone_label.pack()
        playerone_score.pack()
        playertwo_label.pack()
        playertwo_score.pack()
        pause_button.pack()
        quit_button.pack()
        root.update()
        self.root = root

    def message(self, msg):
        is_paused = self.pause.value == 1
        if not is_paused:
            self.pause.value = 1
            self.stream.stop_stream()
        messagebox.showinfo(message=msg)
        if not is_paused:
            self.pause.value = 0
            self.stream.start_stream()

    def confirm(self, msg):
        '''
        confirm the promp with the user, pause the input stream while waiting
        '''
        is_paused = self.pause.value == 1
        if not is_paused:
            self.pause.value = 1
            self.stream.stop_stream()
        answer = messagebox.askquestion(message=msg)
        if answer == "yes":
            resp = True
        else:
            resp = False
        if not is_paused:
            self.pause.value = 0
            self.stream.start_stream()
        return resp

    def input(self, prompt):
        '''
        get an input from the user, pausing the input while waiting
        '''
        is_paused = self.pause.value == 1
        if not is_paused:
            self.pause.value = 1
            self.stream.stop_stream()
        answer = simpledialog.askstring('Input', prompt)
        if not is_paused:
            self.pause.value = 0
            self.stream.start_stream()
        return answer

    def update_score(self, score_state):
        if score_state.player == self.p1:
            self.score[0] += 1
        elif score_state.player == self.p2:
            self.score[1] += 1
        else:
            return ErrorState(msg="invalid player passed to scoreboard")

        print(self.score)
        if (self.score[0] >= 21) and (self.score[1] <= 19):
            return EndState(self.p1)
        elif (self.score[1] >= 21) and (self.score[0] <= 19):
            return EndState(self.p2)
        else:
            return score_state



if __name__ == "__main__":
    sb = Scoreboard()
    sb.init_tk()
    sb.root.update()
    sb.message("testing")
    sb.root.update()
    sb.root.quit()
