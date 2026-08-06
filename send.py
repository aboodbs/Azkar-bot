import json
import os
import random
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

TZ = ZoneInfo(os.environ.get("TIMEZONE", "Asia/Amman"))
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL_ID = os.environ["TELEGRAM_CHANNEL_ID"]

CONFIG_PATH = "azkar.json"
STATE_PATH = "state.json"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    resp = requests.post(
        url,
        data={"chat_id": CHANNEL_ID, "text": f"<b>{text}</b>", "parse_mode": "HTML"},
    )
    if resp.status_code != 200:
        print("TELEGRAM ERROR RESPONSE:", resp.text)
    resp.raise_for_status()


def log_send(state, kind, text):
    log = state.setdefault("log", [])
    preview = text.replace("\n", " ")[:60]
    log.append(
        {
            "time": datetime.now(TZ).strftime("%Y-%m-%d %H:%M"),
            "kind": kind,
            "preview": preview,
        }
    )
    state["log"] = log[-20:]


def next_from_queue(config, state, list_key, queue_key):
    items = config[list_key]
    queue = state.get(queue_key) or []
    if not queue:
        queue = list(range(len(items)))
        random.shuffle(queue)
    idx = queue.pop(0)
    state[queue_key] = queue
    return items[idx]


def main():
    config = load_json(CONFIG_PATH)
    state = load_json(STATE_PATH)
    sent_special = state.setdefault("sent_special", {})

    if state.get("paused"):
        return

    now = datetime.now(TZ)
    today_str = now.strftime("%Y-%m-%d")
    hhmm = now.strftime("%H:%M")
    weekday = now.weekday()  # Monday=0 ... Sunday=6

    is_friday = weekday == 4
    is_sunday = weekday == 6
    is_wednesday = weekday == 2

    # 1) أول رسالة يوم الجمعة (مرة وحدة كل جمعة)
    if is_friday and sent_special.get("friday_first") != today_str:
        send_message(config["friday_first_message"])
        log_send(state, "friday_first", config["friday_first_message"])
        sent_special["friday_first"] = today_str
        save_state(state)
        return

    # 2) رسالة الفجر اليومية (مرة وحدة كل يوم)
    if (
        hhmm >= config["fajr_time"]
        and sent_special.get("fajr", "") != today_str
    ):
        send_message(config["fajr_message"])
        log_send(state, "fajr", config["fajr_message"])
        sent_special["fajr"] = today_str
        save_state(state)
        return

    # 3) رسالة العصر اليومية (مرة وحدة كل يوم)
    if (
        hhmm >= config["asr_time"]
        and sent_special.get("asr", "") != today_str
    ):
        send_message(config["asr_message"])
        log_send(state, "asr", config["asr_message"])
        sent_special["asr"] = today_str
        save_state(state)
        return

    # 4) رسالة مساء الأحد (مرة وحدة كل أحد)
    if (
        is_sunday
        and hhmm >= config["sunday_evening_time"]
        and sent_special.get("sunday_evening") != today_str
    ):
        send_message(config["sunday_evening_message"])
        log_send(state, "sunday_evening", config["sunday_evening_message"])
        sent_special["sunday_evening"] = today_str
        save_state(state)
        return

    # 5) رسالة مساء الأربعاء (مرة وحدة كل أربعاء)
    if (
        is_wednesday
        and hhmm >= config["wednesday_evening_time"]
        and sent_special.get("wednesday_evening") != today_str
    ):
        send_message(config["wednesday_evening_message"])
        log_send(state, "wednesday_evening", config["wednesday_evening_message"])
        sent_special["wednesday_evening"] = today_str
        save_state(state)
        return

    # 6) باقي الأوقات: أذكار عشوائية بدون تكرار لحد ما تخلص القائمة
    if is_friday and hhmm < config["friday_maghrib_time"]:
        text = next_from_queue(config, state, "friday_azkar", "friday_queue")
    else:
        text = next_from_queue(config, state, "azkar", "general_queue")

    send_message(text)
    log_send(state, "azkar", text)
    save_state(state)


if __name__ == "__main__":
    main()
