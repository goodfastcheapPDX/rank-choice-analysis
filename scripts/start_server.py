#!/usr/bin/env python3
"""
Start the web server for the Ranked Elections Analyzer.
"""

import argparse
import socket
import sys
from pathlib import Path

import uvicorn

# Add src to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from web.main import set_database_path  # noqa: E402


def find_available_port(host, start_port, max_attempts=10):
    """Find an available port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind((host, port))
                return port
        except OSError:
            continue
    return None


def main():
    parser = argparse.ArgumentParser(description="Start the web server")
    parser.add_argument("--db", required=True, help="Path to DuckDB database file")
    parser.add_argument(
        "--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port to bind to (default: 8000)"
    )
    parser.add_argument(
        "--reload", action="store_true", help="Enable auto-reload for development"
    )
    parser.add_argument(
        "--auto-port",
        action="store_true",
        help="Automatically find available port if default is taken",
    )

    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Error: Database file not found: {db_path}")
        print("Run process_data.py first to create the database.")
        sys.exit(1)

    # Set the database path for the web application
    set_database_path(str(db_path.absolute()))

    # Find available port if auto-port is enabled
    port = args.port
    if args.auto_port:
        available_port = find_available_port(args.host, args.port)
        if available_port is None:
            print(f"Error: No available ports found starting from {args.port}")
            sys.exit(1)
        elif available_port != args.port:
            print(f"Port {args.port} is taken, using port {available_port} instead")
        port = available_port

    print("Starting Ranked Elections Analyzer web server...")
    print(f"Database: {db_path.absolute()}")
    print(f"Server: http://{args.host}:{port}")
    print("Press Ctrl+C to stop")

    uvicorn.run("web.main:app", host=args.host, port=port, reload=args.reload)


if __name__ == "__main__":
    main()
