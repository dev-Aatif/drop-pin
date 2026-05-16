import os
import time
import json
import random
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv
from urllib.parse import quote

# Load env variables
load_dotenv()

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Credentials
MAKE_WEBHOOK_URL = os.getenv("MAKE_WEBHOOK_URL")
BASE_URL = os.getenv("BASE_URL", "").rstrip("/") 
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PINS_DIR = os.path.join(BASE_DIR, "data", "pins")
DONE_DIR = os.path.join(BASE_DIR, "data", "done")
TITLES_FILE = os.path.join(BASE_DIR, "data", "titles.txt")
RECENT_FILE = os.path.join(BASE_DIR, "data", "recent.json")

# Supported image types
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}

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
                if filename.startswith('.'): continue
                ext = os.path.splitext(filename)[1].lower()
                if ext not in IMAGE_EXTENSIONS: continue
                    
                file_path = os.path.join(folder_path, filename)
                if os.path.isfile(file_path):
                    file_time = os.path.getmtime(file_path)
                    if file_time < oldest_time:
                        oldest_time = file_time
                        oldest_file = file_path
                        board_name = folder
    
    return oldest_file, board_name

def _fallback_content(board_name):
    titles = [f"Stunning {board_name} Ideas", f"The Ultimate {board_name} Board", f"{board_name} Goals"]
    return random.choice(titles), f"Beautiful {board_name} inspiration. #aesthetic #{board_name.replace(' ', '')}"

def generate_ai_content(board_name):
    if not GEMINI_API_KEY: return _fallback_content(board_name)
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        prompt = f"Create a viral Pinterest title and a short SEO description (with 5 hashtags) for a pin about '{board_name}'. Return ONLY valid JSON: {{\"title\": \"...\", \"description\": \"...\"}}"
        response = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
        data = response.json()
        if 'candidates' not in data: return _fallback_content(board_name)
        text = data['candidates'][0]['content']['parts'][0]['text'].replace('```json', '').replace('```', '').strip()
        result = json.loads(text)
        return result.get('title'), result.get('description')
    except: return _fallback_content(board_name)

def log_activity(filename, board_name, status, title):
    try:
        activities = []
        if os.path.exists(RECENT_FILE):
            with open(RECENT_FILE, 'r') as f:
                try: activities = json.load(f)
                except: pass
        activities.insert(0, {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "filename": os.path.basename(filename), "board": board_name, "title": title, "status": status})
        with open(RECENT_FILE, 'w') as f: json.dump(activities[:20], f, indent=4)
    except: pass

def run_bot_job():
    logging.info("Starting Pinterest bot job via Make.com Bridge...")
    
    if not MAKE_WEBHOOK_URL:
        logging.error("MAKE_WEBHOOK_URL is missing from .env")
        return

    image_path, board_name = get_oldest_image()
    if not image_path: return
    
    title, description = generate_ai_content(board_name)
    relative_path = os.path.relpath(image_path, PINS_DIR)
    encoded_path = "/".join(quote(segment) for segment in relative_path.split(os.sep))
    image_url = f"{BASE_URL}/pins/{encoded_path}"
    
    logging.info(f"Sending to Make.com: {title}")

    try:
        payload = {
            "title": title,
            "description": f"{title}\n\n{description}",
            "image_url": image_url,
            "board": board_name,
            "link": BASE_URL
        }
        
        response = requests.post(MAKE_WEBHOOK_URL, json=payload, timeout=30)
        
        if response.status_code == 200:
            logging.info("Success! Make.com received the data.")
            filename = os.path.basename(image_path)
            done_path = os.path.join(DONE_DIR, f"{int(time.time())}_{filename}")
            os.rename(image_path, done_path)
            log_activity(image_path, board_name, "Success (via Bridge)", title)
        else:
            logging.error(f"Make.com Error: {response.status_code}")
            log_activity(image_path, board_name, f"Bridge Error: {response.status_code}", title)
            
    except Exception as e:
        logging.error(f"Bot Exception: {e}")
        log_activity(image_path, board_name, f"System Error: {str(e)}", title)

if __name__ == "__main__":
    run_bot_job()
