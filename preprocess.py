#!/usr/bin/env python3
"""
Preprocesses the AudioFeel chatbot CSV logs.
Groups messages into conversations, detects new/updated ones,
and writes pending_analysis.json for Claude Code to analyze.
"""

import csv
import json
import os
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).parent
CSV_PATH = BASE_DIR / "raw" / "latest.csv"
STATE_PATH = BASE_DIR / "state.json"
PENDING_PATH = BASE_DIR / "pending_analysis.json"
DASHBOARD_DATA_PATH = BASE_DIR / "dashboard_data.json"


def load_json(path, default=None):
    if default is None:
        default = {}
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def parse_csv():
    """Read CSV and group messages by Conversation_ID."""
    conversations = defaultdict(lambda: {
        "conversation_id": "",
        "date": "",
        "platform": "",
        "contact_name": "",
        "contact_phone": "",
        "bot_name": "",
        "messages": [],
        "message_count": 0,
        "has_human_agent": False,
    })

    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = row.get("Conversation_ID", "").strip()
            if not cid:
                continue

            conv = conversations[cid]
            conv["conversation_id"] = cid
            # Use earliest date for the conversation
            if not conv["date"] or row.get("Date", "") < conv["date"]:
                conv["date"] = row.get("Date", "")
            conv["platform"] = row.get("Platform", "")
            conv["contact_name"] = row.get("Contact_Name", "") or conv["contact_name"]
            conv["contact_phone"] = row.get("Contact_Phone", "") or conv["contact_phone"]
            conv["bot_name"] = row.get("Bot_Name", "") or conv["bot_name"]

            sent_by = row.get("Sent_By", "").strip()
            # Detect human agent (not "Bot" and not empty = human agent name)
            if sent_by and sent_by != "Bot":
                conv["has_human_agent"] = True

            msg = {
                "time": row.get("Time_UTC", ""),
                "direction": row.get("Direction", ""),
                "sender": sent_by or ("customer" if row.get("Direction") == "inbound" else "system"),
                "text": row.get("Message", ""),
                "type": row.get("Message_Type", ""),
                "event_type": row.get("Event_Type", ""),
            }
            conv["messages"].append(msg)
            conv["message_count"] = len(conv["messages"])

    # Sort messages within each conversation by time
    for conv in conversations.values():
        conv["messages"].sort(key=lambda m: m["time"])

    return dict(conversations)


def detect_pending(conversations, state):
    """Find conversations that are new or have new messages."""
    pending = []
    for cid, conv in conversations.items():
        prev_count = state.get(cid, 0)
        if conv["message_count"] > prev_count:
            pending.append(conv)
    # Sort by date descending (newest first)
    pending.sort(key=lambda c: c["date"], reverse=True)
    return pending


def main():
    if not CSV_PATH.exists():
        print("No CSV found. Run fetch.sh first.")
        return

    print(f"Reading {CSV_PATH}...")
    conversations = parse_csv()
    print(f"Found {len(conversations)} total conversations")

    state = load_json(STATE_PATH)
    pending = detect_pending(conversations, state)
    print(f"Pending analysis: {len(pending)} conversations (new or updated)")

    # Write pending conversations for Claude to analyze
    save_json(PENDING_PATH, pending)
    print(f"Wrote {PENDING_PATH}")

    # Also write a summary for quick reference
    platforms = defaultdict(int)
    for conv in conversations.values():
        platforms[conv["platform"]] += 1
    print(f"Platforms: {dict(platforms)}")
    print(f"Date range: {min(c['date'] for c in conversations.values())} to {max(c['date'] for c in conversations.values())}")


if __name__ == "__main__":
    main()
