from flask import Flask, request, jsonify, send_from_directory
import json
from flask_cors import CORS
import os
import sqlite3
import random
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, auth
from dotenv import load_dotenv

# Load environment variables
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)

# Define the root directory (where the HTML files are)
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB_PATH = os.path.join(os.path.dirname(__file__), 'civix.db')
MESSAGES_DIR = os.path.join(os.path.dirname(__file__), 'messages')
if not os.path.exists(MESSAGES_DIR):
    os.makedirs(MESSAGES_DIR)
MASTER_PASSWORD = "old_password" # Hardcoded per user request, can be moved to .env

print(f"DEBUG: ROOT_DIR is {ROOT_DIR}")
print(f"DEBUG: DB_PATH is {DB_PATH}")

app = Flask(__name__, static_folder='../', static_url_path='')
CORS(app)

# --- DATABASE INITIALIZATION ---

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create Users Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT,
            email TEXT UNIQUE,
            name TEXT,
            picture TEXT,
            role TEXT,
            status TEXT,
            password TEXT,
            createdAt TEXT,
            lastLogin TEXT
        )
    ''')
    
    # Create Surveys Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS surveys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            size TEXT,
            loc TEXT,
            emp TEXT,
            cli TEXT,
            cliNum TEXT,
            area TEXT,
            instrument TEXT,
            scaleFactor TEXT,
            tempC TEXT,
            date TEXT,
            time TEXT,
            fileName TEXT,
            filePath TEXT,
            createdBy TEXT,
            createdAt TEXT,
            updatedAt TEXT
        )
    ''')

    # Create Callback Requests Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS callback_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            phone TEXT,
            email TEXT,
            message TEXT,
            status TEXT DEFAULT 'New',
            createdAt TEXT
        )
    ''')
    
    # Create Change Requests (Tokens) Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS change_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            surveyId INTEGER,
            fieldName TEXT,
            oldValue TEXT,
            newValue TEXT,
            requestedBy TEXT,
            status TEXT DEFAULT 'Pending',
            createdAt TEXT
        )
    ''')
    
    conn.commit()

    # --- MIGRATIONS: add new columns to existing tables safely ---
    existing_cols = [row[1] for row in cursor.execute("PRAGMA table_info(surveys)").fetchall()]
    if 'cliNum' not in existing_cols:
        cursor.execute("ALTER TABLE surveys ADD COLUMN cliNum TEXT DEFAULT ''")
    if 'password' not in [row[1] for row in cursor.execute("PRAGMA table_info(users)").fetchall()]:
        cursor.execute("ALTER TABLE users ADD COLUMN password TEXT DEFAULT ''")
    
    if 'instrument' not in existing_cols:
        cursor.execute("ALTER TABLE surveys ADD COLUMN instrument TEXT DEFAULT 'Total Station'")
    if 'scaleFactor' not in existing_cols:
        cursor.execute("ALTER TABLE surveys ADD COLUMN scaleFactor TEXT DEFAULT '1.0000'")
    if 'tempC' not in existing_cols:
        cursor.execute("ALTER TABLE surveys ADD COLUMN tempC TEXT DEFAULT '25'")
    if 'fileName' not in existing_cols:
        cursor.execute("ALTER TABLE surveys ADD COLUMN fileName TEXT")
    if 'filePath' not in existing_cols:
        cursor.execute("ALTER TABLE surveys ADD COLUMN filePath TEXT")
    
    conn.commit()
    print("Migration: Updated surveys table with technical columns.")

    conn.close()
    print(f"SQLite Database initialized at {DB_PATH}")

init_db()

# --- FIREBASE INITIALIZATION ---

