# ARQULAT Agent CLI — Complete entries via API (no browser needed)
#
# This script lets AI agents work on entries by calling your backend API directly.
# It's 10-100x faster and cheaper than navigating the browser UI.
#
# Usage:
#   python agent_cli.py --help                     # Show all commands
#   python agent_cli.py login                      # Login and cache token
#   python agent_cli.py list                       # List your assigned entries
#   python agent_cli.py show <entry_id>            # Show entry details + prompt
#   python agent_cli.py save <entry_id>            # Save think_block + phase2_code
#   python agent_cli.py run <entry_id>             # Run test + wait + download render
#   python agent_cli.py verify <entry_id>          # Download render to verify visually
#   python agent_cli.py submit <entry_id>          # Submit for review
#   python agent_cli.py do <entry_id>              # Workflow: save -> run -> download render (verify before submit)
#
# Environment variables (or .env file):
#   ARQULAT_API_URL    — Backend URL (default: https://arqulat-p2-dataset-collector.onrender.com)
#   ARQULAT_USERNAME   — Login username
#   ARQULAT_PASSWORD   — Login password

import os
import sys
import json
import time
import argparse
import requests
from pathlib import Path

# ─── Configuration ──────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

API_URL = os.getenv("ARQULAT_API_URL", "https://arqulat-p2-dataset-collector.onrender.com")
USERNAME = os.getenv("ARQULAT_USERNAME", "")
PASSWORD = os.getenv("ARQULAT_PASSWORD", "")

TOKEN_FILE = Path(__file__).parent / ".agent_token"
OUTPUT_DIR = Path(__file__).parent / "agent_output"
POLL_INTERVAL = 4  # seconds between job status checks
MAX_POLL_ATTEMPTS = 90  # max ~6 minutes wait


# ─── Token Management ──────────────────────────────────────────────
def save_token(token: str):
    TOKEN_FILE.write_text(token)

def load_token() -> str:
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text().strip()
    return ""

def auth_headers() -> dict:
    token = load_token()
    if not token:
        print("ERROR: Not logged in. Run: python agent_cli.py login")
        sys.exit(1)
    return {"Authorization": f"Bearer {token}"}


