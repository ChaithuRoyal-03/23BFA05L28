from flask import Flask, request, jsonify, redirect
from urllib.parse import urlparse
from datetime import datetime, timedelta
import pytz
import sqlite3
import os

from logging_middleware import log_event

app = Flask(__name__)
DATABASE = os.path.join(os.path.dirname(__file__), 'urls.db')

# --- Database Setup ---
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shortcode TEXT UNIQUE NOT NULL,
            original_url TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            total_clicks INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

# --- Shortcode Generator ---
import random
import string

def generate_unique_shortcode(length=6):
    conn = get_db_connection()
    cursor = conn.cursor()
    while True:
        shortcode = ''.join(random.choices(string.ascii_letters + string.digits, k=length))
        cursor.execute('SELECT id FROM urls WHERE shortcode = ?', (shortcode,))
        if not cursor.fetchone():
            conn.close()
            return shortcode

# --- Flask Routes ---
@app.route('/')
def index():
    return "URL Shortener Microservice is running!"

@app.route('/shorturls', methods=['POST'])
def create_short_url():
    log_event(stack="backend", level="info", package="controller", message="Attempting to create a new short URL.")
    data = request.get_json()
    if not data:
        log_event(stack="backend", level="error", package="handler", message="Invalid JSON request body for short URL creation.")
        return jsonify({"error": "Bad Request", "message": "Request must be JSON."}), 400
    original_url = data.get('url')
    custom_shortcode = data.get('shortcode')
    validity_minutes = data.get('validity')
    if not original_url:
        log_event(stack="backend", level="error", package="handler", message="URL is required for short URL creation.")
        return jsonify({"error": "Bad Request", "message": "'url' is required."}), 400
    try:
        result = urlparse(original_url)
        if not all([result.scheme, result.netloc]):
            raise ValueError("Invalid URL format")
    except ValueError as e:
        log_event(stack="backend", level="error", package="handler", message=f"Invalid URL format: {original_url}")
        return jsonify({"error": "Bad Request", "message": f"Invalid URL format: {original_url}"}), 400
    except Exception as e:
        log_event(stack="backend", level="error", package="handler", message=f"Unexpected URL parsing error: {e}")
        return jsonify({"error": "Internal Server Error", "message": "Failed to parse URL."}), 500
    default_validity = 30
    if validity_minutes is None:
        validity_minutes = default_validity
    else:
        try:
            validity_minutes = int(validity_minutes)
            if validity_minutes <= 0:
                log_event(stack="backend", level="error", package="handler", message=f"Invalid validity period: {validity_minutes}")
                return jsonify({"error": "Bad Request", "message": "'validity' must be a positive integer."}), 400
        except ValueError:
            log_event(stack="backend", level="error", package="handler", message=f"Invalid validity format: {validity_minutes}")
            return jsonify({"error": "Bad Request", "message": "'validity' must be an integer."}), 400
    now_utc = datetime.now(pytz.utc)
    expires_at_dt = now_utc + timedelta(minutes=validity_minutes)
    expires_at_iso = expires_at_dt.isoformat(timespec='seconds').replace('+00:00', 'Z')
    shortcode_to_use = None
    conn = get_db_connection()
    cursor = conn.cursor()
    if custom_shortcode:
        if not isinstance(custom_shortcode, str) or not custom_shortcode.isalnum() or not (3 <= len(custom_shortcode) <= 15):
            log_event(stack="backend", level="error", package="handler", message=f"Invalid custom shortcode format: {custom_shortcode}")
            conn.close()
            return jsonify({"error": "Bad Request", "message": "'shortcode' must be alphanumeric and between 3 and 15 characters."}), 400
        cursor.execute('SELECT id FROM urls WHERE shortcode = ?', (custom_shortcode,))
        if cursor.fetchone():
            log_event(stack="backend", level="warn", package="controller", message=f"Custom shortcode '{custom_shortcode}' already exists.")
            conn.close()
            return jsonify({"error": "Conflict", "message": f"Shortcode '{custom_shortcode}' already in use."}), 409
        shortcode_to_use = custom_shortcode
    else:
        shortcode_to_use = generate_unique_shortcode()
    try:
        created_at_iso = now_utc.isoformat(timespec='seconds').replace('+00:00', 'Z')
        cursor.execute(
            'INSERT INTO urls (shortcode, original_url, created_at, expires_at, total_clicks) VALUES (?, ?, ?, ?, ?)',
            (shortcode_to_use, original_url, created_at_iso, expires_at_iso, 0)
        )
        conn.commit()
        log_event(stack="backend", level="info", package="db", message=f"New short URL saved: {shortcode_to_use}")
        shortlink = f"{request.url_root}{shortcode_to_use}"
        log_event(stack="backend", level="info", package="controller", message=f"Short URL created: {shortlink}")
        return jsonify({
            "shortLink": shortlink,
            "expiry": expires_at_iso
        }), 201
    except sqlite3.Error as e:
        log_event(stack="backend", level="fatal", package="db", message=f"Database error saving short URL: {e}")
        conn.rollback()
        return jsonify({"error": "Internal Server Error", "message": "Database operation failed."}), 500
    except Exception as e:
        log_event(stack="backend", level="fatal", package="handler", message=f"Unhandled error during short URL creation: {e}")
        return jsonify({"error": "Internal Server Error", "message": "An unexpected error occurred."}), 500
    finally:
        conn.close()

@app.route('/<shortcode>', methods=['GET'])
def redirect_short_url(shortcode):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT original_url, expires_at FROM urls WHERE shortcode = ?', (shortcode,))
    row = cursor.fetchone()
    if not row:
        log_event(stack="backend", level="warn", package="controller", message=f"Shortcode not found: {shortcode}")
        conn.close()
        return jsonify({"error": "Not Found", "message": "Shortcode does not exist."}), 404
    original_url = row[0]
    expires_at = row[1]
    now_utc = datetime.now(pytz.utc)
    expires_at_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
    if now_utc > expires_at_dt:
        log_event(stack="backend", level="warn", package="controller", message=f"Shortcode expired: {shortcode}")
        conn.close()
        return jsonify({"error": "Gone", "message": "Shortcode has expired."}), 410
    # Increment click count
    cursor.execute('UPDATE urls SET total_clicks = total_clicks + 1 WHERE shortcode = ?', (shortcode,))
    conn.commit()
    conn.close()
    log_event(stack="backend", level="info", package="controller", message=f"Redirecting shortcode: {shortcode} to {original_url}")
    return redirect(original_url)

if __name__ == '__main__':
    init_db()
    app.run(debug=True) 