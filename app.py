import os
import time
import random
import shutil
from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename

# Import from our new database module and bot
from database import init_db, get_recent_activity, set_setting, get_setting, set_board_description, get_stats
from bot import run_bot_job, PINS_DIR, DONE_DIR, IMAGE_EXTENSIONS

# Ensure DB is initialized
init_db()

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super-secret-default-key-change-in-prod")

CRON_SECRET = os.getenv("CRON_SECRET", "")
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin") # Default if not set in .env

# --- Setup Flask-Login ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    if user_id == ADMIN_USER:
        return User(user_id)
    return None

def is_it_time_to_post():
    target_time = float(get_setting('target_timestamp', 0))
    return time.time() >= target_time

def set_next_post_time():
    # 20-25 posts a day means an average interval of ~64 minutes
    # Random interval between 45 and 85 minutes ensures human-like randomness
    interval_minutes = random.randint(45, 85)
    next_time = time.time() + (interval_minutes * 60)
    set_setting('target_timestamp', str(next_time))

def get_queue_data():
    queue = {}
    if not os.path.exists(PINS_DIR):
        return queue
    for folder in os.listdir(PINS_DIR):
        folder_path = os.path.join(PINS_DIR, folder)
        if os.path.isdir(folder_path):
            count = len([f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f)) and not f.endswith('.error')])
            queue[folder] = count
    return queue

# --- Routes ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == ADMIN_USER and password == ADMIN_PASS:
            login_user(User(username))
            return redirect(url_for('index'))
        return render_template('login.html', error="Invalid credentials")
    return render_template('login.html', error=None)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/api/queue', methods=['GET'])
@login_required
def api_queue():
    return jsonify({"status": "success", "data": get_queue_data()})

@app.route('/api/board/<board_name>/pins', methods=['GET'])
@login_required
def api_board_pins(board_name):
    safe_board = secure_filename(board_name)
    board_dir = os.path.join(PINS_DIR, safe_board)
    if not os.path.exists(board_dir):
        return jsonify({"status": "success", "data": []})
        
    pins = []
    for f in os.listdir(board_dir):
        if os.path.isfile(os.path.join(board_dir, f)):
            pins.append(f)
    return jsonify({"status": "success", "data": pins})

@app.route('/api/upload', methods=['POST'])
@login_required
def api_upload():
    if 'image' not in request.files:
        return jsonify({"status": "error", "message": "No image part"}), 400
    
    files = request.files.getlist('image')
    board_name = request.form.get('board_name')
    
    if not files or all(f.filename == '' for f in files):
        return jsonify({"status": "error", "message": "No selected file"}), 400
        
    if not board_name:
        return jsonify({"status": "error", "message": "No board selected"}), 400
        
    safe_board = secure_filename(board_name)
    board_dir = os.path.join(PINS_DIR, safe_board)
    os.makedirs(board_dir, exist_ok=True)
    
    count = 0
    for file in files:
        if file and file.filename != '':
            ext = os.path.splitext(file.filename)[1].lower()
            if ext in IMAGE_EXTENSIONS:
                safe_name = secure_filename(file.filename)
                base_name, _ = os.path.splitext(safe_name)
                final_name = f"{int(time.time())}_{count}_{base_name}{ext}"
                file_path = os.path.join(board_dir, final_name)
                file.save(file_path)
                count += 1
                
    if count == 0:
         return jsonify({"status": "error", "message": "No valid image files uploaded"}), 400
         
    return jsonify({"status": "success", "message": f"Uploaded {count} images to {safe_board}"})

@app.route('/api/delete_pin', methods=['POST'])
@login_required
def api_delete_pin():
    data = request.json
    board_name = secure_filename(data.get('board_name', ''))
    filename = secure_filename(data.get('filename', ''))
    
    if not board_name or not filename:
        return jsonify({"status": "error", "message": "Missing parameters"}), 400
        
    file_path = os.path.join(PINS_DIR, board_name, filename)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        os.remove(file_path)
        return jsonify({"status": "success", "message": "Pin deleted"})
    return jsonify({"status": "error", "message": "Pin not found"}), 404



@app.route('/api/boards/description', methods=['GET', 'POST'])
@login_required
def api_board_desc():
    if request.method == 'GET':
        board_name = request.args.get('board_name')
        if board_name:
            desc = get_board_description(board_name)
            return jsonify({"status": "success", "data": {"description": desc}})
        return jsonify({"status": "error", "message": "Board name required"}), 400
        
    data = request.json
    board_name = data.get('board_name')
    desc = data.get('description', '')
    if board_name:
        set_board_description(board_name, desc)
        return jsonify({"status": "success", "message": "Description saved"})
    return jsonify({"status": "error", "message": "Board name required"}), 400

@app.route('/api/activity', methods=['GET'])
@login_required
def api_activity():
    data = get_recent_activity(20)
    return jsonify({"status": "success", "data": data})

@app.route('/api/stats', methods=['GET'])
@login_required
def api_stats():
    return jsonify({"status": "success", "data": get_stats()})

@app.route('/api/clear_done', methods=['POST'])
@login_required
def api_clear_done():
    if not os.path.exists(DONE_DIR):
        return jsonify({"status": "success", "message": "Done folder is empty"})
    count = 0
    for filename in os.listdir(DONE_DIR):
        file_path = os.path.join(DONE_DIR, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
                count += 1
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception:
            pass
    return jsonify({"status": "success", "message": f"Cleared {count} files"})

@app.route('/api/test_bot', methods=['GET', 'POST'])
def test_bot():
    token = request.args.get('token', '')
    force = request.args.get('force', 'false').lower() == 'true'
    
    is_admin = current_user.is_authenticated and current_user.id == ADMIN_USER
    
    if not is_admin and (CRON_SECRET and token != CRON_SECRET):
        return jsonify({"status": "error", "message": "Unauthorized."}), 401
    
    if not force and not is_it_time_to_post():
        return jsonify({"status": "waiting", "message": "Not time to post yet. Skipping."})
        
    run_bot_job()
    set_next_post_time()
    return jsonify({"status": "success", "message": "Bot job executed successfully."})

@app.route('/pins/<board>/<path:filename>')
@login_required
def serve_pin_image(board, filename):
    safe_board = secure_filename(board)
    board_dir = os.path.join(PINS_DIR, safe_board)
    return send_from_directory(board_dir, filename)

@app.route('/done/<path:filename>')
def serve_done_image(filename):
    return send_from_directory(DONE_DIR, filename)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