try:
    adminsdk_path = os.path.join(os.path.dirname(__file__), 'firebase-adminsdk.json')
    if os.path.exists(adminsdk_path):
        # Local development: use JSON file
        cred = credentials.Certificate(adminsdk_path)
        firebase_admin.initialize_app(cred)
        print("Firebase Admin SDK initialized from JSON file.")
    elif os.environ.get('FIREBASE_PROJECT_ID'):
        # Production (Render): use environment variables
        private_key = os.environ.get('FIREBASE_PRIVATE_KEY', '').replace('\\n', '\n')
        cred = credentials.Certificate({
            "type": "service_account",
            "project_id": os.environ.get('FIREBASE_PROJECT_ID'),
            "private_key_id": os.environ.get('FIREBASE_PRIVATE_KEY_ID'),
            "private_key": private_key,
            "client_email": os.environ.get('FIREBASE_CLIENT_EMAIL'),
            "client_id": os.environ.get('FIREBASE_CLIENT_ID'),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{os.environ.get('FIREBASE_CLIENT_EMAIL')}"
        })
        firebase_admin.initialize_app(cred)
        print("Firebase Admin SDK initialized from environment variables.")
    else:
        print("CRITICAL: No Firebase credentials found (no JSON file or env vars).")
except Exception as e:
    print(f"ERROR: Firebase Admin SDK failed to initialize: {e}")

# --- SECURITY DECORATOR ---
from functools import wraps

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        id_token = request.headers.get('Authorization')
        if not id_token:
            return jsonify({"message": "Forbidden: No token provided"}), 403
            
        try:
            # Strip 'Bearer ' if present
            if id_token.startswith('Bearer '):
                id_token = id_token[7:]
                
            decoded_token = auth.verify_id_token(id_token)
            request.uid = decoded_token['uid']
            request.email = decoded_token.get('email')
        except Exception as e:
            return jsonify({"message": f"Unauthorized: {str(e)}"}), 401
            
        return f(*args, **kwargs)
    return decorated_function

def row_to_dict(row):
    return dict(row) if row else None

# --- API ROUTES ---

@app.route('/')
def index():
    return send_from_directory(ROOT_DIR, 'index.html')

