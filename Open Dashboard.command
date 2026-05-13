#!/bin/bash
cd "$(dirname "$0")"
echo "Starting AudioFeel Dashboard..."
echo "Opening http://localhost:8080/dashboard/"
echo "Press Ctrl+C to stop."
echo ""
open "http://localhost:8080/dashboard/"
python3 -m http.server 8080
