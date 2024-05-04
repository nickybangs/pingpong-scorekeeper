'''
code frr the player class used to represent each player in a ping pong game
'''
class Player:
    def __init__(self, id, name=None, position=None):
        if name is None:
            name = "no name"
        self.name = name
        # i.e. either Left or Right
        self.position = position
        self.id = id

    def __str__(self):
        return str(self.name)

    def __repr__(self):
        return self.name



if __name__ == "__main__":
    player = Player()
    player.name = 'nicky'
    print(player)
