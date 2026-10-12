"""Launch the local imagery operations console."""
import argparse
import threading
import webbrowser
import uvicorn

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start the STPS local web interface.")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535.")
    url = f"http://127.0.0.1:{args.port}"
    print(f"STPS operations console: {url}", flush=True)
    if not args.no_browser:
        timer = threading.Timer(2.0, lambda: webbrowser.open(url))
        timer.daemon = True
        timer.start()
    uvicorn.run("app:app", host="127.0.0.1", port=args.port, log_level="info")
