from functools import partial
import sys
import tkinter as Tk
from tkinter import messagebox, simpledialog
from threading import Thread

from pingpong_game.state_machine import ErrorState, EndState


LEFT_ARROW = b'\xe2\x87\x90'.decode()
UP_ARROW = b'\xe2\x87\x91'.decode()
RIGHT_ARROW = b'\xe2\x87\x92'.decode()
DOWN_ARROW = b'\xe2\x87\x93'.decode()

def pause_stream(pause):
    if pause.value == 0:
        pause.value = 1
    else:
        pause.value = 0

def quit_stream(quit_):
    quit_.value = 1

class Scoreboard:
    def __init__(self, p1=None, p2=None):
        self.p1 = p1
        self.p2 = p2
        self.serving = self.p1
        self.score = [0,0]
        self.points_to_win = 21
        self.win_by = 2

    def set_server(self, pos):
        if pos == "Left":
            self.serving_arrow_label.set(LEFT_ARROW)
        else:
            self.serving_arrow_label.set(RIGHT_ARROW)

    def init_tk(self, pause, quit_):
        root = Tk.Tk()
        root.geometry("330x330+1000+100")
        self.p1_str_var = Tk.StringVar(value="Player One")
        self.p1_score_var = Tk.StringVar(value="0")
        self.p2_str_var = Tk.StringVar(value="Player Two")
        self.p2_score_var = Tk.StringVar(value="0")
        serving_str = Tk.StringVar(value=LEFT_ARROW)

        playerone_label = Tk.Label(root, textvariable=self.p1_str_var,font=("Arial", 20))
        playerone_score = Tk.Label(root, textvariable=self.p1_score_var,font=("Arial", 15))
        playertwo_label = Tk.Label(root, textvariable=self.p2_str_var,font=("Arial", 20))
        playertwo_score = Tk.Label(root, textvariable=self.p2_score_var,font=("Arial", 15))
        empty_label = Tk.Label(root, text="")
        serving_label = Tk.Label(root, text="Now Serving", font=("Arial", 15))
        serving_arrow_label = Tk.Label(root, textvariable=serving_str, font=("Arial",15))

        adjust_p1_label = Tk.Label(root, text="Adjust Score",font=("Arial", 15))
        adjust_p2_label = Tk.Label(root, text="Adjust Score",font=("Arial", 15))

        p1_adjust_up = partial(self.adjust_score, 'p1', 'up')
        p1_adjust_down = partial(self.adjust_score, 'p1', 'down')
        p2_adjust_up = partial(self.adjust_score, 'p2', 'up')
        p2_adjust_down = partial(self.adjust_score, 'p2', 'down')

        adjust_p1_up_button = Tk.Button(root, text=UP_ARROW, command=p1_adjust_up)
        adjust_p1_down_button = Tk.Button(root, text=DOWN_ARROW, command=p1_adjust_down)
        adjust_p2_up_button = Tk.Button(root, text=UP_ARROW, command=p2_adjust_up)
        adjust_p2_down_button = Tk.Button(root, text=DOWN_ARROW, command=p2_adjust_down)

        self.quit = quit_
        self.pause = pause
        pause_func = partial(pause_stream, pause)
        quit_func = partial(quit_stream, quit_)
        pause_button = Tk.Button(root, text="Pause/Resume", command=pause_func)
        quit_button = Tk.Button(root, text="Quit", command=quit_func)


        playerone_label.grid(row=0,column=0,ipady=10)
        playerone_score.grid(row=1,column=0)
        playertwo_label.grid(row=0,column=2,ipadx=0,ipady=10)
        playertwo_score.grid(row=1,column=2,ipadx=0)
        serving_label.grid(row=2,column=1,ipady=10)
        serving_arrow_label.grid(row=3,column=1,ipadx=0)

        adjust_p1_label.grid(row=4, column=0)
        adjust_p2_label.grid(row=4, column=2)
        adjust_p1_up_button.grid(row=5,column=0)
        adjust_p1_down_button.grid(row=6,column=0)
        adjust_p2_up_button.grid(row=5,column=2)
        adjust_p2_down_button.grid(row=6,column=2)

        empty_label.grid(row=7,column=0,columnspan=2,ipady=20)
        pause_button.grid(row=8,column=0,columnspan=1)
        quit_button.grid(row=8,column=2,columnspan=1,ipadx=15)
        root.update()
        self.root = root

    def adjust_score(self, player, up_or_down):
        if player == 'p1':
            if up_or_down == "up":
                self.score[0] = min(self.score[0] + 1, 21)
            else:
                self.score[0] = max(self.score[0] - 1, 0)
        else:
            if up_or_down == "up":
                self.score[1] = min(self.score[1] + 1, 21)
            else:
                self.score[1] = max(self.score[1] - 1, 0)
        self.p1_score_var.set(self.score[0])
        self.p2_score_var.set(self.score[1])

    def message(self, msg):
        is_paused = self.pause.value == 1
        if not is_paused:
            self.pause.value = 1
        messagebox.showinfo(message=msg)
        if not is_paused:
            self.pause.value = 0

    def confirm(self, msg):
        '''
        confirm the promp with the user, pause the input stream while waiting
        '''
        is_paused = self.pause.value == 1
        if not is_paused:
            self.pause.value = 1
        answer = messagebox.askquestion(message=msg)
        if answer == "yes":
            resp = True
        else:
            resp = False
        if not is_paused:
            self.pause.value = 0
        return resp

    def input(self, prompt):
        '''
        get an input from the user, pausing the input while waiting
        '''
        is_paused = self.pause.value == 1
        if not is_paused:
            self.pause.value = 1
        answer = simpledialog.askstring('Input', prompt)
        if not is_paused:
            self.pause.value = 0
        return answer

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



if __name__ == "__main__":
    from multiprocessing import Value
    pause = Value('i', 0)
    quit_ = Value('i', 0)
    sb = Scoreboard()
    sb.init_tk(pause, quit_)
    sb.root.mainloop()

