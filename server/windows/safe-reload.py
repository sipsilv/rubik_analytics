import os
import sys
import time
import subprocess
import signal
from watchfiles import watch

# Paths
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
APP_DIR = os.path.join(BACKEND_DIR, "app")
ENV_FILE = os.path.join(BACKEND_DIR, ".env")
# Removed --env-file to bypass Uvicorn's faulty metadata check
CMD = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

def load_env_vars(env_path):
    """Manually parse .env file to avoid Uvicorn's internal loader issues"""
    env_dict = {}
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, val = line.split('=', 1)
                # Removing surrounding quotes if present
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                env_dict[key] = val
    return env_dict

def start_server():
    print(f"[RELOAD] Starting Server...")
    
    # 1. Base Environment
    env = os.environ.copy()
    
    # 2. Load .env manually
    dotenv_vars = load_env_vars(ENV_FILE)
    env.update(dotenv_vars)
    
    # 3. Fixes & Optimizations
    env["UVICORN_RELOAD"] = "False"      # Disable Uvicorn's reloader (we use watchfiles)
    env["PYTHONIOENCODING"] = "utf-8"    # Fix Windows unicode issues
    env["TZ"] = "Asia/Kolkata"           # Force IST Timezone
    
    # Start as subprocess
    return subprocess.Popen(CMD, cwd=BACKEND_DIR, env=env)

def kill_server(process):
    if process:
        print("[RELOAD] Stopping Server (PID: {})...".format(process.pid))
        # Hard kill to ensure release
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True)
        # Verify dead
        process.wait()
        print("[RELOAD] Server Stopped. Cleanup Complete.")
        time.sleep(3)

def cleanup_zombies():
    """Aggressively kill any lingering uvicorn processes"""
    print("[RELOAD] Checking for zombie Uvicorn processes...")
    try:
        # Kill by port 8000? Or just generic python/uvicorn cleanup if possible?
        # Using netstat to find PID on port 8000 is safer but complex.
        # For now, relying on the fact that we are the supervisor.
        # But if we just restarted, maybe previous zombies exist.
        subprocess.run("taskkill /F /IM uvicorn.exe /T", shell=True, capture_output=True)
    except:
        pass

import threading

# Global Control
restart_needed = False
server_process = None

def get_process_status(process):
    if process is None:
        return "NOT_STARTED"
    return_code = process.poll()
    if return_code is None:
        return "RUNNING"
    return "STOPPED"

def watcher_thread():
    """Background thread to monitor file changes"""
    global restart_needed
    print(f"[RELOAD] Watching directory: {APP_DIR}")
    
    # Watch blocks, so we run it here
    for changes in watch(APP_DIR):
        print("\n[RELOAD] Detected changes:")
        for mode, path in changes:
            print(f"  - {mode.name}: {os.path.basename(path)}")
        restart_needed = True

def main():
    global server_process, restart_needed
    
    print(f"====================================================")
    print(f"  SAFE AUTO-RELOADER FOR RUBIK ANALYTICS")
    print(f"====================================================")
    print(f"  Watching: {APP_DIR}")
    print(f"  Mode:     Keep-Alive + Hard Restart")
    print(f"====================================================")

    # 1. Start Watcher Thread
    t = threading.Thread(target=watcher_thread, daemon=True)
    t.start()

    # 2. Start Initial Server
    server_process = start_server()

    # 3. Main Keep-Alive Loop
    try:
        while True:
            time.sleep(1)
            
            # Case A: File Change Detected
            if restart_needed:
                restart_needed = False
                print("[RELOAD] Triggering Restart due to file changes...")
                kill_server(server_process)
                server_process = start_server()
                continue
                
            # Case B: Server Crashed / Stopped
            status = get_process_status(server_process)
            if status == "STOPPED":
                print("[RELOAD] ⚠️ Server process ended unexpectedly. Restarting in 3s...")
                kill_server(server_process) # Clean up just in case
                time.sleep(3)
                server_process = start_server()

    except KeyboardInterrupt:
        print("\n[RELOAD] Exiting...")
        kill_server(server_process)

if __name__ == "__main__":
    main()