@app.route('/api/auth/firebase', methods=['POST'])
def firebase_auth():
# ... (rest of the code below)

    try:
        data = request.json
        id_token = data.get('idToken')
        passed_name = data.get('name') # Name from frontend UI
        
        if not id_token:
            return jsonify({"message": "ID Token is required"}), 400
        
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token['uid']
        email = decoded_token.get('email')
        name = decoded_token.get('name') or passed_name or "New User"
        picture = decoded_token.get('picture')

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        
        if not user:
            # Check if this is the first user ever
            is_first = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0
            role = "Admin" if is_first else "User/Creator"
            status = "Approved" if is_first else "Pending"
            now = datetime.utcnow().isoformat()
            
            conn.execute('''
                INSERT INTO users (uid, email, name, picture, role, status, createdAt, lastLogin)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (uid, email, name, picture, role, status, now, now))
            conn.commit()
            user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        else:
            if user['status'] == 'Rejected':
                conn.close()
                return jsonify({"message": "Access denied. Your account request was rejected."}), 403
            
            # Update UID and Last Login
            conn.execute('UPDATE users SET uid = ?, lastLogin = ? WHERE email = ?', 
                         (uid, datetime.utcnow().isoformat(), email))
            conn.commit()

        user_data = row_to_dict(user)
        conn.close()

        if user_data['status'] == 'Pending':
            return jsonify({"message": "Registration received. Waiting for Admin approval.", "status": "Pending", "user": user_data}), 200

        return jsonify({"message": "Successfully authenticated", "user": user_data}), 200
    except Exception as e:
        print(f"Auth error: {e}")
        return jsonify({"message": f"Authentication failed: {str(e)}"}), 401

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "Backend is running",
        "storage": "SQLite",
        "auth_model": "Owner-Centric",
        "static_root": ROOT_DIR
    }), 200

@app.route('/api/surveys', methods=['GET'])
@require_auth
def get_surveys():
    try:
        email = request.args.get('email')
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        
        if not user:
            conn.close()
            return jsonify({"message": "User not found"}), 404
            
        if user['role'] in ['Admin', 'Worker']:
            surveys = conn.execute('SELECT * FROM surveys ORDER BY createdAt DESC').fetchall()
        else:
            surveys = conn.execute('SELECT * FROM surveys WHERE createdBy = ? ORDER BY createdAt DESC', (email,)).fetchall()
            
        result = [row_to_dict(s) for s in surveys]
        conn.close()
        return jsonify(result)
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route('/api/callback', methods=['POST'])
def callback_request():
    try:
        data = request.json
        name = data.get('name')
        phone = data.get('phone')
        email = data.get('email')
        message = data.get('message', '')
        
        if not name or not phone:
            return jsonify({"message": "Name and Phone are required"}), 400
            
        now = datetime.utcnow().isoformat()
        
        # 1. Store in DB
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO callback_requests (name, phone, email, message, createdAt)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, phone, email, message, now))
        conn.commit()
        conn.close()

        # Save to physical message folder as archival backup
        try:
            msg_filename = f"msg_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{name.replace(' ','_')}.json"
            msg_path = os.path.join(MESSAGES_DIR, msg_filename)
            with open(msg_path, 'w') as f:
                json.dump({
                    "name": name, 
                    "phone": phone, 
                    "email": email, 
                    "message": message, 
                    "timestamp": now
                }, f, indent=4)
        except Exception as f_err:
            print(f"DEBUG: Failed to save message file: {f_err}")

        # 2. Try to Send Email (Optional/Simulated)
        owner_email = os.getenv('OWNER_EMAIL', 'shanthiniprinttech@gmail.com')
        smtp_server = os.getenv('SMTP_SERVER')
        smtp_port = os.getenv('SMTP_PORT')
        smtp_user = os.getenv('SMTP_USER')
        smtp_pass = os.getenv('SMTP_PASS')
        
        email_status = "Logged in database"
        
        if smtp_server and smtp_user and smtp_pass:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            try:
                msg = MIMEMultipart()
                msg['From'] = smtp_user
                msg['To'] = owner_email
                msg['Subject'] = f"Callback Request from {name}"
                
                body = f"""
                New Callback Request Received:
                
                Name: {name}
                Phone: {phone}
                Email: {email}
                Message: {message}
                
                Received at: {now}
                """
                msg.attach(MIMEText(body, 'plain'))
                
                with smtplib.SMTP(smtp_server, int(smtp_port or 587)) as server:
                    server.starttls()
                    server.login(smtp_user, smtp_pass)
                    server.send_message(msg)
                
                email_status = "Logged and Email Sent"
            except Exception as e:
                print(f"DEBUG: Email sending failed: {e}")
                email_status = f"Logged, but Email failed: {str(e)}"
        
        return jsonify({
            "message": "Callback request submitted successfully",
            "email_status": email_status
        }), 201
        
    except Exception as e:
        print(f"Error in callback: {e}")
        return jsonify({"message": str(e)}), 500

@app.route('/api/analytics', methods=['GET'])
@require_auth
def get_analytics():
    try:
        conn = get_db_connection()
        
        counts = {
            "total_surveys": conn.execute('SELECT COUNT(*) FROM surveys').fetchone()[0],
            "total_users": conn.execute('SELECT COUNT(*) FROM users').fetchone()[0],
            "pending_users": conn.execute('SELECT COUNT(*) FROM users WHERE status = "Pending"').fetchone()[0],
        }
        
        # Surveys by Month
        monthly = conn.execute('''
            SELECT date as month, COUNT(*) as count 
            FROM surveys 
            GROUP BY date 
            ORDER BY date DESC 
            LIMIT 7
        ''').fetchall()
        
        # Top Locations
        locations = conn.execute('''
            SELECT loc, COUNT(*) as count 
            FROM surveys 
            GROUP BY loc 
            ORDER BY count DESC 
            LIMIT 5
        ''').fetchall()

        conn.close()
        return jsonify({
            "counts": counts,
            "monthly": [dict(m) for m in monthly],
            "locations": [dict(l) for l in locations]
        })
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route('/api/surveys', methods=['POST'])
@require_auth
def add_survey():
    try:
        # Check if it's multipart/form-data (contains file) or JSON
        if request.content_type.startswith('multipart/form-data'):
            data = request.form
            file = request.files.get('file')
        else:
            data = request.json
            file = None

        email = data.get('createdBy')
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        
        if not user:
             conn.close()
             return jsonify({"message": "User not found."}), 403
             
        if user['status'] != 'Approved':
            conn.close()
            return jsonify({"message": "Account not approved."}), 403

        file_name = None
        file_path = None
        
        if file:
            from werkzeug.utils import secure_filename
            file_name = secure_filename(file.filename)
            upload_folder = os.path.join(ROOT_DIR, 'uploads')
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
            
            # Add timestamp to avoid filename collisions
            unique_filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{file_name}"
            file.save(os.path.join(upload_folder, unique_filename))
            file_path = f"/uploads/{unique_filename}"
            file_name = unique_filename

        now = datetime.utcnow().isoformat()
        date = data.get('date', datetime.utcnow().strftime('%Y-%m-%d'))
        time = data.get('time', datetime.utcnow().strftime('%H:%M:%S'))
        
        conn.execute('''
            INSERT INTO surveys (size, loc, emp, cli, cliNum, area, instrument, scaleFactor, tempC, date, time, fileName, filePath, createdBy, createdAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (data['size'], data['loc'], data['emp'], data['cli'], data.get('cliNum', ''), data['area'], data.get('instrument', 'Total Station'), data.get('scaleFactor', '1.0000'), data.get('tempC', '25'), date, time, file_name, file_path, email, now))
        conn.commit()
        conn.close()
        return jsonify({"message": "Survey added successfully"}), 201
    except Exception as e:
        print(f"Error adding survey: {e}")
        return jsonify({"message": str(e)}), 400

@app.route('/api/surveys/<id>', methods=['GET'])
@require_auth
def get_survey(id):
    try:
        conn = get_db_connection()
        survey = conn.execute('SELECT * FROM surveys WHERE id = ?', (id,)).fetchone()
        conn.close()
        if not survey:
            return jsonify({"message": "Survey not found"}), 404
        return jsonify(row_to_dict(survey))
    except Exception as e:
        return jsonify({"message": str(e)}), 400

@app.route('/api/surveys/<id>', methods=['PUT'])
@require_auth
def update_survey(id):
    try:
        # Handle both multipart/form-data and JSON
        if request.content_type and request.content_type.startswith('multipart/form-data'):
            data = request.form
        else:
            data = request.json

        email = data.get('updatedBy')
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        
        if not user:
            conn.close()
            return jsonify({"message": "User not found"}), 404
            
        existing_survey = conn.execute('SELECT * FROM surveys WHERE id = ?', (id,)).fetchone()
        if not existing_survey:
            conn.close()
            return jsonify({"message": "Survey not found"}), 404
            
        # Role check: Only Admin can edit per user request
        if user['role'] != 'Admin':
             conn.close()
             return jsonify({"message": "Only the company master can change stored data."}), 403

        now = datetime.utcnow().isoformat()
        conn.execute('''
            UPDATE surveys SET size=?, loc=?, emp=?, cli=?, cliNum=?, area=?, instrument=?, scaleFactor=?, tempC=?, date=?, time=?, updatedAt=?
            WHERE id=?
        ''', (data['size'], data['loc'], data['emp'], data['cli'], data.get('cliNum', ''), data['area'], data.get('instrument', 'Total Station'), data.get('scaleFactor', '1.0000'), data.get('tempC', '25'), data['date'], data['time'], now, id))
        conn.commit()
        conn.close()
        return jsonify({"message": "Updated successfully"}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 400

@app.route('/api/admin/users/pending', methods=['GET'])
@require_auth
def get_pending_users():
    try:
        admin_email = request.args.get('adminEmail')
        conn = get_db_connection()
        admin = conn.execute('SELECT * FROM users WHERE email = ? AND role = "Admin"', (admin_email,)).fetchone()
        if not admin:
            conn.close()
            return jsonify({"message": "Unauthorized"}), 401
            
        pending = conn.execute('SELECT * FROM users WHERE status = "Pending"').fetchall()
        result = [row_to_dict(u) for u in pending]
        conn.close()
        return jsonify(result)
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route('/api/admin/users/create', methods=['POST'])
@require_auth
def create_employee():
    try:
        data = request.json
        admin_email = data.get('adminEmail')
        
        conn = get_db_connection()
        admin = conn.execute('SELECT * FROM users WHERE email = ? AND role = "Admin"', (admin_email,)).fetchone()
        if not admin:
            conn.close()
            return jsonify({"message": "Unauthorized"}), 401
            
        emp_name = data.get('name')
        emp_email = data.get('email')
        emp_pass = data.get('password')
        emp_role = data.get('role', 'Worker')
        
        # 1. Create in Firebase first so they can actually log in
        try:
            fb_user = auth.create_user(
                email=emp_email,
                password=emp_pass,
                display_name=emp_name
            )
            uid = fb_user.uid
        except Exception as fb_err:
            print(f"Firebase user creation failed: {fb_err}")
            # If user already exists in Firebase but not in our DB, we can still proceed or return error
            if "already exists" in str(fb_err).lower():
                try:
                    fb_user = auth.get_user_by_email(emp_email)
                    uid = fb_user.uid
                except:
                    return jsonify({"message": f"User already exists in Firebase: {str(fb_err)}"}), 400
            else:
                return jsonify({"message": f"Firebase error: {str(fb_err)}"}), 400
            
        now = datetime.utcnow().isoformat()
        conn.execute('''
            INSERT INTO users (uid, email, name, role, status, password, createdAt, lastLogin)
            VALUES (?, ?, ?, ?, "Approved", ?, ?, ?)
        ''', (uid, emp_email, emp_name, emp_role, emp_pass, now, now))
        conn.commit()
        conn.close()
        return jsonify({"message": f"Employee {emp_name} created successfully in both System & Firebase"}), 201
    except Exception as e:
        return jsonify({"message": str(e)}), 400

@app.route('/api/admin/users/approve', methods=['POST'])
@require_auth
def approve_user():
    try:
        data = request.json
        admin_email = data.get('adminEmail')
        user_email = data.get('userEmail')
        role = data.get('role', 'User/Creator')
        
        conn = get_db_connection()
        admin = conn.execute('SELECT * FROM users WHERE email = ? AND role = "Admin"', (admin_email,)).fetchone()
        if not admin:
            conn.close()
            return jsonify({"message": "Unauthorized"}), 401
            
        conn.execute('UPDATE users SET status = "Approved", role = ? WHERE email = ?', (role, user_email))
        conn.commit()
        conn.close()
        return jsonify({"message": f"User {user_email} approved as {role}"}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 400

@app.route('/api/admin/users/all', methods=['GET'])
@require_auth
def get_all_users():
    try:
        admin_email = request.args.get('adminEmail')
        conn = get_db_connection()
        admin = conn.execute('SELECT * FROM users WHERE email = ? AND role = "Admin"', (admin_email,)).fetchone()
        
        if not admin:
            conn.close()
            return jsonify({"message": "Unauthorized"}), 401
            
        users = conn.execute('SELECT * FROM users ORDER BY createdAt DESC').fetchall()
        result = [row_to_dict(u) for u in users]
        conn.close()
        return jsonify(result)
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route('/api/admin/users/delete', methods=['POST'])
@require_auth
def delete_user():
    try:
        data = request.json
        admin_email = data.get('adminEmail')
        target_email = data.get('targetEmail')
        
        if target_email == admin_email:
            return jsonify({"message": "Cannot delete your own admin account"}), 400
            
        conn = get_db_connection()
        admin = conn.execute('SELECT * FROM users WHERE email = ? AND role = "Admin"', (admin_email,)).fetchone()
        if not admin:
            conn.close()
            return jsonify({"message": "Unauthorized"}), 401
            
        # Optional: Delete from Firebase too
        try:
            target_user = conn.execute('SELECT uid FROM users WHERE email = ?', (target_email,)).fetchone()
            if target_user and target_user['uid']:
                auth.delete_user(target_user['uid'])
        except Exception as fb_err:
            print(f"Firebase delete error: {fb_err}")
            
        conn.execute('DELETE FROM users WHERE email = ?', (target_email,))
        conn.commit()
        conn.close()
        return jsonify({"message": f"User {target_email} has been removed from the system"}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 400

# --- TICKET / CHANGE REQUEST SYSTEM ---

@app.route('/api/tickets/create', methods=['POST'])
@require_auth
def create_ticket():
    try:
        if request.content_type and request.content_type.startswith('multipart/form-data'):
            data = request.form
            file = request.files.get('file')
        else:
            data = request.json
            file = None

        survey_id = data.get('surveyId')
        requested_by = data.get('requestedBy')
        
        changes_json = data.get('changes')
        if changes_json:
            changes = json.loads(changes_json)
        else:
            changes = [{
                "fieldName": data.get('fieldName'),
                "oldValue": data.get('oldValue'),
                "newValue": data.get('newValue')
            }] if data.get('fieldName') else []

        if not survey_id or (not changes and not file):
            return jsonify({"message": "Incomplete request"}), 400
            
        now = datetime.utcnow().isoformat()
        conn = get_db_connection()
        
        for change in changes:
            if not change.get('fieldName'):
                continue
            conn.execute('''
                INSERT INTO change_requests (surveyId, fieldName, oldValue, newValue, requestedBy, createdAt)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (survey_id, change['fieldName'], change.get('oldValue'), change.get('newValue'), requested_by, now))

        file_msg = ""
        if file:
            from werkzeug.utils import secure_filename
            file_name = secure_filename(file.filename)
            upload_folder = os.path.join(ROOT_DIR, 'uploads')
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
            
            unique_filename = f"ticket_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{file_name}"
            file_path = f"/uploads/{unique_filename}"
            file.save(os.path.join(upload_folder, unique_filename))
            
            conn.execute('''
                INSERT INTO change_requests (surveyId, fieldName, oldValue, newValue, requestedBy, createdAt)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (survey_id, "file", "Existing Document", json.dumps({"fileName": file_name, "filePath": file_path}), requested_by, now))
            file_msg = " and file upload"

        conn.commit()
        conn.close()
        return jsonify({"message": f"Change request(s){file_msg} submitted for approval"}), 201
    except Exception as e:
        print(f"Error creating ticket: {e}")
        return jsonify({"message": str(e)}), 500

@app.route('/api/tickets/all', methods=['GET'])
@require_auth
def get_tickets():
    try:
        admin_email = request.args.get('adminEmail')
        conn = get_db_connection()
        admin = conn.execute('SELECT * FROM users WHERE email = ? AND role = "Admin"', (admin_email,)).fetchone()
        
        if not admin:
            conn.close()
            return jsonify({"message": "Unauthorized"}), 401
            
        # Get pending tickets with survey details (e.g., client name for context)
        tickets = conn.execute('''
            SELECT t.*, s.cli as clientName, s.loc as location 
            FROM change_requests t
            JOIN surveys s ON t.surveyId = s.id
            ORDER BY t.createdAt DESC
        ''').fetchall()
        
        result = [row_to_dict(t) for t in tickets]
        conn.close()
        return jsonify(result)
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route('/api/tickets/approve', methods=['POST'])
@require_auth
def approve_ticket():
    try:
        data = request.json
        admin_email = data.get('adminEmail')
        ticket_id = data.get('ticketId')
        
        conn = get_db_connection()
        admin = conn.execute('SELECT * FROM users WHERE email = ? AND role = "Admin"', (admin_email,)).fetchone()
        if not admin:
            conn.close()
            return jsonify({"message": "Unauthorized"}), 401
            
        # 1. Get Ticket Details
        ticket = conn.execute('SELECT * FROM change_requests WHERE id = ?', (ticket_id,)).fetchone()
        if not ticket or ticket['status'] != 'Pending':
            conn.close()
            return jsonify({"message": "Invalid or already processed ticket"}), 400
            
        # 2. Update Survey Log
        survey_id = ticket['surveyId']
        field = ticket['fieldName']
        new_val = ticket['newValue']
        
        # Security: whitelist allowed fields to prevent SQL injection or accidents
        allowed_fields = ['size', 'loc', 'emp', 'cli', 'cliNum', 'area', 'instrument', 'scaleFactor', 'tempC', 'date', 'time', 'file']
        if field not in allowed_fields:
            conn.close()
            return jsonify({"message": "Field modification restricted"}), 403
            
        if field == 'file':
            try:
                file_info = json.loads(new_val)
                file_name = file_info.get('fileName')
                file_path = file_info.get('filePath')
                conn.execute('UPDATE surveys SET fileName = ?, filePath = ? WHERE id = ?', (file_name, file_path, survey_id))
            except Exception as jerr:
                print(f"Error parsing file JSON: {jerr}")
        else:
            conn.execute(f'UPDATE surveys SET {field} = ? WHERE id = ?', (new_val, survey_id))
        
        # 3. Mark Ticket as Approved
        conn.execute('UPDATE change_requests SET status = "Approved" WHERE id = ?', (ticket_id,))
        
        conn.commit()
        conn.close()
        return jsonify({"message": f"Change approved! Survey ID {survey_id} has been updated."}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route('/api/tickets/history', methods=['GET'])
@require_auth
def get_survey_history():
    try:
        survey_id = request.args.get('surveyId')
        conn = get_db_connection()
        # Get all approved change requests for this specific survey lot
        history = conn.execute('''
            SELECT * FROM change_requests 
            WHERE surveyId = ? AND status = 'Approved'
            ORDER BY createdAt DESC
        ''', (survey_id,)).fetchall()
        
        result = [row_to_dict(h) for h in history]
        conn.close()
        return jsonify(result)
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route('/api/messages/all', methods=['GET'])
@require_auth
def get_all_messages():
    try:
        admin_email = request.args.get('adminEmail')
        conn = get_db_connection()
        admin = conn.execute('SELECT * FROM users WHERE email = ? AND role = "Admin"', (admin_email,)).fetchone()
        
        if not admin:
            conn.close()
            return jsonify({"message": "Unauthorized"}), 401
            
        messages = conn.execute('SELECT * FROM callback_requests ORDER BY createdAt DESC').fetchall()
        result = [row_to_dict(m) for m in messages]
        conn.close()
        return jsonify(result)
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route('/api/profile/update', methods=['POST'])
@require_auth
def update_profile():
    try:
        data = request.json
        email = data.get('email')
        new_name = data.get('name')
        
        if not email:
            return jsonify({"message": "Email is required"}), 400
            
        conn = get_db_connection()
        conn.execute('UPDATE users SET name = ? WHERE email = ?', (new_name, email))
        conn.commit()
        
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()
        
        if user:
            return jsonify({"message": "Profile updated successfully", "user": row_to_dict(user)}), 200
        else:
            return jsonify({"message": "User not found"}), 404
    except Exception as e:
        return jsonify({"message": str(e)}), 400

@app.route('/api/users', methods=['POST'])
def save_user():
    try:
        user_data = request.json
        email = user_data.get('email')
        password = user_data.get('password')
        
        conn = get_db_connection()
        existing_user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        
        if existing_user:
            # Login check (basic for now, in prod use hash)
            # If owner, check master pass? Or just let them in if approved.
            user_dict = row_to_dict(existing_user)
            conn.close()
            return jsonify({"message": "User logged in", "user": user_dict}), 200
        
        # New Registration: ONLY allowed if it's the very first user (Owner)
        # AND they use the MASTER_PASSWORD
        user_count = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        
        if user_count == 0:
            if password == MASTER_PASSWORD:
                role = "Admin"
                status = "Approved"
                now = datetime.utcnow().isoformat()
                
                conn.execute('''
                    INSERT INTO users (email, name, role, status, createdAt, lastLogin)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (email, user_data.get('name', 'Company Owner'), role, status, now, now))
                conn.commit()
                
                user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
                user_dict = row_to_dict(user)
                conn.close()
                return jsonify({"message": "Owner registered successfully", "user": user_dict}), 201
            else:
                conn.close()
                return jsonify({"message": "Invalid master password for owner registration."}), 401
        
        conn.close()
        return jsonify({"message": "Public registration is disabled. Please contact the site owner."}), 403
    except Exception as e:
        return jsonify({"message": str(e)}), 400

@app.route('/<path:path>')
def serve_static(path):
    if os.path.exists(os.path.join(ROOT_DIR, path)):
        return send_from_directory(ROOT_DIR, path)
    return send_from_directory(ROOT_DIR, 'index.html')

if __name__ == '__main__':
    import socket
    
    port = int(os.getenv('PORT', 5001))
    
    # Find an open port automatically if the current one is in use
    def is_port_open(p):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', p)) != 0
            
    while not is_port_open(port) and port < 5050:
        print(f"Port {port} is in use, trying next...")
        port += 1
        
    print(f"Starting API Server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
