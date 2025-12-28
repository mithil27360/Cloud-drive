import requests
import os

# Config
BASE_URL = "http://localhost:8000"
FILE_PATH = "/Users/mithil/Desktop/cloud-drive/data/test source/attentionisallyouneed.pdf"
ADMIN_EMAIL = "mithil27360"
ADMIN_PASS = "expelliarmus@27"

def get_token():
    print("🔑 Authenticating...")
    resp = requests.post(f"{BASE_URL}/auth/admin/login", json={
        "username": ADMIN_EMAIL, 
        "password": ADMIN_PASS
    })
    if resp.status_code != 200:
        raise Exception(f"Login failed: {resp.text}")
    return resp.json()["access_token"]

def upload_file(token):
    print(f"📤 Uploading {os.path.basename(FILE_PATH)}...")
    
    if not os.path.exists(FILE_PATH):
        raise Exception("File not found!")
        
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": open(FILE_PATH, "rb")}
    
    resp = requests.post(f"{BASE_URL}/api/files/upload", headers=headers, files=files)
    
    if resp.status_code == 200:
        print("✅ Upload successful!")
        print(resp.json())
    else:
        print(f"❌ Upload failed: {resp.status_code} - {resp.text}")

if __name__ == "__main__":
    try:
        token = get_token()
        upload_file(token)
    except Exception as e:
        print(f"Error: {e}")
