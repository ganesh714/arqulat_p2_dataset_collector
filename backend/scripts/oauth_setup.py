import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from dotenv import load_dotenv, set_key

# Load existing .env
dotenv_path = ".env"
load_dotenv(dotenv_path)

CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

if not CLIENT_ID or not CLIENT_SECRET:
    print("Error: GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET not found in .env")
    exit(1)

# Create a temporary client_secrets.json expected by InstalledAppFlow
client_config = {
    "installed": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}

SCOPES = ["https://www.googleapis.com/auth/drive.file"]

def main():
    print("Starting local OAuth flow...", flush=True)
    print("NOTE: You will likely see a 'Google hasn't verified this app' warning.", flush=True)
    print("      This is expected because it is your own test app. Click 'Advanced' -> 'Go to <app_name> (unsafe)' to proceed.\n", flush=True)

    # Save temp config
    with open("temp_client_secrets.json", "w") as f:
        json.dump(client_config, f)

    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            "temp_client_secrets.json", scopes=SCOPES
        )
        
        prompt_msg = (
            "\n" + "="*80 + "\n"
            "Please visit the following URL to authorize the application:\n"
            "{url}\n"
            + "="*80 + "\n"
        )
        
        creds = flow.run_local_server(port=8080, open_browser=False, authorization_prompt_message=prompt_msg)

        print("\nSuccessfully authenticated!", flush=True)
        print("Refresh Token obtained:", creds.refresh_token, flush=True)

        # Append to .env
        if creds.refresh_token:
            set_key(dotenv_path, "GOOGLE_REFRESH_TOKEN", creds.refresh_token)
            print("Saved GOOGLE_REFRESH_TOKEN to .env", flush=True)
        else:
            print("Warning: No refresh token returned. If you have authenticated before, you may need to revoke access in your Google Account settings and try again.", flush=True)
            
    finally:
        if os.path.exists("temp_client_secrets.json"):
            os.remove("temp_client_secrets.json")

if __name__ == "__main__":
    main()
