#!/usr/bin/env python3
"""
Send MOU expiry notifications via command line.
Can be run via cron job.

Usage: python3 send_notifications.py
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, send_expiry_notifications


def main():
    """Send expiry notifications."""
    print("📧 Sending MOU expiry notifications...")
    
    with app.app_context():
        send_expiry_notifications()
    
    print("✅ Done!")


if __name__ == '__main__':
    main()
