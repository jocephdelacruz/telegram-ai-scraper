#!/usr/bin/env python3
"""
Telegram AI Scraper - Entry Point
This script provides easy access to the main application from the root directory
"""

import sys
import os

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Import and run the main application
from src.core.main import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())