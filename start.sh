#!/bin/bash
# Start the Flask job board
cd "$(dirname "$0")"
exec python3 -m app
