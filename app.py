from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
import secrets
import json
import os
import zipfile
import io
import shutil
from werkzeug.utils import secure_filename
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix

# Load environment variables
load_dotenv()

app = Flask(__name__)
# Fix for running behind Nginx proxy (ensures correct URL generation on VPS)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
# Secure stable secret key for sessions
# On Vercel the filesystem is read-only except /tmp
IS_VERCEL = os.environ.get('VERCEL') or os.environ.get('VERCEL_ENV')
DB_PATH = '/tmp/hotel.db' if IS_VERCEL else os.environ.get('DATABASE', 'hotel.db')
DEFAULT_UPLOAD = '/tmp/uploads' if IS_VERCEL else 'static/uploads'

# Seed /tmp/hotel.db from the bundled repo file on first Vercel startup
if IS_VERCEL and not os.path.exists('/tmp/hotel.db'):
    bundled = os.path.join(os.path.dirname(__file__), 'hotel.db')
    if os.path.exists(bundled):
        import shutil as _shutil
        _shutil.copy2(bundled, '/tmp/hotel.db')
        print("[Vercel] Seeded /tmp/hotel.db from bundled hotel.db")

def get_db_connection():
    db_path = app.config.get('DATABASE', DB_PATH)
    return sqlite3.connect(db_path)
app.config['DATABASE'] = DB_PATH

app.secret_key = os.environ.get('SECRET_KEY', 'dev_key_845372_change_this_in_production')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=365) # Persistent login for 1 year
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', DEFAULT_UPLOAD)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def save_uploaded_file(file, prefix='id'):
    """Robustly save uploaded image file with guaranteed extension and safe filename."""
    if not file or not getattr(file, 'filename', None):
        return None
    raw_filename = file.filename
    ext = os.path.splitext(raw_filename)[1].lower()
    allowed_exts = ['.jpg', '.jpeg', '.png', '.webp', '.heic', '.bmp', '.pdf']
    if not ext or ext not in allowed_exts:
        ext = '.jpg'
    safe_base = secure_filename(os.path.splitext(raw_filename)[0])
    if not safe_base:
        safe_base = 'photo'
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S_%f')[:18]
    filename = f"{prefix}_{timestamp}_{safe_base}{ext}"
    upload_dir = app.config['UPLOAD_FOLDER']
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, filename)
    file.save(filepath)
    return f"uploads/{filename}"


# Prevent Caching on all API responses to avoid data leak between sessions
@app.after_request
def add_header(response):
    if request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
    return response