# ─── API Helpers ────────────────────────────────────────────────────
def api_get(path: str, params: dict = None) -> dict:
    resp = requests.get(f"{API_URL}{path}", headers=auth_headers(), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()

def api_post(path: str, json_data: dict = None) -> dict:
    resp = requests.post(f"{API_URL}{path}", headers=auth_headers(), json=json_data, timeout=60)
    resp.raise_for_status()
    return resp.json()

def api_patch(path: str, json_data: dict) -> dict:
    resp = requests.patch(f"{API_URL}{path}", headers=auth_headers(), json=json_data, timeout=30)
    resp.raise_for_status()
    return resp.json()

def api_download(path: str, save_to: Path) -> Path:
    """Download a binary file (render image, model) from the API."""
    resp = requests.get(f"{API_URL}{path}", headers=auth_headers(), timeout=120, stream=True)
    resp.raise_for_status()
    save_to.parent.mkdir(parents=True, exist_ok=True)
    with open(save_to, "wb") as f:
        for chunk in resp.iter_content(chunk_size=65536):
            f.write(chunk)
    return save_to


def download_render_for_entry(entry_id: str, job: dict = None) -> Path:
    """
    Download the render image for an entry to a local file.
    If a test-run job is provided, downloads the temp render.
    Otherwise downloads the entry's saved render.
    Returns the local file path.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    if job and job.get("is_test_run") and job["status"] == "done" and job.get("temp_render_url"):
        # Download temp render from test run
        render_path = OUTPUT_DIR / f"{entry_id}_render.png"
        job_id = job["id"]
        api_download(f"/api/entries/{entry_id}/jobs/{job_id}/temp-render", render_path)
    else:
        # Download saved render from entry
        render_path = OUTPUT_DIR / f"{entry_id}_render.png"
        api_download(f"/api/entries/{entry_id}/render", render_path)
    
    return render_path


# ─── Commands ───────────────────────────────────────────────────────
def cmd_login(args):
    """Login and cache the JWT token."""
    username = args.username or USERNAME
    password = args.password or PASSWORD
    if not username or not password:
        print("ERROR: Provide --username and --password, or set ARQULAT_USERNAME/ARQULAT_PASSWORD env vars")
        sys.exit(1)

    resp = requests.post(
        f"{API_URL}/api/auth/login",
        data={"username": username, "password": password},
        timeout=15,
    )
    resp.raise_for_status()
    token = resp.json()["access_token"]
    save_token(token)
    
    # Verify by fetching profile
    me = requests.get(f"{API_URL}/api/auth/me", headers={"Authorization": f"Bearer {token}"}, timeout=10).json()
    print(f"OK Logged in as: {me.get('username')} (role: {me.get('role')})")
    print(f"  Token saved to: {TOKEN_FILE}")


def cmd_list(args):
    """List entries assigned to this user."""
    params = {}
    if args.status:
        params["entry_status"] = args.status
    
    entries = api_get("/api/entries", params)
    
    if not entries:
        print("No entries found.")
        return
    
    # Filter by status for display
    status_filter = args.status
    
    print(f"\n{'ID':<38} {'Code':<25} {'Status':<12} {'Prompt ID'}")
    print("-" * 110)
    for e in entries:
        status = e.get("status", "?")
        if status_filter and status != status_filter:
            continue
        print(f"{e['id']:<38} {e.get('code', 'N/A'):<25} {status:<12} {e.get('prompt_id', 'N/A')}")
    
    # Summary
    statuses = {}
    for e in entries:
        s = e.get("status", "unknown")
        statuses[s] = statuses.get(s, 0) + 1
    print(f"\nTotal: {len(entries)} entries -- " + ", ".join(f"{v} {k}" for k, v in sorted(statuses.items())))


def cmd_show(args):
    """Show full details of an entry + its prompt text."""
    entry_id = args.entry_id
    
    # Get entry details
    entries = api_get("/api/entries")
    entry = next((e for e in entries if e["id"] == entry_id), None)
    if not entry:
        print(f"ERROR: Entry {entry_id} not found or not accessible")
        sys.exit(1)
    
    print(f"\n=== Entry: {entry.get('code', 'N/A')} ===")
    print(f"  ID:     {entry['id']}")
    print(f"  Status: {entry['status']}")
    print(f"  Has render: {'Yes' if entry.get('render_url') else 'No'}")
    print(f"  Has model:  {'Yes' if entry.get('glb_url') else 'No'}")
    
    # Get prompt
    prompt_id = entry.get("prompt_id")
    if prompt_id:
        try:
            prompt = api_get(f"/api/prompts/{prompt_id}")
            print(f"\n--- Prompt ({prompt.get('code', 'N/A')}) ---")
            print(f"  Text: {prompt.get('prompt_text', 'N/A')}")
            if prompt.get("tags"):
                print(f"  Tags: {', '.join(prompt['tags'])}")
            
            # Get category name
            cat_id = prompt.get("category_id")
            if cat_id:
                try:
                    taxonomy = api_get("/api/taxonomy")
                    for phase in taxonomy:
                        for sub in phase.get("subphases", []):
                            for cat in sub.get("categories", []):
                                if cat["id"] == cat_id:
                                    print(f"  Category: {cat['name']}")
                except: pass
        except Exception as e:
            print(f"  (Could not load prompt: {e})")
    
    # Show existing code
    if entry.get("think_block"):
        tb = entry["think_block"]
        print(f"\n--- Think Block (current) ---")
        print(tb[:500] + ("..." if len(tb) > 500 else ""))
    
    if entry.get("phase2_code"):
        pc = entry["phase2_code"]
        print(f"\n--- Phase 2 Code (current) ---")
        print(pc[:500] + ("..." if len(pc) > 500 else ""))
    
    # Show reviewer notes if any
    if entry.get("reviewer_notes"):
        print(f"\n--- WARNING: Reviewer Notes ---")
        print(entry["reviewer_notes"])


def cmd_save(args):
    """Save think_block and/or phase2_code to an entry."""
    entry_id = args.entry_id
    payload = {}
    
    if args.think_block_file:
        payload["think_block"] = Path(args.think_block_file).read_text(encoding="utf-8")
    elif args.think_block:
        payload["think_block"] = args.think_block
    
    if args.code_file:
        payload["phase2_code"] = Path(args.code_file).read_text(encoding="utf-8")
    elif args.code:
        payload["phase2_code"] = args.code
    
    if not payload:
        print("ERROR: Provide --think-block/--think-block-file and/or --code/--code-file")
        sys.exit(1)
    
    result = api_patch(f"/api/entries/{entry_id}", payload)
    print(f"OK Saved entry {result.get('code', entry_id)} (status: {result['status']})")


def cmd_run(args):
    """Run a test and wait for the result."""
    entry_id = args.entry_id
    
    # Get current entry code
    entries = api_get("/api/entries")
    entry = next((e for e in entries if e["id"] == entry_id), None)
    if not entry:
        print(f"ERROR: Entry {entry_id} not found")
        sys.exit(1)
    
    think_block = entry.get("think_block", "")
    phase2_code = entry.get("phase2_code", "")
    
    # Allow override from files
    if args.code_file:
        phase2_code = Path(args.code_file).read_text(encoding="utf-8")
    if args.think_block_file:
        think_block = Path(args.think_block_file).read_text(encoding="utf-8")
    
    if not phase2_code.strip():
        print("ERROR: No phase2_code found. Save code first with 'save' command.")
        sys.exit(1)
    
    # Submit test run
    print(f">> Submitting test run for {entry.get('code', entry_id)}...")
    try:
        job = api_post(f"/api/entries/{entry_id}/test-run", {
            "think_block": think_block,
            "phase2_code": phase2_code,
        })
    except requests.HTTPError as e:
        error_detail = ""
        try: error_detail = e.response.json().get("detail", "")
        except: pass
        print(f"ERROR: {e}\n  {error_detail}")
        sys.exit(1)
    
    job_id = job["id"]
    print(f"  Job created: {job_id}")
    
    # Poll for completion
    print(f"  Waiting for worker...", end="", flush=True)
    for i in range(MAX_POLL_ATTEMPTS):
        time.sleep(POLL_INTERVAL)
        jobs = api_get(f"/api/entries/{entry_id}/jobs")
        latest = next((j for j in jobs if j["id"] == job_id), None)
        if not latest:
            print(".", end="", flush=True)
            continue
        
        if latest["status"] == "pending":
            print(".", end="", flush=True)
        elif latest["status"] == "running":
            if i == 0 or jobs[0]["status"] != "running":
                print("\n  Worker picked up the job, executing...", end="", flush=True)
            else:
                print(".", end="", flush=True)
        elif latest["status"] == "done":
            print(f"\nOK Test run SUCCEEDED!")
            if latest.get("error_log"):
                print(f"\n--- Terminal Output ---")
                print(latest["error_log"])
            else:
                print("  No errors. Script executed successfully.")
            
            # Auto-download the render for visual verification
            try:
                render_path = download_render_for_entry(entry_id, latest)
                print(f"\n>>> RENDER SAVED: {render_path.resolve()}")
                print(f"    View this image to verify the 3D model matches the prompt.")
                print(f"    If it looks correct, run: python agent_cli.py submit {entry_id}")
                print(f"    If NOT correct, fix code and re-run.")
            except Exception as e:
                print(f"  (Could not download render: {e})")
            
            return {"success": True, "job": latest}
        elif latest["status"] == "failed":
            print(f"\nFAIL Test run FAILED!")
            if latest.get("error_log"):
                print(f"\n--- Error Log ---")
                print(latest["error_log"])
            return {"success": False, "job": latest}
    
    print(f"\nWARNING: Timed out after {MAX_POLL_ATTEMPTS * POLL_INTERVAL}s. Job may still be running.")
    return {"success": False, "job": None}


def cmd_promote(args):
    """Promote a successful test run result to the entry (save 3D model/render)."""
    entry_id = args.entry_id
    
    # Find the latest successful test run
    jobs = api_get(f"/api/entries/{entry_id}/jobs")
    test_jobs = [j for j in jobs if j.get("is_test_run") and j["status"] == "done"]
    if not test_jobs:
        print("ERROR: No successful test run found to promote")
        sys.exit(1)
    
    job_id = args.job_id or test_jobs[0]["id"]
    result = api_post(f"/api/entries/{entry_id}/promote-test", {"job_id": job_id})
    print(f"OK Promoted test run -> entry {result.get('code', entry_id)}")
    return result


def cmd_submit(args):
    """Submit an entry for review."""
    entry_id = args.entry_id
    
    # Promote any pending test run first
    jobs = api_get(f"/api/entries/{entry_id}/jobs")
    test_jobs = [j for j in jobs if j.get("is_test_run") and j["status"] == "done"]
    if test_jobs:
        print("  Promoting latest test run result...")
        api_post(f"/api/entries/{entry_id}/promote-test", {"job_id": test_jobs[0]["id"]})
    
    result = api_post(f"/api/entries/{entry_id}/submit")
    print(f"OK Submitted entry {result.get('code', entry_id)} for review (status: {result['status']})")


def cmd_verify(args):
    """Download the render image for visual verification."""
    entry_id = args.entry_id
    
    # Check for latest successful test run first
    jobs = api_get(f"/api/entries/{entry_id}/jobs")
    test_job = None
    if jobs:
        test_jobs = [j for j in jobs if j.get("is_test_run") and j["status"] == "done"]
        if test_jobs:
            test_job = test_jobs[0]
    
    try:
        render_path = download_render_for_entry(entry_id, test_job)
        print(f"OK Render downloaded to: {render_path.resolve()}")
        print(f"\n>>> VERIFY: Open this image and check if the 3D model matches the prompt.")
        print(f"    If correct: python agent_cli.py submit {entry_id}")
        print(f"    If wrong:   Fix code, then: python agent_cli.py run {entry_id}")
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            print("No render available yet. Run a test first: python agent_cli.py run <entry_id>")
        else:
            raise


def cmd_logs(args):
    """Show terminal/error logs from the latest job."""
    entry_id = args.entry_id
    jobs = api_get(f"/api/entries/{entry_id}/jobs")
    if not jobs:
        print("No jobs found for this entry.")
        return
    
    latest = jobs[0]
    print(f"Job: {latest['id']} | Status: {latest['status']} | Test run: {latest.get('is_test_run', False)}")
    if latest.get("error_log"):
        print(f"\n--- Output ---")
        print(latest["error_log"])
    else:
        print("  (No output available)")


def cmd_do(args):
    """Workflow: save -> run -> download render for verification.
    
    Does NOT auto-submit. The agent must:
    1. View the downloaded render image
    2. Compare it to the prompt
    3. If it matches: run 'python agent_cli.py submit <entry_id>'
    4. If it doesn't match: fix code and re-run 'python agent_cli.py do <entry_id> ...'
    """
    entry_id = args.entry_id
    
    # Step 1: Save code
    payload = {}
    if args.think_block_file:
        payload["think_block"] = Path(args.think_block_file).read_text(encoding="utf-8")
    if args.code_file:
        payload["phase2_code"] = Path(args.code_file).read_text(encoding="utf-8")
    
    if payload:
        print("Step 1: Saving code...")
        result = api_patch(f"/api/entries/{entry_id}", payload)
        print(f"  OK Saved ({result['status']})")
    else:
        print("Step 1: Using existing code (no files provided)")
    
    # Step 2: Run test
    print("\nStep 2: Running test...")
    run_result = cmd_run(args)
    
    if not run_result or not run_result.get("success"):
        print("\nFAIL Test run failed. Fix the code and try again.")
        print("  Use: python agent_cli.py logs <entry_id>")
        sys.exit(1)
    
    # Step 3: Render is already downloaded by cmd_run.
    # Show the prompt again so the agent can compare.
    print("\n" + "=" * 60)
    print("VERIFICATION REQUIRED")
    print("=" * 60)
    
    # Fetch and display the prompt for comparison
    entries = api_get("/api/entries")
    entry = next((e for e in entries if e["id"] == entry_id), None)
    if entry and entry.get("prompt_id"):
        try:
            prompt = api_get(f"/api/prompts/{entry['prompt_id']}")
            print(f"\nPrompt: {prompt.get('prompt_text', 'N/A')}")
            if prompt.get("tags"):
                print(f"Tags: {', '.join(prompt['tags'])}")
        except: pass
    
    render_file = OUTPUT_DIR / f"{entry_id}_render.png"
    print(f"\nRender image: {render_file.resolve()}")
    print(f"\n>>> VIEW the render image above and compare to the prompt.")
    print(f"    If it MATCHES the prompt:")
    print(f"      python agent_cli.py submit {entry_id}")
    print(f"    If it does NOT match:")
    print(f"      Fix code.py, then: python agent_cli.py do {entry_id} --code-file code.py")


# ─── CLI Parser ─────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="ARQULAT Agent CLI -- Complete entries via API (no browser needed)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python agent_cli.py login --username agent1 --password secret123
  python agent_cli.py list --status draft
  python agent_cli.py show abc123-def456
  python agent_cli.py save abc123 --code-file code.py --think-block-file think.txt
  python agent_cli.py run abc123
  python agent_cli.py verify abc123              # Download render to verify
  python agent_cli.py submit abc123              # Submit after verification
  python agent_cli.py do abc123 --code-file code.py --think-block-file think.txt
        """
    )
    sub = parser.add_subparsers(dest="command")
    
    # login
    p_login = sub.add_parser("login", help="Login and cache JWT token")
    p_login.add_argument("--username", "-u", default="")
    p_login.add_argument("--password", "-p", default="")
    
    # list
    p_list = sub.add_parser("list", help="List your assigned entries")
    p_list.add_argument("--status", "-s", choices=["draft", "needs_fix", "submitted", "approved", "rejected"], default=None)
    
    # show
    p_show = sub.add_parser("show", help="Show entry details + prompt")
    p_show.add_argument("entry_id")
    
    # save
    p_save = sub.add_parser("save", help="Save think_block and/or phase2_code")
    p_save.add_argument("entry_id")
    p_save.add_argument("--think-block", default=None, help="Think block text (inline)")
    p_save.add_argument("--think-block-file", default=None, help="Path to think block file")
    p_save.add_argument("--code", default=None, help="Phase 2 code (inline)")
    p_save.add_argument("--code-file", default=None, help="Path to phase 2 code file")
    
    # run
    p_run = sub.add_parser("run", help="Run test and wait for result")
    p_run.add_argument("entry_id")
    p_run.add_argument("--code-file", default=None, help="Override phase 2 code from file")
    p_run.add_argument("--think-block-file", default=None, help="Override think block from file")
    
    # promote
    p_promote = sub.add_parser("promote", help="Promote a test run result")
    p_promote.add_argument("entry_id")
    p_promote.add_argument("--job-id", default=None)
    
    # submit
    p_submit = sub.add_parser("submit", help="Submit entry for review")
    p_submit.add_argument("entry_id")
    
    # verify
    p_verify = sub.add_parser("verify", help="Download render image for visual verification")
    p_verify.add_argument("entry_id")
    
    # logs
    p_logs = sub.add_parser("logs", help="Show latest job output/errors")
    p_logs.add_argument("entry_id")
    
    # do (full workflow minus submit)
    p_do = sub.add_parser("do", help="Workflow: save -> run -> download render (verify before submit)")
    p_do.add_argument("entry_id")
    p_do.add_argument("--think-block-file", default=None)
    p_do.add_argument("--code-file", default=None)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(0)
    
    commands = {
        "login": cmd_login,
        "list": cmd_list,
        "show": cmd_show,
        "save": cmd_save,
        "run": cmd_run,
        "verify": cmd_verify,
        "promote": cmd_promote,
        "submit": cmd_submit,
        "logs": cmd_logs,
        "do": cmd_do,
    }
    
    try:
        commands[args.command](args)
    except requests.HTTPError as e:
        detail = ""
        try: detail = e.response.json().get("detail", "")
        except: pass
        print(f"API Error: {e.response.status_code} -- {detail or e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(130)


if __name__ == "__main__":
    main()
