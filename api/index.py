"""
Vercel Serverless Function entrypoint for FastAPI application.
Exposes the ASGI app instance for @vercel/python runtime.
"""
import os
import sys
from pathlib import Path

# Add project root to sys.path so modules (server, config, etc.) can be imported on Vercel
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Ensure VERCEL environment marker is active for serverless fallbacks
os.environ.setdefault("VERCEL", "1")

# Import the FastAPI application
from server import app
