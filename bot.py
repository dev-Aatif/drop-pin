import os
import time
import json
import random
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv
from urllib.parse import quote

# Import database functions
from database import log_activity, get_board_description

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

def get_random_board_image():
    """Finds an image from a randomly selected board to diversify the feed."""
    if not os.path.exists(PINS_DIR):
        return None, None
        
    valid_boards = []
    
    # Gather boards that have at least one valid image
    for folder in os.listdir(PINS_DIR):
        folder_path = os.path.join(PINS_DIR, folder)
        if os.path.isdir(folder_path):
            has_images = any(
                os.path.isfile(os.path.join(folder_path, f)) 
                and not f.startswith('.') 
                and os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS 
                for f in os.listdir(folder_path)
            )
            if has_images:
                valid_boards.append(folder)
                
    if not valid_boards:
        return None, None
        
    # Pick a random board
    board_name = random.choice(valid_boards)
    folder_path = os.path.join(PINS_DIR, board_name)
    
    # Get the oldest image from THAT board to maintain order within the topic
    oldest_file = None
    oldest_time = float('inf')
    
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
                
    return oldest_file, board_name

def clean_old_done_files():
    if not os.path.exists(DONE_DIR):
        return
    now = time.time()
    for filename in os.listdir(DONE_DIR):
        file_path = os.path.join(DONE_DIR, filename)
        try:
            if os.path.isfile(file_path):
                # Check if file is older than 48 hours (48 * 3600 seconds)
                if os.stat(file_path).st_mtime < now - (48 * 3600):
                    os.remove(file_path)
                    logging.info(f"Auto-cleaned old file: {filename}")
        except Exception as e:
            logging.error(f"Failed to clean old file {filename}: {e}")

def _fallback_content(board_name):
    clean_name = board_name.replace('_', ' ')
    title = f"Stunning {clean_name} Ideas"
    desc = (
        f"Beautiful {clean_name} inspiration. A carefully curated collection of aesthetic ideas, designs, "
        f"and style concepts. Let these visual ideas inspire your next creative project, mood board, or home update. "
        f"Discover the best inspiration and unique creative details today. #aesthetic #{clean_name.replace(' ', '')} "
        f"#inspiration #decor #style"
    )
    return title, desc

def generate_ai_content(board_name):
    if not GEMINI_API_KEY: return _fallback_content(board_name)
    
    display_board_name = board_name.replace('_', ' ')
    board_desc = get_board_description(board_name)
    context_str = f"The context/description of this board is: '{board_desc}'." if board_desc else ""
    
    # Injected random variation to prevent duplicate copy
    styles = [
        "minimalist elegance", "modern details", "bold statement", "warm tones", 
        "airy & light", "moody & raw", "sophisticated textures", "creative angles",
        "timeless layout", "inspiring vibes", "unique elements", "artistic flow"
    ]
    random_style = random.choice(styles)
    
    # Cascade list of fallback models
    models_to_try = [
        "gemini-flash-latest",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-pro-latest"
    ]
    
    prompt = (
        f"Act as an expert Pinterest SEO copywriter. Write a highly engaging, click-worthy title (max 60 characters) "
        f"and a descriptive, keyword-rich SEO description (MUST be between 350 and 480 characters long, do not make it shorter than 350 characters, and end it with exactly 5 highly relevant hashtags) "
        f"for an aesthetic Pinterest pin saved to the board: '{display_board_name}'. {context_str} "
        f"Write detailed sentences describing the aesthetic, mood, and visual features of the pin topic to reach the required length limit. "
        f"Focus the tone of the description on a '{random_style}' perspective. Ensure the overall style is inspiring, aesthetic, and modern. "
        f"Return ONLY valid JSON exactly matching this format: {{\"title\": \"...\", \"description\": \"...\"}} "
        f"Do not include any markdown formatting, backticks, or extra text."
    )
    
    # Configure temperature to maximize creativity/variety
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 1.0,
            "topP": 0.95
        }
    }
    
    for model in models_to_try:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
            response = requests.post(url, json=payload, timeout=15)
            response.raise_for_status()
            data = response.json()
            if 'candidates' not in data: 
                continue
                
            text = data['candidates'][0]['content']['parts'][0]['text'].replace('```json', '').replace('```', '').strip()
            result = json.loads(text)
            title = result.get('title')
            desc = result.get('description')
            if title and desc:
                logging.info(f"AI Generation Succeeded using model: {model}")
                return title, desc
        except Exception as e:
            logging.warning(f"AI Generation failed with model {model}: {str(e)}. Trying next fallback...")
            continue
            
    # If all models fail, resort to fallback hardcoded content
    logging.error("All Gemini API models failed or quota exceeded. Falling back to default text.")
    return _fallback_content(board_name)

def run_bot_job():
    logging.info("Starting Pinterest bot job via Make.com Bridge...")
    
    if not MAKE_WEBHOOK_URL:
        logging.error("MAKE_WEBHOOK_URL is missing from .env")
        return

    image_path, board_name = get_random_board_image()
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
            "board": board_name.replace('_', ' '),
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
        
    # Automatically clean up files older than 48 hours in the done folder
    clean_old_done_files()

if __name__ == "__main__":
    run_bot_job()
