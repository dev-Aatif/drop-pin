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
BUFFER_TOKEN = os.getenv("BUFFER_ACCESS_TOKEN")
BUFFER_PROFILE_ID = os.getenv("BUFFER_PROFILE_ID")
BASE_URL = os.getenv("BASE_URL", "").rstrip("/")  # e.g., https://username.pythonanywhere.com
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PINS_DIR = os.path.join(BASE_DIR, "data", "pins")
DONE_DIR = os.path.join(BASE_DIR, "data", "done")
TITLES_FILE = os.path.join(BASE_DIR, "data", "titles.txt")
RECENT_FILE = os.path.join(BASE_DIR, "data", "recent.json")

# Ensure directories exist
os.makedirs(DONE_DIR, exist_ok=True)
os.makedirs(PINS_DIR, exist_ok=True)

# Supported image types
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}

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
                # Skip hidden files and non-images
                if filename.startswith('.'):
                    continue
                ext = os.path.splitext(filename)[1].lower()
                if ext not in IMAGE_EXTENSIONS:
                    continue
                    
                file_path = os.path.join(folder_path, filename)
                if os.path.isfile(file_path):
                    file_time = os.path.getmtime(file_path)
                    if file_time < oldest_time:
                        oldest_time = file_time
                        oldest_file = file_path
                        board_name = folder
    
    return oldest_file, board_name

def get_queue_count():
    """Returns total number of images waiting in all board folders."""
    count = 0
    if not os.path.exists(PINS_DIR):
        return 0
    for folder in os.listdir(PINS_DIR):
        folder_path = os.path.join(PINS_DIR, folder)
        if os.path.isdir(folder_path):
            for filename in os.listdir(folder_path):
                if not filename.startswith('.'):
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in IMAGE_EXTENSIONS:
                        count += 1
    return count

def generate_ai_content(board_name):
    """Uses Gemini to generate a viral title and description for Pinterest."""
    if not GEMINI_API_KEY:
        logging.info("No Gemini API key. Using fallback content.")
        return _fallback_content(board_name)

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
        prompt = (
            f"You are a Pinterest marketing expert. Create a viral pin title and "
            f"a short SEO-optimized description with 5 relevant hashtags for a pin "
            f"about '{board_name}'. The title should be catchy and under 100 chars. "
            f"The description should be 2-3 sentences max.\n\n"
            f"Return ONLY valid JSON: {{\"title\": \"...\", \"description\": \"...\"}}"
        )
        
        response = requests.post(url, json={
            "contents": [{"parts": [{"text": prompt}]}]
        }, timeout=15)
        
        if response.status_code != 200:
            logging.error(f"Gemini API returned {response.status_code}")
            return _fallback_content(board_name)
            
        data = response.json()
        text = data['candidates'][0]['content']['parts'][0]['text']
        # Clean JSON from markdown code fences
        text = text.replace('```json', '').replace('```', '').strip()
        result = json.loads(text)
        
        title = result.get('title', f'{board_name} Inspiration')
        description = result.get('description', f'Beautiful {board_name} ideas.')
        
        logging.info(f"AI generated: '{title}'")
        return title, description
        
    except Exception as e:
        logging.error(f"Gemini error: {e}")
        return _fallback_content(board_name)

def _fallback_content(board_name):
    """Generates decent content when Gemini is unavailable."""
    titles = [
        f"Stunning {board_name} Ideas You Need to See",
        f"The Ultimate {board_name} Inspiration Board",
        f"{board_name} Goals That Will Blow Your Mind",
        f"Dreamy {board_name} Aesthetic for 2026",
        f"Top {board_name} Trends Everyone Is Loving",
    ]
    descriptions = [
        f"Discover the most inspiring {board_name.lower()} ideas curated just for you. Save this pin for later! #aesthetic #{board_name.lower().replace(' ', '')} #inspiration #trending #pinterest",
        f"Looking for {board_name.lower()} inspiration? You've found it. Double tap to save! #viral #{board_name.lower().replace(' ', '')} #goals #inspo #trending",
    ]
    return random.choice(titles), random.choice(descriptions)

def log_activity(filename, board_name, status, title):
    """Logs bot activity to recent.json for the dashboard."""
    try:
        activities = []
        if os.path.exists(RECENT_FILE):
            with open(RECENT_FILE, 'r') as f:
                try:
                    activities = json.load(f)
                except json.JSONDecodeError:
                    pass
        
        activities.insert(0, {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "filename": os.path.basename(filename),
            "board": board_name,
            "title": title,
            "status": status
        })
        
        # Keep only last 20 entries
        with open(RECENT_FILE, 'w') as f:
            json.dump(activities[:20], f, indent=4)
    except Exception as e:
        logging.error(f"Failed to log activity: {e}")

def run_bot_job():
    """Main bot function. Picks an image, generates AI content, sends to Buffer."""
    logging.info("Starting Pinterest bot job via Buffer...")
    
    # Preflight checks
    if not BUFFER_TOKEN:
        logging.error("BUFFER_ACCESS_TOKEN is missing from .env")
        return
    if not BUFFER_PROFILE_ID:
        logging.error("BUFFER_PROFILE_ID is missing from .env")
        return
    if not BASE_URL:
        logging.error("BASE_URL is missing from .env")
        return
    
    image_path, board_name = get_oldest_image()
    if not image_path:
        logging.info("No images in queue. Nothing to post.")
        return
    
    remaining = get_queue_count()
    logging.info(f"Found image: {os.path.basename(image_path)} (Board: {board_name}, Queue: {remaining})")
    
    # Generate AI content
    title, description = generate_ai_content(board_name)
    
    # Construct the public URL for the image
    # URL-encode the path segments to handle spaces/special chars
    relative_path = os.path.relpath(image_path, PINS_DIR)
    encoded_path = "/".join(quote(segment) for segment in relative_path.split(os.sep))
    image_url = f"{BASE_URL}/pins/{encoded_path}"
    
    logging.info(f"Image URL: {image_url}")
    logging.info(f"Title: {title}")

    try:
        # Buffer API - Create Update (Post Now)
        buffer_url = "https://api.bufferapp.com/1/updates/create.json"
        
        payload = {
            "profile_ids[]": BUFFER_PROFILE_ID,
            "text": description,
            "now": "true",
            "media[picture]": image_url,
            "media[title]": title,
            "media[link]": BASE_URL,
        }
        
        headers = {
            "Authorization": f"Bearer {BUFFER_TOKEN}"
        }
        
        response = requests.post(buffer_url, data=payload, headers=headers, timeout=30)
        result = response.json()

        if response.status_code == 200 and result.get('success'):
            logging.info(f"Successfully sent to Buffer! Pin will appear on Pinterest shortly.")
            # Move file to done folder
            filename = os.path.basename(image_path)
            done_path = os.path.join(DONE_DIR, f"{int(time.time())}_{filename}")
            os.rename(image_path, done_path)
            log_activity(image_path, board_name, "Success (via Buffer)", title)
        else:
            error_msg = result.get('message', json.dumps(result))
            logging.error(f"Buffer API Error ({response.status_code}): {error_msg}")
            log_activity(image_path, board_name, f"Buffer Error: {error_msg}", title)
            
    except requests.exceptions.Timeout:
        logging.error("Buffer API timed out after 30 seconds.")
        log_activity(image_path, board_name, "Error: Timeout", title)
    except Exception as e:
        logging.error(f"Bot Exception: {e}")
        log_activity(image_path, board_name, f"System Error: {str(e)}", title)

if __name__ == "__main__":
    run_bot_job()
