#!/usr/bin/env python3
"""
Start the web server for the Ranked Elections Analyzer.
"""

import argparse
import sys
from pathlib import Path

import uvicorn

# Add src to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from web.main import app, set_database_path


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

    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Error: Database file not found: {db_path}")
        print("Run process_data.py first to create the database.")
        sys.exit(1)

    # Set the database path for the web application
    set_database_path(str(db_path.absolute()))

    print(f"Starting Ranked Elections Analyzer web server...")
    print(f"Database: {db_path.absolute()}")
    print(f"Server: http://{args.host}:{args.port}")
    print(f"Press Ctrl+C to stop")

    uvicorn.run("web.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
