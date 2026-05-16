import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()
BUFFER_API_KEY = os.getenv("BUFFER_API_KEY")

if not BUFFER_API_KEY:
    print("Error: BUFFER_API_KEY not found in .env file.")
    exit(1)

url = "https://api.buffer.com/v2/graphql"
headers = {"Authorization": f"Bearer {BUFFER_API_KEY}"}

print("Fetching your Organization ID...")
org_query = """
query {
  account {
    organizations {
      id
    }
  }
}
"""

try:
    org_response = requests.post(url, headers=headers, json={"query": org_query}, timeout=15)
    org_data = org_response.json()
    
    orgs = org_data.get('data', {}).get('account', {}).get('organizations', [])
    if not orgs:
        print("Error: Could not find any Buffer organizations on this account.")
        print(org_data)
        exit(1)
        
    org_id = orgs[0]['id']
    print(f"Found Organization ID: {org_id}")
    
    channels_query = f"""
    query {{
      channels(input: {{ organizationId: "{org_id}" }}) {{
        id
        name
        service
      }}
    }}
    """
    
    print("\nFetching Pinterest boards...")
    response = requests.post(url, headers=headers, json={"query": channels_query}, timeout=15)
    
    if response.status_code == 200:
        data = response.json()
        if 'errors' in data:
            print("GraphQL Error:", data['errors'])
            exit(1)
            
        channels = data.get('data', {}).get('channels', [])
        boards_mapping = {}
        
        print("\n--- FOUND PINTEREST BOARDS ---")
        for channel in channels:
            if channel.get('service') == 'pinterest':
                board_name = channel.get('name')
                board_id = channel.get('id')
                
                print(f"Board Name: {board_name}")
                print(f"Channel ID: {board_id}")
                print("-" * 30)
                
                boards_mapping[board_name] = board_id
        
        if not boards_mapping:
            print("No Pinterest boards found.")
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            boards_file = os.path.join(base_dir, "data", "boards.json")
            with open(boards_file, 'w') as f:
                json.dump(boards_mapping, f, indent=4)
            print(f"\nSUCCESS: Saved {len(boards_mapping)} boards to data/boards.json!")
    else:
        print(f"Failed: {response.text}")

except Exception as e:
    print(f"Error connecting: {e}")
    print("WARNING: You cannot run this on PythonAnywhere due to their firewall.")
    print("Please run this script on your LOCAL machine.")
