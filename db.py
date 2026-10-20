"""
db.py  —  RESCUE Database Layer
Handles connection, table creation, and sample data seeding.
"""

import mysql.connector
from mysql.connector import Error
from werkzeug.security import generate_password_hash
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ─────────────────────────────────────────
#  CONFIG  (change here or use .env)
# ─────────────────────────────────────────
DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),   # set MYSQL_PASSWORD in your environment or a .env file
    "database": os.getenv("MYSQL_DATABASE", "rescue_db"),
    "charset": "utf8mb4",
    "autocommit": False,
}

DB_CONFIG_NO_DB = {
    "host": DB_CONFIG["host"],
    "user": DB_CONFIG["user"],
    "password": DB_CONFIG["password"],  # ✔ reuse correctly
    "charset": "utf8mb4",
}
# ─────────────────────────────────────────
#  CONNECTION HELPERS
# ─────────────────────────────────────────
def get_connection():
    """Return a fresh MySQL connection (caller must close it)."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except Error as e:
        raise RuntimeError(f"[DB] Connection failed: {e}")


def query(sql: str, params: tuple = (), fetchone: bool = False, commit: bool = False):
    """
    Utility wrapper:
      - SELECT  -> returns list of dicts  (or one dict if fetchone=True)
      - INSERT/UPDATE/DELETE -> returns lastrowid if commit=True
    """
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, params)
        if commit:
            conn.commit()
            return cursor.lastrowid
        if fetchone:
            return cursor.fetchone()
        return cursor.fetchall()
    except Error as e:
        conn.rollback()
        raise RuntimeError(f"[DB] Query error: {e}\nSQL: {sql}")
    finally:
        cursor.close()
        conn.close()


# ─────────────────────────────────────────
#  INIT — create DB + tables + seed
# ─────────────────────────────────────────
def init_db():
    """Called on app startup. Creates database, tables, and seeds data."""
    _create_database()
    _create_tables()
    _seed_data()
    print("[DB] Database ready.")


def _create_database():
    try:
        conn = mysql.connector.connect(**DB_CONFIG_NO_DB)
        cursor = conn.cursor()
        name = DB_CONFIG["database"].replace("`", "")
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{name}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        conn.commit()
        cursor.close()
        conn.close()
        print(f"[DB] Database '{name}' ensured.")
    except Error as e:
        raise RuntimeError(f"[DB] Could not create database: {e}")


def _create_tables():
    statements = [
        # hospitals
        """
        CREATE TABLE IF NOT EXISTS hospitals (
            id            INT          PRIMARY KEY AUTO_INCREMENT,
            name          VARCHAR(255) NOT NULL,
            location      VARCHAR(255) NOT NULL,
            network       ENUM('5G','4G','3G') DEFAULT '5G',
            status        ENUM('online','offline','maintenance') DEFAULT 'online',
            icu_capacity  INT DEFAULT 0,
            icu_available INT DEFAULT 0,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        # users
        """
        CREATE TABLE IF NOT EXISTS users (
            id          INT          PRIMARY KEY AUTO_INCREMENT,
            username    VARCHAR(100) NOT NULL UNIQUE,
            email       VARCHAR(255) NOT NULL UNIQUE,
            password    VARCHAR(255) NOT NULL,
            role        ENUM('admin','staff') NOT NULL DEFAULT 'staff',
            hospital_id INT NULL,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (hospital_id) REFERENCES hospitals(id) ON DELETE SET NULL
        )
        """,
        # resources
        """
        CREATE TABLE IF NOT EXISTS resources (
            id                 INT          PRIMARY KEY AUTO_INCREMENT,
            name               VARCHAR(255) NOT NULL,
            category           ENUM('drug','equipment','bed','blood','other') DEFAULT 'other',
            hospital_id        INT NOT NULL,
            stock              INT NOT NULL DEFAULT 0,
            unit               VARCHAR(50)  DEFAULT 'units',
            critical_threshold INT DEFAULT 5,
            updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (hospital_id) REFERENCES hospitals(id) ON DELETE CASCADE
        )
        """,
        # transfers
        """
        CREATE TABLE IF NOT EXISTS transfers (
            id               INT PRIMARY KEY AUTO_INCREMENT,
            from_hospital_id INT NOT NULL,
            to_hospital_id   INT NOT NULL,
            resource_id      INT NOT NULL,
            units            INT NOT NULL DEFAULT 1,
            status           ENUM('pending','approved','rejected','completed') DEFAULT 'pending',
            requested_by     INT NOT NULL,
            approved_by      INT NULL,
            notes            TEXT NULL,
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (from_hospital_id) REFERENCES hospitals(id),
            FOREIGN KEY (to_hospital_id)   REFERENCES hospitals(id),
            FOREIGN KEY (resource_id)      REFERENCES resources(id),
            FOREIGN KEY (requested_by)     REFERENCES users(id),
            FOREIGN KEY (approved_by)      REFERENCES users(id) ON DELETE SET NULL
        )
        """,
        # messages
        """
        CREATE TABLE IF NOT EXISTS messages (
            id          INT PRIMARY KEY AUTO_INCREMENT,
            sender_id   INT NOT NULL,
            content     TEXT NOT NULL,
            broadcast   TINYINT(1) DEFAULT 1,
            to_hospital INT NULL,
            timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sender_id)   REFERENCES users(id),
            FOREIGN KEY (to_hospital) REFERENCES hospitals(id) ON DELETE SET NULL
        )
        """,
        # ambulances
        """
        CREATE TABLE IF NOT EXISTS ambulances (
            id          INT PRIMARY KEY AUTO_INCREMENT,
            code        VARCHAR(50) NOT NULL UNIQUE,
            hospital_id INT NULL,
            status      ENUM('active','busy','offline') DEFAULT 'active',
            location    VARCHAR(255) DEFAULT 'Base',
            eta         VARCHAR(50)  DEFAULT '--',
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (hospital_id) REFERENCES hospitals(id) ON DELETE SET NULL
        )
        """,
        # triage
        """
        CREATE TABLE IF NOT EXISTS triage (
            id            INT PRIMARY KEY AUTO_INCREMENT,
            case_code     VARCHAR(20) UNIQUE,
            hospital_id   INT NOT NULL,
            patient_anon  VARCHAR(100),
            condition_name VARCHAR(255),
            priority      ENUM('P1','P2','P3') DEFAULT 'P2',
            status        ENUM('active','stable','discharged') DEFAULT 'active',
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (hospital_id) REFERENCES hospitals(id)
        )
        """,
    ]

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    for stmt in statements:
        cursor.execute(stmt)
    conn.commit()
    cursor.close()
    conn.close()
    print("[DB] Tables ensured.")


