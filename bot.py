import os
import time
import json
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv
from urllib.parse import quote

# Import database functions
from database import log_activity, get_board_description, get_random_fallback_title

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
    title = get_random_fallback_title()
    if not title:
        title = f"Stunning {board_name} Ideas"
    return title, f"Beautiful {board_name} inspiration. #aesthetic #{board_name.replace(' ', '')}"

def generate_ai_content(board_name):
    if not GEMINI_API_KEY: return _fallback_content(board_name)
    
    board_desc = get_board_description(board_name)
    context_str = f"The context/description of this board is: '{board_desc}'." if board_desc else ""
    
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        prompt = (
            f"Act as an expert Pinterest SEO copywriter. Write a highly engaging, click-worthy title (max 60 characters) "
            f"and a descriptive, keyword-rich SEO description (max 400 characters, ending with 5 highly relevant hashtags) "
            f"for an aesthetic Pinterest pin saved to the board: '{board_name}'. {context_str} Ensure the tone is inspiring, aesthetic, and modern. "
            f"Return ONLY valid JSON exactly matching this format: {{\"title\": \"...\", \"description\": \"...\"}} "
            f"Do not include any markdown formatting, backticks, or extra text."
        )
        response = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
        response.raise_for_status()
        data = response.json()
        if 'candidates' not in data: 
            return _fallback_content(board_name)
            
        text = data['candidates'][0]['content']['parts'][0]['text'].replace('```json', '').replace('```', '').strip()
        result = json.loads(text)
        return result.get('title'), result.get('description')
    except Exception as e:
        logging.error(f"AI Generation Failed: {str(e)}")
        return _fallback_content(board_name)

def run_bot_job():
    logging.info("Starting Pinterest bot job via Make.com Bridge...")
    
    if not MAKE_WEBHOOK_URL:
        logging.error("MAKE_WEBHOOK_URL is missing from .env")
        return

    image_path, board_name = get_oldest_image()
    if not image_path: 
        logging.info("No images found in queue.")
        return
    
    title, description = generate_ai_content(board_name)
    filename = os.path.basename(image_path)
    done_filename = f"{int(time.time())}_{filename}"
    encoded_filename = quote(done_filename)
    image_url = f"{BASE_URL}/done/{encoded_filename}"
    
    logging.info(f"Sending to Make.com: {title} (Board: {board_name})")

    try:
        payload = {
            "title": title,
            "description": f"{title}\n\n{description}",
            "image_url": image_url,
            "board": board_name,
            "link": BASE_URL
        }
        
        response = requests.post(MAKE_WEBHOOK_URL, json=payload, timeout=30)
        
        time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if response.status_code == 200:
            logging.info("Success! Make.com received the data.")
            os.makedirs(DONE_DIR, exist_ok=True)
            done_path = os.path.join(DONE_DIR, done_filename)
            os.rename(image_path, done_path)
            log_activity(filename, board_name, "Success", title, time_str)
        else:
            logging.error(f"Make.com Error: {response.status_code}")
            log_activity(filename, board_name, f"Make.com Error: {response.status_code}", title, time_str)
            
    except Exception as e:
        logging.error(f"Bot Exception: {e}")
        time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_activity(filename, board_name, f"System Error", title, time_str)

if __name__ == "__main__":
    run_bot_job()
