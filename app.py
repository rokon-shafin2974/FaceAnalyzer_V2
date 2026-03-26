import os
import csv
from io import StringIO
from flask import Flask, request, jsonify, session, send_file
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, static_folder='public', static_url_path='')
app.secret_key = os.getenv("SECRET_KEY", "super_secret_default_key")
DATABASE_URL = os.getenv("DATABASE_URL")

def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    conn.autocommit = True
    return conn

# --- Initialize Database Tables ---
def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, username VARCHAR UNIQUE, password VARCHAR, role VARCHAR);
                CREATE TABLE IF NOT EXISTS ratings (id SERIAL PRIMARY KEY, subject_name VARCHAR, image_data TEXT, score INTEGER);
                CREATE TABLE IF NOT EXISTS settings (key VARCHAR PRIMARY KEY, value TEXT);
            """)
init_db()

# --- Auth Routes ---
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE username = %s AND role = %s", (data['username'], data['role_type']))
            user = cur.fetchone()
            if user and check_password_hash(user['password'], data['password']):
                session['user_id'] = user['id']
                session['role'] = user['role']
                return jsonify({"success": True, "redirect": "admin.html" if user['role'] == 'admin' else "index.html"})
    return jsonify({"success": False, "message": "Invalid credentials or wrong role."})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"success": True})

# --- Admin: User Management ---
@app.route('/api/admin/users', methods=['GET', 'POST', 'DELETE', 'PUT'])
def manage_users():
    if session.get('role') != 'admin': return jsonify({"error": "Unauthorized"}), 403
    with get_db() as conn:
        with conn.cursor() as cur:
            if request.method == 'GET':
                cur.execute("SELECT id, username, role FROM users")
                return jsonify(cur.fetchall())
            elif request.method == 'POST':
                data = request.json
                hashed = generate_password_hash(data['password'])
                try:
                    cur.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)", (data['username'], hashed, data['role']))
                    return jsonify({"success": True})
                except:
                    return jsonify({"success": False, "message": "Username exists"})
            elif request.method == 'DELETE':
                cur.execute("DELETE FROM users WHERE id = %s", (request.json['id'],))
                return jsonify({"success": True})
            elif request.method == 'PUT':
                data = request.json
                hashed = generate_password_hash(data['new_password'])
                cur.execute("UPDATE users SET password = %s WHERE id = %s", (hashed, data['id']))
                return jsonify({"success": True})

# --- Admin: Settings & Wallpapers ---
@app.route('/api/settings/wallpaper', methods=['GET', 'POST'])
def handle_wallpaper():
    with get_db() as conn:
        with conn.cursor() as cur:
            if request.method == 'POST':
                if session.get('role') != 'admin': return jsonify({"error": "Unauthorized"}), 403
                cur.execute("INSERT INTO settings (key, value) VALUES ('wallpaper', %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (request.json['url'],))
                return jsonify({"success": True})
            else:
                cur.execute("SELECT value FROM settings WHERE key = 'wallpaper'")
                row = cur.fetchone()
                return jsonify({"url": row['value'] if row else "https://images.unsplash.com/photo-1555255707-c07966088b7b?q=80&w=2070&auto=format&fit=crop"})

# --- Rating System ---
@app.route('/api/ratings', methods=['POST', 'GET'])
def handle_ratings():
    with get_db() as conn:
        with conn.cursor() as cur:
            if request.method == 'POST':
                data = request.json
                cur.execute("INSERT INTO ratings (subject_name, image_data, score) VALUES (%s, %s, %s)", (data['subject'], data['image'], data['score']))
                return jsonify({"success": True})
            elif request.method == 'GET':
                cur.execute("SELECT id, subject_name, score FROM ratings ORDER BY id DESC")
                return jsonify(cur.fetchall())

# --- CSV Export ---
@app.route('/api/export_csv')
def export_csv():
    if session.get('role') != 'admin': return "Unauthorized", 403
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, subject_name, score FROM ratings")
            rows = cur.fetchall()
            
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'Subject Name', 'Score'])
    for r in rows:
        cw.writerow([r['id'], r['subject_name'], r['score']])
    
    return send_file(StringIO(si.getvalue()), mimetype='text/csv', as_attachment=True, download_name='ratings_export.csv')

@app.route('/')
def home(): return app.send_static_file('login.html')

if __name__ == '__main__':
    app.run(port=int(os.getenv("PORT", 5000)))
