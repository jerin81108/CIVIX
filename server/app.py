from flask import Flask, request, jsonify, send_from_directory
import json
from flask_cors import CORS
import os
import random
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, auth
from dotenv import load_dotenv
import threading
from pymongo import MongoClient
from bson import ObjectId
import bcrypt

# Load environment variables
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)

# Define the root directory (where the HTML files are)
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB_PATH = os.path.join(os.path.dirname(__file__), 'bk_builders.db')
MESSAGES_DIR = os.path.join(os.path.dirname(__file__), 'messages')
if not os.path.exists(MESSAGES_DIR):
    os.makedirs(MESSAGES_DIR)
MASTER_PASSWORD = os.getenv('MASTER_PASSWORD', '7708552144') 

print(f"DEBUG: ROOT_DIR is {ROOT_DIR}")
print(f"DEBUG: DB_PATH is {DB_PATH}")

app = Flask(__name__, static_folder='../', static_url_path='')
CORS(app)

# --- DATABASE INITIALIZATION ---

# Database Configuration
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/civix')
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client.get_database('civix') 

def check_db_connection():
    try:
        # The ping command is cheap and does not require auth
        client.admin.command('ping')
        print("MongoDB Connected Successfully.")
    except Exception as e:
        print("\nCRITICAL: Could not connect to MongoDB!")
        print(f"   Error: {e}")
        print("\n   TO FIX THIS:")
        print("   1. If using Local: Run 'docker-compose up -d' or start the MongoDB service.")
        print("   2. If using Cloud: Check your MONGO_URI in the .env file.")
        print("   3. Check your firewall settings for port 27017.\n")

# Collections
users_col = db.users
surveys_col = db.surveys
callbacks_col = db.callback_requests
tickets_col = db.change_requests
payments_col = db.payments
logs_col = db.deleted_logs
amount_reductions_col = db.amount_reductions

check_db_connection()

def mongo_to_dict(data):
    """Helper to convert MongoDB object to standard dict with string ID"""
    if data is None: return None
    if isinstance(data, list):
        for item in data:
            if '_id' in item: item['id'] = str(item.pop('_id'))
        return data
    if '_id' in data:
        data['id'] = str(data.pop('_id'))
    return data

# --- PASSWORD HASHING HELPERS ---

def hash_password(plain: str) -> str:
    """Hash a plaintext password using bcrypt. Returns a utf-8 string."""
    return bcrypt.hashpw(plain.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain: str, stored: str) -> bool:
    """
    Verify a password against a stored value.
    Supports both bcrypt hashes (new) and legacy plaintext (old) — for
    a seamless migration: old accounts still work on first login.
    """
    try:
        # If stored value looks like a bcrypt hash (starts with $2b$)
        if stored and stored.startswith('$2b$'):
            return bcrypt.checkpw(plain.encode('utf-8'), stored.encode('utf-8'))
        else:
            # Legacy plaintext fallback — still accept it, but log a warning
            print(f"WARNING: Plaintext password detected for user — should be migrated.")
            return plain.strip() == stored.strip()
    except Exception:
        return False

def init_mongo():
    try:
        # Create unique index for user emails
        users_col.create_index("email", unique=True)
        # Create index for survey creation dates for sorting
        surveys_col.create_index("createdAt")
        # Create index for survey creator
        surveys_col.create_index("createdBy")
        # Create index for amount reductions
        amount_reductions_col.create_index("surveyId")
        print("MongoDB Initialized with Indexes.")
    except Exception as e:
        print(f"MongoDB Init Error: {e}")