def _seed_data():
    """Insert sample data only if tables are empty."""
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    # Hospitals
    cursor.execute("SELECT COUNT(*) AS c FROM hospitals")
    if cursor.fetchone()["c"] == 0:
        cursor.executemany(
            "INSERT INTO hospitals (name, location, network, icu_capacity, icu_available) "
            "VALUES (%s, %s, %s, %s, %s)",
            [
                ("KEM Hospital",               "Parel, South Mumbai",   "5G", 342, 87),
                ("Hinduja Hospital",            "Mahim, Mumbai",         "5G", 220, 54),
                ("Kokilaben Dhirubhai Ambani",  "Andheri West, Mumbai",  "5G", 310, 120),
            ],
        )
        conn.commit()
        print("[DB] Hospitals seeded.")

    # Users
    cursor.execute("SELECT COUNT(*) AS c FROM users")
    if cursor.fetchone()["c"] == 0:
        users = [
            ("admin",  "admin@rescue.in",  generate_password_hash("admin123"),  "admin", None),
            ("staff1", "staff1@kem.in",    generate_password_hash("staff123"),  "staff", 1),
            ("staff2", "staff2@hinduja.in",generate_password_hash("staff123"),  "staff", 2),
        ]
        cursor.executemany(
            "INSERT INTO users (username, email, password, role, hospital_id) "
            "VALUES (%s, %s, %s, %s, %s)",
            users,
        )
        conn.commit()
        print("[DB] Users seeded.  admin/admin123  staff1/staff123  staff2/staff123")

    # Resources
    cursor.execute("SELECT COUNT(*) AS c FROM resources")
    if cursor.fetchone()["c"] == 0:
        cursor.executemany(
            "INSERT INTO resources (name, category, hospital_id, stock, unit, critical_threshold) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            [
                ("ICU Bed",         "bed",       1, 87,  "beds",  10),
                ("Ventilator",      "equipment", 1, 14,  "units",  3),
                ("Oxygen Cylinder", "equipment", 1,  4,  "units",  5),
                ("Remdesivir",      "drug",      1, 45,  "vials",  8),
                ("Blood O+",        "blood",     1, 12,  "units",  5),
                ("ICU Bed",         "bed",       2, 54,  "beds",  10),
                ("Defibrillator",   "equipment", 2,  8,  "units",  2),
                ("Insulin",         "drug",      2,200,  "vials", 20),
                ("ICU Bed",         "bed",       3,120,  "beds",  15),
                ("Pembrolizumab",   "drug",      3, 18,  "vials",  4),
                ("Cardiac Monitor", "equipment", 3, 22,  "units",  4),
            ],
        )
        conn.commit()
        print("[DB] Resources seeded.")

    # Ambulances
    cursor.execute("SELECT COUNT(*) AS c FROM ambulances")
    if cursor.fetchone()["c"] == 0:
        cursor.executemany(
            "INSERT INTO ambulances (code, hospital_id, status, location, eta) "
            "VALUES (%s, %s, %s, %s, %s)",
            [
                ("MH-001", 1, "active", "KEM Base",           "--"),
                ("MH-002", 1, "busy",   "KEM -> Hinduja",     "8 min"),
                ("MH-003", 2, "active", "Hinduja Base",       "--"),
                ("MH-004", 2, "busy",   "Hinduja -> Andheri", "12 min"),
                ("MH-005", 3, "offline","Maintenance Depot",  "--"),
            ],
        )
        conn.commit()
        print("[DB] Ambulances seeded.")

    cursor.close()
    conn.close()
