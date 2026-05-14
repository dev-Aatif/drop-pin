import os
import time
import json
import random
import logging
import mimetypes
from datetime import datetime
from dotenv import load_dotenv
from py3pin.Pinterest import Pinterest

# Load env variables
load_dotenv()

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Credentials
EMAIL = os.getenv("PINTEREST_EMAIL")
PASSWORD = os.getenv("PINTEREST_PASSWORD")
USERNAME = os.getenv("PINTEREST_USERNAME")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PINS_DIR = os.path.join(BASE_DIR, "data", "pins")
DONE_DIR = os.path.join(BASE_DIR, "data", "done")
TITLES_FILE = os.path.join(BASE_DIR, "data", "titles.txt")
RECENT_FILE = os.path.join(BASE_DIR, "data", "recent.json")
CREDS_FILE = os.path.join(BASE_DIR, "data", "creds.json")

# Initialize Pinterest Client
def get_client():
    if not EMAIL or not PASSWORD:
        logging.error("PINTEREST_EMAIL or PINTEREST_PASSWORD missing from .env")
        return None
    try:
        # The library uses a creds file to stay logged in
        return Pinterest(email=EMAIL, password=PASSWORD, username=USERNAME, creds_state=CREDS_FILE)
    except Exception as e:
        logging.error(f"Failed to initialize Pinterest client: {e}")
        return None

def get_oldest_image():
    """Finds the absolute oldest image file across all board folders."""
    oldest_file = None
    oldest_time = float('inf')
    board_name = None

    if not os.path.exists(PINS_DIR):
        return None, None

    for folder in os.listdir(PINS_DIR):
        folder_path = os.path.join(PINS_DIR, folder)
        if os.path.isdir(folder_path):
            for filename in os.listdir(folder_path):
                file_path = os.path.join(folder_path, filename)
                if os.path.isfile(file_path) and not filename.endswith('.gitkeep'):
                    mimetype, _ = mimetypes.guess_type(file_path)
                    if mimetype and mimetype.startswith('image'):
                        file_time = os.path.getmtime(file_path)
                        if file_time < oldest_time:
                            oldest_time = file_time
                            oldest_file = file_path
                            board_name = folder
    
    return oldest_file, board_name

def get_random_title(board_name):
    try:
        with open(TITLES_FILE, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
        if not lines:
            return f"Inspiration | {board_name}"
        phrase = random.choice(lines)
        return f"{phrase} | {board_name}"
    except Exception as e:
        return f"Aesthetic | {board_name}"

def log_activity(filename, board_name, status, title):
    try:
        activities = []
        if os.path.exists(RECENT_FILE):
            with open(RECENT_FILE, 'r') as f:
                try:
                    activities = json.load(f)
                except: pass
        
        activities.insert(0, {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "filename": os.path.basename(filename),
            "board": board_name,
            "title": title,
            "status": status
        })
        
        with open(RECENT_FILE, 'w') as f:
            json.dump(activities[:5], f, indent=4)
    except: pass

def run_bot_job():
    logging.info("Starting hourly Pinterest bot job (Login Method)...")
    
    image_path, board_name = get_oldest_image()
    if not image_path:
        logging.info("No images in queue.")
        return
        
    title = get_random_title(board_name)
    client = get_client()
    if not client:
        log_activity(image_path, board_name, "Error: Login Failed", title)
        return

    try:
        # 1. Get Board ID (Unofficial API way)
        boards = client.get_boards()
        board_id = None
        for b in boards:
            if b['name'].lower() == board_name.lower():
                board_id = b['id']
                break
        
        if not board_id:
            logging.error(f"Board '{board_name}' not found. Creating it...")
            new_board = client.create_board(name=board_name)
            board_id = new_board.get('id')

        if not board_id:
            log_activity(image_path, board_name, "Error: Board ID not found", title)
            return

        # 2. Upload Pin
        result = client.upload_pin(
            board_id=board_id,
            image_file=image_path,
            description=f"Aesthetic {board_name} inspiration.",
            title=title
        )

        if result:
            logging.info(f"Successfully uploaded {title}!")
            filename = os.path.basename(image_path)
            done_path = os.path.join(DONE_DIR, f"{int(time.time())}_{filename}")
            os.rename(image_path, done_path)
            log_activity(image_path, board_name, "Success", title)
        else:
            logging.error("Upload failed.")
            log_activity(image_path, board_name, "Error: Upload Failed", title)
            
    except Exception as e:
        logging.error(f"Exception: {e}")
        log_activity(image_path, board_name, f"Error: {str(e)}", title)

if __name__ == "__main__":
    run_bot_job()
