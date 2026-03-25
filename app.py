import os
from flask import Flask, request, jsonify, send_from_directory, session, redirect
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder='public', static_url_path='')
app.secret_key = os.getenv("SECRET_KEY", "fallback-secret-key")
DATABASE_URL = os.getenv("DATABASE_URL")

UPLOAD_FOLDER = os.path.join('public', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def get_db():
    db_url = DATABASE_URL.replace("postgres://", "postgresql://")
    return psycopg2.connect(db_url)

# ==========================================
# 1. PAGE ROUTES (Serving HTML)
# ==========================================
@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect('/login.html')
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(app.static_folder, path)

# ==========================================
# 2. AUTHENTICATION API
# ==========================================
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    role_type = data.get('role_type') # 'user' or 'admin' (From your UI toggle)

    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM Users WHERE username = %s AND role = %s", (username, role_type.lower()))
        user = cur.fetchone()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['role'] = user['role']
            session['username'] = user['username']
            return jsonify({"success": True, "redirect": "/admin.html" if user['role'] == 'admin' else "/index.html"})
        else:
            return jsonify({"success": False, "message": "Invalid credentials or wrong role selected."}), 401
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if 'conn' in locals(): conn.close()

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"success": True})

# ==========================================
# 3. ADMIN & SETTINGS API
# ==========================================
@app.route('/api/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'GET':
        try:
            conn = get_db()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT key, value FROM Settings")
            settings = {row['key']: row['value'] for row in cur.fetchall()}
            return jsonify(settings)
        finally:
            if 'conn' in locals(): conn.close()
            
    if request.method == 'POST':
        if session.get('role') != 'admin':
            return jsonify({"error": "Unauthorized"}), 403
            
        data = request.json
        try:
            conn = get_db()
            cur = conn.cursor()
            for key, value in data.items():
                cur.execute("UPDATE Settings SET value = %s WHERE key = %s", (value, key))
            conn.commit()
            return jsonify({"success": True})
        finally:
            if 'conn' in locals(): conn.close()

# ==========================================
# 4. APP LOGIC (Uploads & Subjects)
# ==========================================
@app.route('/api/analyze', methods=['POST'])
def upload_photos():
    if 'user_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    
    subject_name = request.form.get('subject_name', 'Unknown')
    files = request.files.getlist('images')
    
    if not files or files[0].filename == '':
        return jsonify({"error": "No files uploaded"}), 400

    try:
        conn = get_db()
        cur = conn.cursor()
        
        # 1. Create the Subject in the database
        cur.execute("INSERT INTO Subjects (name) VALUES (%s) RETURNING id", (subject_name,))
        subject_id = cur.fetchone()[0]
        
        # 2. Save all images
        saved_paths = []
        for file in files:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            db_path = f"/uploads/{filename}"
            saved_paths.append(db_path)
            
            cur.execute("INSERT INTO Uploads (subject_id, file_path) VALUES (%s, %s)", (subject_id, db_path))
            
        conn.commit()
        return jsonify({"success": True, "subject_id": subject_id, "images_saved": len(saved_paths)})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if 'conn' in locals(): conn.close()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)