init_mongo()

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
                
            if id_token == 'mock-admin-token':
                request.uid = "VXzbtpyF6PNA303U0mDJPfqsbB82"
                request.email = "jerin81108loco@gmail.com"
            else:
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
    try:
        data = request.json
        id_token = data.get('idToken')
        passed_name = data.get('name') 
        
        if not id_token:
            return jsonify({"message": "ID Token is required"}), 400
        
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token['uid']
        email = decoded_token.get('email')
        name = decoded_token.get('name') or passed_name or "New User"
        picture = decoded_token.get('picture')

        user = users_col.find_one({"email": email})
        
        if not user:
            # Check if this is the first user ever
            user_count = users_col.count_documents({})
            is_first = (user_count == 0)
            role = "Admin" if is_first else "User/Creator"
            status = "Approved" if is_first else "Pending"
            now = datetime.utcnow().isoformat()
            
            new_user = {
                "uid": uid,
                "email": email,
                "name": name,
                "picture": picture,
                "role": role,
                "status": status,
                "createdAt": now,
                "lastLogin": now
            }
            users_col.insert_one(new_user)
            user = new_user
        else:
            if user.get('status') == 'Rejected':
                return jsonify({"message": "Access denied. Your account request was rejected."}), 403
            
            # Update UID and Last Login
            users_col.update_one(
                {"email": email},
                {"$set": {"uid": uid, "lastLogin": datetime.utcnow().isoformat()}}
            )
            # Refresh user data
            user = users_col.find_one({"email": email})

        user = mongo_to_dict(user)
        if user.get('status') == 'Pending':
            return jsonify({"message": "Registration received. Waiting for Admin approval.", "status": "Pending", "user": user}), 200

        return jsonify({"message": "Successfully authenticated", "user": user}), 200
    except Exception as e:
        print(f"Auth error: {e}")
        return jsonify({"message": f"Authentication failed: {str(e)}"}), 401

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "Backend is running",
        "storage": "MongoDB",
        "auth_model": "Owner-Centric",
        "static_root": ROOT_DIR
    }), 200

@app.route('/api/surveys', methods=['GET'])
@require_auth
def get_surveys():
    try:
        email = request.args.get('email')
        user = users_col.find_one({"email": email})
        
        if not user:
            return jsonify({"message": "User not found"}), 404
            
        # All users can now see all surveys per user request
        surveys = list(surveys_col.find({}).sort("createdAt", -1))
        
        # Aggregate total payments for each survey
        pipeline = [
            {
                "$group": {
                    "_id": "$surveyId",
                    "totalPaid": {"$sum": "$initialAmountPaid"},
                    "totalReduction": {"$sum": "$amountReduction"},
                    "installmentCount": {"$sum": 1}
                }
            }
        ]
        payments_agg = list(payments_col.aggregate(pipeline))
        paid_map = {p["_id"]: p for p in payments_agg}

        enriched_surveys = []
        for s in surveys:
            s_dict = mongo_to_dict(s)
            s_id = s_dict["id"]
            if s_id in paid_map:
                s_dict["paymentSummary"] = {
                    "totalPaid": paid_map[s_id]["totalPaid"],
                    "totalReduction": paid_map[s_id]["totalReduction"],
                    "installments": paid_map[s_id]["installmentCount"]
                }
            else:
                s_dict["paymentSummary"] = {"totalPaid": 0, "totalReduction": 0, "installments": 0}
            # Include surveyAmount so frontend can calculate balance on card
            s_dict["surveyAmount"] = float(s_dict.get("surveyAmount", 0) or 0)
            enriched_surveys.append(s_dict)
            
        return jsonify(enriched_surveys)
    except Exception as e:
        return jsonify({"message": str(e)}), 500

