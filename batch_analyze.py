#!/usr/bin/env python3
"""
Batch-analyzes pending conversations and merges results into dashboard_data.json.
Uses keyword-based classification (no API calls needed).
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent
PENDING_PATH = BASE / "pending_analysis.json"
DASHBOARD_PATH = BASE / "dashboard_data.json"
STATE_PATH = BASE / "state.json"

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

# ── Topic keywords ──
TOPIC_KEYWORDS = {
    "product_inquiry": [
        'מה ההבדל', 'איזה דגם', 'ממליצים', 'מתאים לי', 'כמה דציבל', 'db', 'הנחתה',
        'מידה', 'מידות', 'גודל', 'מתאים לאוזן', 'איזה אוזניות', 'מה עדיף',
        'איך עובד', 'מה זה', 'תספרו לי', 'רוצה לשמוע', 'מעוניין לדעת',
        'איך האוזניות', 'מה ההבדל בין', 'live או zen', 'zen או live',
        'חוסם', 'מסנן', 'הפחתת רעש', 'רעש', 'שמיעה', 'הגנה על השמיעה',
        'מוסיקה', 'הופעה', 'הופעות', 'קונצרט', 'מועדון', 'dj', 'מפיק',
        'כמה עולה', 'מחיר', 'עלות', 'הנחה', 'קופון', 'מבצע',
    ],
    "purchase": [
        'רוצה לקנות', 'רוצה להזמין', 'איך מזמינים', 'הזמנתי', 'קניתי',
        'רכישה', 'לרכוש', 'להזמין', 'הזמנה', 'קנייה',
        'עגלה', 'תשלום', 'לשלם', 'כרטיס אשראי', 'אשראי',
        'bit', 'ביט', 'paypal', 'פייפאל',
    ],
    "shipping": [
        'משלוח', 'מתי מגיע', 'זמן הגעה', 'שליח', 'דואר', 'חבילה',
        'הגיע', 'לא הגיע', 'מספר מעקב', 'tracking', 'מעקב',
        'נקודת איסוף', 'box', 'בוקס', 'סניף דואר', 'שליחות',
        'כתובת', 'למשלוח', 'הזמנה שלי', 'איפה ההזמנה',
    ],
    "complaint": [
        'לא עובד', 'לא מרוצה', 'לא מרגיש', 'מאוכזב', 'מאכזב', 'מאכזבת',
        'נשבר', 'התפרק', 'פגום', 'תקלה', 'בעיה', 'לא טוב',
        'כואב', 'לא נוח', 'לחץ', 'מפריע', 'נופל', 'נופלים',
        'להחזיר', 'החזר', 'זיכוי', 'refund', 'return',
        'רוצה להחזיר', 'לא מתאים', 'אחזיר',
    ],
    "support": [
        'עזרה', 'תמיכה', 'שאלה', 'בבקשה', 'help',
        'איך', 'למה', 'מה עושים', 'אפשר',
        'אחריות', 'תיקון', 'החלפה',
    ],
    "greeting": [
        'שלום', 'היי', 'הי', 'אהלן', 'מה קורה', 'hello', 'hi',
    ],
}

SENTIMENT_NEGATIVE = [
    'לא מרוצה', 'מאוכזב', 'מאכזב', 'מאכזבת', 'גרוע', 'נורא', 'בעיה',
    'לא עובד', 'לא מרגיש', 'לא עוזר', 'להחזיר', 'החזר', 'זיכוי',
    'כואב', 'נשבר', 'התפרק', 'פגום', 'תקלה', 'לא טוב',
    'עצבני', 'כעס', 'frustrated', 'angry', 'terrible', 'bad',
    'לא מתאים', 'חרא', 'שטויות', 'עלבון',
]

SENTIMENT_POSITIVE = [
    'תודה', 'מעולה', 'נהדר', 'אהבתי', 'מרוצה', 'שמח', 'מושלם',
    'ממליץ', 'ממליצה', 'מדהים', 'אלוף', 'הכי טוב', 'super', 'amazing',
    'fantastic', 'great', 'love', 'perfect', 'thank',
    'מצוין', 'טוב מאוד', 'שירות מעולה', '❤️', '🙏', '💪', 'אחלה',
    'ברכות', 'יופי', 'הכל טוב', 'הסתדר', 'נפלא',
]

RESOLUTION_RESOLVED = [
    'תודה', 'הסתדר', 'מעולה', 'הבנתי', 'נהדר', 'יופי', 'סבבה',
    'אוקי', 'אוקיי', 'ok', 'okay', 'thanks', 'thank you',
    'תודה רבה', 'תודה לכם', 'מושלם', 'הזמנתי', 'קניתי',
    'בסדר גמור', 'בסדר', 'נפלא',
]

def get_customer_text(conv):
    return " ".join(
        m.get("text", "") for m in conv.get("messages", [])
        if m.get("direction") == "inbound"
    ).lower()

def get_all_text(conv):
    return " ".join(
        m.get("text", "") for m in conv.get("messages", [])
    ).lower()

def get_last_customer_msgs(conv, n=3):
    inbound = [m for m in conv.get("messages", []) if m.get("direction") == "inbound"]
    return " ".join(m.get("text", "") for m in inbound[-n:]).lower()

def classify_topic(conv):
    text = get_customer_text(conv)
    all_text = get_all_text(conv)

    scores = {}
    for topic, keywords in TOPIC_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text or kw in all_text)
        if score > 0:
            scores[topic] = score

    if not scores:
        if conv.get("message_count", 0) <= 2:
            return "greeting"
        return "general"

    # Prioritize complaint over others
    if "complaint" in scores and scores["complaint"] >= 2:
        return "complaint"

    return max(scores, key=scores.get)

def classify_sentiment(conv):
    text = get_customer_text(conv)
    last_msgs = get_last_customer_msgs(conv)

    neg_score = sum(1 for kw in SENTIMENT_NEGATIVE if kw in text)
    pos_score = sum(1 for kw in SENTIMENT_POSITIVE if kw in text)

    # Give extra weight to last messages
    last_pos = sum(1 for kw in SENTIMENT_POSITIVE if kw in last_msgs)
    last_neg = sum(1 for kw in SENTIMENT_NEGATIVE if kw in last_msgs)

    pos_score += last_pos
    neg_score += last_neg

    if neg_score > pos_score and neg_score >= 2:
        return "negative"
    elif pos_score > neg_score:
        return "positive"
    elif neg_score > 0:
        return "negative"
    return "neutral"

def classify_resolution(conv):
    last_msgs = get_last_customer_msgs(conv, n=2)
    all_text = get_all_text(conv)

    if any(kw in last_msgs for kw in RESOLUTION_RESOLVED):
        return "resolved"

    if conv.get("message_count", 0) <= 1:
        return "no_response"

    # Check if bot/agent responded
    outbound = [m for m in conv.get("messages", []) if m.get("direction") == "outbound" and m.get("text", "").strip()]
    if not outbound:
        return "no_response"

    return "pending"

def estimate_lead_score(conv):
    text = get_customer_text(conv)
    score = 1

    purchase_signals = ['רוצה לקנות', 'רוצה להזמין', 'איך מזמינים', 'כמה עולה', 'מחיר',
                        'הנחה', 'קופון', 'לרכוש', 'עגלה', 'תשלום', 'bit', 'ביט']
    high_intent = ['הזמנתי', 'קניתי', 'שילמתי', 'ביצעתי הזמנה']

    if any(kw in text for kw in high_intent):
        score = 5
    elif any(kw in text for kw in purchase_signals):
        score = 4
    elif conv.get("message_count", 0) >= 6:
        score = 3
    elif conv.get("message_count", 0) >= 3:
        score = 2

    return score

def generate_summary(conv):
    name = conv.get("contact_name", "Customer")
    platform = conv.get("platform", "")
    msgs = conv.get("messages", [])

    customer_msgs = [m.get("text", "") for m in msgs if m.get("direction") == "inbound" and m.get("text", "").strip()]

    if not customer_msgs:
        return f"{name} initiated contact on {platform}."

    first_msg = customer_msgs[0][:100]
    return f"{name} on {platform}: {first_msg}"

def detect_key_issues(conv):
    text = get_customer_text(conv)
    issues = []

    issue_map = {
        "Product selection help": ['מתאים', 'איזה דגם', 'מה ההבדל', 'ממליצים'],
        "Price inquiry": ['כמה עולה', 'מחיר', 'הנחה', 'קופון'],
        "Shipping question": ['משלוח', 'מתי מגיע', 'חבילה', 'כתובת'],
        "Return/refund request": ['להחזיר', 'החזר', 'זיכוי'],
        "Product quality issue": ['לא עובד', 'נשבר', 'לא מרגיש הבדל'],
        "Comfort issue": ['כואב', 'לא נוח', 'לחץ', 'נופל'],
        "Noise reduction question": ['דציבל', 'db', 'חוסם', 'מסנן', 'רעש'],
        "Store/physical location": ['חנות', 'פיזי', 'נקודת מכירה', 'להגיע'],
    }

    for issue, keywords in issue_map.items():
        if any(kw in text for kw in keywords):
            issues.append(issue)

    return issues if issues else ["General inquiry"]

def classify_bot_vs_human(conv):
    if conv.get("has_human_agent"):
        bot_msgs = any(m.get("sender") == "Bot" for m in conv.get("messages", []))
        if bot_msgs:
            return "both"
        return "human_only"
    return "bot_only"

def detect_escalation(conv):
    topic = classify_topic(conv)
    sentiment = classify_sentiment(conv)

    if topic == "complaint" and sentiment == "negative":
        return True

    text = get_customer_text(conv)
    escalation_kw = ['מנהל', 'תלונה', 'אתבע', 'עורך דין', 'לא מקובל', 'חוצפה']
    if any(kw in text for kw in escalation_kw):
        return True

    return False


def analyze_conversation(conv):
    topic = classify_topic(conv)
    sentiment = classify_sentiment(conv)
    resolution = classify_resolution(conv)
    lead_score = estimate_lead_score(conv)
    bot_human = classify_bot_vs_human(conv)
    escalation = detect_escalation(conv)
    summary = generate_summary(conv)
    key_issues = detect_key_issues(conv)

    conv["topic"] = topic
    conv["sentiment"] = sentiment
    conv["resolution"] = resolution
    conv["lead_score"] = lead_score
    conv["bot_vs_human"] = bot_human
    conv["escalation_needed"] = escalation
    conv["summary"] = summary
    conv["key_issues"] = key_issues

    return conv


def main():
    pending = load_json(PENDING_PATH, [])
    if not pending:
        print("No pending conversations to analyze.")
        return

    dashboard = load_json(DASHBOARD_PATH, {"conversations": [], "last_updated": ""})
    state = load_json(STATE_PATH)

    existing_ids = {c["conversation_id"] for c in dashboard["conversations"]}

    analyzed = []
    for conv in pending:
        result = analyze_conversation(conv)
        analyzed.append(result)

    # Merge: update existing, add new
    updated_count = 0
    new_count = 0
    conv_map = {c["conversation_id"]: c for c in dashboard["conversations"]}

    for conv in analyzed:
        cid = conv["conversation_id"]
        if cid in conv_map:
            conv_map[cid] = conv
            updated_count += 1
        else:
            conv_map[cid] = conv
            new_count += 1

    dashboard["conversations"] = list(conv_map.values())
    dashboard["last_updated"] = datetime.now(timezone.utc).isoformat()

    # Update state
    for conv in analyzed:
        state[conv["conversation_id"]] = conv["message_count"]

    save_json(DASHBOARD_PATH, dashboard)
    save_json(STATE_PATH, state)

    # Stats
    from collections import Counter
    topics = Counter(c["topic"] for c in analyzed)
    sentiments = Counter(c["sentiment"] for c in analyzed)

    print(f"Analyzed {len(analyzed)} conversations ({new_count} new, {updated_count} updated)")
    print(f"Total in dashboard: {len(dashboard['conversations'])}")
    print(f"Topics: {dict(topics)}")
    print(f"Sentiments: {dict(sentiments)}")

if __name__ == "__main__":
    main()
