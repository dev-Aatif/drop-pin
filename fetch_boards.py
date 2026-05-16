import os
import json
import requests
from dotenv import load_dotenv

# Load env variables
load_dotenv()
BUFFER_API_KEY = os.getenv("BUFFER_API_KEY")

if not BUFFER_API_KEY:
    print("Error: BUFFER_API_KEY not found in .env file.")
    exit(1)

# We use api.bufferapp.com because it is officially whitelisted by PythonAnywhere's free tier
url = "https://api.bufferapp.com/1/profiles.json"
headers = {"Authorization": f"Bearer {BUFFER_API_KEY}"}

print("Fetching your Pinterest boards from Buffer...")
try:
    response = requests.get(url, headers=headers, timeout=15)
    
    if response.status_code == 200:
        profiles = response.json()
        boards_mapping = {}
        
        print("\n--- FOUND PINTEREST BOARDS ---")
        for profile in profiles:
            if profile.get('service') == 'pinterest':
                # Buffer stores the board name in different fields depending on how it was connected
                # Usually 'service_username' or 'formatted_username'
                board_name = profile.get('service_username', profile.get('formatted_username', 'Unknown Board'))
                board_id = profile.get('id')
                
                print(f"Board Name: {board_name}")
                print(f"Channel ID: {board_id}")
                print("-" * 30)
                
                # Add to mapping
                boards_mapping[board_name] = board_id
        
        if not boards_mapping:
            print("No Pinterest boards found in this Buffer account.")
        else:
            # Save directly to boards.json
            base_dir = os.path.dirname(os.path.abspath(__file__))
            boards_file = os.path.join(base_dir, "data", "boards.json")
            
            with open(boards_file, 'w') as f:
                json.dump(boards_mapping, f, indent=4)
                
            print(f"\nSUCCESS: Automatically saved {len(boards_mapping)} boards to data/boards.json!")
            print("Please check data/boards.json. You may need to rename the keys to match your exact folder names.")
            
    else:
        print(f"Failed to fetch profiles. Status Code: {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"Error connecting to Buffer API: {e}")
    print("If you get a Proxy Error, it means PythonAnywhere is blocking this request.")
