import os
import psycopg2
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def setup_database():
    if not DATABASE_URL:
        print("❌ Error: DATABASE_URL is missing!")
        return

    try:
        db_url = DATABASE_URL.replace("postgres://", "postgresql://")
        conn = psycopg2.connect(db_url)
        c = conn.cursor()

        print("🛠️ Building database tables...")
        
        # 1. Users Table (From Screenshot 3)
        c.execute("""
            CREATE TABLE IF NOT EXISTS Users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT DEFAULT 'user'
            );
        """)

        # 2. System Settings Table (From Screenshot 3 & 4)
        c.execute("""
            CREATE TABLE IF NOT EXISTS Settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)

        # 3. Subjects Database (From Screenshot 4)
        c.execute("""
            CREATE TABLE IF NOT EXISTS Subjects (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                average_score TEXT DEFAULT 'Pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 4. Uploads/Images Table
        c.execute("""
            CREATE TABLE IF NOT EXISTS Uploads (
                id SERIAL PRIMARY KEY,
                subject_id INTEGER REFERENCES Subjects(id) ON DELETE CASCADE,
                file_path TEXT NOT NULL
            );
        """)

        # --- Default Data Insertion ---
        
        # Add Admin User
        c.execute("SELECT id FROM Users WHERE username = 'shafin'")
        if not c.fetchone():
            hashed_pw = generate_password_hash("admin123")
            c.execute("INSERT INTO Users (username, password, role) VALUES (%s, %s, %s)", ('shafin', hashed_pw, 'admin'))
            print("✅ Created default admin: shafin / admin123")

        # Add Default Settings (Mode & Wallpaper)
        c.execute("INSERT INTO Settings (key, value) VALUES ('active_mode', 'MANUAL') ON CONFLICT (key) DO NOTHING;")
        c.execute("INSERT INTO Settings (key, value) VALUES ('wallpaper', 'default.jpg') ON CONFLICT (key) DO NOTHING;")

        conn.commit()
        print("✅ Database successfully set up and ready for Render!")

    except Exception as e:
        print(f"❌ Database error: {e}")
    finally:
        if 'conn' in locals():
            c.close()
            conn.close()

if __name__ == "__main__":
    setup_database()