# Database initialization
def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Enable Foreign Keys
    c.execute("PRAGMA foreign_keys = ON")

    # SaaS Tables: Hotels & Users
    c.execute('''CREATE TABLE IF NOT EXISTS hotels
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT,
                  email TEXT,
                  phone TEXT,
                  plan TEXT DEFAULT 'monthly',
                  is_restaurant_active INTEGER DEFAULT 0, -- Support for restaurant subscription
                  is_hotel_active INTEGER DEFAULT 0,      -- Support for hotel subscription
                  expiry_date TEXT,
                  is_active INTEGER DEFAULT 0, -- 0: Pending/Suspended, 1: Active
                  utr_ref TEXT, -- For payment verification
                  created_at TEXT,
                  housekeeping_token TEXT,
                  currency_symbol TEXT DEFAULT '₹',
                  tax_rate REAL DEFAULT 0,
                  google_review_url TEXT)''')
    
    # ... existing tables ...
    
    # Restaurant Tables
    c.execute('''CREATE TABLE IF NOT EXISTS restaurant_menu
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  hotel_id INTEGER,
                  item_name TEXT,
                  item_code TEXT,
                  price REAL,
                  UNIQUE(hotel_id, item_code),
                  FOREIGN KEY(hotel_id) REFERENCES hotels(id))''')

    c.execute('''CREATE TABLE IF NOT EXISTS restaurant_tables
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  hotel_id INTEGER,
                  table_number TEXT,
                  status TEXT DEFAULT 'available',
                  FOREIGN KEY(hotel_id) REFERENCES hotels(id))''')

    c.execute('''CREATE TABLE IF NOT EXISTS restaurant_bills
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  hotel_id INTEGER,
                  table_id INTEGER,
                  customer_mobile TEXT,
                  total_amount REAL,
                  payment_status TEXT DEFAULT 'unpaid',
                  created_at TEXT,
                  FOREIGN KEY(hotel_id) REFERENCES hotels(id))''')

    c.execute('''CREATE TABLE IF NOT EXISTS restaurant_bill_items
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  bill_id INTEGER,
                  item_name TEXT,
                  quantity INTEGER,
                  price REAL,
                  status TEXT DEFAULT 'pending',
                  FOREIGN KEY(bill_id) REFERENCES restaurant_bills(id))''')

    # Migration: Add status to restaurant_bill_items if missing
    try:
        c.execute("ALTER TABLE restaurant_bill_items ADD COLUMN status TEXT DEFAULT 'pending'")
        conn.commit()
    except:
        pass

    c.execute('''CREATE TABLE IF NOT EXISTS restaurant_inventory
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  hotel_id INTEGER,
                  item_name TEXT,
                  category TEXT,
                  stock_quantity REAL DEFAULT 0,
                  unit TEXT DEFAULT 'pcs',
                  alert_level REAL DEFAULT 5,
                  FOREIGN KEY(hotel_id) REFERENCES hotels(id))''')

    c.execute('''CREATE TABLE IF NOT EXISTS super_transactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  hotel_id INTEGER,
                  amount REAL,
                  utr_ref TEXT,
                  plan TEXT,
                  date TEXT,
                  FOREIGN KEY(hotel_id) REFERENCES hotels(id))''')

    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE,
                  password_hash TEXT,
                  role TEXT DEFAULT 'owner',
                  hotel_id INTEGER,
                  is_2fa_enabled INTEGER DEFAULT 0,
                  FOREIGN KEY(hotel_id) REFERENCES hotels(id))''')
                  
    # Migration: Add is_2fa_enabled to users if not exists
    try:
        c.execute("ALTER TABLE users ADD COLUMN is_2fa_enabled INTEGER DEFAULT 0")
        conn.commit()
    except:
        pass

    # Hotel Data Tables (Now with hotel_id)
    c.execute('''CREATE TABLE IF NOT EXISTS rooms
                 (room_id TEXT,
                  hotel_id INTEGER,
                  status TEXT DEFAULT 'available',
                  last_checkout TEXT,
                  room_type TEXT,
                  PRIMARY KEY (room_id, hotel_id),
                  FOREIGN KEY(hotel_id) REFERENCES hotels(id))''')

    c.execute('''CREATE TABLE IF NOT EXISTS bookings
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  hotel_id INTEGER,
                  room_id TEXT, -- Legacy fallback, mostly unused now
                  guest_name TEXT,
                  phone TEXT,
                  address TEXT,
                  id_number TEXT,
                  id_photo TEXT,
                  members TEXT,
                  amount REAL,
                  checkin_time TEXT,
                  checkout_time TEXT,
                  extra_charges REAL DEFAULT 0,
                  food REAL DEFAULT 0,
                  laundry REAL DEFAULT 0,
                  water_bottle REAL DEFAULT 0,
                  car_wash REAL DEFAULT 0,
                  status TEXT DEFAULT 'active',
                  FOREIGN KEY(hotel_id) REFERENCES hotels(id))''')
                  
    # Migration: Add members to bookings
    try:
        c.execute("ALTER TABLE bookings ADD COLUMN members TEXT")
        conn.commit()
    except:
        pass

    c.execute('''CREATE TABLE IF NOT EXISTS expenses
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  hotel_id INTEGER,
                  name TEXT,
                  amount REAL,
                  category TEXT DEFAULT 'General',
                  date TEXT,
                  FOREIGN KEY(hotel_id) REFERENCES hotels(id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS guests
                 (phone TEXT,
                  hotel_id INTEGER,
                  name TEXT,
                  email TEXT,
                  id_number TEXT,
                  address TEXT,
                  status TEXT DEFAULT 'regular',
                  notes TEXT,
                  PRIMARY KEY (phone, hotel_id),
                  FOREIGN KEY(hotel_id) REFERENCES hotels(id))''')
    
    # Migration: Add email to guests if not exists
    try:
        c.execute("ALTER TABLE guests ADD COLUMN email TEXT")
    except:
        pass
                  
    c.execute('''CREATE TABLE IF NOT EXISTS booking_rooms
                 (booking_id INTEGER,
                  room_id TEXT,
                  FOREIGN KEY(booking_id) REFERENCES bookings(id))''')

    # Support messages
    c.execute('''CREATE TABLE IF NOT EXISTS support_messages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  hotel_id INTEGER,
                  subject TEXT,
                  message TEXT,
                  status TEXT DEFAULT 'pending',
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY(hotel_id) REFERENCES hotels(id))''')

    # Self Check-in Requests (Guest Portal)
    c.execute('''CREATE TABLE IF NOT EXISTS self_checkin_requests
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  hotel_id INTEGER,
                  guest_name TEXT,
                  phone TEXT,
                  address TEXT,
                  id_photo TEXT,
                  members TEXT,
                  status TEXT DEFAULT 'pending',
                  created_at TEXT,
                  FOREIGN KEY(hotel_id) REFERENCES hotels(id))''')
                  
    # Migration: Add members to self_checkin_requests
    try:
        c.execute("ALTER TABLE self_checkin_requests ADD COLUMN members TEXT")
        conn.commit()
    except:
        pass

    
    c.execute("""CREATE TABLE IF NOT EXISTS announcements
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  message TEXT,
                  type TEXT DEFAULT 'info',
                  is_active INTEGER DEFAULT 1,
                  created_at TEXT)""")
    conn.commit()
    conn.close()


# --- Security Helpers ---
def log_action(user_id, action, details, hotel_id=None):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        if not hotel_id and session.get('hotel_id'):
            hotel_id = session.get('hotel_id')
        
        ip = request.remote_addr if request else '0.0.0.0'
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Check if table exists to avoid crash on first run
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_logs'")
        if c.fetchone():
            c.execute("INSERT INTO audit_logs (hotel_id, user_id, action, details, timestamp, ip_address) VALUES (?, ?, ?, ?, ?, ?)",
                      (hotel_id, user_id, action, details, timestamp, ip))
            conn.commit()
    except Exception as e:
        print(f"Audit Log Error: {e}")
    finally:
        conn.close()

def send_otp_email(to_email, otp):
    smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.environ.get('SMTP_PORT', 587))
    smtp_user = os.environ.get('SMTP_USER')
    smtp_password = os.environ.get('SMTP_PASSWORD')

    if not smtp_user or not smtp_password:
        print(f"\n[⚠️ WARNING] SMTP credentials not set. OTP for {to_email}: {otp}\n")
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = to_email
        msg['Subject'] = "Your JoyHotels 2FA Code"

        body = f"Your verification code is: {otp}\n\nThis code will expire in 10 minutes."
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()
        
        print(f"[✅ SUCCESS] OTP sent to {to_email}")
        return True
    except Exception as e:
        print(f"[❌ ERROR] Failed to send email: {e}")
        return False

# Initialize DB (This will only create tables if they don't exist)
init_db()

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        
        # Super Admin bypasses activation check
        if session.get('role') == 'super_admin':
            return f(*args, **kwargs)

        # Check if hotel is suspended
        hotel_id = session.get('hotel_id')
        if hotel_id:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT is_active FROM hotels WHERE id = ?", (hotel_id,))
            res = c.fetchone()
            conn.close()
            if res and res[0] == 0:
                # Redirect to a status page or logout
                session.clear()
                return render_template('suspended.html')
        
        return f(*args, **kwargs)
    return decorated_function

def super_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session or session.get('role') != 'super_admin':
            return jsonify({'error': 'Unauthorized'}), 403
        return f(*args, **kwargs)
    return decorated_function

# Owner required decorator (Owner or Super Admin)
def owner_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        if session.get('role') not in ['owner', 'super_admin']:
            return jsonify({'error': 'Unauthorized'}), 403
        return f(*args, **kwargs)
    return decorated_function

# Admin required decorator (Admin, Owner, or Super Admin)
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        if session.get('role') not in ['admin', 'owner', 'super_admin']:
            return jsonify({'error': 'Unauthorized'}), 403
        return f(*args, **kwargs)
    return decorated_function

from email.mime.application import MIMEApplication

def send_backup_email(to_email, hotel_name):
    smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.environ.get('SMTP_PORT', 587))
    smtp_user = os.environ.get('SMTP_USER')
    smtp_password = os.environ.get('SMTP_PASSWORD')

    if not smtp_user or not smtp_password:
        return False, "SMTP_USER or SMTP_PASSWORD environment variables are not set in .env"

    try:
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = to_email
        msg['Subject'] = f"Database Backup - {hotel_name}"

        body = f"Attached is the database backup for {hotel_name} as of {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}."
        msg.attach(MIMEText(body, 'plain'))

        # Attach database file
        with open('hotel.db', 'rb') as f:
            part = MIMEApplication(f.read(), Name='hotel.db')
            part['Content-Disposition'] = 'attachment; filename="hotel.db"'
            msg.attach(part)

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()
        return True, "Success"
    except Exception as e:
        print(f"Backup Error: {e}")
        return False, str(e)

@app.route('/api/settings/backup', methods=['POST'])
@owner_required
def trigger_backup():
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT email, name FROM hotels WHERE id = ?", (hotel_id,))
    row = c.fetchone()
    conn.close()
    
    if not row or not row[0]:
        return jsonify({'success': False, 'message': 'Owner email not set in Settings -> Hotel Profile'})
        
    success, message = send_backup_email(row[0], row[1])
    if success:
        log_action(session.get('user_id'), 'BACKUP', "Database backup sent to email", hotel_id)
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': f"Failed to send email: {message}"})

# Routes
@app.route('/')
def index():
    if 'logged_in' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/landing')
def landing_page():
    return render_template('landing.html')

@app.route('/restaurant')
def restaurant_index():
    return render_template('restaurant_landing.html')

@app.route('/login')
def login():
    if 'logged_in' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/pricing')
def pricing():
    return render_template('pricing.html')

@app.route('/signup')
def signup():
    return render_template('signup.html')

@app.route('/payment')
def payment():
    return render_template('payment.html')

@app.route('/api/login', methods=['POST'])
def do_login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    conn = get_db_connection()
    c = conn.cursor()
    # Join with hotels to get hotel name, 2FA status, and email
    c.execute("""
        SELECT u.id, u.password_hash, u.role, u.hotel_id, u.username, h.name, u.is_2fa_enabled, h.email
        FROM users u 
        LEFT JOIN hotels h ON u.hotel_id = h.id 
        WHERE u.username = ?
    """, (username,))
    user = c.fetchone()
    conn.close()
    
    if user and check_password_hash(user[1], password):
        session.permanent = True
        if user[2] == 'super_admin':
            session['logged_in'] = True
            session['user_id'] = user[0]
            session['role'] = user[2]
            session['hotel_id'] = user[3]
            session['username'] = user[4]
            session['hotel_name'] = user[5] or 'JoyHotels'
            session['active_system'] = 'hotel' # Super Admin defaults to hotel view
            return jsonify({'success': True, 'redirect': '/super_admin'})

        # Check for 2FA
        is_2fa_enabled = user[6] if len(user) > 6 else 0
        if is_2fa_enabled:
            otp = str(random.randint(100000, 999999))
            session['temp_user'] = {
                'id': user[0],
                'role': user[2],
                'hotel_id': user[3],
                'username': user[4],
                'hotel_name': user[5] or 'JoyHotels'
            }
            session['2fa_otp'] = otp
            
            # Destination email: use hotel email if available, else fallback to username
            target_email = user[7] if (len(user) > 7 and user[7]) else username
            
            print(f"[🛡️ 2FA] Attempting to send OTP to: {target_email}")
            send_otp_email(target_email, otp)
            return jsonify({'success': True, 'redirect': '/verify-2fa-page'})

        # Normal Login
        session['logged_in'] = True
        session['user_id'] = user[0]
        session['role'] = user[2]
        session['hotel_id'] = user[3]
        session['username'] = user[4]
        session['hotel_name'] = user[5] or 'JoyHotels'
        
        # Initialize Active System
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT is_hotel_active, is_restaurant_active FROM hotels WHERE id = ?", (user[3],))
        h_data = c.fetchone()
        conn.close()
        
        if h_data:
            session['is_hotel_active'] = bool(h_data[0])
            session['is_restaurant_active'] = bool(h_data[1])
            if h_data[0]: session['active_system'] = 'hotel'
            elif h_data[1]: session['active_system'] = 'restaurant'
            else: session['active_system'] = 'hotel'
        else:
            session['is_hotel_active'] = False
            session['is_restaurant_active'] = False
            session['active_system'] = 'hotel'
        
        log_action(user[0], 'LOGIN', 'User logged in', user[3])
        return jsonify({'success': True, 'redirect': '/dashboard'})
    
    # Hardcoded Super Admin check
    if username == 'admin_joy' and password == 'admin123':
        session.permanent = True
        session['logged_in'] = True
        session['role'] = 'super_admin'
        session['username'] = 'Joy Admin'
        return jsonify({'success': True, 'redirect': '/super_admin'})

    return jsonify({'success': False, 'message': 'Invalid credentials'})

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    hotel_name = data.get('hotel_name')
    email = data.get('email')
    phone = data.get('phone')
    username = data.get('username')
    password = data.get('password')
    plan = data.get('plan', 'monthly')
    utr_ref = data.get('utr_ref')
    
    if not all([hotel_name, email, phone, username, password, utr_ref]):
        return jsonify({'success': False, 'message': 'All fields are required'})
        
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # Create Hotel (Starts as Inactive)
        hk_token = secrets.token_urlsafe(16)
        
        # Subscription Flags & Expiry
        is_restaurant = 1 if 'restaurant' in plan or 'both' in plan else 0
        is_hotel = 1 if 'hotel' in plan or 'both' in plan else 0
        
        days_to_add = 365 if '_yearly' in plan else 30
        expiry_date = (datetime.now() + timedelta(days=days_to_add)).strftime('%Y-%m-%d')
        
        c.execute("INSERT INTO hotels (name, email, phone, plan, utr_ref, created_at, is_active, housekeeping_token, is_restaurant_active, is_hotel_active, expiry_date) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)", 
                  (hotel_name, email, phone, plan, utr_ref, datetime.now().strftime('%Y-%m-%d'), hk_token, is_restaurant, is_hotel, expiry_date))
        hotel_id = c.lastrowid
        
        # Create Owner User
        hashed_pw = generate_password_hash(password)
        c.execute("INSERT INTO users (username, password_hash, role, hotel_id) VALUES (?, ?, 'owner', ?)",
                  (username, hashed_pw, hotel_id))
        user_id = c.lastrowid
        
        conn.commit()
        
        # Auto Login
        session.permanent = True
        session['logged_in'] = True
        session['user_id'] = user_id
        session['role'] = 'owner'
        session['hotel_id'] = hotel_id
        session['username'] = username
        session['hotel_name'] = hotel_name
        
        return jsonify({'success': True})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'Username already exists'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

# --- Super Admin Routes ---

@app.route('/super_admin')
@super_admin_required
def super_admin_page():
    return render_template('super_admin.html')

@app.route('/api/super/hotels')
@super_admin_required
def get_super_hotels():
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, name, email, phone, plan, expiry_date, is_active, utr_ref, created_at, is_restaurant_active, is_hotel_active FROM hotels ORDER BY id DESC")
    hotels = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(hotels)

@app.route('/api/super/toggle_status', methods=['POST'])
@super_admin_required
def super_toggle_status():
    data = request.json
    hotel_id = data.get('hotel_id')
    status = data.get('status') # 1 for active, 0 for suspended
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE hotels SET is_active = ? WHERE id = ?", (status, hotel_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/super/record_payment', methods=['POST'])
@super_admin_required
def super_record_payment():
    data = request.json
    hotel_id = data.get('hotel_id')
    amount = data.get('amount')
    plan = data.get('plan')
    utr_ref = data.get('utr_ref')
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # 1. Update Hotel Expiry and status
    today = datetime.now()
    if plan == 'yearly':
        expiry = (today + timedelta(days=365)).strftime('%Y-%m-%d')
    else:
        expiry = (today + timedelta(days=30)).strftime('%Y-%m-%d')
        
    # Subscription Flags
    is_restaurant = 1 if 'restaurant' in plan or 'both' in plan else 0
    is_hotel = 1 if 'hotel' in plan or 'both' in plan else 0
    
    c.execute("UPDATE hotels SET expiry_date = ?, is_active = 1, is_restaurant_active = ?, is_hotel_active = ?, plan = ? WHERE id = ?", 
              (expiry, is_restaurant, is_hotel, plan, hotel_id))
    
    # 2. Log in transactions
    c.execute("INSERT INTO super_transactions (hotel_id, amount, utr_ref, plan, date) VALUES (?, ?, ?, ?, ?)",
              (hotel_id, amount, utr_ref, plan, today.strftime('%Y-%m-%d %H:%M')))
    
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/super/stats')
@super_admin_required
def super_stats():
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM hotels")
    total_hotels = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM hotels WHERE is_active = 1")
    active_hotels = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM hotels WHERE is_active = 0 AND expiry_date IS NULL")
    pending_hotels = c.fetchone()[0]
    
    c.execute("SELECT SUM(amount) FROM super_transactions")
    total_revenue = c.fetchone()[0] or 0
    
    # Revenue monthly distribution (last 6 months)
    c.execute("""
        SELECT strftime('%Y-%m', date) as month, SUM(amount) 
        FROM super_transactions 
        GROUP BY month 
        ORDER BY month DESC 
        LIMIT 6
    """)
    revenue_chart = c.fetchall()
    
    conn.close()
    return jsonify({
        'total_hotels': total_hotels,
        'active_hotels': active_hotels,
        'pending_hotels': pending_hotels,
        'total_revenue': total_revenue,
        'revenue_chart': revenue_chart[::-1]
    })

@app.route('/api/super/transactions')
@super_admin_required
def super_transactions():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT t.*, h.name as hotel_name 
        FROM super_transactions t 
        JOIN hotels h ON t.hotel_id = h.id 
        ORDER BY t.date DESC
    """)
    rows = [dict(zip([col[0] for col in c.description], row)) for row in c.fetchall()]
    conn.close()
    return jsonify(rows)

@app.route('/api/super/messages')
@super_admin_required
def super_messages():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT m.*, h.name as hotel_name 
        FROM support_messages m 
        JOIN hotels h ON m.hotel_id = h.id 
        ORDER BY m.created_at DESC
    """)
    rows = [dict(zip([col[0] for col in c.description], row)) for row in c.fetchall()]
    conn.close()
    return jsonify(rows)

@app.route('/api/hotel/message', methods=['POST'])
@login_required
def send_message():
    data = request.json
    hotel_id = session.get('hotel_id')
    subject = data.get('subject')
    message = data.get('message')
    
    if not subject or not message:
        return jsonify({'success': False, 'message': 'Fill all fields'}), 400
        
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO support_messages (hotel_id, subject, message) VALUES (?, ?, ?)",
              (hotel_id, subject, message))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/super/message/update', methods=['POST'])
@super_admin_required
def update_message_status():
    data = request.json
    msg_id = data.get('id')
    status = data.get('status') # 'resolved' or 'pending'
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE support_messages SET status = ? WHERE id = ?", (status, msg_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/super/impersonate/<int:hotel_id>')
@super_admin_required
def super_impersonate(hotel_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, name FROM hotels WHERE id = ?", (hotel_id,))
    hotel = c.fetchone()
    conn.close()
    
    if not hotel:
        return "Hotel not found", 404
        
    # Magic: Set session as if they are the owner
    session['hotel_id'] = hotel[0]
    session['role'] = 'owner'
    session['hotel_name'] = hotel[1]
    # Keep a flag so we know it's a ghost login
    session['is_impersonating'] = True
    
    return redirect(url_for('dashboard'))

@app.route('/api/super/announce', methods=['POST'])
@super_admin_required
def post_announcement():
    data = request.json
    message = data.get('message')
    type = data.get('type', 'info') # info, warning, success
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    conn = get_db_connection()
    c = conn.cursor()
    # Deactivate old active announcements first
    c.execute("UPDATE announcements SET is_active = 0")
    c.execute("INSERT INTO announcements (message, type, is_active, created_at) VALUES (?, ?, 1, ?)",
              (message, type, timestamp))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/public/announcement')
def get_announcement():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT message, type, created_at FROM announcements WHERE is_active = 1 ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    
    if row:
        message, msg_type, created_at = row
        if created_at:
            try:
                posted_time = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
                if datetime.now() - posted_time > timedelta(hours=12):
                    return jsonify({'has_announcement': False})
            except Exception as e:
                print(f"Announcement time error: {e}")
        
        return jsonify({'has_announcement': True, 'message': message, 'type': msg_type})
    return jsonify({'has_announcement': False})

# --- Existing Staff Routes ---
@app.route('/api/setup/staff', methods=['POST'])
@login_required
def setup_staff():
    if session.get('role') != 'owner':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    data = request.json
    username = data.get('username')
    password = data.get('password')
    hotel_id = session.get('hotel_id')
    
    if not username or not password:
        return jsonify({'success': False, 'message': 'Missing fields'})
        
    conn = get_db_connection()
    c = conn.cursor()
    try:
        hashed_pw = generate_password_hash(password)
        c.execute("INSERT INTO users (username, password_hash, role, hotel_id) VALUES (?, ?, 'staff', ?)",
                  (username, hashed_pw, hotel_id))
        conn.commit()
        return jsonify({'success': True})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'Username already exists'})
    finally:
        conn.close()

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/calendar')
@login_required
def calendar_page():
    return render_template('calendar.html', role=session.get('role', 'owner'))

@app.route('/dashboard')
@login_required
def dashboard():
    # If user is in restaurant mode, redirect to restaurant dashboard
    if session.get('active_system') == 'restaurant':
        return redirect(url_for('restaurant_dashboard'))
    return render_template('dashboard.html', role=session.get('role'))

@app.route('/restaurant_dashboard')
@login_required
def restaurant_dashboard():
    # If user is in hotel mode, redirect to hotel dashboard
    if session.get('active_system') == 'hotel':
        return redirect(url_for('dashboard'))
        
    # Get hotel profile for settings section
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT name, email, phone FROM hotels WHERE id = ?", (hotel_id,))
    row = c.fetchone()
    conn.close()
    
    hotel_name = row[0] if row else ''
    hotel_email = row[1] if row else ''
    hotel_phone = row[2] if row else ''
    
    return render_template('restaurant_dashboard.html', 
                          role=session.get('role'),
                          hotel_name=hotel_name,
                          hotel_email=hotel_email,
                          hotel_phone=hotel_phone)


# --- Restaurant API Endpoints ---

@app.route('/restaurant_kds')
@login_required
def restaurant_kds():
    return render_template('kds.html', hotel_name=session.get('hotel_name'))

@app.route('/api/restaurant/kds/orders')
@login_required
def get_kds_orders():
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()
    # Get items for unpaid bills that are NOT 'ready'
    c.execute("""
        SELECT i.id, i.item_name, i.quantity, b.table_id, b.id as bill_id, b.created_at
        FROM restaurant_bill_items i
        JOIN restaurant_bills b ON i.bill_id = b.id
        WHERE b.hotel_id = ? AND b.payment_status = 'unpaid' AND i.status = 'pending'
        ORDER BY b.created_at ASC
    """, (hotel_id,))
    orders = []
    for r in c.fetchall():
        orders.append({
            'id': r[0],
            'item_name': r[1],
            'quantity': r[2],
            'table_id': r[3],
            'bill_id': r[4],
            'time': r[5]
        })
    conn.close()
    return jsonify(orders)

@app.route('/api/restaurant/kds/ready/<int:item_id>', methods=['POST'])
@login_required
def mark_item_ready(item_id):
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()
    # Verify the item belongs to the hotel's bill
    c.execute("""
        SELECT i.id FROM restaurant_bill_items i
        JOIN restaurant_bills b ON i.bill_id = b.id
        WHERE i.id = ? AND b.hotel_id = ?
    """, (item_id, hotel_id))
    if not c.fetchone():
        conn.close()
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    c.execute("UPDATE restaurant_bill_items SET status = 'ready' WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/restaurant/kds/ready_notifications')
@login_required
def get_ready_notifications():
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()
    # Get items for unpaid bills that are 'ready' but not yet 'served'
    c.execute("""
        SELECT i.id, i.item_name, i.quantity, b.table_id
        FROM restaurant_bill_items i
        JOIN restaurant_bills b ON i.bill_id = b.id
        WHERE b.hotel_id = ? AND b.payment_status = 'unpaid' AND i.status = 'ready'
    """, (hotel_id,))
    ready_items = []
    for r in c.fetchall():
        ready_items.append({
            'id': r[0],
            'item_name': r[1],
            'quantity': r[2],
            'table_id': r[3]
        })
    conn.close()
    return jsonify(ready_items)

@app.route('/api/restaurant/kds/serve/<int:item_id>', methods=['POST'])
@login_required
def mark_item_served(item_id):
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()
    # Verify ownership
    c.execute("""
        SELECT i.id FROM restaurant_bill_items i
        JOIN restaurant_bills b ON i.bill_id = b.id
        WHERE i.id = ? AND b.hotel_id = ?
    """, (item_id, hotel_id))
    if not c.fetchone():
        conn.close()
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    c.execute("UPDATE restaurant_bill_items SET status = 'served' WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/restaurant/menu')
@login_required
def get_restaurant_menu():
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, item_name, item_code, price FROM restaurant_menu WHERE hotel_id = ?", (hotel_id,))
    items = [{'id': r[0], 'name': r[1], 'code': r[2], 'price': r[3]} for r in c.fetchall()]
    conn.close()
    return jsonify(items)

@app.route('/api/restaurant/menu/add', methods=['POST'])
@admin_required
def add_menu_item():
    data = request.json
    hotel_id = session.get('hotel_id')
    name = data.get('name')
    code = data.get('code')
    price = data.get('price')
    
    if not all([name, code, price]):
        return jsonify({'success': False, 'message': 'Missing data'})
        
    conn = get_db_connection()
    c = conn.cursor()
    
    # Check for duplicate code
    c.execute("SELECT id FROM restaurant_menu WHERE hotel_id = ? AND item_code = ?", (hotel_id, code))
    if c.fetchone():
        conn.close()
        return jsonify({'success': False, 'message': f'Item code "{code}" already exists'})
        
    c.execute("INSERT INTO restaurant_menu (hotel_id, item_name, item_code, price) VALUES (?, ?, ?, ?)",
              (hotel_id, name, code, price))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/restaurant/menu/delete/<int:item_id>', methods=['DELETE'])
@admin_required
def delete_menu_item(item_id):
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM restaurant_menu WHERE id = ? AND hotel_id = ?", (item_id, hotel_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/restaurant/tables')
@login_required
def get_restaurant_tables():
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, table_number, status FROM restaurant_tables WHERE hotel_id = ?", (hotel_id,))
    tables = [{'id': r[0], 'number': r[1], 'status': r[2]} for r in c.fetchall()]
    conn.close()
    return jsonify(tables)

@app.route('/api/restaurant/tables/add', methods=['POST'])
@login_required
def add_restaurant_table():
    data = request.json
    hotel_id = session.get('hotel_id')
    number = data.get('number')
    
    if not number:
        return jsonify({'success': False, 'message': 'Table number required'})
        
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO restaurant_tables (hotel_id, table_number) VALUES (?, ?)",
              (hotel_id, number))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/restaurant/tables/delete/<int:table_id>', methods=['DELETE'])
@login_required
def delete_restaurant_table(table_id):
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM restaurant_tables WHERE id = ? AND hotel_id = ?", (table_id, hotel_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/restaurant/bill/create', methods=['POST'])
@login_required
def create_restaurant_bill():
    data = request.json
    hotel_id = session.get('hotel_id')
    table_id = data.get('table_id')
    mobile = data.get('customer_mobile')
    items = data.get('items') # List of {name, quantity, price}
    total = data.get('total')
    
    if not all([table_id, items, total]):
        return jsonify({'success': False, 'message': 'Missing bill data'})
        
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # Create Bill
        c.execute("INSERT INTO restaurant_bills (hotel_id, table_id, customer_mobile, total_amount, created_at) VALUES (?, ?, ?, ?, ?)",
                  (hotel_id, table_id, mobile, total, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        bill_id = c.lastrowid
        
        # Add Items
        for it in items:
            c.execute("INSERT INTO restaurant_bill_items (bill_id, item_name, quantity, price) VALUES (?, ?, ?, ?)",
                      (bill_id, it['name'], it['quantity'], it['price']))
        
        # Update Table Status to Occupied (or stays occupied if already was)
        # Actually, for fast billing, we might just settle it immediately
        # If paying now, status stays available. If 'unpaid', status becomes occupied.
        status = data.get('payment_status', 'unpaid')
        if status == 'unpaid':
            c.execute("UPDATE restaurant_tables SET status = 'occupied' WHERE id = ? AND hotel_id = ?", (table_id, hotel_id))
        else:
            c.execute("UPDATE restaurant_bills SET payment_status = 'paid' WHERE id = ?", (bill_id,))
            c.execute("UPDATE restaurant_tables SET status = 'available' WHERE id = ? AND hotel_id = ?", (table_id, hotel_id))
            
        conn.commit()
        return jsonify({'success': True, 'bill_id': bill_id})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/api/restaurant/bills')
@login_required
def get_restaurant_bills():
    hotel_id = session.get('hotel_id')
    date = request.args.get('date') # YYYY-MM-DD
    month = request.args.get('month') # YYYY-MM
    year = request.args.get('year') # YYYY

    conn = get_db_connection()
    c = conn.cursor()
    
    query = """
        SELECT b.id, t.table_number, b.customer_mobile, b.total_amount, b.payment_status, b.created_at 
        FROM restaurant_bills b
        LEFT JOIN restaurant_tables t ON b.table_id = t.id
        WHERE b.hotel_id = ?
    """
    params = [hotel_id]

    if date:
        query += " AND b.created_at LIKE ?"
        params.append(date + '%')
    elif month:
        query += " AND b.created_at LIKE ?"
        params.append(month + '%')
    elif year:
        query += " AND b.created_at LIKE ?"
        params.append(year + '%')

    query += " ORDER BY b.created_at DESC"
    
    c.execute(query, params)
    bills = [{'id': r[0], 'table': r[1], 'mobile': r[2], 'total': r[3], 'status': r[4], 'date': r[5]} for r in c.fetchall()]
    conn.close()
    return jsonify(bills)

@app.route('/api/restaurant/bill/<int:bill_id>')
@login_required
def get_restaurant_bill_detail(bill_id):
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("SELECT id, table_id, customer_mobile, total_amount, payment_status, created_at FROM restaurant_bills WHERE id = ? AND hotel_id = ?", (bill_id, hotel_id))
    bill = c.fetchone()
    if not bill:
        conn.close()
        return jsonify({'success': False, 'message': 'Bill not found'})
        
    c.execute("SELECT item_name, quantity, price FROM restaurant_bill_items WHERE bill_id = ?", (bill_id,))
    items = [{'name': r[0], 'quantity': r[1], 'price': r[2]} for r in c.fetchall()]
    conn.close()
    
    return jsonify({
        'id': bill[0],
        'table_id': bill[1],
        'mobile': bill[2],
        'total': bill[3],
        'status': bill[4],
        'date': bill[5],
        'items': items
    })

@app.route('/api/restaurant/table/<int:table_id>/active_bill')
@login_required
def get_table_active_bill(table_id):
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()
    
    # Get the unpaid bill for this table
    c.execute("SELECT id, customer_mobile, total_amount, created_at FROM restaurant_bills WHERE hotel_id = ? AND table_id = ? AND payment_status = 'unpaid' ORDER BY created_at DESC LIMIT 1", (hotel_id, table_id))
    bill = c.fetchone()
    
    if not bill:
        conn.close()
        return jsonify({'has_bill': False})
    
    # Get items
    c.execute("SELECT item_name, quantity, price FROM restaurant_bill_items WHERE bill_id = ?", (bill[0],))
    items = [{'name': r[0], 'quantity': r[1], 'price': r[2]} for r in c.fetchall()]
    conn.close()
    
    return jsonify({
        'has_bill': True,
        'bill_id': bill[0],
        'mobile': bill[1],
        'total': bill[2],
        'date': bill[3],
        'items': items
    })

@app.route('/api/restaurant/bill/<int:bill_id>/update', methods=['POST'])
@login_required
def update_restaurant_bill(bill_id):
    data = request.json
    hotel_id = session.get('hotel_id')
    new_items = data.get('items', [])
    new_total = data.get('total')
    
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # Verify bill belongs to this hotel
        c.execute("SELECT id FROM restaurant_bills WHERE id = ? AND hotel_id = ?", (bill_id, hotel_id))
        if not c.fetchone():
            return jsonify({'success': False, 'message': 'Bill not found'})
        
        # Add new items
        for it in new_items:
            c.execute("INSERT INTO restaurant_bill_items (bill_id, item_name, quantity, price) VALUES (?, ?, ?, ?)",
                      (bill_id, it['name'], it['quantity'], it['price']))
        
        # Update total
        c.execute("UPDATE restaurant_bills SET total_amount = ? WHERE id = ?", (new_total, bill_id))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/api/restaurant/bill/<int:bill_id>/settle', methods=['POST'])
@login_required
def settle_restaurant_bill(bill_id):
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # Get table_id first
        c.execute("SELECT table_id FROM restaurant_bills WHERE id = ? AND hotel_id = ?", (bill_id, hotel_id))
        result = c.fetchone()
        if not result:
            return jsonify({'success': False, 'message': 'Bill not found'})
        
        table_id = result[0]
        
        # Mark bill as paid
        c.execute("UPDATE restaurant_bills SET payment_status = 'paid' WHERE id = ?", (bill_id,))
        
        # Free the table
        c.execute("UPDATE restaurant_tables SET status = 'available' WHERE id = ? AND hotel_id = ?", (table_id, hotel_id))
        
        # Deduct Inventory (Simple matching by name)
        c.execute("SELECT item_name, quantity FROM restaurant_bill_items WHERE bill_id = ?", (bill_id,))
        items = c.fetchall()
        for item_name, qty in items:
            c.execute("UPDATE restaurant_inventory SET stock_quantity = stock_quantity - ? WHERE item_name = ? AND hotel_id = ?", 
                      (qty, item_name, hotel_id))

        conn.commit()
        return jsonify({'success': True, 'bill_id': bill_id})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/api/restaurant/stats')
@login_required
def get_restaurant_stats():
    hotel_id = session.get('hotel_id')
    today = datetime.now().strftime('%Y-%m-%d')
    conn = get_db_connection()
    c = conn.cursor()
    
    # Today's Sales
    c.execute("SELECT SUM(total_amount) FROM restaurant_bills WHERE hotel_id = ? AND created_at LIKE ?", (hotel_id, today + '%'))
    sales = c.fetchone()[0] or 0
    
    # Today's Orders
    c.execute("SELECT COUNT(*) FROM restaurant_bills WHERE hotel_id = ? AND created_at LIKE ?", (hotel_id, today + '%'))
    orders = c.fetchone()[0] or 0
    
    # Occupied Tables
    c.execute("SELECT COUNT(*) FROM restaurant_tables WHERE hotel_id = ? AND status = 'occupied'", (hotel_id,))
    occupied = c.fetchone()[0] or 0
    
    conn.close()
    return jsonify({
        'sales': sales,
        'orders': orders,
        'occupied': occupied
    })

@app.route('/api/restaurant/expenses')
@login_required
def get_restaurant_expenses():
    hotel_id = session.get('hotel_id')
    date = request.args.get('date')
    month = request.args.get('month')
    year = request.args.get('year')

    conn = get_db_connection()
    c = conn.cursor()
    
    query = "SELECT id, name, amount, category, date FROM expenses WHERE hotel_id = ?"
    params = [hotel_id]

    if date:
        query += " AND date LIKE ?"
        params.append(date + '%')
    elif month:
        query += " AND date LIKE ?"
        params.append(month + '%')
    elif year:
        query += " AND date LIKE ?"
        params.append(year + '%')

    query += " ORDER BY date DESC"
    
    c.execute(query, params)
    expenses = [{'id': r[0], 'name': r[1], 'amount': r[2], 'category': r[3], 'date': r[4]} for r in c.fetchall()]
    conn.close()
    return jsonify(expenses)

@app.route('/api/restaurant/expenses/add', methods=['POST'])
@admin_required
def add_restaurant_expense():
    data = request.json
    hotel_id = session.get('hotel_id')
    name = data.get('name')
    amount = data.get('amount')
    category = data.get('category', 'General')
    date = data.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    if not all([name, amount]):
        return jsonify({'success': False, 'message': 'Name and amount required'})
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO expenses (hotel_id, name, amount, category, date) VALUES (?, ?, ?, ?, ?)",
              (hotel_id, name, amount, category, date))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/restaurant/expenses/delete/<int:expense_id>', methods=['DELETE'])
@admin_required
def delete_restaurant_expense(expense_id):
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM expenses WHERE id = ? AND hotel_id = ?", (expense_id, hotel_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/restaurant/financial_summary')
@login_required
def get_restaurant_financial_summary():
    hotel_id = session.get('hotel_id')
    period = request.args.get('period')  # today, month, year
    c_date = request.args.get('date')
    c_month = request.args.get('month')
    c_year = request.args.get('year')
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # Determine date filter
    if c_date:
        date_filter = c_date + '%'
    elif c_month:
        date_filter = c_month + '%'
    elif c_year:
        date_filter = c_year + '%'
    elif period == 'today':
        date_filter = datetime.now().strftime('%Y-%m-%d') + '%'
    elif period == 'month':
        date_filter = datetime.now().strftime('%Y-%m') + '%'
    elif period == 'year':
        date_filter = datetime.now().strftime('%Y') + '%'
    else:
        date_filter = '%'  # all time
    
    # Calculate revenue (paid bills)
    c.execute("SELECT SUM(total_amount) FROM restaurant_bills WHERE hotel_id = ? AND payment_status = 'paid' AND created_at LIKE ?", 
              (hotel_id, date_filter))
    revenue = c.fetchone()[0] or 0
    
    # Calculate expenses
    c.execute("SELECT SUM(amount) FROM expenses WHERE hotel_id = ? AND date LIKE ?",
              (hotel_id, date_filter))
    expenses = c.fetchone()[0] or 0
    
    conn.close()
    
    profit = revenue - expenses
    
    return jsonify({
        'revenue': revenue,
        'expenses': expenses,
        'profit': profit
    })

# --- Inventory API ---

@app.route('/api/restaurant/inventory')
@login_required
def get_inventory():
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, item_name, category, stock_quantity, unit, alert_level FROM restaurant_inventory WHERE hotel_id = ?", (hotel_id,))
    items = []
    for r in c.fetchall():
        items.append({
            'id': r[0],
            'name': r[1],
            'category': r[2],
            'stock': r[3],
            'unit': r[4],
            'alert_level': r[5]
        })
    conn.close()
    return jsonify(items)

@app.route('/api/restaurant/inventory/add', methods=['POST'])
@owner_required
def add_inventory_item():
    data = request.json
    hotel_id = session.get('hotel_id')
    name = data.get('name')
    category = data.get('category')
    stock = data.get('stock', 0)
    unit = data.get('unit', 'pcs')
    alert = data.get('alert_level', 5)
    
    if not name:
        return jsonify({'success': False, 'message': 'Item name required'})
        
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO restaurant_inventory (hotel_id, item_name, category, stock_quantity, unit, alert_level) VALUES (?, ?, ?, ?, ?, ?)",
              (hotel_id, name, category, stock, unit, alert))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/restaurant/inventory/update/<int:item_id>', methods=['POST'])
@login_required
def update_inventory_stock(item_id):
    data = request.json
    hotel_id = session.get('hotel_id')
    change = data.get('change', 0) # Positive for inward, negative for outward
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE restaurant_inventory SET stock_quantity = stock_quantity + ? WHERE id = ? AND hotel_id = ?", (change, item_id, hotel_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/restaurant/inventory/delete/<int:item_id>', methods=['DELETE'])
@owner_required
def delete_inventory_item(item_id):
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM restaurant_inventory WHERE id = ? AND hotel_id = ?", (item_id, hotel_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/switch_system')
@login_required
def switch_system():
    current = session.get('active_system', 'hotel')
    hotel_id = session.get('hotel_id')
    
    # Verify they actually have both plans before allowing switch
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT is_hotel_active, is_restaurant_active FROM hotels WHERE id = ?", (hotel_id,))
    h_data = c.fetchone()
    conn.close()
    
    if h_data and h_data[0] and h_data[1]:
        session['active_system'] = 'restaurant' if current == 'hotel' else 'hotel'
        target = 'dashboard' if session['active_system'] == 'hotel' else 'restaurant_dashboard'
        return redirect(url_for(target))
    
    return redirect(url_for('dashboard'))

@app.route('/api/rooms')
@login_required
def get_rooms():
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()
    
    # Updated query for Multi-Tenancy
    # critical: filtering by hotel_id for both rooms and joined bookings
    c.execute('''SELECT 
                    r.room_id, 
                    r.status, 
                    COALESCE(b.guest_name, b_legacy.guest_name) as guest_name, 
                    COALESCE(b.id, b_legacy.id) as booking_id, 
                    r.last_checkout, 
                    r.room_type, 
                    COALESCE(g.status, g_legacy.status) as guest_status
                 FROM rooms r
                 -- New System Join
                 LEFT JOIN booking_rooms br ON r.room_id = br.room_id
                 LEFT JOIN bookings b ON br.booking_id = b.id AND b.status = 'active' AND b.hotel_id = r.hotel_id
                 LEFT JOIN guests g ON b.phone = g.phone AND g.hotel_id = r.hotel_id
                 -- Legacy System Join (Fallback)
                 LEFT JOIN bookings b_legacy ON r.room_id = b_legacy.room_id AND b_legacy.status = 'active' AND b_legacy.hotel_id = r.hotel_id
                 LEFT JOIN guests g_legacy ON b_legacy.phone = g_legacy.phone AND g_legacy.hotel_id = r.hotel_id
                 WHERE r.hotel_id = ?''', (hotel_id,))
                 
    rooms_dict = {}
    for row in c.fetchall():
        room_id = row[0]
        status = row[1]
        
        # Validation: If we already processed this room
        if room_id in rooms_dict:
            # If current stored version has a booking_id, keep it
            if rooms_dict[room_id]['booking_id']:
                continue
            # If current stored version is occupied but new row is available, keep occupied
            if rooms_dict[room_id]['status'] == 'occupied' and status != 'occupied':
                continue
        
        rooms_dict[room_id] = {
            'room_id': row[0], 
            'status': row[1], 
            'guest_name': row[2], 
            'booking_id': row[3],
            'last_checkout': row[4], 
            'room_type': row[5],
            'guest_status': row[6]
        }

    # Auto-heal: if a room is 'occupied' but has no active booking, reset it to 'available'
    for room_id, room in rooms_dict.items():
        if room['status'] == 'occupied' and not room['booking_id']:
            c.execute("UPDATE rooms SET status = 'available' WHERE room_id = ? AND hotel_id = ?", (room_id, hotel_id))
            rooms_dict[room_id]['status'] = 'available'
    conn.commit()

    # Check for Today's Reservations
    today_str = datetime.now().strftime('%Y-%m-%d')
    c.execute('''SELECT room_id, guest_name FROM bookings 
                 WHERE hotel_id = ? AND status = 'reserved' 
                 AND date(checkin_time) <= ? AND date(checkout_time) >= ?''', 
              (hotel_id, today_str, today_str))
    
    for row in c.fetchall():
        rid, gname = row[0], row[1]
        if rid in rooms_dict and rooms_dict[rid]['status'] == 'available':
            rooms_dict[rid]['status'] = 'reserved'
            rooms_dict[rid]['guest_name'] = gname # Show reserved guest name

    conn.close()
    return jsonify(list(rooms_dict.values()))

@app.route('/api/rooms/add', methods=['POST'])
@admin_required
def add_room():
    if session.get('role') not in ['admin', 'owner']:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
    data = request.json
    hotel_id = session.get('hotel_id')
    room_id = data.get('room_id')
    room_type = data.get('room_type')
    
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO rooms (room_id, hotel_id, status, room_type) VALUES (?, ?, 'available', ?)",
                  (room_id, hotel_id, room_type))
        conn.commit()
        return jsonify({'success': True})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'Room already exists'})
    finally:
        conn.close()

@app.route('/api/rooms/delete', methods=['POST'])
@admin_required
def delete_room():
    data = request.json
    room_id = data.get('room_id')
    hotel_id = session.get('hotel_id')
    
    if not room_id:
        return jsonify({'success': False, 'message': 'Missing Room ID'}), 400
        
    conn = get_db_connection()
    c = conn.cursor()
    
    # Check if the room has active bookings
    c.execute("SELECT COUNT(*) FROM bookings WHERE room_id = ? AND hotel_id = ? AND status = 'active'", 
              (room_id, hotel_id))
    active_count = c.fetchone()[0]
    
    if active_count > 0:
        conn.close()
        return jsonify({'success': False, 'message': 'Cannot delete a room with active bookings. Please check-out the guest first.'})

    try:
        c.execute("DELETE FROM rooms WHERE room_id = ? AND hotel_id = ?", (room_id, hotel_id))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/api/book', methods=['POST'])
@login_required
def book_room():
    data = request.form
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()
    
    room_ids = data.get('room_ids', '').split(',')
    if not room_ids or room_ids == ['']:
        room_ids = [data.get('room_id')]

    checkin_time = data.get('checkin_time', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    # Collision Check
    # Check if any of the requested rooms has a reservation for TODAY
    # Logic: If I check in now, I collide with any reservation that overlaps with [now, now+24h] roughly, 
    # but simplest is: Is there a reservation for this room overlapping 'today'?
    checkin_date = checkin_time.split(' ')[0]
    for rid in room_ids:
        c.execute('''SELECT guest_name FROM bookings 
                     WHERE hotel_id = ? AND room_id = ? AND status = 'reserved'
                     AND date(checkin_time) <= ? AND date(checkout_time) >= ?''',
                  (hotel_id, rid, checkin_date, checkin_date))
        conflict = c.fetchone()
        
        # New Logic: Conflict Management
        if conflict:
            if not data.get('force_override'):
                 conn.close()
                 return jsonify({
                     'success': False, 
                     'message': f"Room {rid} is reserved for {conflict[0]}. Confirm to override?",
                     'requires_confirmation': True
                 })
            else:
                # If overriding, we 'fulfill' the reservation so it doesn't block or clutter
                # Update the colliding reservation to 'fulfilled' status
                # We assume the user is converting this reservation.
                c.execute("UPDATE bookings SET status = 'fulfilled' WHERE hotel_id = ? AND room_id = ? AND status = 'reserved' AND date(checkin_time) <= ? AND date(checkout_time) >= ?",
                          (hotel_id, rid, checkin_date, checkin_date))

    import json
    members = data.get('members', '[]')
    try:
        members_data = json.loads(members)
    except:
        members_data = []

    id_photo_paths = []
    base_room = room_ids[0] if room_ids else 'room'
    
    # Collect files from all photo file input keys
    upload_files = []
    if 'id_photos' in request.files:
        upload_files.extend(request.files.getlist('id_photos'))
    if 'id_photo' in request.files:
        upload_files.extend(request.files.getlist('id_photo'))
        
    for file in upload_files:
        if file and getattr(file, 'filename', None):
            rel_path = save_uploaded_file(file, prefix=f"h{hotel_id}_{base_room}")
            if rel_path:
                id_photo_paths.append(rel_path)

    if len(members_data) == 0:
        if len(id_photo_paths) < 1:
            conn.close()
            return jsonify({'success': False, 'message': 'ID Photo is compulsory for primary guest'})
    else:
        if len(id_photo_paths) < 2:
            conn.close()
            return jsonify({'success': False, 'message': 'Minimum 2 ID photos required when there are multiple guests'})

    id_photos_str = ','.join(id_photo_paths) if id_photo_paths else None
    main_room_str = ','.join(room_ids)
    members = data.get('members', '[]')
    
    c.execute('''INSERT INTO bookings
                 (hotel_id, room_id, guest_name, phone, address, id_number, id_photo, members, amount, checkin_time, status)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')''',
              (hotel_id, main_room_str, data['guest_name'], data['phone'], data['address'],
               data['id_number'], id_photos_str, members, float(data['amount']), checkin_time))
    
    booking_id = c.lastrowid
    
    for rid in room_ids:
        c.execute("INSERT INTO booking_rooms (booking_id, room_id) VALUES (?, ?)", (booking_id, rid))
        c.execute("UPDATE rooms SET status = 'occupied' WHERE room_id = ? AND hotel_id = ?", (rid, hotel_id))
        
    c.execute('''INSERT OR REPLACE INTO guests (phone, hotel_id, name, id_number, address, status)
                 VALUES (?, ?, ?, ?, ?, COALESCE((SELECT status FROM guests WHERE phone = ? AND hotel_id = ?), 'regular'))''',
              (data['phone'], hotel_id, data['guest_name'], data['id_number'], data['address'], data['phone'], hotel_id))

    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/booking/<int:booking_id>')
