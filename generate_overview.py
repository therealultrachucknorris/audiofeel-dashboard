#!/usr/bin/env python3
"""
Generates the AF Chat Overview report files from dashboard_data.json.
Outputs markdown files to "AF Chat Overview/" folder.
"""

import json
import os
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent
DATA_PATH = BASE / "dashboard_data.json"
OUT_DIR = BASE / "AF Chat Overview"
OUT_DIR.mkdir(exist_ok=True)

with open(DATA_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

convos = data["conversations"]
total = len(convos)
dates = sorted(set(c.get("date", "") for c in convos if c.get("date")))
date_range = f"{dates[0]} to {dates[-1]}" if dates else "N/A"

# ── Helper: group by month ──
def month_key(d):
    return d[:7] if d else "unknown"

months = sorted(set(month_key(c.get("date", "")) for c in convos))

# ── Compute all stats ──
platforms = Counter(c.get("platform", "unknown") for c in convos)
topics = Counter(c.get("topic", "unknown") for c in convos)
sentiments = Counter(c.get("sentiment", "unknown") for c in convos)
resolutions = Counter(c.get("resolution", "unknown") for c in convos)
bot_human = Counter(c.get("bot_vs_human", "unknown") for c in convos)
daily = Counter(c.get("date", "") for c in convos)

escalations = [c for c in convos if c.get("escalation_needed")]
lead_scores = [c.get("lead_score", 0) for c in convos if c.get("lead_score")]
avg_lead = round(sum(lead_scores) / len(lead_scores), 1) if lead_scores else 0

# Per-month stats
monthly_stats = {}
for m in months:
    m_convos = [c for c in convos if month_key(c.get("date", "")) == m]
    m_total = len(m_convos)
    m_neg = sum(1 for c in m_convos if c.get("sentiment") == "negative")
    m_pos = sum(1 for c in m_convos if c.get("sentiment") == "positive")
    m_resolved = sum(1 for c in m_convos if c.get("resolution") == "resolved")
    m_esc = sum(1 for c in m_convos if c.get("escalation_needed"))
    monthly_stats[m] = {
        "total": m_total,
        "negative": m_neg,
        "positive": m_pos,
        "resolved": m_resolved,
        "escalations": m_esc,
        "resolution_rate": round(m_resolved / m_total * 100) if m_total else 0,
    }

# Per-platform stats
platform_stats = {}
for p in platforms:
    p_convos = [c for c in convos if c.get("platform") == p]
    p_total = len(p_convos)
    p_neg = sum(1 for c in p_convos if c.get("sentiment") == "negative")
    p_pos = sum(1 for c in p_convos if c.get("sentiment") == "positive")
    p_resolved = sum(1 for c in p_convos if c.get("resolution") == "resolved")
    p_avg_msgs = round(sum(c.get("message_count", 0) for c in p_convos) / p_total, 1) if p_total else 0
    platform_stats[p] = {
        "total": p_total,
        "negative": p_neg,
        "positive": p_pos,
        "resolved": p_resolved,
        "resolution_rate": round(p_resolved / p_total * 100) if p_total else 0,
        "neg_rate": round(p_neg / p_total * 100) if p_total else 0,
        "avg_msgs": p_avg_msgs,
    }

# ── Return analysis (careful) ──
false_positives = ['אחזור אליך', 'אחזור לארץ', 'נחזור אליך', 'נחזור אלייך', 'חזרה לארץ', 'אחזור', 'נחזור', 'תחזור', 'חזור', 'חוזר אליך', 'חוזרים אליך']
actual_return_kw = ['רוצה להחזיר', 'אחזיר', 'להחזיר את', 'מעוניינת להחזיר', 'רוצה החזר', 'אשמח להחזיר', 'חושבת להחזיר', 'לבצע החזר', 'לקבל החזר', 'כסף בחזרה', 'תורידו לי זיכוי', 'אשמח להגיע להחזיר', 'לא מרגיש שום הבדל', 'לצערי המוצר', 'מאכזבת', 'מה קורה עם ההחזר', 'איך מחזירים']

actual_returns = []
policy_asks = []
bot_pitch_kw = ['30 ימי נסיון', 'זיכוי כספי מלא אם לא', 'ימי נסיון חינם']
asking_kw = ['איך עובדת ההחזרה', 'מדיניות ההחזרה', 'אפשר להחזיר', 'איך מבצעים החזרת']

for c in convos:
    msgs = c.get("messages", [])
    customer_text = " ".join(m.get("text", "") for m in msgs if m.get("direction") == "inbound").lower()
    all_text = " ".join(m.get("text", "") for m in msgs).lower()
    bot_text = " ".join(m.get("text", "") for m in msgs if m.get("direction") == "outbound").lower()

    cleaned = all_text
    for fp in false_positives:
        cleaned = cleaned.replace(fp, "")

    if not any(w in cleaned for w in ['החזר', 'להחזיר', 'זיכוי', 'refund', 'return', 'החזרה', 'מחזירים']):
        continue

    if any(w in customer_text for w in actual_return_kw):
        actual_returns.append(c)
    elif any(w in customer_text for w in asking_kw) or any(w in all_text for w in asking_kw):
        policy_asks.append(c)

# Dedupe returns by phone/name
seen = set()
unique_returns = []
for c in actual_returns:
    key = c.get("contact_phone", "") or c.get("contact_name", "")
    if key not in seen:
        seen.add(key)
        unique_returns.append(c)

# ── Product mentions ──
products = {
    'Live': ['live', 'לייב'],
    'Zen': ['zen', 'זן'],
    'Chain': ['chain', 'שרשרת', 'צ׳יין', "צ'יין"],
}
product_stats = {}
for prod, kws in products.items():
    mentions = 0
    returns = 0
    negative = 0
    for c in convos:
        full = " ".join(m.get("text", "") for m in c.get("messages", [])).lower() + " " + c.get("summary", "").lower()
        if any(k in full for k in kws):
            mentions += 1
            if c in actual_returns:
                returns += 1
            if c.get("sentiment") == "negative":
                negative += 1
    product_stats[prod] = {"mentions": mentions, "returns": returns, "negative": negative}

# ── Complaint reasons ──
complaint_categories = {
    'איכות (לא חוסם / לא מרגיש הבדל)': ['לא מרגיש', 'לא עובד', 'לא עוזר', 'לא חוסם', 'איכות', 'נשבר', 'התפרק'],
    'משלוח (לא הגיע / איחור)': ['לא הגיע', 'לא קיבלתי', 'איחור', 'חבילה לא', 'לא נשלח'],
    'נוחות (כאב / נופל)': ['כואב', 'לא נוח', 'נופל', 'נופלים', 'לחץ', 'מפריע'],
    'מוצר שגוי (צבע / דגם לא נכון)': ['לא נכון', 'שגוי', 'טעות', 'צבע אחר', 'לא מה שהזמנתי'],
    'מחיר / עלות': ['יקר', 'מחיר', 'הנחה'],
}
complaint_counts = Counter()
neg_convos = [c for c in convos if c.get("sentiment") == "negative" or c.get("topic") == "complaint"]
for c in neg_convos:
    customer_text = " ".join(m.get("text", "") for m in c.get("messages", []) if m.get("direction") == "inbound").lower()
    for reason, kws in complaint_categories.items():
        if any(k in customer_text for k in kws):
            complaint_counts[reason] += 1

# ── Top questions ──
inquiry_categories = {
    'איזה דגם מתאים לי (Live vs Zen)': ['מתאים', 'ממליצים', 'איזה דגם', 'מה ההבדל', 'ההבדל בין'],
    'כמה dB מוריד / הנחתת רעש': ['דציבל', 'db', 'הנחתה', 'חוסם', 'רעש', 'הורדת'],
    'מידות / התאמה לאוזן': ['מידה', 'מידות', 'אוזן', 'גודל', 'קטן', 'גדול'],
    'מחיר / הנחות / קופון': ['מחיר', 'עולה', 'הנחה', 'קופון', 'מבצע', 'כמה עולה'],
    'זמינות / מלאי': ['מלאי', 'זמין', 'אזל', 'יש לכם', 'מתי יחזור'],
    'משלוח / זמן הגעה': ['משלוח', 'מתי מגיע', 'זמן הגעה', 'שליח', 'דואר'],
}
inquiry_counts = Counter()
for c in convos:
    if c.get("topic") != "product_inquiry":
        continue
    customer_text = " ".join(m.get("text", "") for m in c.get("messages", []) if m.get("direction") == "inbound").lower()
    for topic, kws in inquiry_categories.items():
        if any(k in customer_text for k in kws):
            inquiry_counts[topic] += 1


# ═══════════════════════════════════════
# WRITE REPORT FILES
# ═══════════════════════════════════════

now = datetime.now().strftime("%Y-%m-%d %H:%M")

# ── 1. SUMMARY.md ──
with open(OUT_DIR / "SUMMARY.md", "w", encoding="utf-8") as f:
    f.write(f"""# AudioFeel Chatbot — Overview Summary
**Generated:** {now}
**Period:** {date_range}
**Total Conversations:** {total}

---

## Key Metrics

| Metric | Value |
|---|---|
| Total Conversations | **{total}** |
| Resolution Rate | **{round(resolutions.get('resolved', 0) / total * 100)}%** ({resolutions.get('resolved', 0)}/{total}) |
| Avg Lead Score | **{avg_lead}** / 5 |
| Escalations Needed | **{len(escalations)}** ({round(len(escalations) / total * 100, 1)}%) |
| Negative Sentiment | **{sentiments.get('negative', 0)}** ({round(sentiments.get('negative', 0) / total * 100, 1)}%) |
| Positive Sentiment | **{sentiments.get('positive', 0)}** ({round(sentiments.get('positive', 0) / total * 100, 1)}%) |

## Platform Breakdown

| Platform | Conversations | Resolution | Negative | Positive | Avg Messages |
|---|---|---|---|---|---|
""")
    for p in ['WHATSAPP', 'INSTAGRAM', 'LIVE_CHAT']:
        s = platform_stats.get(p, {})
        f.write(f"| {p} | {s.get('total', 0)} | {s.get('resolution_rate', 0)}% | {s.get('neg_rate', 0)}% | {round(s.get('positive', 0) / max(1, s.get('total', 1)) * 100)}% | {s.get('avg_msgs', 0)} |\n")

    f.write(f"""
## Topic Distribution

| Topic | Count | % |
|---|---|---|
""")
    for t, count in topics.most_common():
        f.write(f"| {t} | {count} | {round(count / total * 100, 1)}% |\n")

    f.write(f"""
## Bot vs Human

| Handler | Count | % |
|---|---|---|
""")
    for b, count in bot_human.most_common():
        f.write(f"| {b} | {count} | {round(count / total * 100, 1)}% |\n")

    f.write(f"""
## Monthly Trend

| Month | Conversations | Resolution | Negative | Escalations |
|---|---|---|---|---|
""")
    for m in months:
        s = monthly_stats[m]
        f.write(f"| {m} | {s['total']} | {s['resolution_rate']}% | {s['negative']} | {s['escalations']} |\n")


# ── 2. RETURNS.md ──
with open(OUT_DIR / "RETURNS.md", "w", encoding="utf-8") as f:
    f.write(f"""# AudioFeel — Returns & Refunds Analysis
**Generated:** {now}
**Period:** {date_range}

---

## Summary

| Category | Count | % of Total ({total}) |
|---|---|---|
| **Actual returns (customer requested/did)** | **{len(unique_returns)}** unique customers | **{round(len(unique_returns) / total * 100, 1)}%** |
| Asked about return policy (pre-purchase) | {len(policy_asks)} | {round(len(policy_asks) / total * 100, 1)}% |

## Actual Return Requests — Detail

| Date | Customer | Platform | Snippet |
|---|---|---|---|
""")
    for c in sorted(unique_returns, key=lambda x: x.get("date", ""), reverse=True):
        snippet = ""
        for m in c.get("messages", []):
            if m.get("direction") == "inbound":
                t = m.get("text", "").lower()
                if any(w in t for w in actual_return_kw):
                    snippet = m.get("text", "")[:80].replace("|", "/").replace("\n", " ")
                    break
        f.write(f"| {c.get('date', '')} | {c.get('contact_name', '?')} | {c.get('platform', '')} | {snippet} |\n")

    f.write(f"""
## Returns by Product

| Product | Total Mentions | Linked to Returns | Negative Sentiment |
|---|---|---|---|
""")
    for prod in ['Live', 'Zen', 'Chain']:
        s = product_stats[prod]
        f.write(f"| {prod} | {s['mentions']} | {s['returns']} | {s['negative']} |\n")

    f.write(f"""
## Monthly Return Trend

| Month | Return Requests |
|---|---|
""")
    monthly_returns = Counter()
    for c in unique_returns:
        monthly_returns[month_key(c.get("date", ""))] += 1
    for m in months:
        f.write(f"| {m} | {monthly_returns.get(m, 0)} |\n")


# ── 3. COMPLAINTS.md ──
with open(OUT_DIR / "COMPLAINTS.md", "w", encoding="utf-8") as f:
    f.write(f"""# AudioFeel — Complaint Analysis
**Generated:** {now}
**Period:** {date_range}
**Total Negative Conversations:** {sentiments.get('negative', 0)} ({round(sentiments.get('negative', 0) / total * 100, 1)}%)

---

## Top Complaint Reasons (from customer messages)

| Reason | Count |
|---|---|
""")
    for reason, count in complaint_counts.most_common():
        f.write(f"| {reason} | {count} |\n")

    f.write(f"""
## Complaint Breakdown by Platform

| Platform | Negative Count | Negative % |
|---|---|---|
""")
    for p in ['WHATSAPP', 'INSTAGRAM', 'LIVE_CHAT']:
        s = platform_stats.get(p, {})
        f.write(f"| {p} | {s.get('negative', 0)} | {s.get('neg_rate', 0)}% |\n")

    f.write(f"""
## Escalations Needing Attention

| Date | Customer | Platform | Topic | Summary |
|---|---|---|---|---|
""")
    for c in sorted(escalations, key=lambda x: x.get("date", ""), reverse=True)[:30]:
        summary = (c.get("summary", "") or "")[:80].replace("|", "/").replace("\n", " ")
        f.write(f"| {c.get('date', '')} | {c.get('contact_name', '?')} | {c.get('platform', '')} | {c.get('topic', '')} | {summary} |\n")


# ── 4. INSIGHTS.md ──
with open(OUT_DIR / "INSIGHTS.md", "w", encoding="utf-8") as f:
    f.write(f"""# AudioFeel — Key Insights & Recommendations
**Generated:** {now}
**Period:** {date_range}

---

## Top Customer Questions (Product Inquiries)

| Question Theme | Count |
|---|---|
""")
    for q, count in inquiry_counts.most_common():
        f.write(f"| {q} | {count} |\n")

    f.write(f"""
## Product Performance

| Product | Mentions | Return Rate | Negative Rate |
|---|---|---|---|
""")
    for prod in ['Live', 'Zen', 'Chain']:
        s = product_stats[prod]
        ret_rate = round(s['returns'] / max(1, s['mentions']) * 100, 1)
        neg_rate = round(s['negative'] / max(1, s['mentions']) * 100, 1)
        f.write(f"| {prod} | {s['mentions']} | {ret_rate}% | {neg_rate}% |\n")

    f.write(f"""
## Platform Performance Comparison

| Metric | WhatsApp | Instagram | Live Chat |
|---|---|---|---|
""")
    wa = platform_stats.get('WHATSAPP', {})
    ig = platform_stats.get('INSTAGRAM', {})
    lc = platform_stats.get('LIVE_CHAT', {})
    f.write(f"| Volume | {wa.get('total', 0)} | {ig.get('total', 0)} | {lc.get('total', 0)} |\n")
    f.write(f"| Resolution Rate | {wa.get('resolution_rate', 0)}% | {ig.get('resolution_rate', 0)}% | {lc.get('resolution_rate', 0)}% |\n")
    f.write(f"| Negative Rate | {wa.get('neg_rate', 0)}% | {ig.get('neg_rate', 0)}% | {lc.get('neg_rate', 0)}% |\n")
    f.write(f"| Avg Messages | {wa.get('avg_msgs', 0)} | {ig.get('avg_msgs', 0)} | {lc.get('avg_msgs', 0)} |\n")

    # Lead distribution
    lead_dist = Counter(c.get("lead_score", 0) for c in convos if c.get("lead_score"))
    high_leads = sum(1 for c in convos if c.get("lead_score", 0) >= 4)
    f.write(f"""
## Lead Score Distribution

| Score | Count |
|---|---|
""")
    for score in sorted(lead_dist.keys()):
        f.write(f"| {score}/5 | {lead_dist[score]} |\n")
    f.write(f"| **Hot leads (4-5)** | **{high_leads}** |\n")

    f.write(f"""
## Actionable Recommendations

1. **Live Chat needs attention** — {lc.get('neg_rate', 0)}% negative sentiment and only {lc.get('resolution_rate', 0)}% resolution rate. This is significantly worse than WhatsApp ({wa.get('resolution_rate', 0)}% resolution). Investigate response times and agent availability.

2. **Zen vs Live confusion** — {inquiry_counts.get('איזה דגם מתאים לי (Live vs Zen)', 0)} customers asked "which model fits me?". A comparison table on the website would reduce these inquiries.

3. **dB/noise reduction is top question** — {inquiry_counts.get('כמה dB מוריד / הנחתת רעש', 0)} conversations about noise reduction levels. Make this more prominent in product pages.

4. **Return rate is low** — Only {len(unique_returns)} unique customers requested returns ({round(len(unique_returns) / total * 100, 1)}%). Main reasons: unmet expectations about filtering vs blocking.

5. **Bot escalation rate is high** — {round(bot_human.get('both', 0) / total * 100)}% of conversations require human intervention. Review bot flows for common handoff points.

6. **{high_leads} hot leads** — {round(high_leads / total * 100, 1)}% of conversations show high purchase intent (lead score 4-5). These should be targeted for remarketing.
""")

print(f"Generated reports in {OUT_DIR}/")
print(f"  - SUMMARY.md")
print(f"  - RETURNS.md")
print(f"  - COMPLAINTS.md")
print(f"  - INSIGHTS.md")
