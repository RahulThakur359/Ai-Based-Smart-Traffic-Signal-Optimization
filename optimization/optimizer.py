import time
import threading
import logging
from config import Config
from optimization.priority import RoadPriorityCalculator
from optimization.timing import DynamicTimingCalculator
from optimization.signal_controller import SignalController, SignalState

logger = logging.getLogger(__name__)


class IntersectionSignalManager:
    """
    Coordinates 4-way intersection adaptive signal timing:
    - Never enables conflicting greens simultaneously (exactly one road GREEN or YELLOW).
    - Dynamically allocates green durations from 15s to 60s based on area density & congestion.
    - Implements starvation prevention fairness to ensure low-traffic lanes get green time.
    - Records human-readable decision reasons for academic & demonstration clarity.
    """

    def __init__(self, road_ids=None, auto_activate=True):
        self.road_ids = road_ids or ['road1', 'road2', 'road3', 'road4']
        self.priority_calculator = RoadPriorityCalculator()
        self.timing_calculator = DynamicTimingCalculator()

        self.yellow_time = Config.YELLOW_TIME
        self.min_green = Config.MIN_GREEN_TIME
        self.max_green = Config.MAX_GREEN_TIME

        self.current_road_index = 0  # Starts with Road 1 (index 0)
        self.is_active = auto_activate
        self.active_road = self.road_ids[0]
        self.active_state = SignalState.GREEN
        self.allocated_green = self.min_green
        self.remaining_time = self.min_green if auto_activate else None
        self.current_reason = "Initial startup phase (default baseline timing)." if auto_activate else "Standby: Awaiting video upload and processing completion."
        self.starvation_counters = {rid: 0 for rid in self.road_ids}

        self.lock = threading.Lock()
        self._running = False
        self._thread = None

    def start_simulation(self):
        """Starts background clock thread to tick signal timers."""
        with self.lock:
            if not self._running:
                self._running = True
                self._thread = threading.Thread(target=self._run_loop, daemon=True, name="SignalSimulationClock")
                self._thread.start()
                logger.info("Adaptive Traffic Signal Simulation Engine started.")

    def stop_simulation(self):
        with self.lock:
            self._running = False

    def activate(self):
        """
        Activates signal switching upon completion of video analysis.
        Strictly starts sequential cycle with ROAD 1 first.
        """
        with self.lock:
            self.current_road_index = 0
            self.active_road = self.road_ids[0]
            decision = self.compute_road_phase_parameters(self.active_road)

            self.active_state = SignalState.GREEN
            self.allocated_green = decision["green_duration"]
            self.remaining_time = decision["green_duration"]
            self.current_reason = decision["reason"]
            self.is_active = True
            logger.info(
                f"[Adaptive Signal] Sequential cycle activated starting with {self.active_road.upper()} "
                f"GREEN for {self.allocated_green}s. Reason: {self.current_reason}"
            )

    def on_road_completed(self, road_id=None):
        """Callback invoked when a road finishes video processing."""
        self.activate()

    def _check_any_road_completed(self):
        """Checks whether any road in traffic_state has COMPLETED processing."""
        try:
            from routes.traffic_api import traffic_state
            return any(
                r.get('status') == 'COMPLETED'
                for r in traffic_state.values()
            )
        except Exception:
            return False

    def get_estimated_green(self, road_id, road_metrics=None):
        """
        Computes dynamic green duration for a designated road branch based on real-time traffic load.
        Roads with fewer vehicles receive a shorter green duration; roads with more vehicles receive longer.
        """
        if road_metrics is None:
            try:
                from routes.traffic_api import traffic_state
                road_metrics = traffic_state
            except Exception:
                road_metrics = {}

        m = road_metrics.get(road_id, {})
        density_pct = m.get('density_percentage')
        if density_pct is None:
            cat = str(m.get('density', 'LOW')).upper()
            density_pct = {'LOW': 15.0, 'MEDIUM': 40.0, 'HIGH': 65.0, 'VERY HIGH': 85.0}.get(cat, 15.0)

        active_v = m.get('active_vehicles') or m.get('current_vehicles') or m.get('total_unique') or 0
        congestion = m.get('congestion_level') or m.get('congestion') or 'NORMAL'
        has_emg = (m.get('emergency') is True) or (m.get('emergency') == 'YES')

        priority_score = 9999.0 if has_emg else 0.0

        return self.timing_calculator.calculate_green_time(
            density_pct=float(density_pct),
            congestion_level=str(congestion),
            priority_score=priority_score,
            vehicle_count=int(active_v)
        )

    def compute_road_phase_parameters(self, road_id, road_metrics=None):
        """Calculates dynamic green timing and formatted decision explanation for a given road."""
        if road_metrics is None:
            try:
                from routes.traffic_api import traffic_state
                road_metrics = traffic_state
            except Exception:
                road_metrics = {}

        m = road_metrics.get(road_id, {})
        density_pct = m.get('density_percentage')
        if density_pct is None:
            cat = str(m.get('density', 'LOW')).upper()
            density_pct = {'LOW': 15.0, 'MEDIUM': 40.0, 'HIGH': 65.0, 'VERY HIGH': 85.0}.get(cat, 15.0)

        active_v = m.get('active_vehicles') or m.get('current_vehicles') or m.get('total_unique') or 0
        congestion = m.get('congestion_level') or m.get('congestion') or 'NORMAL'
        has_emg = (m.get('emergency') is True) or (m.get('emergency') == 'YES')

        priority_score = 9999.0 if has_emg else 0.0

        duration = self.timing_calculator.calculate_green_time(
            density_pct=float(density_pct),
            congestion_level=str(congestion),
            priority_score=priority_score,
            vehicle_count=int(active_v)
        )

        if has_emg:
            reason = f"EMERGENCY OVERRIDE: {road_id.upper()} granted max clearance green ({duration}s)."
        else:
            reason = (
                f"Sequential Phase: {road_id.upper()} allocated {duration}s Green "
                f"(Vehicles: {active_v}, Density: {float(density_pct):.1f}%, Congestion: {congestion})."
            )

        return {
            "selected_road": road_id,
            "green_duration": duration,
            "reason": reason
        }

    def optimize_cycle(self, road_metrics=None, advance_sequence=False):
        """
        Determines sequential green progression: Road 1 -> Road 2 -> Road 3 -> Road 4.
        
        Args:
            road_metrics (dict, optional): Mapping of road_id -> metrics dict.
            advance_sequence (bool): If True, advances current pointer to next road in sequence.
            
        Returns:
            dict with selected_road, green_duration, reason, and candidate scores.
        """
        if road_metrics is None:
            try:
                from routes.traffic_api import traffic_state
                road_metrics = traffic_state
            except Exception:
                road_metrics = {}

        # 1. Emergency vehicle check: highest safety override
        for rid in self.road_ids:
            m = road_metrics.get(rid, {})
            if (m.get('emergency') is True) or (m.get('emergency') == 'YES'):
                self.current_road_index = self.road_ids.index(rid)
                decision = self.compute_road_phase_parameters(rid, road_metrics)
                decision["scores"] = {r: (9999.0 if r == rid else 0.0) for r in self.road_ids}
                return decision

        # 2. Sequential progression: Road 1 -> Road 2 -> Road 3 -> Road 4
        if advance_sequence:
            self.current_road_index = (self.current_road_index + 1) % len(self.road_ids)

        selected_road = self.road_ids[self.current_road_index]
        decision = self.compute_road_phase_parameters(selected_road, road_metrics)

        # Calculate relative priority scores for reporting/audit transparency
        scores = {}
        for rid in self.road_ids:
            m = road_metrics.get(rid, {})
            d_pct = float(m.get('density_percentage') or 15.0)
            v_cnt = int(m.get('active_vehicles') or m.get('current_vehicles') or m.get('total_unique') or 0)
            cong = str(m.get('congestion_level') or 'NORMAL')
            score, _ = self.priority_calculator.calculate_priority_score(
                density_pct=d_pct,
                active_vehicles=v_cnt,
                congestion_level=cong,
                starvation_cycles=self.starvation_counters.get(rid, 0)
            )
            scores[rid] = score

        decision["scores"] = scores
        return decision

    def _run_loop(self):
        """Simulation tick loop executed once per second."""
        while self._running:
            time.sleep(1.0)
            with self.lock:
                if not self.is_active:
                    # Do not tick or switch lights until a video analysis has completed
                    if self._check_any_road_completed():
                        self.activate()
                    continue

                if self.remaining_time is not None:
                    self.remaining_time -= 1

                    if self.remaining_time <= 0:
                        if self.active_state == SignalState.GREEN:
                            # Transition to Yellow safety clearance
                            self.active_state = SignalState.YELLOW
                            self.remaining_time = self.yellow_time
                            self.current_reason = f"Safety clearance: {self.active_road.upper()} in Yellow transition phase."
                        else:
                            # Yellow expired: advance to next road in sequential order (1 -> 2 -> 3 -> 4)
                            decision = self.optimize_cycle(advance_sequence=True)
                            next_road = decision["selected_road"]
                            next_duration = decision["green_duration"]

                            # Update starvation counters
                            for rid in self.road_ids:
                                if rid == next_road:
                                    self.starvation_counters[rid] = 0
                                else:
                                    self.starvation_counters[rid] += 1

                            self.active_road = next_road
                            self.active_state = SignalState.GREEN
                            self.allocated_green = next_duration
                            self.remaining_time = next_duration
                            self.current_reason = decision["reason"]

                            logger.info(
                                f"[Adaptive Signal] Phase sequentially switched to {next_road.upper()} "
                                f"(Green: {next_duration}s). Reason: {self.current_reason}"
                            )

    def get_status(self):
        """
        Returns instantaneous intersection signal states and countdowns for all 4 roads.
        - Active road displays its remaining GREEN or YELLOW time.
        - Next sequential road (e.g. Road 2 when Road 1 is active) displays a RED signal
          with an exact countdown timer showing how many seconds it will remain red.
        - Subsequent queued roads display their total wait countdown until their green phase.
        """
        with self.lock:
            data = {}
            if not self.is_active or self.remaining_time is None:
                for rid in self.road_ids:
                    data[rid] = {
                        "state": SignalState.RED.value,
                        "remaining_time": None,
                        "optimized_green": None,
                        "decision_reason": "Standby: Awaiting video upload and processing completion.",
                        "starvation_count": self.starvation_counters.get(rid, 0),
                        "is_active": False
                    }
                data["meta"] = {
                    "active_road": self.active_road,
                    "active_state": "STANDBY",
                    "is_active": False,
                    "current_reason": self.current_reason,
                    "yellow_time": self.yellow_time,
                    "min_green": self.min_green,
                    "max_green": self.max_green
                }
                return data

            active_idx = self.road_ids.index(self.active_road) if self.active_road in self.road_ids else 0
            active_rem = max(0, self.remaining_time)

            # Pre-compute estimated green duration for all roads
            planned_greens = {rid: self.get_estimated_green(rid) for rid in self.road_ids}
            planned_greens[self.active_road] = self.allocated_green

            for idx, rid in enumerate(self.road_ids):
                if rid == self.active_road:
                    data[rid] = {
                        "state": self.active_state.value,
                        "remaining_time": active_rem,
                        "optimized_green": self.allocated_green,
                        "decision_reason": self.current_reason,
                        "starvation_count": 0,
                        "is_active": True
                    }
                else:
                    # Calculate how many sequence steps away this road is from the active road
                    steps_away = (idx - active_idx) % len(self.road_ids)

                    # For the immediate next road (steps_away == 1, e.g. Road 2 when Road 1 is active),
                    # its red countdown timer is active_rem (exact time until it receives green).
                    red_countdown = active_rem

                    # For roads further down the sequential queue, add the planned green times of intermediate roads
                    for s in range(1, steps_away):
                        intermediate_road = self.road_ids[(active_idx + s) % len(self.road_ids)]
                        red_countdown += planned_greens[intermediate_road]

                    next_str = "Next in sequence" if steps_away == 1 else f"Position #{steps_away + 1} in sequence"
                    data[rid] = {
                        "state": SignalState.RED.value,
                        "remaining_time": red_countdown,
                        "optimized_green": planned_greens[rid],
                        "decision_reason": f"Waiting in Red phase ({next_str}). Turns Green in {red_countdown}s.",
                        "starvation_count": self.starvation_counters.get(rid, 0),
                        "is_active": True
                    }

            data["meta"] = {
                "active_road": self.active_road,
                "active_state": self.active_state.value,
                "is_active": True,
                "current_reason": self.current_reason,
                "yellow_time": self.yellow_time,
                "min_green": self.min_green,
                "max_green": self.max_green
            }
            return data


# Global singleton manager instance
_signal_manager = None


def get_signal_manager(auto_activate=False):
    global _signal_manager
    if _signal_manager is None:
        _signal_manager = IntersectionSignalManager(auto_activate=auto_activate)
        _signal_manager.start_simulation()
    return _signal_manager


# Backward compatibility alias
TrafficSignalOptimizer = IntersectionSignalManager
