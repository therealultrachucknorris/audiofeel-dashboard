#!/bin/bash
# Downloads the latest chatbot logs from Google Sheets as CSV
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
curl -sL -o "$SCRIPT_DIR/raw/latest.csv" \
  "https://docs.google.com/spreadsheets/d/1A382PL9lJKenqgILqsh-DQaxNyUB54JJKReHL_uM6uc/export?format=csv&gid=1690283584"
echo "Downloaded $(wc -l < "$SCRIPT_DIR/raw/latest.csv") lines to raw/latest.csv"
