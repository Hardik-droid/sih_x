"""Single-command local launch; all evidence remains under TRACE_DATA or ./data."""
import argparse
import socket
import threading
import time
import webbrowser

import uvicorn

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trace forensic workstation")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Choose a port between 1024 and 65535")
    url = f"http://127.0.0.1:{args.port}"
    with socket.socket() as check:
        occupied = check.connect_ex(("127.0.0.1", args.port)) == 0
    if occupied:
        parser.error(f"Port {args.port} is in use. Open {url} if Trace is already running, or choose --port 8001.")
    if not args.no_browser:
        def launch_browser():
            import urllib.request
            for _ in range(40):
                try:
                    urllib.request.urlopen(url + "/api/session", timeout=1)
                    webbrowser.open(url)
                    return
                except OSError:
                    time.sleep(0.25)
        threading.Thread(target=launch_browser, daemon=True).start()
    print(f"Trace forensic workspace: {url}")
    uvicorn.run("app:app", host="127.0.0.1", port=args.port, log_level="info")
