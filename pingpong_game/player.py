class Player:
    def __init__(self, name=None, position=None):
        self.name = name
        self.position = position

    def __str__(self):
        return self.name


if __name__ == "__main__":
    player = Player()
    player.name = 'nicky'
    print(player)
