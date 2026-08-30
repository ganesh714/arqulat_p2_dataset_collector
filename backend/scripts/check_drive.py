import os
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()
creds = Credentials(
    token=None,
    refresh_token=os.getenv('GOOGLE_REFRESH_TOKEN'),
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    token_uri='https://oauth2.googleapis.com/token',
    scopes=['https://www.googleapis.com/auth/drive.file']
)
service = build('drive', 'v3', credentials=creds)

results = service.files().list(
    q="trashed=false",
    fields='files(id, name, size, mimeType, parents)',
    supportsAllDrives=True,
    includeItemsFromAllDrives=True,
    pageSize=20,
    orderBy='createdTime desc'
).execute()

print('Recent files:')
for f in results.get('files', []):
    print(f"Name: {f['name']} | ID: {f['id']} | Size: {f.get('size', 'N/A')} | Mime: {f.get('mimeType')}")

