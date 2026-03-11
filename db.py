import sqlite3
from datetime import datetime

class Database:
    def __init__(self, db_file):
        self.connection = sqlite3.connect(db_file)
        self.cursor = self.connection.cursor()
        self.create_tables()

    def create_tables(self):
        with self.connection:
            # Foydalanuvchilar jadvali
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    full_name TEXT,
                    username TEXT,
                    is_owner BOOLEAN DEFAULT 0,
                    latitude REAL,
                    longitude REAL
                )
            """)
            # Stadionlar jadvali
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS stadiums (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_id INTEGER,
                    name TEXT,
                    address_link TEXT,
                    latitude REAL,
                    longitude REAL,
                    price_per_hour INTEGER,
                    work_hours TEXT,
                    photo_id TEXT,
                    FOREIGN KEY (owner_id) REFERENCES users (id)
                )
            """)
            # Bronlar jadvali
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS bookings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    stadium_id INTEGER,
                    booking_date TEXT,
                    time_slot TEXT,
                    status TEXT DEFAULT 'active'
                )
            """)

    def add_user(self, user_id, full_name, username):
        with self.connection:
            return self.cursor.execute(
                "INSERT OR IGNORE INTO users (id, full_name, username) VALUES (?, ?, ?)",
                (user_id, full_name, username)
            )

    def get_user(self, user_id):
        with self.connection:
            return self.cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    def update_user_role(self, user_id, is_owner):
        with self.connection:
            return self.cursor.execute("UPDATE users SET is_owner = ? WHERE id = ?", (is_owner, user_id))

    def add_stadium(self, owner_id, name, link, lat, lon, price, hours, photo):
        with self.connection:
            return self.cursor.execute(
                "INSERT INTO stadiums (owner_id, name, address_link, latitude, longitude, price_per_hour, work_hours, photo_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (owner_id, name, link, lat, lon, price, hours, photo)
            )

    def get_all_stadiums(self):
        with self.connection:
            return self.cursor.execute("SELECT * FROM stadiums").fetchall()

    def get_stadium_by_id(self, s_id):
        with self.connection:
            return self.cursor.execute("SELECT * FROM stadiums WHERE id = ?", (s_id,)).fetchone()

    def get_owner_stadiums(self, owner_id):
        with self.connection:
            return self.cursor.execute("SELECT * FROM stadiums WHERE owner_id = ?", (owner_id,)).fetchall()

    def add_booking(self, user_id, s_id, date, slot):
        with self.connection:
            return self.cursor.execute(
                "INSERT INTO bookings (user_id, stadium_id, booking_date, time_slot) VALUES (?, ?, ?, ?)",
                (user_id, s_id, date, slot)
            )

    def get_booked_slots(self, s_id, date):
        with self.connection:
            res = self.cursor.execute(
                "SELECT time_slot FROM bookings WHERE stadium_id = ? AND booking_date = ? AND status = 'active'",
                (s_id, date)
            ).fetchall()
            return [r[0] for r in res]

    def get_user_bookings(self, u_id):
        with self.connection:
            return self.cursor.execute("""
                SELECT b.booking_date, b.time_slot, s.name, s.address_link 
                FROM bookings b 
                JOIN stadiums s ON b.stadium_id = s.id 
                WHERE b.user_id = ? AND b.status = 'active'
            """, (u_id,)).fetchall()
            
