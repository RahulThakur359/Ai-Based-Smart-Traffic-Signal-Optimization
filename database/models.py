def _serialize_timestamp(ts):
    """Safely formats timestamp whether it is a datetime object or already a string."""
    if ts is None:
        return None
    if hasattr(ts, 'isoformat'):
        return ts.isoformat()
    return str(ts)


class TrafficRecord:
    """
    Data model representing a historical traffic record snapshot for a road.
    """
    def __init__(self, road_id, vehicle_count, density, congestion_level, emergency_detected=False, timestamp=None, record_id=None):
        self.id = record_id
        self.road_id = road_id
        self.vehicle_count = vehicle_count
        self.density = density
        self.congestion_level = congestion_level
        self.emergency_detected = emergency_detected
        self.timestamp = timestamp

    def to_dict(self):
        return {
            'id': self.id,
            'road_id': self.road_id,
            'vehicle_count': self.vehicle_count,
            'density': self.density,
            'congestion_level': self.congestion_level,
            'emergency_detected': self.emergency_detected,
            'timestamp': _serialize_timestamp(self.timestamp)
        }


class SignalTimingRecord:
    """
    Data model representing the signal controller decision logs.
    """
    def __init__(self, road_id, green_duration, reason=None, timestamp=None, record_id=None):
        self.id = record_id
        self.road_id = road_id
        self.green_duration = green_duration
        self.reason = reason
        self.timestamp = timestamp

    def to_dict(self):
        return {
            'id': self.id,
            'road_id': self.road_id,
            'green_duration': self.green_duration,
            'reason': self.reason,
            'timestamp': _serialize_timestamp(self.timestamp)
        }


class User:
    """
    Data model representing an operator or administrator user account.
    """
    def __init__(self, username, password_hash, email=None, full_name=None, role='operator', status='PENDING', created_at=None, user_id=None):
        self.id = user_id
        self.username = username
        self.password_hash = password_hash
        self.email = email
        self.full_name = full_name
        self.role = role
        self.status = status
        self.created_at = created_at

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'role': self.role,
            'status': self.status,
            'created_at': _serialize_timestamp(self.created_at)
        }

