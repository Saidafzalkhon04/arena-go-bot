import sqlite3
from datetime import datetime

class Database:
    def __init__(self, db_file):
        self.connection = sqlite3.connect(db_file)
        self.cursor = self.connection.cursor()
        self.create_tables()

    def create_tables(self):
        with self.connection:
            # Users table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    full_name TEXT,
                    username TEXT,
                    is_owner BOOLEAN DEFAULT 0,
                    latitude REAL,
                    longitude REAL,
                    games_played INTEGER DEFAULT 0,
                    goals INTEGER DEFAULT 0
                )
            """)
            # Stadiums table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS stadiums (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_id INTEGER,
                    name TEXT,
                    address TEXT,
                    latitude REAL,
                    longitude REAL,
                    price_per_hour INTEGER,
                    description TEXT,
                    photo_id TEXT,
                    work_hours TEXT,
                    FOREIGN KEY (owner_id) REFERENCES users (id)
                )
            """)
            # Bookings table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS bookings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    stadium_id INTEGER,
                    booking_date TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    status TEXT DEFAULT 'active',
                    invite_link TEXT,
                    created_at TEXT
                )
            """)
            # Team members table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS team_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    booking_id INTEGER,
                    user_id INTEGER,
                    UNIQUE(booking_id, user_id)
                )
            """)

    # User Methods
    def add_user(self, user_id, full_name, username):
        with self.connection:
            return self.cursor.execute("INSERT OR IGNORE INTO users (id, full_name, username) VALUES (?, ?, ?)", (user_id, full_name, username))

    def get_user(self, user_id):
        with self.connection:
            return self.cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    # Stadium Methods
    def add_stadium(self, owner_id, name, address, lat, lon, price, desc, photo, hours):
        with self.connection:
            return self.cursor.execute("INSERT INTO stadiums (owner_id, name, address, latitude, longitude, price_per_hour, description, photo_id, work_hours) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (owner_id, name, address, lat, lon, price, desc, photo, hours))

    def update_stadium(self, s_id, price, hours):
        with self.connection:
            return self.cursor.execute("UPDATE stadiums SET price_per_hour=?, work_hours=? WHERE id=?", (price, hours, s_id))

    def delete_stadium(self, s_id):
        with self.connection:
            self.cursor.execute("DELETE FROM stadiums WHERE id=?", (s_id,))

    def get_all_stadiums(self):
        with self.connection:
            return self.cursor.execute("SELECT * FROM stadiums").fetchall()

    def get_stadium_by_id(self, s_id):
        with self.connection:
            return self.cursor.execute("SELECT * FROM stadiums WHERE id=?", (s_id,)).fetchone()

    def get_owner_stadiums(self, owner_id):
        with self.connection:
            return self.cursor.execute("SELECT * FROM stadiums WHERE owner_id=?", (owner_id,)).fetchall()

    # Booking & Team Methods
    def check_availability(self, s_id, date, start, end):
        with self.connection:
            # Band vaqtlar bilan kesishishni tekshirish
            res = self.cursor.execute("""
                SELECT id FROM bookings 
                WHERE stadium_id = ? AND booking_date = ? AND status = 'active'
                AND ((start_time <= ? AND end_time > ?) OR (start_time < ? AND end_time >= ?))
            """, (s_id, date, start, start, end, end)).fetchone()
            return res is None

    def add_booking(self, user_id, s_id, date, start, end, link):
        with self.connection:
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.cursor.execute("INSERT INTO bookings (user_id, stadium_id, booking_date, start_time, end_time, invite_link, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (user_id, s_id, date, start, end, link, created_at))
            b_id = self.cursor.lastrowid
            self.cursor.execute("INSERT INTO team_members (booking_id, user_id) VALUES (?, ?)", (b_id, user_id))
            return b_id

    def get_booking_by_link(self, link):
        with self.connection:
            return self.cursor.execute("SELECT * FROM bookings WHERE invite_link = ?", (link,)).fetchone()

    def add_team_member(self, b_id, u_id):
        with self.connection:
            return self.cursor.execute("INSERT OR IGNORE INTO team_members (booking_id, user_id) VALUES (?, ?)", (b_id, u_id))

    def get_team_members(self, b_id):
        with self.connection:
            return self.cursor.execute("SELECT u.* FROM users u JOIN team_members tm ON u.id = tm.user_id WHERE tm.booking_id = ?", (b_id,)).fetchall()

    def get_user_bookings(self, u_id):
        with self.connection:
            return self.cursor.execute("SELECT b.*, s.name FROM bookings b JOIN stadiums s ON b.stadium_id = s.id WHERE b.user_id = ? AND b.status = 'active'", (u_id,)).fetchall()

    def cancel_booking(self, b_id):
        with self.connection:
            return self.cursor.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ?", (b_id,))
        
