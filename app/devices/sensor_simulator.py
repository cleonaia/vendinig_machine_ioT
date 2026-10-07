class SensorSimulator:
    def __init__(self) -> None:
        self.timeout_detected = False

    def trigger_timeout(self) -> None:
        self.timeout_detected = True
