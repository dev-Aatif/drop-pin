import os
import glob
import time
import json
import random
import logging
import base64
import requests
import mimetypes
from datetime import datetime
from dotenv import load_dotenv

# Load env variables
load_dotenv()

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

PINTEREST_API_URL = "https://api.pinterest.com/v5"
ACCESS_TOKEN = os.getenv("PINTEREST_ACCESS_TOKEN")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PINS_DIR = os.path.join(BASE_DIR, "data", "pins")
DONE_DIR = os.path.join(BASE_DIR, "data", "done")
TITLES_FILE = os.path.join(BASE_DIR, "data", "titles.txt")
RECENT_FILE = os.path.join(BASE_DIR, "data", "recent.json")

def get_oldest_image():
    """Finds the absolute oldest image file across all board folders."""
    oldest_file = None
    oldest_time = float('inf')
    board_name = None

    if not os.path.exists(PINS_DIR):
        return None, None

    # Iterate through all subfolders in data/pins/
    for folder in os.listdir(PINS_DIR):
        folder_path = os.path.join(PINS_DIR, folder)
        if os.path.isdir(folder_path):
            # Check files in this folder
            for filename in os.listdir(folder_path):
                file_path = os.path.join(folder_path, filename)
                if os.path.isfile(file_path):
                    # Check if it's an image
                    mimetype, _ = mimetypes.guess_type(file_path)
                    if mimetype and mimetype.startswith('image'):
                        # Get modification time
                        file_time = os.path.getmtime(file_path)
                        if file_time < oldest_time:
                            oldest_time = file_time
                            oldest_file = file_path
                            board_name = folder
    
    return oldest_file, board_name

def get_random_title(board_name):
    """Combines a random phrase from titles.txt with the board name."""
    try:
        with open(TITLES_FILE, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
        if not lines:
            return f"Inspiration | {board_name}"
        phrase = random.choice(lines)
        return f"{phrase} | {board_name}"
    except Exception as e:
        logging.error(f"Error reading titles: {e}")
        return f"Aesthetic | {board_name}"

def log_activity(filename, board_name, status, title):
    """Logs the activity to recent.json"""
    try:
        # Read current log
        activities = []
        if os.path.exists(RECENT_FILE):
            with open(RECENT_FILE, 'r') as f:
                try:
                    activities = json.load(f)
                except json.JSONDecodeError:
                    pass
        
        # Add new log entry
        activities.insert(0, {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "filename": os.path.basename(filename),
            "board": board_name,
            "title": title,
            "status": status
        })
        
        # Keep only the last 5
        activities = activities[:5]
        
        with open(RECENT_FILE, 'w') as f:
            json.dump(activities, f, indent=4)
            
    except Exception as e:
        logging.error(f"Error logging activity: {e}")

def get_pinterest_board_id(board_name):
    """
    Fetches the user's Pinterest boards and tries to find a matching ID by name.
    """
    if not ACCESS_TOKEN:
        logging.error("No Pinterest Access Token provided.")
        return None
        
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(f"{PINTEREST_API_URL}/boards", headers=headers)
        if response.status_code == 200:
            boards = response.json().get('items', [])
            for board in boards:
                if board.get('name').lower() == board_name.lower():
                    return board.get('id')
            logging.error(f"Board '{board_name}' not found on your Pinterest account.")
            return None
        else:
            logging.error(f"Failed to fetch boards: {response.text}")
            return None
    except Exception as e:
        logging.error(f"Error fetching boards: {e}")
        return None

def run_bot_job():
    """Main job that runs once per hour."""
    logging.info("Starting hourly Pinterest bot job...")
    
    if not ACCESS_TOKEN:
        logging.warning("PINTEREST_ACCESS_TOKEN is missing. Job aborted.")
        return
        
    # 1. Get the oldest image
    image_path, board_name = get_oldest_image()
    if not image_path:
        logging.info("No images found in the queue. Sleeping until next hour.")
        return
        
    logging.info(f"Selected image: {image_path} for board: {board_name}")
    
    # 2. Get Title
    title = get_random_title(board_name)
    
    # 3. Get Pinterest Board ID
    board_id = get_pinterest_board_id(board_name)
    if not board_id:
        # We can't upload without a valid board ID
        log_activity(image_path, board_name, "Error: Board ID not found", title)
        # We don't move it to done, we just skip. But wait, if we don't move it, 
        # it will be the oldest image again next time and block the queue!
        # Let's rename the file or move it to an error folder to avoid blocking.
        error_path = image_path + ".error"
        os.rename(image_path, error_path)
        logging.error(f"Renamed {image_path} to avoid blocking the queue.")
        return
        
    # 4. Read and Base64 Encode Image
    mimetype, _ = mimetypes.guess_type(image_path)
    if not mimetype:
        mimetype = 'image/jpeg' # Fallback
        
    try:
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        logging.error(f"Error reading image file: {e}")
        error_path = image_path + ".error"
        os.rename(image_path, error_path)
        log_activity(image_path, board_name, "Error: Could not read file", title)
        return

    # 5. Send to Pinterest
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "title": title,
        "description": f"Amazing {board_name} aesthetic.",
        "board_id": board_id,
        "media_source": {
            "source_type": "image_base64",
            "content_type": mimetype,
            "data": encoded_string
        }
    }
    
    try:
        response = requests.post(f"{PINTEREST_API_URL}/pins", headers=headers, json=payload)
        if response.status_code == 201:
            logging.info(f"Successfully uploaded {title} to Pinterest!")
            # Move to done directory
            filename = os.path.basename(image_path)
            done_path = os.path.join(DONE_DIR, f"{int(time.time())}_{filename}")
            os.rename(image_path, done_path)
            
            log_activity(image_path, board_name, "Success", title)
        else:
            logging.error(f"Failed to upload to Pinterest: {response.status_code} - {response.text}")
            error_path = image_path + ".error"
            os.rename(image_path, error_path)
            log_activity(image_path, board_name, f"Error: API {response.status_code}", title)
            
    except Exception as e:
        logging.error(f"Exception during Pinterest upload: {e}")
        error_path = image_path + ".error"
        os.rename(image_path, error_path)
        log_activity(image_path, board_name, "Error: Network Exception", title)

if __name__ == "__main__":
    # Test run
    run_bot_job()
