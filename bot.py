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
BUFFER_API_KEY = os.getenv("BUFFER_API_KEY")
BUFFER_CHANNEL_ID = os.getenv("BUFFER_CHANNEL_ID")
BASE_URL = os.getenv("BASE_URL", "").rstrip("/") 
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# DEFINITIVE 2026 BUFFER ENDPOINT
BUFFER_API_URL = "https://api.buffer.com"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PINS_DIR = os.path.join(BASE_DIR, "data", "pins")
DONE_DIR = os.path.join(BASE_DIR, "data", "done")
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

def generate_ai_content(board_name):
    """Uses Gemini to generate a viral title and description."""
    if not GEMINI_API_KEY:
        return f"{board_name} Inspiration", f"Beautiful {board_name} aesthetic. #inspiration"

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
        prompt = (
            f"Create a viral Pinterest title and a short SEO description (with 5 hashtags) "
            f"for a pin about '{board_name}'. Return ONLY valid JSON: {{\"title\": \"...\", \"description\": \"...\"}}"
        )
        response = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
        text = response.json()['candidates'][0]['content']['parts'][0]['text']
        text = text.replace('```json', '').replace('```', '').strip()
        result = json.loads(text)
        return result.get('title'), result.get('description')
    except Exception as e:
        logging.error(f"Gemini error: {e}")
        return f"{board_name} Style", f"The best {board_name} inspiration. #aesthetic"

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
    logging.info("Starting Pinterest bot job via Buffer GraphQL...")
    
    image_path, board_name = get_oldest_image()
    if not image_path: return
    
    title, description = generate_ai_content(board_name)
    relative_path = os.path.relpath(image_path, PINS_DIR)
    encoded_path = "/".join(quote(segment) for segment in relative_path.split(os.sep))
    image_url = f"{BASE_URL}/pins/{encoded_path}"
    
    logging.info(f"Preparing post for: {title}")

    try:
        # LATEST 2026 GRAPHQL MUTATION
        mutation = """
        mutation CreatePost($input: CreatePostInput!) {
            createPost(input: $input) {
                ... on PostActionSuccess {
                    post { id }
                }
                ... on MutationError {
                    message
                }
            }
        }
        """
        
        variables = {
            "input": {
                "text": f"{title}\n\n{description}",
                "channelId": BUFFER_CHANNEL_ID,
                "schedulingType": "automatic",
                "mode": "addToQueue",
                "assets": [
                    {
                        "image": {
                            "url": image_url
                        }
                    }
                ]
            }
        }
        
        headers = {
            "Authorization": f"Bearer {BUFFER_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        response = requests.post(
            BUFFER_API_URL,
            json={"query": mutation, "variables": variables},
            headers=headers,
            timeout=30
        )
        
        result = response.json()
        
        if "errors" in result:
            error_msg = result["errors"][0].get("message")
            logging.error(f"Buffer API Error: {error_msg}")
            log_activity(image_path, board_name, f"Error: {error_msg}", title)
            return

        post_data = result.get("data", {}).get("createPost", {})
        if "post" in post_data:
            logging.info(f"Successfully sent to Buffer!")
            filename = os.path.basename(image_path)
            done_path = os.path.join(DONE_DIR, f"{int(time.time())}_{filename}")
            os.rename(image_path, done_path)
            log_activity(image_path, board_name, "Success", title)
        else:
            msg = post_data.get("message", "Unknown Mutation Error")
            logging.error(f"Mutation Error: {msg}")
            log_activity(image_path, board_name, f"Error: {msg}", title)
            
    except Exception as e:
        logging.error(f"Bot Exception: {e}")
        log_activity(image_path, board_name, f"System Error: {str(e)}", title)

if __name__ == "__main__":
    run_bot_job()
