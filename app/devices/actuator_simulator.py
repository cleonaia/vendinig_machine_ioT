class ActuatorSimulator:
    def __init__(self) -> None:
        self.online = True

    def disconnect(self) -> None:
        self.online = False

    def reconnect(self) -> None:
        self.online = True
