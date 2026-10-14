from enum import Enum

class SignalState(Enum):
    RED = 'RED'
    YELLOW = 'YELLOW'
    GREEN = 'GREEN'

class SignalController:
    """
    Manages the phase states and timers for a specific intersection lane.
    """
    def __init__(self, road_id):
        self.road_id = road_id
        self.current_state = SignalState.RED
        self.remaining_time = 0

    def transition_to(self, state, duration):
        """
        Transitions signal state to RED, YELLOW, or GREEN with a set timer.
        Args:
            state (SignalState): The target state.
            duration (int): Countdown timer in seconds.
        """
        self.current_state = state
        self.remaining_time = duration

    def tick(self):
        """
        Decrements the countdown timer by 1 second.
        Returns:
            int: Remaining time.
        """
        if self.remaining_time > 0:
            self.remaining_time -= 1
        return self.remaining_time

    def get_status(self):
        """
        Returns a dict of current signal parameters.
        """
        return {
            'road_id': self.road_id,
            'state': self.current_state.value,
            'remaining_time': self.remaining_time
        }
