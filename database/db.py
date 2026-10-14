import os
import sqlite3
import logging
from config import Config

from werkzeug.security import generate_password_hash

# Set up logging for tracking DB status
logger = logging.getLogger(__name__)

SQLITE_DB_PATH = os.path.join(Config.BASE_DIR, 'database', 'traffic_records.db')

try:
    import mysql.connector
    from mysql.connector import Error
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False
    logger.info("mysql-connector-python not available. Using high-performance built-in SQLite storage engine.")


def get_sqlite_connection():
    """
    Establish a connection to the local SQLite database.
    Always available and requires zero configuration.
    Configured with Write-Ahead Logging (WAL) and 20s timeout to prevent concurrency lockouts.
    """
    try:
        os.makedirs(os.path.dirname(SQLITE_DB_PATH), exist_ok=True)
        conn = sqlite3.connect(SQLITE_DB_PATH, timeout=20.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 10000")
        return conn
    except Exception as e:
        logger.error(f"SQLite connection error: {e}")
        return None


def get_db_connection():
    """
    Establish a connection to the MySQL database.
    Returns None if the database connection fails or is unavailable.
    """
    if not MYSQL_AVAILABLE:
        return None
        
    try:
        connection = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            port=Config.DB_PORT,
            connection_timeout=2
        )
        if connection.is_connected():
            return connection
    except Exception as e:
        logger.debug(f"MySQL connection offline: {e}. Fallback to SQLite.")
        return None


def init_db():
    """
    Initializes database tables required for the system in both SQLite and MySQL (if available).
    Ensures users table has approval status and seeds default admin account.
    """
    # 1. Initialize local SQLite tables (always succeeds)
    sq_conn = get_sqlite_connection()
    if sq_conn:
        try:
            cursor = sq_conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    email TEXT,
                    full_name TEXT,
                    role TEXT DEFAULT 'operator',
                    status TEXT DEFAULT 'PENDING',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Upgrade existing table columns if needed
            for col_name, col_type in [
                ("email", "TEXT"),
                ("full_name", "TEXT"),
                ("status", "TEXT DEFAULT 'PENDING'")
            ]:
                try:
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                except Exception:
                    pass

            # Seed default pre-approved administrator account
            cursor.execute("SELECT id FROM users WHERE username = 'admin'")
            admin_row = cursor.fetchone()
            if not admin_row:
                admin_pw = generate_password_hash("admin123")
                cursor.execute("""
                    INSERT INTO users (username, password_hash, email, full_name, role, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, ('admin', admin_pw, 'admin@traffic.control', 'System Administrator', 'admin', 'APPROVED'))
                logger.info("Default administrator account created (admin / admin123) with APPROVED access.")
            else:
                cursor.execute("UPDATE users SET status = 'APPROVED', role = 'admin' WHERE username = 'admin'")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS traffic_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    road_id TEXT NOT NULL,
                    vehicle_count INTEGER NOT NULL,
                    density REAL NOT NULL,
                    congestion_level TEXT NOT NULL,
                    emergency_detected INTEGER DEFAULT 0,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS signal_timings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    road_id TEXT NOT NULL,
                    green_duration INTEGER NOT NULL,
                    reason TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            sq_conn.commit()
            logger.info("Local SQLite traffic analytics tables initialized.")
        except Exception as e:
            logger.error(f"Error initializing SQLite tables: {e}")
        finally:
            sq_conn.close()

    # 2. Try MySQL initialization if connected
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    email VARCHAR(100),
                    full_name VARCHAR(100),
                    role VARCHAR(20) DEFAULT 'operator',
                    status VARCHAR(20) DEFAULT 'PENDING',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS traffic_records (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    road_id VARCHAR(10) NOT NULL,
                    vehicle_count INT NOT NULL,
                    density FLOAT NOT NULL,
                    congestion_level VARCHAR(20) NOT NULL,
                    emergency_detected BOOLEAN DEFAULT FALSE,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS signal_timings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    road_id VARCHAR(10) NOT NULL,
                    green_duration INT NOT NULL,
                    reason VARCHAR(100),
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            connection.commit()
            logger.info("MySQL database tables initialized successfully.")
        except Exception as e:
            logger.error(f"Error during MySQL initialization: {e}")
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()

    return True
