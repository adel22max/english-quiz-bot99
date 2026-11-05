#!/usr/bin/env python3
"""
بوت تليجرام ينشر كل يوم أسئلة إنكليزي (Quiz) في قناة.

التشغيل:
    python3 bot.py                  -> يبقى شغال وينشر كل يوم بالوقت المحدد
    python3 bot.py --once           -> ينشر سؤال واحد فوراً (للتجربة أو للـ cron)
    python3 bot.py --once --count 3 -> ينشر 3 أسئلة فوراً (مختلفة عن بعض)

الإعدادات (متغيرات بيئة):
    BOT_TOKEN   توكن البوت من BotFather            (مطلوب)
    CHANNEL_ID  @username للقناة أو رقمها -100...   (مطلوب)
    POST_TIME   وقت النشر اليومي HH:MM              (افتراضي 10:00)
    POST_COUNT  عدد الأسئلة بكل مرة نشر             (افتراضي 1)
    TZ_NAME     المنطقة الزمنية                     (افتراضي Asia/Damascus)
"""

import json
import os
import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

BASE_DIR = Path(__file__).parent
QUESTIONS_FILE = BASE_DIR / "questions.json"
STATE_FILE = BASE_DIR / "state.json"

TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHANNEL = os.environ.get("CHANNEL_ID", "").strip()
POST_TIME = os.environ.get("POST_TIME", "10:00").strip()
POST_COUNT = int(os.environ.get("POST_COUNT", "1"))
TZ = ZoneInfo(os.environ.get("TZ_NAME", "Asia/Damascus"))


def load_questions():
    data = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))
    for i, q in enumerate(data):
        if len(q["options"]) != 3:
            raise ValueError(f"السؤال رقم {i + 1} لازم يكون فيه 3 خيارات بالضبط")
        if len(q["q"]) > 300:
            raise ValueError(f"السؤال رقم {i + 1} أطول من 300 حرف")
        if any(len(o) > 100 for o in q["options"]):
            raise ValueError(f"أحد خيارات السؤال رقم {i + 1} أطول من 100 حرف")
        if len(q.get("explanation", "")) > 200:
            raise ValueError(f"شرح السؤال رقم {i + 1} أطول من 200 حرف")
    return data


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"used": []}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state), encoding="utf-8")


def post_quiz():
    questions = load_questions()
    state = load_state()

    used = set(state.get("used", []))
    remaining = [i for i in range(len(questions)) if i not in used]
    if not remaining:  # خلصت كل الأسئلة، نبدأ من جديد
        used = set()
        remaining = list(range(len(questions)))

    idx = random.choice(remaining)
    q = questions[idx]

    # أول خيار بالملف هو الصحيح، منخلط الترتيب حتى ما يكون الجواب دايماً بنفس المكان
    options = q["options"][:]
    correct_text = options[0]
    random.shuffle(options)

    payload = {
        "chat_id": CHANNEL,
        "question": q["q"],
        "options": options,
        "type": "quiz",
        "correct_option_id": options.index(correct_text),
        "is_anonymous": True,  # القنوات لازم تكون مجهولة
    }
    if q.get("explanation"):
        payload["explanation"] = q["explanation"]

    resp = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendPoll", json=payload, timeout=30
    )
    result = resp.json()
    if not result.get("ok"):
        raise RuntimeError(f"تليجرام رجّع خطأ: {result.get('description')}")

    used.add(idx)
    save_state({"used": sorted(used)})
    print(f"[{datetime.now(TZ):%Y-%m-%d %H:%M}] تم نشر السؤال: {q['q']}")


def post_batch(count):
    """ينشر count سؤال ورا بعض، مع فاصل صغير بينهم."""
    for i in range(count):
        post_quiz()
        if i < count - 1:
            time.sleep(3)


def seconds_until_next_post():
    hour, minute = map(int, POST_TIME.split(":"))
    now = datetime.now(TZ)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds(), target


def main():
    if not TOKEN or not CHANNEL:
        sys.exit("لازم تحدد BOT_TOKEN و CHANNEL_ID كمتغيرات بيئة (شوف README.md)")

    count = POST_COUNT
    if "--count" in sys.argv:
        count = int(sys.argv[sys.argv.index("--count") + 1])

    if "--once" in sys.argv:
        post_batch(count)
        return

    print(f"البوت شغال. النشر اليومي الساعة {POST_TIME} ({TZ.key}) — {count} أسئلة")
    while True:
        wait, target = seconds_until_next_post()
        print(f"النشر القادم: {target:%Y-%m-%d %H:%M}")
        time.sleep(wait)
        try:
            post_batch(count)
        except Exception as e:  # ما منوقف البوت بسبب خطأ مؤقت
            print(f"صار خطأ: {e}")
        time.sleep(60)


if __name__ == "__main__":
    main()