@login_required
def get_booking(booking_id):
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM bookings WHERE id = ? AND hotel_id = ?', (booking_id, hotel_id))
    row = c.fetchone()
    conn.close()

    if row:
        booking = {
            'id': row[0], 'room_id': row[2], 'guest_name': row[3], 'phone': row[4],
            'address': row[5], 'id_number': row[6], 'id_photo': row[7], 'amount': row[8],
            'checkin_time': row[9], 'checkout_time': row[10], 'extra_charges': row[11],
            'food': row[12], 'laundry': row[13], 'water_bottle': row[14], 'car_wash': row[15]
        }
        return jsonify(booking)
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/checkout', methods=['POST'])
@login_required
def checkout():
    data = request.json
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()

    checkout_time = data.get('checkout_time', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    extra_charges = data.get('food', 0) + data.get('laundry', 0) + data.get('water_bottle', 0) + data.get('car_wash', 0)

    # Validate booking belongs to hotel
    c.execute("UPDATE bookings SET checkout_time = ?, food = ?, laundry = ?, water_bottle = ?, car_wash = ?, extra_charges = ?, status = 'completed' WHERE id = ? AND hotel_id = ?",
              (checkout_time, data.get('food', 0), data.get('laundry', 0),
               data.get('water_bottle', 0), data.get('car_wash', 0), extra_charges, data['booking_id'], hotel_id))
    
    if c.rowcount == 0:
         conn.close()
         return jsonify({'success': False, 'message': 'Booking not found or access denied'})

    # Get all rooms associated with this booking
    c.execute("SELECT room_id FROM booking_rooms WHERE booking_id = ?", (data['booking_id'],))
    room_rows = c.fetchall()
    
    if room_rows:
        room_ids = [row[0] for row in room_rows]
    else:
        c.execute("SELECT room_id FROM bookings WHERE id = ?", (data['booking_id'],))
        row = c.fetchone()
        room_ids = [row[0]] if row else []
        
    for rid in room_ids:
        c.execute("UPDATE rooms SET status = 'dirty', last_checkout = ? WHERE room_id = ? AND hotel_id = ?", (checkout_time, rid, hotel_id))

    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/clean-room/<room_id>', methods=['POST'])
@login_required
def clean_room(room_id):
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE rooms SET status = 'available', last_checkout = NULL WHERE room_id = ? AND hotel_id = ?", (room_id, hotel_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/financials')
@login_required
@admin_required
def get_financials():
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()

    # Daily revenue
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute('''SELECT SUM(amount + extra_charges) FROM bookings
                 WHERE DATE(checkout_time) = ? AND status = 'completed' AND hotel_id = ?''', (today, hotel_id))
    daily = c.fetchone()[0] or 0

    # Daily expenses
    c.execute('''SELECT SUM(amount) FROM expenses
                 WHERE DATE(date) = ? AND hotel_id = ?''', (today, hotel_id))
    daily_expenses = c.fetchone()[0] or 0

    # Daily profit
    daily_profit = daily - daily_expenses

    # Monthly revenue
    month = datetime.now().strftime('%Y-%m')
    c.execute('''SELECT SUM(amount + extra_charges) FROM bookings
                 WHERE strftime('%Y-%m', checkout_time) = ? AND status = 'completed' AND hotel_id = ?''', (month, hotel_id))
    monthly = c.fetchone()[0] or 0

    # Yearly revenue
    year = datetime.now().strftime('%Y')
    c.execute('''SELECT SUM(amount + extra_charges) FROM bookings
                 WHERE strftime('%Y', checkout_time) = ? AND status = 'completed' AND hotel_id = ?''', (year, hotel_id))
    yearly = c.fetchone()[0] or 0

    conn.close()
    return jsonify({
        'daily': daily,
        'daily_expenses': daily_expenses,
        'daily_profit': daily_profit,
        'monthly': monthly,
        'yearly': yearly
    })

@app.route('/api/financials/ledger')
@login_required
@admin_required
def get_financial_ledger():
    try:
        hotel_id = session.get('hotel_id')
        date_range = request.args.get('range', '30days')
        specific_date = request.args.get('date') # Format: YYYY-MM-DD
        
        conn = get_db_connection()
        c = conn.cursor()
        
        # Determine Start Date
        today = datetime.now().date()
        if specific_date:
            start_str = specific_date
            end_str = specific_date
        else:
            if date_range == 'today':
                start_date = today
            elif date_range == '7days':
                start_date = today - timedelta(days=6)
            elif date_range == 'month':
                start_date = today.replace(day=1)
            else: # 30days default
                start_date = today - timedelta(days=29)
            start_str = start_date.strftime('%Y-%m-%d')
            end_str = None

        # 1. Fetch Income (Completed Bookings)
        if specific_date:
            c.execute('''SELECT checkout_time, guest_name, room_id, amount, extra_charges, id 
                         FROM bookings 
                         WHERE hotel_id = ? AND status = 'completed' AND date(checkout_time) = ?
                         ORDER BY checkout_time DESC''', (hotel_id, start_str))
        else:
            c.execute('''SELECT checkout_time, guest_name, room_id, amount, extra_charges, id 
                         FROM bookings 
                         WHERE hotel_id = ? AND status = 'completed' AND date(checkout_time) >= ?
                         ORDER BY checkout_time DESC''', (hotel_id, start_str))
        income_rows = c.fetchall()
        
        # 2. Fetch Expenses
        if specific_date:
            c.execute('''SELECT date, name, category, amount 
                         FROM expenses 
                         WHERE hotel_id = ? AND date(date) = ?
                         ORDER BY date DESC''', (hotel_id, start_str))
        else:
            c.execute('''SELECT date, name, category, amount 
                         FROM expenses 
                         WHERE hotel_id = ? AND date(date) >= ?
                         ORDER BY date DESC''', (hotel_id, start_str))
        expense_rows = c.fetchall()
        
        # 3. Process Transactions & Totals
        transactions = []
        total_revenue = 0
        total_expenses = 0
        expense_cats = {}
        
        for row in income_rows:
            amt = (row[3] or 0) + (row[4] or 0)
            total_revenue += amt
            # Safety check for checkout_time
            raw_date = row[0] or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            transactions.append({
                'id': row[5], # Booking ID
                'date': raw_date.split(' ')[0],
                'description': f"Stay: {row[1]} (Room {row[2]})",
                'type': 'income',
                'category': 'Room Revenue',
                'amount': amt,
                'timestamp': raw_date
            })

        for row in expense_rows:
            amt = row[3] or 0
            total_expenses += amt
            cat = row[2] or 'General'
            expense_cats[cat] = expense_cats.get(cat, 0) + amt
            raw_date = row[0] or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            transactions.append({
                'date': raw_date.split(' ')[0],
                'description': row[1],
                'type': 'expense',
                'category': cat,
                'amount': amt,
                'timestamp': raw_date 
            })
            
        # Sort transactions by date desc
        transactions.sort(key=lambda x: str(x['timestamp']), reverse=True)
        
        # 4. Prepare Chart Data (Daily Aggregation)
        chart_data = {}
        delta = (today - start_date).days + 1
        for i in range(delta):
            d = (start_date + timedelta(days=i)).strftime('%Y-%m-%d')
            chart_data[d] = {'revenue': 0, 'expenses': 0}
            
        for t in transactions:
            d = t['date']
            if d in chart_data:
                if t['type'] == 'income':
                    chart_data[d]['revenue'] += t['amount']
                else:
                    chart_data[d]['expenses'] += t['amount']
                    
        # Flatten for Chart.js
        sorted_dates = sorted(chart_data.keys())
        chart_labels = [datetime.strptime(d, '%Y-%m-%d').strftime('%b %d') for d in sorted_dates]
        chart_revenue = [chart_data[d]['revenue'] for d in sorted_dates]
        chart_daily_expenses = [chart_data[d]['expenses'] for d in sorted_dates]

        conn.close()
        
        return jsonify({
            'revenue': total_revenue,
            'expenses': total_expenses,
            'profit': total_revenue - total_expenses,
            'transactions': transactions[:100],
            'chart_labels': chart_labels,
            'chart_revenue': chart_revenue,
            'chart_expenses': chart_daily_expenses,
            'expense_breakdown': expense_cats
        })
    except Exception as e:
        import traceback
        print("LEDGER ERROR:", str(e))
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics')
@login_required
@admin_required
def get_analytics():
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()

    # 1. Last 30 Days Revenue & Expenses
    dates = []
    revenues = []
    expenses = []
    
    today = datetime.now()
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        date_str = d.strftime('%Y-%m-%d')
        dates.append(d.strftime('%b %d'))
        
        # Revenue
        c.execute("SELECT SUM(amount + extra_charges) FROM bookings WHERE DATE(checkout_time) = ? AND status = 'completed' AND hotel_id = ?", (date_str, hotel_id))
        rev = c.fetchone()[0] or 0
        revenues.append(rev)
        
        # Expense
        c.execute("SELECT SUM(amount) FROM expenses WHERE DATE(date) = ? AND hotel_id = ?", (date_str, hotel_id))
        exp = c.fetchone()[0] or 0
        expenses.append(exp)

    # 2. Room Occupancy Stats (Using CURRENT occupied rooms)
    # Actually, let's show ALL rooms distribution (Occupied vs Available vs Dirty) 
    # OR Room Type popularity? The plan said "Occupancy Split". 
    # Let's do Room Type count based on existing rooms.
    c.execute("SELECT room_type, COUNT(*) FROM rooms WHERE hotel_id = ? GROUP BY room_type", (hotel_id,))
    room_counts = dict(c.fetchall())

    conn.close()
    
    return jsonify({
        'dates': dates,
        'revenue': revenues,
        'expenses': expenses,
        'room_counts': room_counts
    })

@app.route('/api/reservations')
@login_required
def get_reservations():
    hotel_id = session.get('hotel_id')
    include_history = request.args.get('history', 'false') == 'true'
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # Fetch bookings
    # If history=true, show ALL (cancelled, fulfilled, outdated).
    # If history=false (default), show only active, reserved, completed (for past views)
    # Actually, fulfilled means it became active, so we don't show the 'fulfilled' stub in default view, we show the 'active' one.
    
    query = '''SELECT guest_name, room_id, checkin_time, checkout_time, status 
               FROM bookings 
               WHERE hotel_id = ?'''
               
    if not include_history:
        # Hide internal states
        query += " AND status NOT IN ('cancelled', 'fulfilled')"
        
    c.execute(query, (hotel_id,))
    
    events = []
    for row in c.fetchall():
        name, room, start, end, status = row
        
        color = '#10b981' # Green (Completed)
        if status == 'active': color = '#f59e0b' # Orange (Active)
        if status == 'reserved': color = '#3b82f6' # Blue (Reserved)
        if status == 'cancelled': color = '#9ca3af' # Grey (Cancelled)
        if status == 'fulfilled': color = '#8b5cf6' # Purple (Converted) - mostly hidden

        events.append({
            'resourceId': room,
            'title': f"{name} ({status})" if include_history else name,
            'start': start,
            'end': end,
            'backgroundColor': color,
            'borderColor': 'transparent',
            'extendedProps': {'status': status}
        })
        
    conn.close()
    return jsonify(events)

@app.route('/api/reports')
@login_required
@admin_required
def get_reports():
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()
    
    # 1. Monthly Summary
    # We join with booking_rooms to get accurate per-room count if available, 
    # otherwise fallback to count of bookings.
    c.execute('''
        SELECT 
            strftime('%Y-%m', b.checkout_time) as month,
            SUM(b.amount + b.extra_charges) as revenue,
            COUNT(DISTINCT b.id) as booking_count
        FROM bookings b
        WHERE b.hotel_id = ? AND b.status = 'completed'
        GROUP BY month
        ORDER BY month DESC
    ''', (hotel_id,))
    monthly_raw = c.fetchall()
    
    # Get monthly expenses
    c.execute('''
        SELECT 
            strftime('%Y-%m', date) as month,
            SUM(amount) as expenses
        FROM expenses
        WHERE hotel_id = ?
        GROUP BY month
    ''', (hotel_id,))
    monthly_expenses = dict(c.fetchall())
    
    # Get yearly summary
    c.execute('''
        SELECT 
            strftime('%Y', b.checkout_time) as year,
            SUM(b.amount + b.extra_charges) as revenue,
            COUNT(DISTINCT b.id) as booking_count
        FROM bookings b
        WHERE b.hotel_id = ? AND b.status = 'completed'
        GROUP BY year
        ORDER BY year DESC
    ''', (hotel_id,))
    yearly_raw = c.fetchall()
    
    # Get yearly expenses
    c.execute('''
        SELECT 
            strftime('%Y', date) as year,
            SUM(amount) as expenses
        FROM expenses
        WHERE hotel_id = ?
        GROUP BY year
    ''', (hotel_id,))
    yearly_expenses = dict(c.fetchall())

    # Format Monthly
    monthly = []
    for row in monthly_raw:
        m = row[0]
        revenue = row[1] or 0
        exp = monthly_expenses.get(m, 0)
        monthly.append({
            'period': m,
            'revenue': revenue,
            'expenses': exp,
            'profit': revenue - exp,
            'rooms_booked': row[2] # Fallback to booking count for simplicity unless specific room count is needed
        })

    # Format Yearly
    yearly = []
    for row in yearly_raw:
        y = row[0]
        revenue = row[1] or 0
        exp = yearly_expenses.get(y, 0)
        yearly.append({
            'period': y,
            'revenue': revenue,
            'expenses': exp,
            'profit': revenue - exp,
            'rooms_booked': row[2]
        })

    conn.close()
    return jsonify({
        'monthly': monthly,
        'yearly': yearly
    })



@app.route('/api/reserve', methods=['POST', 'DELETE'])
@login_required
def reserve_room():
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()

    if request.method == 'DELETE':
        data = request.json
        guest_name = data.get('guest_name')
        room_id = data.get('room_id')
        
        try:
            # Soft Delete (Cancel) reservation
            c.execute("UPDATE bookings SET status = 'cancelled' WHERE hotel_id = ? AND room_id = ? AND guest_name = ? AND status = 'reserved'", 
                      (hotel_id, room_id, guest_name))
            conn.commit()
            conn.close()
            return jsonify({'success': True})
        except Exception as e:
            conn.close()
            return jsonify({'success': False, 'message': str(e)})

    # POST (Create)
    data = request.json
    try:
        # Insert reservation
        c.execute('''INSERT INTO bookings 
                     (hotel_id, guest_name, phone, room_id, members, checkin_time, checkout_time, status, amount)
                     VALUES (?, ?, ?, ?, ?, ?, ?, 'reserved', 0)''', 
                  (hotel_id, data['guest_name'], data['phone'], data['room_id'], data.get('members', '[]'),
                   data['checkin_date'], data['checkout_date']))
        
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/guests')
@login_required
def get_guests():
    hotel_id = session.get('hotel_id')
    date_q  = request.args.get('date')   # YYYY-MM-DD
    month_q = request.args.get('month')  # YYYY-MM

    conn = get_db_connection()
    c = conn.cursor()

    query  = '''SELECT id, guest_name, phone, checkin_time, checkout_time, room_id, members
                FROM bookings WHERE hotel_id = ?'''
    params = [hotel_id]

    if date_q:
        query += ' AND checkin_time LIKE ?'
        params.append(f'{date_q}%')
    elif month_q:
        query += ' AND checkin_time LIKE ?'
        params.append(f'{month_q}%')

    query += ' ORDER BY id DESC'
    c.execute(query, params)
    guests = []
    for row in c.fetchall():
        members = []
        if row[6]:
            try:
                import json
                parsed = json.loads(row[6])
                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict):
                            name = item.get('name') or item.get('full_name')
                            age = item.get('age')
                            if name:
                                if age:
                                    members.append(f"{name} ({age})")
                                else:
                                    members.append(name)
                        elif item:
                            members.append(str(item))
                elif isinstance(parsed, dict):
                    name = parsed.get('name') or parsed.get('full_name')
                    age = parsed.get('age')
                    if name:
                        if age:
                            members.append(f"{name} ({age})")
                        else:
                            members.append(name)
            except Exception:
                members = []
        guests.append({
            'id': row[0],
            'guest_name': row[1],
            'phone': row[2],
            'checkin_time': row[3],
            'checkout_time': row[4],
            'room_id': row[5],
            'members': members
        })
    conn.close()
    return jsonify(guests)