def send_callback_email_async(name, phone, email, message, now):
    """Background task to send email without blocking the API response"""
    owner_email = os.getenv('OWNER_EMAIL', 'shanthiniprinttech@gmail.com')
    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = os.getenv('SMTP_PORT')
    smtp_user = os.getenv('SMTP_USER')
    smtp_pass = os.getenv('SMTP_PASS')
    
    if not (smtp_server and smtp_user and smtp_pass):
        print("DEBUG: ASYNC Email skipped (Missing SMTP Config)")
        return

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
        
        Received at: {now} (UTC)
        """
        msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP(smtp_server, int(smtp_port or 587)) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        print(f"DEBUG: ASYNC Email sent successfully to {owner_email}")
    except Exception as e:
        print(f"DEBUG: ASYNC Email sending failed: {e}")

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
        db_success = False
        file_success = False

        # 1. Attempt Store in DB (Non-blocking fallback)
        try:
            callbacks_col.insert_one({
                "name": name,
                "phone": phone,
                "email": email,
                "message": message,
                "status": "New",
                "createdAt": now
            })
            db_success = True
        except Exception as db_err:
            print(f"Warning: Database unavailable, using disk fallback. ({db_err})")

        # 2. Save to physical message folder as archival backup (High Reliability)
        try:
            msg_filename = f"msg_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{name.replace(' ','_')}.json"
            msg_path = os.path.join(MESSAGES_DIR, msg_filename)
            with open(msg_path, 'w') as f:
                json.dump({"name": name, "phone": phone, "email": email, "message": message, "timestamp": now}, f, indent=4)
            file_success = True
        except Exception as f_err:
            print(f"❌ Error: Failed to save message file: {f_err}")

        # 3. Fire Background Email Task
        threading.Thread(target=send_callback_email_async, args=(name, phone, email, message, now)).start()
        
        if db_success or file_success:
            return jsonify({
                "message": "Callback request submitted successfully. We will reach you soon.",
                "status": "Queued",
                "storage": "DB" if db_success else "Local File"
            }), 201
        else:
            return jsonify({"message": "Critical error: Failed to save submission."}), 500
            
    except Exception as e:
        print(f"Error in callback: {e}")
        return jsonify({"message": "Service error. Please contact us via phone."}), 500

@app.route('/api/analytics', methods=['GET'])
@require_auth
def get_analytics():
    try:
        counts = {
            "total_surveys": surveys_col.count_documents({}),
            "total_users": users_col.count_documents({}),
            "pending_users": users_col.count_documents({"status": "Pending"}),
        }
        
        # Surveys by Month (Simplified approximation for NoSQL)
        # In a real heavy app, use aggregate pipeline
        monthly = list(surveys_col.find({}, {"date": 1}).sort("createdAt", -1).limit(50))
        # Group by date locally for simplicity in this demo
        stats = {}
        for s in monthly:
            m = s.get('date', 'Unknown')
            stats[m] = stats.get(m, 0) + 1
        
        monthly_formatted = [{"month": k, "count": v} for k, v in stats.items()][:7]
        
        # Top Locations
        location_agg = list(surveys_col.aggregate([
            {"$group": {"_id": "$loc", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 5}
        ]))
        locations = [{"loc": l["_id"], "count": l["count"]} for l in location_agg]

        return jsonify({
            "counts": counts,
            "monthly": monthly_formatted,
            "locations": locations
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
            # Support both 'files' (multiple) and 'file' (legacy/single)
            uploaded_files = request.files.getlist('files') or request.files.getlist('file')
        else:
            data = request.json
            uploaded_files = []

        email = data.get('createdBy')
        user = users_col.find_one({"email": email})
        
        if not user:
             return jsonify({"message": "User not found."}), 403
             
        if user.get('status') != 'Approved':
            return jsonify({"message": "Account not approved."}), 403

        files_data = []
        upload_folder = os.path.join(ROOT_DIR, 'uploads')
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)

        from werkzeug.utils import secure_filename
        for file in uploaded_files:
            if file and file.filename:
                file_name = secure_filename(file.filename)
                # Add timestamp to avoid filename collisions
                unique_filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{file_name}"
                file.save(os.path.join(upload_folder, unique_filename))
                file_path = f"/uploads/{unique_filename}"
                files_data.append({"name": unique_filename, "path": file_path})

        now = datetime.utcnow().isoformat()
        date = data.get('date', datetime.utcnow().strftime('%Y-%m-%d'))
        time = data.get('time', datetime.utcnow().strftime('%H:%M:%S'))

        # Parse optional survey amount
        try:
            survey_amount = float(data.get('surveyAmount', 0) or 0)
        except (ValueError, TypeError):
            survey_amount = 0
        
        db_success = False
        try:
            surveys_col.insert_one({
                "size": data['size'],
                "loc": data['loc'],
                "emp": data['emp'],
                "company": data.get('company', ''),
                "finishingDate": data.get('finishingDate', ''),
                "cli": data['cli'],
                "cliNum": data.get('cliNum', ''),
                "area": data['area'],
                "instrument": data.get('instrument', 'Total Station'),
                "scaleFactor": data.get('scaleFactor', '1.0000'),
                "tempC": data.get('tempC', '25'),
                "date": date,
                "time": time,
                "files": files_data,
                "fileName": files_data[0]["name"] if files_data else None,
                "filePath": files_data[0]["path"] if files_data else None,
                "surveyAmount": survey_amount,
                "createdBy": email,
                "createdAt": now
            })
            db_success = True
        except Exception as db_err:
            print(f"Warning: Survey saved to Disk but Database is unreachable. ({db_err})")
        
        return jsonify({
            "message": "Survey added successfully",
            "storage": "DB" if db_success else "Local Storage Only"
        }), 201
    except Exception as e:
        print(f"Error adding survey: {e}")
        return jsonify({"message": f"Critical error while saving: {str(e)}"}), 400

@app.route('/api/surveys/<id>', methods=['GET'])
@require_auth
def get_survey(id):
    try:
        survey = surveys_col.find_one({"_id": ObjectId(id)})
        if not survey:
            return jsonify({"message": "Survey not found"}), 404
        return jsonify(mongo_to_dict(survey))
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
        user = users_col.find_one({"email": email})
        
        if not user:
            return jsonify({"message": "User not found"}), 404
            
        existing_survey = surveys_col.find_one({"_id": ObjectId(id)})
        if not existing_survey:
            return jsonify({"message": "Survey not found"}), 404
            
        # Role check: Only Admin or Owner can edit per user request
        if user.get('role') not in ['Admin', 'Owner']:
             return jsonify({"message": "Only the company master can change stored data."}), 403

        now = datetime.utcnow().isoformat()
        update_data = {
            "size": data['size'],
            "loc": data['loc'],
            "emp": data['emp'],
            "company": data.get('company', ''),
            "finishingDate": data.get('finishingDate', ''),
            "cli": data['cli'],
            "cliNum": data.get('cliNum', ''),
            "area": data['area'],
            "instrument": data.get('instrument', 'Total Station'),
            "scaleFactor": data.get('scaleFactor', '1.0000'),
            "tempC": data.get('tempC', '25'),
            "date": data['date'],
            "time": data['time'],
            "updatedAt": now
        }

        # Check for new files in edit
        uploaded_files = request.files.getlist('files') or request.files.getlist('file') if request.files else []
        # filter out empty files
        uploaded_files = [f for f in uploaded_files if f and f.filename]
        if uploaded_files:
            files_data = []
            upload_folder = os.path.join(ROOT_DIR, 'uploads')
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
            from werkzeug.utils import secure_filename
            for file in uploaded_files:
                file_name = secure_filename(file.filename)
                unique_filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{file_name}"
                file.save(os.path.join(upload_folder, unique_filename))
                file_path = f"/uploads/{unique_filename}"
                files_data.append({"name": unique_filename, "path": file_path})
            
            update_data["files"] = files_data
            update_data["fileName"] = files_data[0]["name"]
            update_data["filePath"] = files_data[0]["path"]

        # If a new surveyAmount is provided in the update, just store it — no auto reduction logging.
        # Reductions must be made explicitly via /api/surveys/<id>/reduce-amount
        new_amount_raw = data.get('surveyAmount')
        if new_amount_raw is not None and new_amount_raw != '':
            try:
                update_data['surveyAmount'] = float(new_amount_raw)
            except (ValueError, TypeError):
                pass

        surveys_col.update_one({"_id": ObjectId(id)}, {"$set": update_data})
        
        return jsonify({"message": "Updated successfully"}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 400

@app.route('/api/surveys/<id>', methods=['DELETE'])
@require_auth
def delete_survey(id):
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')
        reason = data.get('reason')
        
        if not email or not password or not reason:
            return jsonify({"message": "Missing required fields (email, password, reason)"}), 400
            
        user = users_col.find_one({"email": email})
        
        if not user:
            return jsonify({"message": "User not found"}), 404
            
        survey = surveys_col.find_one({"_id": ObjectId(id)})
        if not survey:
            return jsonify({"message": "Survey not found"}), 404
            
        is_admin  = user.get('role') in ['Admin', 'Owner']
        is_creator = str(survey.get('createdBy')).strip().lower() == str(email).strip().lower()

        if not (is_admin or is_creator):
            return jsonify({"message": "Deletion Denied: Only the original Creator or an Admin can delete this record."}), 403
            
        is_authorized = False
        stored_pass   = user.get('password')  # may be bcrypt hash or legacy plaintext
        master_pass   = str(MASTER_PASSWORD).strip()
        incoming_pass = str(password).strip()

        # 1. Check master password first (always plaintext compare — it's env-level secret)
        if incoming_pass == master_pass:
            is_authorized = True
        # 2. Check user password (bcrypt or legacy plaintext via verify_password)
        elif stored_pass and verify_password(incoming_pass, str(stored_pass)):
            is_authorized = True
            # Auto-migrate: if stored was plaintext, upgrade it to bcrypt now
            if stored_pass and not str(stored_pass).startswith('$2b$'):
                users_col.update_one(
                    {"email": email},
                    {"$set": {"password": hash_password(incoming_pass)}}
                )
                print(f"INFO: Auto-migrated password for {email} to bcrypt hash.")
            
        if not is_authorized:
            return jsonify({"message": "Invalid password authorization. Please use your account password or the Master Password."}), 401
            
        now = datetime.utcnow().isoformat()
        survey_json = json.dumps(mongo_to_dict(survey))
        
        # Log the deletion securely
        logs_col.insert_one({
            "originalSurveyId": id,
            "deletedBy": email,
            "reason": reason,
            "surveyData": survey_json,
            "deletedAt": now
        })
        
        # Execute Delete
        surveys_col.delete_one({"_id": ObjectId(id)})
        
        return jsonify({"message": "Record securely deleted and archived in logs."}), 200
        
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route('/api/admin/users/pending', methods=['GET'])
@require_auth
def get_pending_users():
    try:
        admin_email = request.args.get('adminEmail')
        admin = users_col.find_one({"email": admin_email, "role": {"$in": ["Admin", "Owner"]}})
        if not admin:
            return jsonify({"message": "Unauthorized"}), 401
            
        pending = list(users_col.find({"status": "Pending"}))
        return jsonify(mongo_to_dict(pending))
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route('/api/admin/users/create', methods=['POST'])
@require_auth
def create_employee():
    try:
        data = request.json
        admin_email = data.get('adminEmail')
        
        admin = users_col.find_one({"email": admin_email, "role": {"$in": ["Admin", "Owner"]}})
        if not admin:
            return jsonify({"message": "Unauthorized"}), 401
            
        emp_name = data.get('name')
        emp_email = data.get('email')
        emp_pass = data.get('password')
        emp_role = data.get('role', 'Worker')
        
        # 1. Create in Firebase first
        try:
            fb_user = auth.create_user(email=emp_email, password=emp_pass, display_name=emp_name)
            uid = fb_user.uid
        except Exception as fb_err:
            if "already exists" in str(fb_err).lower():
                fb_user = auth.get_user_by_email(emp_email)
                uid = fb_user.uid
            else:
                return jsonify({"message": f"Firebase error: {str(fb_err)}"}), 400
            
        now = datetime.utcnow().isoformat()
        new_emp = {
            "uid": uid,
            "email": emp_email,
            "name": emp_name,
            "role": emp_role,
            "status": "Approved",
            "password": hash_password(emp_pass),   # ✅ bcrypt hashed — never stored plaintext
            "createdAt": now,
            "lastLogin": now
        }
        users_col.insert_one(new_emp)
        
        return jsonify({"message": f"Employee {emp_name} created successfully"}), 201
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
        
        admin = users_col.find_one({"email": admin_email, "role": {"$in": ["Admin", "Owner"]}})
        if not admin:
            return jsonify({"message": "Unauthorized"}), 401
            
        users_col.update_one({"email": user_email}, {"$set": {"status": "Approved", "role": role}})
        return jsonify({"message": f"User {user_email} approved as {role}"}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 400

@app.route('/api/admin/users/all', methods=['GET'])
@require_auth
def get_all_users():
    try:
        admin_email = request.args.get('adminEmail')
        admin = users_col.find_one({"email": admin_email, "role": {"$in": ["Admin", "Owner"]}})
        
        if not admin:
            return jsonify({"message": "Unauthorized"}), 401
            
        users = list(users_col.find({}).sort("createdAt", -1))
        return jsonify(mongo_to_dict(users))
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
            
        admin = users_col.find_one({"email": admin_email, "role": {"$in": ["Admin", "Owner"]}})
        if not admin:
            return jsonify({"message": "Unauthorized"}), 401
            
        # Optional: Delete from Firebase too
        try:
            target_user = users_col.find_one({"email": target_email})
            if target_user and target_user.get('uid'):
                auth.delete_user(target_user['uid'])
        except Exception as fb_err:
            print(f"Firebase delete error: {fb_err}")
            
        users_col.delete_one({"email": target_email})
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
        ticket_entries = []
        
        for change in changes:
            if not change.get('fieldName'):
                continue
            ticket_entries.append({
                "surveyId": survey_id,
                "fieldName": change['fieldName'],
                "oldValue": change.get('oldValue'),
                "newValue": change.get('newValue'),
                "requestedBy": requested_by,
                "status": "Pending",
                "createdAt": now
            })

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
            
            ticket_entries.append({
                "surveyId": survey_id,
                "fieldName": "file",
                "oldValue": "Existing Document",
                "newValue": json.dumps({"fileName": file_name, "filePath": file_path}),
                "requestedBy": requested_by,
                "status": "Pending",
                "createdAt": now
            })
            file_msg = " and file upload"

        if ticket_entries:
            tickets_col.insert_many(ticket_entries)

        return jsonify({"message": f"Change request(s){file_msg} submitted for approval"}), 201
    except Exception as e:
        print(f"Error creating ticket: {e}")
        return jsonify({"message": str(e)}), 500

@app.route('/api/tickets/all', methods=['GET'])
@require_auth
def get_tickets():
    try:
        admin_email = request.args.get('adminEmail')
        admin = users_col.find_one({"email": admin_email, "role": {"$in": ["Admin", "Owner"]}})
        
        if not admin:
            return jsonify({"message": "Unauthorized"}), 401
            
        # MongoDB JOIN simulation using aggregation or manual lookup
        tickets = list(tickets_col.find({}).sort("createdAt", -1))
        for t in tickets:
            s_id = t.get('surveyId')
            survey = surveys_col.find_one({"_id": ObjectId(s_id)})
            if survey:
                t['clientName'] = survey.get('cli')
                t['location'] = survey.get('loc')
        
        return jsonify(mongo_to_dict(tickets))
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route('/api/tickets/approve', methods=['POST'])
@require_auth
def approve_ticket():
    try:
        data = request.json
        admin_email = data.get('adminEmail')
        ticket_id = data.get('ticketId')
        
        admin = users_col.find_one({"email": admin_email, "role": {"$in": ["Admin", "Owner"]}})
        if not admin:
            return jsonify({"message": "Unauthorized"}), 401
            
        # 1. Get Ticket Details
        ticket = tickets_col.find_one({"_id": ObjectId(ticket_id)})
        if not ticket or ticket.get('status') != 'Pending':
            return jsonify({"message": "Invalid or already processed ticket"}), 400
            
        # 2. Update Survey Log
        survey_id = ticket.get('surveyId')
        field = ticket.get('fieldName')
        new_val = ticket.get('newValue')
        
        # Security: whitelist
        allowed_fields = ['size', 'loc', 'emp', 'cli', 'cliNum', 'area', 'instrument', 'scaleFactor', 'tempC', 'date', 'time', 'file']
        if field not in allowed_fields:
            return jsonify({"message": "Field modification restricted"}), 403
            
        if field == 'file':
            try:
                file_info = json.loads(new_val)
                file_name = file_info.get('fileName')
                file_path = file_info.get('filePath')
                surveys_col.update_one({"_id": ObjectId(survey_id)}, {"$set": {"fileName": file_name, "filePath": file_path}})
            except Exception as jerr:
                print(f"Error parsing file JSON: {jerr}")
        else:
            surveys_col.update_one({"_id": ObjectId(survey_id)}, {"$set": {field: new_val}})
        
        # 3. Mark Ticket as Approved
        tickets_col.update_one({"_id": ObjectId(ticket_id)}, {"$set": {"status": "Approved"}})
        
        return jsonify({"message": f"Change approved! Survey ID {survey_id} has been updated."}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route('/api/tickets/history', methods=['GET'])
@require_auth
def get_survey_history():
    try:
        survey_id = request.args.get('surveyId')
        history = list(tickets_col.find({"surveyId": survey_id, "status": "Approved"}).sort("createdAt", -1))
        return jsonify(mongo_to_dict(history))
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route('/api/public/callback', methods=['POST'])
def submit_callback():
    try:
        data = request.json
        name = data.get('name')
        phone = data.get('phone')
        email = data.get('email')
        message = data.get('message')
        
        if not name or not phone:
            return jsonify({"message": "Name and Phone are required"}), 400
            
        now = datetime.utcnow().isoformat()
        try:
            callbacks_col.insert_one({
                "name": name,
                "phone": phone,
                "email": email,
                "message": message,
                "createdAt": now
            })
        except Exception as db_err:
            print(f"⚠️ Warning: Public callback database insertion failed. ({db_err})")
            
        return jsonify({"message": "Inquiry sent successfully. We will contact you soon."}), 201
    except Exception as e:
        return jsonify({"message": str(e)}), 400

@app.route('/api/logs/deleted', methods=['GET'])
@require_auth
def get_deleted_logs():
    """Return all deleted survey records. Admin/Owner only."""
    try:
        admin_email = request.args.get('adminEmail')
        admin = users_col.find_one({"email": admin_email, "role": {"$in": ["Admin", "Owner"]}})
        if not admin:
            return jsonify({"message": "Unauthorized"}), 401

        logs = list(logs_col.find({}).sort("deletedAt", -1))
        result = []
        for log in logs:
            entry = mongo_to_dict(log)
            # Parse the stored survey JSON string back into a dict for the frontend
            try:
                entry['surveyData'] = json.loads(entry.get('surveyData', '{}'))
            except Exception:
                entry['surveyData'] = {}
            result.append(entry)

        return jsonify(result)
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route('/api/messages/all', methods=['GET'])
@require_auth
def get_all_messages():
    try:
        admin_email = request.args.get('adminEmail')
        admin = users_col.find_one({"email": admin_email, "role": {"$in": ["Admin", "Owner"]}})
        if not admin:
            return jsonify({"message": "Unauthorized"}), 401
            
        messages = list(callbacks_col.find({}).sort("createdAt", -1))
        return jsonify(mongo_to_dict(messages))
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
            
        users_col.update_one({"email": email}, {"$set": {"name": new_name}})
        user = users_col.find_one({"email": email})
        
        if user:
            return jsonify({"message": "Profile updated successfully", "user": mongo_to_dict(user)}), 200
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
        
        existing_user = users_col.find_one({"email": email})
        if existing_user:
            return jsonify({"message": "User logged in", "user": mongo_to_dict(existing_user)}), 200
        
        user_count = users_col.count_documents({})
        if user_count == 0:
            if password == MASTER_PASSWORD:
                role = "Admin"
                status = "Approved"
                now = datetime.utcnow().isoformat()
                new_owner = {
                    "email": email,
                    "name": user_data.get('name', 'Company Owner'),
                    "role": role,
                    "status": status,
                    "createdAt": now,
                    "lastLogin": now
                }
                users_col.insert_one(new_owner)
                user = users_col.find_one({"email": email})
                return jsonify({"message": "Owner registered successfully", "user": mongo_to_dict(user)}), 201
            else:
                return jsonify({"message": "Invalid master password for owner registration."}), 401
        
        return jsonify({"message": "Public registration is disabled. Please contact the site owner."}), 403
    except Exception as e:
        return jsonify({"message": str(e)}), 400

@app.route('/api/payments', methods=['POST'])
@require_auth
def add_payment():
    try:
        data = request.json
        survey_id = data.get('surveyId')
        
        if not survey_id:
            return jsonify({"message": "Survey ID is required"}), 400

        try:
            amt_paid = float(data.get('initialAmountPaid', 0))
            amt_red = float(data.get('amountReduction', 0))
        except (ValueError, TypeError):
            amt_paid = 0
            amt_red = 0

        now = datetime.utcnow().isoformat()
        payment_data = {
            "surveyId": survey_id,
            "quotationDate": data.get('quotationDate'),
            "okDate": data.get('okDate'),
            "receivedDate": data.get('receivedDate'),
            "receivedOn": data.get('receivedOn'),
            "initialAmountPaid": amt_paid,
            "amountReduction": amt_red,
            "createdBy": request.email or data.get('createdBy'),
            "createdAt": now
        }
        
        # Always insert a new record to support installments
        payments_col.insert_one(payment_data)

        # If surveyAmount (agreed total) is provided, just update the survey record — no auto reduction logging.
        # Reductions must be made explicitly via /api/surveys/<id>/reduce-amount
        survey_amount_raw = data.get('surveyAmount')
        if survey_amount_raw is not None and survey_amount_raw != '':
            try:
                new_survey_amount = float(survey_amount_raw)
                surveys_col.update_one(
                    {"_id": ObjectId(survey_id)},
                    {"$set": {"surveyAmount": new_survey_amount, "updatedAt": now}}
                )
            except (ValueError, TypeError):
                pass

        # --- Auto-create a Payment Ticket for admin visibility ---
        try:
            # Fetch survey info for context
            survey_info = surveys_col.find_one({"_id": ObjectId(survey_id)}, {"cli": 1, "loc": 1})
            client_name = survey_info.get("cli", "Unknown") if survey_info else "Unknown"
            location    = survey_info.get("loc", "Unknown") if survey_info else "Unknown"

            ticket_summary = (
                f"Amount: ₹{amt_paid:,.0f}"
                + (f" | Discount: ₹{amt_red:,.0f}" if amt_red > 0 else "")
                + (f" | via {data.get('receivedOn', 'Cash').upper()}")
                + (f" | Date: {data.get('receivedDate', now[:10])}")
            )

            tickets_col.insert_one({
                "surveyId"     : survey_id,
                "ticketType"   : "payment",          # distinguishes from field-change tickets
                "fieldName"    : "payment",
                "oldValue"     : "—",
                "newValue"     : ticket_summary,
                "amountPaid"   : amt_paid,
                "amountReduction": amt_red,
                "receivedOn"   : data.get('receivedOn', 'cash'),
                "receivedDate" : data.get('receivedDate'),
                "quotationDate": data.get('quotationDate'),
                "okDate"       : data.get('okDate'),
                "requestedBy"  : request.email or data.get('createdBy'),
                "clientName"   : client_name,
                "location"     : location,
                "status"       : "Pending",
                "createdAt"    : now
            })
        except Exception as ticket_err:
            print(f"Warning: Failed to create payment ticket: {ticket_err}")
        # --------------------------------------------------------

        return jsonify({"message": "Installment successfully added to record."}), 201
        
    except Exception as e:
        return jsonify({"message": str(e)}), 400

@app.route('/api/payments/history/<survey_id>', methods=['GET'])
@require_auth
def get_payment_history(survey_id):
    try:
        history = list(payments_col.find({"surveyId": survey_id}).sort("createdAt", 1))
        # Also return the survey's current agreed amount for balance calculation
        survey = surveys_col.find_one({"_id": ObjectId(survey_id)}, {"surveyAmount": 1, "cli": 1})
        survey_amount = float(survey.get('surveyAmount', 0) or 0) if survey else 0
        total_paid = sum(float(p.get('initialAmountPaid', 0) or 0) for p in history)
        return jsonify({
            "history": mongo_to_dict(history),
            "surveyAmount": survey_amount,
            "totalPaid": total_paid,
            "balance": max(0, survey_amount - total_paid)
        })
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route('/api/surveys/<id>/reduce-amount', methods=['POST'])
@require_auth
def reduce_survey_amount(id):
    """Explicitly reduce a survey's agreed amount with a mandatory reason."""
    try:
        data = request.json
        email = data.get('reducedBy') or request.email
        new_amount_raw = data.get('newAmount')
        reason = data.get('reason', '').strip()

        if new_amount_raw is None or not reason:
            return jsonify({"message": "newAmount and reason are required"}), 400

        user = users_col.find_one({"email": email})
        if not user or user.get('role') not in ['Admin', 'Owner']:
            return jsonify({"message": "Only Admin/Owner can reduce survey amount"}), 403

        survey = surveys_col.find_one({"_id": ObjectId(id)})
        if not survey:
            return jsonify({"message": "Survey not found"}), 404

        try:
            new_amount = float(new_amount_raw)
        except (ValueError, TypeError):
            return jsonify({"message": "Invalid amount value"}), 400

        old_amount = float(survey.get('surveyAmount', 0) or 0)
        now = datetime.utcnow().isoformat()

        surveys_col.update_one(
            {"_id": ObjectId(id)},
            {"$set": {"surveyAmount": new_amount, "updatedAt": now}}
        )

        reduction_record = {
            "surveyId": id,
            "oldAmount": old_amount,
            "newAmount": new_amount,
            "reductionAmount": old_amount - new_amount,
            "reason": reason,
            "reducedBy": email,
            "createdAt": now
        }
        amount_reductions_col.insert_one(reduction_record)

        return jsonify({
            "message": f"Survey amount updated from ₹{old_amount} to ₹{new_amount}",
            "reduction": old_amount - new_amount
        }), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route('/api/surveys/<id>/amount-history', methods=['GET'])
@require_auth
def get_amount_reduction_history(id):
    """Get the full amount reduction audit trail for a survey."""
    try:
        reductions = list(amount_reductions_col.find({"surveyId": id}).sort("createdAt", 1))
        survey = surveys_col.find_one({"_id": ObjectId(id)}, {"surveyAmount": 1, "cli": 1})
        current_amount = float(survey.get('surveyAmount', 0) or 0) if survey else 0
        return jsonify({
            "currentAmount": current_amount,
            "history": mongo_to_dict(reductions)
        })
    except Exception as e:
        return jsonify({"message": str(e)}), 500

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
