import sqlite3
from datetime import datetime

class Database:
    def __init__(self, db_file):
        self.connection = sqlite3.connect(db_file)
        self.cursor = self.connection.cursor()
        self.create_tables()

    def create_tables(self):
        with self.connection:
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
                    work_hours TEXT DEFAULT '09:00-23:00',
                    FOREIGN KEY (owner_id) REFERENCES users (id)
                )
            """)
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS bookings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    stadium_id INTEGER,
                    booking_date TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    status TEXT DEFAULT 'active',
                    created_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (stadium_id) REFERENCES stadiums (id)
                )
            """)
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS teams (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    creator_id INTEGER,
                    stadium_name TEXT,
                    game_date TEXT,
                    game_time TEXT,
                    needed_players INTEGER,
                    joined_players INTEGER DEFAULT 0,
                    description TEXT,
                    created_at TEXT,
                    FOREIGN KEY (creator_id) REFERENCES users (id)
                )
            """)

    def add_user(self, user_id, full_name, username):
        with self.connection:
            return self.cursor.execute(
                "INSERT OR IGNORE INTO users (id, full_name, username) VALUES (?, ?, ?)",
                (user_id, full_name, username)
            )

    def update_user_role(self, user_id, is_owner):
        with self.connection:
            return self.cursor.execute("UPDATE users SET is_owner = ? WHERE id = ?", (is_owner, user_id))

    def update_user_location(self, user_id, lat, lon):
        with self.connection:
            return self.cursor.execute("UPDATE users SET latitude = ?, longitude = ? WHERE id = ?", (lat, lon, user_id))

    def get_user(self, user_id):
        with self.connection:
            return self.cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    def add_stadium(self, owner_id, name, address, lat, lon, price, description, photo_id, work_hours):
        with self.connection:
            return self.cursor.execute(
                "INSERT INTO stadiums (owner_id, name, address, latitude, longitude, price_per_hour, description, photo_id, work_hours) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (owner_id, name, address, lat, lon, price, description, photo_id, work_hours)
            )

    def get_all_stadiums(self):
        with self.connection:
            return self.cursor.execute("SELECT * FROM stadiums").fetchall()

    def get_stadium_by_id(self, stadium_id):
        with self.connection:
            return self.cursor.execute("SELECT * FROM stadiums WHERE id = ?", (stadium_id,)).fetchone()

    def get_stadium_by_name(self, name):
        with self.connection:
            return self.cursor.execute("SELECT * FROM stadiums WHERE name LIKE ?", (f"%{name}%",)).fetchone()

    def get_owner_stadiums(self, owner_id):
        with self.connection:
            return self.cursor.execute("SELECT * FROM stadiums WHERE owner_id = ?", (owner_id,)).fetchall()

    def add_booking(self, user_id, stadium_id, date, start_time, end_time):
        with self.connection:
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.cursor.execute(
                "INSERT INTO bookings (user_id, stadium_id, booking_date, start_time, end_time, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, stadium_id, date, start_time, end_time, created_at)
            )
            return self.cursor.lastrowid

    def cancel_booking(self, booking_id, user_id):
        with self.connection:
            return self.cursor.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ? AND user_id = ?", (booking_id, user_id))

    def get_booking_by_id(self, booking_id):
        with self.connection:
            return self.cursor.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()

    def get_stadium_bookings(self, stadium_id, date):
        with self.connection:
            return self.cursor.execute(
                "SELECT start_time, end_time FROM bookings WHERE stadium_id = ? AND booking_date = ? AND status = 'active'",
                (stadium_id, date)
            ).fetchall()

    def get_user_bookings(self, user_id):
        with self.connection:
            return self.cursor.execute(
                "SELECT b.*, s.name FROM bookings b JOIN stadiums s ON b.stadium_id = s.id WHERE b.user_id = ? AND b.status = 'active'",
                (user_id,)
            ).fetchall()

    def get_owner_stadium_bookings(self, owner_id):
        with self.connection:
            return self.cursor.execute(
                "SELECT b.*, s.name, u.full_name FROM bookings b JOIN stadiums s ON b.stadium_id = s.id JOIN users u ON b.user_id = u.id WHERE s.owner_id = ? AND b.status = 'active'",
                (owner_id,)
            ).fetchall()

    def add_team_post(self, creator_id, stadium_name, date, time, players, description):
        with self.connection:
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return self.cursor.execute(
                "INSERT INTO teams (creator_id, stadium_name, game_date, game_time, needed_players, description, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (creator_id, stadium_name, date, time, players, description, created_at)
            )

    def get_all_teams(self):
        with self.connection:
            # Faqat kerakli odam yig'ilmagan e'lonlarni ko'rsatish
            return self.cursor.execute("SELECT t.*, u.full_name FROM teams t JOIN users u ON t.creator_id = u.id WHERE t.joined_players < t.needed_players ORDER BY t.id DESC").fetchall()

    def get_team_by_id(self, team_id):
        with self.connection:
            return self.cursor.execute("SELECT * FROM teams WHERE id = ?", (team_id,)).fetchone()

    def join_team(self, team_id):
        with self.connection:
            return self.cursor.execute("UPDATE teams SET joined_players = joined_players + 1 WHERE id = ?", (team_id,))
            