@app.route('/api/guest/update', methods=['POST'])
@login_required
def update_guest():
    try:
        if request.is_json:
            data = request.json or {}
        else:
            data = request.form or {}
            
        hotel_id = session.get('hotel_id')
        old_phone = data.get('old_phone')
        new_name = data.get('name')
        new_email = data.get('email')
        new_phone = data.get('phone')
        booking_id = data.get('booking_id')
        members_json = data.get('members')
        new_amount = data.get('amount')
        
        if not all([old_phone, new_name, new_phone]):
            return jsonify({'success': False, 'message': 'Missing required fields'})
            
        # Process any uploaded photos
        new_id_photos = []
        for key in ['id_photo', 'id_photos']:
            if key in request.files:
                for file in request.files.getlist(key):
                    rel_path = save_uploaded_file(file, prefix=f"h{hotel_id}_update")
                    if rel_path:
                        new_id_photos.append(rel_path)
                        
        conn = get_db_connection()
        c = conn.cursor()
        
        try:
            target_phone = new_phone if old_phone != new_phone else old_phone

            if old_phone != new_phone:
                c.execute("SELECT phone FROM guests WHERE phone = ? AND hotel_id = ?", (new_phone, hotel_id))
                if c.fetchone():
                    return jsonify({'success': False, 'message': 'New phone number already belongs to another profile'})
                    
                c.execute("""UPDATE guests SET phone = ?, name = ?, email = ?
                             WHERE phone = ? AND hotel_id = ?""",
                          (new_phone, new_name, new_email, old_phone, hotel_id))
                
                c.execute("UPDATE bookings SET phone = ?, guest_name = ? WHERE phone = ? AND hotel_id = ?",
                          (new_phone, new_name, old_phone, hotel_id))
                c.execute("UPDATE restaurant_bills SET customer_mobile = ? WHERE customer_mobile = ? AND hotel_id = ?",
                          (new_phone, old_phone, hotel_id))
            else:
                c.execute("""UPDATE guests SET name = ?, email = ?
                             WHERE phone = ? AND hotel_id = ?""",
                          (new_name, new_email, old_phone, hotel_id))
                
                c.execute("UPDATE bookings SET guest_name = ? WHERE phone = ? AND hotel_id = ?",
                          (new_name, old_phone, hotel_id))

            # Update members and amount on the specific booking if booking_id supplied
            if booking_id:
                if members_json is not None:
                    c.execute("UPDATE bookings SET members = ? WHERE id = ? AND hotel_id = ?",
                              (members_json, booking_id, hotel_id))
                if new_amount is not None:
                    c.execute("UPDATE bookings SET amount = ? WHERE id = ? AND hotel_id = ?",
                              (new_amount, booking_id, hotel_id))

            if new_id_photos:
                photo_str = ','.join(new_id_photos)
                c.execute("""UPDATE bookings SET id_photo = CASE 
                             WHEN id_photo IS NULL OR id_photo = '' THEN ? 
                             ELSE id_photo || ',' || ? END 
                             WHERE phone = ? AND hotel_id = ?""",
                          (photo_str, photo_str, target_phone, hotel_id))

            conn.commit()
            return jsonify({'success': True})
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/guest/<int:guest_id>')
@login_required
def get_guest_details(guest_id):
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM bookings WHERE id = ? AND hotel_id = ?', (guest_id, hotel_id))
    row = c.fetchone()
    conn.close()

    if row:
        raw_members = row['members'] if 'members' in row.keys() else '[]'
        member_names = []
        try:
            if raw_members:
                parsed_members = json.loads(raw_members)
                if isinstance(parsed_members, list):
                    for member in parsed_members:
                        if isinstance(member, dict):
                            name = member.get('name') or member.get('full_name')
                            age = member.get('age')
                            if name:
                                if age:
                                    member_names.append(f"{name} ({age})")
                                else:
                                    member_names.append(name)
                        elif member:
                            member_names.append(str(member))
                elif isinstance(parsed_members, dict):
                    name = parsed_members.get('name') or parsed_members.get('full_name')
                    age = parsed_members.get('age')
                    if name:
                        if age:
                            member_names.append(f"{name} ({age})")
                        else:
                            member_names.append(name)
        except Exception:
            member_names = []

        guest = {
            'id': row['id'], 'room_id': row['room_id'], 'guest_name': row['guest_name'], 'phone': row['phone'],
            'address': row['address'], 'id_number': row['id_number'], 'id_photo': row['id_photo'],
            'amount': row['amount'], 'checkin_time': row['checkin_time'], 'checkout_time': row['checkout_time'],
            'extra_charges': row['extra_charges'],
            'food': row['food'], 'laundry': row['laundry'], 'water_bottle': row['water_bottle'], 'car_wash': row['car_wash'],
            'members': member_names
        }
        return jsonify(guest)
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/expenses', methods=['GET', 'POST'])
@login_required
def expenses():
    try:
        hotel_id = session.get('hotel_id')
        conn = get_db_connection()
        c = conn.cursor()

        if request.method == 'POST':
            data = request.json
            user_date = data.get('date')
            if user_date:
                # If only date is selected (YYYY-MM-DD), append the current time of day
                if len(user_date) == 10:
                    current_time = datetime.now().strftime('%H:%M:%S')
                    date = f"{user_date} {current_time}"
                else:
                    date = user_date
            else:
                date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            category = data.get('category', 'General')
            c.execute('INSERT INTO expenses (hotel_id, name, amount, category, date) VALUES (?, ?, ?, ?, ?)',
                      (hotel_id, data['name'], data['amount'], category, date))
            conn.commit()
            conn.close()
            return jsonify({'success': True})

        # GET Handling with filters
        date_q = request.args.get('date')
        month_q = request.args.get('month')
        year_q = request.args.get('year')

        query = 'SELECT id, name, amount, category, date FROM expenses WHERE hotel_id = ?'
        params = [hotel_id]

        if date_q:
            query += ' AND date LIKE ?'
            params.append(f'{date_q}%')
        elif month_q and year_q:
            query += ' AND date LIKE ?'
            params.append(f'{year_q}-{month_q}%')
        elif year_q:
            query += ' AND date LIKE ?'
            params.append(f'{year_q}%')

        query += ' ORDER BY id DESC'
        c.execute(query, tuple(params))
        
        expenses = [{'id': row[0], 'name': row[1], 'amount': row[2], 'category': row[3], 'date': row[4]}
                    for row in c.fetchall()]
        conn.close()
        return jsonify(expenses)
    except Exception as e:
        import traceback
        print("EXPENSE ERROR:", str(e))
        print(traceback.format_exc())
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/expenses/delete', methods=['POST'])
@login_required
def delete_expense():
    if session.get('role') not in ['owner', 'staff']:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
    data = request.json
    hotel_id = session.get('hotel_id')
    expense_id = data.get('id')
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM expenses WHERE id = ? AND hotel_id = ?", (expense_id, hotel_id))
    conn.commit()
    conn.close()
    
    # Audit Log
    log_action(session.get('user_id'), 'DELETE_EXPENSE', f"Deleted Expense ID {expense_id}", hotel_id)
    
    return jsonify({'success': True})

