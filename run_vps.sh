#!/bin/bash
# Run the HLTV scraper on a VPS without a display.
# Uses xvfb to create a virtual framebuffer so Chrome runs
# non-headless (best Cloudflare bypass) without needing a screen.
#
# Install dependencies (Ubuntu/Debian):
#   sudo apt-get install -y xvfb google-chrome-stable
#   pip install -r requirements.txt
#
# Usage:
#   ./run_vps.sh                     # Sync all events
#   ./run_vps.sh --event 8504        # Sync single event
#   ./run_vps.sh --limit 5           # Sync 5 events

set -e

# Check if xvfb-run is available
if ! command -v xvfb-run &> /dev/null; then
    echo "ERROR: xvfb-run not found. Install with: sudo apt-get install -y xvfb"
    exit 1
fi

# Run with virtual display, non-headless for Cloudflare bypass
exec xvfb-run --auto-servernum --server-args="-screen 0 1920x1080x24" \
    python3 sync_all.py --show "$@"
