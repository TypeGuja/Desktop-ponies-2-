#!/usr/bin/env python3
"""
Desktop Ponies AI - Main entry point
Usage: python main.py --mode=ipc  (stdin/stdout JSON protocol)
       python main.py --mode=http --port=8765  (HTTP server for external use)
"""

import sys
import os

# Добавляем src_py в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server import IPCServer, HTTPServer


def main():
    mode = "ipc"
    port = 8765

    for arg in sys.argv[1:]:
        if arg.startswith("--mode="):
            mode = arg.split("=")[1]
        elif arg.startswith("--port="):
            port = int(arg.split("=")[1])

    if mode == "ipc":
        print("[PY] Starting IPC server...", file=sys.stderr)
        server = IPCServer()
        server.run()
    elif mode == "http":
        print(f"[PY] Starting HTTP server on port {port}...", file=sys.stderr)
        server = HTTPServer(port=port)
        server.run()
    else:
        print(f"Unknown mode: {mode}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()