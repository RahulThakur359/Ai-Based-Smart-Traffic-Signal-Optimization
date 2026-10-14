# Database Package Initializer
from .db import get_db_connection, get_sqlite_connection, init_db
from .models import TrafficRecord, SignalTimingRecord, User
from .queries import (
    insert_traffic_record,
    insert_signal_timing,
    get_latest_traffic_records,
    get_analytics_summary,
    get_user_by_username,
    get_user_by_id,
    create_user,
    get_all_users,
    update_user_status,
    delete_user,
    get_system_setting,
    set_system_setting,
)
