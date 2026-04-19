import os
import json
import requests
import hashlib
from datetime import datetime

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

SEEN_FILE = "seen_lots.json"

def load_seen():
    try:
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    except:
        return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

def lot_id(lot):
    key = f"{lot.get('platform','')}-{lot.get('url','')}-{lot.get('title','')}"
    return hashlib.md5(key.encode()).hexdigest()

def fetch_flippa():
    try:
        url = "https://flippa.com/search.json?filter[listing_type]=auction,classified&filter[property_type]=website,app&sort=score&page=1"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        listings = r.json().get("data", [])[:15]
        results = []
        for item in listings:
            attr = item.get("attributes", {})
            results.append({
                "platform": "Flippa",
                "title": attr.get("name", "—"),
                "price": attr.get("asking_price", "—"),
                "monthly_revenue": attr.get("monthly_net_profit", "—"),
                "type": attr.get("property_type", "—"),
                "url": f"https://flippa.com/listings/{item.get('id', '')}"
            })
        return results
    except Exception as e:
        print(f"Flippa ошибка: {e}")
        return []

def fetch_telderi():
    try:
        url = "https://telderi.ru/api/v2/lots?order=new&per_page=15"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        listings = r.json().get("data", [])[:15]
        results = []
        for item in listings:
            results.append({
                "platform": "Telderi",
                "title": item.get("name", "—"),
                "price": item.get("price", "—"),
                "monthly_revenue": item.get("income_month", "—"),
                "type": item.get("type", "—"),
                "url": f"https://telderi.ru/lot/{item.get('id', '')}"
            })
        return results
    except Exception as e:
        print(f"Telderi ошибка: {e}")
        return []

def fetch_exchange():
    try:
        url = "https://exchangemarketplace.com/api/listings?sort=newest&limit=15"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        listings = r.json().get("listings", [])[:15]
        results = []
        for item in listings:
            results.append({
                "platform": "Exchange Marketplace",
                "title": item.get("title", "—"),
                "price": item.get("asking_price", "—"),
                "monthly_revenue": item.get("monthly_revenue", "—"),
                "type": "Shopify store",
                "url": item.get("url", "—")
            })
        return results
    except Exception as e:
        print(f"Exchange ошибка: {e}")
        return []

def evaluate_lot(lot):
    prompt = f"""Ты эксперт по покупке сайтов и приложений.
Оцени этот лот:
{json.dumps(lot, ensure_ascii=False, indent=2)}
Ответь ТОЛЬКО в формате JSON (без markdown, без пояснений):
{{
  "score": <число от 1 до 10>,
  "verdict": "хорошая сделка" | "средний вариант" | "не интересно",
  "why": "<2-3 предложения почему>",
  "risks": "<главные риски если есть>",
  "payback_months": <примерная окупаемость в месяцах или null>
}}"""
    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 400,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        text = response.json()["content"][0]["text"]
        result = json.loads(text)
        return result.get("score", 0) >= 7, result
    except Exception as e:
        print(f"Claude ошибка при оценке: {e}")
        return False, {}

def send_alert(lot, analysis):
    score = analysis.get("score", "?")
    verdict = analysis.get("verdict", "—")
    why = analysis.get("why", "—")
    risks = analysis.get("risks", "—")
    payback = analysis.get("payback_months")
    payback_str = f"{payback} мес." if payback else "неизвестно"
    stars = "⭐" * min(int(score), 10) if isinstance(score, int) else "⭐"
    text = f"""🔥 *Горячий лот!* {stars}
📌 *{lot.get('title', '—')}*
🏪 Площадка: {lot.get('platform', '—')}
💰 Цена: {lot.get('price', '—')}
📈 Доход/мес: {lot.get('monthly_revenue', '—')}
📦 Тип: {lot.get('type', '—')}
✅ *Почему интересно:*
{why}
⚠️ *Риски:* {risks}
⏱ *Окупаемость:* {payback_str}
🏆 *Оценка:* {score}/10 — {verdict}
🔗 {lot.get('url', '—')}"""
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"},
        timeout=15
    )

def main():
    seen = load_seen()
    all_lots = fetch_flippa() + fetch_telderi() + fetch_exchange()
    new_lots = [l for l in all_lots if lot_id(l) not in seen]
    good_count = 0
    for lot in new_lots:
        seen.add(lot_id(lot))
        is_good, analysis = evaluate_lot(lot)
        if is_good:
            send_alert(lot, analysis)
            good_count += 1
    save_seen(seen)
    print(f"✅ Готово! Отправлено: {good_count}")

if __name__ == "__main__":
    main()