@app.route('/api/expenses/summary')
@login_required
def expenses_summary():
    try:
        hotel_id = session.get('hotel_id')
        conn = get_db_connection()
        c = conn.cursor()
        
        # 1. Total All Time
        c.execute("SELECT SUM(amount) FROM expenses WHERE hotel_id = ?", (hotel_id,))
        total_all_time = c.fetchone()[0] or 0
        
        # 2. Total Today (local date format YYYY-MM-DD)
        local_today = datetime.now().strftime('%Y-%m-%d')
        c.execute("SELECT SUM(amount) FROM expenses WHERE hotel_id = ? AND date LIKE ?", (hotel_id, f"{local_today}%"))
        total_today = c.fetchone()[0] or 0
        
        conn.close()
        return jsonify({
            'success': True,
            'total_all_time': total_all_time,
            'total_today': total_today
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/guests/delete', methods=['POST'])
@owner_required
def delete_guest_history():
    data = request.json
    hotel_id = session.get('hotel_id')
    guest_id = data.get('id') # This is the booking ID in the guests view
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # Fetch guest details BEFORE deleting for audit log
    c.execute("SELECT guest_name, room_id, status FROM bookings WHERE id = ? AND hotel_id = ?", (guest_id, hotel_id))
    row = c.fetchone()
    guest_name = row[0] if row else 'Unknown'
    room_number = row[1] if row else 'N/A'
    booking_status = row[2] if row else ''

    # Reset rooms to available if the booking was still active
    if booking_status in ('active', 'occupied'):
        # Check booking_rooms table first (multi-room bookings)
        c.execute("SELECT room_id FROM booking_rooms WHERE booking_id = ?", (guest_id,))
        linked_rooms = [r[0] for r in c.fetchall()]
        if not linked_rooms and room_number and room_number != 'N/A':
            linked_rooms = [room_number]
        for rid in linked_rooms:
            c.execute("UPDATE rooms SET status = 'available' WHERE room_id = ? AND hotel_id = ?", (rid, hotel_id))

    # Deleting from bookings effectively removes the history record
    c.execute("DELETE FROM bookings WHERE id = ? AND hotel_id = ?", (guest_id, hotel_id))
    conn.commit()
    conn.close()
    
    # Audit Log with room number
    log_action(session.get('user_id'), 'DELETE_GUEST', f"Deleted Guest '{guest_name}' from Room {room_number}", hotel_id)
    
    return jsonify({'success': True})


@app.route('/api/print-bill/<int:guest_id>')
@login_required
def print_bill(guest_id):
    return redirect(url_for('bill_page', guest_id=guest_id))

@app.route('/bill/<int:guest_id>')
@login_required
def bill_page(guest_id):
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT currency_symbol, tax_rate, name, email, phone FROM hotels WHERE id = ?", (hotel_id,))
    row = c.fetchone()
    conn.close()
    
    currency = row[0] if row else '₹'
    tax_rate = row[1] if row else 0.0
    hotel_name = row[2] if row else ''
    hotel_email = row[3] if row else ''
    hotel_phone = row[4] if row else ''
    hotel_address = ''
    
    return render_template('bill.html', 
                          guest_id=guest_id, 
                          currency=currency, 
                          tax_rate=tax_rate,
                          hotel_name=hotel_name,
                          hotel_email=hotel_email,
                          hotel_phone=hotel_phone,
                          hotel_address=hotel_address)

@app.route('/restaurant/bill/<int:bill_id>')
@login_required
def restaurant_bill_page(bill_id):
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT currency_symbol, tax_rate, name, email, phone FROM hotels WHERE id = ?", (hotel_id,))
    row = c.fetchone()
    conn.close()
    
    currency = row[0] if row else '₹'
    tax_rate = row[1] if row else 0.0
    hotel_name = row[2] if row else ''
    hotel_email = row[3] if row else ''
    hotel_phone = row[4] if row else ''
    hotel_address = ''
    
    return render_template('restaurant_bill.html', 
                          bill_id=bill_id, 
                          currency=currency, 
                          tax_rate=tax_rate,
                          hotel_name=hotel_name,
                          hotel_email=hotel_email,
                          hotel_phone=hotel_phone,
                          hotel_address=hotel_address)
@app.route('/settings')
@login_required
def settings_page():
    if session.get('role') not in ['owner', 'staff']:
        return redirect(url_for('dashboard'))
    
    # Get housekeeping token & finance settings & hotel profile
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT housekeeping_token, currency_symbol, tax_rate, google_review_url, name, email, phone FROM hotels WHERE id = ?", (hotel_id,))
    row = c.fetchone()
    
    # Auto-generate token if missing (Self-healing for old accounts)
    token = row[0] if row else None
    if token is None or token == 'None' or token == '':
        token = secrets.token_urlsafe(16)
        c.execute("UPDATE hotels SET housekeeping_token = ? WHERE id = ?", (token, hotel_id))
        conn.commit()
        
    conn.close()
    
    # row indices: 0:token, 1:currency, 2:tax, 3:google_review_url, 4:name, 5:email, 6:phone
    currency = row[1] if row else '₹'
    tax = row[2] if row else 0.0
    google_review_url = row[3] if row else ''
    hotel_name = row[4] if row else ''
    hotel_email = row[5] if row else ''
    hotel_phone = row[6] if row else ''
    
    return render_template('settings.html', 
                          housekeeping_token=token, 
                          currency=currency, 
                          tax_rate=tax, 
                          google_review_url=google_review_url,
                          hotel_name=hotel_name,
                          hotel_email=hotel_email,
                          hotel_phone=hotel_phone)

@app.route('/api/settings/hotel_profile', methods=['POST'])
@login_required
def update_hotel_profile():
    if session.get('role') != 'owner':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    try:
        data = request.json
        hotel_id = session.get('hotel_id')
        name = data.get('name')
        email = data.get('email')
        phone = data.get('phone')
        
        if not name:
            return jsonify({'success': False, 'message': 'Hotel Name is required'})
            
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE hotels SET name = ?, email = ?, phone = ? WHERE id = ?",
                  (name, email, phone, hotel_id))
        conn.commit()
        conn.close()
        
        # Update session
        session['hotel_name'] = name
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500



@app.route('/api/staff')
@login_required
def get_staff():
    if session.get('role') != 'owner':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, username, role FROM users WHERE hotel_id = ? AND role != 'super_admin'", (hotel_id,))
    staff = [{'id': r[0], 'username': r[1], 'role': r[2]} for r in c.fetchall()]
    conn.close()
    return jsonify(staff)

@app.route('/api/staff/add', methods=['POST'])
@login_required
def add_staff():
    if session.get('role') != 'owner':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
    data = request.json
    username = data.get('username')
    password = data.get('password')
    role = data.get('role', 'staff')
    hotel_id = session.get('hotel_id')
    
    if not username or not password:
        return jsonify({'success': False, 'message': 'Missing fields'})
        
    try:
        conn = get_db_connection()
        c = conn.cursor()
        password_hash = generate_password_hash(password)
        c.execute("INSERT INTO users (username, password_hash, role, hotel_id) VALUES (?, ?, ?, ?)",
                  (username, password_hash, role, hotel_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'Username already exists'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/staff/remove/<int:user_id>', methods=['POST'])
@login_required
def remove_staff(user_id):
    if session.get('role') != 'owner':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()
    
    # Ensure they are not deleting themselves or someone from another hotel
    if user_id == session.get('user_id'):
        return jsonify({'success': False, 'message': 'Cannot remove yourself'})
        
    c.execute("DELETE FROM users WHERE id = ? AND hotel_id = ?", (user_id, hotel_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/settings/finance', methods=['POST'])
@owner_required
def update_finance_settings():
    data = request.json
    hotel_id = session.get('hotel_id')
    currency = data.get('currency', '₹')
    tax = data.get('tax', 0.0)
    google_review_url = data.get('google_review_url', '')
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE hotels SET currency_symbol = ?, tax_rate = ?, google_review_url = ? WHERE id = ?", (currency, tax, google_review_url, hotel_id))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/setup')
@login_required
def setup_page():
    return render_template('setup.html')

@app.route('/api/guests/search')
@login_required
def search_guest():
    phone = request.args.get('phone')
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM guests WHERE phone = ? AND hotel_id = ?', (phone, hotel_id))
    row = c.fetchone()
    conn.close()
    
    if row:
        return jsonify({
            'success': True,
            'guest': {
                'phone': row[0],
                'name': row[2],
                'email': row[3],
                'id_number': row[4],
                'address': row[5],
                'status': row[6],
                'notes': row[7]
            }
        })
    return jsonify({'success': False, 'message': 'Guest not found'})

@app.route('/api/backup')
@login_required
@admin_required
def backup_system():
    # Create in-memory zip
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add Database
        if os.path.exists('hotel.db'):
            zf.write('hotel.db')
        
        # Add Uploads
        upload_folder = app.config['UPLOAD_FOLDER']
        for root, dirs, files in os.walk(upload_folder):
            for file in files:
                abs_path = os.path.join(root, file)
                # Store relative to current dir so it unzips correctly
                rel_path = os.path.relpath(abs_path, start='.')
                zf.write(abs_path, rel_path)
    
    memory_file.seek(0)
    return send_file(
        memory_file,
        download_name=f"backup_{datetime.now().strftime('%Y%m%d')}.zip",
        as_attachment=True
    )

@app.route('/api/backup/export_all')
@login_required
@admin_required
def export_all_formats():
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT name FROM hotels WHERE id = ?', (hotel_id,))
    hotel_row = c.fetchone()
    conn.close()
    
    hotel_name = hotel_row[0] if hotel_row else 'Hotel'
    import export_generator
    zip_buffer = export_generator.generate_multi_backup(hotel_id, hotel_name)
    
    return send_file(
        zip_buffer,
        download_name=f"Guest_History_Export_{datetime.now().strftime('%Y%m%d_%H%M')}.zip",
        as_attachment=True
    )

@app.route('/report/full-database')
@login_required
@admin_required
def full_database_report():
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''SELECT id, guest_name, phone, room_id, checkin_time, checkout_time,
                        amount, extra_charges, food, laundry, water_bottle, car_wash,
                        members, address, id_number, status
                 FROM bookings WHERE hotel_id = ? ORDER BY id DESC''', (hotel_id,))
    bookings = c.fetchall()
    c.execute('SELECT name FROM hotels WHERE id = ?', (hotel_id,))
    hotel_row = c.fetchone()
    conn.close()

    hotel_name = hotel_row['name'] if hotel_row else 'Hotel'
    now_str = datetime.now().strftime('%d %b %Y, %I:%M %p')

    rows_html = ''
    for b in bookings:
        raw_members = b['members'] or '[]'
        try:
            members_list = json.loads(raw_members)
            if isinstance(members_list, list):
                member_str = ', '.join([
                    m if isinstance(m, str) else (
                        f"{m.get('name')} ({m.get('age')})" if m.get('age') else (m.get('name') or '')
                    ) for m in members_list if m
                ])
            else:
                member_str = ''
        except Exception:
            member_str = ''
        all_names = b['guest_name'] or ''
        if member_str:
            all_names += '<br><small style="color:#6b7280;">' + member_str + '</small>'
        total = (b['amount'] or 0) + (b['extra_charges'] or 0) + (b['food'] or 0) + \
                (b['laundry'] or 0) + (b['water_bottle'] or 0) + (b['car_wash'] or 0)
        status = b['status'] or '-'
        bg = '#d1fae5' if status == 'active' else '#fee2e2'
        fg = '#065f46' if status == 'active' else '#991b1b'
        rows_html += f'''
        <tr>
            <td>{b["id"]}</td>
            <td>{all_names}</td>
            <td>{b["phone"] or "-"}</td>
            <td>{b["room_id"] or "-"}</td>
            <td>{b["checkin_time"] or "-"}</td>
            <td>{b["checkout_time"] or "Active"}</td>
            <td>&#8377;{total:.0f}</td>
            <td><span style="padding:2px 8px;border-radius:4px;background:{bg};color:{fg};">{status}</span></td>
        </tr>'''

    html = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{hotel_name} &ndash; Full Guest Report</title>
<style>
  body {{ font-family: Arial, sans-serif; padding: 24px; color: #111; background: #fff; }}
  h1 {{ color: #4f46e5; margin-bottom: 4px; }}
  .meta {{ color: #6b7280; font-size: 0.9rem; margin-bottom: 24px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
  th {{ background: #4f46e5; color: #fff; padding: 10px 8px; text-align: left; }}
  td {{ padding: 8px; border-bottom: 1px solid #e5e7eb; vertical-align: top; }}
  tr:nth-child(even) {{ background: #f9fafb; }}
  @media print {{ .no-print {{ display: none; }} }}
</style>
</head>
<body>
  <h1>&#127968; {hotel_name}</h1>
  <p class="meta">Full Guest Database Report &nbsp;|&nbsp; Generated: {now_str}</p>
  <button class="no-print" onclick="window.print()" style="margin-bottom:16px;padding:8px 20px;background:#4f46e5;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:0.95rem;">&#128424;&#65039; Print / Save as PDF</button>
  <table>
    <thead>
      <tr>
        <th>#</th><th>Guest Name(s)</th><th>Phone</th><th>Room</th>
        <th>Check-in</th><th>Check-out</th><th>Total</th><th>Status</th>
      </tr>
    </thead>
    <tbody>{rows_html}</tbody>
  </table>
  <p class="meta" style="margin-top:20px;">Total records: {len(bookings)}</p>
</body>
</html>'''
    from flask import make_response
    resp = make_response(html)
    resp.headers['Content-Type'] = 'text/html; charset=utf-8'
    return resp
import uuid
import shutil

@app.route('/api/backup/view', methods=['POST'])
@login_required
@admin_required
def view_backup():
    if 'backup_zip' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded'})
        
    file = request.files['backup_zip']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'})

    if file:
        try:
            backup_id = str(uuid.uuid4())
            backup_dir = os.path.join('temp_backups', backup_id)
            os.makedirs(backup_dir, exist_ok=True)
            
            temp_zip_path = os.path.join(backup_dir, 'uploaded_backup.zip')
            file.save(temp_zip_path)
            
            with zipfile.ZipFile(temp_zip_path, 'r') as zf:
                zf.extractall(backup_dir)
                
            return jsonify({'success': True, 'backup_id': backup_id})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})

@app.route('/backup_viewer/<backup_id>')
@login_required
@admin_required
def backup_viewer(backup_id):
    backup_db_path = os.path.join('temp_backups', backup_id, 'hotel.db')
    if not os.path.exists(backup_db_path):
        return "Backup not found or expired", 404
    return render_template('backup_viewer.html', backup_id=backup_id)

@app.route('/api/backup/data/<backup_id>')
@login_required
@admin_required
def backup_data(backup_id):
    backup_db_path = os.path.join('temp_backups', backup_id, 'hotel.db')
    if not os.path.exists(backup_db_path):
        return jsonify({'success': False, 'message': 'Backup DB not found'})
        
    hotel_id = session.get('hotel_id')
    try:
        conn = sqlite3.connect(backup_db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Get bookings
        c.execute('''
            SELECT b.*, GROUP_CONCAT(br.room_id) as room_ids 
            FROM bookings b 
            LEFT JOIN booking_rooms br ON b.id = br.booking_id 
            WHERE b.hotel_id = ? 
            GROUP BY b.id
            ORDER BY b.checkin_time DESC
        ''', (hotel_id,))
        bookings = [dict(row) for row in c.fetchall()]
        
        # Get guests
        c.execute('SELECT * FROM guests WHERE hotel_id = ?', (hotel_id,))
        guests = [dict(row) for row in c.fetchall()]
        
        conn.close()
        
        return jsonify({
            'success': True,
            'bookings': bookings,
            'guests': guests
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/backup_viewer/media/<backup_id>/<path:filename>')
@login_required
@admin_required
def backup_media(backup_id, filename):
    backup_upload_path = os.path.join(os.getcwd(), 'temp_backups', backup_id)
    return send_from_directory(backup_upload_path, filename)

# --- Housekeeping Portal (No Login Required) ---
@app.route('/hk/<token>')
def housekeeping_portal(token):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, name FROM hotels WHERE housekeeping_token = ?", (token,))
    hotel = c.fetchone()
    
    if not hotel:
        conn.close()
        return render_template('error.html', message="Invalid or Expired Housekeeping Link")
    
    hotel_id, hotel_name = hotel
    
    # Get all rooms for this hotel
    c.execute("SELECT room_id, room_type, status FROM rooms WHERE hotel_id = ? ORDER BY room_id", (hotel_id,))
    rooms = [{'id': r[0], 'type': r[1], 'status': r[2]} for r in c.fetchall()]
    conn.close()
    
    return render_template('housekeeping.html', rooms=rooms, hotel_name=hotel_name, token=token)

@app.route('/hk/<token>/update', methods=['POST'])
def housekeeping_update(token):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM hotels WHERE housekeeping_token = ?", (token,))
    hotel = c.fetchone()
    
    if not hotel:
        conn.close()
        return jsonify({'success': False, 'message': 'Invalid token'}), 403
    
    data = request.json
    room_id = data.get('room_id')
    new_status = data.get('status')
    
    if new_status not in ['available', 'dirty', 'cleaning']:
        return jsonify({'success': False, 'message': 'Invalid status'}), 400
    
    c.execute("UPDATE rooms SET status = ? WHERE room_id = ? AND hotel_id = ?", (new_status, room_id, hotel[0]))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

# --- Guest Feedback Portal (No Login Required) ---
@app.route('/feedback/<int:hotel_id>')
def feedback_portal(hotel_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT name, google_review_url FROM hotels WHERE id = ?", (hotel_id,))
    hotel = c.fetchone()
    conn.close()
    
    if not hotel:
        return render_template('error.html', message="Hotel not found")
    
    hotel_name, google_review_url = hotel
    
    # If Google Review URL is set, redirect directly
    if google_review_url:
        return redirect(google_review_url)
    
    return render_template('feedback.html', hotel_id=hotel_id, hotel_name=hotel_name)

@app.route('/feedback/<int:hotel_id>/submit', methods=['POST'])
def submit_feedback(hotel_id):
    data = request.json
    rating = data.get('rating', 5)
    comment = data.get('comment', '')
    guest_name = data.get('name', 'Anonymous')
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # Create feedback table if not exists
    c.execute('''CREATE TABLE IF NOT EXISTS guest_feedback
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  hotel_id INTEGER,
                  guest_name TEXT,
                  rating INTEGER,
                  comment TEXT,
                  created_at TEXT,
                  FOREIGN KEY(hotel_id) REFERENCES hotels(id))''')
    
    c.execute("INSERT INTO guest_feedback (hotel_id, guest_name, rating, comment, created_at) VALUES (?, ?, ?, ?, ?)",
              (hotel_id, guest_name, rating, comment, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Thank you for your feedback!'})

# --- 2FA Routes ---

@app.route('/verify-2fa-page')
def verify_2fa_page():

    if 'temp_user' not in session:

        return redirect(url_for('login'))

    return render_template('verify_2fa.html')

@app.route('/verify-2fa', methods=['POST'])
def verify_2fa_submit():

    data = request.json

    otp = data.get('otp')

    

    if 'temp_user' not in session or '2fa_otp' not in session:

        return jsonify({'success': False, 'message': 'Session expired'})

        

    if otp == session['2fa_otp']:

        user_data = session['temp_user']

        session['logged_in'] = True

        session['user_id'] = user_data['id']

        session['role'] = user_data['role']

        session['hotel_id'] = user_data['hotel_id']

        session['username'] = user_data['username']

        session['hotel_name'] = user_data['hotel_name']

        

        # Cleanup

        session.pop('temp_user', None)

        session.pop('2fa_otp', None)

        

        log_action(user_data['id'], 'LOGIN_2FA', 'User logged in via 2FA', user_data['hotel_id'])

        return jsonify({'success': True, 'redirect': '/dashboard'})

    

    return jsonify({'success': False, 'message': 'Invalid OTP'})

@app.route('/api/settings/2fa', methods=['POST'])
@login_required
def toggle_2fa():

    hotel_id = session.get('hotel_id')

    user_id = session.get('user_id')

    data = request.json

    enable = data.get('enable', False)

    

    conn = get_db_connection()

    c = conn.cursor()

    c.execute("UPDATE users SET is_2fa_enabled = ? WHERE id = ?", (1 if enable else 0, user_id))

    conn.commit()

    conn.close()

    

    log_action(user_id, 'UPDATE_SETTINGS', f"2FA {'Enabled' if enable else 'Disabled'}", hotel_id)

    return jsonify({'success': True})

@app.route('/api/audit-logs')
@owner_required
def get_audit_logs():
    hotel_id = session.get('hotel_id')

    hotel_id = session.get('hotel_id')

    conn = get_db_connection()

    c = conn.cursor()

    c.execute("SELECT user_id, action, details, timestamp, ip_address FROM audit_logs WHERE hotel_id = ? ORDER BY id DESC LIMIT 50", (hotel_id,))

    rows = c.fetchall()

    conn.close()

    

    logs = []

    for r in rows:

        logs.append({

            'user': 'Owner' if r[0] == session.get('user_id') else 'Staff', # Simplified

            'action': r[1],

            'details': r[2],

            'timestamp': r[3],

            'ip': r[4]

        })

    return jsonify(logs)

# --- Smart Backup Logic ---

def check_and_send_backup(hotel_id, user_id):

    try:

        conn = get_db_connection()

        c = conn.cursor()

        c.execute("SELECT last_backup_sent FROM users WHERE id = ?", (user_id,))

        row = c.fetchone()

        

        last_sent = row[0]

        should_send = False

        

        if not last_sent:

            should_send = True

        else:

            last_date = datetime.strptime(last_sent, '%Y-%m-%d')

            if (datetime.now() - last_date).days >= 14:

                should_send = True

        

        if should_send:

            # Update DB first to prevent multiple Sends

            new_date = datetime.now().strftime('%Y-%m-%d')

            c.execute("UPDATE users SET last_backup_sent = ? WHERE id = ?", (new_date, user_id))

            conn.commit()

            

            # Mock Sending Backup

            print(f"\n[x BACKUP] Auto-generating backup for User {user_id}...")

            # In prod: Zip DB and email it

            log_action(user_id, 'AUTO_BACKUP', 'System sent bi-weekly backup', hotel_id)

            

        conn.close()

    except Exception as e:

        print(f"Backup Error: {e}")

# --- Guest Portal Routes ---

@app.route('/guest-portal/<int:booking_id>')
def guest_portal(booking_id):

    conn = get_db_connection()

    c = conn.cursor()

    # Fetch booking details + Room info

    c.execute("""

        SELECT b.id, b.guest_name, b.room_id, b.hotel_id, h.currency_symbol, h.tax_rate, b.status 

        FROM bookings b

        JOIN hotels h ON b.hotel_id = h.id

        WHERE b.id = ?

    """, (booking_id,))

    booking = c.fetchone()

    conn.close()

    

    if not booking or booking[6] != 'active':

        return render_template('error.html', message="Invalid or Expired Booking Link")

        

    return render_template('guest_portal.html', booking={

        'id': booking[0],

        'guest_name': booking[1],

        'room': booking[2],

        'hotel_id': booking[3],

        'currency': booking[4],

        'tax': booking[5]

    })

@app.route('/api/guest/request', methods=['POST'])
def guest_request():

    data = request.json

    booking_id = data.get('booking_id')

    req_type = data.get('type') # 'cleaning', 'water', 'checkout'

    

    conn = get_db_connection()

    c = conn.cursor()

    c.execute("SELECT hotel_id, room_id, guest_name FROM bookings WHERE id = ?", (booking_id,))

    row = c.fetchone()

    

    if row:

        hotel_id, room_id, guest_name = row

        # Log as audit for now (or create a support_message)

        msg = f"Guest {guest_name} (Room {room_id}) requested: {req_type}"

        log_action(0, 'GUEST_REQUEST', msg, hotel_id)

        

        # Also add to support messages

        c.execute("INSERT INTO support_messages (hotel_id, subject, message, status) VALUES (?, ?, ?, 'pending')",

                 (hotel_id, 'Guest Request', msg))

        conn.commit()

        conn.close()

        return jsonify({'success': True})

    

    conn.close()

    return jsonify({'success': False, 'message': 'Booking not found'})

@app.route('/api/guest/edit-details/<int:booking_id>', methods=['GET'])
def get_booking_details_edit(booking_id):
    """Fetch current guest booking details for edit form"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""SELECT b.id, b.guest_name, b.phone, b.address, b.id_number, b.room_id, b.members 
                 FROM bookings b WHERE b.id = ?""", (booking_id,))
    row = c.fetchone()
    conn.close()
    
    if not row:
        return jsonify({'success': False, 'message': 'Booking not found'})
    
    # Parse members to extract second guest name if available
    second_guest_name = ''
    if row[6]:
        try:
            import json
            members = json.loads(row[6])
            if members and len(members) > 0:
                second_guest_name = members[0].get('name', '')
        except:
            pass
    
    return jsonify({
        'success': True,
        'id': row[0],
        'guest_name': row[1],
        'phone': row[2],
        'address': row[3],
        'id_number': row[4],
        'room': row[5],
        'second_guest_name': second_guest_name
    })

@app.route('/api/guest/update-details', methods=['POST'])
def update_guest_details():
    """Update guest booking details"""
    booking_id = request.form.get('booking_id')
    guest_name = request.form.get('guest_name')
    second_guest_name = request.form.get('second_guest_name')
    phone = request.form.get('phone')
    address = request.form.get('address')
    id_number = request.form.get('id_number')
    room = request.form.get('room')
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # Verify booking exists
    c.execute("SELECT id, hotel_id FROM bookings WHERE id = ?", (booking_id,))
    booking = c.fetchone()
    
    if not booking:
        conn.close()
        return jsonify({'success': False, 'message': 'Booking not found'})
    
    hotel_id = booking[1]
    
    # Handle photo upload if provided
    id_photo = None
    if 'id_photo' in request.files:
        file = request.files['id_photo']
        if file and file.filename:
            id_photo = save_uploaded_file(file, prefix='id')
    
    # Update booking details
    update_query = """UPDATE bookings SET 
                      guest_name = ?, 
                      phone = ?, 
                      address = ?, 
                      id_number = ?"""
    params = [guest_name, phone, address, id_number]
    
    if id_photo:
        update_query += ", id_photo = ?"
        params.append(id_photo)
    
    update_query += " WHERE id = ?"
    params.append(booking_id)
    
    c.execute(update_query, params)
    
    # Update members if second guest name provided
    if second_guest_name:
        import json
        members = [{'name': second_guest_name}]
        c.execute("UPDATE bookings SET members = ? WHERE id = ?", 
                 (json.dumps(members), booking_id))
    
    # Update room if changed
    if room:
        c.execute("UPDATE bookings SET room_id = ? WHERE id = ?", (room, booking_id))
    
    conn.commit()
    conn.close()
    
    # Log the update
    log_action(0, 'GUEST_UPDATE', f"Guest {guest_name} updated booking {booking_id}", hotel_id)
    
    return jsonify({'success': True, 'message': 'Details updated successfully'})

# --- Guest Self Check-in Portal ---

@app.route('/guest-checkin/<token>')
def guest_checkin_page(token):
    """Public page: guest scans QR and sees a form to fill their details."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, name FROM hotels WHERE housekeeping_token = ?", (token,))
    hotel = c.fetchone()
    conn.close()
    
    if not hotel:
        return render_template('error.html', message="Invalid QR Code / अमान्य QR कोड")
    
    return render_template('guest_checkin_form.html', hotel_id=hotel[0], hotel_name=hotel[1], token=token)

@app.route('/api/guest/self-checkin', methods=['POST'])

def guest_self_checkin():
    """Public API: guest submits their details (multipart form for photo upload)."""
    hotel_id = request.form.get('hotel_id')
    guest_name = request.form.get('guest_name')
    phone = request.form.get('phone')
    address = request.form.get('address', '')
    
    members = request.form.get('members', '[]')
    
    if not all([hotel_id, guest_name, phone, address]):
        return jsonify({'success': False, 'message': 'All fields are required / सभी जानकारी आवश्यक है'})
    
    # Process primary ID photo and member photos
    id_photo_paths = []
    
    if 'id_photo' in request.files:
        files = request.files.getlist('id_photo')
        for file in files:
            rel_path = save_uploaded_file(file, prefix=f"selfcheckin_h{hotel_id}")
            if rel_path:
                id_photo_paths.append(rel_path)
        
    import json
    try:
        members_data = json.loads(members)
    except:
        members_data = []
        
    for key in request.files:
        if key.startswith('member_photo_'):
            for file in request.files.getlist(key):
                rel_path = save_uploaded_file(file, prefix=f"selfcheckin_mem_h{hotel_id}")
                if rel_path:
                    id_photo_paths.append(rel_path)

    if len(members_data) == 0:
        if len(id_photo_paths) < 1:
            return jsonify({'success': False, 'message': 'ID Photo is compulsory for primary guest'})
    else:
        if len(id_photo_paths) < 2:
            return jsonify({'success': False, 'message': 'Minimum 2 ID photos required when there are multiple guests'})

    id_photo_path = ','.join(id_photo_paths)
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''INSERT INTO self_checkin_requests 
                 (hotel_id, guest_name, phone, address, id_photo, members, status, created_at)
                 VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)''',
              (hotel_id, guest_name, phone, address, id_photo_path, members,
               datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/portal/requests')
@login_required
def portal_requests():
    """Staff API: get all self-checkin requests for this hotel."""
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''SELECT id, guest_name, phone, address, id_photo, status, created_at, members
                 FROM self_checkin_requests
                 WHERE hotel_id = ?
                 ORDER BY CASE WHEN status = 'pending' THEN 0 ELSE 1 END, id DESC''', (hotel_id,))
    requests_list = []
    for row in c.fetchall():
        requests_list.append({
            'id': row[0], 'guest_name': row[1], 'phone': row[2],
            'address': row[3], 'id_photo': row[4], 'status': row[5], 'created_at': row[6],
            'members': row[7] if len(row) > 7 else '[]'
        })
    conn.close()
    return jsonify(requests_list)

@app.route('/api/portal/accept', methods=['POST'])
@login_required
def portal_accept():
    """Staff API: accept a self-checkin request and create a booking."""
    data = request.json
    request_id = data.get('request_id')
    room_id = data.get('room_id')
    amount = float(data.get('amount', 0))
    checkin_time = data.get('checkin_time', datetime.now().strftime('%Y-%m-%d %H:%M'))
    checkout_time = data.get('checkout_time', '')
    hotel_id = session.get('hotel_id')
    
    if not request_id or not room_id:
        return jsonify({'success': False, 'message': 'Room and Request ID required'})
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # Get the request
    c.execute("SELECT * FROM self_checkin_requests WHERE id = ? AND hotel_id = ? AND status = 'pending'", 
              (request_id, hotel_id))
    req = c.fetchone()
    if not req:
        conn.close()
        return jsonify({'success': False, 'message': 'Request not found or already processed'})
    
    guest_name = req[2]
    phone = req[3]
    address = req[4]
    id_photo = req[5]
    members = req[6] if len(req) > 6 else '[]'
    
    # Create booking (same as normal check-in)
    c.execute('''INSERT INTO bookings
                 (hotel_id, room_id, guest_name, phone, address, id_photo, members, amount, checkin_time, checkout_time, status)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')''',
              (hotel_id, room_id, guest_name, phone, address, id_photo, members, amount, checkin_time, checkout_time))
    
    booking_id = c.lastrowid
    
    # Link room to booking
    c.execute("INSERT INTO booking_rooms (booking_id, room_id) VALUES (?, ?)", (booking_id, room_id))
    
    # Mark room as occupied
    c.execute("UPDATE rooms SET status = 'occupied' WHERE room_id = ? AND hotel_id = ?", (room_id, hotel_id))
    
    # Update/insert guest profile
    c.execute('''INSERT OR REPLACE INTO guests (phone, hotel_id, name, address, status)
                 VALUES (?, ?, ?, ?, COALESCE((SELECT status FROM guests WHERE phone = ? AND hotel_id = ?), 'regular'))''',
              (phone, hotel_id, guest_name, address, phone, hotel_id))
    
    # Only mark request as accepted on the final room booking
    is_last = data.get('is_last', True)
    if is_last:
        c.execute("UPDATE self_checkin_requests SET status = 'accepted' WHERE id = ?", (request_id,))
    
    conn.commit()
    conn.close()
    
    log_action(session.get('user_id'), 'SELF_CHECKIN_ACCEPT', 
               f"Accepted self check-in for {guest_name} in room {room_id}", hotel_id)
    
    return jsonify({'success': True, 'booking_id': booking_id})

@app.route('/api/portal/reject', methods=['POST'])
@login_required
def portal_reject():
    """Staff API: reject a self-checkin request."""
    data = request.json
    request_id = data.get('request_id')
    hotel_id = session.get('hotel_id')
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE self_checkin_requests SET status = 'rejected' WHERE id = ? AND hotel_id = ?", 
              (request_id, hotel_id))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/portal/qr-data')
@login_required
def portal_qr_data():
    """Staff API: return the public URL for QR code generation."""
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT housekeeping_token FROM hotels WHERE id = ?", (hotel_id,))
    row = c.fetchone()
    conn.close()
    
    if not row or not row[0]:
        return jsonify({'success': False, 'message': 'Token not found'})
    
    # Build the URL using the server's address
    base_url = request.host_url.rstrip('/')
    portal_url = f"{base_url}/guest-checkin/{row[0]}"
    
    return jsonify({'success': True, 'url': portal_url, 'token': row[0]})

@app.route('/print-standee')
@login_required
def print_standee():
    """Renders a printable reception standee with the QR code."""
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT name, housekeeping_token FROM hotels WHERE id = ?", (hotel_id,))
    row = c.fetchone()
    conn.close()
    
    if not row or not row[1]:
        return render_template('error.html', message="QR Code token not found. Please verify your hotel settings.")
        
    hotel_name = row[0]
    token = row[1]
    
    base_url = request.host_url.rstrip('/')
    portal_url = f"{base_url}/guest-checkin/{token}"
    
    return render_template('standee.html', hotel_name=hotel_name, portal_url=portal_url)

@app.route('/api/portal/pending-count')
@login_required
def portal_pending_count():
    """Staff API: return count of pending self-checkin requests (for badge)."""
    hotel_id = session.get('hotel_id')
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM self_checkin_requests WHERE hotel_id = ? AND status = 'pending'", (hotel_id,))
    count = c.fetchone()[0]
    conn.close()
    return jsonify({'count': count})

# --- Auto Backup Hook ---

@app.before_request
def trigger_backup_check():

    if request.endpoint == 'dashboard' and session.get('role') == 'owner':

        try:

            check_and_send_backup(session.get('hotel_id'), session.get('user_id'))

        except Exception as e:

            print(f"Backup Hook Error: {e}")

# --- PWA Mobile Routes ---
@app.route('/manifest.json')
def serve_manifest():
    from flask import send_from_directory
    return send_from_directory('static', 'manifest.json')

@app.route('/sw.js')
def serve_sw():
    from flask import send_from_directory, make_response
    response = make_response(send_from_directory('static', 'sw.js'))
    response.headers['Content-Type'] = 'application/javascript'
    response.headers['Service-Worker-Allowed'] = '/'
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

if __name__ == '__main__':

    # Initialize DB (This will only create tables if they don't exist)

    init_db()

    # Run the app

    app.run(debug=False, host='0.0.0.0', port=5000)
