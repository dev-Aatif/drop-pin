import os
import json
import time
import random
import shutil
from flask import Flask, render_template, request, jsonify
from bot import run_bot_job, PINS_DIR, DONE_DIR, TITLES_FILE, RECENT_FILE

app = Flask(__name__, static_folder='static', template_folder='templates')

# Read optional secret token for cron job security
CRON_SECRET = os.getenv("CRON_SECRET", "")
NEXT_POST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "next_post_at.json")

def is_it_time_to_post():
    if not os.path.exists(NEXT_POST_FILE):
        return True
    try:
        with open(NEXT_POST_FILE, 'r') as f:
            data = json.load(f)
            target_time = data.get('target_timestamp', 0)
            return time.time() >= target_time
    except:
        return True

def set_next_post_time():
    # Target 20 posts per day = 1 post every 72 minutes on average
    # We add a random jitter of +/- 30 minutes
    average_interval = 72 * 60 # 72 minutes in seconds
    jitter = random.randint(-30 * 60, 30 * 60) # +/- 30 minutes
    next_time = time.time() + average_interval + jitter
    
    with open(NEXT_POST_FILE, 'w') as f:
        json.dump({'target_timestamp': next_time, 'human_time': time.ctime(next_time)}, f)

# Helper function to get queue status
def get_queue_data():
    queue = {}
    if not os.path.exists(PINS_DIR):
        return queue
    
    for folder in os.listdir(PINS_DIR):
        folder_path = os.path.join(PINS_DIR, folder)
        if os.path.isdir(folder_path):
            # Count only files (images)
            count = len([f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f)) and not f.endswith('.error')])
            queue[folder] = count
    return queue

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/queue', methods=['GET'])
def api_queue():
    queue_data = get_queue_data()
    return jsonify({"status": "success", "data": queue_data})

@app.route('/api/upload', methods=['POST'])
def api_upload():
    if 'image' not in request.files:
        return jsonify({"status": "error", "message": "No image part"}), 400
    
    file = request.files['image']
    board_name = request.form.get('board_name')
    
    if file.filename == '':
        return jsonify({"status": "error", "message": "No selected file"}), 400
        
    if not board_name:
        return jsonify({"status": "error", "message": "No board selected"}), 400
        
    # Create board directory if it doesn't exist
    board_dir = os.path.join(PINS_DIR, board_name)
    os.makedirs(board_dir, exist_ok=True)
    
    # Save the file
    file_path = os.path.join(board_dir, file.filename)
    file.save(file_path)
    
    return jsonify({"status": "success", "message": f"Uploaded to {board_name}"})

@app.route('/api/titles', methods=['POST'])
def api_titles():
    data = request.json
    new_titles = data.get('titles', '')
    
    if not new_titles:
        return jsonify({"status": "error", "message": "No titles provided"}), 400
        
    # Append to titles.txt
    with open(TITLES_FILE, 'a', encoding='utf-8') as f:
        f.write("\n" + new_titles)
        
    return jsonify({"status": "success", "message": "Titles added"})

@app.route('/api/activity', methods=['GET'])
def api_activity():
    if not os.path.exists(RECENT_FILE):
        return jsonify({"status": "success", "data": []})
        
    try:
        with open(RECENT_FILE, 'r') as f:
            data = json.load(f)
            return jsonify({"status": "success", "data": data})
    except json.JSONDecodeError:
         return jsonify({"status": "success", "data": []})

@app.route('/api/clear_done', methods=['POST'])
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
        except Exception as e:
            pass
            
    return jsonify({"status": "success", "message": f"Cleared {count} files"})

@app.route('/api/test_bot', methods=['GET', 'POST'])
def test_bot():
    """Endpoint for testing the bot manually or via cron-job.org."""
    token = request.args.get('token', '')
    force = request.args.get('force', 'false').lower() == 'true'
    
    if CRON_SECRET and token != CRON_SECRET:
        return jsonify({"status": "error", "message": "Unauthorized. Invalid token."}), 401
    
    # Check if it's actually time to post (unless forced)
    if not force and not is_it_time_to_post():
        return jsonify({"status": "waiting", "message": "Not time to post yet. Skipping."})
        
    # We call it directly
    run_bot_job()
    
    # Schedule the next one
    set_next_post_time()
    
    return jsonify({"status": "success", "message": "Bot job executed successfully. Next post scheduled."})

if __name__ == '__main__':
    # Start the server
    # host='0.0.0.0' allows external access if needed (like on Oracle Cloud)
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
